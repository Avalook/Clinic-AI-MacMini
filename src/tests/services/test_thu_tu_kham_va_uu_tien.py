"""Khách ưu tiên là cờ hồ sơ; lễ tân kéo thứ tự khám (Tuyền chốt 15/09/2026).

Smoke Postgres thật chạy đủ đường; đây khoá phần luật thuần và cửa vai.
"""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.booking_service import CHECKIN_ROLES
from clinicai.services.thu_tu_kham_service import (
    KHOANG_DAU_CUOI_MS,
    VAI_DANH_DAU_UU_TIEN,
    VAI_KEO_THU_TU,
    ThuTuKhamService,
    moc_moi,
)


@pytest.fixture(autouse=True)
def _cua_quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kết nối giả không chạy được `v_quyen_hieu_luc` — cửa quyền trả lời theo
    nhóm mẫu của vai (tests/quyen_gia.py). 24/09: kéo thứ tự / đặt lịch hỏi quyền."""
    import clinicai.services.booking_service as bk
    import clinicai.services.thu_tu_kham_service as ttk
    from tests.quyen_gia import doi_quyen_theo_nhom_mau

    monkeypatch.setattr(ttk, "doi_quyen", doi_quyen_theo_nhom_mau)
    monkeypatch.setattr(bk, "doi_quyen", doi_quyen_theo_nhom_mau)


def _identity(role: ClinicRole) -> StaffIdentity:
    x = "a0000000-0000-4000-8000-000000000001"
    return StaffIdentity(
        staff_id=x,
        auth_user_id=x,
        full_name="x",
        department=role.value,
        role=role,
        clinic_id=x,
        location_id=x,
        location_name="CS",
    )


def test_moc_moi_nam_giua_hai_nguoi_ke_ben() -> None:
    assert moc_moi(truoc=2000.0, sau=1000.0) == 1500.0
    assert moc_moi(truoc=1000.0, sau=None) == 1000.0 - KHOANG_DAU_CUOI_MS
    assert moc_moi(truoc=None, sau=1000.0) == 1000.0 + KHOANG_DAU_CUOI_MS


@pytest.mark.parametrize("truoc,sau", [(None, None), (1000.0, 2000.0), (5.0, 5.0)])
def test_moc_moi_tu_choi_cho_tha_vo_nghia(
    truoc: float | None, sau: float | None
) -> None:
    with pytest.raises(ValidationError):
        moc_moi(truoc=truoc, sau=sau)


def test_vai_keo_thu_tu_la_quay_va_dieu_phoi_khong_co_cskh() -> None:
    assert VAI_KEO_THU_TU == frozenset(
        {ClinicRole.RECEPTION, ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT}
    )
    assert ClinicRole.CSKH in VAI_DANH_DAU_UU_TIEN
    assert ClinicRole.CSKH not in CHECKIN_ROLES


@pytest.mark.asyncio
async def test_cskh_keo_thu_tu_bi_chan_truoc_khi_cham_db() -> None:
    """CSKH không có quyền "Check-in khách" → chặn ngay khi hỏi quyền, trước
    mọi câu đọc/ghi dữ liệu (24/09: hỏi quyền thay vì hỏi vai)."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    conn = AsyncMock()

    class _Pool:
        @asynccontextmanager
        async def acquire(self):  # type: ignore[no-untyped-def]
            @asynccontextmanager
            async def tx():  # type: ignore[no-untyped-def]
                yield None

            conn.transaction = tx
            yield conn

    with pytest.raises(SafetyGateError):
        await ThuTuKhamService(_Pool()).keo(
            identity=_identity(ClinicRole.CSKH),
            appointment_id="a",
            sau_appointment_id=None,
            truoc_appointment_id="b",
        )
    assert not conn.fetch.await_args_list


@pytest.mark.asyncio
async def test_bat_uu_tien_phai_co_ly_do() -> None:
    with pytest.raises(ValidationError, match="lý do"):
        await ThuTuKhamService(None).dat_uu_tien(
            identity=_identity(ClinicRole.RECEPTION),
            clinic_patient_id="p",
            uu_tien=True,
            ly_do="  ",
        )
