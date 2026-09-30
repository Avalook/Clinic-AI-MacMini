"""Chọn bác sĩ trong phòng nhiều bác sĩ — hàm thuần (30/09/2026)."""

from __future__ import annotations

import pytest

from clinicai.core.shifts import CA_MAC_DINH
from clinicai.services.lan_bac_si import (
    DongLich,
    bac_si_cua_phong,
    bac_si_tu_gan,
    can_chon_bac_si,
    dang_trong_ca,
    la_khach_lan_toi,
    lan_cua_nguoi,
    noi_lam,
    ten_bac_si,
)
from clinicai.services.lich_su_phong import dong_lich_su
from clinicai.services.service_routing_service import (
    _ma_bac_si,
    gan_bac_si_vao_ung_vien,
)

CA = dict(CA_MAC_DINH)
SANG, CHIEU, TOI = 9 * 60, 15 * 60, 19 * 60
TRUA = 13 * 60 + 30


def _d(
    ai: str,
    lan: int | None,
    ca: str = "FULL",
    *,
    vi_tri: str | None = None,
    bac_si: bool = True,
    tt: str = "APPROVED",
    sort: int = 0,
) -> DongLich:
    return DongLich(
        room_id="p",
        vi_tri=vi_tri or f"VT{lan}",
        lan=lan,
        sort=sort,
        staff_id=ai,
        ten=f"Tên {ai}",
        ca=ca,
        trang_thai=tt,
        bac_si=bac_si,
    )


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("Nguyễn Văn A", "BS Nguyễn Văn A"),
        ("BS SA Bá Linh", "BS SA Bá Linh"),
        ("bác sĩ Hà", "bác sĩ Hà"),
        ("  ", "BS"),
        (None, "BS"),
        (123, "BS"),
    ],
)
def test_ten_bac_si_khong_lap_chu_bs(vao: object, ra: str) -> None:
    assert ten_bac_si(vao) == ra


def test_noi_lam_ghep_phong_va_bac_si() -> None:
    assert (
        noi_lam("Phòng siêu âm 2 máy", "Bá Linh") == "Phòng siêu âm 2 máy · BS Bá Linh"
    )
    assert noi_lam("Phòng siêu âm 2 máy", None) == "Phòng siêu âm 2 máy"
    assert noi_lam(None, "A") is None and noi_lam("", "A") is None


def test_theo_ca_dang_dien_ra_ngoai_ca_thi_ca_ngay() -> None:
    dong = [_d("a", 1, "SANG"), _d("b", 2, "CHIEU"), _d("c", 2, "TOI")]
    assert [d.staff_id for d in dang_trong_ca(dong, SANG, CA)] == ["a"]
    assert [d.staff_id for d in dang_trong_ca(dong, CHIEU, CA)] == ["b"]
    assert [d.staff_id for d in dang_trong_ca(dong, TOI, CA)] == ["c"]
    # Nghỉ trưa: không ai trong ca → cả ngày (quầy không mất ô chọn).
    assert len(dang_trong_ca(dong, TRUA, CA)) == 3
    # Xem ngày khác (phút None) → cả ngày; REJECTED luôn bỏ.
    dong.append(_d("x", 1, "SANG", tt="REJECTED"))
    assert "x" not in {d.staff_id for d in dang_trong_ca(dong, None, CA)}
    assert "x" not in {d.staff_id for d in dang_trong_ca(dong, SANG, CA)}


def test_lua_chon_theo_lan_moi_bac_si_mot_lan_bo_dieu_duong() -> None:
    dong = [
        _d("b", 2, sort=3),
        _d("dd", 2, bac_si=False, sort=4),
        _d("a", 1, sort=1),
        _d("khong_lan", None, sort=0),
        _d("a", 1, "SANG", vi_tri="VT1b", sort=1),  # trùng người
    ]
    ds = bac_si_cua_phong(dong, SANG, CA)
    assert [(x["staff_id"], x["lan"]) for x in ds] == [
        ("a", 1),
        ("b", 2),
        ("khong_lan", None),
    ]
    assert can_chon_bac_si(ds) and bac_si_tu_gan(ds) is None


