"""Kho thuốc kiểu KiotViet (Tuyền 29/09/2026: "ai cho vào có lịch sử ghi hết lại").

Thẻ kho (tồn trước → sau, người làm, mã phiếu), xuất–nhập–tồn theo khoảng
ngày, phiếu nhập nhiều dòng, phiếu kiểm kho, sổ/phiếu chỉ-thêm.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _thuoc_moi(q: Quay) -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 'viên') RETURNING id::text",
            q.duoc_si.clinic_id,
            f"Thuốc kho {uuid.uuid4().hex[:8]}",
        )
    )


async def _phieu_nhap(
    q: Quay, dong: list[dict[str, Any]], khoa: str | None = None
) -> Any:
    return await kho.tao_phieu_nhap(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=khoa or uuid.uuid4().hex,
        nha_cung_cap="Công ty Dược A",
        so_hoa_don="HD-001",
        ngay_chung_tu="2026-09-29",
        dong=dong,
    )


def _dong_nhap(drug: str, so: Any, gia: Any = 1000) -> dict[str, Any]:
    return {
        "drug_catalog_id": drug,
        "batch_code": f"LO-{uuid.uuid4().hex[:10]}",
        "expiry_date": "2099-12-31",
        "so_luong": so,
        "gia_nhap": gia,
    }


async def _ton_thuoc(q: Quay, drug: str) -> float:
    return float(
        await q.pool.fetchval(
            "SELECT coalesce(sum(quantity_on_hand), 0) FROM drug_batch"
            " WHERE drug_catalog_id = $1::uuid",
            drug,
        )
    )


async def test_phieu_nhap_hai_dong_ra_the_kho(q: Quay) -> None:
    a, b = await _thuoc_moi(q), await _thuoc_moi(q)
    kq = await _phieu_nhap(q, [_dong_nhap(a, 30), _dong_nhap(b, "12")])
    assert kq["ma_phieu"].startswith("PN") and kq["gui_lai"] is False
    assert await _ton_thuoc(q, a) == 30 and await _ton_thuoc(q, b) == 12
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=a)
    [d] = the["dong"]
    assert d["loai_nhan"] == "Nhập hàng" and d["ma_phieu"] == kq["ma_phieu"]
    assert (float(d["ton_truoc"]), float(d["ton_sau"])) == (0, 30)
    assert d["nguoi_lam"]
    phieu = await kho.danh_sach_phieu(q.pool, identity=q.duoc_si, loai="NHAP")
    p = next(x for x in phieu if x["id"] == kq["id"])
    assert len(p["dong"]) == 2 and p["nha_cung_cap"] == "Công ty Dược A"


async def test_phieu_nhap_gui_lai_cung_khoa_khong_nhap_lan_hai(q: Quay) -> None:
    a = await _thuoc_moi(q)
    khoa = uuid.uuid4().hex
    dong = [_dong_nhap(a, 5)]
    kq1 = await _phieu_nhap(q, dong, khoa)
    kq2 = await _phieu_nhap(q, dong, khoa)
    assert kq2["gui_lai"] is True and kq2["id"] == kq1["id"]
    assert await _ton_thuoc(q, a) == 5


async def test_phieu_nhap_mot_dong_hong_thi_ca_phieu_khong_vao(q: Quay) -> None:
    a = await _thuoc_moi(q)
    with pytest.raises(ValidationError, match="Dòng 2"):
        await _phieu_nhap(q, [_dong_nhap(a, 5), _dong_nhap(a, 0)])
    assert await _ton_thuoc(q, a) == 0


async def test_giao_thuoc_vao_the_kho(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=8
    )
    lo = await _nhap_lo(q, drug, 30)
    dong = next(
        d
        for d in (await PharmacyService(q.pool).cho_gan_lo(identity=q.duoc_si))["dong"]
        if d["prescription_id"] == rx
    )
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
    )
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=drug)
    moi_nhat = the["dong"][0]
    assert moi_nhat["loai_nhan"] == "Bán / giao thuốc"
    assert float(moi_nhat["so_luong"]) == -8
    assert float(moi_nhat["ton_sau"]) == float(the["thuoc"]["ton_hien_tai"])
    assert float(moi_nhat["ton_truoc"]) - 8 == float(moi_nhat["ton_sau"])


async def test_kiem_kho_lech_am_hai(q: Quay) -> None:
    a = await _thuoc_moi(q)
    await _phieu_nhap(q, [_dong_nhap(a, 20)])
    lo = str(
        await q.pool.fetchval(
            "SELECT id::text FROM drug_batch WHERE drug_catalog_id = $1::uuid", a
        )
    )
    kq = await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo, "thuc_te": 18}],
    )
    assert kq["ma_phieu"].startswith("KK")
    assert float(kq["dong"][0]["lech"]) == -2
    assert await _ton_thuoc(q, a) == 18
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=a)
    assert the["dong"][0]["loai_nhan"] == "Kiểm kho"
    assert the["dong"][0]["ma_phieu"] == kq["ma_phieu"]
    assert (float(the["dong"][0]["ton_truoc"]), float(the["dong"][0]["ton_sau"])) == (
        20,
        18,
    )
    phieu = await kho.danh_sach_phieu(q.pool, identity=q.duoc_si, loai="KIEM")
    [d] = next(x for x in phieu if x["id"] == kq["id"])["dong"]
    assert (d["ton_may"], d["thuc_te"], d["lech"]) == (20, 18, -2)


async def test_kiem_kho_khop_thi_khong_ghi_so(q: Quay) -> None:
    a = await _thuoc_moi(q)
    await _phieu_nhap(q, [_dong_nhap(a, 7)])
    lo = str(
        await q.pool.fetchval(
            "SELECT id::text FROM drug_batch WHERE drug_catalog_id = $1::uuid", a
        )
    )
    await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo, "thuc_te": 7}],
    )
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=a)
    assert len(the["dong"]) == 1


async def test_xuat_nhap_ton_khoang_ngay(q: Quay) -> None:
    a = await _thuoc_moi(q)
    await _phieu_nhap(q, [_dong_nhap(a, 50, gia=2000)])
    lo = str(
        await q.pool.fetchval(
            "SELECT id::text FROM drug_batch WHERE drug_catalog_id = $1::uuid", a
        )
    )
    await PharmacyService(q.pool).huy(
        identity=q.duoc_si, drug_batch_id=lo, so_luong=5, ly_do="Vỡ"
    )
    hom_nay = hom_nay_vn().isoformat()
    kq = await kho.xuat_nhap_ton(q.pool, identity=q.duoc_si, tu=hom_nay, den=hom_nay)
    d = next(x for x in kq["dong"] if x["drug_catalog_id"] == a)
    assert float(d["ton_dau"]) == 0 and float(d["nhap"]) == 50
    assert float(d["huy"]) == 5 and float(d["ton_cuoi"]) == 45
    assert float(d["gia_tri_ton"]) == 45 * 2000
    # Khoảng đã qua (trước khi nhập): tồn đầu = tồn cuối = 0.
    cu = await kho.xuat_nhap_ton(
        q.pool, identity=q.duoc_si, tu="2021-01-01", den="2021-01-31"
    )
    d = next(x for x in cu["dong"] if x["drug_catalog_id"] == a)
    assert float(d["ton_dau"]) == 0 and float(d["ton_cuoi"]) == 0
    # Ngày rác → hôm nay, không ném.
    rac = await kho.xuat_nhap_ton(q.pool, identity=q.duoc_si, tu="abc", den=None)
    assert rac["tu"] == rac["den"] == hom_nay


async def test_so_kho_va_phieu_khong_sua_xoa_duoc(q: Quay) -> None:
    a = await _thuoc_moi(q)
    kq = await _phieu_nhap(q, [_dong_nhap(a, 3)])
    for sql in (
        "UPDATE inventory_txn SET reason = 'x' WHERE ref_id = $1::uuid",
        "DELETE FROM inventory_txn WHERE ref_id = $1::uuid",
        "UPDATE phieu_kho SET ghi_chu = 'x' WHERE id = $1::uuid",
        "DELETE FROM phieu_kho_dong WHERE phieu_kho_id = $1::uuid",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await q.pool.execute(sql, kq["id"])


async def test_canh_bao_sap_het_hang_va_han(q: Quay) -> None:
    a = await _thuoc_moi(q)
    svc = PharmacyService(q.pool)
    await svc.luu_thuoc(
        identity=q.duoc_si, drug_catalog_id=a, ten=f"Thuốc cb {a[:6]}", ton_toi_thieu=10
    )
    await _nhap_lo(q, a, 8, han=date.fromordinal(hom_nay_vn().toordinal() + 30))
    dm = next(t for t in await svc.danh_muc(identity=q.duoc_si) if t["id"] == a)
    assert dm["sap_het_hang"] is True and dm["so_lo_can_han"] == 1
    lo = next(
        b for b in await svc.ton_kho(identity=q.duoc_si) if b["drug_catalog_id"] == a
    )
    assert lo["trang_thai_han"] == "sap_het_han" and lo["canh_bao_han"] is True
    # Lưu lại không gửi ngưỡng → giữ ngưỡng cũ.
    await svc.luu_thuoc(identity=q.duoc_si, drug_catalog_id=a, ten=f"Thuốc cb {a[:6]}")
    dm = next(t for t in await svc.danh_muc(identity=q.duoc_si) if t["id"] == a)
    assert float(dm["ton_toi_thieu"]) == 10


async def test_ton_khac_don_vi_khong_cong_chung(q: Quay) -> None:
    """Tuyền bấm thử 29/09: lô cũ 20 hộp + phiếu nhập 50 viên → thẻ kho báo
    "70 viên". Hộp và viên không cộng được — tồn tách theo đơn vị lô."""
    a = await _thuoc_moi(q)
    await _phieu_nhap(q, [{**_dong_nhap(a, 20), "unit": "hộp"}])
    await _phieu_nhap(q, [{**_dong_nhap(a, 50), "unit": "viên"}])
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=a)
    assert the["thuoc"]["ton_hien_tai"] is None
    assert sorted(
        (x["don_vi"], float(x["ton"])) for x in the["thuoc"]["ton_theo_don_vi"]
    ) == [("hộp", 20), ("viên", 50)]
    # Tồn trước → sau chạy riêng từng đơn vị: dòng viên mới nhất 0 → 50.
    moi = the["dong"][0]
    assert moi["don_vi"] == "viên"
    assert (float(moi["ton_truoc"]), float(moi["ton_sau"])) == (0, 50)
    hom_nay = hom_nay_vn().isoformat()
    xnt = await kho.xuat_nhap_ton(q.pool, identity=q.duoc_si, tu=hom_nay, den=hom_nay)
    dong = sorted(
        (x["don_vi"], float(x["ton_cuoi"]))
        for x in xnt["dong"]
        if x["drug_catalog_id"] == a
    )
    assert dong == [("hộp", 20), ("viên", 50)]
    dm = next(
        t
        for t in await PharmacyService(q.pool).danh_muc(identity=q.duoc_si)
        if t["id"] == a
    )
    assert sorted(dm["don_vi_lo"]) == ["hộp", "viên"]
    assert len(dm["ton_theo_don_vi"]) == 2


async def test_sap_het_hang_so_tung_don_vi_va_an_don_vi_het(q: Quay) -> None:
    """30/09: chip "Sắp hết hàng" không cộng hộp với viên — 8 hộp + 5 viên với
    ngưỡng 10 là sắp hết (cộng thành 13 thì lọt). Còn một đơn vị trên ngưỡng
    (20 hộp) thì chưa hết. Đơn vị đã về 0 không hiện ("20 hộp · 0 viên")."""
    svc = PharmacyService(q.pool)

    async def dm(drug: str) -> dict[str, Any]:
        return next(
            t for t in await svc.danh_muc(identity=q.duoc_si) if t["id"] == drug
        )

    a = await _thuoc_moi(q)
    await svc.luu_thuoc(
        identity=q.duoc_si, drug_catalog_id=a, ten=f"Thuốc dv {a[:6]}", ton_toi_thieu=10
    )
    await _phieu_nhap(q, [{**_dong_nhap(a, 8), "unit": "hộp"}])
    await _phieu_nhap(q, [{**_dong_nhap(a, 5), "unit": "viên"}])
    assert (await dm(a))["sap_het_hang"] is True

    await _phieu_nhap(q, [{**_dong_nhap(a, 12), "unit": "hộp"}])
    assert (await dm(a))["sap_het_hang"] is False

    lo_vien = str(
        await q.pool.fetchval(
            "SELECT id::text FROM drug_batch"
            " WHERE drug_catalog_id = $1::uuid AND unit = 'viên'",
            a,
        )
    )
    await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo_vien, "thuc_te": 0}],
    )
    assert [
        (x["don_vi"], float(x["ton"])) for x in (await dm(a))["ton_theo_don_vi"]
    ] == [("hộp", 20)]
    the = await kho.the_kho(q.pool, identity=q.duoc_si, drug_catalog_id=a)
    assert [
        (x["don_vi"], float(x["ton"])) for x in the["thuoc"]["ton_theo_don_vi"]
    ] == [("hộp", 20)]
    assert float(the["thuoc"]["ton_hien_tai"]) == 20
