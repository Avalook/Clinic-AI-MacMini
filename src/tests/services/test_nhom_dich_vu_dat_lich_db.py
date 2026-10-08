"""Bộ chọn dịch vụ 4 nhóm khi đặt lịch (T0–T3, Tuyền chốt 07/10/2026) — Postgres thật.

Migration 20261007600000: cột `service_type.nhom`, 6 loại Điều trị trỏ đúng dòng
bảng giá, 1 loại "Khác". Ghi chú lịch (`appointment.notes`) gửi đủ, đổi lịch
sửa được ghi chú mà bản cũ còn trong nhật ký.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.v1.routers.booking import o_doi_dich_vu_kham
from clinicai.core.clock import CLINIC_TZ
from clinicai.services import dich_vu_dat_lich
from clinicai.services.booking_service import BookingService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_dich_vu_kham_db import _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Mã loại Điều trị → giá dòng bảng giá (migration 20261002100000).
GIA_DIEU_TRI = {
    "DT_BIO": 900_000,
    "DT_GHE_DTT": 3_000_000,
    "DT_LASER_TIEN_DINH": 4_500_000,
    "DT_LASER_TIEN_DINH_AM_DAO": 7_000_000,
    "DT_LASER_1_THANH": 10_000_000,
    "DT_LASER_2_THANH": 15_000_000,
}


async def _ma(pool: asyncpg.Pool, code: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT id::text FROM service_type"
            " WHERE clinic_id = $1::uuid AND code = $2",
            CLINIC,
            code,
        )
    )


def _gio_xa() -> dt.datetime:
    return dt.datetime.now(CLINIC_TZ).replace(
        hour=9, minute=0, second=0, microsecond=0
    ) + dt.timedelta(days=7 * (60 + uuid.uuid4().int % 300))


async def test_sau_loai_dieu_tri_tro_dung_dong_gia(pool: asyncpg.Pool) -> None:  # noqa: F811
    rows = await pool.fetch(
        """
        SELECT st.code, st.form_code, st.qua_tu_van, st.di_thang_phong,
               sp.unit_price, sp.clinic_id = st.clinic_id AS cung_pk
          FROM service_type st
          JOIN service_price sp ON sp.id = st.service_price_id
         WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI' AND st.is_active
        """,
        CLINIC,
    )
    # Bỏ loại điều trị do bài liệu trình tự dựng (`dung_ca`: mã "DT-<8 hex>") —
    # cùng DB test, thứ tự chạy khác nhau thì chúng có hoặc không.
    theo_ma = {
        r["code"]: r for r in rows if not re.fullmatch(r"DT-[0-9a-f]{8}", r["code"])
    }
    assert set(theo_ma) == set(GIA_DIEU_TRI)
    for ma, gia in GIA_DIEU_TRI.items():
        r = theo_ma[ma]
        assert int(r["unit_price"]) == gia, ma
        assert r["cung_pk"]
        # Điều trị: không phiếu khám riêng. (qua_tu_van / di_thang_phong là dây
        # quản lý chỉnh trên màn — test khác cùng DB bật/tắt, không khẳng định.)
        assert r["form_code"] is None


async def test_dieu_tri_bat_buoc_co_dong_gia(pool: asyncpg.Pool) -> None:  # noqa: F811
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO service_type (clinic_id, code, name, nhom)"
            " VALUES ($1::uuid, $2, 'Điều trị không giá', 'DIEU_TRI')",
            CLINIC,
            f"DTX-{uuid.uuid4().hex[:8]}",
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO service_type (clinic_id, code, name, nhom)"
            " VALUES ($1::uuid, $2, 'Nhóm lạ', 'LA')",
            CLINIC,
            f"DTX-{uuid.uuid4().hex[:8]}",
        )


async def test_doc_tra_bon_nhom_thuoc_an(pool: asyncpg.Pool) -> None:  # noqa: F811
    # Một loại nhóm Thuốc đang bật — vẫn KHÔNG được trả (T4).
    await pool.execute(
        "INSERT INTO service_type (clinic_id, code, name, nhom)"
        " VALUES ($1::uuid, $2, 'Thuốc thử', 'THUOC')",
        CLINIC,
        f"TH-{uuid.uuid4().hex[:8]}",
    )
    async with pool.acquire() as conn:
        goi = await dich_vu_dat_lich.doc(conn, CLINIC)
    ma_nhom = [n["ma"] for n in goi["nhom"]]
    assert ma_nhom[:1] == ["KHAM"]
    assert "DIEU_TRI" in ma_nhom and ma_nhom[-1] == "KHAC"
    assert "THUOC" not in ma_nhom
    dieu_tri = next(n for n in goi["nhom"] if n["ma"] == "DIEU_TRI")
    assert [d["ten"] for d in dieu_tri["dich_vu"]][:2] == [
        "Tập máy Bio điều trị (chưa gồm đầu dò)",
        "Ghế điện từ trường",
    ]
    khac = goi["nhom"][-1]
    assert khac["goi_y_ghi_chu"] and [d["ten"] for d in khac["dich_vu"]] == ["Khác"]


async def test_khac_luu_duoc_khong_ghi_chu(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    khac = await _ma(pool, "KHAC")
    bd = _gio_xa()
    kq = await BookingService(pool).create(
        clinic_patient_id=ca["pid"],
        service_type_id=khac,
        location_id=ca["loc"],
        slot_start=bd,
        slot_end=bd + dt.timedelta(minutes=15),
        identity=ca["cskh"],
        booking_channel="PHONE",
    )
    row = await pool.fetchrow(
        "SELECT service_type_id::text, notes FROM appointment WHERE id = $1::uuid",
        kq["appointment_id"],
    )
    assert row["service_type_id"] == khac
    assert row["notes"] is None


async def test_doi_lich_sua_ghi_chu_giu_ban_cu_trong_nhat_ky(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    khac = await _ma(pool, "KHAC")
    bd = _gio_xa()
    luat = BookingService(pool)
    kq = await luat.create(
        clinic_patient_id=ca["pid"],
        service_type_id=khac,
        location_id=ca["loc"],
        slot_start=bd,
        slot_end=bd + dt.timedelta(minutes=15),
        identity=ca["cskh"],
        booking_channel="PHONE",
        notes="Khách muốn gặp bác sĩ hỏi kết quả",
    )
    aid = kq["appointment_id"]
    await luat.apply_action(
        appointment_id=aid,
        action="reschedule",
        identity=ca["cskh"],
        slot_start=bd,
        slot_end=bd + dt.timedelta(minutes=15),
        ghi_chu="  Khách hỏi kết quả + tư vấn laser ",
        ghi_chu_provided=True,
    )
    assert (
        await pool.fetchval("SELECT notes FROM appointment WHERE id = $1::uuid", aid)
        == "Khách hỏi kết quả + tư vấn laser"
    )
    nk = await pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND payload ? 'ghi_chu_cu' ORDER BY recorded_at DESC LIMIT 1",
        aid,
    )
    nk = json.loads(nk) if isinstance(nk, str) else nk
    assert nk["ghi_chu_cu"] == "Khách muốn gặp bác sĩ hỏi kết quả"
    assert nk["ghi_chu_moi"] == "Khách hỏi kết quả + tư vấn laser"

    # Không gửi ghi chú = giữ nguyên (đổi giờ thôi).
    await luat.apply_action(
        appointment_id=aid,
        action="reschedule",
        identity=ca["cskh"],
        slot_start=bd + dt.timedelta(minutes=15),
        slot_end=bd + dt.timedelta(minutes=30),
    )
    assert (
        await pool.fetchval("SELECT notes FROM appointment WHERE id = $1::uuid", aid)
        == "Khách hỏi kết quả + tư vấn laser"
    )


async def test_popover_doi_dich_vu_tra_nhom(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    goi = await o_doi_dich_vu_kham(
        appointment_id=UUID(ca["appt"]), identity=ca["le_tan"], pool=pool
    )
    ma_nhom = [n["ma"] for n in goi["nhom"]]
    assert "DIEU_TRI" in ma_nhom and "KHAC" in ma_nhom
    # Danh sách phẳng cũ vẫn còn (màn cũ đọc không vỡ) và khớp số mục.
    # (Dòng rác "FREE" — còn bật ở DB thử dựng từ seed — nhóm bỏ, danh sách cũ giữ.)
    assert sum(len(n["dich_vu"]) for n in goi["nhom"]) == len(
        [x for x in goi["lua_chon"] if x["ten"].upper() != "FREE"]
    )
    hien_tai = [d for n in goi["nhom"] for d in n["dich_vu"] if d.get("hien_tai")]
    assert [d["id"] for d in hien_tai] == [ca["dv"]]
