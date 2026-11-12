"""Gmail G14 + G16 — thư "không khớp khách" mà tên + năm sinh chỉ ra ĐÚNG MỘT hồ sơ
(Tuyền 12/11/2026). Tách khỏi `gmail.py` (trần 400 dòng).

* G14: SĐT trên phiếu lệch hồ sơ (số mới / số người nhà — prod 12/11: 33/59 thư chờ là
  "tên khớp, SĐT khác"), cả phòng khám chỉ MỘT hồ sơ mang cặp tên + năm sinh của phiếu,
  và người đó có chỉ định của lab ⇒ quyết như khách đã khớp (`quyet_mot_khach`: một
  chỉ định chờ ⇒ tự gán; nhiều / đã có tờ ⇒ lý do + gợi ý).
* G16: như trên nhưng người đó KHÔNG có chỉ định nào của lab (bác sĩ không nhập chỉ
  định — prod: lượt chỉ có siêu âm, mẫu máu lấy cùng tối) ⇒ neo bằng LƯỢT KHÁM trong
  `NEO_LUOT_NGAY` ngày trước thư: tờ vào hồ sơ theo lượt (như G8).

Không chắc ⇒ giữ quyết định cũ (G9 gợi ý, người gán).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Final

import asyncpg

from clinicai.services.xet_nghiem import ghep_khach, gmail_doc, gmail_ghep, gmail_luu

#: G16 — lượt khám làm neo khi không có chỉ định: trong bấy nhiêu ngày trước thư (Tuyền
#: chốt 14: đủ cho lab trả chậm như NIPT ~7–10 ngày).
NEO_LUOT_NGAY: Final = 14


async def quyet(
    conn: asyncpg.Connection,
    cid: str,
    doc: gmail_doc.DocThu,
    viec: list[ghep_khach.UngVien],
    nhan_luc: datetime,
    q: gmail_ghep.QuyetGmail,
) -> gmail_ghep.QuyetGmail:
    """`q` đang KHONG_KHOP_KHACH ⇒ quyết lại theo tên + năm sinh (G14, G16)."""
    if doc.nam_sinh is None:
        return q
    ids = await gmail_luu.khach_cung_ten_nam(conn, cid, doc.ten, doc.nam_sinh)
    kh = gmail_ghep.khop_ten_nam_sinh(doc, viec, len(ids))
    if kh is None:
        if len(ids) != 1 or any(v.clinic_patient_id == ids[0] for v in viec):
            return q
        luot = await ghep_khach.luot_gan_nhat(
            conn, cid, ids[0], nhan_luc, so_ngay=NEO_LUOT_NGAY
        )
        if luot is None:
            return q
        return gmail_ghep.gan_ho_so(
            replace(q, ly_do="KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id=ids[0]),
            luot,
        )
    cua_kh = [v for v in viec if v.clinic_patient_id == kh]
    q2 = gmail_ghep.quyet_mot_khach(doc.loai, cua_kh, kh, nhan_luc)
    return q2 if q2.ly_do is None else replace(q2, goi_y_clinic_patient_id=kh)
