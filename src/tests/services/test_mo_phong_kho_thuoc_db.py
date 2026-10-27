"""Bước 0 G3a: service thật trên main, 40 hạt giống × 10 thao tác.

Hai bài cuối theo quyết định Tuyền 14/10: giữ giao trước/gán lô sau và
phiếu kiểm kho KiotViet điều chỉnh ngay khi lưu.
Main chưa có chuyển kho/quầy hay phiếu kiểm nháp: không giả lập bằng SQL.
SQL chỉ dựng fixture/đọc sổ; mọi thay đổi tồn đều gọi service thật.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q được import từ CP1.
import random
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import _dong_nhap, _phieu_nhap
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _ton(q: Quay, lo: str) -> Decimal:
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
            )
        )
    )


async def _bat_bien(q: Quay, drug: str, rx: str, trace: tuple[str, ...]) -> None:
    rows = await q.pool.fetch(
        "SELECT b.id::text, b.quantity_on_hand, coalesce(sum(t.quantity) FILTER "
        "(WHERE t.txn_type = ANY($2::text[])), 0) AS so "
        "FROM drug_batch b LEFT JOIN inventory_txn t ON t.drug_batch_id = b.id "
        "WHERE b.drug_catalog_id = $1::uuid GROUP BY b.id",
        drug,
        list(kho.LOAI_VAT_LY),
    )
    for r in rows:
        assert r["quantity_on_hand"] == r["so"], (r, trace)
        assert r["quantity_on_hand"] >= 0, (r, trace)
    giao = await q.pool.fetchval(
        "SELECT dispensed_qty FROM prescription WHERE id = $1::uuid", rx
    )
    so_giao = await q.pool.fetchval(
        "SELECT coalesce(sum(-quantity), 0) FROM inventory_txn "
        "WHERE ref_id = $1::uuid AND txn_type = 'DISPENSE'",
        rx,
    )
    chua_gan = await q.pool.fetchval(
        "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo "
        "WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL",
        rx,
    )
    assert giao == so_giao + chua_gan, (giao, so_giao, chua_gan, trace)


@pytest.mark.parametrize("seed", range(40))
async def test_bam_ngau_nhien_40_luot_10_buoc(q: Quay, seed: int) -> None:
    rng = random.Random(seed)
    svc = PharmacyService(q.pool)
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    khac = await _nhap_lo(q, drug, 100)
    await _thu(q)
    trace: tuple[str, ...] = ()
    for buoc in range(10):
        lenh = rng.choice(
            ("nhap", "huy", "kiem", "dieu_chinh", "hoan_tac", "giao", "tra")
        )
        chon = rng.choice((lo, khac))
        luong = rng.randint(1, 3)
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh} lo={chon} so={luong}")
        truoc = await _ton(q, chon)
        try:
            if lenh == "nhap":
                await _phieu_nhap(q, [{**_dong_nhap(drug, luong), "unit": "viên"}])
            elif lenh == "huy":
                await svc.huy(
                    identity=q.duoc_si,
                    drug_batch_id=chon,
                    so_luong=luong,
                    ly_do="Mô phỏng hỏng",
                )
                assert await _ton(q, chon) == truoc - luong, trace
            elif lenh == "giao":
                await svc.cap_phat(
                    identity=q.duoc_si,
                    prescription_id=rx,
                    drug_batch_id=chon,
                    so_luong=1,
                )
                assert await _ton(q, chon) == truoc - 1, trace
            elif lenh == "tra":
                xuat = await q.pool.fetchval(
                    "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id = $1::uuid "
                    "AND t.txn_type = 'DISPENSE' AND NOT EXISTS "
                    "(SELECT 1 FROM drug_return r "
                    "WHERE r.original_dispense_txn_id = t.id) "
                    "ORDER BY t.performed_at LIMIT 1",
                    rx,
                )
                if xuat is None:
                    await svc.cap_phat(
                        identity=q.duoc_si,
                        prescription_id=rx,
                        drug_batch_id=chon,
                        so_luong=1,
                    )
                    trace = (*trace, "tra: chưa giao -> giao 1 trước")
                else:
                    await svc.khach_tra_thuoc(
                        identity=q.duoc_si,
                        dispense_txn_id=xuat,
                        so_luong=1,
                        ly_do="Khách trả mô phỏng",
                        ket_cuc_tien="GIU_LAI",
                        ly_do_tien="Mô phỏng kho — tiền giữ lại",
                    )
            elif lenh == "kiem":
                kq = await kho.kiem_kho(
                    q.pool,
                    identity=q.duoc_si,
                    khoa_gui=uuid.uuid4().hex,
                    dong=[{"drug_batch_id": chon, "thuc_te": truoc - luong}],
                )
                assert kq["dong"][0]["lech"] == -luong, trace
                assert kq["dong"][0]["ton_may"] == truoc, trace
                assert await _ton(q, chon) == truoc - luong, trace
            else:
                await svc.dieu_chinh(
                    identity=q.duoc_si,
                    drug_batch_id=chon,
                    so_luong=luong,
                    ly_do="Điều chỉnh mô phỏng",
                )
                if lenh == "hoan_tac":
                    await svc.dieu_chinh(
                        identity=q.duoc_si,
                        drug_batch_id=chon,
                        so_luong=-luong,
                        ly_do="Đảo điều chỉnh mô phỏng",
                    )
                    assert await _ton(q, chon) == truoc, trace
            await _bat_bien(q, drug, rx, trace)
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")


async def test_lo_het_han_khong_giao_hoac_gan_lo(q: Quay) -> None:
    svc = PharmacyService(q.pool)
    rx, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20, han=hom_nay_vn() - timedelta(days=1))
    await _thu(q)
    with pytest.raises(ConflictError, match="hết hạn"):
        await svc.cap_phat(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
        )
    assert await _ton(q, lo) == 20
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE ref_id = $1::uuid "
            "AND txn_type = 'DISPENSE'",
            rx,
        )
        == 0
    )
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=1
    )
    dong = await q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id = $1::uuid",
        rx,
    )
    with pytest.raises(ConflictError, match="hết hạn"):
        await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong, drug_batch_id=lo)
    assert await _ton(q, lo) == 20
    assert (
        await q.pool.fetchval(
            "SELECT drug_batch_id FROM thuoc_giao_chua_gan_lo WHERE id = $1::uuid", dong
        )
        is None
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE ref_id = $1::uuid "
            "AND txn_type = 'DISPENSE'",
            rx,
        )
        == 0
    )


async def test_bat_bien_giao_chua_gan_lo_va_gan_sau(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 3)
    await _thu(q)
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=3
    )  # kho chưa có lô → chờ gán lô
    lo = await _nhap_lo(q, drug, 20)
    lo_khac = await _nhap_lo(q, drug, 10)
    await _bat_bien(q, drug, rx, ("nhap20", "thu3", "giao3 khong lo"))
    dong = await q.pool.fetchrow(
        "SELECT id::text, so_luong FROM thuoc_giao_chua_gan_lo "
        "WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL",
        rx,
    )
    assert dong is not None
    ton_so = await q.pool.fetchval(
        "SELECT sum(quantity_on_hand) FROM drug_batch WHERE drug_catalog_id = $1::uuid",
        drug,
    )
    # Tồn vật lý theo hành trình độc lập: nhập30, khách nhận3 -> còn27.
    assert ton_so - dong["so_luong"] == 27
    assert await _ton(q, lo) == 20
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
    )
    await _bat_bien(q, drug, rx, ("giao3 khong lo", "gan3 vao lo20"))
    assert await _ton(q, lo) == 17
    assert await _ton(q, lo_khac) == 10
    [txn] = await q.pool.fetch(
        "SELECT drug_batch_id::text, quantity FROM inventory_txn "
        "WHERE ref_id = $1::uuid AND txn_type = 'DISPENSE'",
        rx,
    )
    assert (txn["drug_batch_id"], txn["quantity"]) == (lo, -3)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM thuoc_giao_chua_gan_lo "
            "WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL",
            rx,
        )
        == 0
    )


async def test_bat_bien_kiem_kho_cu_dieu_chinh_ngay(q: Quay) -> None:
    _, drug = await _dong_da_xac_dinh(q, 3)
    lo = await _nhap_lo(q, drug, 20)
    kq = await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo, "thuc_te": 30}],
    )
    assert kq["dong"][0]["lech"] == 10
    assert kq["dong"][0]["ton_may"] == 20
    assert await _ton(q, lo) == 30
    [txn] = await q.pool.fetch(
        "SELECT drug_batch_id::text, quantity FROM inventory_txn "
        "WHERE ref_id = $1::uuid AND txn_type = 'ADJUST'",
        kq["id"],
    )
    assert (txn["drug_batch_id"], txn["quantity"]) == (lo, 10)
    [dong] = await q.pool.fetch(
        "SELECT d.ton_may, d.thuc_te, d.lech, t.quantity FROM phieu_kho_dong d "
        "JOIN inventory_txn t ON t.id = d.inventory_txn_id "
        "WHERE d.phieu_kho_id = $1::uuid",
        kq["id"],
    )
    assert dong["quantity"] == dong["lech"] == dong["thuc_te"] - dong["ton_may"]
