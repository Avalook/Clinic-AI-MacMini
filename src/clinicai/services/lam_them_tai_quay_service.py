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

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import LamThemDaBo, LamThemDaThem
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import cap_nhat_vi_tri
from clinicai.services.lenh_kham_core import LuotKhamConflictError, khoa_luot
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

ORIGIN = "api:lam-them-tai-quay"
QUYEN_CAU_HINH = "config.wiring.manage"

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


# Chỉ định SỐNG của một dịch vụ trong lượt (cả của bác sĩ lẫn của quầy):
# chưa huỷ, khách chưa bỏ, chưa xong / chưa "không làm".
_SQL_SONG = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_code,
       o.nguon_lam_them, o.exec_status, o.selection_status, o.execution_status,
       o.routing_status, o.room_id::text AS room_id,
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
   AND coalesce(o.execution_status, 'PENDING')
       NOT IN ('CANCELLED', 'COMPLETED', 'NOT_PERFORMED')
 ORDER BY (o.nguon_lam_them IS NOT NULL) DESC, o.created_at
"""


def _da_bat_dau(o: asyncpg.Record | dict[str, Any]) -> bool:
    return (o["execution_status"] or "PENDING") != "PENDING" or (
        o["exec_status"] in _TRANG_THAI_DA_LAM
    )


def trang_thai_nut(o: dict[str, Any] | None) -> dict[str, Any]:
    """Trạng thái MỘT nút cho một lượt — hàm thuần, màn chỉ vẽ.

    ``chon`` = đang tick; ``doi_duoc`` = bấm được (tick hoặc bỏ); ``ghi_chu`` nói
    vì sao không bỏ được / ai đã chỉ định.
    """
    if o is None:
        return {"chon": False, "doi_duoc": True, "order_id": None, "ghi_chu": None}
    la_quay = bool(o.get("nguon_lam_them"))
    if not la_quay:
        # Bác sĩ đã chỉ định dịch vụ này — quầy không chồng thêm, cũng không bỏ hộ.
        if o.get("selection_status") == "NOT_SELECTED":
            return {"chon": False, "doi_duoc": True, "order_id": None, "ghi_chu": None}
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "ghi_chu": "bác sĩ đã chỉ định",
        }
    if o.get("selection_status") == "NOT_SELECTED":
        # Khách bỏ ở quầy thu → nút về chưa tick; tick lại là chốt lại.
        return {"chon": False, "doi_duoc": True, "order_id": o["id"], "ghi_chu": None}
    if _da_bat_dau(o):
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "ghi_chu": "đang làm" + (f" ở {o['phong']}" if o.get("phong") else ""),
        }
    if o.get("da_thu"):
        return {
            "chon": True,
            "doi_duoc": False,
            "order_id": o["id"],
            "ghi_chu": "đã thu tiền — bỏ ở quầy thu",
        }
    return {
        "chon": True,
        "doi_duoc": True,
        "order_id": o["id"],
        "ghi_chu": nhan_lam_them(o.get("nguon_lam_them")),
    }


class LamThemTaiQuayService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Cấu hình (quản lý) ──────────────────────────────────────────────────

    async def cau_hinh(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Danh sách nút + dịch vụ chọn được (dịch vụ ĐANG BÁN, đã gắn bước làm)."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            muc = await self._doc_muc(conn, cid)
            dich_vu = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT DISTINCT ON (s.service_code)
                           s.service_code, s.name AS ten, s.unit_price AS gia
                      FROM service_price s
                     WHERE s.clinic_id = $1::uuid AND s."group" = 'dich_vu'
                       AND s.active AND s.node_code IS NOT NULL
                     ORDER BY s.service_code, s.unit_price NULLS LAST
                    """,
                    cid,
                )
            ]
        for d in dich_vu:
            d["gia"] = int(d["gia"]) if d["gia"] is not None else None
        dich_vu.sort(key=lambda d: str(d["ten"]))
        return {"muc": muc, "dich_vu": dich_vu}

    async def luu_muc(
        self,
        *,
        identity: StaffIdentity,
        service_code: Any,
        nhan: Any = None,
        bat: Any = True,
        thu_tu: Any = None,
        o_tiep_don: Any = True,
        o_sinh_hieu: Any = True,
    ) -> dict[str, Any]:
        """Thêm hoặc sửa MỘT nút. Bật mà không hiện ở đâu → báo, không lưu câm."""
        cid = identity.clinic_id
        ma = _ma_dich_vu(service_code)
        nhan_sach = nhan.strip() if isinstance(nhan, str) and nhan.strip() else None
        if nhan_sach is not None and len(nhan_sach) > 40:
            raise ValidationError("Chữ trên nút dài tối đa 40 ký tự.")
        bat_b = bool(bat)
        tiep = bool(o_tiep_don)
        sinh = bool(o_sinh_hieu)
        if bat_b and not (tiep or sinh):
            raise ValidationError(
                "Nút đang bật phải hiện ở ít nhất một nơi (Tiếp đón hoặc Đo sinh"
                " hiệu) — không hiện ở đâu thì tắt nút."
            )
        try:
            so = int(thu_tu) if thu_tu is not None and thu_tu != "" else None
        except (TypeError, ValueError):
            raise ValidationError("Thứ tự phải là số.") from None
        if so is not None and not 0 <= so <= 9999:
            raise ValidationError("Thứ tự trong khoảng 0–9999.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
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
            if dv is None:
                raise ValidationError(
                    "Dịch vụ này không có (hoặc đã ngừng bán) trong bảng giá."
                )
            if not dv["node_code"]:
                raise ValidationError(
                    f"“{dv['name']}” chưa gắn bước thực hiện — gắn ở bảng giá"
                    " trước rồi mới làm nút được."
                )
            if so is None:
                so = int(
                    await conn.fetchval(
                        "SELECT coalesce(max(thu_tu), 0) + 10 FROM lam_them_tai_quay"
                        " WHERE clinic_id = $1::uuid",
                        cid,
                    )
                )
            await conn.execute(
                """
                INSERT INTO lam_them_tai_quay
                    (clinic_id, service_code, nhan, bat, thu_tu, o_tiep_don,
                     o_sinh_hieu, updated_by)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::uuid)
                ON CONFLICT (clinic_id, service_code) DO UPDATE
                   SET nhan = EXCLUDED.nhan, bat = EXCLUDED.bat,
                       thu_tu = EXCLUDED.thu_tu, o_tiep_don = EXCLUDED.o_tiep_don,
                       o_sinh_hieu = EXCLUDED.o_sinh_hieu,
                       updated_by = EXCLUDED.updated_by, updated_at = now()
                """,
                cid,
                ma,
                nhan_sach,
                bat_b,
                so,
                tiep,
                sinh,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="config.desk_service_saved",
                aggregate_type="clinic",
                aggregate_id=cid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "service_code": ma,
                    "nhan": nhan_sach,
                    "bat": bat_b,
                    "thu_tu": so,
                    "o_tiep_don": tiep,
                    "o_sinh_hieu": sinh,
                },
            )
            muc = await self._doc_muc(conn, cid)
        return {"ok": True, "muc": muc}

    async def bo_muc(
        self, *, identity: StaffIdentity, service_code: Any
    ) -> dict[str, Any]:
        """Bớt một nút khỏi danh sách. Chỉ định đã tick trước đó GIỮ NGUYÊN."""
        cid = identity.clinic_id
        ma = _ma_dich_vu(service_code)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            xoa = await conn.fetchval(
                "DELETE FROM lam_them_tai_quay WHERE clinic_id = $1::uuid"
                " AND service_code = $2 RETURNING service_code",
                cid,
                ma,
            )
            if xoa is None:
                raise NotFoundError("Nút này không có trong danh sách.")
            await record_event(
                conn,
                event_type="config.desk_service_removed",
                aggregate_type="clinic",
                aggregate_id=cid,
                identity=identity,
                origin=ORIGIN,
                payload={"service_code": ma},
            )
            muc = await self._doc_muc(conn, cid)
        return {"ok": True, "muc": muc}

    @staticmethod
    async def _doc_muc(conn: asyncpg.Connection, cid: str) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT l.service_code, l.nhan, l.bat, l.thu_tu, l.o_tiep_don,
                   l.o_sinh_hieu, dv.ten, dv.gia, dv.dang_ban
              FROM lam_them_tai_quay l
              LEFT JOIN LATERAL (
                   SELECT s.name AS ten, s.unit_price AS gia,
                          (s.active AND s.node_code IS NOT NULL) AS dang_ban
                     FROM service_price s
                    WHERE s.clinic_id = l.clinic_id AND s."group" = 'dich_vu'
                      AND s.service_code = l.service_code
                    ORDER BY s.active DESC LIMIT 1) dv ON true
             WHERE l.clinic_id = $1::uuid
             ORDER BY l.thu_tu, l.service_code
            """,
            cid,
        )
        return [
            {
                "service_code": r["service_code"],
                "nhan": r["nhan"],
                "nhan_hien": r["nhan"] or r["ten"] or r["service_code"],
                "ten": r["ten"],
                "gia": int(r["gia"]) if r["gia"] is not None else None,
                "bat": bool(r["bat"]),
                "thu_tu": int(r["thu_tu"]),
                "o_tiep_don": bool(r["o_tiep_don"]),
                "o_sinh_hieu": bool(r["o_sinh_hieu"]),
                # Bảng giá ngừng bán / bỏ bước làm → nút tự ẩn ở quầy.
                "dang_ban": bool(r["dang_ban"]),
            }
            for r in rows
        ]

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
                # Lượt còn mở (chưa check-out) mới bấm được.
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
                for vid in ids:
                    luot[vid] = {
                        x["service_code"]: {
                            **trang_thai_nut(song.get((vid, x["service_code"]))),
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
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_THEO_NOI[n])
            luot = await khoa_luot(conn, cid, vid)
            if luot["closed_at"] is not None:
                raise LuotKhamConflictError(
                    "VISIT_CHECKED_OUT", "Khách đã check-out — không thêm dịch vụ."
                )
            ds = [
                dict(r)
                for r in await conn.fetch(
                    _SQL_SONG + " FOR UPDATE OF o", cid, [vid], [ma]
                )
            ]
            cua_quay = next((o for o in ds if o["nguon_lam_them"]), None)
            if bool(chon):
                kq = await self._tick(conn, identity, vid, ma, n, ds, cua_quay)
            else:
                kq = await self._bo(conn, identity, vid, ma, n, cua_quay)
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
                return {"ok": True, "changed": False, "order_id": cua_quay["id"]}
            # Khách đã bỏ ở quầy thu, nay muốn làm lại → chốt lại chính chỉ định ấy.
            await conn.execute(
                "UPDATE service_order SET selection_status = 'SELECTED',"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                cua_quay["id"],
            )
            oid = cua_quay["id"]
            ten = await conn.fetchval(
                "SELECT service_name FROM service_order WHERE id = $1::uuid", oid
            )
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
            oid = await conn.fetchval(
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
                RETURNING id::text
                """,
                cid,
                vid,
                ma,
                dv["name"],
                dv["node_code"],
                identity.staff_id,
                noi,
            )
            if oid is None:  # người khác vừa tick (đã khoá lượt nên hiếm)
                oid = await conn.fetchval(
                    "SELECT id::text FROM service_order WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND service_code = $3"
                    " AND nguon_lam_them IS NOT NULL AND exec_status <> 'cancelled'",
                    cid,
                    vid,
                    ma,
                )
                return {"ok": True, "changed": False, "order_id": oid}
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
        return {"ok": True, "changed": True, "order_id": oid}

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
            return {"ok": True, "changed": False, "order_id": None}
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
        await conn.execute(
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
        return {"ok": True, "changed": True, "order_id": oid}


__all__ = [
    "NHAN_NGUON",
    "QUYEN_THEO_NOI",
    "LamThemTaiQuayService",
    "doc_noi",
    "nhan_lam_them",
    "trang_thai_nut",
]
