"""Thu tiền thuốc xong là giao luôn — trừ kho ngay lúc thu (16/11/2026).

Luật Tuyền chốt:
1. trừ QUẦY trước, lô hạn gần nhất;
2. quầy không đủ → phần còn lại TỰ trừ ở KHO, lô hạn gần nhất, không vào sổ chờ gán
   lô; dòng sổ ghi rõ "lấy từ kho", xem lại ở "Theo dõi thuốc";
3. cả hai thiếu → vẫn thu được, phần thiếu vào sổ chờ gán lô;
4. hoàn tác lần thu → mọi lô (quầy, kho) về đúng số cũ, phần chờ gán huỷ;
5. chuyển khoản: chờ xác minh thì CHƯA trừ, xác minh xong mới trừ.

Các bài có KHO chạy ở cơ sở riêng đã bật tách kho (`co` của test_kho_quay_db) —
KHÔNG import fixture tắt tự giao của tệp đó.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services import theo_doi_thuoc_service
from clinicai.services.kiem_ke_ca_service import xnt_theo_ca
from clinicai.services.lo_mau import LO_MAU_TIEN_TO
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import LY_DO_LAY_TU_KHO, PharmacyService
from clinicai.services.tu_giao_khi_thu import VI_TRI_LOI
from tests.services.test_kho_quay_db import (
    Co,
    _bat,
    _chuyen,
    _id_dich,
    _nhap_kho,
    co,  # noqa: F401
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    _thuoc,
    q,
    tao_quay,
)
from tests.services.test_tien_thuoc_cp3_db import _thu, _xac_minh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mặc định prod (Tuyền 20/09): thu không giữ chỗ lô.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _chuan_bi(q: Quay, ke: int, ton: int) -> tuple[str, str]:  # noqa: F811
    rx = await _don(q, ke)
    thuoc = await _thuoc(q)
    svc = PharmacyService(q.pool)
    await svc.xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=thuoc
    )
    lo = ""
    if ton:
        kq = await svc.nhap_lo(
            identity=q.duoc_si,
            drug_catalog_id=thuoc,
            so_luong=ton,
            batch_code=f"LO-{uuid.uuid4().hex[:8]}",
            expiry_date=hom_nay_vn() + timedelta(days=400),
            unit="viên",
        )
        lo = str(kq["drug_batch_id"])
    return rx, lo


async def _ton(q: Quay, lo: str) -> Decimal:  # noqa: F811
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
            )
        )
    )


async def _da_giao(q: Quay, rx: str) -> Decimal:  # noqa: F811
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT coalesce(dispensed_qty, 0) FROM prescription"
                " WHERE id = $1::uuid",
                rx,
            )
        )
    )


async def _cho(pool: asyncpg.Pool, rx: str) -> Decimal:
    return Decimal(
        str(
            await pool.fetchval(
                "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo"
                " WHERE prescription_id = $1::uuid AND huy_luc IS NULL"
                " AND drug_batch_id IS NULL",
                rx,
            )
        )
    )


async def _huy(q: Quay, cycle: str) -> None:  # noqa: F811
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Khách đổi ý",
        identity=q.thu_ngan,
    )


# ── Chưa tách kho (cơ sở chung của `q`): mọi lô ở QUẦY, như trước ─────────


async def test_thu_tien_mat_tru_kho_ngay_hoan_tac_tra_ve(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=30)
    kq = await _thu(q)
    assert await _da_giao(q, rx) == 10
    assert await _ton(q, lo) == 20

    await _huy(q, kq["payment_cycle_id"])
    assert await _da_giao(q, rx) == 0
    assert await _ton(q, lo) == 30  # về quầy, không trừ lố


async def test_chuyen_khoan_chi_tru_khi_xac_minh(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=5, ton=30)
    kq = await _thu(q, "TRANSFER")
    assert kq["status"] == "PENDING_VERIFICATION"
    assert await _ton(q, lo) == 30
    await _xac_minh(q, kq["payment_cycle_id"])
    assert await _da_giao(q, rx) == 5
    assert await _ton(q, lo) == 25


async def test_chua_tach_kho_thieu_ton_van_thu_phan_thieu_cho_gan(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=4)
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    assert await _da_giao(q, rx) == 10
    assert await _ton(q, lo) == 0
    assert await _cho(q.pool, rx) == 6

    # Hoàn tác lần thu: 4 viên về lô, 6 viên chờ gán lô huỷ — không trừ lố.
    await _huy(q, kq["payment_cycle_id"])
    assert await _ton(q, lo) == 4
    assert await _da_giao(q, rx) == 0
    assert await _cho(q.pool, rx) == 0


async def test_khach_mua_bot_chi_tru_so_mua(q: Quay) -> None:  # noqa: F811
    rx, lo = await _chuan_bi(q, ke=10, ton=30)
    await q.pool.execute(
        "UPDATE prescription SET purchased_qty = 4 WHERE id = $1::uuid", rx
    )
    await _thu(q)
    assert await _da_giao(q, rx) == 4
    assert await _ton(q, lo) == 26


# ── Đã tách kho: quầy trước, kho sau, rồi mới chờ gán ────────────────────


async def _rx(co: Co, thuoc: str, so: int) -> str:  # noqa: F811
    rx = await _don(co.q, so)
    await PharmacyService(co.q.pool).xac_dinh_thuoc(
        identity=co.ds, prescription_id=rx, drug_catalog_id=thuoc
    )
    return rx


async def _ton_lo(co: Co, *lo: str) -> list[Decimal]:  # noqa: F811
    return [await _ton(co.q, x) for x in lo]


async def _giao_cua(pool: asyncpg.Pool, rx: str) -> list[dict[str, Any]]:
    """Các dòng DISPENSE còn hiệu lực của dòng đơn: lô, nơi, số, lý do."""
    return [
        dict(r)
        for r in await pool.fetch(
            "SELECT t.drug_batch_id::text AS lo, b.noi_chua, -t.quantity AS so,"
            " t.reason FROM inventory_txn t JOIN drug_batch b"
            " ON b.id = t.drug_batch_id WHERE t.ref_id = $1::uuid"
            " AND t.txn_type = 'DISPENSE' AND NOT EXISTS (SELECT 1 FROM"
            " inventory_txn x WHERE x.reverses_txn_id = t.id)"
            " ORDER BY t.performed_at, b.noi_chua DESC, b.expiry_date",
            rx,
        )
    ]


async def _san_kho(co: Co, so: int, han: int = 900) -> tuple[str, str]:  # noqa: F811
    """Bật tách kho ở cơ sở riêng, nhập `so` viên vào KHO. Trả (thuốc, lô kho)."""
    await _bat(co)
    thuoc = await _thuoc(co.q)
    lo = await _nhap_kho(co, thuoc, so, han=hom_nay_vn() + timedelta(days=han))
    return thuoc, lo


async def test_a_quay_du_chi_tru_quay(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 50)
    quay = _id_dich(await _chuyen(co, kho, 20))
    rx = await _rx(co, thuoc, 10)
    kq = await _thu(co.q)
    assert kq["status"] == "PAID"
    assert await _ton_lo(co, quay, kho) == [10, 30]
    assert await _cho(co.q.pool, rx) == 0
    assert [g["reason"] for g in await _giao_cua(co.q.pool, rx)] == [None]

    await _huy(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, quay, kho) == [20, 30]
    assert await _da_giao(co.q, rx) == 0


async def test_b_quay_thieu_lay_tiep_o_kho_lo_han_gan_nhat(co: Co) -> None:  # noqa: F811
    thuoc, kho_xa = await _san_kho(co, 50, han=900)
    kho_gan = await _nhap_kho(co, thuoc, 50, han=hom_nay_vn() + timedelta(days=100))
    # Lô quầy hạn XA hơn lô kho gần — quầy vẫn trừ trước.
    quay = _id_dich(await _chuyen(co, kho_xa, 4))
    rx = await _rx(co, thuoc, 10)
    tu = datetime.now(CLINIC_TZ) - timedelta(minutes=5)
    kq = await _thu(co.q)
    assert kq["status"] == "PAID"
    assert await _da_giao(co.q, rx) == 10
    assert await _ton_lo(co, quay, kho_gan, kho_xa) == [0, 44, 46]
    assert await _cho(co.q.pool, rx) == 0  # không vào sổ chờ gán lô
    giao = await _giao_cua(co.q.pool, rx)
    assert [(g["lo"], g["noi_chua"], g["so"], g["reason"]) for g in giao] == [
        (quay, "QUAY", 4, None),
        (kho_gan, "KHO", 6, LY_DO_LAY_TU_KHO),
    ]

    # Xem lại được: "Theo dõi thuốc" có dòng Kho → Khách, đúng lô, khách, lý do.
    td = await theo_doi_thuoc_service.theo_doi_thuoc(
        co.q.pool, identity=co.ds, thuoc=thuoc, noi="KHO", hanh_dong="DISPENSE"
    )
    (d,) = td["dong"]
    assert (d["tu"], d["den"], d["so_lo"], d["so_luong"]) == (
        "Kho",
        "Khách",
        (
            await co.q.pool.fetchval(
                "SELECT batch_code FROM drug_batch WHERE id = $1::uuid", kho_gan
            )
        ),
        -6,
    )
    assert d["khach"] == "BN thử tiền thuốc" and d["ly_do"] == LY_DO_LAY_TU_KHO

    # Kiểm ca quầy: SL bán chỉ phần quầy (4), tồn cuối quầy 0 — không trừ 2 lần.
    xnt = await xnt_theo_ca(
        co.q.pool,
        clinic_id=CLINIC,
        location_id=co.loc,
        tu=tu,
        den=datetime.now(CLINIC_TZ) + timedelta(minutes=5),
    )
    (dong,) = [r for r in xnt if r["drug_catalog_id"] == thuoc]
    assert (dong["ban"], dong["ton_cuoi"], dong["nhap"]) == (4, 0, 4)

    await _huy(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, quay, kho_gan, kho_xa) == [4, 50, 46]
    assert await _da_giao(co.q, rx) == 0
    assert await _giao_cua(co.q.pool, rx) == []
    # Hàng kho về vẫn ở KHO, không thành hàng quầy.
    assert (
        await co.q.pool.fetchval(
            "SELECT noi_chua FROM drug_batch WHERE id = $1::uuid", kho_gan
        )
        == "KHO"
    )


async def test_c_quay_het_kho_du(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 30)
    rx = await _rx(co, thuoc, 10)
    kq = await _thu(co.q)
    assert await _ton_lo(co, kho) == [20]
    assert await _cho(co.q.pool, rx) == 0
    assert await _da_giao(co.q, rx) == 10

    await _huy(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, kho) == [30]
    assert await _da_giao(co.q, rx) == 0


async def test_d_quay_va_kho_deu_thieu_van_thu_phan_thieu_cho_gan(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 5)
    quay = _id_dich(await _chuyen(co, kho, 2))
    rx = await _rx(co, thuoc, 10)
    kq = await _thu(co.q)
    assert kq["status"] == "PAID"
    assert await _da_giao(co.q, rx) == 10
    assert await _ton_lo(co, quay, kho) == [0, 0]
    assert await _cho(co.q.pool, rx) == 5

    await _huy(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, quay, kho) == [2, 3]
    assert await _cho(co.q.pool, rx) == 0
    assert await _da_giao(co.q, rx) == 0


async def test_h_lo_kho_het_han_khong_bi_lay(co: Co) -> None:  # noqa: F811
    thuoc, het = await _san_kho(co, 50)
    con_han = await _nhap_kho(co, thuoc, 50, han=hom_nay_vn() + timedelta(days=500))
    await co.q.pool.execute(
        "UPDATE drug_batch SET expiry_date = $2 WHERE id = $1::uuid",
        het,
        hom_nay_vn() - timedelta(days=1),
    )
    rx = await _rx(co, thuoc, 10)
    await _thu(co.q)
    assert await _ton_lo(co, het, con_han) == [50, 40]
    # Chốt ở DB: kể cả mang dấu "lấy từ kho", lô kho hết hạn không ghi giao được.
    with pytest.raises(asyncpg.PostgresError, match="đang ở KHO"):
        await co.q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " reason, ref_type, ref_id, performed_by_staff_id)"
            " VALUES ($1::uuid, $2::uuid, 'DISPENSE', -1, $3, 'prescription',"
            " $4::uuid, $5::uuid)",
            CLINIC,
            het,
            LY_DO_LAY_TU_KHO,
            rx,
            co.ds.staff_id,
        )


async def test_lo_mau_demo_khong_bao_gio_bi_tu_tru(co: Co) -> None:  # noqa: F811
    # Prod 19/11: 80 lô mẫu DEMO1709-* còn tồn ở KHO (Hào Nam) và QUẦY (Kim Ngưu).
    # Lô mẫu hạn GẦN hơn, lại có ở quầy — FEFO mà không loại thì trừ nhầm vào nó.
    thuoc, mau_kho = await _san_kho(co, 50, han=100)
    await co.q.pool.execute(
        "UPDATE drug_batch SET batch_code = $2 WHERE id = $1::uuid",
        mau_kho,
        f"{LO_MAU_TIEN_TO}{uuid.uuid4().hex[:6]}",
    )
    mau_quay = _id_dich(await _chuyen(co, mau_kho, 10))
    that = await _nhap_kho(co, thuoc, 30, han=hom_nay_vn() + timedelta(days=900))
    rx = await _rx(co, thuoc, 10)
    kq = await _thu(co.q)
    assert kq["status"] == "PAID"
    assert await _ton_lo(co, mau_quay, mau_kho, that) == [10, 40, 20]
    assert await _cho(co.q.pool, rx) == 0


async def test_chot_db_dau_kho_chua_thu_tien_bi_chan(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 50)
    rx = await _rx(co, thuoc, 3)
    with pytest.raises(asyncpg.PostgresError, match="đang ở KHO"):
        await co.q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " reason, ref_type, ref_id, performed_by_staff_id)"
            " VALUES ($1::uuid, $2::uuid, 'DISPENSE', -1, $3, 'prescription',"
            " $4::uuid, $5::uuid)",
            CLINIC,
            kho,
            LY_DO_LAY_TU_KHO,
            rx,
            co.ds.staff_id,
        )
    assert await _ton_lo(co, kho) == [50]


async def test_i_chuyen_khoan_co_kho_chi_tru_khi_xac_minh(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 30)
    quay = _id_dich(await _chuyen(co, kho, 2))
    rx = await _rx(co, thuoc, 5)
    kq = await _thu(co.q, "TRANSFER")
    assert kq["status"] == "PENDING_VERIFICATION"
    assert await _ton_lo(co, quay, kho) == [2, 28]
    await _xac_minh(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, quay, kho) == [0, 25]
    assert await _cho(co.q.pool, rx) == 0


async def test_g_chua_tach_kho_fefo_tren_quay_nhu_cu(co: Co) -> None:  # noqa: F811
    # Không bật tách: nhập lô vào QUẦY như cũ.
    thuoc = await _thuoc(co.q)
    xa = await _nhap_kho(co, thuoc, 3, han=hom_nay_vn() + timedelta(days=900))
    gan = await _nhap_kho(co, thuoc, 4, han=hom_nay_vn() + timedelta(days=100))
    assert {
        r["noi_chua"]
        for r in await co.q.pool.fetch(
            "SELECT noi_chua FROM drug_batch WHERE id = ANY($1::uuid[])", [xa, gan]
        )
    } == {"QUAY"}
    # Một hàng KHO còn tồn (dữ liệu cũ) ở cơ sở CHƯA tách: không được đụng tới.
    kho = await _nhap_kho(co, thuoc, 50)
    await co.q.pool.execute(
        "UPDATE drug_batch SET noi_chua = 'KHO' WHERE id = $1::uuid", kho
    )
    rx = await _rx(co, thuoc, 10)
    kq = await _thu(co.q)
    assert await _ton_lo(co, gan, xa, kho) == [0, 0, 50]
    assert [g["reason"] for g in await _giao_cua(co.q.pool, rx)] == [None, None]
    assert await _cho(co.q.pool, rx) == 3  # như cũ: quầy thiếu → chờ gán
    await _huy(co.q, kq["payment_cycle_id"])
    assert await _ton_lo(co, gan, xa, kho) == [4, 3, 50]
    assert await _cho(co.q.pool, rx) == 0


async def test_thu_hai_thuoc_khi_ben_khac_khoa_nguoc_khong_mat_dau(co: Co) -> None:  # noqa: F811
    """Lần thu hai thuốc A, B khoá mọi lô MỘT lần theo id. Một giao dịch khác khoá
    lô id lớn rồi lô id nhỏ (ngược thứ tự). Nếu Postgres huỷ phía lần thu vì
    deadlock: lần thu vẫn PAID, hai dòng hiện ở `tu_giao_bo_qua`, kho lỗi có dòng,
    tồn không đổi. Nếu huỷ phía bên kia: giao đủ cả hai."""
    pool = co.q.pool
    a, b = await _thuoc(co.q), await _thuoc(co.q, ten=f"Thuốc B {co.q.duoi}")
    lo_a = await _nhap_kho(co, a, 20)
    lo_b = await _nhap_kho(co, b, 20)
    rx_a, rx_b = await _rx(co, a, 3), await _rx(co, b, 4)
    nho, lon = sorted([lo_a, lo_b])
    truoc = await pool.fetchval(
        "SELECT coalesce(sum(so_lan), 0) FROM loi_nhom WHERE vi_tri = $1",
        VI_TRI_LOI,
    )

    async with pool.acquire() as khac:
        tr = khac.transaction()
        await tr.start()
        try:
            await khac.execute(
                "SELECT 1 FROM drug_batch WHERE id = $1::uuid FOR UPDATE", lon
            )
            thu = asyncio.create_task(_thu(co.q))
            await asyncio.sleep(0.4)  # lần thu đã giữ lô nhỏ, đang chờ lô lớn
            await khac.execute(
                "SELECT 1 FROM drug_batch WHERE id = $1::uuid FOR UPDATE", nho
            )
        except asyncpg.DeadlockDetectedError:
            pass  # Postgres huỷ phía bên kia — lần thu giao đủ
        finally:
            await tr.rollback()
        kq = await asyncio.wait_for(thu, timeout=30)

    assert kq["status"] == "PAID"
    giao = (await _da_giao(co.q, rx_a), await _da_giao(co.q, rx_b))
    if not kq["tu_giao_bo_qua"]:
        assert giao == (Decimal(3), Decimal(4))
        assert await _ton_lo(co, lo_a, lo_b) == [17, 16]
        return
    assert giao == (Decimal(0), Decimal(0))
    assert await _ton_lo(co, lo_a, lo_b) == [20, 20]
    assert {x["prescription_id"] for x in kq["tu_giao_bo_qua"]} == {rx_a, rx_b}
    sau = await pool.fetchval(
        "SELECT coalesce(sum(so_lan), 0) FROM loi_nhom WHERE vi_tri = $1",
        VI_TRI_LOI,
    )
    assert sau == truoc + 1
    # Bấm Giao sau đó vẫn giao được.
    await PharmacyService(pool).cap_phat(
        identity=co.ds, prescription_id=rx_a, drug_batch_id=None, so_luong=3
    )
    assert await _ton_lo(co, lo_a) == [17]


async def test_f_hai_lan_thu_cung_luc_tranh_lo_kho_cuoi(co: Co) -> None:  # noqa: F811
    thuoc, kho = await _san_kho(co, 12)
    q2 = await tao_quay(co.q.pool)
    await co.q.pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        q2.visit_id,
        co.loc,
    )
    rx1 = await _rx(co, thuoc, 10)
    rx2 = await _don(q2, 10)
    await PharmacyService(co.q.pool).xac_dinh_thuoc(
        identity=co.ds, prescription_id=rx2, drug_catalog_id=thuoc
    )
    k1, k2 = await asyncio.gather(_thu(co.q), _thu(q2))
    assert k1["status"] == k2["status"] == "PAID"
    assert await _ton_lo(co, kho) == [0]  # không âm
    tru = Decimal(0)
    for rx in (rx1, rx2):
        tru += sum((g["so"] for g in await _giao_cua(co.q.pool, rx)), Decimal(0))
    cho = await _cho(co.q.pool, rx1) + await _cho(co.q.pool, rx2)
    assert (tru, cho) == (Decimal(12), Decimal(8))
    assert await _da_giao(co.q, rx1) + await _da_giao(co.q, rx2) == 20


# ── Tiền KHÔNG đổi theo công tắc tự giao ─────────────────────────────────


async def _tien(q: Quay, cycle: str) -> dict[str, Any]:  # noqa: F811
    lan = await q.pool.fetchrow(
        "SELECT status, amount, method FROM payment_cycle"
        " WHERE payment_cycle_id = $1::uuid",
        cycle,
    )
    dong = await q.pool.fetch(
        "SELECT kind, source_type, quantity, unit, unit_price, line_total,"
        " billing_owner FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " ORDER BY name_snapshot, quantity",
        cycle,
    )
    tt = await q.pool.fetch(
        "SELECT kind, status, amount FROM payment WHERE visit_id = $1::uuid"
        " ORDER BY created_at, amount",
        q.visit_id,
    )
    return {
        "lan": dict(lan),
        "dong": [dict(r) for r in dong],
        "payment": [dict(r) for r in tt],
    }


async def _kich_ban_tien(pool: asyncpg.Pool, method: str) -> list[dict[str, Any]]:
    q = await tao_quay(pool)  # noqa: F811
    rx1, _ = await _chuan_bi(q, ke=10, ton=6)  # thiếu tồn → một phần chờ gán
    rx2 = await _don(q, 8, ten="thuoc thu hai")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si,
        prescription_id=rx2,
        drug_catalog_id=await _thuoc(q, 7_000, f"Thuốc hai {q.duoi}"),
    )
    await q.pool.execute(
        "UPDATE prescription SET purchased_qty = 3 WHERE id = $1::uuid", rx2
    )
    kq = await _thu(q, method)
    if method == "TRANSFER":
        await _xac_minh(q, kq["payment_cycle_id"])
    sau_thu = await _tien(q, kq["payment_cycle_id"])
    await _huy(q, kq["payment_cycle_id"])
    sau_huy = await _tien(q, kq["payment_cycle_id"])
    return [sau_thu, sau_huy]


@pytest.mark.parametrize("method", ["CASH", "TRANSFER"])
async def test_tien_giong_het_khi_bat_tat_tu_giao(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    monkeypatch.setenv("CLINICAI_TU_GIAO_KHI_THU", "0")
    tat = await _kich_ban_tien(pool, method)
    monkeypatch.setenv("CLINICAI_TU_GIAO_KHI_THU", "1")
    bat = await _kich_ban_tien(pool, method)
    assert bat == tat
    assert tat[0]["lan"]["status"] == "PAID" and tat[0]["lan"]["amount"] == 71_000
