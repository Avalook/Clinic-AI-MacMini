"""Hồ sơ một lần khám (bản đọc gộp cho CSKH xem trước và tải PDF)."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.ho_so_kham_service import HoSoKhamService

CLINIC = "a0000000-0000-4000-8000-000000000001"
LICH = "c0000000-0000-4000-8000-000000000003"


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Chị CSKH",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id="l1",
        location_name="Kim Ngưu",
    )


class Pool:
    def __init__(self, *kq: Any) -> None:
        self.kq = list(kq)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _lay(self, sql: str, a: tuple[Any, ...]) -> Any:
        self.calls.append((sql, a))
        return self.kq.pop(0) if self.kq else None

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        return self._lay(sql, a)

    async def fetch(self, sql: str, *a: Any) -> Any:
        return self._lay(sql, a) or []

    def acquire(self) -> "Pool":
        return self

    async def __aenter__(self) -> "Pool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.mark.asyncio
async def test_lich_khong_co_hoac_khac_phong_kham_thi_404() -> None:
    with pytest.raises(NotFoundError):
        await HoSoKhamService(Pool(None)).doc(identity=_ai(), appointment_id=LICH)


@pytest.mark.asyncio
async def test_moi_cau_doc_deu_khoa_theo_phong_kham() -> None:
    """Đoán đúng một mã lịch không đủ để đọc hồ sơ của phòng khám khác."""
    lich = {"clinic_patient_id": "p1", "appointment_id": LICH}
    luot = {"visit_id": "v1"}
    pool = Pool(lich, luot, None, [], [], [], [], [], [])
    d = await HoSoKhamService(pool).doc(identity=_ai(), appointment_id=LICH)

    assert len(pool.calls) == 9
    for sql, args in pool.calls:
        assert "clinic_id" in sql, sql
        assert CLINIC in args, sql
    assert set(d) == {
        "lich",
        "luot",
        "sinh_hieu",
        "phien_kham",
        "phieu_kham",
        "chi_dinh",
        "tep",
        "xet_nghiem",
        "don_thuoc",
    }


@pytest.mark.asyncio
async def test_chua_check_in_thi_van_tra_ho_so_rong() -> None:
    lich = {"clinic_patient_id": "p1", "appointment_id": LICH}
    pool = Pool(lich, None, [], [])
    d = await HoSoKhamService(pool).doc(identity=_ai(), appointment_id=LICH)
    assert d["luot"] is None and d["phieu_kham"] == [] and d["chi_dinh"] == []
