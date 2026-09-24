"""Đối tác nhận việc BẰNG SỰ KIỆN (Tuyền 24/09/2026: "bác sĩ chỉ định sinh event
đối tác nhận chưa").

  * Đối tác tự lấy mẫu: bác sĩ chỉ định → CHƯA sang bàn đối tác; khách chọn làm
    + trả tiền (`payment.service_collected`) → khối Đối tác nhận việc, phát
    `partner.order_received`, réo chuông vai Đối tác.
  * Điều dưỡng lấy mẫu: phòng bấm Xong (`service.completed`, lối mới) → nhận.
  * Quầy thu thấy nhãn "Đối tác làm" (`doi_tac`) ở ô chọn dịch vụ.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.events.catalogue import CHUONG
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_selection_service import cho_khach_quyet
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh, doi_tac_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dich_vu(pool: asyncpg.Pool, node: str, *, tu_lay: bool) -> str:  # noqa: F811
    ma = f"DT-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code, doi_tac_lay_mau) VALUES ($1::uuid, $2, $3,"
        " 'dich_vu', 200000, $4, $5)",
        CLINIC,
        ma,
        f"Dịch vụ đối tác {ma}",
        node,
        tu_lay,
    )
    return ma


async def _chi_dinh(pool: asyncpg.Pool, ca: Ca, visit: str, ma: str) -> str:  # noqa: F811
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ma],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    return str(kq["order_ids"][0])


def _tren_ban(kq: dict[str, Any], order: str) -> dict[str, Any] | None:
    return next(
        (v for k in kq["khach"] for v in k["viec"] if v["chi_dinh_id"] == order),
        None,
    )


async def _so_su_kien(pool: asyncpg.Pool, order: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'partner.order_received' AND aggregate_id = $1::uuid",
            order,
        )
    )


async def test_doi_tac_tu_lay_mau_chi_nhan_sau_khi_khach_tra_tien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    ma = await _dich_vu(pool, "DICHVU-HINHANH-NGOAI", tu_lay=True)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh(pool, ca, visit, ma)
    async with pool.acquire() as conn:
        doi_tac = await _nguoi(conn, ca.loc, "PARTNER")
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    # Quầy thu nói ra "Đối tác làm".
    [cd] = [c for c in cho["chi_dinh"] if c["id"] == order]
    assert cd["doi_tac"] is True

    # Bác sĩ vừa chỉ định, khách CHƯA chọn / CHƯA trả → chưa sang bàn đối tác.
    await doi_tac_nhan(pool)
    assert (
        _tren_ban(await DoiTacService(pool).viec_doi_tac(identity=doi_tac), order)
        is None
    )

    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    await doi_tac_nhan(pool)

    viec = _tren_ban(await DoiTacService(pool).viec_doi_tac(identity=doi_tac), order)
    assert viec is not None and viec["trang_thai"] == "CHO_LAY_MAU"
    assert await _so_su_kien(pool, order) == 1
    assert (
        await pool.fetchval(
            "SELECT ly_do FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid",
            order,
        )
        == "DA_THU_TIEN"
    )
    # Chuông cho vai Đối tác.
    await chay_ben_nhan(pool, CHUONG)
    assert await pool.fetchval(
        "SELECT count(*) FROM thong_bao WHERE vai_nhan = 'PARTNER'"
        " AND nguon = 'doi_tac_viec' AND nguon_id = $1",
        f"partner.order_received:{order}",
    )
    # Chạy lại bên nhận không nhận trùng.
    await doi_tac_nhan(pool)
    assert await _so_su_kien(pool, order) == 1
    # Đối tác bấm "Đã lấy mẫu" kèm ghi chú → hiện trên bàn (24/09/2026).
    await DoiTacService(pool).doi_tac_da_lay_mau(
        order_id=order, identity=doi_tac, ghi_chu="Lấy mẫu 10h, mẫu đủ"
    )
    viec = _tren_ban(await DoiTacService(pool).viec_doi_tac(identity=doi_tac), order)
    assert viec is not None and viec["ghi_chu_lay_mau"] == "Lấy mẫu 10h, mẫu đủ"


async def test_dieu_duong_lay_mau_xong_thi_doi_tac_nhan_viec(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    node = "DICHVU-LAYMAU-MAU"
    ma = await _dich_vu(pool, node, tu_lay=False)
    async with pool.acquire() as conn:
        # Phòng lấy mẫu CỦA ca thử (cùng cơ sở) để thu xong dây H4 xếp vào.
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3,"
            " 'Lấy mẫu thử', $4, true, true, 0) RETURNING id::text",
            CLINIC,
            ca.loc,
            f"LM-{uuid.uuid4().hex[:6]}",
            node,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong,
            node,
        )
        doi_tac = await _nguoi(conn, ca.loc, "PARTNER")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh(pool, ca, visit, ma)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    await doi_tac_nhan(pool)
    # Đã trả nhưng điều dưỡng CHƯA lấy mẫu → đối tác chưa có gì để nhận.
    assert (
        _tren_ban(await DoiTacService(pool).viec_doi_tac(identity=doi_tac), order)
        is None
    )

    o = await pool.fetchrow(
        "SELECT execution_revision, routing_revision, routing_status"
        " FROM service_order WHERE id = $1::uuid",
        order,
    )
    assert o["routing_status"] == "ASSIGNED"
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
    )
    await doi_tac_nhan(pool)
    viec = _tren_ban(await DoiTacService(pool).viec_doi_tac(identity=doi_tac), order)
    assert viec is not None and viec["trang_thai"] == "DA_LAY_MAU"
    assert (
        await pool.fetchval(
            "SELECT ly_do FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid",
            order,
        )
        == "DA_LAY_MAU"
    )
