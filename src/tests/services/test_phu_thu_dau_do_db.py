"""Món kèm dịch vụ (đầu dò) — tick + sửa giá ở thu tiền dịch vụ (28/09/2026).

Tuyền: "thêm ô tick vào thu dịch vụ là thêm đầu dò và điền được giá vào". Tick
→ dòng `phu_thu` trong hoá đơn DỊCH VỤ đúng giá chốt; sửa giá → hoá đơn đổi
theo; bỏ tick → mất khỏi hoá đơn; món không thuộc dịch vụ → từ chối.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.phu_thu_service import PhuThuService
from tests.services.test_full_chi_dinh_slice_ab_db import (
    BoKichBan,
    _bat_dau_kham_primary,
    _tao_nhan_vien,
    kban,  # noqa: F401
)


async def _thu_ngan(kb: BoKichBan) -> StaffIdentity:
    async with kb.pool.acquire() as conn:
        return await _tao_nhan_vien(
            conn, kb.bac_si.clinic_id, kb.location_id, "CASHIER"
        )


pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dich_vu_co_dau_do(kb: BoKichBan) -> tuple[str, str]:
    """Chỉ định dịch vụ `ma_sa` (đã chọn) + món kèm "Đầu dò thử" 300k."""
    phien = await _bat_dau_kham_primary(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    oid = str(duyet["order_ids"][0])
    cid = kb.bac_si.clinic_id
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_order SET selection_status = 'SELECTED'"
            " WHERE id = $1::uuid",
            oid,
        )
        mau = await conn.fetchval(
            "INSERT INTO phu_thu_mau (clinic_id, service_price_id, ten, gia_mac_dinh)"
            " SELECT $1::uuid, sp.id, $3, 300000 FROM service_price sp"
            " WHERE sp.clinic_id = $1::uuid AND sp.service_code = $2 AND sp.active"
            " LIMIT 1 RETURNING id::text",
            cid,
            kb.ma_sa,
            f"Đầu dò thử {uuid.uuid4().hex[:4]}",
        )
    assert mau is not None
    return oid, str(mau)


async def _dong_phu_thu(kb: BoKichBan) -> list[dict[str, object]]:
    async with kb.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=kb.bac_si.clinic_id, visit_id=kb.visit_id, kind="dich_vu"
        )
    return [d for d in hd.cho_api()["dong"] if d["source_type"] == "phu_thu"]


async def test_tick_sua_gia_bo_tick_dau_do(kban: BoKichBan) -> None:  # noqa: F811
    oid, mau = await _dich_vu_co_dau_do(kban)
    svc = PhuThuService(kban.pool)
    ai = await _thu_ngan(kban)
    await svc.dat(order_id=oid, mau_id=mau, chon=True, don_gia=None, identity=ai)
    dong = await _dong_phu_thu(kban)
    assert len(dong) == 1 and Decimal(str(dong[0]["don_gia"])) == 300000
    # Sửa giá tại quầy → hoá đơn theo giá mới.
    await svc.dat(order_id=oid, mau_id=mau, chon=True, don_gia="250.000", identity=ai)
    dong = await _dong_phu_thu(kban)
    assert len(dong) == 1 and Decimal(str(dong[0]["don_gia"])) == 250000
    # Bỏ tick → không còn trong hoá đơn.
    await svc.dat(order_id=oid, mau_id=mau, chon=False, don_gia=None, identity=ai)
    assert await _dong_phu_thu(kban) == []


async def test_mon_khong_thuoc_dich_vu_bi_tu_choi(kban: BoKichBan) -> None:  # noqa: F811
    oid, _mau = await _dich_vu_co_dau_do(kban)
    with pytest.raises(ValidationError):
        await PhuThuService(kban.pool).dat(
            order_id=oid,
            mau_id=str(uuid.uuid4()),
            chon=True,
            don_gia=None,
            identity=await _thu_ngan(kban),
        )
