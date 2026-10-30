"""Canh gác máy chủ: ngưỡng ổ đĩa, khung giờ sao lưu, bộ đo chết, tệp rác."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from clinicai.services.canh_gac import KetQuaKiem
from clinicai.services.canh_gac_may_chu import (
    danh_gia_may_chu,
    doc_trang_thai,
    kiem_may_chu,
)

# 10:00 giờ VN — trong khung sao lưu.
GIUA_NGAY = datetime(2026, 10, 31, 3, 0, tzinfo=UTC)


def snap(
    luc: datetime = GIUA_NGAY,
    pt: Any = 70.0,
    sao_luu_truoc: timedelta | None = timedelta(minutes=10),
) -> dict[str, Any]:
    return {
        "generated_at": luc.isoformat(),
        "host": {"disk_used_percent": pt},
        "backup": None
        if sao_luu_truoc is None
        else {"completed_at": (luc - sao_luu_truoc).isoformat()},
    }


def theo_ma(kq: list[KetQuaKiem]) -> dict[str, KetQuaKiem]:
    return {k.ma: k for k in kq}


@pytest.mark.parametrize(
    ("pt", "gan_day", "rat_day"),
    [
        (70.0, False, False),
        (82.0, False, False),
        (83.0, None, False),  # trong khoảng đệm: giữ nguyên
        (85.0, None, False),  # đúng ngưỡng chưa mở
        (86.0, True, False),
        (90.0, True, False),
        (91.0, True, None),
        (92.0, True, None),  # đúng ngưỡng chưa mở
        (93.0, True, True),
    ],
)
def test_nguong_o_dia(pt: float, gan_day: bool | None, rat_day: bool | None) -> None:
    kq = theo_ma(danh_gia_may_chu(snap(pt=pt), GIUA_NGAY))
    assert kq["O_DIA_GAN_DAY"].co_chuyen is gan_day
    assert kq["O_DIA_RAT_DAY"].co_chuyen is rat_day
    assert kq["O_DIA_RAT_DAY"].muc == "critical"


@pytest.mark.parametrize("rac", [None, "89", True, [], {}])
def test_so_o_dia_rac_thi_bo_qua(rac: Any) -> None:
    kq = theo_ma(danh_gia_may_chu(snap(pt=rac), GIUA_NGAY))
    assert "O_DIA_GAN_DAY" not in kq
    assert kq["SAO_LUU_CU"].co_chuyen is False


@pytest.mark.parametrize(
    ("gio_utc", "phut", "trong_khung"),
    [
        (0, 0, False),  # 07:00 VN — bản đầu ngày chưa kịp
        (0, 29, False),
        (0, 30, True),  # 07:30 VN
        (15, 29, True),  # 22:29 VN
        (15, 30, False),  # 22:30 VN
        (19, 30, False),  # 02:30 VN
    ],
)
def test_khung_gio_sao_luu(gio_utc: int, phut: int, trong_khung: bool) -> None:
    luc = datetime(2026, 10, 31, gio_utc, phut, tzinfo=UTC)
    kq = theo_ma(danh_gia_may_chu(snap(luc, sao_luu_truoc=timedelta(hours=5)), luc))
    if trong_khung:
        assert kq["SAO_LUU_CU"].co_chuyen is True
    else:
        assert "SAO_LUU_CU" not in kq


@pytest.mark.parametrize(
    ("cach", "co_chuyen"),
    [(timedelta(minutes=119), False), (timedelta(minutes=121), True)],
)
def test_nguong_sao_luu(cach: timedelta, co_chuyen: bool) -> None:
    kq = theo_ma(danh_gia_may_chu(snap(sao_luu_truoc=cach), GIUA_NGAY))
    assert kq["SAO_LUU_CU"].co_chuyen is co_chuyen


def test_ban_sao_luu_khong_dat_la_co_chuyen() -> None:
    """Bộ đo trả backup = null khi bản mới nhất không `verified`."""
    k = theo_ma(danh_gia_may_chu(snap(sao_luu_truoc=None), GIUA_NGAY))["SAO_LUU_CU"]
    assert k.co_chuyen is True
    assert k.muc == "critical"
    assert "hỏng" in k.noi_dung


def test_bo_do_chet_giu_nguyen_ma_khac() -> None:
    cu = GIUA_NGAY - timedelta(minutes=16)
    kq = danh_gia_may_chu(snap(cu, pt=99.0), GIUA_NGAY)
    assert [(k.ma, k.co_chuyen) for k in kq] == [("MAY_CHU_KHONG_DO", True)]


def test_bo_do_vua_du_moi() -> None:
    vua = GIUA_NGAY - timedelta(minutes=15)
    kq = theo_ma(danh_gia_may_chu(snap(vua), GIUA_NGAY))
    assert kq["MAY_CHU_KHONG_DO"].co_chuyen is False


def test_khong_co_tep_thi_khong_kiem() -> None:
    assert danh_gia_may_chu(None, GIUA_NGAY) == []


@pytest.mark.parametrize("noi_dung", [b"", b"{rac", b"[1]", b"x" * (256 * 1024 + 1)])
def test_tep_rac_bao_bo_do_chet(
    noi_dung: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tep = tmp_path / "status.json"
    tep.write_bytes(noi_dung)
    monkeypatch.setenv("OPS_STATUS_FILE", str(tep))
    assert doc_trang_thai() == {}
    assert [k.ma for k in kiem_may_chu(GIUA_NGAY)] == ["MAY_CHU_KHONG_DO"]


def test_doc_tep_that(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tep = tmp_path / "status.json"
    tep.write_text(json.dumps(snap(pt=89.0)), encoding="utf-8")
    monkeypatch.setenv("OPS_STATUS_FILE", str(tep))
    assert theo_ma(kiem_may_chu(GIUA_NGAY))["O_DIA_GAN_DAY"].noi_dung.startswith(
        "Ổ gốc VPS đang dùng 89%"
    )
    monkeypatch.setenv("OPS_STATUS_FILE", str(tmp_path / "khong-co.json"))
    assert kiem_may_chu(GIUA_NGAY) == []


def test_moc_gio_rac_khong_nem() -> None:
    kq = danh_gia_may_chu({"generated_at": "hôm qua"}, GIUA_NGAY)
    assert [k.ma for k in kq] == ["MAY_CHU_KHONG_DO"]
