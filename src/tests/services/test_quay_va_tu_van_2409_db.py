"""Tuyền 24/09/2026 (giao diện): quầy chọn phòng trước khi chốt + thu; bàn tư
vấn một ô chữ tự do sang mục "mang sang" của bác sĩ chính.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.luot_kham_service import LuotKhamConflictError, LuotKhamService
from clinicai.services.service_routing_service import ServiceRoutingService
from clinicai.services.service_selection_service import cho_khach_quyet
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _phong,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_quay_chon_phong_truoc_khi_thu_thi_thu_xong_vao_dung_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        phong_chon = await _phong(conn, ca.loc, f"chon{uuid.uuid4().hex[:4]}")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    # Quầy thấy phòng chọn được NGAY lúc khách còn đang quyết.
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    [cd] = [c for c in cho["chi_dinh"] if c["id"] == order]
    assert phong_chon in {p["id"] for p in cd["phong_chon_duoc"]}
    assert cd["phong_du_kien_id"] is None

    await _chon(pool, ca, visit, [order])
    kq = await ServiceRoutingService(pool).dat_phong_du_kien(
        order_id=order, room_id=phong_chon, identity=ca.le_tan
    )
    assert kq["phong_du_kien_id"] == phong_chon
    assert (await _don(pool, order))["routing_status"] in (None, "UNASSIGNED")

    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"
    assert (
        await pool.fetchval(
            "SELECT room_id::text FROM service_order WHERE id = $1::uuid", order
        )
        == phong_chon
    )
    # Đã xếp chính thức thì không đặt "dự kiến" nữa — đổi ở Điều phối.
    with pytest.raises(LuotKhamConflictError):
        await ServiceRoutingService(pool).dat_phong_du_kien(
            order_id=order, room_id=None, identity=ca.le_tan
        )


async def test_phong_du_kien_phai_lam_duoc_buoc_nay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    buoc_khac = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid AND code <>"
        " (SELECT node_code FROM service_order WHERE id = $2::uuid) LIMIT 1",
        CLINIC,
        order,
    )
    phong_khac = await pool.fetchval(
        "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
        " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3,"
        " 'Phòng bước khác', $4, true, true, 999) RETURNING id::text",
        CLINIC,
        ca.loc,
        f"BK-{uuid.uuid4().hex[:6]}",
        buoc_khac,
    )
    await pool.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, $3)",
        CLINIC,
        phong_khac,
        buoc_khac,
    )
    with pytest.raises(LuotKhamConflictError):
        await ServiceRoutingService(pool).dat_phong_du_kien(
            order_id=order, room_id=phong_khac, identity=ca.le_tan
        )


async def test_o_chu_tu_van_sang_muc_mang_sang_ban_moi_nhat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await pool.execute(
        "UPDATE service_type SET qua_tu_van = true WHERE id = $1::uuid", ca.loai_kham
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    tu_van = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'TU_VAN'",
        visit,
    )
    assert tu_van, "khách qua tư vấn phải có phiên tư vấn"
    svc = LuotKhamService(pool)
    await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van, noi_dung="Đau bụng 3 ngày", identity=ca.bac_si
    )
    kq = await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van,
        noi_dung="Đau bụng 3 ngày, sốt nhẹ",
        identity=ca.bac_si,
    )
    assert kq["doi"] is True
    # Gửi lại đúng nội dung cũ → không thêm dòng.
    kq = await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van,
        noi_dung="Đau bụng 3 ngày, sốt nhẹ",
        identity=ca.bac_si,
    )
    assert kq["doi"] is False
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    cua_tu_van = [g for g in dau["tu_van"] if g["consultation_id"] == tu_van]
    assert [g["noi_dung"] for g in cua_tu_van] == ["Đau bụng 3 ngày, sốt nhẹ"]
    # Phiên KHÁM CHÍNH không nhận lệnh này.
    chinh = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'PRIMARY'",
        visit,
    )
    if chinh:
        with pytest.raises(LuotKhamConflictError):
            await svc.luu_noi_dung_tu_van(
                consultation_id=chinh, noi_dung="x", identity=ca.bac_si
            )


async def test_gioi_thieu_va_ho_so_dong_bo_sang_phieu_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Kênh Giới thiệu ghi người giới thiệu vào HỒ SƠ; phiếu khám đọc đủ hồ sơ."""
    import datetime as dt

    from clinicai.core.clock import CLINIC_TZ
    from clinicai.services.booking_service import BookingService

    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await pool.execute(
        "UPDATE patient SET gender = 'Nữ', phone_secondary = '0911222333',"
        " occupation = 'Giáo viên', ethnicity = 'Kinh'"
        " WHERE clinic_patient_id = $1::uuid",
        pid,
    )
    bd = dt.datetime.now(CLINIC_TZ).replace(
        hour=9, minute=0, second=0, microsecond=0
    ) + dt.timedelta(days=7 * (60 + uuid.uuid4().int % 300))
    await BookingService(pool).create(
        clinic_patient_id=pid,
        service_type_id=ca.loai_kham,
        location_id=ca.loc,
        slot_start=bd,
        slot_end=bd + dt.timedelta(minutes=15),
        identity=ca.le_tan,
        booking_channel="REFERRAL",
        nguoi_gioi_thieu="  Chị   Hoa (khách cũ) ",
    )
    assert (
        await pool.fetchval(
            "SELECT nguoi_gioi_thieu FROM patient WHERE clinic_patient_id = $1::uuid",
            pid,
        )
        == "Chị Hoa (khách cũ)"
    )
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    hc = dau["hanh_chinh"]
    assert hc["patient.referrer"] == "Chị Hoa (khách cũ)"
    assert hc["patient.gender"] == "Nữ"
    assert hc["patient.phone_family"] == "0911222333"
    assert hc["patient.occupation"] == "Giáo viên"
    assert "patient.referrer" in dau["ho_so"] and dau["nhan"]["patient.referrer"]


async def test_mau_ket_qua_danh_dau_mau_cua_dich_vu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.phieu_kham.mau_goi_y import ma_mau_goi_y, mau_cho_dich_vu

    ma_dv = next(
        (
            c
            for c in ("CLS_SIEU_AM_2D_TC_BT", "CLS_SOI_CO_TU_CUNG", "CLS_THAO_VONG")
            if ma_mau_goi_y(c)
        ),
        None,
    )
    if ma_dv is None:
        pytest.skip("không có dịch vụ nào có mẫu gợi ý")
    async with pool.acquire() as conn:
        mau, goi_y = await mau_cho_dich_vu(conn, clinic_id=CLINIC, service_code=ma_dv)
    if not mau:
        pytest.skip("DB thử chưa có mẫu kết quả")
    cua = [m["ma"] for m in mau if m["cua_dich_vu"]]
    da_gan = [
        r["mau"]
        for r in await pool.fetch(
            "SELECT mau FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
            " AND service_code = $2",
            CLINIC,
            ma_dv,
        )
    ]
    if da_gan:
        # Dịch vụ đã gắn mẫu (26/09/2026, theo mã phòng khám của PDF): mẫu của
        # dịch vụ = đúng các mẫu đã gắn.
        assert sorted(cua) == sorted(da_gan)
    elif goi_y:
        # Mẫu gợi ý + mẫu CHUNG nhập tự do (không thuộc dịch vụ nào khác).
        assert sorted(cua) == sorted([goi_y, "CHUNG"])
    else:
        assert len(cua) == len(mau)
