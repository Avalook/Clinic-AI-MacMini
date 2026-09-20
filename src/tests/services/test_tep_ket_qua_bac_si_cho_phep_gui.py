"""Tệp kết quả: bác sĩ cho phép gửi từng tệp trước khi CSKH gửi (Tuyền 15/09/2026).

Hành vi đầy đủ đã chạy thật trên Postgres (smoke 15/09: CSKH gửi khi chưa cho
phép bị chặn, CSKH tự cho phép bị chặn, ghi thẳng DB bị trigger chặn, bác sĩ cho
phép → việc CSKH đổi CHO_BAC_SI → KQ_CHUA_GUI → gửi xong hết việc).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.tep_ket_qua_service import TepKetQuaService

TEP = "33333333-3333-4333-8333-333333333333"


def _identity(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="11111111-1111-4111-8111-111111111111",
        auth_user_id="u1",
        full_name="x",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


@pytest.mark.parametrize(
    "role", [ClinicRole.CSKH, ClinicRole.TKYK, ClinicRole.MANAGEMENT]
)
def test_chi_bac_si_cho_phep_gui(role: ClinicRole) -> None:
    pool = MagicMock()
    with pytest.raises(SafetyGateError):
        asyncio.run(
            TepKetQuaService(pool).cho_phep_gui(identity=_identity(role), tep_id=TEP)
        )
    pool.acquire.assert_not_called()


class _Pool:
    async def fetchrow(self, *_: Any) -> dict[str, Any]:
        return {"gui_luc": None, "cho_phep_gui_luc": None, "xac_nhan_trang_thai": None}


def test_chua_cho_phep_thi_cskh_khong_danh_dau_da_gui() -> None:
    with pytest.raises(ConflictError, match="chưa cho phép"):
        asyncio.run(
            TepKetQuaService(_Pool()).danh_dau_da_gui(
                identity=_identity(ClinicRole.CSKH), tep_id=TEP, kenh="ZALO"
            )
        )


def test_cau_update_da_gui_tu_kiem_cho_phep() -> None:
    ma = inspect.getsource(TepKetQuaService.danh_dau_da_gui)
    dau = ma.index("UPDATE public.tep_ket_qua")
    assert "cho_phep_gui_luc IS NOT NULL" in ma[dau : ma.index('"""', dau)]