def test_mot_bac_si_thi_tu_gan_khong_hien_o() -> None:
    ds = bac_si_cua_phong([_d("a", 1), _d("dd", 1, bac_si=False)], SANG, CA)
    assert not can_chon_bac_si(ds)
    assert (bac_si_tu_gan(ds) or {}).get("staff_id") == "a"
    assert bac_si_tu_gan([]) is None and not can_chon_bac_si([])


def test_lan_cua_nguoi_va_loc_khach() -> None:
    lua_chon = bac_si_cua_phong([_d("a", 1), _d("b", 2)], SANG, CA)
    # Điều dưỡng làn 2.
    toi = lan_cua_nguoi(
        [_d("dd", 2, bac_si=False)], lua_chon, toi="dd", phut=SANG, ca=CA
    )
    assert toi["co"] and toi["lan"] == [2] and toi["bac_si_ids"] == ["b"]
    assert toi["nhan"].startswith("Làn 2 · BS")
    assert la_khach_lan_toi(bac_si_lam_id="b", lan_lam=2, lan_toi=toi)
    assert not la_khach_lan_toi(bac_si_lam_id="a", lan_lam=1, lan_toi=toi)
    # Chưa chọn bác sĩ: thuộc mọi làn.
    assert la_khach_lan_toi(bac_si_lam_id=None, lan_lam=None, lan_toi=toi)
    # Lựa chọn cũ không ghi làn nhưng đúng bác sĩ của làn tôi.
    assert la_khach_lan_toi(bac_si_lam_id="b", lan_lam=None, lan_toi=toi)
    # Không đứng làn nào → không lọc gì.
    khong = lan_cua_nguoi(
        [_d("x", None, bac_si=False)], lua_chon, toi="x", phut=SANG, ca=CA
    )
    assert not khong["co"]
    assert la_khach_lan_toi(bac_si_lam_id="a", lan_lam=1, lan_toi=khong)
    # Bác sĩ đứng vị trí không ghi làn → "làn" của chính mình.
    bs = lan_cua_nguoi([_d("c", None)], lua_chon, toi="c", phut=SANG, ca=CA)
    assert bs["co"] and bs["bac_si_ids"] == ["c"]


def test_gan_bac_si_vao_ung_vien_chi_khi_hai_bac_si() -> None:
    uv = [{"room_id": "p1"}, {"room_id": "p2"}, {"room_id": "p3"}]
    gan_bac_si_vao_ung_vien(
        uv,
        {
            "p1": [{"staff_id": "a"}, {"staff_id": "b"}],
            "p2": [{"staff_id": "c"}],
        },
    )
    assert [len(u["bac_si"]) for u in uv] == [2, 0, 0]


@pytest.mark.parametrize("rac", [None, "", "   "])
def test_ma_bac_si_rong_la_bo_chon(rac: object) -> None:
    assert _ma_bac_si(rac) is None


def test_ma_bac_si_rac_bi_tu_choi() -> None:
    from clinicai.api.exceptions import ValidationError

    with pytest.raises(ValidationError):
        _ma_bac_si("khong-phai-uuid")
    with pytest.raises(ValidationError):
        _ma_bac_si(123)


def test_lich_su_chon_bac_si() -> None:
    ten = {"a": "Nguyễn A", "b": "BS Bá Linh"}
    phong = {"p": "Phòng siêu âm 2 máy"}

    def cau(**p: object) -> str:
        return str(
            dong_lich_su(
                loai="service.doctor_chosen",
                payload={"room_id": "p", **p},
                ten_phong=phong,
                luc=None,
                ai=None,
                ten_nguoi=ten,
            )["cau"]
        )

    assert cau(bac_si_id="a", nguon="quay_thu") == (
        "Quầy thu chọn BS Nguyễn A · Phòng siêu âm 2 máy"
    )
    assert "đổi bác sĩ BS Nguyễn A → BS Bá Linh" in cau(
        bac_si_id="b", tu_bac_si_id="a", nguon="truong_ca"
    )
    assert cau(tu_bac_si_id="a", nguon="quay_thu").startswith("Quầy thu bỏ chọn bác sĩ")
    assert cau(bac_si_id="a", tu_dong=True).endswith("phòng chỉ có một bác sĩ trực")
    # Payload rác vẫn ra một dòng.
    assert dong_lich_su(
        loai="service.doctor_chosen",
        payload="rac",  # type: ignore[arg-type]
        ten_phong={},
        luc=None,
        ai=None,
    )["cau"]
