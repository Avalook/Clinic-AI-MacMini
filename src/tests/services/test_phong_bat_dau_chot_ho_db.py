"""Phòng bấm Bắt đầu với chỉ định đang CHỜ CHỐT — cửa tiền chung, chốt hộ
(Tuyền chốt 09/10/2026), trên Postgres thật.

    scripts/test-nhanh.sh src/tests/services/test_phong_bat_dau_chot_ho_db.py

Lượt Điều trị (Laser) đi thẳng phòng: chỉ định tự sinh còn chờ khách quyết,
phòng Nhận được. Bắt đầu ở phòng đi CÙNG cửa với bàn khám:
  * dây thu trước BẬT, chưa thu, chưa tick → 409 câu "chưa thu";
  * đã tick (kể cả tick trước khi có chỉ định) → chốt hộ, làm; quầy thấy dòng
    phải thu, check-out chặn nợ;
  * Huỷ bắt đầu → lựa chọn về lại "chờ quyết";
  * dây thu trước TẮT → làm được;
  * khách đã chọn KHÔNG làm → chặn;
  * dây Nhận tại phòng TẮT (H4 tự xếp nghe `service_selection.confirmed`) →
    chốt hộ không làm H4 xếp lại chỉ định đã có phòng / đang làm.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.events.consumers.hanh_trinh import _tu_xep_bat
from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.finance_gate import CAU_CHUA_THU
from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.service_execution_service import (
    CAU_KHACH_KHONG_CHON,
    ServiceExecutionService,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh, chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
    _khoa,
    _phong,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@asynccontextmanager
async def _day(pool: asyncpg.Pool, ma: str, gia_tri: Any) -> AsyncIterator[None]:  # noqa: F811
    """Đặt một dây nối cho phòng khám thử, trả lại như cũ sau đó."""
    cu = await pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
        " AND ma = $2",
        CLINIC,
        ma,
    )
    sql = (
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri) VALUES ($1::uuid, $2,"
        " $3::jsonb) ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri ="
        " EXCLUDED.gia_tri"
    )
    await pool.execute(sql, CLINIC, ma, json.dumps(gia_tri))
    try:
        yield
    finally:
        if cu is None:
            await pool.execute(
                "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid AND ma = $2",
                CLINIC,
                ma,
            )
        else:
            await pool.execute(sql, CLINIC, ma, cu)


async def _loai_laser(pool: asyncpg.Pool) -> str:  # noqa: F811
    st = await pool.fetchval(
        "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
        " AND code = 'DT_LASER_TIEN_DINH'",
        CLINIC,
    )
    assert st is not None, "migration 20261007600000 phải có loại Điều trị Laser"
    return str(st)


async def _luot_dieu_tri(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    return await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai_laser(pool)
    )


async def _chi_dinh_tu_sinh(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    [order] = [
        r["id"]
        for r in await pool.fetch(
            "SELECT id::text FROM service_order WHERE visit_id = $1::uuid"
            " AND exec_status <> 'cancelled'",
            visit,
        )
    ]
    return str(order)


async def _phong_cua(pool: asyncpg.Pool, ca: Ca, order: str) -> str:  # noqa: F811
    """Phòng thử làm ĐÚNG bước của chỉ định (không thành phòng thừa cho bài khác)."""
    node = await pool.fetchval(
        "SELECT node_code FROM service_order WHERE id = $1::uuid", order
    )
    async with pool.acquire() as conn:
        phong = await _phong(conn, ca.loc, uuid.uuid4().hex[:8])
        await conn.execute(
            "DELETE FROM clinic_room_node WHERE room_id = $1::uuid", phong
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
            CLINIC,
            phong,
            node,
        )
    return phong


async def _nhan(pool: asyncpg.Pool, ca: Ca, visit: str, order: str) -> str:  # noqa: F811
    """Phòng bấm Nhận (dây Nhận tại phòng bật cho riêng bước này)."""
    phong = await _phong_cua(pool, ca, order)
    async with _day(pool, "nhan_tai_phong", True):
        kq = await ntp.NhanTaiPhongService(pool).nhan(
            visit_id=visit,
            room_id=phong,
            identity=ca.thu_ngan,
            chi_dinh_ids=[order],
        )
    assert kq["da_nhan"] == [order]
    return phong


async def _don(pool: asyncpg.Pool, order: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT selection_status, execution_status, exec_status, routing_status,"
        "       room_id::text AS room_id, routing_revision, execution_revision"
        "  FROM service_order WHERE id = $1::uuid",
        order,
    )
    assert r is not None
    return r


async def _bat_dau(pool: asyncpg.Pool, ca: Ca, order: str) -> dict[str, Any]:  # noqa: F811
    d = await _don(pool, order)
    return await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _so_su_kien(pool: asyncpg.Pool, ten: str, agg: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = $1"
            " AND aggregate_id = $2::uuid",
            ten,
            agg,
        )
    )


async def test_day_bat_chua_tick_bat_dau_bi_chan_cau_ro(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, True):
        ca = await _dung(pool)
        visit = await _luot_dieu_tri(pool, ca)
        order = await _chi_dinh_tu_sinh(pool, visit)
        await _nhan(pool, ca, visit, order)
        assert (await _don(pool, order))["selection_status"] == "PENDING"
        with pytest.raises(LuotKhamConflictError) as e:
            await _bat_dau(pool, ca, order)
        assert e.value.error_code == "FINANCE_NOT_READY"
        assert str(e.value) == CAU_CHUA_THU
        # Bị chặn thì không chốt gì, không mở lần làm nào.
        d = await _don(pool, order)
        assert d["selection_status"] == "PENDING"
        assert d["execution_status"] in (None, "PENDING")
        assert not await pool.fetchval(
            "SELECT count(*) FROM service_execution_attempt"
            " WHERE service_order_id = $1::uuid",
            order,
        )


async def test_da_tick_bat_dau_chot_ho_quay_thu_check_out_chan_no(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, True):
        ca = await _dung(pool)
        visit = await _luot_dieu_tri(pool, ca)
        # Tick ở bước TRƯỚC (lễ tân / bác sĩ) khi chỉ định chưa sinh ra: tick
        # không chốt được gì, chỉ định sinh sau vẫn "chờ quyết".
        await LamTruocThuSauService(pool).dat(
            visit_id=visit, bat=True, identity=ca.bac_si
        )
        order = await _chi_dinh_tu_sinh(pool, visit)
        phong = await _nhan(pool, ca, visit, order)
        assert (await _don(pool, order))["selection_status"] == "PENDING"

        bd = await _bat_dau(pool, ca, order)
        assert bd["execution_status"] == "IN_PROGRESS" and bd["chot_lua_chon"] is True
        d = await _don(pool, order)
        assert (d["selection_status"], d["room_id"]) == ("SELECTED", phong)
        lan = await pool.fetchrow(
            "SELECT chot_lua_chon_tu, chot_lua_chon_rev, noi_lam"
            "  FROM service_execution_attempt WHERE id = $1::uuid",
            bd["attempt_id"],
        )
        assert lan["chot_lua_chon_tu"] == "PENDING" and lan["chot_lua_chon_rev"]
        assert lan["noi_lam"] is None
        chot = await pool.fetchval(
            "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
            " AND event_type = 'service_selection.confirmed'"
            " ORDER BY recorded_at DESC LIMIT 1",
            visit,
        )
        assert json.loads(chot)["nguon"] == "lam_tai_phong"

        await ServiceExecutionService(pool).xong(
            order_id=order,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=bd["execution_revision"],
            identity=ca.dd,
            idempotency_key=_khoa(),
        )
        # Quầy thấy ĐÚNG một dòng phải thu của chỉ định; check-out chặn nợ.
        async with pool.acquire() as conn:
            hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
        dong = [x for x in hd.dong if x.source_id == order]
        assert len(dong) == 1 and int(dong[0].thanh_tien or 0) > 0
        ss = await CheckoutService(pool).readiness(identity=ca.le_tan, visit_id=visit)
        assert order in [x["source_id"] for x in ss["no_khi_ve"]["dong"]]
        assert ss["no_khi_ve"]["chan"] is True and ss["can_close"] is False


async def test_day_tat_lam_duoc_huy_bat_dau_ve_cho_quyet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, False):
        ca = await _dung(pool)
        visit = await _luot_dieu_tri(pool, ca)
        order = await _chi_dinh_tu_sinh(pool, visit)
        phong = await _nhan(pool, ca, visit, order)
        bd = await _bat_dau(pool, ca, order)
        assert (await _don(pool, order))["selection_status"] == "SELECTED"

        kq = await ServiceExecutionService(pool).huy_bat_dau(
            order_id=order,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=bd["execution_revision"],
            identity=ca.dd,
            idempotency_key=_khoa(),
        )
        assert kq["tra_lua_chon_ve"] == "PENDING"
        d = await _don(pool, order)
        assert (d["selection_status"], d["execution_status"], d["room_id"]) == (
            "PENDING",
            "PENDING",
            phong,
        )
        huy = await pool.fetchval(
            "SELECT payload FROM domain_event WHERE aggregate_id = $1::uuid"
            " AND event_type = 'service.start_cancelled'",
            order,
        )
        assert json.loads(huy)["tra_lua_chon_ve"] == "PENDING"
        # Khách về lại hàng chờ của phòng; bắt đầu lại được (chốt hộ lần nữa).
        assert await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
            " AND reason = 'SERVICE' AND status NOT IN ('done', 'left', 'cancelled')",
            order,
        ) in ("waiting", "blocked")
        lai = await _bat_dau(pool, ca, order)
        assert lai["chot_lua_chon"] is True


async def test_khach_chon_khong_lam_thi_phong_khong_bat_dau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, False):
        ca = await _dung(pool)
        visit = await _luot_dieu_tri(pool, ca)
        order = await _chi_dinh_tu_sinh(pool, visit)
        await _nhan(pool, ca, visit, order)
        # Quầy ghi khách KHÔNG làm sau khi phòng đã nhận (trạng thái dựng tay).
        await pool.execute(
            "UPDATE service_order SET selection_status = 'NOT_SELECTED'"
            " WHERE id = $1::uuid",
            order,
        )
        with pytest.raises(LuotKhamConflictError) as e:
            await _bat_dau(pool, ca, order)
        assert e.value.error_code == "SELECTION_NOT_CONFIRMED"
        assert str(e.value) == CAU_KHACH_KHONG_CHON
        assert (await _don(pool, order))["selection_status"] == "NOT_SELECTED"


async def test_nhan_tai_phong_tat_chot_ho_h4_khong_xep_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """RỦI RO: chốt hộ phát `service_selection.confirmed`; dây Nhận tại phòng
    TẮT thì H4 (`tu_xep_da_thu`) nghe tin ấy. Chỉ định đã có phòng / đang làm
    không bị xếp lại — kể cả sau Huỷ bắt đầu."""
    async with day_thu_truoc(pool, False):
        ca = await _dung(pool)
        visit = await _luot_dieu_tri(pool, ca)
        order = await _chi_dinh_tu_sinh(pool, visit)
        phong = await _nhan(pool, ca, visit, order)
        async with (
            _day(pool, "nhan_tai_phong", False),
            _day(pool, "h4_tu_xep_phong", True),
        ):
            async with pool.acquire() as conn:
                assert await _tu_xep_bat(conn, CLINIC) is True
            truoc = await _don(pool, order)
            xep_truoc = await _so_su_kien(pool, "service.routed", order)

            bd = await _bat_dau(pool, ca, order)
            assert bd["chot_lua_chon"] is True
            await chay_hanh_trinh(pool)
            d = await _don(pool, order)
            assert (d["room_id"], d["routing_revision"]) == (
                phong,
                truoc["routing_revision"],
            )
            assert d["execution_status"] == "IN_PROGRESS"
            assert await _so_su_kien(pool, "service.routed", order) == xep_truoc

            await ServiceExecutionService(pool).huy_bat_dau(
                order_id=order,
                attempt_id=bd["attempt_id"],
                expected_execution_revision=bd["execution_revision"],
                identity=ca.dd,
                idempotency_key=_khoa(),
            )
            await chay_hanh_trinh(pool)
            d = await _don(pool, order)
            assert (d["room_id"], d["routing_revision"]) == (
                phong,
                truoc["routing_revision"],
            )
            assert await _so_su_kien(pool, "service.routed", order) == xep_truoc
