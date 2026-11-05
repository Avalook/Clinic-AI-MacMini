"""Bảng test hàm trạng thái xét nghiệm đối tác (kế hoạch 4.6 + 5c, ≥ 15 ca)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from clinicai.services.xet_nghiem.trang_thai import (
    NHAN,
    THU_TU,
    SuViecXN,
    trang_thai_xet_nghiem,
)

H = date(2026, 11, 5)
HQ = H - timedelta(days=1)

CA = [
    # (tên, sự việc, mã mong đợi)
    ("moi_chi_dinh", SuViecXN(hom_nay=H), "CHO_THU"),
    ("da_thu", SuViecXN(hom_nay=H, ngay_thu=H), "CHO_LAY_MAU"),
    ("thu_0d_van_tinh", SuViecXN(hom_nay=H, ngay_thu=H), "CHO_LAY_MAU"),
    ("quan_ly_cho_qua", SuViecXN(hom_nay=H, duoc_cho_qua=True), "CHO_LAY_MAU"),
    (
        "co_mau",
        SuViecXN(hom_nay=H, ngay_thu=HQ, co_mau=True, hen_tra=H),
        "CHO_KET_QUA",
    ),
    (
        "co_mau_khong_thu_nhung_cho_qua",
        SuViecXN(hom_nay=H, duoc_cho_qua=True, co_mau=True, hen_tra=H),
        "CHO_KET_QUA",
    ),
    ("co_tep", SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, co_tep=True), "CO_KET_QUA"),
    (
        "da_gui",
        SuViecXN(hom_nay=H, co_mau=True, co_tep=True, tep_moi_nhat_da_gui=True),
        "DA_GUI",
    ),
    (
        "ban_2_chua_gui",
        SuViecXN(hom_nay=H, co_mau=True, co_tep=True, tung_gui=True),
        "CO_KET_QUA",
    ),
    ("huy_chi_dinh", SuViecXN(hom_nay=H, da_huy_chi_dinh=True), "DA_HUY"),
    (
        "huy_thang_da_gui",
        SuViecXN(
            hom_nay=H, da_huy_chi_dinh=True, co_tep=True, tep_moi_nhat_da_gui=True
        ),
        "DA_HUY",
    ),
    (
        "huy_thang_dong",
        SuViecXN(hom_nay=H, da_huy_chi_dinh=True, da_dong=True),
        "DA_HUY",
    ),
    (
        "da_gui_thang_dong",
        SuViecXN(hom_nay=H, co_tep=True, tep_moi_nhat_da_gui=True, da_dong=True),
        "DA_GUI",
    ),
    (
        "dong_khi_cho_ket_qua",
        SuViecXN(hom_nay=H, ngay_thu=H, co_mau=True, da_dong=True),
        "DA_DONG",
    ),
    (
        "dong_thang_co_tep_chua_gui",
        SuViecXN(hom_nay=H, co_mau=True, co_tep=True, da_dong=True),
        "DA_DONG",
    ),
    ("dong_khi_cho_thu", SuViecXN(hom_nay=H, da_dong=True), "DA_DONG"),
    # Mẫu bị huỷ (MAU_HONG): co_mau=False — về chờ lấy mẫu, khoản thu giữ nguyên.
    ("mau_huy_ve_cho_lay_mau", SuViecXN(hom_nay=H, ngay_thu=HQ), "CHO_LAY_MAU"),
    # Tệp bị từ chối/thu hồi hết: co_tep=False — về chờ kết quả.
    (
        "tep_tu_choi_ve_cho_ket_qua",
        SuViecXN(hom_nay=H, ngay_thu=HQ, co_mau=True, tung_gui=True),
        "CHO_KET_QUA",
    ),
]


@pytest.mark.parametrize(("ten", "sv", "ma"), CA, ids=[c[0] for c in CA])
def test_bang_trang_thai(ten: str, sv: SuViecXN, ma: str) -> None:
    tt = trang_thai_xet_nghiem(sv)
    assert tt.ma == ma, ten
    assert tt.nhan == NHAN[ma]


def test_chi_cho_lay_mau_moi_mo_nut() -> None:
    for _, sv, ma in CA:
        tt = trang_thai_xet_nghiem(sv)
        assert tt.co_the_lay_mau == (ma == "CHO_LAY_MAU")
        assert (tt.ly_do_khong_lay_mau is None) == tt.co_the_lay_mau


def test_cho_thu_ly_do_cho_nut_mo() -> None:
    tt = trang_thai_xet_nghiem(SuViecXN(hom_nay=H))
    assert tt.ly_do_khong_lay_mau == "Chưa ghi nhận thu hộ"


@pytest.mark.parametrize(
    ("hen_tra", "qua", "so_ngay"),
    [(H, False, 0), (HQ, True, 1), (H - timedelta(days=3), True, 3), (None, False, 0)],
)
def test_qua_hen_tra(hen_tra: date | None, qua: bool, so_ngay: int) -> None:
    tt = trang_thai_xet_nghiem(
        SuViecXN(hom_nay=H, ngay_thu=HQ, co_mau=True, hen_tra=hen_tra)
    )
    assert (tt.qua_hen, tt.so_ngay_qua_hen) == (qua, so_ngay)


@pytest.mark.parametrize(
    ("lui", "vang"), [(0, False), (1, False), (2, True), (5, True)]
)
def test_qua_han_lay_mau_nguong_2_ngay(lui: int, vang: bool) -> None:
    tt = trang_thai_xet_nghiem(SuViecXN(hom_nay=H, ngay_thu=H - timedelta(days=lui)))
    assert tt.qua_han_lay_mau is vang


def test_nguong_lay_mau_doc_tu_cai_dat() -> None:
    sv = SuViecXN(hom_nay=H, ngay_thu=HQ, nguong_lay_mau_ngay=1)
    assert trang_thai_xet_nghiem(sv).qua_han_lay_mau is True


def test_cho_qua_khong_co_ngay_thu_khong_vang() -> None:
    tt = trang_thai_xet_nghiem(SuViecXN(hom_nay=H, duoc_cho_qua=True))
    assert tt.qua_han_lay_mau is False


def test_hoan_tien_la_co_phu_khong_phai_trang_thai() -> None:
    tt = trang_thai_xet_nghiem(SuViecXN(hom_nay=H, ngay_thu=H, da_hoan_tien=True))
    assert (tt.ma, tt.da_hoan_tien) == ("CHO_LAY_MAU", True)


def test_thu_tu_du_moi_ma() -> None:
    assert set(THU_TU) == set(NHAN)


#: Ratchet (luật 3, kế hoạch 4.6): mã trạng thái chỉ được viết ở module trạng thái.
MA_CHI_O_TRANG_THAI = ("CHO_LAY_MAU", "CHO_KET_QUA", "CO_KET_QUA", "DA_DONG")

#: Tệp CŨ (bàn đối tác cũ, trạng thái riêng của nó) đã dùng chuỗi trùng tên trước
#: 05/11/2026 — CHỈ ĐƯỢC BỚT (chặng 4 tắt bàn cũ thì gạch dần). Thêm tên vào đây là vi
#: phạm luật 1 + 3: màn mới phải đọc `trang_thai_xet_nghiem()`.
TEP_CU_DUOC_PHEP = frozenset(
    {
        "clinicai/phieu_kham/ket_qua_chi_dinh.py",
        "clinicai/services/man_khach_hang_service.py",
        "clinicai/services/doi_tac_service.py",
        "clinicai/services/lam_them_tai_quay_service.py",
        "dashboard/app/doi-tac/BangDoiTac.tsx",
        "dashboard/app/(dashboard)/customers/CustomersView.tsx",
        "dashboard/app/(dashboard)/ban-kham/BanKham.tsx",
        "dashboard/app/(dashboard)/_lam-viec/NhapKetQuaLamThem.tsx",
        "dashboard/app/(dashboard)/_lam-viec/KhoiDoiTac.tsx",
        "dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx",
        "dashboard/app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx",
    }
)


def test_ma_trang_thai_khong_viet_ngoai_module() -> None:
    src = Path(__file__).resolve().parents[2]
    goc = src / "clinicai" / "services" / "xet_nghiem" / "trang_thai.py"
    pat = re.compile(r"['\"](" + "|".join(MA_CHI_O_TRANG_THAI) + r")['\"]")
    tep = [
        *src.joinpath("clinicai").rglob("*.py"),
        *src.joinpath("dashboard", "app").rglob("*.tsx"),
    ]
    co = {
        str(p.relative_to(src))
        for p in tep
        if p != goc
        and "node_modules" not in p.parts
        and pat.search(p.read_text(encoding="utf-8", errors="ignore"))
    }
    assert co <= TEP_CU_DUOC_PHEP, (
        f"Mã trạng thái XN viết ngoài trang_thai.py: {sorted(co - TEP_CU_DUOC_PHEP)}"
    )
