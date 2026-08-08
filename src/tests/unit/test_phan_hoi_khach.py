"""Phản hồi / khiếu nại của khách — vòng đời phải đóng cho tử tế.

Luật đắt nhất ở đây: "đã xử lý" mà không nói xử lý ra sao thì ba tuần sau khách
gọi lại và không ai biết lần trước đã hứa gì. Service chặn bằng tiếng Việt
TRƯỚC khi CHECK của Postgres nổ thành một lỗi 500.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.phan_hoi_khach_service import PhanHoiKhachService

CLINIC = "a0000000-0000-4000-8000-000000000001"
BN = "b0000000-0000-4000-8000-000000000001"


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Chị Điều",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id="l1",
        location_name="Kim Ngưu",
    )


class FakePool:
    def __init__(self, *kq: Any) -> None:
        self._kq = list(kq)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _lay(self) -> Any:
        return self._kq.pop(0) if self._kq else None

    async def fetchval(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._lay()

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._lay()

    async def execute(self, sql: str, *a: Any) -> None:
        self.calls.append((sql, a))

    def acquire(self) -> "FakePool":
        return self

    def transaction(self) -> "FakePool":
        return self

    async def __aenter__(self) -> "FakePool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.mark.asyncio
async def test_ghi_can_noi_dung_va_loai_hop_le() -> None:
    with pytest.raises(ValidationError):
        await PhanHoiKhachService(FakePool()).ghi(
            identity=_ai(), clinic_patient_id=BN, loai="KHIEU_NAI", noi_dung="   "
        )
    with pytest.raises(ValidationError):
        await PhanHoiKhachService(FakePool()).ghi(
            identity=_ai(), clinic_patient_id=BN, loai="CHUI", noi_dung="x"
        )


@pytest.mark.asyncio
async def test_ghi_thi_nguoi_tiep_nhan_lay_tu_phien() -> None:
    pool = FakePool(1, "ph-1")  # patient tồn tại → id dòng mới
    d = await PhanHoiKhachService(pool).ghi(
        identity=_ai(),
        clinic_patient_id=BN,
        loai="KHIEU_NAI",
        noi_dung="  Chờ lâu quá  ",
    )
    assert d["ok"] is True
    sql, args = pool.calls[1]
    assert "INSERT INTO public.phan_hoi_khach" in sql
    assert "s1" in args  # người tiếp nhận = phiên đăng nhập
    assert "Chờ lâu quá" in args  # đã cắt khoảng trắng


@pytest.mark.asyncio
async def test_khach_phong_kham_khac_thi_khong_ghi_duoc() -> None:
    with pytest.raises(NotFoundError):
        await PhanHoiKhachService(FakePool(None)).ghi(
            identity=_ai(), clinic_patient_id=BN, loai="GOP_Y", noi_dung="x"
        )


@pytest.mark.asyncio
async def test_dong_ma_khong_noi_xu_ly_the_nao_thi_tu_choi() -> None:
    with pytest.raises(ValidationError):
        await PhanHoiKhachService(FakePool()).cap_nhat(
            identity=_ai(), phan_hoi_id="ph-1", trang_thai="DA_XU_LY", huong_xu_ly="  "
        )


@pytest.mark.asyncio
async def test_dong_du_thong_tin_thi_ghi_nguoi_xu_ly() -> None:
    pool = FakePool({"id": "ph-1"})
    d = await PhanHoiKhachService(pool).cap_nhat(
        identity=_ai(),
        phan_hoi_id="ph-1",
        trang_thai="DA_XU_LY",
        huong_xu_ly="Đã gọi xin lỗi, tặng voucher tái khám",
    )
    assert d["ok"] is True
    sql, args = pool.calls[0]
    assert "UPDATE public.phan_hoi_khach" in sql and "s1" in args


@pytest.mark.asyncio
async def test_cap_nhat_phan_hoi_khong_ton_tai() -> None:
    with pytest.raises(NotFoundError):
        await PhanHoiKhachService(FakePool(None)).cap_nhat(
            identity=_ai(), phan_hoi_id="ph-x", trang_thai="DANG_XU_LY"
        )
