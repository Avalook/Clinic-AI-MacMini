"""Giao thuốc TỰ CHỌN LÔ theo hạn sớm nhất, trừ kho ngay lúc giao (Tuyền 27/10/2026).

"Trừ kho ở bước giao — thuốc thật rời kệ. Bước chọn lô để máy tự gợi ý lô hết
hạn sớm nhất, không bắt gõ tay. Kho không đủ lô thì VẪN CHO GIAO, ghi vào danh
sách chờ gán lô và hiện cảnh báo (an toàn trong giai đoạn chưa nạp tồn thật)."

Bất biến (giả lập trước khi code — luật làm việc của repo):
  B1  tồn lô không bao giờ âm;
  B2  số đã giao = số trừ ở lô + số ghi chờ gán lô (không mất, không đếm hai lần);
  B3  lô hết hạn sớm nhất bị trừ trước; lô không hạn xếp cuối;
  B4  lô hết hạn / khác đơn vị / ở KHO không bao giờ bị tự chọn.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import pytest

from clinicai.services import ban_thuoc_service as bt
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu, _ton
from tests.services.test_tien_thuoc_cp5_db import _tra

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chế độ đang chạy trên prod: thu tiền thuốc không chờ kho.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _sau(ngay: int) -> date:
    return date.today() + timedelta(days=ngay)


async def _giao(q: Quay, rx: str, so: Any) -> dict[str, Any]:
    """Bấm "Giao thuốc" — KHÔNG chọn lô."""
    return await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=so
    )


async def _cho(q: Quay, rx: str) -> list[dict[str, Any]]:
    kq = await PharmacyService(q.pool).cho_gan_lo(identity=q.duoc_si)
    return [d for d in kq["dong"] if d["prescription_id"] == rx]


async def _xuat(q: Quay, rx: str) -> list[tuple[str, float]]:
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(g for g in man["luot"] if g["visit_id"] == q.visit_id)
    dong = next(d for d in luot["dong"] if d["id"] == rx)
    return [(x["batch_code"], float(x["so_luong"])) for x in dong["xuat"]]


async def _ma(q: Quay, lo: str) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT batch_code FROM drug_batch WHERE id = $1::uuid", lo
        )
    )


async def test_tru_lo_het_han_som_nhat_truoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 5)
    xa = await _nhap_lo(q, drug, 20, han=_sau(400))
    gan = await _nhap_lo(q, drug, 20, han=_sau(30))
    khong_han = await _nhap_lo(q, drug, 20, han=None)
    await _thu(q)

    kq = await _giao(q, rx, 5)

    assert await _ton(q, gan) == 15, "lô hết hạn sớm nhất bị trừ trước"
    assert await _ton(q, xa) == 20
    assert await _ton(q, khong_han) == 20, "lô không hạn xếp cuối"
    assert float(kq["dispensed_qty"]) == 5
    assert [(float(x["so_luong"])) for x in kq["lo_da_tru"]] == [5.0]
    assert kq["chua_tru_kho"] == 0
    assert await _xuat(q, rx) == [(await _ma(q, gan), 5.0)]
    assert not await _cho(q, rx), "đủ lô thì không vào danh sách chờ gán lô"


async def test_giao_vuot_mot_lo_thi_tru_tiep_lo_sau(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    gan = await _nhap_lo(q, drug, 3, han=_sau(30))
    xa = await _nhap_lo(q, drug, 20, han=_sau(400))
    await _thu(q)

    kq = await _giao(q, rx, 8)

    assert await _ton(q, gan) == 0
    assert await _ton(q, xa) == 15
    assert kq["chua_tru_kho"] == 0
    assert sorted(await _xuat(q, rx)) == sorted(
        [(await _ma(q, gan), 3.0), (await _ma(q, xa), 5.0)]
    )


async def test_thieu_ton_van_giao_phan_con_lai_cho_gan_lo(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    lo = await _nhap_lo(q, drug, 3)
    await _thu(q)

    kq = await _giao(q, rx, 8)

    assert await _ton(q, lo) == 0, "B1: không âm — chỉ trừ phần có thật"
    assert float(kq["dispensed_qty"]) == 8, "vẫn cho giao đủ số khách mua"
    assert float(kq["chua_tru_kho"]) == 5
    cho = await _cho(q, rx)
    assert [float(d["so_luong"]) for d in cho] == [5.0], "B2: phần thiếu chờ gán lô"
    assert await _xuat(q, rx) == [(await _ma(q, lo), 3.0)]


async def test_kho_chua_co_lo_nao_giao_het_vao_danh_sach_cho(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 6)
    await _thu(q)

    kq = await _giao(q, rx, 6)

    assert float(kq["dispensed_qty"]) == 6
    assert kq["lo_da_tru"] == []
    assert float(kq["chua_tru_kho"]) == 6
    assert [float(d["so_luong"]) for d in await _cho(q, rx)] == [6.0]


async def test_khong_tu_chon_lo_het_han_khac_don_vi_hay_o_kho(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 4)
    het_han = await _nhap_lo(q, drug, 50)
    hop = await _nhap_lo(q, drug, 50, don_vi="hộp")
    o_kho = await _nhap_lo(q, drug, 50)
    async with q.pool.acquire() as conn:
        await conn.execute(
            "UPDATE drug_batch SET expiry_date = $2 WHERE id = $1::uuid",
            het_han,
            date.today() - timedelta(days=1),
        )
        await conn.execute(
            "UPDATE drug_batch SET noi_chua = 'KHO' WHERE id = $1::uuid", o_kho
        )
    await _thu(q)

    kq = await _giao(q, rx, 4)

    for lo in (het_han, hop, o_kho):
        assert await _ton(q, lo) == 50, "B4: không lô nào trong ba lô này bị trừ"
    assert float(kq["chua_tru_kho"]) == 4, "không có lô hợp lệ → chờ gán lô"


async def test_hai_lan_giao_cung_luc_khong_tru_qua_ton(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 16)
    lo = await _nhap_lo(q, drug, 10)
    await _thu(q)

    await asyncio.gather(_giao(q, rx, 8), _giao(q, rx, 8))

    assert await _ton(q, lo) == 0, "B1: không âm dù hai lần giao cùng lúc"
    da_tru = sum(so for _ma_lo, so in await _xuat(q, rx))
    cho = sum(float(d["so_luong"]) for d in await _cho(q, rx))
    assert da_tru == 10 and cho == 6, "B2: 16 đã giao = 10 trừ lô + 6 chờ gán lô"


async def test_khach_tra_thuoc_duoc_vi_lan_giao_nao_cung_co_lo(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    lo = await _nhap_lo(q, drug, 30)
    await _thu(q)
    await _giao(q, rx, 8)

    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(g for g in man["luot"] if g["visit_id"] == q.visit_id)
    dong = next(d for d in luot["dong"] if d["id"] == rx)
    assert dong["xuat"][0]["thao_tac"]["tra"] is True

    xuat = str(
        await q.pool.fetchval(
            "SELECT id::text FROM inventory_txn WHERE txn_type = 'DISPENSE'"
            " AND ref_id = $1::uuid",
            rx,
        )
    )
    await _tra(q, xuat, 3)
    assert await _ton(q, lo) == 25, "trả 3: tồn vật lý +3 (chờ kiểm, chưa bán lại)"
