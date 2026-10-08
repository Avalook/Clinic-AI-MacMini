"""Bảng Bác sĩ × tuần cho màn Đặt lịch (Tuyền duyệt 16/09/2026).

Mỗi ô tóm từ CHÍNH kết quả `quote` — một nguồn "còn chỗ" với popup khung giờ.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.capacity_service import (
    bang_tuan,
    nguong_it_cho,
    tom_tat_ngay,
)
from tests.services.fake_sql import pool


def _q(date: str = "2026-09-17", **kw: Any) -> dict[str, Any]:
    slots = kw.pop(
        "slots",
        [
            {"regular_cap": 2, "regular_used": 1, "con_lai": 1},
            {"regular_cap": 2, "regular_used": 0, "con_lai": 2},
        ],
    )
    base = {
        "date": date,
        "closed": False,
        "off_duty": False,
        "dat_tu_do": False,
        "it_cho_toi_da": 2,
        "slots": slots,
    }
    base.update(kw)
    return base


def test_con_cho_it_cho_day_theo_tong_cua_ngay() -> None:
    nhieu = [{"regular_cap": 3, "regular_used": 0, "con_lai": 3}] * 4  # 12 chỗ
    o = tom_tat_ngay(_q(slots=nhieu), hom_nay="2026-09-16")
    assert (o["trang_thai"], o["con_cho"], o["tong_cho"]) == ("CON_CHO", 12, 12)
    # Còn 3/4 chỗ ≤ ngưỡng 2? không; ≤ 20% của 4 = 1? không → nhưng còn 3 > 2.
    it = [
        {"regular_cap": 5, "regular_used": 4, "con_lai": 1},
        {"regular_cap": 5, "regular_used": 4, "con_lai": 1},
    ]
    assert tom_tat_ngay(_q(slots=it), hom_nay="2026-09-16")["trang_thai"] == "IT_CHO"
    day = [{"regular_cap": 2, "regular_used": 2, "con_lai": 0}]
    assert tom_tat_ngay(_q(slots=day), hom_nay="2026-09-16")["trang_thai"] == "DAY"


def test_it_cho_con_tinh_theo_20_phan_tram_khi_ngay_lon() -> None:
    # Tổng 40 chỗ, còn 8 = 20% → ít chỗ dù 8 > ngưỡng số 2.
    slots = [{"regular_cap": 4, "regular_used": 3, "con_lai": 1}] * 8 + [
        {"regular_cap": 4, "regular_used": 4, "con_lai": 0}
    ] * 2
    assert tom_tat_ngay(_q(slots=slots), hom_nay="2026-09-16")["trang_thai"] == "IT_CHO"


def test_tu_do_nghi_dong_cua_da_qua_khong_in_so_cho() -> None:
    assert (
        tom_tat_ngay(_q(dat_tu_do=True), hom_nay="2026-09-16")["trang_thai"] == "TU_DO"
    )
    tu_do = tom_tat_ngay(_q(dat_tu_do=True), hom_nay="2026-09-16")
    assert tu_do["con_cho"] is None and tu_do["da_dat"] == 1
    assert (
        tom_tat_ngay(_q(off_duty=True, closed=True, slots=[]), hom_nay="2026-09-16")[
            "trang_thai"
        ]
        == "NGHI"
    )
    assert (
        tom_tat_ngay(_q(closed=True, slots=[]), hom_nay="2026-09-16")["trang_thai"]
        == "DONG_CUA"
    )
    qua = tom_tat_ngay(_q(date="2026-09-15"), hom_nay="2026-09-16")
    assert qua["trang_thai"] == "DA_QUA" and qua["con_cho"] is None


@pytest.mark.parametrize(
    "raw,ra",
    [
        ('{"it_cho_toi_da": 4}', 4),
        ({"it_cho_toi_da": 0}, 0),
        ({"it_cho_toi_da": "nhiều"}, 2),
        ({"it_cho_toi_da": True}, 2),
        ({"it_cho_toi_da": 999}, 2),
        ("{hỏng", 2),
        (None, 2),
    ],
)
def test_nguong_it_cho_doc_cau_hinh_khong_bao_gio_nem(raw: object, ra: int) -> None:
    assert nguong_it_cho(raw) == ra


class _SvcGia:
    def __init__(self) -> None:
        self.goi: list[tuple[str, str | None]] = []
        #: Số lần lưới hỏi lịch trực. Từ 16/09/2026 phải là ĐÚNG MỘT — trước đó
        #: mỗi ô tự hỏi lại, và trên máy chủ thật (17 bác sĩ × 7 ngày) thành 126
        #: lời gọi cho một lần mở màn.
        self.lan_hoi_boi_canh = 0

    async def boi_canh_tuan(
        self, *, clinic_id: str, ngay: list[str], location_id: str | None = None
    ) -> dict[str, dict[str, Any]]:
        self.lan_hoi_boi_canh += 1
        return {d: {"ca_theo_bac_si": {}} for d in ngay}

    async def quote(
        self,
        *,
        date: str,
        location_id: str,
        doctor_id: str | None,
        clinic_id: str,
        boi_canh: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.goi.append((date, doctor_id))
        assert boi_canh is not None, (
            "lưới tuần phải truyền bối cảnh đã lấy sẵn xuống từng ô — "
            "thiếu nó là mỗi ô lại tự hỏi lịch trực một lần"
        )
        return _q(date=date, dat_tu_do=doctor_id is None)


@pytest.mark.asyncio
async def test_bang_tuan_moi_bac_si_7_ngay_them_hang_chua_phan() -> None:
    svc = _SvcGia()
    p = pool(
        (
            "FROM clinic_membership m",
            [{"id": "b1", "full_name": "BS A", "role": "DOCTOR"}],
        )
    )
    out = await bang_tuan(
        svc,  # type: ignore[arg-type]
        p,
        week_start="2026-09-17",  # thứ Năm → lùi về thứ Hai
        location_id="loc",
        clinic_id="c",
        hom_nay="2026-09-16",
    )
    assert out["week_start"] == "2026-09-14" and len(out["ngay"]) == 7
    assert [b["full_name"] for b in out["bac_si"]] == ["BS A", "Chưa phân bác sĩ"]
    # MỘT lần hỏi lịch trực cho cả tuần, dù lưới có bao nhiêu ô.
    assert svc.lan_hoi_boi_canh == 1
    assert len(svc.goi) == 14
    assert out["bac_si"][1]["o"][3]["trang_thai"] == "TU_DO"
    assert out["bac_si"][0]["o"][0]["trang_thai"] == "DA_QUA"
    with pytest.raises(ValidationError):
        await bang_tuan(
            svc,  # type: ignore[arg-type]
            p,
            week_start="hôm nay",
            location_id="l",
            clinic_id="c",
            hom_nay="2026-09-16",
        )
