"""Khu 1 — ĐỐI CHIẾU ĐỘC LẬP báo cáo kho thuốc (XNT quầy) với sổ gốc `inventory_txn`.

VÌ SAO CÓ FILE NÀY. `test_kiem_ke_ca_db` đã kiểm đẳng thức "tồn cuối = đầu + nhập −
bán + trả + khác" và có một case vàng tính tay, nhưng đẳng thức ấy là phép tính trên
CHÍNH các cột báo cáo trả ra — một cột bị phân loại sai (vd. huỷ lọt vào "bán") mà
tổng vẫn cộng đúng thì nó không thấy. Ở đây đáp án được tính LẠI từ sổ gốc bằng Python
(không dùng SQL dựng ngược từ tồn hiện tại của `xnt_theo_ca`), từ ĐỊNH NGHĨA ghi ở
đầu `kiem_ke_ca_service`:

    Nhập = RECEIVE + CHUYEN_VAO · Bán = số GIAO (DISPENSE, đảo dấu)
    Trả = RETURN_RECEIVED · Khác = ADJUST + DISCARD + CHUYEN_RA
    SALE/SALE_REVERSAL là cam kết bán, KHÔNG đổi tồn vật lý (trigger
    `inventory_txn_apply`) nên không vào báo cáo.

Kiểm nhiều ĐƠN VỊ giữa các thuốc và nhập hộp đổi về viên, cửa sổ thời gian
cắt giữa chuỗi thao tác, giao trước rồi gắn lô đã quy đổi. Nhập mới cùng một
thuốc luôn về đơn vị bán; fixture cũ nhập hộp không hệ số không còn hợp lệ.

Mọi thay đổi tồn đều gọi service thật; SQL chỉ đọc sổ.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import Co, _nhap_kho, co  # noqa: F401
from tests.services.test_kiem_ke_ca_db import _tra_thuoc
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _dong_da_xac_dinh as _dong_chua_don_vi,
)
from tests.services.test_tien_thuoc_cp3_db import _thu, _ton

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal

_NHAP = ("RECEIVE", "CHUYEN_VAO")
_KHAC = ("ADJUST", "DISCARD", "CHUYEN_RA")
_VAT_LY = (*_NHAP, "DISPENSE", "RETURN_RECEIVED", *_KHAC)
_COT = ("ton_dau", "nhap", "ban", "tra", "khac", "ton_cuoi")


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _cua_so() -> tuple[datetime, datetime]:
    h = hom_nay_vn()
    tu = datetime(h.year, h.month, h.day, tzinfo=CLINIC_TZ)
    return tu, tu + timedelta(days=2)


async def _dong_da_xac_dinh(q: Quay, so: int = 10) -> tuple[str, str]:
    """Fixture CP3 chưa khai đơn vị danh mục; bài quy đổi cần thuốc bán viên."""
    rx, drug = await _dong_chua_don_vi(q, so)
    thuoc = await q.pool.fetchrow(
        "SELECT name_raw, unit_price FROM drug_catalog WHERE id = $1::uuid", drug
    )
    await PharmacyService(q.pool).luu_thuoc(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        ten=thuoc["name_raw"],
        gia=thuoc["unit_price"],
        don_vi_ban="viên",
    )
    return rx, drug


# ── Đáp án độc lập ───────────────────────────────────────────────────────


async def dap_an(
    co: Co, drug: str, tu: datetime, den: datetime
) -> dict[str, dict[str, Decimal]]:
    """(đơn vị → 6 cột) tính từ sổ gốc, chỉ lô ở QUẦY của cơ sở `co.loc`."""
    rows = await co.q.pool.fetch(
        "SELECT lower(btrim(b.unit)) AS dv, t.txn_type, t.quantity, t.performed_at"
        " FROM inventory_txn t JOIN drug_batch b ON b.id = t.drug_batch_id"
        " WHERE b.drug_catalog_id = $1::uuid AND b.location_id = $2::uuid"
        " AND b.noi_chua = 'QUAY'",
        drug,
        co.loc,
    )
    ra: dict[str, dict[str, Decimal]] = {}
    for r in rows:
        if r["txn_type"] not in _VAT_LY:
            continue
        o = ra.setdefault(r["dv"], {c: D(0) for c in _COT})
        so = D(str(r["quantity"]))
        t = r["performed_at"]
        if t < tu:
            o["ton_dau"] += so
        if t < den:
            o["ton_cuoi"] += so
        if not tu <= t < den:
            continue
        if r["txn_type"] in _NHAP:
            o["nhap"] += so
        elif r["txn_type"] == "DISPENSE":
            o["ban"] -= so
        elif r["txn_type"] == "RETURN_RECEIVED":
            o["tra"] += so
        else:
            o["khac"] += so
    # Báo cáo bỏ dòng toàn số 0 (HAVING) — đáp án cũng vậy để so cho công bằng.
    return {dv: o for dv, o in ra.items() if any(o.values())}


async def bao_cao(
    co: Co, drug: str, tu: datetime, den: datetime
) -> dict[str, dict[str, Decimal]]:
    """(đơn vị → 6 cột) do code thật trả ra."""
    async with co.q.pool.acquire() as conn:
        rows = await kk.xnt_theo_ca(
            conn, clinic_id=co.ds.clinic_id, location_id=co.loc, tu=tu, den=den
        )
    return {
        r["don_vi"]: {c: D(str(r[c])) for c in _COT}
        for r in rows
        if r["drug_catalog_id"] == drug
    }


async def khop(
    co: Co, drug: str, tu: datetime, den: datetime, *, dau: str = ""
) -> dict[str, dict[str, Decimal]]:
    """Báo cáo PHẢI bằng đáp án độc lập, từng đơn vị, từng cột."""
    an = await dap_an(co, drug, tu, den)
    thuc = await bao_cao(co, drug, tu, den)
    assert thuc == an, f"{dau} báo cáo ≠ sổ gốc:\n  báo cáo={thuc}\n  sổ gốc ={an}"
    return an


async def _nhap(
    co: Co, drug: str, so: int, don_vi: str, *, he_so: int | None = None
) -> str:
    kq = await PharmacyService(co.q.pool).nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=f"LO-{random.getrandbits(40):x}",
        expiry_date=hom_nay_vn() + timedelta(days=900),
        unit=don_vi,
        he_so=he_so,
    )
    return str(kq["drug_batch_id"])


# ── Case vàng: số tính tay, biết đáp án trước ────────────────────────────


async def _thuoc_ban_hop(co: Co) -> str:
    kq = await PharmacyService(co.q.pool).luu_thuoc(
        identity=co.ds,
        drug_catalog_id=None,
        ten=f"Thuốc bán hộp {random.getrandbits(40):x}",
        don_vi_ban="hộp",
    )
    return str(kq["id"])


async def test_hai_don_vi_va_nhap_quy_doi_khong_cong_lan(co: Co) -> None:
    """Thuốc A: 30 viên + 5 hộp × 10, giao 4, huỷ 1 → tồn 75 viên.

    Thuốc B bán theo hộp: nhập 5, điều chỉnh −1 → tồn 4 hộp. Đáp án đọc
    sổ độc lập, đồng thời phải bằng các số tính tay theo từng thuốc/đơn vị.
    """
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    await _thu(co.q)
    lo_vien = await _nhap(co, drug, 30, "viên")
    await _nhap(co, drug, 5, "hộp", he_so=10)
    drug_hop = await _thuoc_ban_hop(co)
    lo_hop = await _nhap(co, drug_hop, 5, "hộp")
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=lo_vien, so_luong=4
    )
    await svc.huy(identity=co.ds, drug_batch_id=lo_vien, so_luong=1, ly_do="Vỡ")
    await svc.dieu_chinh(
        identity=co.ds, drug_batch_id=lo_hop, so_luong=-1, ly_do="Kiểm lệch"
    )
    tu, den = _cua_so()
    assert await khop(co, drug, tu, den) == {
        "viên": dict(zip(_COT, (D(0), D(80), D(4), D(0), D(-1), D(75)), strict=True))
    }
    assert await khop(co, drug_hop, tu, den) == {
        "hộp": dict(zip(_COT, (D(0), D(5), D(0), D(0), D(-1), D(4)), strict=True))
    }


async def test_khach_tra_thuoc_la_cot_tra_khong_phai_cot_nhap(co: Co) -> None:
    """Khách trả 1 viên đã giao: cột TRẢ +1, cột BÁN vẫn giữ 4 (bán = số giao)."""
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    await _thu(co.q)
    lo = await _nhap_kho(co, drug, 20)
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=4)
    txn = await co.q.pool.fetchval(
        "SELECT id::text FROM inventory_txn WHERE ref_id = $1::uuid"
        " AND txn_type = 'DISPENSE' LIMIT 1",
        rx,
    )
    await _tra_thuoc(svc, co, txn)
    tu, den = _cua_so()
    an = await khop(co, drug, tu, den)
    assert an == {
        "viên": dict(zip(_COT, (D(0), D(20), D(4), D(1), D(0), D(17)), strict=True))
    }
    assert await _ton(co.q, lo) == 17


async def test_cua_so_cat_giua_chuoi_thao_tac(co: Co) -> None:
    """Mốc cắt giữa hai lần nhập: cửa sổ trước chỉ thấy lần 1, cửa sổ sau đầu = 10.

    Tay: [đầu ngày, mốc) nhập 10 → cuối 10. [mốc, +2 ngày) đầu 10, nhập 7 → cuối 17.
    """
    drug = await _thuoc_moi(co.q)
    await _nhap_kho(co, drug, 10)
    moc = await co.q.pool.fetchval("SELECT clock_timestamp()")
    await asyncio.sleep(0.05)  # performed_at = now() của giao dịch → phải sau mốc
    await _nhap_kho(co, drug, 7)
    tu, den = _cua_so()
    truoc = await khop(co, drug, tu, moc, dau="cửa sổ trước")
    sau = await khop(co, drug, moc, den, dau="cửa sổ sau")
    assert truoc["viên"]["nhap"] == D(10) and truoc["viên"]["ton_cuoi"] == D(10)
    assert sau["viên"]["ton_dau"] == D(10) and sau["viên"]["nhap"] == D(7)
    assert sau["viên"]["ton_cuoi"] == D(17)


# ── Bấm ngẫu nhiên có hạt cố định: báo cáo luôn bằng sổ gốc ──────────────


@pytest.mark.parametrize("seed", range(25))
async def test_bam_ngau_nhien_bao_cao_luon_bang_so_goc(co: Co, seed: int) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    rx, drug0 = await _dong_da_xac_dinh(co.q, 10)
    await _thu(co.q)
    thuoc_vien = [drug0, await _thuoc_moi(co.q)]
    drug_hop = await _thuoc_ban_hop(co)
    thuoc = [*thuoc_vien, drug_hop]
    await _nhap(co, drug_hop, 6, "hộp")
    for d in thuoc_vien:
        await _nhap(co, d, 12, "viên")
    moc: list[datetime] = []
    trace: tuple[str, ...] = ()
    tu, den = _cua_so()

    for buoc in range(8):
        lenh = rng.choice(
            ("nhap_vien", "nhap_hop", "giao", "tra", "huy", "chinh", "chinh")
        )
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        lo = await pool.fetchval(
            "SELECT id::text FROM drug_batch WHERE drug_catalog_id = ANY($1::uuid[])"
            " AND location_id = $2::uuid AND noi_chua = 'QUAY'"
            " AND quantity_on_hand > 0 ORDER BY id LIMIT 1",
            thuoc,
            co.loc,
        )
        if lenh == "nhap_vien":
            await _nhap(co, rng.choice(thuoc_vien), rng.randint(1, 5), "viên")
        elif lenh == "nhap_hop":
            drug = rng.choice(thuoc)
            await _nhap(
                co,
                drug,
                rng.randint(1, 3),
                "hộp",
                he_so=10 if drug in thuoc_vien else None,
            )
        elif lenh == "giao":
            lo_giao = await pool.fetchval(
                "SELECT id::text FROM drug_batch WHERE drug_catalog_id = $1::uuid"
                " AND location_id = $2::uuid AND noi_chua = 'QUAY'"
                " AND lower(btrim(unit)) = 'viên' AND quantity_on_hand > 0"
                " ORDER BY id LIMIT 1",
                drug0,
                co.loc,
            )
            if lo_giao:
                try:
                    await svc.cap_phat(
                        identity=co.ds,
                        prescription_id=rx,
                        drug_batch_id=lo_giao,
                        so_luong=1,
                    )
                except Exception:  # noqa: BLE001 — hết số kê / hết hạn: bước bỏ qua
                    pass
        elif lenh == "tra":
            txn = await pool.fetchval(
                "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id = $1::uuid"
                " AND t.txn_type = 'DISPENSE' AND NOT EXISTS (SELECT 1 FROM"
                " drug_return r WHERE r.original_dispense_txn_id = t.id) LIMIT 1",
                rx,
            )
            if txn:
                await _tra_thuoc(svc, co, txn)
        elif lo and lenh == "huy":
            await svc.huy(identity=co.ds, drug_batch_id=lo, so_luong=1, ly_do="Vỡ")
        elif lo and lenh == "chinh":
            await svc.dieu_chinh(
                identity=co.ds,
                drug_batch_id=lo,
                so_luong=rng.choice((-1, 1, 2)),
                ly_do="Mô phỏng",
            )
        moc.append(await pool.fetchval("SELECT clock_timestamp()"))
        await asyncio.sleep(0.01)
        for d in thuoc:
            await khop(co, d, tu, den, dau=" | ".join(trace))
            cat = rng.choice(moc)  # cửa sổ cắt ngang một mốc bất kỳ trước đó
            await khop(co, d, cat, den, dau=f"[cắt tại bước] {' | '.join(trace)}")


# ── Giao trước, gắn lô sau khi nhập đã quy đổi ──────────────────────────


async def test_giao_khi_lo_nhap_hop_da_doi_ve_vien_thi_kho_phan_anh(q: Quay) -> None:
    """Bất biến KHÔNG phụ thuộc cách quyết: thuốc đã giao thì tồn lô phải giảm."""
    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    svc = PharmacyService(q.pool)
    nhap = await svc.nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=30,
        batch_code=f"QD-{random.getrandbits(40):x}",
        expiry_date=hom_nay_vn() + timedelta(days=900),
        unit="hộp",
        he_so=10,
    )
    lo_hop = str(nhap["drug_batch_id"])
    assert await _ton(q, lo_hop) == 300
    # Lô nhập hộp đã về viên nên máy tự chọn được cho dòng bán theo viên.
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=8
    )
    assert await _ton(q, lo_hop) == 292, "300 viên − 8 viên đã giao"
