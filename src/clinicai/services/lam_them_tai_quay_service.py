"""LÀM THÊM TẠI QUẦY — nút "+ dịch vụ" ở Tiếp đón và Đo sinh hiệu (Tuyền 01/10/2026).

Sau buổi thực nghiệm thật: "nhiều việc làm luôn được ở bàn đo sinh hiệu mà không
cần bác sĩ chỉ định; khách muốn làm luôn mà đang rảnh bàn, ai lại bắt lên gặp bác
sĩ chỉ định rồi mới xuống làm. Lễ tân chưa tích mà khách muốn lúc đo sinh hiệu
thì đo sinh hiệu tích và làm luôn … QUẢN LÝ ĐIỀU KHIỂN được nút này".

BA LỆNH, MỘT CÂU ĐỌC
  * ``dat`` (AddDeskService / RemoveDeskService) — tick = tạo NGAY một chỉ định
    đã chốt làm (``selection_status = SELECTED``) cho lượt, không qua phiên khám
    (``consultation_id`` NULL, ``nguon_lam_them`` = nơi tick). Từ đó chỉ định đi
    ĐÚNG luồng có sẵn: quầy thu thấy dòng (khách vẫn bỏ được ở quầy), cửa làm
    của FinanceGate (dây ``thu_truoc_khi_lam`` / tick "Làm trước – thu sau"),
    khối Hành trình xếp phòng theo ``phong_lam_duoc`` (sự kiện
    ``service_order.desk_added``), phòng làm thấy khách. Bỏ tick = huỷ chỉ định
    khi CHƯA bắt đầu làm và CHƯA thu tiền; đã làm / đã thu thì báo rõ đi đường
    nào.
  * ``luu_muc`` / ``bo_muc`` (ConfigureDeskServices) — quản lý thêm / bớt / bật /
    tắt / đổi thứ tự / chỗ hiện của từng nút. Quyền ``config.wiring.manage``
    (cùng cửa màn Dây nối).
  * ``nut_cho_luot`` — nút nào hiện ở màn này + nút nào đã tick cho từng lượt.

QUYỀN: tick / bỏ ở Tiếp đón hỏi ``reception.checkin.perform`` (lego Tiếp đón),
ở Đo sinh hiệu hỏi ``vitals.measure`` (lego Sinh hiệu) — hỏi trong CHÍNH giao
dịch của lệnh. Người đo bỏ được cái lễ tân tick và ngược lại (phòng khám mở, sửa
sai được).

TRANH CHẤP: lệnh khoá dòng ``visit`` trước (như mọi lệnh trên lượt), và Postgres
giữ "một nút một chỉ định sống mỗi lượt" bằng chỉ mục duy nhất từng phần
(``uq_service_order_lam_them_song``) — lễ tân và điều dưỡng bấm cùng lúc thì
người sau nhận lại chỉ định của người trước.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import LamThemDaBo, LamThemDaThem
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import cap_nhat_vi_tri
from clinicai.services.lam_them_tai_quay_config import LamThemCauHinhMixin
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

ORIGIN = "api:lam-them-tai-quay"

#: Nơi bấm → quyền cần có. Thêm một màn có nút = thêm một dòng ở đây.
QUYEN_THEO_NOI: dict[str, str] = {
    "tiep_don": "reception.checkin.perform",
    "sinh_hieu": "vitals.measure",
}
#: Nhãn nguồn cho màn ("làm thêm tại quầy tiếp đón").
NHAN_NGUON: dict[str, str] = {
    "tiep_don": "quầy tiếp đón",
    "sinh_hieu": "bàn sinh hiệu",
}

#: Trần số lượt một lần đọc — màn tiếp đón cả ngày chỉ vài chục lượt.
MAX_LUOT = 300

_TRANG_THAI_DA_LAM = frozenset({"in_progress", "performed", "not_performed"})


def doc_noi(value: Any) -> str | None:
    """'tiep_don' / 'sinh_hieu'; rác → None (không ném)."""
    if isinstance(value, str) and value.strip() in QUYEN_THEO_NOI:
        return value.strip()
    return None


def nhan_lam_them(nguon: str | None) -> str | None:
    """Câu hiện ở hành trình / quầy thu: "Làm thêm tại quầy tiếp đón"."""
    if not nguon:
        return None
    return "Làm thêm tại " + NHAN_NGUON.get(nguon, "quầy")


def _doc_ma_luot(value: Any) -> list[str]:
    """'id1,id2' hoặc danh sách → mã hợp lệ, bỏ trùng, bỏ rác (không ném)."""
    if isinstance(value, str):
        tho = value.split(",")
    elif isinstance(value, list | tuple):
        tho = list(value)
    else:
        return []
    ra: list[str] = []
    for x in tho:
        try:
            ma = _uuid(str(x).strip(), "")
        except ValidationError:
            continue
        if ma not in ra:
            ra.append(ma)
    return ra[:MAX_LUOT]


def _ma_dich_vu(value: Any) -> str:
    ma = value.strip() if isinstance(value, str) else ""
    if not ma or len(ma) > 64:
        raise ValidationError("Mã dịch vụ không hợp lệ.")
    return ma


# Chỉ định chưa huỷ của một dịch vụ trong lượt (cả bác sĩ lẫn quầy). Giữ cả dòng
# đã xong / không làm để nút không quay về dấu "+" và tạo trùng lần đã kết thúc.
_SQL_SONG = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_code,
       o.service_name, o.nguon_lam_them, o.exec_status, o.selection_status,
       o.execution_status,
       o.routing_status, o.room_id::text AS room_id, o.version,
       r.name AS phong,
       nb.full_name AS nguoi_tick,
       EXISTS (
           SELECT 1 FROM payment_bill_line bl
             JOIN payment_cycle c
               ON c.clinic_id = bl.clinic_id
              AND c.payment_cycle_id = bl.payment_cycle_id
            WHERE bl.clinic_id = o.clinic_id
              AND bl.source_type = 'service_order'
              AND bl.source_id = o.id::text
              AND bl.billing_owner = 'CLINIC'
              AND c.status IN ('PENDING_VERIFICATION', 'PAID')) AS da_thu
  FROM service_order o
  LEFT JOIN clinic_room r ON r.id = o.room_id
  LEFT JOIN staff nb ON nb.id = o.recorded_by
 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
   AND o.service_code = ANY($3::text[])
   AND o.exec_status NOT IN ('draft', 'cancelled')
   AND coalesce(o.execution_status, 'PENDING') <> 'CANCELLED'
 ORDER BY (o.nguon_lam_them IS NOT NULL) DESC, o.created_at
"""


