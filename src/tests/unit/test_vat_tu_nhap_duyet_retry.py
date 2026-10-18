"""Retry một yêu cầu nhập phải giữ nguyên quyết định đã ghi nhận."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.vat_tu_nhap_duyet_service import xu_ly_nhap_can_duyet


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="staff",
        auth_user_id="auth",
        full_name="Nhân viên thử",
        department="Nhà thuốc",
        role=ClinicRole.PHARMACIST,
        clinic_id="clinic",
        location_id="location",
        location_name="Cơ sở thử",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("trang_thai", ["CHO_DUYET", "DA_DUYET", "TU_CHOI", "RUT_LAI"])
async def test_retry_request_survives_approval_flag_being_removed(
    trang_thai: str,
) -> None:
    """Bỏ cờ duyệt sau lần gửi đầu không được mở đường nhập kho lần hai."""
    identity = _identity()
    original = {
        "id": "request",
        "ma_yeu_cau": "YC-0001",
        "trang_thai": trang_thai,
        "phieu_id": "receipt" if trang_thai == "DA_DUYET" else None,
    }
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value=original),
        fetchval=AsyncMock(return_value=False),
    )

    result = await xu_ly_nhap_can_duyet(conn, identity, "same-key", [], None)

    assert result is not None
    assert result["yeu_cau_id"] == "request"
    assert result["gui_lai"] is True
    assert result["cho_duyet"] is (trang_thai == "CHO_DUYET")
    conn.fetchval.assert_not_awaited()
    assert conn.fetchrow.await_args.args[1:] == ("clinic", "location", "same-key")


@pytest.mark.asyncio
async def test_new_request_without_approval_flag_uses_normal_receipt_path() -> None:
    identity = _identity()
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=False),
    )

    assert await xu_ly_nhap_can_duyet(conn, identity, "new-key", [], None) is None
    conn.fetchval.assert_awaited_once()
