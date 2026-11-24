"""Bác sĩ — không phải nhóm AI — quyết báo kết quả xét nghiệm (15/09/2026).

Kết quả được báo khách khi BÁC SĨ đã duyệt và chốt, bất kể nhóm AI tự phân. Bản
cũ chỉ cho GROUP_A: không có AI hoặc AI xếp B/C thì kết quả bác sĩ đã duyệt
không bao giờ được báo (CONTEXT v1.0: bác sĩ cho phép gửi).

(24/11/2026: hai cửa AI `/lab/triage` và `/tools/*` đã gỡ, nên bài "thiếu khoá
AI thì 503" và client AI dùng chung trong `main.lifespan` cũng gỡ theo.)
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers import lab


class _Pool:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchrow(self, *_: Any) -> dict[str, Any] | None:
        return self._row


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _quyet(triage: str | None, finalized: bool) -> Any:
    return asyncio.run(
        lab.lab_release_decision(
            uuid4(),
            identity=_identity(),
            pool=_Pool({"triage_group": triage, "is_finalized": finalized}),
        )
    )


@pytest.mark.parametrize("triage", ["GROUP_A", "GROUP_B", "GROUP_C", "PENDING", None])
def test_bac_si_da_chot_thi_duoc_bao_bat_ke_nhom_ai(triage: str | None) -> None:
    assert _quyet(triage, True).allowed is True


@pytest.mark.parametrize("triage", ["GROUP_A", "GROUP_B", "GROUP_C", "PENDING", None])
def test_chua_chot_thi_khong_bao_ke_ca_group_a(triage: str | None) -> None:
    assert _quyet(triage, False).allowed is False