def _da_bat_dau(o: asyncpg.Record | dict[str, Any]) -> bool:
    return (o["execution_status"] or "PENDING") != "PENDING" or (
        o["exec_status"] in _TRANG_THAI_DA_LAM
    )


def trang_thai_nut(o: dict[str, Any] | None, state_revision: int = 0) -> dict[str, Any]:
    """Trạng thái MỘT nút cho một lượt — hàm thuần, màn chỉ vẽ.

    ``chon`` = đang tick; ``doi_duoc`` = bấm được (tick hoặc bỏ); ``ghi_chu`` nói
    vì sao không bỏ được / ai đã chỉ định.
    """
    if o is None:
        return {
            "chon": False,
            "doi_duoc": True,
            "order_id": None,
            "order_version": None,
            "state_revision": state_revision,
            "ghi_chu": None,
        }
    la_quay = bool(o.get("nguon_lam_them"))
    if not la_quay:
        # Bác sĩ đã chỉ định dịch vụ này — quầy không chồng thêm, cũng không bỏ hộ.
        if o.get("selection_status") == "NOT_SELECTED":
            return {
                "chon": False,
                "doi_duoc": True,
                "order_id": None,
                "order_version": None,
                "state_revision": state_revision,
                "ghi_chu": None,
            }
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "order_version": o.get("version"),
            "state_revision": state_revision,
            "ghi_chu": "bác sĩ đã chỉ định",
        }
    if o.get("selection_status") == "NOT_SELECTED":
        # Khách bỏ ở quầy thu → nút về chưa tick; tick lại là chốt lại.
        return {
            "chon": False,
            "doi_duoc": True,
            "order_id": o["id"],
            "order_version": o.get("version"),
            "state_revision": state_revision,
            "ghi_chu": None,
        }
    ket_thuc = o.get("execution_status")
    if ket_thuc in {"COMPLETED", "NOT_PERFORMED"}:
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "order_version": o.get("version"),
            "state_revision": state_revision,
            "ghi_chu": (
                "đã làm xong" if ket_thuc == "COMPLETED" else "đã ghi không làm"
            ),
        }
    if _da_bat_dau(o):
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "order_version": o.get("version"),
            "state_revision": state_revision,
            "ghi_chu": "đang làm" + (f" ở {o['phong']}" if o.get("phong") else ""),
        }
    if o.get("da_thu"):
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "order_version": o.get("version"),
            "state_revision": state_revision,
            "ghi_chu": "đã thu tiền — bỏ ở quầy thu",
        }
    return {
        "chon": True,
        "doi_duoc": True,
        "order_id": o["id"],
        "order_version": o.get("version"),
        "state_revision": state_revision,
        "ghi_chu": nhan_lam_them(o.get("nguon_lam_them")),
    }


