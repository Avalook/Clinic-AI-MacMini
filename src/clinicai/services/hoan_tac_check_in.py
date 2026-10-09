"""Hoàn tác check-in — chỉ khi khách CHƯA có việc thật nào sau check-in.

Phòng khám xin nút Hoàn tác ở bước check-in "để xử lý check-in nhầm"; Tuyền chốt
(09/10/2026): *"đã làm rồi thì không hoàn tác được nữa"*. Hoàn tác đóng lượt
(INCOMPLETE) và huỷ các bước còn mở — làm thế với một khách đã đo, đã vào phòng,
đã nộp tiền là để lại số đo / tiền / chỉ định treo trên một lượt "khách về giữa
chừng". Trường hợp ấy trưởng ca điều phối, không phải nút ở quầy.

KHÔNG TÍNH là "đã làm" — những gì HỆ THỐNG tự làm lúc check-in: mở lượt, đặt vào
trạm đầu (`place_visit_at_first_station` mở bước ga IN_PROGRESS), xếp hàng chờ
(`queue_entry` blocked/waiting), quyết đường đi (`route_decision`), phiên tư vấn /
bác sĩ còn `queued`, nhận lần đo của BUỔI từ lượt khác (chỉ cờ, không có số đo
của lượt này), chỉ định mang sang từ lượt trước (`mang_tu_visit_id`) và chỉ định
Điều trị tự sinh (gắn phiên còn `queued`) — chừng nào chưa ai bắt đầu làm chúng.

Luật ở MỘT chỗ: `ly_do_khong_hoan_tac` (thuần, test được) đọc các cờ do
`VIEC_DA_LAM_SQL` tính. Lệnh ghi (`BookingService.apply_action("undo_checkin")`)
khoá dòng lịch + lượt rồi mới hỏi; danh sách tiếp đón dùng cùng câu để vẽ nút.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg

#: (cờ, phần câu sau "Khách đã …") — thứ tự = thứ tự việc thường xảy ra.
VIEC_DA_LAM: tuple[tuple[str, str], ...] = (
    ("dang_do_sinh_hieu", "được bắt đầu đo sinh hiệu"),
    ("da_do_sinh_hieu", "được đo sinh hiệu"),
    ("vao_phong", "được nhận vào phòng"),
    ("phien_kham", "được bắt đầu tư vấn/khám"),
    ("phieu_kham", "có phiếu khám"),
    ("chi_dinh", "có chỉ định dịch vụ"),
    ("lam_dich_vu", "được bắt đầu làm dịch vụ"),
    ("nop_tien", "nộp tiền"),
)

CUOI_CAU = "không hoàn tác check-in được. Nhờ trưởng ca điều phối."


def ly_do_khong_hoan_tac(viec: Mapping[str, Any] | None) -> str | None:
    """Câu nói rõ vì sao KHÔNG hoàn tác được; None = hoàn tác được.

    Thiếu cờ / cờ rác coi như chưa làm — cờ đọc từ database, thiếu nghĩa là
    không có dòng nào. Nhiều việc thì kể hết, cách nhau dấu phẩy.
    """
    if not viec:
        return None
    da = [nhan for co, nhan in VIEC_DA_LAM if viec.get(co) is True]
    if not da:
        return None
    return f"Khách đã {', '.join(da)} — {CUOI_CAU}"


#: Cờ "đã làm" của nhiều lượt một lần: $1 = clinic, $2 = mảng visit_id.
VIEC_DA_LAM_SQL = """
SELECT v.visit_id::text AS visit_id,
       coalesce(f.vitals_status = 'in_progress', false) AS dang_do_sinh_hieu,
       EXISTS (
           SELECT 1 FROM public.vital_measurement m
            WHERE m.clinic_id = v.clinic_id AND m.visit_id = v.visit_id
       ) AS da_do_sinh_hieu,
       EXISTS (
           SELECT 1 FROM public.queue_entry q
            WHERE q.clinic_id = v.clinic_id AND q.visit_id = v.visit_id
              AND q.status IN ('serving', 'done')
       ) AS vao_phong,
       EXISTS (
           SELECT 1 FROM public.consultation c
            WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
              AND c.status NOT IN ('queued', 'cancelled')
       ) AS phien_kham,
       EXISTS (
           SELECT 1 FROM public.phieu_kham_luot p
            WHERE p.clinic_id = v.clinic_id AND p.visit_id = v.visit_id
       ) AS phieu_kham,
       -- Chỉ định do NGƯỜI đặt: không tính chỉ định mang sang từ lượt trước và
       -- chỉ định Điều trị tự sinh (gắn phiên còn queued — người chưa ai khám).
       -- Chỉ định tại quầy (`nguon_lam_them`, không phiên) thì tính.
       EXISTS (
           SELECT 1 FROM public.service_order o
            WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
              AND o.exec_status <> 'cancelled'
              AND o.mang_tu_visit_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM public.consultation c
                   WHERE c.clinic_id = o.clinic_id AND c.id = o.consultation_id
                     AND c.status = 'queued')
       ) AS chi_dinh,
       EXISTS (
           SELECT 1 FROM public.service_order o
            WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
              AND o.exec_status IN ('in_progress', 'performed', 'not_performed')
       ) OR EXISTS (
           SELECT 1 FROM public.work_item w
             JOIN public.node_definition n
               ON n.clinic_id = w.clinic_id AND n.code = w.node_code
            WHERE w.clinic_id = v.clinic_id AND w.visit_id = v.visit_id
              AND n.flow_group IN ('dich_vu', 'ket_qua')
              AND w.status IN ('IN_PROGRESS', 'COMPLETED')
       ) AS lam_dich_vu,
       EXISTS (
           SELECT 1 FROM public.payment_cycle c
            WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
              AND c.status IN ('PENDING_VERIFICATION', 'PAID')
       ) AS nop_tien
  FROM public.visit v
  LEFT JOIN public.encounter_flow f
    ON f.clinic_id = v.clinic_id AND f.visit_id = v.visit_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""


