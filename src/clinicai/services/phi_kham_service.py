"""Chọn DỊCH VỤ KHÁM theo mã KiotViet cho một lượt (Tuyền 28/09/2026).

"Tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … thêm khu vực tick dưới
dòng Bác sĩ tư vấn ghi để chọn loại dịch vụ chính xác của dịch vụ khám, lúc đó
tiền mới tính, mình không còn bịa giá nữa."

* Danh sách chọn được = `loai_kham_phi` của loại khám của lượt (migration
  20260928000100, nguồn file KiotViet).
* Tick lưu ở `luot_phi_kham`; tiền khám = các dòng còn sống
  (`bill_service.dong_kham_theo_chon`).
* Ai tick: người khám (Bàn khám / tư vấn / ghi bệnh án) hoặc quầy thu — hỏi
  QUYỀN, không hỏi vai. Đổi sau khi đã thu tạo một nghĩa vụ mới, không sửa ảnh
  chụp lần thu cũ.
* Chỉ lượt thực sự rẽ thẳng sang phòng dịch vụ mới không có tiền khám. Loại
  Sàn chậu / Thủ thuật đã rơi về bác sĩ chính vẫn được chọn như lượt khám khác.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import DichVuKhamDaDoi
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

#: Có MỘT trong các quyền này thì tick được: người khám, người ghi bệnh án,
#: người tư vấn, quầy thu tiền dịch vụ.
QUYEN_TICK = (
    "clinical.consult.perform",
    "clinical.record.write",
    "clinical.intake.perform",
    "payment.service.collect",
)

_LOAI_KHAM_SQL = """
SELECT st.id::text AS st_id, st.name,
       coalesce(st.di_thang_phong, false) AS di_thang,
       (coalesce(st.di_thang_phong, false)
        AND coalesce(ef.route_decision, 'SERVICES') = 'SERVICES') AS khong_kham
  FROM public.visit vi
  LEFT JOIN public.appointment a
    ON a.id = vi.appointment_id AND a.clinic_id = vi.clinic_id
  JOIN public.service_type st
    ON st.id = coalesce(vi.service_type_id, a.service_type_id)
  LEFT JOIN public.encounter_flow ef
    ON ef.clinic_id = vi.clinic_id AND ef.visit_id = vi.visit_id
 WHERE vi.clinic_id = $1::uuid AND vi.visit_id = $2::uuid
"""

_LUA_CHON_SQL = """
SELECT sp.id::text AS id, sp.ma_kiotviet, sp.name, sp.unit_price
  FROM public.loai_kham_phi l
  JOIN public.service_price sp
    ON sp.id = l.service_price_id AND sp.clinic_id = l.clinic_id AND sp.active
 WHERE l.clinic_id = $1::uuid AND l.service_type_id = $2::uuid
 ORDER BY l.thu_tu, sp.name
