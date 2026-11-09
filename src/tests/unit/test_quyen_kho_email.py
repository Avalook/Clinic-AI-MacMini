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


def test_khoi_cap_rieng_khong_phai_khoi_noi_bo() -> None:
    # Khác khối nội bộ (quản lý không cấp được): khối cấp riêng vẫn cấp được.
    assert not (KHOI_CAP_RIENG & KHOI_NOI_BO)
    # Công tắc lego "Kho email" khai ở G2 cùng trang + mục thanh bên (frontend ép
    # mỗi lego có page.tsx và mục thanh bên) — G1 chưa có màn nào để mở.
    assert "kho_email" not in MAN


def test_quyen_kho_email_da_khai_va_co_module() -> None:
    q = QUYEN["xet_nghiem.kho_email"]
    assert q.khoi == "kho_email"
    assert q.rui_ro.value == "clinical"
    assert "xet_nghiem.kho_email" in MODULE["xet_nghiem_doi_tac"].quyen
    # Sự kiện "mở PDF ở Kho email" khai ở G2, cùng code phát (không khai dây chết).
    assert "lab.archive_viewed" not in DANH_MUC
