"""Hồ sơ tiếp nhận tối thiểu cần gọi đặt lịch; lịch/lượt thật thay thế việc này."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from clinicai.services.man_khach_hang_service import ManKhachHangService
from tests.services.test_lieu_trinh_db import dung_ca, luot
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhan_luot_db import _lich, _st_kham

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _nhap(pool: asyncpg.Pool, pid: str, clinic: str = CLINIC) -> None:
    await pool.execute(
        "INSERT INTO event_log (clinic_id, event_type, aggregate_type, aggregate_id,"
        " source, payload) VALUES ($1::uuid, 'patient.created', 'patient',"
        " $2, 'api:patient-intake', '{}'::jsonb)",
        clinic,
        pid,
    )


async def test_chi_ten_can_goi_va_dat_lich_thi_bien_mat(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    await pool.execute(
        "UPDATE patient SET phone_primary = NULL WHERE clinic_patient_id = $1::uuid",
        ca.khach,
    )
    svc = ManKhachHangService(pool)
    # Hồ sơ import/legacy chưa từng có lịch không bị đưa vào danh sách gọi.
    assert not (await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach]))["trang_thai"]
    await _nhap(pool, ca.khach)
    goi = await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert goi["trang_thai"] == [
        {
            "clinic_patient_id": UUID(ca.khach),
            "trang_thai": "CHO_DAT_LICH",
            "nhan": "Gọi điện xác nhận",
            "han_xu_ly": None,
            "qua_han": False,
            "so_viec_mo": 1,
            "co_viec_qua_han": False,
            "appointment_id": None,
            "da_xac_nhan": False,
        }
    ]
    assert goi["viec_mo"][0]["trang_thai"] == "CHO_DAT_LICH"
    assert goi["viec_mo"][0]["uu_tien"] == 10
    await _lich(
        ca, await _st_kham(pool), datetime.now(UTC) + timedelta(days=7), "CONFIRMED"
    )
    goi = await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert all(r["trang_thai"] != "CHO_DAT_LICH" for r in goi["trang_thai"])
    assert all(r["trang_thai"] != "CHO_DAT_LICH" for r in goi["viec_mo"])


async def test_co_luot_khong_lich_khong_can_goi(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    await luot(ca)
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert all(r["trang_thai"] != "CHO_DAT_LICH" for r in goi["trang_thai"])


async def test_viec_goi_lai_hien_co_duoc_uu_tien(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    await pool.execute(
        "INSERT INTO hen_goi_lai (clinic_id, clinic_patient_id, ngay_goi, ly_do,"
        " tao_boi_staff_id) VALUES ($1::uuid, $2::uuid, CURRENT_DATE - 1,"
        " 'Gọi lại theo giờ khách yêu cầu', $3::uuid)",
        CLINIC,
        ca.khach,
        ca.cskh.staff_id,
    )
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert goi["trang_thai"][0]["trang_thai"] == "HEN_GOI_LAI"
    assert all(r["trang_thai"] != "CHO_DAT_LICH" for r in goi["viec_mo"])


async def test_khong_doc_ho_so_va_event_cua_phong_kham_khac(pool: asyncpg.Pool) -> None:
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    svc = ManKhachHangService(pool)
    goi = await svc.goi_du_lieu(clinic_id=str(uuid4()), ids=[ca.khach])
    assert goi["trang_thai"] == [] and goi["viec_mo"] == []
