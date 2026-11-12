"""Gmail G14 + G16 — thư "không khớp khách" mà tên + năm sinh chỉ ra ĐÚNG MỘT hồ sơ
(Tuyền 12/11/2026). Tách khỏi `gmail.py` (trần 400 dòng).

* G14: SĐT trên phiếu lệch hồ sơ (số mới / số người nhà — prod 12/11: 33/59 thư chờ là
  "tên khớp, SĐT khác"), cả phòng khám chỉ MỘT hồ sơ mang cặp tên + năm sinh của phiếu,
  và người đó có chỉ định của lab ⇒ quyết như khách đã khớp (`quyet_mot_khach`: một
  chỉ định chờ ⇒ tự gán; nhiều / đã có tờ ⇒ lý do + gợi ý).
* G16: như trên nhưng người đó KHÔNG có chỉ định nào của lab (bác sĩ không nhập chỉ
  định — prod: lượt chỉ có siêu âm, mẫu máu lấy cùng tối) ⇒ neo bằng LƯỢT KHÁM trong
  `NEO_LUOT_NGAY` ngày trước thư: tờ vào hồ sơ theo lượt (như G8). Có chỉ định của
  lab mà khác loại phiếu ⇒ cùng neo lượt.

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
        q0 = replace(q, ly_do="KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id=ids[0])
        return await _neo_luot(conn, cid, nhan_luc, q0, q)
    cua_kh = [v for v in viec if v.clinic_patient_id == kh]
    q2 = gmail_ghep.quyet_mot_khach(doc.loai, cua_kh, kh, nhan_luc)
    if q2.ly_do is None:
        return q2
    q2 = replace(q2, goi_y_clinic_patient_id=kh)
    # Có chỉ định của lab nhưng KHÁC loại phiếu ⇒ như không có chỉ định (G16), không để
    # "chỉ định sai loại" được tự động ít hơn "không chỉ định nào".
    return await _neo_luot(conn, cid, nhan_luc, q2, q2)


async def _neo_luot(
    conn: asyncpg.Connection,
    cid: str,
    nhan_luc: datetime,
    q: gmail_ghep.QuyetGmail,
    khong_neo: gmail_ghep.QuyetGmail,
) -> gmail_ghep.QuyetGmail:
    """`q` KHONG_THAY_CHI_DINH có khách ⇒ vào hồ sơ theo lượt ≤ `NEO_LUOT_NGAY` ngày
    trước thư; không có lượt (hay lý do khác) ⇒ `khong_neo`."""
    kh = q.goi_y_clinic_patient_id
    if q.ly_do != "KHONG_THAY_CHI_DINH" or kh is None:
        return khong_neo
    luot = await ghep_khach.luot_gan_nhat(
        conn, cid, kh, nhan_luc, so_ngay=NEO_LUOT_NGAY
    )
    return khong_neo if luot is None else gmail_ghep.gan_ho_so(q, luot)
