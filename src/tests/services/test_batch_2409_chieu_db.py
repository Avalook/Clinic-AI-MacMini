"""Batch Tuyền 24/09/2026 chiều.

* Số "đang chờ" ở phòng là người THẬT: không tính chính khách đang xếp.
* Chỉ định khách BỎ ở quầy: màn Xem lượt ghi "Khách không làm" (không còn
  "Chờ xếp phòng").
* Ghi chú khi bấm Xong (điều dưỡng lấy mẫu) — lưu vào lần làm, hiện ở Xem lượt.
* Thuốc quy chuẩn một kho: lưu đơn bằng TÊN → tự gắn mã kho (có sẵn thì gắn,
  chưa có thì thêm vào danh mục, cần soát).
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.services.dinh_chinh_don import luu_don_chua_ky
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import eligible_rooms
from clinicai.services.xem_luot_service import XemLuotService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    NODE,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_so_nguoi_cho_khong_tinh_chinh_khach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    phong = (await _don(pool, order))["room_id"]
    async with pool.acquire() as conn:
        tai = {
            r.room_id: r.tai for r in await eligible_rooms(conn, CLINIC, NODE, ca.loc)
        }
        tai_tru = {
            r.room_id: r.tai
            for r in await eligible_rooms(conn, CLINIC, NODE, ca.loc, tru_luot=visit)
        }
    assert tai[phong] >= 1
    assert tai_tru[phong] == tai[phong] - 1, "không đếm chính khách đang xếp"


async def test_khach_bo_va_ghi_chu_lay_mau_hien_o_xem_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    # Một chỉ định khác khách BỎ ở quầy.
    bo = await pool.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, selection_status,"
        " recorded_by, authorized_by, authorized_at)"
        " SELECT clinic_id, visit_id, consultation_id, service_code,"
        " 'Đo mật độ xương thử', node_code, 'authorized', 'NOT_SELECTED',"
        " recorded_by, authorized_by, authorized_at"
        " FROM service_order WHERE id = $1::uuid"
        " RETURNING id::text",
        order,
    )
    o = await _don(pool, order)
    ex = ServiceExecutionService(pool)
    bd = await ex.bat_dau(
        order_id=order,
        expected_execution_revision=int(o["execution_revision"]),
        expected_routing_revision=int(o["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await ex.xong(
        order_id=order,
        attempt_id=str(bd["attempt_id"]),
        expected_execution_revision=int(bd["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
        ghi_chu="  Khách khó lấy ven, lấy lần 2 ",
    )
    kq = await XemLuotService(pool).doc(visit_id=visit, identity=ca.le_tan)
    dv = {d["id"]: d for d in kq["dich_vu"]}
    assert dv[bo]["trang_thai"] == "khach_khong_lam"
    assert dv[order]["ghi_chu"] == ["Khách khó lấy ven, lấy lần 2"]


async def test_luu_don_bang_ten_tu_gan_ma_kho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    co_san = f"Thuoc co san {uuid.uuid4().hex[:6]}"
    id_co_san = await pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_raw, name_base)"
        " VALUES ($1::uuid, $2, $2) RETURNING id::text",
        CLINIC,
        co_san,
    )
    chua_co = f"Thuoc moi {uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn, conn.transaction():
        await luu_don_chua_ky(
            conn,
            visit_id=visit,
            clinic_id=CLINIC,
            clinic_patient_id=pid,
            prescriptions=[
                {"drug_name": f"  {co_san.upper()} ", "quantity": "2 hộp"},
                {"drug_name": chua_co, "quantity": "1 hộp"},
            ],
            created_by=ca.bac_si.staff_id,
            identity=ca.bac_si,
            ly_do=None,
        )
    rows = await pool.fetch(
        "SELECT pr.drug_catalog_id::text AS ma, d.name_raw, d.needs_review"
        " FROM prescription pr JOIN drug_catalog d ON d.id = pr.drug_catalog_id"
        " WHERE pr.visit_id = $1::uuid AND pr.removed_at IS NULL",
        visit,
    )
    ma = {r["name_raw"]: r for r in rows}
    assert ma[co_san]["ma"] == id_co_san  # gắn đúng thuốc có sẵn
    assert ma[chua_co]["needs_review"] is True  # thuốc mới vào danh mục, cần soát
    assert len(rows) == 2, "không còn dòng chưa gắn kho"


async def test_khach_thu_thuat_san_chau_hien_o_moi_phong_thu_thuat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 24/09/2026: khách đặt Thủ thuật / Sàn chậu → hiện ở hàng chờ các
    phòng làm thủ thuật (dù lịch đã gắn bác sĩ khác); khách khám thường thì không.
    """
    from clinicai.services.luot_kham_doc import BangLuotKham

    ca = await _dung(pool)
    async with pool.acquire() as conn:
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3,"
            " 'Phòng thủ thuật thử', 'DICHVU-THUTHUAT', true, true, 0)"
            " RETURNING id::text",
            CLINIC,
            ca.loc,
            f"TT-{uuid.uuid4().hex[:6]}",
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, 'DICHVU-THUTHUAT')",
            CLINIC,
            phong,
        )
    tt = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_thu_thuat)
    thuong = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    kq = await BangLuotKham(pool).hang_cho(identity=ca.dd, room_id=phong)
    luot = {d["visit_id"] for d in kq["hang_cho"]}
    assert tt in luot, "khách Thủ thuật/Sàn chậu phải hiện ở phòng thủ thuật"
    assert thuong not in luot, "khách khám thường không lạc sang phòng thủ thuật"
