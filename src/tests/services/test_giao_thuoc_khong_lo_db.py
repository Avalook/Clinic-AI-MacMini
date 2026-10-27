"""Giao thuốc KHÔNG cần lô, gán lô sau (Tuyền 28/09/2026).

"Chưa cần quan tâm lô nào, số lượng điền tay … áp dụng bán luôn, lô nhập và
gán sau." Trước bản này quầy không giao được khi kho chưa có lô: màn chỉ hiện
"Nhập lô ở Kho thuốc trước" và không có nút giao nào.

Luật: lần thu tiền thuốc KHÔNG gắn lô → giao không chọn lô được (không quá số
kê, không quá số mua); kho CHƯA trừ, dòng vào sổ `thuoc_giao_chua_gan_lo`; gán
lô sau → ghi DISPENSE, tồn lô giảm; mỗi lần giao gán đúng một lần.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _thu,
    _ton,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Chế độ đang chạy trên prod: thu tiền thuốc không chờ kho.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _dong(q: Quay, rx: str) -> dict[str, Any]:
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(g for g in man["luot"] if g["visit_id"] == q.visit_id)
    return next(d for d in luot["dong"] if d["id"] == rx)


async def _giao_khong_lo(q: Quay, rx: str, so: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=so
    )


async def _cho(q: Quay) -> list[dict[str, Any]]:
    kq = await PharmacyService(q.pool).cho_gan_lo(identity=q.duoc_si)
    return list(kq["dong"])


async def test_kho_chua_co_lo_van_thu_va_giao_duoc(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 10)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    kq = await _giao_khong_lo(q, rx, 4)
    assert float(kq["dispensed_qty"]) == 4
    # Còn phần bán chưa giao → nút vẫn còn; giao nốt thì hết nút.
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    await _giao_khong_lo(q, rx, 6)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is False
    cho = [d for d in await _cho(q) if d["prescription_id"] == rx]
    assert sorted(float(d["so_luong"]) for d in cho) == [4.0, 6.0]


async def test_khong_giao_qua_so_ke(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 5)
    await _thu(q)
    with pytest.raises(ValidationError):
        await _giao_khong_lo(q, rx, 6)


async def test_gan_lo_sau_thi_kho_moi_tru_va_chi_gan_mot_lan(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)
    lo = await _nhap_lo(q, drug, 30)
    assert await _ton(q, lo) == 30, "giao không lô chưa trừ kho"
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    assert lo in {b["drug_batch_id"] for b in dong["lo_gan_duoc"]}
    svc = PharmacyService(q.pool)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
    assert await _ton(q, lo) == 22
    assert dong["id"] not in {d["id"] for d in await _cho(q)}
    with pytest.raises(ConflictError):
        await svc.gan_lo_da_giao(
            identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
        )


async def test_da_chon_lo_nhung_lan_thu_khong_gan_lo_van_giao_khong_lo(
    q: Quay,
) -> None:
    # Thu không chờ kho: lô đã chọn KHÔNG gắn vào lần thu → trước bản này dòng
    # không có nút giao nào. Nay giao không lô được.
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 50)
    await _chon(q, rx, lo, 6)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    await _giao_khong_lo(q, rx, 6)


async def test_quet_lo_o_dong_giao_khong_lo_giao_thang_tu_lo_do_va_kho_tru_ngay(
    q: Quay,
) -> None:
    """Bấm thật 14/10: quét tem lô rồi "Giao thuốc" ở dòng đã thu chưa phân lô —
    trước đây màn bỏ qua lô vừa quét (giao không lô, kho chưa trừ, không có dòng
    "Đã giao … Lô … Khách trả"). Nay giao kèm lô: kho trừ ngay, dòng xuất mang lô."""
    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    lo = await _nhap_lo(q, drug, 30)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is True
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=3
    )
    assert await _ton(q, lo) == 27, "giao từ lô đã quét thì kho trừ ngay"
    xuat = (await _dong(q, rx))["xuat"]
    assert [float(x["so_luong"]) for x in xuat] == [3.0]
    assert xuat[0]["batch_code"], "dòng xuất mang mã lô — đủ để khách trả theo lô"
    # Không vào sổ "giao chưa gán lô" — lô đã rõ.
    assert not [d for d in await _cho(q) if d["prescription_id"] == rx]


async def test_dong_da_ban_theo_lo_thi_phai_giao_dung_lo(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Thu CHỜ kho (công tắc bật): lần thu gắn lô → giao đúng lô, không giao trơn.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 50)
    await _chon(q, rx, lo, 6)
    await _thu(q)
    assert (await _dong(q, rx))["thao_tac"]["giao_khong_lo"] is False
    with pytest.raises(ValidationError):
        await _giao_khong_lo(q, rx, 6)


async def _kha_dung(q: Quay, lo: str) -> tuple[float, float]:
    rows = await PharmacyService(q.pool).ton_kho(identity=q.duoc_si)
    r = next(r for r in rows if r["id"] == lo)
    return float(r["ton_kha_dung_thuoc"]), float(r["da_giao_chua_doi_chieu"])


async def test_giao_tru_kha_dung_gan_lo_kho_sau_khong_tru_hai_lan(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    lo = await _nhap_lo(q, drug, 30)
    async with q.pool.acquire() as conn:
        await conn.execute(
            "UPDATE drug_batch SET noi_chua = 'KHO' WHERE id = $1::uuid", lo
        )
    await _thu(q)
    assert await _kha_dung(q, lo) == (30, 0)
    await _giao_khong_lo(q, rx, 8)
    assert await _ton(q, lo) == 30  # chưa bịa lô
    assert await _kha_dung(q, lo) == (22, 8)
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    assert (
        next(b for b in dong["lo_gan_duoc"] if b["drug_batch_id"] == lo)["noi_chua"]
        == "KHO"
    )
    svc = PharmacyService(q.pool)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
    assert await _ton(q, lo) == 22
    assert await _kha_dung(q, lo) == (22, 0)
    with pytest.raises(ConflictError):
        await svc.gan_lo_da_giao(
            identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
        )
    assert await _kha_dung(q, lo) == (22, 0)


async def test_gan_lo_dong_thoi_chi_ghi_mot_lan(q: Quay) -> None:
    import asyncio

    rx, drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)  # kho chưa có lô → chờ gán lô
    lo = await _nhap_lo(q, drug, 30)
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    svc = PharmacyService(q.pool)
    results = await asyncio.gather(
        *(
            svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(r, ConflictError) for r in results) == 1
    assert await _ton(q, lo) == 22
    assert await _kha_dung(q, lo) == (22, 0)


async def test_pending_thuoc_khac_khong_mo_gac_xuat_kho(q: Quay) -> None:
    import asyncpg

    rx, _drug = await _dong_da_xac_dinh(q, 8)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)
    from tests.services.test_tien_thuoc_cp1_db import _thuoc

    khac = await _thuoc(q, ten=f"Thuốc khác {q.duoi}")
    lo = await _nhap_lo(q, khac, 30)
    async with q.pool.acquire() as conn:
        await conn.execute("UPDATE drug_batch SET noi_chua='KHO' WHERE id=$1::uuid", lo)
        with pytest.raises(asyncpg.ExclusionViolationError):
            await conn.execute(
                "INSERT INTO inventory_txn"
                " (clinic_id, drug_batch_id, txn_type, quantity, ref_type, ref_id)"
                " VALUES ($1::uuid,$2::uuid,'DISPENSE',-8,'prescription',$3::uuid)",
                q.duoc_si.clinic_id,
                lo,
                rx,
            )
    assert await _ton(q, lo) == 30


async def test_kha_dung_khong_cong_lan_don_vi_va_cho_phep_lo_thieu_nhap(
    q: Quay,
) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 8)
    vien = await _nhap_lo(q, drug, 3)
    hop = await _nhap_lo(q, drug, 20, don_vi="hộp")
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)
    # Máy tự trừ 3 viên có thật; 5 viên thiếu chờ gán lô và đã được trừ khỏi
    # "có thể gán" (−5). Lô hộp KHÔNG bị cộng vào.
    assert await _kha_dung(q, vien) == (-5, 5)
    assert await _kha_dung(q, hop) == (20, 0)


async def test_doi_chieu_khong_dung_hang_khach_tra_cho_kiem(q: Quay) -> None:
    from tests.services.test_tien_thuoc_cp5_db import _tra, _xuat

    rx, drug = await _dong_da_xac_dinh(q, 10)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)  # kho chưa có lô → chờ gán lô
    lo = await _nhap_lo(q, drug, 8)
    svc = PharmacyService(q.pool)
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
    await _tra(q, await _xuat(q, rx), 8)
    assert await _ton(q, lo) == 8
    assert await _kha_dung(q, lo) == (0, 0)
    await _giao_khong_lo(q, rx, 2)
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    assert not dong["lo_gan_duoc"], "hàng trả chờ kiểm không được gợi ý"
    with pytest.raises(ValidationError):
        await svc.gan_lo_da_giao(
            identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo
        )
    assert await _ton(q, lo) == 8
    assert await _kha_dung(q, lo) == (-2, 2)


async def test_khach_tra_lo_kho_hoan_tien_va_cach_ly(q: Quay) -> None:
    from tests.services.test_tien_thuoc_cp5_db import _xuat

    rx, drug = await _dong_da_xac_dinh(q, 8)
    lo = await _nhap_lo(q, drug, 30)
    async with q.pool.acquire() as conn:
        await conn.execute("UPDATE drug_batch SET noi_chua='KHO' WHERE id=$1::uuid", lo)
    await _thu(q)
    await _giao_khong_lo(q, rx, 8)
    svc = PharmacyService(q.pool)
    dong = next(d for d in await _cho(q) if d["prescription_id"] == rx)
    await svc.gan_lo_da_giao(identity=q.duoc_si, dong_id=dong["id"], drug_batch_id=lo)
    kq = await svc.khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=await _xuat(q, rx),
        so_luong=3,
        ly_do="Khách trả ba viên",
        ket_cuc_tien="HOAN",
        hinh_thuc="CASH",
    )
    assert kq["hoan"]["refund_id"]
    assert await _ton(q, lo) == 25
    assert await _kha_dung(q, lo) == (22, 0), "hàng trả chờ kiểm không bán lại"
    async with q.pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT disposition, returned_qty, refund_id::text FROM drug_return"
            " WHERE id=$1::uuid",
            kq["drug_return_id"],
        )
        assert r["disposition"] is None
        assert float(r["returned_qty"]) == 3
        assert r["refund_id"] == kq["hoan"]["refund_id"]
        tien = await conn.fetchrow(
            "SELECT amount, status FROM payment_refund WHERE refund_id=$1::uuid",
            r["refund_id"],
        )
        assert float(tien["amount"]) == 15000
        assert tien["status"] == "COMPLETED"


async def test_nhan_tra_vao_kho_khong_co_ho_so_tra_bi_chan(q: Quay) -> None:
    import asyncpg

    rx, drug = await _dong_da_xac_dinh(q, 8)
    lo = await _nhap_lo(q, drug, 30)
    async with q.pool.acquire() as conn:
        await conn.execute("UPDATE drug_batch SET noi_chua='KHO' WHERE id=$1::uuid", lo)
        with pytest.raises(asyncpg.ExclusionViolationError):
            await conn.execute(
                "INSERT INTO inventory_txn"
                " (clinic_id, drug_batch_id, txn_type, quantity, ref_type, ref_id)"
                " VALUES ($1::uuid,$2::uuid,'RETURN_RECEIVED',3,"
                " 'drug_return',$3::uuid)",
                q.duoc_si.clinic_id,
                lo,
                rx,
            )
    assert await _ton(q, lo) == 30