async def doc_viec_da_lam(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """visit_id → cờ "đã làm". Lượt không có trong kết quả = không đọc được."""
    if not visit_ids:
        return {}
    return {
        r["visit_id"]: dict(r)
        for r in await conn.fetch(VIEC_DA_LAM_SQL, clinic_id, visit_ids)
    }


async def chan_hoan_tac_neu_da_lam(
    conn: asyncpg.Connection, *, clinic_id: str, appointment_id: str
) -> str | None:
    """Trong giao dịch của lệnh hoàn tác: KHOÁ lịch + lượt + luồng rồi hỏi.

    Khoá theo thứ tự lịch → lượt → luồng (cùng chiều `xep_sau_check_in`: lượt
    trước luồng), để hai người bấm cùng lúc — một bấm Hoàn tác, một bấm Bắt đầu
    đo / Nhận khách — không lọt qua nhau: người sau chờ người trước xong rồi
    mới đọc cờ (READ COMMITTED: mỗi câu đọc bản đã commit mới nhất). Trả câu từ
    chối; None = hoàn tác được (hoặc chưa có lượt nào để hỏi).
    """
    await conn.execute(
        "SELECT 1 FROM public.appointment"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
        clinic_id,
        appointment_id,
    )
    visit_id = await conn.fetchval(
        "SELECT visit_id::text FROM public.visit"
        " WHERE clinic_id = $1::uuid AND appointment_id = $2::uuid FOR UPDATE",
        clinic_id,
        appointment_id,
    )
    if visit_id is None:
        return None
    await conn.execute(
        "SELECT 1 FROM public.encounter_flow"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
        clinic_id,
        visit_id,
    )
    viec = await doc_viec_da_lam(conn, clinic_id, [visit_id])
    return ly_do_khong_hoan_tac(viec.get(visit_id))


__all__ = [
    "CUOI_CAU",
    "VIEC_DA_LAM",
    "VIEC_DA_LAM_SQL",
    "chan_hoan_tac_neu_da_lam",
    "doc_viec_da_lam",
    "ly_do_khong_hoan_tac",
]
