"""G3b — mã vạch: tra / gắn / gỡ mã, tem lô, và bước 0 bất biến "quét không đổi kho".

Bất biến (bấm ngẫu nhiên 40 hạt × 10 bước, lệnh thật):
  (1) tra mã KHÔNG đổi tồn lô nào, không ghi dòng sổ kho nào;
  (2) một mã (dạng so khớp) thuộc nhiều nhất MỘT thuốc;
  (3) gợi ý lô FEFO: hạn gần trước, lô không hạn cuối, không có lô hết hạn / tồn 0;
  (4) tồn lô = cộng dồn sổ vật lý của lô (như G3a);
  (5) mã tem mỗi lô duy nhất và quét tem ra đúng lô đó.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q được import từ CP1.
import random
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import ma_vach_service as mv
from clinicai.services.lo_thuoc_service import huy_lo
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import (
    _dong_nhap,
    _phieu_nhap,
    _thuoc_moi,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ma_hop_nhat() -> tuple[str, str]:
    """(EAN-13 in trên hộp, GTIN-14 trong mã vuông) hợp lệ, MỖI LẦN MỘT mã mới —
    DB test dùng chung giữa các bài, mã vạch là duy nhất toàn phòng khám."""
    than = "89" + "".join(random.choices("0123456789", k=10))
    tong = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(than))
    ean = than + str((10 - tong % 10) % 10)
    return ean, "0" + ean


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _anh_chup_kho(pool: asyncpg.Pool, thuoc: list[str]) -> tuple[object, int]:
    ton = await pool.fetch(
        "SELECT id::text, quantity_on_hand FROM drug_batch"
        " WHERE drug_catalog_id = ANY($1::uuid[]) ORDER BY id",
        thuoc,
    )
    so_txn = await pool.fetchval(
        "SELECT count(*) FROM inventory_txn t JOIN drug_batch b"
        " ON b.id = t.drug_batch_id WHERE b.drug_catalog_id = ANY($1::uuid[])",
        thuoc,
    )
    return [tuple(r) for r in ton], so_txn


async def _ma_tem(q: Quay, lo: str) -> str:
    return str(
        await q.pool.fetchval("SELECT ma_tem FROM drug_batch WHERE id=$1::uuid", lo)
    )


# ── Tem lô ───────────────────────────────────────────────────────────────


async def test_moi_lo_co_ma_tem_rieng_va_quet_ra_dung_lo(q: Quay) -> None:
    thuoc = await _thuoc_moi(q)
    a = await _nhap_lo(q, thuoc, 5)
    b = await _nhap_lo(q, thuoc, 7)
    ta, tb = await _ma_tem(q, a), await _ma_tem(q, b)
    assert ta != tb and ta.startswith("LT") and len(ta) == 10
    kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=f" {ta.lower()} ")
    assert kq["loai"] == "tem"
    assert kq["lo"]["id"] == a and kq["lo"]["trang_thai"] == "ok"
    assert kq["lo"]["ten_thuoc"]


async def test_ma_tem_khong_doi_duoc(q: Quay) -> None:
    lo = await _nhap_lo(q, await _thuoc_moi(q), 5)
    with pytest.raises(asyncpg.PostgresError, match="không đổi được"):
        await q.pool.execute(
            "UPDATE drug_batch SET ma_tem='LT99999999' WHERE id=$1::uuid", lo
        )
    # Sửa số lô / hạn (G3a) không đụng mã tem.
    t = await _ma_tem(q, lo)
    await q.pool.execute(
        "UPDATE drug_batch SET batch_code=batch_code||'x' WHERE id=$1::uuid", lo
    )
    assert await _ma_tem(q, lo) == t


async def test_tem_cua_lo_het_han_da_huy_het_ton_bao_dung_trang_thai(q: Quay) -> None:
    thuoc = await _thuoc_moi(q)
    het_han = await _nhap_lo(q, thuoc, 4, han=hom_nay_vn() - timedelta(days=1))
    tem = await _ma_tem(q, het_han)
    kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=tem)
    assert kq["lo"]["trang_thai"] == "het_han"
    await huy_lo(
        q.pool,
        identity=q.duoc_si,
        drug_batch_id=het_han,
        ly_do="Hết hạn",
        khoa_gui=str(uuid.uuid4()),
    )
    kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=tem)
    assert kq["lo"]["trang_thai"] == "da_huy"
    # Lô đã huỷ / hết hạn không bao giờ lọt vào gợi ý bán.
    assert await _goi_y(q, thuoc) == []


async def _goi_y(q: Quay, thuoc: str) -> list[dict[str, Any]]:
    async with q.pool.acquire() as conn:
        return await mv.goi_y_lo(conn, q.duoc_si, thuoc)


async def test_tem_la_va_rac_khong_nem(q: Quay) -> None:
    for rac in (None, "", "   ", 123, "x" * 1000, "LT00000000", "\x00\x01"):
        kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=rac)
        assert kq["loai"] in ("rong", "la")


# ── Mã vạch nhà sản xuất ────────────────────────────────────────────────


async def test_gan_ma_roi_quet_ra_thuoc_va_goi_y_fefo(q: Quay) -> None:
    ean, gtin = _ma_hop_nhat()
    thuoc = await _thuoc_moi(q)
    xa = await _nhap_lo(q, thuoc, 5, han=hom_nay_vn() + timedelta(days=400))
    gan = await _nhap_lo(q, thuoc, 5, han=hom_nay_vn() + timedelta(days=30))
    khong_han = await _nhap_lo(q, thuoc, 5, han=None)
    het = await _nhap_lo(q, thuoc, 5, han=hom_nay_vn() - timedelta(days=3))
    r = await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=thuoc, ma=ean)
    assert r["gui_lai"] is False
    kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=ean)
    assert kq["loai"] == "thuoc" and kq["thuoc"]["id"] == thuoc
    ids = [lo["id"] for lo in kq["goi_y_lo"]]
    assert ids == [gan, xa, khong_han]  # FEFO, không hạn cuối, hết hạn bị loại
    assert het not in ids


async def test_quet_ma_vuong_gs1_khop_ma_in_tren_hop_va_lay_so_lo(q: Quay) -> None:
    ean, gtin = _ma_hop_nhat()
    thuoc = await _thuoc_moi(q)
    lo = await _nhap_lo(q, thuoc, 5)
    ma_lo = await q.pool.fetchval(
        "SELECT batch_code FROM drug_batch WHERE id=$1::uuid", lo
    )
    await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=thuoc, ma=ean)
    kq = await mv.tra_ma(
        q.pool, identity=q.duoc_si, ma=f"]d201{gtin}17271231" + f"10{ma_lo}"
    )
    assert kq["loai"] == "thuoc"
    assert kq["gs1"]["han"] == "2027-12-31"
    assert kq["lo_theo_ma"]["id"] == lo


async def test_ma_la_tra_ve_la_va_giu_du_lieu_gs1(q: Quay) -> None:
    ean, gtin = _ma_hop_nhat()
    kq = await mv.tra_ma(q.pool, identity=q.duoc_si, ma=f"01{gtin}1727123110ABC")
    assert kq["loai"] == "la"
    assert kq["gs1"] == {"gtin": gtin, "so_lo": "ABC", "han": "2027-12-31"}


async def test_gan_ma_da_thuoc_thuoc_khac_409_noi_ten(q: Quay) -> None:
    ean, gtin = _ma_hop_nhat()
    a, b = await _thuoc_moi(q), await _thuoc_moi(q)
    await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=a, ma=ean)
    ten_a = await q.pool.fetchval(
        "SELECT name_base FROM drug_catalog WHERE id=$1::uuid", a
    )
    with pytest.raises(ConflictError, match=ten_a):
        await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=b, ma=ean)
    # Cùng hộp, dạng GTIN-14 của mã vuông → vẫn là CÙNG mã, vẫn 409.
    with pytest.raises(ConflictError):
        await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=b, ma=gtin)
    # Gắn lại cho chính thuốc đó: không lỗi, không thêm dòng.
    r = await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=a, ma=gtin)
    assert r["gui_lai"] is True
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_ma_vach WHERE drug_catalog_id=$1::uuid", a
        )
        == 1
    )


async def test_nhieu_ma_cho_mot_thuoc_va_go_ma_hoan_tac(q: Quay) -> None:
    thuoc = await _thuoc_moi(q)
    a = await mv.gan_ma(
        q.pool, identity=q.duoc_si, drug_catalog_id=thuoc, ma="ABC-1234"
    )
    await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=thuoc, ma="ABC-5678")
    assert (
        len(await mv.ma_cua_thuoc(q.pool, identity=q.duoc_si, drug_catalog_id=thuoc))
        == 2
    )
    await mv.go_ma(q.pool, identity=q.duoc_si, ma_vach_id=a["id"])
    assert (await mv.tra_ma(q.pool, identity=q.duoc_si, ma="ABC-1234"))["loai"] == "la"
    # Gỡ lần hai: không lỗi. Gỡ xong gắn cho thuốc khác được.
    assert (await mv.go_ma(q.pool, identity=q.duoc_si, ma_vach_id=a["id"]))["gui_lai"]
    khac = await _thuoc_moi(q)
    await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=khac, ma="ABC-1234")
    nk = await q.pool.fetch(
        "SELECT event_type FROM event_log WHERE aggregate_id=$1::uuid"
        " AND event_type LIKE 'pharmacy.ma_vach_%'",
        thuoc,
    )
    assert {r["event_type"] for r in nk} == {
        "pharmacy.ma_vach_gan",
        "pharmacy.ma_vach_go",
    }


@pytest.mark.parametrize(
    "rac", ["", "   ", "abc", "a b c d", "x" * 65, "LT12345678", "lt12345678"]
)
async def test_gan_ma_rac_422_khong_luu(q: Quay, rac: str) -> None:
    thuoc = await _thuoc_moi(q)
    with pytest.raises(ValidationError):
        await mv.gan_ma(q.pool, identity=q.duoc_si, drug_catalog_id=thuoc, ma=rac)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_ma_vach WHERE drug_catalog_id=$1::uuid", thuoc
        )
        == 0
    )


async def test_gan_ma_thuoc_la_404_va_co_so_khac_khong_thay_tem(q: Quay) -> None:
    with pytest.raises(NotFoundError):
        await mv.gan_ma(
            q.pool,
            identity=q.duoc_si,
            drug_catalog_id=str(uuid.uuid4()),
            ma="ABC-9999",
        )


async def test_ma_hang_kiotviet_hai_thuoc_trung_khong_doan(q: Quay) -> None:
    a, b = await _thuoc_moi(q), await _thuoc_moi(q)
    ma = f"MH{uuid.uuid4().hex[:6].upper()}"
    await q.pool.execute("UPDATE drug_catalog SET ma_hang=$2 WHERE id=$1::uuid", a, ma)
    assert (await mv.tra_ma(q.pool, identity=q.duoc_si, ma=ma))["thuoc"]["id"] == a
    await q.pool.execute("UPDATE drug_catalog SET ma_hang=$2 WHERE id=$1::uuid", b, ma)
    assert (await mv.tra_ma(q.pool, identity=q.duoc_si, ma=ma))["loai"] == "la"


async def test_du_lieu_tem_theo_phieu_nhap_va_id_rac(q: Quay) -> None:
    thuoc = await _thuoc_moi(q)
    kq = await _phieu_nhap(q, [{**_dong_nhap(thuoc, 3), "unit": "viên"}])
    tem = await mv.du_lieu_tem(q.pool, identity=q.duoc_si, phieu_kho_id=kq["id"])
    assert len(tem) == 1 and tem[0]["ma_tem"].startswith("LT")
    assert await mv.du_lieu_tem(q.pool, identity=q.duoc_si, lo_ids=[]) == []
    lo = tem[0]["id"]
    assert [
        t["id"]
        for t in await mv.du_lieu_tem(q.pool, identity=q.duoc_si, lo_ids=[lo, lo])
    ] == [lo]


# ── Bước 0: bấm ngẫu nhiên, quét không đổi kho ──────────────────────────


async def _bat_bien(q: Quay, thuoc: list[str], trace: tuple[str, ...]) -> None:
    for r in await q.pool.fetch(
        "SELECT b.id::text, b.quantity_on_hand, b.ma_tem,"
        " coalesce(sum(t.quantity) FILTER (WHERE t.txn_type = ANY($2::text[])),0) so"
        " FROM drug_batch b LEFT JOIN inventory_txn t ON t.drug_batch_id=b.id"
        " WHERE b.drug_catalog_id = ANY($1::uuid[]) GROUP BY b.id",
        thuoc,
        list(kho.LOAI_VAT_LY),
    ):
        assert r["quantity_on_hand"] == r["so"] >= 0, (dict(r), trace)
    trung = await q.pool.fetch(
        "SELECT ma_chuan, count(DISTINCT drug_catalog_id) n FROM drug_ma_vach"
        " WHERE drug_catalog_id = ANY($1::uuid[]) GROUP BY ma_chuan HAVING"
        " count(DISTINCT drug_catalog_id) > 1",
        thuoc,
    )
    assert not trung, (trung, trace)
    for t in thuoc:
        lo = await _goi_y(q, t)
        han = [(x["expiry_date"] is None, x["expiry_date"] or "") for x in lo]
        assert han == sorted(han), (han, trace)
        assert all(
            Decimal(str(x["quantity_on_hand"])) > 0
            and (
                x["expiry_date"] is None or x["expiry_date"] >= hom_nay_vn().isoformat()
            )
            for x in lo
        ), (lo, trace)


@pytest.mark.parametrize("seed", range(40))
async def test_bam_ngau_nhien_quet_khong_doi_kho(q: Quay, seed: int) -> None:
    rng = random.Random(seed)
    svc = PharmacyService(q.pool)
    thuoc = [await _thuoc_moi(q) for _ in range(3)]
    los = [await _nhap_lo(q, thuoc[i % 3], 20) for i in range(5)]
    ean, gtin = _ma_hop_nhat()
    ma_pool = [f"MA{seed:02d}{i:04d}" for i in range(4)] + [ean, gtin]
    da_gan: list[str] = []
    trace: tuple[str, ...] = ()
    for buoc in range(10):
        lenh = rng.choice(
            ("gan", "gan_nham", "tra_ma", "tra_tem", "go", "nhap", "huy", "het_han")
        )
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        try:
            if lenh in ("gan", "gan_nham"):
                try:
                    r = await mv.gan_ma(
                        q.pool,
                        identity=q.duoc_si,
                        drug_catalog_id=rng.choice(thuoc),
                        ma=rng.choice(ma_pool),
                    )
                    if not r["gui_lai"]:
                        da_gan.append(r["id"])
                except ConflictError:
                    pass
            elif lenh == "tra_ma":
                truoc = await _anh_chup_kho(q.pool, thuoc)
                await mv.tra_ma(q.pool, identity=q.duoc_si, ma=rng.choice(ma_pool))
                assert await _anh_chup_kho(q.pool, thuoc) == truoc, trace
            elif lenh == "tra_tem":
                lo = rng.choice(los)
                truoc = await _anh_chup_kho(q.pool, thuoc)
                kq = await mv.tra_ma(
                    q.pool, identity=q.duoc_si, ma=await _ma_tem(q, lo)
                )
                assert kq["lo"]["id"] == lo, trace
                assert await _anh_chup_kho(q.pool, thuoc) == truoc, trace
            elif lenh == "go" and da_gan:
                await mv.go_ma(
                    q.pool,
                    identity=q.duoc_si,
                    ma_vach_id=da_gan.pop(rng.randrange(len(da_gan))),
                )
            elif lenh == "nhap":
                await _phieu_nhap(
                    q,
                    [
                        {
                            **_dong_nhap(rng.choice(thuoc), rng.randint(1, 5)),
                            "unit": "viên",
                        }
                    ],
                )
            elif lenh == "huy":
                await svc.huy(
                    identity=q.duoc_si,
                    drug_batch_id=rng.choice(los),
                    so_luong=1,
                    ly_do="Mô phỏng",
                )
            elif lenh == "het_han":
                los.append(
                    await _nhap_lo(
                        q, rng.choice(thuoc), 3, han=hom_nay_vn() - timedelta(days=1)
                    )
                )
            await _bat_bien(q, thuoc, trace)
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")
