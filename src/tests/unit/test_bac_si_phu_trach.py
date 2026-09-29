"""Hàm thuần của `bac_si_phu_trach` (Tuyền chốt 29/09/2026 — trợ lý trọn quyền,
bản in "mặc định tên bác sĩ"). Bài kiểm trên Postgres:
`tests/services/test_tro_ly_bac_si_tron_quyen_db.py`."""

from __future__ import annotations

from clinicai.services.bac_si_phu_trach import (
    bac_si_cung_phong,
    bac_si_dang_trong_ca,
    bac_si_trong_ca_hoac_ca_ngay,
    chon_bac_si_phien,
    chon_bac_si_thuc_hien,
    hai_bac_si_khac_nhau,
)


def test_hai_bac_si_khac_nhau_chi_khi_ca_hai_la_bac_si() -> None:
    bs = {"A", "B"}
    assert hai_bac_si_khac_nhau(toi="B", bac_si_cua_viec="A", bac_si=bs)
    assert not hai_bac_si_khac_nhau(toi="A", bac_si_cua_viec="A", bac_si=bs)
    # Trợ lý không bao giờ "giành" của bác sĩ.
    assert not hai_bac_si_khac_nhau(toi="TK", bac_si_cua_viec="A", bac_si=bs)
    # Việc chưa có bác sĩ / đang ghi một người không phải bác sĩ.
    assert not hai_bac_si_khac_nhau(toi="B", bac_si_cua_viec=None, bac_si=bs)
    assert not hai_bac_si_khac_nhau(toi="B", bac_si_cua_viec="DD", bac_si=bs)


def test_chon_bac_si_thuc_hien() -> None:
    # Người bấm là bác sĩ → chính họ.
    assert (
        chon_bac_si_thuc_hien(
            nguoi_bam="A", nguoi_bam_la_bac_si=True, bac_si_phong=["B"]
        )
        == "A"
    )
    # Đúng một bác sĩ đứng phòng → bác sĩ ấy.
    assert (
        chon_bac_si_thuc_hien(
            nguoi_bam="DD", nguoi_bam_la_bac_si=False, bac_si_phong=["B", "B"]
        )
        == "B"
    )
    # Không có / nhiều bác sĩ → giữ người bấm như cũ.
    assert (
        chon_bac_si_thuc_hien(
            nguoi_bam="DD", nguoi_bam_la_bac_si=False, bac_si_phong=[]
        )
        == "DD"
    )
    assert (
        chon_bac_si_thuc_hien(
            nguoi_bam="DD", nguoi_bam_la_bac_si=False, bac_si_phong=["B", "C"]
        )
        == "DD"
    )


def test_bac_si_dang_trong_ca_cong_tac_tat_la_ca_ngay() -> None:
    dong = [("B", "T1", "SANG", "APPROVED"), ("C", "T2", "FULL", "REJECTED")]
    assert bac_si_dang_trong_ca(dong, 20 * 60, {}) == ["B"]


# ── Bác sĩ của phiên + "bác sĩ của phòng" theo ca (29/09/2026) ───────────────

_BAT_CA = {"vai_lich_theo_ca": True}


def test_chon_bac_si_phien_theo_thu_tu_va_chi_bac_si_that() -> None:
    # Ứng viên đầu là điều dưỡng (không phải bác sĩ) → bỏ qua, lấy người kế.
    assert chon_bac_si_phien(["DD", None, "A", "B"], {"A", "B"}, []) == "A"
    # Không ứng viên nào → bác sĩ DUY NHẤT của phòng người bấm.
    assert chon_bac_si_phien([None, None], set(), ["X", "X"]) == "X"
    # Phòng nhiều bác sĩ → không đoán.
    assert chon_bac_si_phien([], set(), ["X", "Y"]) is None
    assert chon_bac_si_phien([], set(), []) is None


def test_bac_si_phong_theo_ca_dang_dien_ra() -> None:
    dong = [
        ("S", "T1", "SANG", "APPROVED"),
        ("C", "T1", "CHIEU", "APPROVED"),
        ("R", "T1", "SANG", "REJECTED"),
    ]
    assert bac_si_trong_ca_hoac_ca_ngay(dong, 9 * 60, _BAT_CA) == ["S"]
    assert bac_si_trong_ca_hoac_ca_ngay(dong, 15 * 60, _BAT_CA) == ["C"]
    # Ngoài giờ ca (tối muộn) → rơi về CẢ NGÀY, không làm rỗng hàng.
    assert bac_si_trong_ca_hoac_ca_ngay(dong, 23 * 60, _BAT_CA) == ["S", "C"]
    # Công tắc ca tắt → cả ngày (trừ REJECTED).
    assert bac_si_trong_ca_hoac_ca_ngay(dong, 9 * 60, {}) == ["S", "C"]


def test_bac_si_cung_phong_theo_phong_dang_dung() -> None:
    toi = [("P1", "T1", "SANG", "APPROVED"), ("P2", "T2", "CHIEU", "APPROVED")]
    bs = [
        ("X", "P1", "T1", "SANG", "APPROVED"),
        ("Y", "P2", "T2", "CHIEU", "APPROVED"),
        ("Z", "P3", "T3", "SANG", "APPROVED"),
    ]
    sang = bac_si_cung_phong(
        dong_cua_toi=toi, dong_bac_si=bs, phut=9 * 60, settings=_BAT_CA
    )
    assert sang == ["X"]
    chieu = bac_si_cung_phong(
        dong_cua_toi=toi, dong_bac_si=bs, phut=15 * 60, settings=_BAT_CA
    )
    assert chieu == ["Y"]
    # Ngoài giờ ca: mọi phòng của tôi hôm nay, mọi bác sĩ của các phòng ấy.
    toi_muon = bac_si_cung_phong(
        dong_cua_toi=toi, dong_bac_si=bs, phut=23 * 60, settings=_BAT_CA
    )
    assert toi_muon == ["X", "Y"]
    assert bac_si_cung_phong(dong_cua_toi=[], dong_bac_si=bs, phut=0, settings={}) == []
