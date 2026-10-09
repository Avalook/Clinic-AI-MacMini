"""Lý do xếp phòng ở Lịch sử điều phối là chữ tiếng Việt, không mã thô."""

from __future__ import annotations

from clinicai.services.dispatch_service import _ly_do_xep_phong


def _dong(ly_do: str, nguon: str | None = None) -> dict[str, str | None]:
    return {
        "event_type": "service.routed",
        "dich_vu": "Siêu âm 2D",
        "ly_do_ma": ly_do,
        "nguon": nguon,
        "ly_do_chu": None,
    }


def test_lam_tai_ban_kham_co_nhan() -> None:
    assert _ly_do_xep_phong(_dong("LAM_TAI_BAN_KHAM")) == (
        "Siêu âm 2D · Làm tại bàn khám"
    )
    assert _ly_do_xep_phong(_dong("HUY_LAM_TAI_BAN_KHAM")) == (
        "Siêu âm 2D · Huỷ làm tại bàn khám — trả phòng cũ"
    )


def test_xep_phong_quay_thu() -> None:
    assert _ly_do_xep_phong(_dong("INITIAL_ASSIGNMENT", "quay_thu")) == (
        "Siêu âm 2D · xếp phòng · quầy thu"
    )
