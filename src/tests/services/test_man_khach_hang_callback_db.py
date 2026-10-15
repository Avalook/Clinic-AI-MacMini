"""Hồ sơ tiếp nhận tối thiểu cần gọi đặt lịch; lịch/lượt thật thay thế việc này."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from clinicai.services.man_khach_hang_service import ManKhachHangService
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from tests.services.test_lieu_trinh_db import LT, dung_ca, luot
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


async def _goi(pool: asyncpg.Pool, ca: LT, ket_qua: str) -> str:
    """CSKH bấm một nút trên việc "Gọi điện xác nhận" — đúng body màn gửi."""
    kq = await TuongTacCskhService(pool).ghi(
        identity=ca.cskh,
        clinic_patient_id=ca.khach,
        loai="HOI_THAM",
        kenh="GOI",
        ket_qua=ket_qua,
        trang_thai_ma="CHO_DAT_LICH",
    )
    return str(kq["id"])


def _con_viec(goi: dict[str, list[Any]]) -> bool:
    return any(r["trang_thai"] == "CHO_DAT_LICH" for r in goi["trang_thai"]) and any(
        r["trang_thai"] == "CHO_DAT_LICH" for r in goi["viec_mo"]
    )


async def test_goi_xong_nhan_mat_hoan_tac_nhan_tro_lai(pool: asyncpg.Pool) -> None:
    """15/10/2026: khách chỉ lưu hồ sơ — CSKH ghi "đã liên hệ" thì hết việc;
    rút lại thì việc quay lại. Người bấm + lúc bấm nằm ở dòng sổ."""
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    svc = ManKhachHangService(pool)
    assert _con_viec(await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach]))

    tt_id = await _goi(pool, ca, "DA_LIEN_HE")
    goi = await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert not any(r["trang_thai"] == "CHO_DAT_LICH" for r in goi["trang_thai"])
    assert not any(r["trang_thai"] == "CHO_DAT_LICH" for r in goi["viec_mo"])
    # Dòng sổ nói ai + lúc nào, gắn đúng mã việc.
    dong = await pool.fetchrow(
        "SELECT nhan_vien_staff_id::text AS ai, xay_ra_luc, trang_thai_ma"
        "  FROM tuong_tac_cskh WHERE id = $1::uuid",
        tt_id,
    )
    assert dong is not None
    assert dong["ai"] == ca.cskh.staff_id
    assert dong["xay_ra_luc"] is not None
    assert dong["trang_thai_ma"] == "CHO_DAT_LICH"

    await TuongTacCskhService(pool).hoan_tac(identity=ca.cskh, tuong_tac_id=tt_id)
    assert _con_viec(await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach]))


async def test_goi_khong_gap_khach_viec_con_mo(pool: asyncpg.Pool) -> None:
    """Không nghe máy / không liên lạc được / hẹn gọi lại: vẫn phải gọi tiếp."""
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    svc = ManKhachHangService(pool)
    for kq in ("CHUA_NGHE_MAY", "KHONG_LIEN_LAC_DUOC", "HEN_GOI_LAI"):
        await _goi(pool, ca, kq)
        assert _con_viec(await svc.goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])), kq


async def test_cuoc_goi_khac_viec_khong_dong_viec_goi_xac_nhan(
    pool: asyncpg.Pool,
) -> None:
    """Chỉ lần gọi mang mã CHO_DAT_LICH mới đóng — ghi chăm sóc tự do thì không."""
    ca = await dung_ca(pool)
    await _nhap(pool, ca.khach)
    await TuongTacCskhService(pool).ghi(
        identity=ca.cskh,
        clinic_patient_id=ca.khach,
        loai="HOI_THAM",
        kenh="GOI",
        ket_qua="DA_LIEN_HE",
    )
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    assert _con_viec(goi)
