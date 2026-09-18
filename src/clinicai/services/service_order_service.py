"""Ordering services on a visit — what LUOTKHAM-05 produces.

The doctor picks services; each one is performed by a node the catalogue names
(service_price.node_code), and ordering creates work in that node's room. The
rules that decide which room, whether a service may be ordered at all, and how
several ultrasounds collapse into one visit to the ultrasound room all live in
SQL (order_services), for the same reason instantiation does: they must hold
whoever calls them, and the backend bypasses RLS.

Ordering deliberately does NOT complete LUOTKHAM-05. A doctor often orders,
looks at something, and orders again; closing the step on the first submit would
force her to reopen it, and there is no reopen command. She completes the step
from her board when she is done.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.route_derivation import derive_route
from clinicai.services.thu_ky_bac_si import (
    bac_si_cua_thu_ky,
    kiem_thu_ky_duoc_lam,
)

logger = structlog.get_logger()

#: Bác sĩ duyệt chỉ định. Cùng tập vai `prepare_prescription_write` coi là bác sĩ.
PHYSICIAN_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})


class ServiceOrderService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def catalogue(self, *, identity: StaffIdentity) -> list[dict[str, object]]:
        """Orderable services for this clinic.

        Services with no node_code are returned but marked orderable=False, so
        the picker can show them greyed with a reason instead of hiding them —
        a service that has vanished from the list is reported as a bug, while a
        service that is visibly not yet configured is reported as configuration.
        """
        rows = await self._pool.fetch(
            """
            SELECT s.service_code,
                   s.name,
                   s."group",
                   s.category,
                   s.unit_price,
                   s.node_code,
                   n.name AS node_name,
                   n.workspace
              FROM service_price s
              LEFT JOIN node_definition n
                ON n.clinic_id = s.clinic_id AND n.code = s.node_code
             WHERE s.clinic_id = $1::uuid AND s.active
             ORDER BY s.node_code NULLS LAST, s.name
            """,
            identity.clinic_id,
        )
        return [
            {
                "service_code": r["service_code"],
                "name": r["name"],
                "group": r["group"],
                "category": r["category"],
                "unit_price": float(r["unit_price"]) if r["unit_price"] else None,
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "workspace": r["workspace"],
                "orderable": r["node_code"] is not None,
            }
            for r in rows
        ]

    async def duplicates(
        self,
        *,
        visit_id: str,
        codes: list[str],
        identity: StaffIdentity,
        days: int = 30,
    ) -> list[dict[str, object]]:
        """Which of these the patient already had ordered recently."""
        if not codes:
            return []
        patient_id = await self._pool.fetchval(
            "SELECT clinic_patient_id FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            identity.clinic_id,
        )
        if patient_id is None:
            raise NotFoundError("Không tìm thấy lượt khám")

        rows = await self._pool.fetch(
            "SELECT service_code, name, ordered_at "
            "FROM recent_duplicate_services($1::uuid, $2::uuid, $3::text[], $4)",
            identity.clinic_id,
            patient_id,
            codes,
            days,
        )
        return [
            {
                "service_code": r["service_code"],
                "name": r["name"],
                "ordered_at": r["ordered_at"],
            }
            for r in rows
        ]

    async def create(
        self, *, visit_id: str, codes: list[str], identity: StaffIdentity
    ) -> list[dict[str, object]]:
        """Order the services. Returns one row per room the work landed in.

        THƯ KÝ Y KHOA KHÔNG TẠO VIỆC THẬT (Tuyền chốt 15/09/2026): thư ký nhập
        theo lời bác sĩ đọc thì đi vào bản nháp (`save_draft`), bác sĩ duyệt mới
        thành việc ở phòng thực hiện. Router gọi `save_draft` cho vai TKYK;
        chặn ở đây nữa để không đường gọi nào khác lọt qua.
        """
        if identity.co_vai({ClinicRole.TKYK}):
            raise SafetyGateError(
                "Thư ký y khoa nhập chỉ định vào bản nháp — bác sĩ duyệt mới gửi phòng"
            )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # SERIALISE PER VISIT, INSIDE THE TRANSACTION.
                #
                # order_services() avoids creating a second work item for a node
                # with `WHERE NOT EXISTS (SELECT 1 FROM existing ...)`. That reads
                # and writes in one statement but nothing stands behind it: two
                # overlapping orders both evaluate "not there yet" and both
                # insert. A doctor double-clicking "Chỉ định", or a doctor and a
                # secretary ordering at once, gets the room queue twice.
                #
                # A unique index on (visit_id, node_code) would be the usual
                # answer and is the wrong one here: a visit may legitimately
                # repeat a node — two ultrasounds in one session — so the index
                # would block correct work to stop incorrect work.
                #
                # The advisory lock releases when this transaction ends, and is
                # the same mechanism check_in_appointment uses so two
                # receptionists cannot hand out one queue number.
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                try:
                    rows = await conn.fetch(
                        "SELECT * FROM order_services("
                        "$1::uuid, $2::uuid, $3::text[], $4::uuid, $5::text)",
                        identity.clinic_id,
                        visit_id,
                        codes,
                        identity.staff_id,
                        identity.role.value,
                    )
                except asyncpg.RaiseError as exc:
                    # The function raises with a message written for a clinician
                    # — it names the service that cannot be ordered. Passing it
                    # through beats replacing it with a generic 409.
                    raise ConflictError(str(exc)) from exc

                await _sync_route(conn, visit_id=visit_id, identity=identity)

        logger.info(
            "services_ordered",
            visit_id=visit_id,
            services=len(codes),
            rooms=len(rows),
            by_staff_id=identity.staff_id,
        )
        return [
            {
                "node_code": r["out_node_code"],
                "work_item_id": str(r["out_work_item_id"]),
                "service_count": r["out_service_count"],
                "created": r["out_created"],
            }
            for r in rows
        ]

    # ── Nháp chỉ định thư ký nhập, bác sĩ duyệt ────────────────────────────

    async def _visit_mo(
        self,
        conn: asyncpg.Connection,
        visit_id: str,
        clinic_id: str,
        identity: StaffIdentity | None = None,
    ) -> Any:
        visit = await conn.fetchrow(
            "SELECT visit_id, attending_doctor_id, closed_at FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            clinic_id,
        )
        if visit is None:
            raise NotFoundError("Không tìm thấy lượt khám")
        if visit["closed_at"] is not None:
            raise ConflictError("Lượt khám đã đóng — không nhập chỉ định được nữa")
        if identity is not None:
            # Thư ký chỉ nhập cho bác sĩ mình được phân (20260915000020).
            kiem_thu_ky_duoc_lam(
                await bac_si_cua_thu_ky(conn, identity),
                str(visit["attending_doctor_id"])
                if visit["attending_doctor_id"]
                else None,
            )
        return visit

    async def _ma_hop_le(
        self, conn: asyncpg.Connection, codes: list[str], clinic_id: str
    ) -> list[str]:
        """Bỏ trùng giữ thứ tự; mọi mã phải là dịch vụ đang bán và có phòng."""
        sach: list[str] = []
        for code in codes:
            c = (code or "").strip()
            if c and c not in sach:
                sach.append(c)
        if not sach:
            return sach
        rows = await conn.fetch(
            "SELECT service_code, node_code FROM service_price "
            "WHERE clinic_id = $1::uuid AND active AND service_code = ANY($2::text[])",
            clinic_id,
            sach,
        )
        co_phong = {r["service_code"] for r in rows if r["node_code"]}
        thieu = [c for c in sach if c not in co_phong]
        if thieu:
            raise ValidationError(
                "Dịch vụ chưa bán hoặc chưa cấu hình phòng thực hiện: "
                + ", ".join(thieu)
            )
        return sach

    async def _nhap_mo(
        self, conn: asyncpg.Connection, visit_id: str, clinic_id: str
    ) -> Any:
        return await conn.fetchrow(
            """
            SELECT id, service_codes, recorded_by, version
              FROM service_order_draft
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND approved_at IS NULL AND discarded_at IS NULL
               FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )

    async def get_draft(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, object] | None:
        """Bản nháp đang chờ duyệt, kèm tên dịch vụ và người nhập."""
        if not identity.co_vai({*PHYSICIAN_ROLES, ClinicRole.TKYK}):
            raise SafetyGateError("Chỉ bác sĩ và thư ký y khoa xem chỉ định chờ duyệt")
        if identity.co_vai({ClinicRole.TKYK}):
            bac_si_luot = await self._pool.fetchval(
                "SELECT attending_doctor_id::text FROM visit"
                " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
                visit_id,
                identity.clinic_id,
            )
            kiem_thu_ky_duoc_lam(
                await bac_si_cua_thu_ky(self._pool, identity), bac_si_luot
            )
        row = await self._pool.fetchrow(
            """
            SELECT d.id, d.version, d.service_codes, d.updated_at,
                   d.recorded_by, st.full_name AS recorded_by_name
              FROM service_order_draft d
              LEFT JOIN staff st ON st.id = d.recorded_by
             WHERE d.clinic_id = $1::uuid AND d.visit_id = $2::uuid
               AND d.approved_at IS NULL AND d.discarded_at IS NULL
            """,
            identity.clinic_id,
            visit_id,
        )
        if row is None:
            return None
        names = await self._pool.fetch(
            "SELECT service_code, name, unit_price, node_code FROM service_price "
            "WHERE clinic_id = $1::uuid AND service_code = ANY($2::text[])",
            identity.clinic_id,
            list(row["service_codes"]),
        )
        by_code = {r["service_code"]: r for r in names}
        return {
            "id": str(row["id"]),
            "version": row["version"],
            "updated_at": row["updated_at"].isoformat(),
            "recorded_by": str(row["recorded_by"]),
            "recorded_by_name": row["recorded_by_name"],
            "services": [
                {
                    "service_code": code,
                    "name": by_code[code]["name"] if code in by_code else code,
                    "unit_price": (
                        float(by_code[code]["unit_price"])
                        if code in by_code and by_code[code]["unit_price"]
                        else None
                    ),
                    "node_code": by_code[code]["node_code"]
                    if code in by_code
                    else None,
                }
                for code in row["service_codes"]
            ],
        }

    async def save_draft(
        self,
        *,
        visit_id: str,
        codes: list[str],
        identity: StaffIdentity,
        replace: bool = False,
        expected_version: int | None = None,
    ) -> dict[str, object] | None:
        """Thư ký nhập chỉ định vào bản nháp của lượt.

        Mặc định GỘP vào bản nháp đang mở (bác sĩ đọc thêm dịch vụ thì thư ký
        bấm thêm). `replace=True` là sửa lại cả danh sách (bỏ bớt dịch vụ) và bắt
        buộc `expected_version` — hai người cùng sửa thì người sau phải thấy bản
        mới trước. Danh sách rỗng khi replace = bỏ nháp.
        """
        if not identity.co_vai({*PHYSICIAN_ROLES, ClinicRole.TKYK}):
            raise SafetyGateError("Chỉ bác sĩ và thư ký y khoa nhập chỉ định")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                await self._visit_mo(conn, visit_id, identity.clinic_id, identity)
                ma = await self._ma_hop_le(conn, codes, identity.clinic_id)
                nhap = await self._nhap_mo(conn, visit_id, identity.clinic_id)
                if replace:
                    if nhap is None or expected_version != nhap["version"]:
                        raise ConflictError(
                            "Bản nháp chỉ định vừa thay đổi — tải lại rồi sửa"
                        )
                    if not ma:
                        await conn.execute(
                            "UPDATE service_order_draft SET discarded_at = now(), "
                            "discarded_by = $3::uuid, "
                            "discard_reason = 'THU_KY_XOA_HET' "
                            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                            nhap["id"],
                            identity.clinic_id,
                            identity.staff_id,
                        )
                        event, draft_id = "service_order.draft_discarded", nhap["id"]
                    else:
                        await conn.execute(
                            "UPDATE service_order_draft SET service_codes = $3::text[] "
                            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                            nhap["id"],
                            identity.clinic_id,
                            ma,
                        )
                        event, draft_id = "service_order.draft_saved", nhap["id"]
                else:
                    if not ma:
                        raise ValidationError("Chưa chọn dịch vụ nào")
                    if nhap is None:
                        draft_id = await conn.fetchval(
                            """
                            INSERT INTO service_order_draft
                                (clinic_id, visit_id, service_codes, recorded_by)
                            VALUES ($1::uuid, $2::uuid, $3::text[], $4::uuid)
                            RETURNING id
                            """,
                            identity.clinic_id,
                            visit_id,
                            ma,
                            identity.staff_id,
                        )
                    else:
                        gop = list(nhap["service_codes"]) + [
                            c for c in ma if c not in nhap["service_codes"]
                        ]
                        await conn.execute(
                            "UPDATE service_order_draft SET service_codes = $3::text[] "
                            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                            nhap["id"],
                            identity.clinic_id,
                            gop,
                        )
                        draft_id = nhap["id"]
                    event = "service_order.draft_saved"
                await record_event(
                    conn,
                    event_type=event,
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:service-order-draft",
                    payload={"draft_id": str(draft_id), "service_codes": ma},
                )
        return await self.get_draft(visit_id=visit_id, identity=identity)

    async def approve_draft(
        self, *, visit_id: str, expected_version: int, identity: StaffIdentity
    ) -> list[dict[str, object]]:
        """Bác sĩ duyệt ĐÚNG bản nháp đang xem → tạo việc ở phòng thực hiện.

        `expected_version` là phiên bản bác sĩ đang nhìn trên màn: thư ký vừa
        sửa sau đó thì từ chối, bác sĩ phải thấy bản mới rồi mới duyệt
        (CONTEXT v1.0: duyệt đúng phiên bản đã xem). Việc thật được tạo bằng
        CHÍNH order_services với danh tính bác sĩ, trong cùng giao dịch với việc
        đánh dấu đã duyệt — không có lúc nháp đã duyệt mà phòng chưa có việc.
        """
        if not identity.co_vai(PHYSICIAN_ROLES):
            raise SafetyGateError("Chỉ bác sĩ mới duyệt chỉ định thư ký đã nhập")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                visit = await self._visit_mo(
                    conn, visit_id, identity.clinic_id, identity
                )
                if (
                    visit["attending_doctor_id"] is not None
                    and str(visit["attending_doctor_id"]) != identity.staff_id
                ):
                    raise SafetyGateError(
                        "Lượt khám này thuộc bác sĩ khác — không thể duyệt chỉ định"
                    )
                nhap = await self._nhap_mo(conn, visit_id, identity.clinic_id)
                if nhap is None:
                    raise ConflictError("Không có chỉ định nháp đang chờ duyệt")
                if nhap["version"] != expected_version:
                    raise ConflictError(
                        "Thư ký vừa sửa chỉ định nháp — xem lại bản mới trước khi duyệt"
                    )
                codes = list(nhap["service_codes"])
                try:
                    rows = await conn.fetch(
                        "SELECT * FROM order_services("
                        "$1::uuid, $2::uuid, $3::text[], $4::uuid, $5::text)",
                        identity.clinic_id,
                        visit_id,
                        codes,
                        identity.staff_id,
                        identity.role.value,
                    )
                except asyncpg.RaiseError as exc:
                    raise ConflictError(str(exc)) from exc
                await conn.execute(
                    "UPDATE service_order_draft SET approved_at = now(), "
                    "approved_by = $3::uuid "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    nhap["id"],
                    identity.clinic_id,
                    identity.staff_id,
                )
                await record_event(
                    conn,
                    event_type="service_order.draft_approved",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:service-order-draft",
                    payload={
                        "draft_id": str(nhap["id"]),
                        "recorded_by": str(nhap["recorded_by"]),
                        "service_codes": codes,
                        "version": expected_version,
                    },
                )
                await _sync_route(conn, visit_id=visit_id, identity=identity)
        logger.info(
            "service_order_draft_approved",
            visit_id=visit_id,
            services=len(codes),
            by_staff_id=identity.staff_id,
        )
        return [
            {
                "node_code": r["out_node_code"],
                "work_item_id": str(r["out_work_item_id"]),
                "service_count": r["out_service_count"],
                "created": r["out_created"],
            }
            for r in rows
        ]

    async def discard_draft(
        self,
        *,
        visit_id: str,
        expected_version: int,
        reason: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Bỏ bản nháp (bác sĩ không duyệt, hoặc thư ký nhập nhầm cả bản)."""
        if not identity.co_vai({*PHYSICIAN_ROLES, ClinicRole.TKYK}):
            raise SafetyGateError("Chỉ bác sĩ và thư ký y khoa bỏ chỉ định nháp")
        ly_do = (reason or "").strip() or None
        if identity.co_vai(PHYSICIAN_ROLES) and not ly_do:
            raise ValidationError(
                "Bác sĩ bỏ chỉ định nháp thì ghi lý do để thư ký biết"
            )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                await self._visit_mo(conn, visit_id, identity.clinic_id, identity)
                nhap = await self._nhap_mo(conn, visit_id, identity.clinic_id)
                if nhap is None or nhap["version"] != expected_version:
                    raise ConflictError("Bản nháp chỉ định vừa thay đổi — tải lại")
                await conn.execute(
                    "UPDATE service_order_draft SET discarded_at = now(), "
                    "discarded_by = $3::uuid, discard_reason = $4 "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    nhap["id"],
                    identity.clinic_id,
                    identity.staff_id,
                    ly_do,
                )
                await record_event(
                    conn,
                    event_type="service_order.draft_discarded",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:service-order-draft",
                    payload={"draft_id": str(nhap["id"]), "has_reason": bool(ly_do)},
                )

    # ── Chỉ định là DANH SÁCH TÍCH của bác sĩ (Tuyền chốt 15/09/2026) ─────────
    #
    # "Bác sĩ tích loại nào thì cứ vậy mà đi khám theo như vậy": màn chỉ định
    # hiện sẵn những dịch vụ đã tích, bỏ tích là bỏ dịch vụ khỏi lượt. Trước bản
    # này bác sĩ không thấy dịch vụ đã chỉ định và không có đường bỏ một dịch vụ
    # — chỉ huỷ cả việc của một phòng.

    async def dang_chi_dinh(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, object]]:
        """Dịch vụ đang tích cho lượt khám, kèm trạng thái việc ở phòng."""
        rows = await self._pool.fetch(
            """
            SELECT s ->> 'service_code' AS service_code,
                   s ->> 'name'         AS name,
                   w.node_code, w.status, w.lan
              FROM work_item w
              JOIN node_definition n
                ON n.clinic_id = w.clinic_id AND n.code = w.node_code
             CROSS JOIN LATERAL jsonb_array_elements(
                   coalesce(w.payload -> 'services', '[]'::jsonb)) AS s
             WHERE w.clinic_id = $1::uuid AND w.visit_id = $2::uuid
               AND w.status <> 'CANCELLED'
             ORDER BY n.name, s ->> 'name'
            """,
            identity.clinic_id,
            visit_id,
        )
        return [dict(r) for r in rows]

    async def bo_chi_dinh(
        self,
        *,
        visit_id: str,
        service_code: str,
        ly_do: str,
        identity: StaffIdentity,
    ) -> dict[str, object]:
        """Bác sĩ bỏ tích một dịch vụ. Việc phòng đó đã bắt đầu thì không bỏ được.

        Huỷ chỉ định BẮT BUỘC lý do (Tuyền chốt 15/09/2026) và chỉ BÁC SĨ CỦA
        LƯỢT (bác sĩ phụ trách) bỏ được — bác sĩ khác không sửa chỉ định của
        đồng nghiệp.
        """
        if not identity.co_vai(PHYSICIAN_ROLES):
            raise SafetyGateError("Chỉ bác sĩ bỏ dịch vụ khỏi chỉ định")
        ly_do_sach = (ly_do or "").strip()
        if not ly_do_sach:
            raise ValidationError("Bỏ dịch vụ khỏi chỉ định phải ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                visit = await self._visit_mo(conn, visit_id, identity.clinic_id)
                if visit["attending_doctor_id"] is not None and str(
                    visit["attending_doctor_id"]
                ) != str(identity.staff_id):
                    raise SafetyGateError(
                        "Chỉ bác sĩ phụ trách lượt khám bỏ được dịch vụ đã chỉ định"
                    )
                item = await conn.fetchrow(
                    """
                    SELECT w.id::text AS id, w.status, w.node_code
                      FROM work_item w
                     WHERE w.clinic_id = $1::uuid AND w.visit_id = $2::uuid
                       AND w.status <> 'CANCELLED'
                       AND EXISTS (
                           SELECT 1 FROM jsonb_array_elements(
                               coalesce(w.payload -> 'services', '[]'::jsonb)) s
                            WHERE s ->> 'service_code' = $3)
                     -- Lần CÒN CHỜ trước (siêu âm lần 2 chờ, lần 1 đã xong).
                     ORDER BY (w.status = 'PENDING') DESC, w.lan DESC
                     LIMIT 1
                       FOR UPDATE
                    """,
                    identity.clinic_id,
                    visit_id,
                    service_code,
                )
                if item is None:
                    raise NotFoundError("Dịch vụ này không có trong chỉ định")
                if item["status"] != "PENDING":
                    raise ConflictError(
                        "Phòng đã bắt đầu hoặc đã làm dịch vụ này — không bỏ được"
                    )
                con_lai = await conn.fetchval(
                    """
                    UPDATE work_item
                       SET payload = jsonb_set(
                               payload, '{services}',
                               coalesce((
                                   SELECT jsonb_agg(s)
                                     FROM jsonb_array_elements(
                                         payload -> 'services') s
                                    WHERE s ->> 'service_code' <> $2), '[]'::jsonb)),
                           status = CASE WHEN EXISTS (
                                        SELECT 1 FROM jsonb_array_elements(
                                            payload -> 'services') s
                                         WHERE s ->> 'service_code' <> $2)
                                    THEN status ELSE 'CANCELLED' END,
                           -- Trạng thái kết thúc phải có giờ kết thúc
                           -- (work_item_finished_when_terminal).
                           finished_at = CASE WHEN EXISTS (
                                        SELECT 1 FROM jsonb_array_elements(
                                            payload -> 'services') s
                                         WHERE s ->> 'service_code' <> $2)
                                    THEN finished_at ELSE now() END,
                           updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $3::uuid
                    RETURNING jsonb_array_length(payload -> 'services')
                    """,
                    item["id"],
                    service_code,
                    identity.clinic_id,
                )
                await record_event(
                    conn,
                    event_type="service_order.removed",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:service-orders",
                    payload={
                        "service_code": service_code,
                        "node_code": item["node_code"],
                        "work_item_id": item["id"],
                        "huy_ca_viec": con_lai == 0,
                        "ly_do": ly_do_sach,
                    },
                )
                await _sync_route(conn, visit_id=visit_id, identity=identity)
        return {"ok": True, "con_lai": con_lai}

    async def charges(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, object]:
        """What this visit owes for, and what has been paid.

        The bill lines come from the work items themselves — every DICHVU node
        carries the services ordered onto it in its payload — because the work
        item IS the order. A separate billing table would be a second truth, and
        the first argument between them would be in front of a patient holding a
        card.

        Amounts are whatever the price list says, INCLUDING nothing: production
        has no prices at all (service_price and drug_catalog are entirely
        unpriced). This returns unit_price as it finds it and reports how many
        lines lack one, so the screen can say so rather than presenting a total
        that quietly means "we could not work it out".
        """
        visit = await self._pool.fetchrow(
            "SELECT visit_id, clinic_patient_id, status FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            identity.clinic_id,
        )
        if visit is None:
            raise NotFoundError("Không tìm thấy lượt khám")

        rows = await self._pool.fetch(
            """
            SELECT w.node_code,
                   w.status AS node_status,
                   n.name   AS node_name,
                   s ->> 'service_code' AS service_code,
                   s ->> 'name'         AS name,
                   (s ->> 'unit_price')::numeric AS unit_price
              FROM work_item w
              JOIN node_definition n
                ON n.clinic_id = w.clinic_id AND n.code = w.node_code
             CROSS JOIN LATERAL jsonb_array_elements(
                   coalesce(w.payload -> 'services', '[]'::jsonb)) AS s
             WHERE w.clinic_id = $2::uuid
               AND w.visit_id = $1::uuid
               AND w.status <> 'CANCELLED'
             ORDER BY n.name, s ->> 'name'
            """,
            visit_id,
            identity.clinic_id,
        )

        # Voided payments are history, not money. They are returned separately
        # so a cashier can see a correction was made without it counting twice.
        paid = await self._pool.fetch(
            """
            SELECT id, kind, status, amount, paid_at, voided_at, void_reason
              FROM payment
             WHERE clinic_id = $2::uuid AND visit_id = $1::uuid
             ORDER BY paid_at NULLS LAST
            """,
            visit_id,
            identity.clinic_id,
        )

        lines = [
            {
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "node_status": r["node_status"],
                "service_code": r["service_code"],
                "name": r["name"],
                "unit_price": float(r["unit_price"]) if r["unit_price"] else None,
            }
            for r in rows
        ]
        unpriced = sum(1 for line in lines if line["unit_price"] is None)
        subtotal = sum(
            float(line["unit_price"] or 0) for line in lines if line["unit_price"]
        )
        collected = sum(float(p["amount"] or 0) for p in paid if p["voided_at"] is None)

        return {
            "visit_id": str(visit["visit_id"]),
            "visit_status": visit["status"],
            "lines": lines,
            "payments": [
                {
                    "id": str(p["id"]),
                    "kind": p["kind"],
                    "status": p["status"],
                    "amount": float(p["amount"] or 0),
                    "paid_at": p["paid_at"],
                    "voided_at": p["voided_at"],
                    "void_reason": p["void_reason"],
                }
                for p in paid
            ],
            "line_count": len(lines),
            # The number that decides whether the total may be shown at all.
            "unpriced_lines": unpriced,
            "subtotal": subtotal,
            "collected": collected,
            "outstanding": subtotal - collected,
        }


async def _sync_route(
    conn: asyncpg.Connection, *, visit_id: str, identity: StaffIdentity
) -> None:
    """Cập nhật tuyến điều phối cho khớp với chỉ định vừa đặt.

    Bảng Trưởng ca đọc "bước kế tiếp" từ `visit_route`, và trước thay đổi này
    tuyến chỉ được ghi khi có người bấm tay — nên trên prod 0/25 lượt khám có
    tuyến, và cột gợi ý trống với mọi bệnh nhân. Chỉ định chính là thứ quyết
    định bệnh nhân phải đi đâu, nên nó ghi luôn tuyến.

    KHÔNG ĐÈ TUYẾN NGƯỜI TA ĐÃ SỬA TAY. Trưởng ca đổi tuyến giữa chừng phải ghi
    lý do (`is_exception`), tức là một quyết định có chủ ý của con người, có khi
    trái với chỉ định — đè lên nó là xoá một quyết định lâm sàng bằng một tác
    dụng phụ.
    """
    manual = await conn.fetchval(
        "SELECT 1 FROM public.visit_route"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL AND is_exception",
        visit_id,
    )
    if manual:
        return

    pending = await conn.fetch(
        "SELECT node_code FROM public.work_item"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND status IN ('PENDING', 'IN_PROGRESS')"
        " ORDER BY created_at",
        identity.clinic_id,
        visit_id,
    )
    templates = await conn.fetch(
        "SELECT steps FROM public.route_template"
        " WHERE clinic_id = $1::uuid AND is_active",
        identity.clinic_id,
    )
    steps = derive_route(
        [r["node_code"] for r in pending],
        [list(t["steps"]) for t in templates],
    )
    if not steps:
        # visit_route_has_steps đòi ít nhất một bước. Không có gì để đi thì
        # không có tuyến — và tuyến cũ (nếu có) vẫn đúng, cứ để nguyên.
        return

    done = await conn.fetchval(
        "SELECT coalesce(array_agg(node_code), '{}') FROM public.work_item"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND status = 'COMPLETED'",
        identity.clinic_id,
        visit_id,
    )
    current = await conn.fetchval(
        "SELECT steps FROM public.visit_route"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL",
        visit_id,
    )
    if current is not None and list(current) == steps:
        # Chỉ định thêm một dịch vụ cùng khoa phòng thì tuyến không đổi. Ghi
        # một dòng y hệt chỉ làm lịch sử tuyến dài ra mà không nói thêm gì.
        return

    await conn.execute(
        "UPDATE public.visit_route SET superseded_at = now()"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL",
        visit_id,
    )
    await conn.execute(
        """
        INSERT INTO public.visit_route
            (clinic_id, visit_id, template_id, steps, kept_steps,
             is_exception, reason, applied_by)
        VALUES ($1::uuid, $2::uuid, NULL, $3, $4, FALSE, $5, $6::uuid)
        """,
        identity.clinic_id,
        visit_id,
        steps,
        list(done or []),
        "Suy ra từ chỉ định của bác sĩ",
        identity.auth_user_id,
    )
