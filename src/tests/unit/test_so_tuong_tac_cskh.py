"""Sổ tương tác CSKH — ràng buộc phải nổ bằng tiếng Việt, không phải 500.

Bốn luật của bảng nằm ở CHECK trong 20260809000003. Nếu service để lời gọi sai
đi thẳng xuống database thì người dùng nhận một lỗi 500 và một dòng log Postgres
tiếng Anh. Kiểm ở đây để họ nhận một câu đọc được.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

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


class PoolTrong:
    """Không kết nối gì cả — mọi bài dưới đây phải dừng TRƯỚC khi chạm database."""

    def acquire(self) -> "PoolTrong":
        raise AssertionError("Lời gọi sai đã đi tới database thay vì bị chặn sớm.")

    async def fetch(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError("Lời gọi sai đã đi tới database thay vì bị chặn sớm.")


def _svc() -> TuongTacCskhService:
    return TuongTacCskhService(PoolTrong())


async def _ghi(**kwargs: Any) -> Any:
    mac_dinh: dict[str, Any] = {
        "identity": _ai(),
        "clinic_patient_id": BN,
        "loai": "KHAC",
        "kenh": "GOI",
        "ket_qua": "DA_LIEN_HE",
    }
    return await _svc().ghi(**{**mac_dinh, **kwargs})


@pytest.mark.asyncio
async def test_bo_qua_phai_di_cung_khong_lien_he() -> None:
    """Tách hai nửa ra thì sẽ có dòng ghi "đã gọi điện" mà kết quả là "bỏ qua"."""
    with pytest.raises(ValidationError):
        await _ghi(kenh="GOI", ket_qua="BO_QUA")
    with pytest.raises(ValidationError):
        await _ghi(kenh="KHONG_LIEN_HE", ket_qua="DA_LIEN_HE")


@pytest.mark.asyncio
async def test_khach_xac_nhan_chi_co_nghia_o_hai_loai_viec() -> None:
    with pytest.raises(ValidationError):
        await _ghi(loai="TRA_KQ", khach_xac_nhan=True)


@pytest.mark.asyncio
async def test_ba_loai_viec_phai_gan_voi_mot_lich_hen() -> None:
    """Ghi "đã gọi xác nhận" mà không nói lịch nào.

    Lần sau mở ra không ai biết đã gọi cho lịch tuần trước hay tuần sau.
    """
    for loai in ("XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY"):
        with pytest.raises(ValidationError):
            await _ghi(loai=loai, appointment_id=None)


@pytest.mark.asyncio
async def test_tu_dien_dong_khong_nhan_gia_tri_la() -> None:
    with pytest.raises(ValidationError):
        await _ghi(loai="GOI_CHO_VUI")
    with pytest.raises(ValidationError):
        await _ghi(kenh="BO_CAU")
    with pytest.raises(ValidationError):
        await _ghi(ket_qua="CHUA_BIET")
