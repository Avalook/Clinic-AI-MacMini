"""Khối ĐỐI TÁC nhận việc — nối bằng sự kiện (Tuyền 24/09/2026: "bác sĩ chỉ
định sinh event đối tác nhận chưa").

Trước đây bàn đối tác là một câu truy vấn tự đọc bảng chỉ định: việc đối tác tự
lấy mẫu hiện NGAY lúc bác sĩ chỉ định — trước cả khi khách chọn làm và trả tiền
(trái luồng chuẩn bước 7: "khách xuống lễ tân TRẢ TIỀN dịch vụ thực làm"). Nay:

    payment.service_collected → chỉ định làm bên ngoài, ĐỐI TÁC TỰ LẤY MẪU, khách
                                đã chọn làm + đủ điều kiện tài chính → nhận việc
    service.completed         → chỉ định làm bên ngoài do ĐIỀU DƯỠNG lấy mẫu,
                                vừa làm xong ở phòng Lấy mẫu → nhận việc

"Nhận việc" = một dòng `doi_tac_nhan_viec` (bảng CỦA khối này) + phát
`partner.order_received` (dòng thời gian lượt + chuông vai Đối tác). Bàn đối
tác đọc đúng bảng ấy.

CHẠY LẠI ĐƯỢC: chỉ định đã có dòng nhận thì bỏ. PHÁT LẠI thì im (node tác vụ).
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import DOI_TAC_NHAN_VIEC, DoiTacNhanViec
from clinicai.events.emit import NguoiGayRa, emit_event
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services import finance_gate

_CHO_NHAN_SQL = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id,
       coalesce(sp.name, o.service_name) AS ten,
       coalesce(sp.doi_tac_lay_mau, false) AS tu_lay_mau
  FROM service_order o
  JOIN node_definition n
    ON n.clinic_id = o.clinic_id AND n.code = o.node_code AND n.lam_ben_ngoai
  LEFT JOIN LATERAL (
       SELECT s.name, s.doi_tac_lay_mau FROM service_price s
        WHERE s.clinic_id = o.clinic_id AND s.service_code = o.service_code
          AND s.active
        ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND coalesce(o.selection_status, 'SELECTED') = 'SELECTED'
   AND NOT EXISTS (SELECT 1 FROM doi_tac_nhan_viec d
                    WHERE d.clinic_id = o.clinic_id AND d.service_order_id = o.id)
   AND (
        (coalesce(sp.doi_tac_lay_mau, false)
         AND o.exec_status IN ('authorized', 'assigned', 'in_progress'))
     OR (NOT coalesce(sp.doi_tac_lay_mau, false) AND o.exec_status = 'performed')
   )
 ORDER BY o.created_at, o.id
"""


async def _luot_cua(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> str | None:
    visit_id = su_kien.payload.get("visit_id")
    if visit_id:
        return str(visit_id)
    so_id = su_kien.payload.get("service_order_id")
    if not so_id:
        return None
    v = await conn.fetchval(
        "SELECT visit_id::text FROM service_order"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        su_kien.clinic_id,
        str(so_id),
    )
    return str(v) if v else None


async def nhan_viec_doi_tac(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = await _luot_cua(conn, su_kien)
    if not visit_id:
        return
    rows = await conn.fetch(_CHO_NHAN_SQL, su_kien.clinic_id, visit_id)
    tu_lay = [r["id"] for r in rows if r["tu_lay_mau"]]
    tai_chinh = (
        await finance_gate.states_for_orders(conn, su_kien.clinic_id, tu_lay)
        if tu_lay
        else {}
    )
    boi = NguoiGayRa(actor_type=su_kien.actor_type, staff_id=su_kien.actor_staff_id)
    for r in rows:
        if r["tu_lay_mau"]:
            # Đối tác tự lấy mẫu: chỉ nhận khi khách ĐÃ trả (hoặc đối tác tự thu).
            q = tai_chinh.get(r["id"])
            if q is None or not q.financially_ready:
                continue
            ly_do = "DA_THU_TIEN"
        else:
            ly_do = "DA_LAY_MAU"
        moi = await conn.fetchval(
            "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do,"
            " nguon_event_id) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)"
            " ON CONFLICT (clinic_id, service_order_id) DO NOTHING"
            " RETURNING service_order_id",
            su_kien.clinic_id,
            r["id"],
            ly_do,
            su_kien.event_id,
        )
        if moi is None:
            continue
        await emit_event(
            conn,
            ten="partner.order_received",
            clinic_id=su_kien.clinic_id,
            aggregate_id=r["id"],
            payload=DoiTacNhanViec(
                visit_id=visit_id,
                service_order_id=r["id"],
                service_name=r["ten"],
                ly_do=ly_do,
            ),
            boi=boi,
            correlation_id=visit_id,
            causation_id=su_kien.event_id,
        )


dang_ky(DOI_TAC_NHAN_VIEC, nhan_viec_doi_tac)
