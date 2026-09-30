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
from clinicai.services.payment_service import PaymentService
from clinicai.services.phu_thu_service import PhuThuService
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


async def test_thu_tien_co_phu_thu(kban: BoKichBan) -> None:  # noqa: F811
    await _gan_loai_kham_co_gia(kban)
    oid, mau = await _dich_vu_co_dau_do(kban)
    ai = await _thu_ngan(kban)
    await PhuThuService(kban.pool).dat(
        order_id=oid, mau_id=mau, chon=True, don_gia=300_000, identity=ai
    )
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
    await PhuThuService(kban.pool).dat(
        order_id=dau_do, mau_id=str(mau), chon=True, don_gia=300_000, identity=ai
    )
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


async def test_dat_lai_cung_gia_khong_doi_revision_hoac_ghi_them(
    kban: BoKichBan,  # noqa: F811
) -> None:
    oid, mau = await _dich_vu_co_dau_do(kban)
    ai = await _thu_ngan(kban)
    svc = PhuThuService(kban.pool)
    await svc.dat(order_id=oid, mau_id=mau, chon=True, don_gia=300_000, identity=ai)
    async with kban.pool.acquire() as conn:
        truoc = await tinh_hoa_don(
            conn,
            clinic_id=kban.bac_si.clinic_id,
            visit_id=kban.visit_id,
            kind="dich_vu",
        )
        dong_truoc = await conn.fetchval(
            "SELECT id::text FROM luot_phu_thu WHERE service_order_id = $1::uuid"
            " AND phu_thu_mau_id = $2::uuid AND bo_luc IS NULL",
            oid,
            mau,
        )
        event_truoc = await conn.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1"
            " AND event_type = 'visit.surcharge_set'",
            oid,
        )
    await svc.dat(order_id=oid, mau_id=mau, chon=True, don_gia="300.000", identity=ai)
    async with kban.pool.acquire() as conn:
        sau = await tinh_hoa_don(
            conn,
            clinic_id=kban.bac_si.clinic_id,
            visit_id=kban.visit_id,
            kind="dich_vu",
        )
        dong_sau = await conn.fetchval(
            "SELECT id::text FROM luot_phu_thu WHERE service_order_id = $1::uuid"
            " AND phu_thu_mau_id = $2::uuid AND bo_luc IS NULL",
            oid,
            mau,
        )
        event_sau = await conn.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1"
            " AND event_type = 'visit.surcharge_set'",
            oid,
        )
    assert sau.revision == truoc.revision
    assert dong_sau == dong_truoc
    assert event_sau == event_truoc
