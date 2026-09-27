"""Luật gộp kỹ năng → lego (ky_nang_service.ke_hoach), Tuyền chốt 28/09/2026."""

from __future__ import annotations

from clinicai.services.ky_nang_service import KyNang, ke_hoach

SA = KyNang("phu_sa", frozenset({"phong"}), frozenset({"sa1", "sa2"}))
TT = KyNang("thu_thuat", frozenset({"phong"}), frozenset({"tt1", "tt2"}))
BIO = KyNang("bio", frozenset({"phong"}), frozenset({"bio"}))
LAY_MAU = KyNang(
    "lay_mau", frozenset({"phong"}), frozenset({"sa1", "sa2", "tt1", "tt2"})
)
TKYK = KyNang("tkyk", frozenset({"ban_kham"}), frozenset())
PHU_BS = KyNang("phu_bs_san", frozenset({"ban_kham"}), frozenset())
LE_TAN = KyNang("le_tan", frozenset({"tiep_don", "thu_tien_dv"}), frozenset())
MOI_PHONG = KyNang("moi", frozenset({"phong"}), frozenset())


def test_bat_them_phong_khong_mat_phong_dang_co() -> None:
    kh = ke_hoach(
        ky_nang=BIO,
        bat=True,
        con_lai=[SA],
        lego_dang_co={"phong"},
        phong_dang_co=["sa1", "sa2"],
    )
    assert kh.bat == {"phong"}
    assert kh.phong == ("bio", "sa1", "sa2")


def test_bat_ky_nang_khong_phong_la_moi_phong() -> None:
    kh = ke_hoach(
        ky_nang=MOI_PHONG, bat=True, con_lai=[], lego_dang_co=set(), phong_dang_co=None
    )
    assert kh.phong is None


def test_bo_ky_nang_chi_bo_phong_cua_rieng_no() -> None:
    kh = ke_hoach(
        ky_nang=BIO,
        bat=False,
        con_lai=[SA],
        lego_dang_co={"phong"},
        phong_dang_co=["bio", "sa1", "sa2"],
    )
    assert kh.tat == set()
    assert kh.bat == {"phong"}
    assert kh.phong == ("sa1", "sa2")


def test_bo_ky_nang_trung_phong_voi_ky_nang_khac_giu_phong() -> None:
    # Lấy mẫu trùm phòng của Phụ SA: bỏ Phụ SA vẫn giữ sa1, sa2 cho Lấy mẫu.
    kh = ke_hoach(
        ky_nang=SA,
        bat=False,
        con_lai=[LAY_MAU],
        lego_dang_co={"phong"},
        phong_dang_co=["sa1", "sa2", "tt1", "tt2"],
    )
    assert kh.phong == ("sa1", "sa2", "tt1", "tt2")


def test_bo_ky_nang_cung_lego_voi_ky_nang_khac_khong_tat() -> None:
    # TKYK và Phụ BS Sản cùng mở Bàn khám — bỏ một cái không tắt Bàn khám.
    kh = ke_hoach(
        ky_nang=TKYK,
        bat=False,
        con_lai=[PHU_BS],
        lego_dang_co={"ban_kham"},
        phong_dang_co=None,
    )
    assert kh.tat == set()


def test_bo_ky_nang_cuoi_tat_lego() -> None:
    kh = ke_hoach(
        ky_nang=LE_TAN,
        bat=False,
        con_lai=[TKYK],
        lego_dang_co={"tiep_don", "thu_tien_dv", "ban_kham"},
        phong_dang_co=None,
    )
    assert kh.tat == {"tiep_don", "thu_tien_dv"}


def test_bo_ky_nang_phong_cuoi_cung_tat_phong() -> None:
    kh = ke_hoach(
        ky_nang=TT,
        bat=False,
        con_lai=[],
        lego_dang_co={"phong"},
        phong_dang_co=["tt1", "tt2"],
    )
    assert kh.tat == {"phong"}
    assert kh.bat == set()
