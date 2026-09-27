"""Bản in + phòng dịch vụ Y HỆT bản mẫu (27/09/2026, mục 7 + 11 của kế hoạch).

Máy chủ phải trả đủ thứ màn cần, để màn không tự đoán:
  · phiếu kết quả in: mã dịch vụ, giờ làm + người làm, chẩn đoán lâm sàng
    (nếu bác sĩ chính đã ghi), cơ sở + địa chỉ, số booking / check-in;
  · đầu phiếu khám (bản in): tên phòng khám + địa chỉ cơ sở;
  · phòng dịch vụ (`thuc-hien`): mã phòng khám + giá của dịch vụ.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.phieu_kham.mang_sang import chan_doan_tu_phieu, doc_dau_phieu
from clinicai.services.form_engine_service import FormEngineService
from tests.services.test_form_engine_db import CLINIC, _don_tron, _nguoi
from tests.services.test_service_execution_db import (  # noqa: F401
    KB,
    kb,
    pool,
)


def test_chan_doan_lay_o_dau_tien_co_chu() -> None:
    assert chan_doan_tu_phieu(None) is None
    assert chan_doan_tu_phieu({"pk_dx": {"gia_tri": "  "}}) is None
    assert (
        chan_doan_tu_phieu(
            {"pk_dx": {"gia_tri": ""}, "nk_dx": {"gia_tri": " Viêm niệu đạo "}}
        )
        == "Viêm niệu đạo"
    )
    # Ô không phải chữ (danh sách chọn…) không được coi là chẩn đoán.
    assert chan_doan_tu_phieu({"pk_dx": {"gia_tri": ["a"]}}) is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_in_ket_qua_co_ma_gio_lam_chan_doan(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
        vid = await conn.fetchval(
            "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", order
        )
        ma = await conn.fetchval(
            "SELECT service_code FROM service_order WHERE id = $1::uuid", order
        )
    svc = FormEngineService(pool)

    # Chưa làm, chưa chẩn đoán: hai trường có mặt nhưng rỗng (màn bỏ dòng).
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert ban["gio_lam"] is None and ban["chan_doan"] is None
    # Dịch vụ không có mã phòng khám → rơi về mã dịch vụ của hệ thống.
    assert ban["ma_dich_vu"] == ma
    assert ban["ngay_kham"] is not None
    assert "so_booking" in ban and "so_tiep_don" in ban
    assert "co_so" in ban["phong_kham"]

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO service_execution_attempt (clinic_id, service_order_id,"
            " attempt_no, routing_revision_snapshot, status, started_by, started_at)"
            " VALUES ($1::uuid, $2::uuid, 1, 0, 'IN_PROGRESS', $3::uuid,"
            " now() - interval '5 minutes')",
            CLINIC,
            order,
            bs.staff_id,
        )
        await conn.execute(
            "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version,"
            " du_lieu) VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
            CLINIC,
            vid,
            json.dumps({"pk_dx": {"gia_tri": "Viêm âm đạo", "nguon": "USER"}}),
        )
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert ban["chan_doan"] == "Viêm âm đạo"
    assert ban["gio_lam"]["bat_dau"] and ban["gio_lam"]["xong"] is None
    assert ban["gio_lam"]["nguoi_lam"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_dau_phieu_co_ten_phong_kham(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
        vid = await conn.fetchval(
            "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", order
        )
        ten = await conn.fetchval("SELECT name FROM clinic WHERE id = $1::uuid", CLINIC)
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=vid)
    assert dau["the_khach"]["phong_kham"] == ten
    assert "dia_chi_co_so" in dau["the_khach"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_thuc_hien_tra_ma_va_gia(kb: KB) -> None:  # noqa: F811
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    gia = await kb.pool.fetchrow(
        "SELECT s.ma_kiotviet, s.unit_price FROM service_order o"
        " JOIN service_price s ON s.clinic_id = o.clinic_id"
        "  AND s.service_code = o.service_code"
        " WHERE o.id = $1::uuid ORDER BY s.active DESC LIMIT 1",
        kb.order_id,
    )
    assert gia is not None
    assert nhin["ma_kiotviet"] == gia["ma_kiotviet"]
    assert nhin["gia"] == (
        int(gia["unit_price"]) if gia["unit_price"] is not None else None
    )
