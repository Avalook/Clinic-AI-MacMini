"""Hàm thuần của `bac_si_phu_trach` (Tuyền chốt 29/09/2026 — trợ lý trọn quyền,
bản in "mặc định tên bác sĩ"). Bài kiểm trên Postgres:
`tests/services/test_tro_ly_bac_si_tron_quyen_db.py`."""

from __future__ import annotations

from clinicai.services.bac_si_phu_trach import (
    bac_si_dang_trong_ca,
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