"""


async def _co_quyen_tick(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_TICK:
        if await can(conn, identity, q):
            return True
    return False


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    loai = await conn.fetchrow(_LOAI_KHAM_SQL, clinic_id, visit_id)
    lua_chon = await conn.fetch(_LUA_CHON_SQL, clinic_id, loai["st_id"]) if loai else []
    da_chon = [
        r["id"]
        for r in await conn.fetch(
            "SELECT service_price_id::text AS id FROM public.luot_phi_kham"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND bo_luc IS NULL"
            " ORDER BY chon_luc, id",
            clinic_id,
            visit_id,
        )
    ]
    return {
        "loai_kham": loai["name"] if loai else None,
        "di_thang_phong": bool(loai["di_thang"]) if loai else False,
        "khong_kham": bool(loai["khong_kham"]) if loai else False,
        "lua_chon": [
            {
                "id": r["id"],
                "ma_kiotviet": r["ma_kiotviet"],
                "ten": r["name"],
                "gia": int(r["unit_price"]) if r["unit_price"] is not None else None,
            }
            for r in lua_chon
        ],
        "da_chon": da_chon,
        # V2: mỗi lựa chọn có nguồn thu riêng; trước check-out có thể tick thêm
        # và chỉ phần mới thành khoản phát sinh. Sau check-out chon() chặn ghi.
        "khoa": False,
    }


async def _chan_bo_dich_vu_da_thu(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    bo: list[str],
    lua_chon: list[dict[str, Any]],
) -> None:
    """Tick THÊM sau khi thu thì được (thu lần 2); BỎ một dịch vụ khám ĐÃ THU thì
    không — khoản đã thu sẽ biến khỏi hoá đơn mà không có hoàn tiền (30/09/2026).

    Đã thu = dòng `exam-{visit}-selected-{id}` trong lần thu còn hiệu lực, hoặc
    (thu trước V2) dòng gộp `exam-{visit}` mà tên ghép có tên dịch vụ này.
    """
    rows = await conn.fetch(
        """
        SELECT bl.source_id, bl.name_snapshot
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = $1::uuid AND bl.source_type = 'exam'
           AND (bl.source_id = $2 OR bl.source_id LIKE $2 || '-selected-%')
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
        """,
        clinic_id,
        f"exam-{visit_id}",
    )
    ten = {str(x["id"]): str(x.get("ten") or "") for x in lua_chon}
    da_thu_nguon = {str(r["source_id"]) for r in rows}
    ten_gop = [
        str(r["name_snapshot"] or "").split(" + ")
        for r in rows
        if str(r["source_id"]) == f"exam-{visit_id}"
    ]
    da_thu = [
        i
        for i in bo
        if f"exam-{visit_id}-selected-{i}" in da_thu_nguon
        or any(ten.get(i) and ten[i] in g for g in ten_gop)
    ]
    if da_thu:
        raise ValidationError(
            "Dịch vụ khám đã thu tiền: "
            + ", ".join(ten.get(i) or i for i in da_thu)
            + ". Muốn bỏ phải huỷ phiếu thu / hoàn tiền trước."
        )


async def chan_trung_dich_vu_kham(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    *,
    ma_chi_dinh: list[str] | None = None,
    id_tick: list[str] | None = None,
) -> None:
    """Tiền khám không tính HAI lần (02/10/2026, C21 — phí khám chỉ định được).

    Một dịch vụ đang tick ở "Dịch vụ khám" (`luot_phi_kham` còn sống) thì không
    chỉ định lại (`ma_chi_dinh`); một dịch vụ đang là chỉ định còn tính tiền
    (`service_order` chưa huỷ / chưa "không làm") thì không tick thêm ở Dịch vụ
    khám (`id_tick` = id `service_price`). Gọi trong giao dịch đã khoá lượt.
    """
    if ma_chi_dinh:
        trung = await conn.fetch(
            """
            SELECT DISTINCT sp.name
              FROM public.luot_phi_kham l
              JOIN public.service_price sp
                ON sp.id = l.service_price_id AND sp.clinic_id = l.clinic_id
             WHERE l.clinic_id = $1::uuid AND l.visit_id = $2::uuid
               AND l.bo_luc IS NULL AND sp.service_code = ANY($3::text[])
             ORDER BY sp.name
            """,
            clinic_id,
            visit_id,
            ma_chi_dinh,
        )
        if trung:
            raise ValidationError(
                "Đã tính ở Dịch vụ khám: "
                + ", ".join(r["name"] for r in trung)
                + ". Không chỉ định lại — bỏ tick ở Dịch vụ khám nếu muốn làm"
                " thành chỉ định."
            )
    if id_tick:
        trung = await conn.fetch(
            """
            SELECT DISTINCT sp.name
              FROM public.service_order o
              JOIN public.service_price sp
                ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
               AND sp."group" = 'dich_vu'
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
               AND o.exec_status NOT IN ('cancelled', 'not_performed')
               AND sp.id = ANY($3::uuid[])
             ORDER BY sp.name
            """,
            clinic_id,
            visit_id,
            id_tick,
        )
        if trung:
            raise ValidationError(
                "Đã chỉ định: "
                + ", ".join(r["name"] for r in trung)
                + ". Tiền tính ở chỉ định — không tick thêm ở Dịch vụ khám."
            )


class PhiKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            kq = await _doc(conn, identity.clinic_id, vid)
            kq["duoc_tick"] = await _co_quyen_tick(conn, identity)
            return kq

    async def chon(
        self,
        *,
        visit_id: str,
        ids: list[str] | None = None,
        them_vao: list[str] | None = None,
        bo_di: list[str] | None = None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Đổi dịch vụ khám của lượt (bỏ tick = đóng dấu, không xoá).

        HAI DẠNG GỬI:
        * `ids` — đặt TẬP = `ids` (dạng cũ, giữ cho khách gọi cũ).
        * `them_vao` / `bo_di` — ĐỔI THEO TỪNG DỊCH VỤ, tính trên tập HIỆN CÓ
          trong chính giao dịch (C18, 02/10/2026). Màn nào cầm tập cũ (tab mở
          từ trước, hai người cùng mở một lượt) gửi lên cũng không ghi đè tick
          của người khác; tick một dịch vụ đã tick là không làm gì (idempotent).
        """
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        muon = list(dict.fromkeys(str(i) for i in (ids or [])))
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _co_quyen_tick(conn, identity):
                raise SafetyGateError("Bạn không có quyền chọn dịch vụ khám.")
            luot = await khoa_luot(conn, cid, vid, cho_phep_da_ky=True)
            if luot["closed_at"] is not None:
                raise ValidationError(
                    "Lượt đã check-out — không thể đổi dịch vụ khám sau khi khách về."
                )
            hien = await _doc(conn, cid, vid)
            if hien["khong_kham"]:
                raise ValidationError(
                    "Loại khám đi thẳng phòng không có tiền khám — thêm dịch vụ ở quầy."
                )
            hop_le = {x["id"] for x in hien["lua_chon"]}
            cu = set(hien["da_chon"])
            if ids is None:
                cong = [str(i) for i in (them_vao or [])]
                tru = {str(i) for i in (bo_di or [])}
                muon = [
                    i for i in dict.fromkeys([*hien["da_chon"], *cong]) if i not in tru
                ]
            la = [i for i in muon if i not in hop_le]
            if la:
                raise ValidationError(
                    "Có dịch vụ không thuộc danh sách khám của loại khám này."
                )
            bo = sorted(cu - set(muon))
            them = [i for i in muon if i not in cu]
            if bo:
                await _chan_bo_dich_vu_da_thu(conn, cid, vid, bo, hien["lua_chon"])
            if them:
                await chan_trung_dich_vu_kham(conn, cid, vid, id_tick=them)
            if bo:
                await conn.execute(
                    "UPDATE public.luot_phi_kham SET bo_luc = now(), bo_boi = $4::uuid"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND service_price_id = ANY($3::uuid[]) AND bo_luc IS NULL",
                    cid,
                    vid,
                    bo,
                    identity.staff_id,
                )
            for i in them:
                await conn.execute(
                    "INSERT INTO public.luot_phi_kham"
                    " (clinic_id, visit_id, service_price_id, chon_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid)",
                    cid,
                    vid,
                    i,
                    identity.staff_id,
                )
            if bo or them:
                # Sổ sự kiện (C18, 02/10/2026): dịch vụ khám con lên Hành trình
                # khách — ai tick / bỏ tick, tên + giá lúc ấy.
                moc = {x["id"]: x for x in hien["lua_chon"]}

                def _dv(i: str) -> dict[str, str | int | None]:
                    return {
                        "id": i,
                        "ten": (moc.get(i) or {}).get("ten"),
                        "gia": (moc.get(i) or {}).get("gia"),
                    }

                await emit_event(
                    conn,
                    ten="visit.exam_service_changed",
                    clinic_id=cid,
                    aggregate_id=vid,
                    so_ke_tiep=True,
                    payload=DichVuKhamDaDoi(
                        visit_id=vid,
                        loai_kham=hien["loai_kham"],
                        them=[_dv(i) for i in them],
                        bo=[_dv(i) for i in bo],
                    ),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )
                await record_event(
                    conn,
                    event_type="visit.exam_fee_selected",
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin="api:phi-kham",
                    payload={"them": them, "bo": bo},
                    correlation_id=vid,
                )
            kq = await _doc(conn, cid, vid)
        kq["duoc_tick"] = True
        return kq


__all__ = ["QUYEN_TICK", "PhiKhamService", "chan_trung_dich_vu_kham"]
