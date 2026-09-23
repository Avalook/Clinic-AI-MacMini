"""Thư ký y khoa = bác sĩ về đơn thuốc (Tuyền chốt 24/09/2026): thư ký của CHÍNH
bác sĩ chính của lượt đính chính được đơn nhà thuốc đã đụng; thư ký của bác sĩ
khác thì không (giữ luật "không đính chính chéo bác sĩ")."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import dinh_chinh_don as dcd

BS_A = "10000000-0000-0000-0000-00000000000a"
BS_B = "10000000-0000-0000-0000-00000000000b"


class _Conn:
    def __init__(self, chinh: str) -> None:
        self.chinh = chinh

    async def fetchval(self, sql: str, *a: Any) -> Any:
        return self.chinh


def _nguoi(
    vai: ClinicRole, sid: str = "20000000-0000-0000-0000-000000000001"
) -> StaffIdentity:
    return StaffIdentity(
        staff_id=sid,
        auth_user_id="x",
        full_name="t",
        department=vai.value,
        role=vai,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="b0000000-0000-4000-8000-000000000001",
        location_name="",
    )


@pytest.fixture(autouse=True)
def _thu_ky_theo_bs_a(monkeypatch: pytest.MonkeyPatch) -> None:
    async def bac_si(conn: Any, identity: StaffIdentity) -> list[str] | None:
        return [BS_A] if identity.co_vai({ClinicRole.TKYK}) else None

    monkeypatch.setattr(dcd, "bac_si_cua_thu_ky", bac_si)


@pytest.mark.asyncio
async def test_thu_ky_cua_bac_si_chinh_dinh_chinh_duoc() -> None:
    await dcd._cho_phep_dinh_chinh(
        _Conn(BS_A), identity=_nguoi(ClinicRole.TKYK), visit_id="v"
    )


@pytest.mark.asyncio
async def test_thu_ky_cua_bac_si_khac_bi_chan() -> None:
    with pytest.raises(SafetyGateError):
        await dcd._cho_phep_dinh_chinh(
            _Conn(BS_B), identity=_nguoi(ClinicRole.TKYK), visit_id="v"
        )


@pytest.mark.asyncio
async def test_dieu_duong_van_khong_dinh_chinh_duoc() -> None:
    with pytest.raises(SafetyGateError):
        await dcd._cho_phep_dinh_chinh(
            _Conn(BS_A), identity=_nguoi(ClinicRole.NURSE_ULTRASOUND), visit_id="v"
        )
