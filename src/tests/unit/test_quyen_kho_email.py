"""Quyền Kho email kết quả (tạm) — chỉ cấp riêng từng người (Gmail G1, 09/11/2026).

Kho chứa mọi thư kết quả đối tác (dữ liệu sức khoẻ, cả thư cũ chưa ghép). "Kho tạm
để mình tôi xem" (Tuyền) ⇒ khối KHÔNG được rơi vào nhóm mẫu nào — kể cả Quản lý, nơi
mọi khối mới tự vào — và không vào "mở full"; vẫn bật/tắt được cho từng người ở màn
Phân quyền.
"""

from __future__ import annotations

from clinicai.events.catalogue import DANH_MUC
from clinicai.modules import MODULE
from clinicai.permissions.catalogue import (
    KHOI,
    KHOI_CAP_RIENG,
    KHOI_MO_FULL,
    KHOI_NOI_BO,
    MAN,
    PRESET,
    QUYEN,
)


def test_khoi_kho_email_khong_nam_trong_nhom_mau_nao() -> None:
    assert "kho_email" in KHOI
    assert "kho_email" in KHOI_CAP_RIENG
    for vai, khoi in PRESET.items():
        assert "kho_email" not in khoi, vai
    assert "kho_email" not in KHOI_MO_FULL


def test_khoi_cap_rieng_van_cap_duoc_o_man_phan_quyen() -> None:
    # Khác khối nội bộ (quản lý không cấp được): khối cấp riêng phải có công tắc.
    assert not (KHOI_CAP_RIENG & KHOI_NOI_BO)
    man = MAN["kho_email"]  # G2b: lego cùng trang + mục thanh bên
    assert "kho_email" in man.khoi
    assert "/ban-xet-nghiem/kho-email" in man.cac_duong


def test_quyen_kho_email_da_khai_va_co_module() -> None:
    q = QUYEN["xet_nghiem.kho_email"]
    assert q.khoi == "kho_email"
    assert q.rui_ro.value == "clinical"
    assert "xet_nghiem.kho_email" in MODULE["xet_nghiem_doi_tac"].quyen
    # Sự kiện "mở PDF ở Kho email" (G2b) — khai cùng code phát (kho_email.mo_pdf).
    assert "lab.archive_viewed" in DANH_MUC
    assert "lab.archive_viewed" in MODULE["xet_nghiem_doi_tac"].phat
