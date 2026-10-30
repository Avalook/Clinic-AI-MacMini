"""Phần KHÔNG cần model của trợ lý: luật chặn bằng code + công cụ thuần.

Luật chặn chạy trên CẢ bộ câu vàng: mọi câu khẩn phải bị bắt (thiếu một là đỏ),
và câu thường (hỏi giá, đặt lịch, chào…) không được bắt nhầm — bỏ dấu làm
"chờ em xíu" thành "xiu", "từ từ" thành "tu tu", nên lỗi này có thật.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from clinicai.services.tro_ly_khach import luat_chan
from clinicai.services.tro_ly_khach.cong_cu import (
    CongCuMau,
    doc_ngay,
    khung_con_cho,
    kiem_ngay_xem,
    loc_dich_vu,
)

CAU_VANG: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "cau_vang.json").read_text()
)["cau"]
LUC = datetime(2026, 10, 30, 10, 15)  # Thứ Sáu


def test_bo_cau_vang_hop_le() -> None:
    ma = [c["ma"] for c in CAU_VANG]
    assert len(ma) == len(set(ma)) >= 60
    assert {c["y_dinh"] for c in CAU_VANG} >= {"khan_cap", "hoi_y_khoa", "hoi_gia"}


@pytest.mark.parametrize(
    "cau", [c for c in CAU_VANG if c["y_dinh"] == "khan_cap"], ids=lambda c: c["ma"]
)
def test_moi_cau_khan_deu_bi_code_chan(cau: dict[str, Any]) -> None:
    chan = luat_chan.kiem_tra(cau["tin"])
    assert chan is not None and chan.loai == "khan_cap", cau["tin"]


@pytest.mark.parametrize(
    "cau",
    [
        c
        for c in CAU_VANG
        if c["y_dinh"]
        in {"hoi_gia", "dat_lich", "doi_huy_lich", "hoi_gio_dia_chi", "chao_hoi"}
    ],
    ids=lambda c: c["ma"],
)
def test_cau_thuong_khong_bi_chan_nham(cau: dict[str, Any]) -> None:
    assert luat_chan.kiem_tra(cau["tin"]) is None, cau["tin"]


def test_khan_xet_truoc_y_khoa() -> None:
    chan = luat_chan.kiem_tra("ra máu có nguy hiểm không")
    assert chan is not None and chan.loai == "khan_cap"


def test_bo_dau() -> None:
    assert luat_chan.bo_dau("  Đau BỤNG   dữ dội ") == "dau bung du doi"


@pytest.mark.parametrize("rac", [None, "", "mai", "30/10/2026", "2026-13-40", 20261030])
def test_doc_ngay_rac_tra_none(rac: Any) -> None:
    assert doc_ngay(rac) is None


def test_kiem_ngay_xem() -> None:
    assert kiem_ngay_xem("2026-10-31", LUC) == date(2026, 10, 31)
    assert "loi" in kiem_ngay_xem("2026-10-29", LUC)  # type: ignore[operator]
    assert "loi" in kiem_ngay_xem("2027-06-01", LUC)  # type: ignore[operator]
    assert "loi" in kiem_ngay_xem("rác", LUC)  # type: ignore[operator]


def _slot(h: int, m: int, con_lai: int) -> dict[str, Any]:
    return {
        "time": f"{h:02d}:{m:02d}",
        "minute_of_day": h * 60 + m,
        "slot_minutes": 30,
        "con_lai": con_lai,
    }


def test_khung_con_cho_bo_khung_da_qua_va_khung_day() -> None:
    q = {
        "slots": [_slot(9, 30, 3), _slot(10, 0, 1), _slot(10, 30, 0), _slot(11, 0, 2)],
        "regular_chan": True,
    }
    kq = khung_con_cho(q, LUC.date(), LUC)
    # 09:30 đã kết thúc; 10:00–10:30 đang diễn ra nên vẫn nhận; 10:30 hết chỗ.
    assert kq["khung_con_cho"] == ["10:00", "11:00"]


def test_khung_con_cho_tuan_chua_cong_bo_khong_chan_theo_tran() -> None:
    q = {"slots": [_slot(14, 0, 0)], "regular_chan": False}
    kq = khung_con_cho(q, date(2026, 10, 31), LUC)
    assert kq["khung_con_cho"] == ["14:00"]


def test_khung_con_cho_dong_cua() -> None:
    assert khung_con_cho({"closed": True, "slots": []}, LUC.date(), LUC)["dong_cua"]


def test_loc_dich_vu_khong_dau_va_moi_tu() -> None:
    dong = [{"ten": "Siêu âm đầu dò"}, {"ten": "Siêu âm tuyến vú"}, {"ten": "Khám"}]
    assert [d["ten"] for d in loc_dich_vu(dong, "sieu am vu")] == ["Siêu âm tuyến vú"]
    assert loc_dich_vu(dong, "") == dong
    assert loc_dich_vu(dong, "laser") == []


@pytest.mark.asyncio
async def test_cong_cu_mau_tra_loi_khong_nem() -> None:
    cc = CongCuMau(dong_ho=lambda: LUC)
    assert (await cc.chay("tra_gia_dich_vu", {"tu_khoa": "hpv"}))["dich_vu"]
    assert (await cc.chay("lich_trong", {"ngay": "rác"}))["loi"]
    assert (await cc.chay("khong_co", {}))["loi"]
