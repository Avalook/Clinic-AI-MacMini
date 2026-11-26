"""Một hàm giá dòng thuốc + "ô đơn vị trống = đơn vị MẸ" (PR A, kế hoạch
docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 14 C1/C3, mục 16).

Bất biến:
  M1  chưa thuốc nào có cờ mẹ → dòng trống đơn vị tính y như cũ (gốc), mọi màn;
  M2  có cờ mẹ → dòng trống = mẹ ở hoá đơn, màn quầy, trừ kho, đơn thuốc quốc gia;
  M3  con chưa có giá thì tự chia từ giá mẹ, làm tròn tới đồng; đủ một mẹ = đúng giá mẹ;
  M4  màn quầy và hoá đơn ra CÙNG một số tiền (một hàm);
  M5  một thuốc tối đa một đơn vị mẹ — Postgres từ chối cờ thứ hai.
Tên thuốc ở đây là tên giả — không dữ liệu khách thật.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.services.bill_service import tong_giam_duoc
from clinicai.services.don_thuoc_quoc_gia.anh_xa import doc_goi_don
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhieu_don_vi_ban_db import (
    _giao,
    _hd,
    _ke,
    _lo,
    _luu,
    _thu,
    _thuoc_goi,
    _ton,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _khong_tu_giao_khi_thu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_TU_GIAO_KHI_THU", "0")


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _ecanix(q: Quay) -> str:
    """Gốc viên (chưa có giá viên), mẹ hộp = 60 viên giá 550.000đ — có cờ mẹ."""
    drug = await _luu(
        q,
        f"Ecanix gia {uuid.uuid4().hex[:8]}",
        gia=None,
        don_vi_ban="viên",
        cac_don_vi=[{"don_vi": "hộp", "he_so": 60, "gia": 550_000}],
    )
    await _dat_me(q, drug, "hộp")
    return drug


async def _dat_me(q: Quay, drug: str, don_vi: str) -> None:
    # Chưa có màn bật cờ (PR C) — test ghi thẳng như dữ liệu sẽ có.
    await q.pool.execute(
        "UPDATE thuoc_quy_doi SET mac_dinh_ke = true"
        " WHERE drug_catalog_id = $1::uuid AND don_vi = $2",
        drug,
        don_vi,
    )


async def _quay(q: Quay, rx: str) -> dict[str, Any]:
    kq = await QuayThuocService(q.pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    return next(d for d in kq["dong"] if d["id"] == rx)


async def _quoc_gia(q: Quay) -> list[Any]:
    async with q.pool.acquire() as conn:
        goi = await doc_goi_don(
            conn, clinic_id=CLINIC, visit_ids=[q.visit_id], ma_lien_thong={}
        )
    return list(goi[q.visit_id].thuoc)


# ── M1: chưa có cờ — hành vi cũ ────────────────────────────────────────────


async def test_trong_don_vi_khong_co_co_me_tinh_nhu_cu_moi_man(q: Quay) -> None:
    drug = await _thuoc_goi(q)  # gói 85.000đ, hộp 30 gói 2.400.000đ, KHÔNG cờ
    lo = await _lo(q, drug, 100)
    rx = await _ke(q, drug, "2")
    assert (await q.pool.fetchval("SELECT unit FROM prescription WHERE id=$1", rx)) in (
        None,
        "",
    )

    d = (await _hd(q)).dong[0]
    assert (d.don_vi, d.don_gia, d.thanh_tien, d.he_so) == (None, 85_000, 170_000, None)
    quay = await _quay(q, rx)
    assert (quay["gia"], quay["thanh_tien"], quay["don_vi_goi_y"]) == (
        85_000,
        170_000,
        "gói",
    )
    assert [t.don_vi for t in await _quoc_gia(q)] == ["gói"]
    await _thu(q)
    await _giao(q, rx, 2)
    assert await _ton(q, lo) == 98, "trống = gói: trừ 2 gói"


# ── M2: có cờ — trống = mẹ ─────────────────────────────────────────────────


async def test_trong_don_vi_co_co_me_la_hop_o_hoa_don_quay_kho_quoc_gia(
    q: Quay,
) -> None:
    drug = await _thuoc_goi(q)
    await _dat_me(q, drug, "hộp")
    lo = await _lo(q, drug, 100)
    rx = await _ke(q, drug, "2")

    hd = await _hd(q)
    d = hd.dong[0]
    assert (d.don_vi, d.don_gia, d.thanh_tien, d.he_so) == (
        "hộp",
        2_400_000,
        4_800_000,
        30,
    )
    quay = await _quay(q, rx)
    assert (quay["gia"], quay["thanh_tien"], quay["don_vi_goi_y"]) == (
        2_400_000,
        4_800_000,
        "hộp",
    )
    assert [t.don_vi for t in await _quoc_gia(q)] == ["hộp"]
    await _thu(q, bill_revision=hd.revision)
    kq = await _giao(q, rx, 2)
    assert await _ton(q, lo) == 40, "2 hộp × 30 gói = trừ 60 gói"
    assert kq["chua_tru_kho"] == 0


async def test_sql_he_so_don_vi_chu_rong_theo_co_me(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    sql = "SELECT public.he_so_don_vi($1::uuid, $2::uuid, NULL)"
    assert await q.pool.fetchval(sql, CLINIC, drug) is None, "không cờ: như cũ"
    await _dat_me(q, drug, "hộp")
    assert await q.pool.fetchval(sql, CLINIC, drug) == 30


async def test_quay_dien_so_dong_trong_ghi_don_vi_me(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _dat_me(q, drug, "hộp")
    rx = await _ke(q, drug, "")
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=rx, so_luong=1, identity=q.thu_ngan
    )
    r = await q.pool.fetchrow("SELECT unit, quantity FROM prescription WHERE id=$1", rx)
    assert (r["unit"], r["quantity"]) == ("hộp", "1 hộp")
    assert (await _hd(q)).dong[0].thanh_tien == 2_400_000


# ── M3 + M4: Ecanix tự chia, quầy = hoá đơn ───────────────────────────────


@pytest.mark.parametrize(
    ("chu", "tien", "tru"),
    [("10 viên", 91_667, 10), ("60 viên", 550_000, 60), ("1", 550_000, 60)],
)
async def test_ecanix_vien_tu_chia_tu_gia_hop_quay_bang_hoa_don(
    q: Quay, chu: str, tien: int, tru: int
) -> None:
    drug = await _ecanix(q)
    lo = await _lo(q, drug, 120, don_vi="viên")
    rx = await _ke(q, drug, chu)

    hd = await _hd(q)
    assert hd.thu_duoc and hd.dong[0].thanh_tien == tien
    quay = await _quay(q, rx)
    assert quay["thanh_tien"] == tien == hd.tong, "màn quầy = hoá đơn"
    if chu != "1":
        assert (quay["gia"], quay["gia_goi_y_con"]) == (9_167, 9_200)
        assert tong_giam_duoc(hd) == 0, "đơn giá lẻ đồng: không giảm trên dòng"
    await _thu(q, bill_revision=hd.revision)
    r = await q.pool.fetchrow(
        "SELECT line_total FROM payment_bill_line WHERE source_id = $1", rx
    )
    assert r["line_total"] == tien
    await _giao(q, rx, Decimal(chu.split()[0]))
    assert await _ton(q, lo) == 120 - tru


async def test_hai_bang_gia_lech_quay_cung_khong_hien_gia_nhu_hoa_don(q: Quay) -> None:
    """Trước 26/11 quầy bỏ qua giá theo tên ở bảng giá dịch vụ: hiện 85.000đ trong
    khi hoá đơn báo mâu thuẫn. Nay một hàm — hai màn cùng nói."""
    drug = await _thuoc_goi(q)
    ten = await q.pool.fetchval("SELECT name_raw FROM drug_catalog WHERE id=$1", drug)
    await q.pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price) VALUES ($1::uuid, 'thuoc', $2, $3, 90000)",
        CLINIC,
        f"T-{uuid.uuid4().hex[:8]}",
        ten,
    )
    rx = await _ke(q, drug, "2")
    hd = await _hd(q)
    assert not hd.thu_duoc and any("mâu thuẫn" in v for v in hd.van_de)
    quay = await _quay(q, rx)
    assert (quay["gia"], quay["thanh_tien"]) == (None, None)


async def test_don_vi_chua_khai_giu_canh_bao_cu(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _dat_me(q, drug, "hộp")
    await _ke(q, drug, "2 lọ")
    hd = await _hd(q)
    assert hd.dong[0].don_gia == 85_000, "đơn vị lạ: giá gốc như cũ"
    assert any("“lọ” chưa khai ở Danh mục" in c for c in hd.canh_bao)


# ── M5: một mẹ ─────────────────────────────────────────────────────────────


async def test_mot_thuoc_hai_don_vi_me_bi_postgres_tu_choi(q: Quay) -> None:
    drug = await _luu(
        q,
        f"Hai me {uuid.uuid4().hex[:8]}",
        gia=10_000,
        don_vi_ban="viên",
        cac_don_vi=[
            {"don_vi": "vỉ", "he_so": 10, "gia": 95_000},
            {"don_vi": "hộp", "he_so": 30, "gia": 280_000},
        ],
    )
    await _dat_me(q, drug, "vỉ")
    with pytest.raises(asyncpg.UniqueViolationError):
        await _dat_me(q, drug, "hộp")


async def test_me_phai_dang_ban(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE thuoc_quy_doi SET mac_dinh_ke = true, dang_ban = false"
            " WHERE drug_catalog_id = $1::uuid",
            drug,
        )
