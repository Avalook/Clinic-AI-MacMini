"""Luật thuần của PR "kết quả điều trị về đúng chỉ định" (Tuyền chốt 09/10/2026):
chỉ định nào mang sang lượt mới, phiếu nào đã là kết quả."""

from __future__ import annotations

from clinicai.phieu_kham.mau_dieu_tri import phieu_co_ket_qua
from clinicai.services.chi_dinh_service import chon_mang_sang
from clinicai.services.dieu_tri_ban_kham import nhan_noi_lam

GHE = "CLS_GHE_DTT"


def test_kham_thuong_chi_mang_cai_da_thu() -> None:
    cu = [("a", "SA", "PAID"), ("b", "SA", "DUE"), ("c", GHE, "DUE")]
    assert chon_mang_sang(cu, di_thang_phong=False, ma_dieu_tri=None) == {"a": True}


def test_di_thang_phong_mang_ca_chua_thu_tru_tien_dang_do() -> None:
    cu = [
        ("a", "SA", "DUE"),
        ("b", "SA", "PENDING_VERIFICATION"),
        ("c", "SA", "NOT_APPLICABLE"),
        ("d", "SA", "REFUND_PENDING"),
    ]
    assert chon_mang_sang(cu, di_thang_phong=True, ma_dieu_tri=None) == {
        "a": False,
        "c": False,
    }


def test_luot_dieu_tri_dung_mot_chi_dinh_chua_thu_gan_nhat_dung_dich_vu() -> None:
    cu = [
        ("cu_nhat", GHE, "DUE"),
        ("sa", "SA", "DUE"),
        ("moi_nhat", GHE, "NOT_APPLICABLE"),
    ]
    assert chon_mang_sang(cu, di_thang_phong=False, ma_dieu_tri=GHE) == {
        "moi_nhat": False
    }


def test_luot_dieu_tri_da_co_cai_da_thu_thi_khong_them_cai_chua_thu() -> None:
    cu = [("da_thu", GHE, "PAID"), ("chua", GHE, "DUE")]
    assert chon_mang_sang(cu, di_thang_phong=False, ma_dieu_tri=GHE) == {"da_thu": True}


def test_luot_dieu_tri_tien_dang_do_khong_mang() -> None:
    for tien in ("PENDING_VERIFICATION", "REFUND_PENDING", "FINANCIAL_DATA_INCOMPLETE"):
        cu = [("x", GHE, tien)]
        assert chon_mang_sang(cu, di_thang_phong=False, ma_dieu_tri=GHE) == {}
    khong_ro = chon_mang_sang([("x", GHE, None)], di_thang_phong=False, ma_dieu_tri=GHE)
    assert khong_ro == {}


def _phieu(**kw: object) -> bool:
    base: dict[str, object] = {
        "form_id": "KQ_PHIEU_DIEU_TRI",
        "trang_thai": "DRAFT",
        "revision": 1,
        "du_lieu": {"cam_nhan": {"gia_tri": "Đỡ", "nguon": "USER"}},
    }
    base.update(kw)
    return phieu_co_ket_qua(**base)  # type: ignore[arg-type]


def test_phieu_dieu_tri_co_chu_la_ket_qua() -> None:
    assert _phieu() is True
    assert _phieu(du_lieu='{"cam_nhan": {"gia_tri": "Đỡ"}}') is True


def test_phieu_dieu_tri_chua_luu_hoac_rong_khong_phai_ket_qua() -> None:
    assert _phieu(revision=0) is False
    assert _phieu(du_lieu={"cam_nhan": {"gia_tri": "  \n "}}) is False
    assert _phieu(du_lieu={}) is False


def test_phieu_khac_chi_ready_moi_la_ket_qua() -> None:
    assert _phieu(form_id="KQ_SIEU_AM") is False
    assert _phieu(form_id="KQ_SIEU_AM", trang_thai="READY") is True


def test_phieu_rac_khong_nem() -> None:
    assert _phieu(revision="abc") is False
    assert _phieu(revision=None) is False
    assert _phieu(du_lieu="{không phải json") is False
    assert _phieu(du_lieu=None) is False
    assert _phieu(du_lieu=["x"]) is False
    assert _phieu(du_lieu={"o": "chuỗi trần"}) is False
    assert _phieu(du_lieu={"o": {"gia_tri": ["a"]}}) is False
    assert _phieu(form_id=None, trang_thai=None) is False


def test_nhan_noi_lam() -> None:
    assert nhan_noi_lam("BAN_KHAM", "P. 3") == "Tại bàn khám"
    assert nhan_noi_lam("PHONG", "P. Điều trị 2") == "P. Điều trị 2"
    assert nhan_noi_lam(None, None) is None