class LamThemTaiQuayService(LamThemCauHinhMixin):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc cho màn quầy ────────────────────────────────────────────────────

    @staticmethod
    async def _nut_dang_hien(
        conn: asyncpg.Connection, cid: str, noi: str
    ) -> list[dict[str, Any]]:
        cot = "o_tiep_don" if noi == "tiep_don" else "o_sinh_hieu"
        rows = await conn.fetch(
            f"""
            SELECT l.service_code, coalesce(l.nhan, dv.ten) AS nhan, dv.ten, dv.gia
              FROM lam_them_tai_quay l
              JOIN LATERAL (
                   SELECT s.name AS ten, s.unit_price AS gia
                     FROM service_price s
                    WHERE s.clinic_id = l.clinic_id AND s."group" = 'dich_vu'
                      AND s.service_code = l.service_code AND s.active
                      AND s.node_code IS NOT NULL
                    ORDER BY s.unit_price NULLS LAST LIMIT 1) dv ON true
             WHERE l.clinic_id = $1::uuid AND l.bat AND l.{cot}
             ORDER BY l.thu_tu, l.service_code
            """,
            cid,
        )
        return [
            {
                "service_code": r["service_code"],
                "nhan": r["nhan"],
                "ten": r["ten"],
                "gia": int(r["gia"]) if r["gia"] is not None else None,
            }
            for r in rows
        ]

    async def nut_cho_luot(
        self, *, identity: StaffIdentity, noi: Any, visit_ids: Any
    ) -> dict[str, Any]:
        """Nút hiện ở màn ``noi`` + trạng thái từng nút cho từng lượt.

        Không có quyền của màn ấy → không có nút (không lỗi: màn vẫn vẽ phần
        còn lại). Mã lượt rác bị bỏ qua.
        """
        n = doc_noi(noi)
        if n is None:
            raise ValidationError("Nơi bấm không hợp lệ.")
        cid = identity.clinic_id
        ids = _doc_ma_luot(visit_ids)
        async with self._pool.acquire() as conn:
            if not await can(conn, identity, QUYEN_THEO_NOI[n]):
                return {"noi": n, "nut": [], "luot": {}}
            nut = await self._nut_dang_hien(conn, cid, n)
            luot: dict[str, dict[str, Any]] = {}
            if nut and ids:
                # Lượt còn mở (chưa check-out) mới bấm được. `INCOMPLETE` là
                # khách đã về khi khám dở, cố ý không hiện nút làm thêm.
                mo = {
                    r["visit_id"]
                    for r in await conn.fetch(
                        "SELECT visit_id::text AS visit_id FROM visit"
                        " WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])"
                        " AND status IN ('OPEN', 'IN_PROGRESS')"
                        " AND closed_at IS NULL",
                        cid,
                        ids,
                    )
                }
                song: dict[tuple[str, str], dict[str, Any]] = {}
                for r in await conn.fetch(
                    _SQL_SONG, cid, ids, [x["service_code"] for x in nut]
                ):
                    song.setdefault((r["visit_id"], r["service_code"]), dict(r))
                revision = {
                    (r["visit_id"], r["service_code"]): int(r["revision"])
                    for r in await conn.fetch(
                        "SELECT visit_id::text AS visit_id, service_code, revision"
                        " FROM lam_them_tai_quay_revision"
                        " WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])"
                        " AND service_code = ANY($3::text[])",
                        cid,
                        ids,
                        [x["service_code"] for x in nut],
                    )
                }
                for vid in ids:
                    luot[vid] = {
                        x["service_code"]: {
                            **trang_thai_nut(
                                song.get((vid, x["service_code"])),
                                revision.get((vid, x["service_code"]), 0),
                            ),
                            "luot_mo": vid in mo,
                        }
                        for x in nut
                    }
        return {"noi": n, "nut": nut, "luot": luot}

    # ── Lệnh tick / bỏ tick ─────────────────────────────────────────────────

    async def dat(
        self,
        *,
        identity: StaffIdentity,
        visit_id: Any,
        service_code: Any,
        noi: Any,
        chon: Any,
        expected_order_id: Any = None,
        expected_version: Any = None,
        expected_state_revision: Any = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Tick (``chon`` = True) hoặc bỏ tick một nút cho một lượt.

        Chạy lại được: tick khi đã tick / bỏ khi đã bỏ → trả trạng thái hiện tại,
        không lỗi, không sự kiện thứ hai.
        """
        n = doc_noi(noi)
        if n is None:
            raise ValidationError("Nơi bấm không hợp lệ.")
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        ma = _ma_dich_vu(service_code)
        cid = identity.clinic_id
        if not idempotency_key:
            raise ValidationError("Thiếu khoá gửi lại cho lệnh làm thêm tại quầy.")
        expected_oid = (
            _uuid(expected_order_id, "Mã chỉ định cũ không hợp lệ.")
            if expected_order_id
            else None
        )
        try:
            expected_ver = (
                int(expected_version) if expected_version is not None else None
            )
        except (TypeError, ValueError):
            raise ValidationError("Phiên bản chỉ định cũ không hợp lệ.") from None
        try:
            expected_state = int(expected_state_revision)
        except (TypeError, ValueError):
            raise ValidationError("Phiên bản nút làm thêm không hợp lệ.") from None
        if expected_state < 0:
            raise ValidationError("Phiên bản nút làm thêm không hợp lệ.")
        payload = {
            "visit_id": vid,
            "service_code": ma,
            "noi": n,
            "chon": bool(chon),
            "expected_order_id": expected_oid,
            "expected_version": expected_ver,
            "expected_state_revision": expected_state,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_THEO_NOI[n])
            cached = await bien_nhan_doc(
                conn, identity, "desk_service.set", idempotency_key, payload
            )
            if cached is not None:
                return cached
            luot = await khoa_luot(conn, cid, vid)
            if luot["closed_at"] is not None:
                raise LuotKhamConflictError(
                    "VISIT_CHECKED_OUT", "Khách đã check-out — không thêm dịch vụ."
                )
            await conn.execute(
                "INSERT INTO lam_them_tai_quay_revision"
                " (clinic_id, visit_id, service_code) VALUES ($1::uuid, $2::uuid, $3)"
                " ON CONFLICT (clinic_id, visit_id, service_code) DO NOTHING",
                cid,
                vid,
                ma,
            )
            state_revision = int(
                await conn.fetchval(
                    "SELECT revision FROM lam_them_tai_quay_revision"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND service_code = $3 FOR UPDATE",
                    cid,
                    vid,
                    ma,
                )
            )
            ds = [
                dict(r)
                for r in await conn.fetch(
                    _SQL_SONG + " FOR UPDATE OF o", cid, [vid], [ma]
                )
            ]
            cua_quay = next((o for o in ds if o["nguon_lam_them"]), None)
            dang_hien = cua_quay or next(
                (
                    o
                    for o in ds
                    if not o["nguon_lam_them"]
                    and o["selection_status"] != "NOT_SELECTED"
                ),
                None,
            )
            hien_oid = dang_hien["id"] if dang_hien else None
            hien_ver = int(dang_hien["version"]) if dang_hien else None
            if state_revision != expected_state:
                # Hai người cùng tick: ý định đã đạt thì nhận trạng thái hiện tại.
                if (
                    bool(chon)
                    and cua_quay is not None
                    and cua_quay["selection_status"] != "NOT_SELECTED"
                ):
                    kq = {
                        "ok": True,
                        "changed": False,
                        "order_id": hien_oid,
                        "order_version": hien_ver,
                        "state_revision": state_revision,
                    }
                    await bien_nhan_ghi(
                        conn,
                        identity,
                        "desk_service.set",
                        idempotency_key,
                        payload,
                        str(hien_oid),
                        kq,
                    )
                    return kq
                raise LuotKhamConflictError(
                    "STALE_DESK_SERVICE",
                    "Dịch vụ vừa được người khác thay đổi — đã tải lại, vui lòng"
                    " xem trạng thái mới rồi bấm lại.",
                )
            if (hien_oid, hien_ver) != (expected_oid, expected_ver):
                raise LuotKhamConflictError(
                    "STALE_DESK_SERVICE",
                    "Dịch vụ vừa được người khác thay đổi — đã tải lại, vui lòng"
                    " xem trạng thái mới rồi bấm lại.",
                )
            if bool(chon):
                kq = await self._tick(conn, identity, vid, ma, n, ds, cua_quay)
            else:
                kq = await self._bo(conn, identity, vid, ma, n, cua_quay)
            if kq.get("changed"):
                state_revision = int(
                    await conn.fetchval(
                        "UPDATE lam_them_tai_quay_revision"
                        " SET revision = revision + 1, updated_at = now()"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                        " AND service_code = $3 RETURNING revision",
                        cid,
                        vid,
                        ma,
                    )
                )
            kq["state_revision"] = state_revision
            await bien_nhan_ghi(
                conn,
                identity,
                "desk_service.set",
                idempotency_key,
                payload,
                str(kq.get("order_id") or vid),
                kq,
            )
        return kq

    async def _tick(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        vid: str,
        ma: str,
        noi: str,
        ds: list[dict[str, Any]],
        cua_quay: dict[str, Any] | None,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        cot = "o_tiep_don" if noi == "tiep_don" else "o_sinh_hieu"
        if not await conn.fetchval(
            f"SELECT EXISTS (SELECT 1 FROM lam_them_tai_quay WHERE clinic_id ="
            f" $1::uuid AND service_code = $2 AND bat AND {cot})",
            cid,
            ma,
        ):
            raise LuotKhamConflictError(
                "DESK_SERVICE_OFF",
                "Nút này quản lý đã tắt (hoặc không hiện ở màn này) — tải lại.",
            )
        if cua_quay is not None:
            if cua_quay["selection_status"] != "NOT_SELECTED":
                return {
                    "ok": True,
                    "changed": False,
                    "order_id": cua_quay["id"],
                    "order_version": int(cua_quay["version"]),
                }
            # Khách đã bỏ ở quầy thu, nay muốn làm lại → chốt lại chính chỉ định ấy.
            version = await conn.fetchval(
                "UPDATE service_order SET selection_status = 'SELECTED',"
                " nguon_lam_them = $3, recorded_by = $4::uuid,"
                " authorized_by = $4::uuid, authorized_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid RETURNING version",
                cid,
                cua_quay["id"],
                noi,
                identity.staff_id,
            )
            oid = cua_quay["id"]
            ten = cua_quay["service_name"]
        else:
            bac_si = next(
                (
                    o
                    for o in ds
                    if not o["nguon_lam_them"]
                    and o["selection_status"] != "NOT_SELECTED"
                ),
                None,
            )
            if bac_si is not None:
                raise LuotKhamConflictError(
                    "ALREADY_ORDERED",
                    "Lượt này đã có chỉ định dịch vụ này (bác sĩ chỉ định) — không"
                    " thêm lần nữa.",
                )
            dv = await conn.fetchrow(
                """
                SELECT s.name, s.node_code FROM service_price s
                 WHERE s.clinic_id = $1::uuid AND s."group" = 'dich_vu'
                   AND s.service_code = $2 AND s.active
                 ORDER BY s.node_code NULLS LAST LIMIT 1
                """,
                cid,
                ma,
            )
            if dv is None or not dv["node_code"]:
                raise LuotKhamConflictError(
                    "SERVICE_NOT_MAPPED",
                    "Dịch vụ đã ngừng bán hoặc chưa gắn bước thực hiện — báo quản"
                    " lý sửa bảng giá.",
                )
            moi = await conn.fetchrow(
                """
                INSERT INTO service_order
                    (clinic_id, visit_id, consultation_id, service_code,
                     service_name, node_code, exec_status, recorded_by,
                     authorized_by, authorized_at, selection_status,
                     routing_status, nguon_lam_them)
                VALUES ($1::uuid, $2::uuid, NULL, $3, $4, $5, 'authorized',
                        $6::uuid, $6::uuid, now(), 'SELECTED', 'UNASSIGNED', $7)
                ON CONFLICT (clinic_id, visit_id, service_code)
                   WHERE nguon_lam_them IS NOT NULL AND exec_status <> 'cancelled'
                DO NOTHING
                RETURNING id::text AS id, version
                """,
                cid,
                vid,
                ma,
                dv["name"],
                dv["node_code"],
                identity.staff_id,
                noi,
            )
            if moi is None:  # người khác vừa tick (đã khoá lượt nên hiếm)
                moi = await conn.fetchrow(
                    "SELECT id::text AS id, version FROM service_order"
                    " WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND service_code = $3"
                    " AND nguon_lam_them IS NOT NULL AND exec_status <> 'cancelled'",
                    cid,
                    vid,
                    ma,
                )
                return {
                    "ok": True,
                    "changed": False,
                    "order_id": moi["id"],
                    "order_version": int(moi["version"]),
                }
            oid = moi["id"]
            version = int(moi["version"])
            ten = dv["name"]
        await emit_event(
            conn,
            ten="service_order.desk_added",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=LamThemDaThem(
                visit_id=vid,
                service_order_id=oid,
                service_code=ma,
                service_name=str(ten),
                nguon=noi,
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        await record_event(
            conn,
            event_type="service_order.desk_added",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"order_id": oid, "service_code": ma, "nguon": noi},
        )
        return {
            "ok": True,
            "changed": True,
            "order_id": oid,
            "order_version": int(version),
        }

    async def _bo(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        vid: str,
        ma: str,
        noi: str,
        cua_quay: dict[str, Any] | None,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        if cua_quay is None or cua_quay["selection_status"] == "NOT_SELECTED":
            # Chưa tick / đã bỏ (hoặc chỉ có chỉ định của bác sĩ — quầy không bỏ hộ).
            return {
                "ok": True,
                "changed": False,
                "order_id": None,
                "order_version": None,
            }
        oid = cua_quay["id"]
        if _da_bat_dau(cua_quay):
            raise LuotKhamConflictError(
                "SERVICE_STARTED",
                "Phòng đã bắt đầu làm dịch vụ này — không bỏ tick được nữa. Muốn"
                " huỷ thì phòng bấm “Huỷ bắt đầu” / “Không làm”.",
            )
        if cua_quay["da_thu"]:
            raise LuotKhamConflictError(
                "SERVICE_ALREADY_PAID",
                "Dịch vụ đã thu tiền — bỏ ở quầy thu (hoàn tiền) chứ không bỏ ở đây.",
            )
        cho = await conn.fetch(
            """
            SELECT id::text AS id, status FROM queue_entry
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND reason = 'SERVICE' AND ref_id = $3::uuid
               AND status NOT IN ('done', 'left', 'cancelled')
               FOR UPDATE
            """,
            cid,
            vid,
            oid,
        )
        if any(q["status"] == "serving" for q in cho):
            raise LuotKhamConflictError(
                "SERVICE_STARTED",
                "Khách đang được làm dịch vụ này ở phòng — không bỏ tick được.",
            )
        if cho:
            await conn.execute(
                "UPDATE queue_entry SET status = 'cancelled',"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
                cid,
                [q["id"] for q in cho],
            )
        version = await conn.fetchval(
            """
            UPDATE service_order
               SET exec_status = 'cancelled', selection_status = 'NOT_SELECTED',
                   execution_status = 'CANCELLED',
                   execution_revision = execution_revision + 1,
                   routing_status = 'UNASSIGNED', room_id = NULL,
                   routing_revision = routing_revision + 1,
                   assigned_by = NULL, assigned_at = NULL,
                   cancelled_by = $3::uuid,
                   cancel_reason = 'Bỏ tick làm thêm tại quầy',
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
             RETURNING version
            """,
            cid,
            oid,
            identity.staff_id,
        )
        # Phụ thu chỉ sống cùng dịch vụ cha (cùng luật với khách bỏ ở quầy thu).
        await conn.execute(
            """
            UPDATE luot_phu_thu SET bo_luc = now(), bo_boi = $3::uuid
             WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
               AND bo_luc IS NULL
            """,
            cid,
            oid,
            identity.staff_id,
        )
        await cap_nhat_vi_tri(conn, cid, vid)
        await emit_event(
            conn,
            ten="service_order.desk_removed",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=LamThemDaBo(
                visit_id=vid, service_order_id=oid, service_code=ma, nguon=noi
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        await record_event(
            conn,
            event_type="service_order.desk_removed",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"order_id": oid, "service_code": ma, "nguon": noi},
        )
        return {
            "ok": True,
            "changed": True,
            "order_id": oid,
            "order_version": int(version),
        }


__all__ = [
    "NHAN_NGUON",
    "QUYEN_THEO_NOI",
    "LamThemTaiQuayService",
    "doc_noi",
    "nhan_lam_them",
    "trang_thai_nut",
]
