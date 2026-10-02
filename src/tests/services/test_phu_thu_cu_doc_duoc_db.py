"""Phụ thu CŨ còn đọc được sau khi gỡ khối "Món kèm" (C17, 02/10/2026).

Tuyền gỡ khối tick "Món kèm dịch vụ" (trùng "Mua thêm vật tư"). Dòng
`luot_phu_thu` đã tick từ trước KHÔNG bị xoá: còn nằm trong hoá đơn dịch vụ, thu
được, theo tick dịch vụ cha. Test chèn thẳng dòng cũ bằng SQL (không còn API tick).
"""

from __future__ import annotations

import uuid

import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_selection_service import ServiceSelectionService
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


async def _tick_cu(kb: BoKichBan, oid: str, mau: str, gia: int = 300_000) -> None:
    """Dòng phụ thu đã tick từ trước khi gỡ khối (không còn đường API)."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO public.luot_phu_thu (clinic_id, visit_id,"
            " service_order_id, phu_thu_mau_id, ten, don_gia)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'Đầu dò cũ', $5)",
            kb.bac_si.clinic_id,
            kb.visit_id,
            oid,
            mau,
            gia,
        )


async def _dong_phu_thu(kb: BoKichBan) -> list[dict[str, object]]:
    async with kb.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=kb.bac_si.clinic_id, visit_id=kb.visit_id, kind="dich_vu"
        )
    return [d for d in hd.cho_api()["dong"] if d["source_type"] == "phu_thu"]


async def _gan_loai_kham_co_gia(kb: BoKichBan) -> None:
    """Cho phép bài kiểm thu thật tập trung vào phụ thu, không vấp lỗi V2."""
    ma = f"KHAM-PHU-THU-{uuid.uuid4().hex[:8]}"
    ten = f"Khám phụ thu {uuid.uuid4().hex[:6]}"
    async with kb.pool.acquire() as conn:
        st = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, name, code)"
            " VALUES ($1::uuid, $2, $3) RETURNING id::text",
            kb.bac_si.clinic_id,
            ten,
            ma,
        )
        await conn.execute(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, active, billing_owner)"
            " VALUES ($1::uuid, $2, $3, 'dich_vu', 150000, true, 'CLINIC')",
            kb.bac_si.clinic_id,
            ma,
            ten,
        )
        await conn.execute(
            "UPDATE visit SET service_type_id = $1::uuid WHERE visit_id = $2::uuid",
            st,
            kb.visit_id,
        )


async def test_thu_tien_co_phu_thu_cu(kban: BoKichBan) -> None:  # noqa: F811
    await _gan_loai_kham_co_gia(kban)
    oid, mau = await _dich_vu_co_dau_do(kban)
    ai = await _thu_ngan(kban)
    await _tick_cu(kban, oid, mau)
    assert len(await _dong_phu_thu(kban)) == 1
    async with kban.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn,
            clinic_id=kban.bac_si.clinic_id,
            visit_id=kban.visit_id,
            kind="dich_vu",
        )
    kq = await PaymentService(kban.pool).record_payment(
        visit_id=kban.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ai,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=f"thu-phu-thu-{uuid.uuid4().hex}",
    )
    dong = await kban.pool.fetch(
        "SELECT source_type, source_id FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid ORDER BY source_type, source_id",
        kq["payment_cycle_id"],
    )
    assert ("service_order", oid) in {(r["source_type"], r["source_id"]) for r in dong}
    assert any(r["source_type"] == "phu_thu" for r in dong)


async def test_bo_dich_vu_cha_tu_bo_phu_thu_va_thu_duoc_phan_con_lai(
    kban: BoKichBan,  # noqa: F811
) -> None:
    await _gan_loai_kham_co_gia(kban)
    phien = await _bat_dau_kham_primary(kban)
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kban.ma_sa, kban.ma_mau_noi_bo],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    dau_do, con_lai = [str(i) for i in duyet["order_ids"]]
    cid = kban.bac_si.clinic_id
    async with kban.pool.acquire() as conn:
        mau = await conn.fetchval(
            "INSERT INTO phu_thu_mau (clinic_id, service_price_id, ten, gia_mac_dinh)"
            " SELECT $1::uuid, sp.id, $3, 300000 FROM service_price sp"
            " WHERE sp.clinic_id = $1::uuid AND sp.service_code = $2 AND sp.active"
            " LIMIT 1 RETURNING id::text",
            cid,
            kban.ma_sa,
            f"Đầu dò thử {uuid.uuid4().hex[:4]}",
        )
    assert mau is not None
    ai = await _thu_ngan(kban)
    await ServiceSelectionService(kban.pool).confirm(
        visit_id=kban.visit_id,
        order_ids_seen=[dau_do, con_lai],
        selected_order_ids=[dau_do, con_lai],
        expected_selection_revision=0,
        identity=ai,
        idempotency_key=f"chon-ca-hai-{uuid.uuid4().hex}",
    )
    await _tick_cu(kban, dau_do, str(mau))
    await ServiceSelectionService(kban.pool).confirm(
        visit_id=kban.visit_id,
        order_ids_seen=[dau_do, con_lai],
        selected_order_ids=[con_lai],
        expected_selection_revision=1,
        identity=ai,
        idempotency_key=f"bo-cha-{uuid.uuid4().hex}",
    )
    async with kban.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=cid, visit_id=kban.visit_id, kind="dich_vu"
        )
        active = await conn.fetchval(
            "SELECT count(*) FROM luot_phu_thu WHERE clinic_id = $1::uuid"
            " AND service_order_id = $2::uuid AND bo_luc IS NULL",
            cid,
            dau_do,
        )
    assert active == 0
    assert {d.source_id for d in hd.dong if d.source_type == "service_order"} == {
        con_lai
    }
    assert all(d.source_type != "phu_thu" for d in hd.dong)
    kq = await PaymentService(kban.pool).record_payment(
        visit_id=kban.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ai,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=f"thu-con-lai-{uuid.uuid4().hex}",
    )
    assert kq["status"] == "PAID"
