"""Nút "Đã gửi kết quả cho bệnh nhân" (màn Quản lý khách hàng) ⇒ ghi đã gửi MỌI tệp
kết quả của LƯỢT (Tuyền 12/11/2026).

Trước: nút chỉ ghi đã gửi tờ của việc đối tác (`xet_nghiem.ket_qua.gui_theo_cskh`); tệp
nội bộ (ảnh siêu âm, PDF tải tay…) vẫn "chưa gửi" dù CSKH đã gửi hết ⇒ check-out
"Hồ sơ trả bệnh nhân" ghi 1/3. Nay: tờ đối tác đi ĐÚNG lõi bàn XN (sự kiện lab.*), các
tệp còn lại đi ĐÚNG lõi nút gửi từng tệp (`TepKetQuaService.danh_dau_da_gui`, sự kiện
result_file.sent_to_patient) — không ghi thẳng bảng, không lõi thứ ba.

"Tệp của lượt" = cùng tiêu chí màn check-out: theo chỉ định của lượt, hoặc gắn thẳng
vào lịch hẹn của lượt. Không có lịch hẹn ⇒ KHÔNG đánh dấu gì (đánh theo khách sẽ ghi
"đã gửi" cho tệp của LƯỢT KHÁC). Tệp đối tác chưa Hợp lệ không gửi (lõi tự chặn).

Gọi SAU khi dòng sổ CSKH đã commit; lỗi chỉ ghi log — sổ là bằng chứng chính, người
trực bấm gửi từng tệp lại được.
"""

from __future__ import annotations

from datetime import date
from typing import Final

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.tep_ket_qua_service import KENH_GUI_HOP_LE, TepKetQuaService
from clinicai.services.xet_nghiem.ket_qua import gui_theo_cskh

logger = structlog.get_logger()

#: Trần tệp một lượt (thực tế < 20; chạm trần ⇒ cảnh báo, không cắt im lặng).
TRAN: Final = 100

#: $1 clinic · $2 khách · $3 lịch hẹn. Tệp còn hiệu lực, chưa gửi, gửi được
#: (nội bộ: xac_nhan NULL; đối tác: HOP_LE) của lượt.
_TEP_CHUA_GUI_SQL = f"""
SELECT t.id::text AS id
  FROM public.v_tep_ket_qua_hieu_luc t
 WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid
   AND t.gui_luc IS NULL
   AND coalesce(t.xac_nhan_trang_thai, 'HOP_LE') = 'HOP_LE'
   AND (t.appointment_id = $3::uuid
        OR t.service_order_id IN (
            SELECT o.id FROM public.service_order o
              JOIN public.visit v
                ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
             WHERE o.clinic_id = $1::uuid AND v.appointment_id = $3::uuid))
 ORDER BY t.tai_len_luc
 LIMIT {TRAN}
"""


async def danh_dau_ca_luot(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    clinic_patient_id: str,
    appointment_id: str | None,
    kenh: str,
    hom_nay: date,
) -> int:
    """Ghi đã gửi mọi tệp chưa gửi của lượt `appointment_id`, kênh `kenh` (kênh sổ
    không phải kênh gửi tệp — GOI — ⇒ TRUC_TIEP). Trả số tệp đã ghi gửi."""
    if not appointment_id:
        return 0
    n = await gui_theo_cskh(
        pool, identity, clinic_patient_id, appointment_id, kenh, hom_nay
    )
    kenh_gui = kenh if kenh in KENH_GUI_HOP_LE else "TRUC_TIEP"
    try:
        rows = await pool.fetch(
            _TEP_CHUA_GUI_SQL, identity.clinic_id, clinic_patient_id, appointment_id
        )
        canh_bao_neu_day(
            "gui_ket_qua_luot", len(rows), TRAN, clinic_id=identity.clinic_id
        )
        svc = TepKetQuaService(pool)
        for r in rows:
            try:
                await svc.danh_dau_da_gui(
                    identity=identity, tep_id=r["id"], kenh=kenh_gui
                )
                n += 1
            except (ConflictError, NotFoundError, ValidationError) as e:
                # Vừa có người gửi / thu hồi / xoá tệp này — bỏ qua tệp đó.
                logger.warning("gui_ket_qua_luot_bo_qua", loai=type(e).__name__)
    except Exception as e:  # noqa: BLE001 — sổ CSKH đã commit
        logger.warning("gui_ket_qua_luot_loi", loai=type(e).__name__)
    return n
