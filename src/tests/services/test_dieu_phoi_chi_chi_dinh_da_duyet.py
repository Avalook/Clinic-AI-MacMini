"""Tuyến điều phối chỉ gồm việc bác sĩ đã chỉ định (15/09/2026).

CONTEXT v1.0: bác sĩ duyệt chỉ định → trưởng ca điều phối. Mẫu tuyến (TUYEN-A…)
liệt kê cả dịch vụ lượt khám không có; trước bản này áp mẫu là ghi nguyên các
bước đó vào tuyến, và `move_visit_to_station` tự sinh việc cho chúng. Luật SQL
khoá ở supabase/tests/dieu_phoi_chi_chi_dinh_da_duyet.sql; đây khoá phần Python.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.dispatch_service import DispatchService, _buoc_theo_chi_dinh

CLINIC = "a0000000-0000-4000-8000-000000000001"
VISIT = "10000000-0000-0000-0000-000000000001"
TUYEN_A = [
    "DICHVU-SIEUAM",
    "DICHVU-LAYMAU-MAU",
    "DICHVU-DUYET-KETQUA",
    "THUOC-04",
    "LUOTKHAM-14",
]


def _conn(co_viec: dict[str, bool]) -> AsyncMock:
    conn = AsyncMock()

    async def fetch(sql: str, *args: Any) -> list[dict[str, Any]]:
        assert "flow_group" in sql and "prescription" in sql
        return [{"code": k, "co_viec": v} for k, v in co_viec.items()]

    conn.fetch.side_effect = fetch
    return conn


@pytest.mark.asyncio
async def test_bo_buoc_dich_vu_chua_chi_dinh_giu_thu_tu_va_buoc_ga() -> None:
    conn = _conn(
        {
            "DICHVU-SIEUAM": True,
            "DICHVU-LAYMAU-MAU": False,
            "DICHVU-DUYET-KETQUA": False,
            "THUOC-04": True,
        }
    )
    giu, bo = await _buoc_theo_chi_dinh(
        conn, clinic_id=CLINIC, visit_id=VISIT, steps=TUYEN_A
    )
    # LUOTKHAM-14 là bước ga — truy vấn không trả nó, nên luôn được giữ.
    assert giu == ["DICHVU-SIEUAM", "THUOC-04", "LUOTKHAM-14"]
    assert bo == ["DICHVU-LAYMAU-MAU", "DICHVU-DUYET-KETQUA"]


class _Ctx:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_: object) -> None:
        pass


@pytest.mark.asyncio
async def test_tuyen_chi_toan_dich_vu_chua_chi_dinh_bi_tu_choi_truoc_khi_ghi() -> None:
    conn = _conn({"DICHVU-SIEUAM": False, "DICHVU-LAYMAU-MAU": False})
    conn.fetchrow.return_value = {
        "id": "t1",
        "steps": ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU"],
    }
    conn.transaction = MagicMock(return_value=_Ctx(conn))
    pool = MagicMock()
    pool.acquire.return_value = _Ctx(conn)
    identity = StaffIdentity(
        staff_id=CLINIC,
        auth_user_id=CLINIC,
        full_name="TC",
        department="TRUONG_CA",
        role=ClinicRole.TRUONG_CA,
        clinic_id=CLINIC,
        location_id=CLINIC,
        location_name="CS",
    )
    with pytest.raises(ValidationError, match="chưa chỉ định"):
        await DispatchService(pool).apply_route(
            identity=identity,
            visit_id=VISIT,
            template_code="TUYEN-X",
            is_exception=False,
            reason=None,
        )
    conn.execute.assert_not_awaited()
