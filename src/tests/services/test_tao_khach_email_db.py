"""Form TẠO khách có ô Email (Tuyền 16/10/2026) — đường POST /api/patients → service.

- Có email → lưu chuẩn hoá (cắt khoảng trắng, chữ thường), đọc lại đúng từ DB.
- Không email / rỗng / toàn khoảng trắng → NULL (form không gửi khoá).
- Email rác → lỗi kiểm định (422 ở API), không phải 500.
- Trùng email giữa hai khách (email gia đình dùng chung) → KHÔNG chặn.
- Khách trùng SĐT (bấm "Dùng bệnh nhân này") → trả cảnh báo, không ghi gì vào hồ sơ
  cũ: email đã có không bị ghi đè bằng email trên form / bằng rỗng.
"""

from __future__ import annotations

import random
import uuid

import asyncpg
import pytest
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.schemas.patient import PatientCreateDTO
from clinicai.services.patient_service import PatientService
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _sdt_moi() -> str:
    return "09" + "".join(random.choice("0123456789") for _ in range(8))


async def _co_so_va_nguoi_tao(pool: asyncpg.Pool) -> tuple[uuid.UUID, StaffIdentity]:
    async with pool.acquire() as conn:
        loc_text = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
    loc = uuid.UUID(str(loc_text))
    staff = StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Lễ tân test",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id=CLINIC,
        location_id=str(loc),
        location_name="Cơ sở test",
    )
    return loc, staff


async def _email_trong_db(pool: asyncpg.Pool, pid: uuid.UUID) -> str | None:
    async with pool.acquire() as conn:
        mail = await conn.fetchval(
            "SELECT email FROM patient WHERE clinic_patient_id = $1;", pid
        )
    return None if mail is None else str(mail)


async def test_tao_khach_co_email_luu_chuan_hoa(pool: asyncpg.Pool) -> None:
    loc, staff = await _co_so_va_nguoi_tao(pool)
    dto = PatientCreateDTO(
        full_name="Khách Có Email",
        phone_primary=_sdt_moi(),
        location_id=loc,
        email="  Mai.Lan@Example.COM  ",
    )
    res = await PatientService(pool).create_patient(dto, staff)
    assert res.patient is not None
    assert res.patient.email == "mai.lan@example.com"
    assert (
        await _email_trong_db(pool, res.patient.clinic_patient_id)
        == "mai.lan@example.com"
    )


@pytest.mark.parametrize("gia_tri", [None, "", "   "])
async def test_tao_khach_khong_email_la_null(
    pool: asyncpg.Pool, gia_tri: str | None
) -> None:
    loc, staff = await _co_so_va_nguoi_tao(pool)
    dto = PatientCreateDTO(
        full_name="Khách Không Email",
        phone_primary=_sdt_moi(),
        location_id=loc,
        email=gia_tri,
    )
    res = await PatientService(pool).create_patient(dto, staff)
    assert res.patient is not None
    assert res.patient.email is None
    assert await _email_trong_db(pool, res.patient.clinic_patient_id) is None


async def test_hai_khach_chung_email_khong_bi_chan(pool: asyncpg.Pool) -> None:
    loc, staff = await _co_so_va_nguoi_tao(pool)
    svc = PatientService(pool)
    chung = f"gia.dinh.{uuid.uuid4().hex[:6]}@example.com"
    ids = []
    for ten in ("Mẹ", "Con gái"):
        res = await svc.create_patient(
            PatientCreateDTO(
                full_name=ten,
                phone_primary=_sdt_moi(),
                location_id=loc,
                email=chung,
            ),
            staff,
        )
        assert res.patient is not None
        ids.append(res.patient.clinic_patient_id)
    for pid in ids:
        assert await _email_trong_db(pool, pid) == chung


async def test_trung_sdt_khong_ghi_de_email_da_co(pool: asyncpg.Pool) -> None:
    """Form gửi SĐT trùng (không force) → cảnh báo, KHÔNG sửa hồ sơ cũ."""
    loc, staff = await _co_so_va_nguoi_tao(pool)
    svc = PatientService(pool)
    sdt = _sdt_moi()
    dau = await svc.create_patient(
        PatientCreateDTO(
            full_name="Khách Cũ",
            phone_primary=sdt,
            location_id=loc,
            email="cu@example.com",
        ),
        staff,
    )
    assert dau.patient is not None
    lai = await svc.create_patient(
        PatientCreateDTO(
            full_name="Khách Cũ",
            phone_primary=sdt,
            location_id=loc,
            email=None,
        ),
        staff,
    )
    assert lai.duplicate is True
    assert lai.patient is None
    assert (
        await _email_trong_db(pool, dau.patient.clinic_patient_id) == "cu@example.com"
    )


@pytest.mark.parametrize(
    "rac",
    [
        "khong-phai-email",
        "abc@",
        "@domain.com",
        "a b@c.com",
        "a@b",
        "a" * 250 + "@b.com",
        123,
        ["a@b.com"],
        {"x": 1},
    ],
)
async def test_tao_khach_email_rac_la_loi_kiem_dinh_khong_500(rac: object) -> None:
    with pytest.raises(PydanticValidationError) as exc:
        PatientCreateDTO.model_validate(
            {
                "full_name": "Khách Email Rác",
                "location_id": str(uuid.uuid4()),
                "email": rac,
            }
        )
    assert "email" in str(exc.value).lower()
