"""Thai kỳ trên Postgres thật — chỉ bác sĩ ghi, dự kiến sinh do bác sĩ nhập kèm
nguồn, một thai kỳ đang theo dõi mỗi khách (batch pilot 18/09/2026)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.thai_ky_service import ThaiKyService, tuoi_thai_tu_edd
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khach(kb: KichBan) -> str:
    return str(
        await kb.pool.fetchval(
            "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    )


def test_tuoi_thai_la_phep_tru_tu_du_kien_sinh() -> None:
    hom_nay = now_vn().date()
    assert tuoi_thai_tu_edd(hom_nay + timedelta(days=280 - 70), hom_nay) == {
        "tuan": 10,
        "ngay": 0,
    }
    assert tuoi_thai_tu_edd(None, hom_nay) is None
    assert tuoi_thai_tu_edd(hom_nay + timedelta(days=400), hom_nay) is None


async def test_nguoi_ghi_benh_an_tao_va_chuyen_thai_ky(kb: KichBan) -> None:
    svc = ThaiKyService(kb.pool)
    khach = await _khach(kb)
    edd = (now_vn().date() + timedelta(days=200)).isoformat()
    du_lieu = {"du_kien_sinh": edd, "nguon_du_kien_sinh": "SIEU_AM"}
    # 28/09/2026: ghi thai kỳ hỏi QUYỀN ghi bệnh án — thư ký / điều dưỡng cùng
    # phòng ghi được như bác sĩ; lễ tân (không có quyền ấy) thì không.
    await ve_goi_mau_cu(kb.pool, kb.le_tan)  # gói lego cũ (mở full lego 30/09)
    for ai in (kb.le_tan,):
        with pytest.raises(SafetyGateError):
            await svc.tao(
                clinic_patient_id=khach, visit_id=None, du_lieu=du_lieu, identity=ai
            )
    with pytest.raises(ValidationError):  # thiếu nguồn
        await svc.tao(
            clinic_patient_id=khach,
            visit_id=kb.visit_id,
            du_lieu={"du_kien_sinh": edd},
            identity=kb.bac_si,
        )
    with pytest.raises(ValidationError):  # ngày rác → câu lỗi, không 500
        await svc.tao(
            clinic_patient_id=khach,
            visit_id=kb.visit_id,
            du_lieu={"du_kien_sinh": "31/02/2027", "nguon_du_kien_sinh": "KHAC"},
            identity=kb.bac_si,
        )
    kq = await svc.tao(
        clinic_patient_id=khach,
        visit_id=kb.visit_id,
        du_lieu=du_lieu,
        identity=kb.bac_si,
    )
    with pytest.raises(ConflictError):  # một thai kỳ đang theo dõi mỗi khách
        await svc.tao(
            clinic_patient_id=khach, visit_id=None, du_lieu=du_lieu, identity=kb.bac_si
        )
    doc = await svc.doc(clinic_patient_id=khach, identity=kb.dieu_duong)
    ht = doc["hien_tai"]
    assert ht is not None and ht["nguon_du_kien_sinh"] == "SIEU_AM"
    assert ht["tuoi_thai"] == {"tuan": 11, "ngay": 3}
    # 29/09/2026: ĐD/TKYK trọn quyền (Tuyền) — điều dưỡng được ghi (lễ tân vẫn
    # bị chặn ghi ở trên và dưới).
    assert doc["duoc_ghi"] is True
    with pytest.raises(SafetyGateError):
        await svc.cap_nhat(
            pregnancy_id=kq["id"],
            du_lieu={"ket_cuc": "DELIVERED", "ngay_ket_cuc": "2027-01-01"},
            identity=kb.le_tan,  # 28/09: thư ký ghi được
        )
    await svc.cap_nhat(
        pregnancy_id=kq["id"],
        du_lieu={"ket_cuc": "DELIVERED", "ngay_ket_cuc": "2027-01-01"},
        identity=kb.bac_si,
    )
    with pytest.raises(ConflictError):  # đã có kết cục → khoá
        await svc.cap_nhat(
            pregnancy_id=kq["id"],
            du_lieu={"du_kien_sinh": edd, "nguon_du_kien_sinh": "KHAC"},
            identity=kb.bac_si,
        )
    doc = await svc.doc(clinic_patient_id=khach, identity=kb.bac_si)
    assert doc["hien_tai"] is None and doc["truoc"][0]["ket_cuc"] == "DELIVERED"
    assert doc["duoc_ghi"] is True
