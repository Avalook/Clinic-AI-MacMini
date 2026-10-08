"""Lưới đặt chỗ đọc sức chứa từ máy chủ (29/09/2026) — phần không cần database.

Bản chạy thật qua trigger nằm ở `tests/services/test_luoi_ngay_khop_trigger_db.py`.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from clinicai.core.trang_thai_lich import DEAD_STATUSES, giu_cho
from clinicai.services.capacity_service import (
    LUOI_NGAY_TOI_DA_BAC_SI,
    luoi_ngay,
    tran_co_chan,
)
from clinicai.services.week_appointments_service import (
    HIDDEN_STATUSES,
    _row_to_dict,
    dem_ghe_truc_tiep,
)

BS_A = "a33a95b4-b43f-479f-8b01-f1003436d85d"
BS_B = "b44b95b4-b43f-479f-8b01-f1003436d85d"


class _Svc:
    """Ghi lại mọi lời gọi; không có database nào ở đây."""

    def __init__(self) -> None:
        self.boi_canh_hoi: list[list[str]] = []
        self.quote_goi: list[dict[str, Any]] = []

    async def boi_canh_tuan(
        self, *, clinic_id: str, ngay: list[str], location_id: str | None = None
    ) -> dict[str, Any]:
        self.boi_canh_hoi.append(ngay)
        return {ngay[0]: {"tuan_da_cong_bo": True}}

    async def quote(self, **kw: Any) -> dict[str, Any]:
        self.quote_goi.append(kw)
        return {
            "doctor_id": kw["doctor_id"],
            "location_id": kw["location_id"],
            "slots": [],
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("rac", ["", "rác", "2026-13-45", "29/09/2026"])
async def test_ngay_rac_tra_luoi_rong_khong_nem(rac: str) -> None:
    svc = _Svc()
    kq = await luoi_ngay(svc, clinic_id="c", date=rac, doctor_ids=[BS_A])  # type: ignore[arg-type]
    assert kq["hang"] == []
    assert svc.boi_canh_hoi == [] and svc.quote_goi == [], "không chạm database"


@pytest.mark.asyncio
async def test_mot_luot_moi_bac_si_mot_hang_them_hang_chua_phan_cuoi() -> None:
    svc = _Svc()
    kq = await luoi_ngay(
        svc,  # type: ignore[arg-type]
        clinic_id="c",
        date="2026-09-30",
        doctor_ids=[BS_A, "rác", BS_A.upper(), "", BS_B],
        bo_qua_lich_id="không-phải-uuid",
    )
    assert [h["doctor_id"] for h in kq["hang"]] == [BS_A, BS_B, None]
    # Bối cảnh lịch trực hỏi MỘT lần cho cả lưới, không một lần mỗi hàng.
    assert svc.boi_canh_hoi == [["2026-09-30"]]
    for g in svc.quote_goi:
        # Đếm ghế ở MỌI cơ sở — như trigger (slot_seats_used không kèm cơ sở).
        assert g["location_id"] is None
        assert g["bo_qua_lich_id"] is None, "uuid rác bị bỏ, không đẩy xuống asyncpg"
        assert g["boi_canh"] == {"tuan_da_cong_bo": True}
    assert all("location_id" not in h for h in kq["hang"])


@pytest.mark.asyncio
async def test_tran_so_hang_moi_luot() -> None:
    svc = _Svc()
    ids = [
        f"{i:08d}-0000-4000-8000-000000000000"
        for i in range(LUOI_NGAY_TOI_DA_BAC_SI + 5)
    ]
    kq = await luoi_ngay(svc, clinic_id="c", date="2026-09-30", doctor_ids=ids)  # type: ignore[arg-type]
    assert len(kq["hang"]) == LUOI_NGAY_TOI_DA_BAC_SI + 1


@pytest.mark.parametrize(
    ("bac_si", "cong_bo", "mong"),
    [
        (BS_A, True, (True, True)),
        # Tuần CHƯA công bố: trigger nhận lịch hẹn vượt trần (20260915000001).
        (BS_A, False, (False, True)),
        # Lịch hẹn CHƯA gán bác sĩ: trigger không kiểm; ghế trực tiếp vẫn kiểm.
        (None, True, (False, True)),
        (None, False, (False, True)),
    ],
)
def test_tran_co_chan_giong_nhanh_mien_kiem_cua_trigger(
    bac_si: str | None, cong_bo: bool, mong: tuple[bool, bool]
) -> None:
    assert tran_co_chan(bac_si, cong_bo) == mong


def test_mot_danh_sach_trang_thai_chet() -> None:
    assert DEAD_STATUSES == {"CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"}
    assert set(HIDDEN_STATUSES) == DEAD_STATUSES
    assert not giu_cho("CANCELLED") and not giu_cho(" NO_SHOW ")
    assert giu_cho("CONFIRMED") and giu_cho(None)


def _dong(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "x",
        "slot_start": dt.datetime(2026, 9, 30, 11, 5, tzinfo=dt.UTC),  # 18:05 VN
        "status": "CONFIRMED",
        "doctor_id": BS_A,
        "booking_channel": "WALK_IN",
        "slot_minutes": 15,
        "walkin_cap": 2,
    }
    base.update(over)
    return base


def test_ghe_truc_tiep_dem_theo_bac_si_khung_va_tran_rieng() -> None:
    rows = [
        _dong(),
        _dong(slot_start=dt.datetime(2026, 9, 30, 11, 14, tzinfo=dt.UTC)),  # cùng khung
        _dong(status="CANCELLED"),  # chết → không chiếm
        _dong(booking_channel="PHONE"),  # ghế hẹn, không phải trực tiếp
        _dong(doctor_id=BS_B),  # bác sĩ khác
        _dong(slot_start=dt.datetime(2026, 9, 30, 11, 15, tzinfo=dt.UTC)),  # khung sau
    ]
    dem = dem_ghe_truc_tiep(rows)
    k = (BS_A, int(dt.datetime(2026, 9, 30, 11, 0, tzinfo=dt.UTC).timestamp()))
    assert dem[k] == 2
    # Trần 2 (luật riêng) − 2 người = 0 → không mời "đặt vào đây".
    assert _row_to_dict(_RowT(_dong()), None, dem)["ghe_truc_tiep_con"] == 0
    # Luật riêng nâng lên 4 → còn 2, dù trần chung phòng khám là 1.
    assert _row_to_dict(_RowT(_dong(walkin_cap=4)), None, dem)["ghe_truc_tiep_con"] == 2
    # Không biết trần → None, màn hình không đoán.
    assert (
        _row_to_dict(_RowT(_dong(walkin_cap=None)), None, dem)["ghe_truc_tiep_con"]
        is None
    )


class _RowT(dict[str, Any]):
    """Đủ khoá mà `_row_to_dict` đọc; dòng thật là asyncpg.Record."""

    def __getitem__(self, k: str) -> Any:
        return self.get(k)
