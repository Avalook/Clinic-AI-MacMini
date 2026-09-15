"""Theo dõi sau thủ thuật — bác sĩ quyết, CSKH chỉ nhìn (Tuyền chốt 16/09/2026)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.theo_doi_thu_thuat_service import (
    TheoDoiThuThuatService,
    han_goi,
)
from tests.services.fake_sql import pool
from tests.services.test_luat_1509_thu_ky_va_dieu_phoi import BS1, BS2, ME, VISIT, who

XONG = datetime(2026, 9, 16, 9, tzinfo=timezone.utc)


def _luot(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "visit_id": VISIT,
        "bac_si_phu_trach": ME,
        "theo_doi_thu_thuat": None,
        "theo_doi_sau_ngay": None,
        "theo_doi_luc": None,
        "theo_doi_boi": None,
        "co_thu_thuat": True,
        "xong_luc": XONG,
        "nguoi_lam": [BS1],
    }
    base.update(kw)
    return base


def test_han_goi_tinh_tu_luc_lam_xong_thu_thuat() -> None:
    assert han_goi(XONG, "CAN", 3) == XONG + timedelta(days=3)
    # Chưa làm xong / không cần / chưa quyết → không bịa hạn.
    assert han_goi(None, "CAN", 3) is None
    assert han_goi(XONG, "KHONG_CAN", None) is None
    assert han_goi(XONG, None, None) is None


@pytest.mark.asyncio
async def test_doc_tra_han_goi_va_chua_co_luot() -> None:
    p = pool(
        (
            "FROM public.visit v",
            _luot(theo_doi_thu_thuat="CAN", theo_doi_sau_ngay=2, theo_doi_luc=XONG),
        )
    )
    out = await TheoDoiThuThuatService(p).doc(
        identity=who(ClinicRole.CSKH), visit_id=VISIT
    )
    assert out["han_goi"] == (XONG + timedelta(days=2)).isoformat()
    with pytest.raises(NotFoundError):
        await TheoDoiThuThuatService(pool()).doc(
            identity=who(ClinicRole.CSKH), visit_id=VISIT
        )


@pytest.mark.asyncio
async def test_bac_si_phu_trach_hoac_nguoi_lam_moi_duoc_chon() -> None:
    svc = TheoDoiThuThuatService
    # CSKH / thư ký không quyết thay bác sĩ.
    for role in (ClinicRole.CSKH, ClinicRole.TKYK, ClinicRole.RECEPTION):
        with pytest.raises(SafetyGateError):
            await svc(pool()).dat(
                identity=who(role), visit_id=VISIT, theo_doi="CAN", sau_ngay=3
            )
    # Bác sĩ không phụ trách, không làm thủ thuật → chặn.
    with pytest.raises(SafetyGateError, match="phụ trách"):
        await svc(pool(("FROM public.visit v", _luot()))).dat(
            identity=who(ClinicRole.DOCTOR, BS2),
            visit_id=VISIT,
            theo_doi="KHONG_CAN",
            sau_ngay=None,
        )
    # Bác sĩ làm thủ thuật (không phải bác sĩ chính) được quyết.
    p = pool(("FROM public.visit v", _luot()))
    await svc(p).dat(
        identity=who(ClinicRole.ULTRASOUND_DOCTOR, BS1),
        visit_id=VISIT,
        theo_doi="CAN",
        sau_ngay=5,
    )
    ghi = p.da_goi("UPDATE public.visit")
    assert ghi and ghi[0][2:5] == ("CAN", 5, BS1)
    assert p.events() or p.da_goi("event_log")


@pytest.mark.asyncio
async def test_dau_vao_sai_va_luot_khong_co_thu_thuat() -> None:
    svc = TheoDoiThuThuatService
    bs = who(ClinicRole.DOCTOR)
    with pytest.raises(ValidationError, match="bao nhiêu ngày"):
        await svc(pool()).dat(
            identity=bs, visit_id=VISIT, theo_doi="CAN", sau_ngay=None
        )
    with pytest.raises(ValidationError, match="bao nhiêu ngày"):
        await svc(pool()).dat(identity=bs, visit_id=VISIT, theo_doi="CAN", sau_ngay=400)
    with pytest.raises(ValidationError, match="Chọn"):
        await svc(pool()).dat(
            identity=bs, visit_id=VISIT, theo_doi="CO_LE", sau_ngay=None
        )
    with pytest.raises(ValidationError, match="không có chỉ định thủ thuật"):
        await svc(pool(("FROM public.visit v", _luot(co_thu_thuat=False)))).dat(
            identity=bs, visit_id=VISIT, theo_doi="KHONG_CAN", sau_ngay=None
        )
    with pytest.raises(NotFoundError):
        await svc(pool()).dat(
            identity=bs, visit_id=VISIT, theo_doi="KHONG_CAN", sau_ngay=None
        )
    # KHONG_CAN bỏ số ngày dù client gửi kèm.
    p = pool(("FROM public.visit v", _luot()))
    await svc(p).dat(identity=bs, visit_id=VISIT, theo_doi="KHONG_CAN", sau_ngay=7)
    assert p.da_goi("UPDATE public.visit")[0][2:4] == ("KHONG_CAN", None)
