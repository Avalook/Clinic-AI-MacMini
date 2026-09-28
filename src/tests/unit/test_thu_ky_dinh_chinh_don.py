"""Ai đính chính được đơn nhà thuốc / thu ngân đã đụng — theo QUYỀN.

* Thư ký y khoa = bác sĩ về đơn thuốc (Tuyền chốt 24/09/2026): thư ký đã phân
  theo bác sĩ chính của lượt đính chính được; phân theo bác sĩ khác thì không.
* Tuyền chốt 29/09/2026 — trợ lý TRỌN QUYỀN: ai có quyền Khám (lego Bàn khám)
  đính chính được, kể cả khi lego làm họ mang vai DOCTOR (bản cũ rơi vào nhánh
  "bác sĩ" rồi bị so `attending_doctor_id != staff_id`).
* Giữ HOLD đính chính CHÉO BÁC SĨ: bác sĩ thật không đính chính lượt của bác sĩ
  thật khác.
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import dinh_chinh_don as dcd

BS_A = "10000000-0000-0000-0000-00000000000a"
BS_B = "10000000-0000-0000-0000-00000000000b"
TK = "20000000-0000-0000-0000-000000000001"
DD = "20000000-0000-0000-0000-000000000002"

#: Tài khoản bác sĩ thật (clinic_membership.role DOCTOR / ULTRASOUND_DOCTOR).
BAC_SI_THAT = {BS_A, BS_B}


class _Conn:
    """Kết nối giả: `fetchval` = bác sĩ chính của lượt; `fetch` = tra tài khoản
    bác sĩ (`bac_si_phu_trach.bac_si_trong`)."""

    def __init__(self, chinh: str | None) -> None:
        self.chinh = chinh

    async def fetchval(self, sql: str, *a: Any) -> Any:
        return self.chinh

    async def fetch(self, sql: str, *a: Any) -> list[dict[str, str]]:
        assert "clinic_membership" in sql
        return [{"id": i} for i in a[1] if i in BAC_SI_THAT]


def _nguoi(
    vai: ClinicRole,
    sid: str = TK,
    *,
    lego: frozenset[ClinicRole] | None = None,
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
        vai_theo_lego=lego,
    )


#: Ai có quyền Khám (`clinical.consult.perform`) trong bài kiểm.
_CO_QUYEN_KHAM: set[str] = set()


@pytest.fixture(autouse=True)
def _gia(monkeypatch: pytest.MonkeyPatch) -> None:
    _CO_QUYEN_KHAM.clear()
    _CO_QUYEN_KHAM.update({BS_A, BS_B, TK})

    async def bac_si(conn: Any, identity: StaffIdentity) -> list[str] | None:
        # Chỉ thư ký TK được phân — theo BS_A.
        return [BS_A] if identity.staff_id == TK else None

    async def can(conn: Any, identity: StaffIdentity, quyen: str, **_k: Any) -> bool:
        assert quyen == "clinical.consult.perform"
        return identity.staff_id in _CO_QUYEN_KHAM

    monkeypatch.setattr(dcd, "bac_si_cua_thu_ky", bac_si)
    monkeypatch.setattr(dcd, "can", can)


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
async def test_thu_ky_co_lego_ban_kham_dinh_chinh_duoc() -> None:
    """Lỗi 29/09: thư ký bật lego Bàn khám mang vai DOCTOR theo lego → bản cũ
    coi là bác sĩ, so `attending != staff_id` → chặn."""
    await dcd._cho_phep_dinh_chinh(
        _Conn(BS_A),
        identity=_nguoi(ClinicRole.TKYK, lego=frozenset({ClinicRole.DOCTOR})),
        visit_id="v",
    )


@pytest.mark.asyncio
async def test_dieu_duong_co_lego_ban_kham_dinh_chinh_duoc() -> None:
    _CO_QUYEN_KHAM.add(DD)
    await dcd._cho_phep_dinh_chinh(
        _Conn(BS_A),
        identity=_nguoi(
            ClinicRole.NURSE_ULTRASOUND, DD, lego=frozenset({ClinicRole.DOCTOR})
        ),
        visit_id="v",
    )


@pytest.mark.asyncio
async def test_dieu_duong_khong_co_quyen_kham_bi_chan() -> None:
    with pytest.raises(SafetyGateError, match="quyền Bàn khám"):
        await dcd._cho_phep_dinh_chinh(
            _Conn(BS_A),
            identity=_nguoi(ClinicRole.NURSE_ULTRASOUND, DD, lego=frozenset()),
            visit_id="v",
        )


@pytest.mark.asyncio
async def test_bac_si_chinh_dinh_chinh_duoc() -> None:
    await dcd._cho_phep_dinh_chinh(
        _Conn(BS_A), identity=_nguoi(ClinicRole.DOCTOR, BS_A), visit_id="v"
    )


@pytest.mark.asyncio
async def test_bac_si_khac_van_bi_chan_cheo() -> None:
    with pytest.raises(SafetyGateError, match="bác sĩ khác"):
        await dcd._cho_phep_dinh_chinh(
            _Conn(BS_A), identity=_nguoi(ClinicRole.DOCTOR, BS_B), visit_id="v"
        )
