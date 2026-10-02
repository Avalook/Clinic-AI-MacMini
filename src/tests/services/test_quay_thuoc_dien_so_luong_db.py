"""C14 (Tuyền 01/10/2026): bác sĩ vội QUÊN số lượng thuốc — quầy thu thuốc điền
tại chỗ, không bị chặn "chờ bác sĩ".

Phủ: dòng trống số lượng → quầy điền → tổng tính lại → thu được · còn trống thì
báo ĐÍCH DANH dòng (không phải khoá) · sự kiện (ai / số cũ → mới) · kho trừ theo
số cuối · lượt đã ký vẫn điền được · hoàn tác lần thu vẫn chạy · luật cũ (số mua
≤ số bác sĩ ghi) giữ nguyên với dòng bác sĩ đã ghi số.

C19 (02/10): bỏ trần số kê — quầy đặt số TUỲ Ý (tăng / giảm) cho dòng bác sĩ đã ghi số.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.phieu_kham_service import PhieuKhamService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    _hd,
    _nhap_lo,
    _thuoc,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import _huy_phieu, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _don_trong_so_luong(
    q: Quay, *, don_vi_kho: str | None = "viên"
) -> tuple[str, str]:
    """Dòng bác sĩ kê KHÔNG ghi số lượng (cũng không đơn vị), đã gắn thuốc kho."""
    drug = await _thuoc(q)
    if don_vi_kho:
        await q.pool.execute(
            "UPDATE drug_catalog SET don_vi_ban = $2 WHERE id = $1::uuid",
            drug,
            don_vi_kho,
        )
    rx = str(
        await q.pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, $3, NULL, NULL,"
            " NULL FROM visit v WHERE v.visit_id = $4::uuid RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            "Thuốc quên số lượng",
            q.visit_id,
        )
    )
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    return rx, drug


async def _su_kien(q: Quay, ten: str) -> list[dict[str, Any]]:
    rows = await q.pool.fetch(
        "SELECT payload FROM domain_event WHERE event_type = $1"
        " AND aggregate_id = $2::uuid ORDER BY occurred_at",
        ten,
        q.visit_id,
    )
    return [
        json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        for r in rows
    ]


async def test_dong_trong_so_luong_bao_dich_danh_va_khong_cong_tien(q: Quay) -> None:
    rx, _ = await _don_trong_so_luong(q)
    hd = await _hd(q, "thuoc")
    assert hd.tong == 0 and not hd.thu_duoc
    assert any(
        "Thuốc quên số lượng" in v and "chưa có số lượng" in v for v in hd.van_de
    )
    with pytest.raises(ValidationError, match="Thuốc quên số lượng.*chưa có số lượng"):
        await _thu(q)
    [d] = (
        await QuayThuocService(q.pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    )["dong"]
    assert (d["id"], d["thieu_so_luong"], d["so_luong_do_thu_ngan"]) == (
        rx,
        True,
        False,
    )
    assert d["don_vi_goi_y"] == "viên"


async def test_quay_dien_so_luong_tong_tinh_lai_thu_duoc_va_ghi_su_kien(
    q: Quay,
) -> None:
    rx, _ = await _don_trong_so_luong(q)
    svc = QuayThuocService(q.pool)
    kq = await svc.doi_so_luong(prescription_id=rx, so_luong=10, identity=q.thu_ngan)
    assert kq["so_luong"] == "10"
    hd = await _hd(q, "thuoc")
    assert hd.van_de == [] and hd.tong == 50_000  # 10 viên × 5.000, máy chủ tính
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert d["thieu_so_luong"] is False and d["so_luong_do_thu_ngan"] is True
    assert d["nguoi_dien"] and d["don_vi"] == "viên" and d["quantity"] == "10 viên"
    # Sự kiện: ai (boi) · số cũ → mới · đúng dòng — lên Hành trình khách.
    [ev] = await _su_kien(q, "medicine.counter_changed")
    assert (
        ev["hanh_dong"],
        ev["so_luong"],
        ev["so_luong_cu"],
        ev["prescription_id"],
    ) == (
        "DIEN_SO_LUONG",
        "10",
        None,
        rx,
    )
    nhat_ky = await q.pool.fetchrow(
        "SELECT payload FROM event_log WHERE event_type = 'pharmacy.counter_changed'"
        " AND aggregate_id = $1::uuid ORDER BY occurred_at DESC LIMIT 1",
        rx,
    )
    p = nhat_ky["payload"]
    p = json.loads(p) if isinstance(p, str) else p
    assert p["ten_thuoc"] == "Thuốc quên số lượng" and p["so_luong_cu"] is None

    # Màn kê đơn của bác sĩ thấy số ấy + nhãn "SL do thu ngân điền".
    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    [dong_bs] = await PhieuKhamService(q.pool, kiem_quyen=_cho_qua).doc_don_thuoc(
        visit_id=q.visit_id, identity=q.bac_si
    )
    assert (dong_bs["quantity"], dong_bs["so_luong_do_thu_ngan"]) == ("10 viên", True)
    kq_thu = await _thu(q)
    assert kq_thu["status"] == "PAID"
    dong = await q.pool.fetchrow(
        "SELECT quantity FROM payment_bill_line WHERE source_id = $1", rx
    )
    assert Decimal(str(dong["quantity"])) == 10


async def test_quay_sua_lai_so_minh_dien_khong_tran(q: Quay) -> None:
    rx, _ = await _don_trong_so_luong(q)
    svc = QuayThuocService(q.pool)
    await svc.doi_so_luong(prescription_id=rx, so_luong=2, identity=q.thu_ngan)
    # Gõ nhầm 2 thay vì 20 — sửa lại được (chưa có dấu vết thu / kho), không trần.
    await svc.doi_so_luong(prescription_id=rx, so_luong=20, identity=q.thu_ngan)
    assert (await _hd(q, "thuoc")).tong == 100_000
    evs = await _su_kien(q, "medicine.counter_changed")
    assert [(e["so_luong_cu"], e["so_luong"]) for e in evs] == [
        (None, "2"),
        ("2", "20"),
    ]


async def _dong_co_so(q: Quay, so: int = 10) -> str:
    rx = await _don(q, so)
    drug = await _thuoc(q)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    return rx


async def test_c19_tang_vuot_so_ke_duoc_tong_tinh_lai_ghi_vet_bac_si_thay_nhan(
    q: Quay,
) -> None:
    rx = await _dong_co_so(q, 10)
    svc = QuayThuocService(q.pool)
    assert (await _hd(q, "thuoc")).tong == 50_000
    await svc.doi_so_luong(prescription_id=rx, so_luong=20, identity=q.thu_ngan)
    assert (await _hd(q, "thuoc")).tong == 100_000  # 20 × 5.000, máy chủ tính
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert (d["so_ke"], d["so_ke_goc"], d["so_luong_do_thu_ngan"]) == (
        "20",
        "10 viên",
        True,
    )
    [ev] = await _su_kien(q, "medicine.counter_changed")
    assert (ev["hanh_dong"], ev["so_luong"], ev["so_luong_cu"]) == (
        "SUA_SO_LUONG",
        "20",
        "10",
    )
    nhat_ky = await q.pool.fetchrow(
        "SELECT payload FROM event_log"
        " WHERE event_type = 'pharmacy.counter_changed' AND aggregate_id = $1::uuid"
        " ORDER BY occurred_at DESC LIMIT 1",
        rx,
    )
    p = nhat_ky["payload"]
    p = json.loads(p) if isinstance(p, str) else p
    assert (p["so_luong_cu"], p["so_luong"]) == ("10", "20")
    ai = await q.pool.fetchrow(
        "SELECT so_luong_dien_boi::text AS boi, so_luong_dien_luc FROM prescription"
        " WHERE id = $1::uuid",
        rx,
    )
    assert ai["boi"] == str(q.thu_ngan.staff_id) and ai["so_luong_dien_luc"] is not None

    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    [dong_bs] = await PhieuKhamService(q.pool, kiem_quyen=_cho_qua).doc_don_thuoc(
        visit_id=q.visit_id, identity=q.bac_si
    )
    assert dong_bs["so_luong_do_thu_ngan"] is True
    assert dong_bs["quantity"].startswith("20")
    assert dong_bs["so_luong_ke_goc"].startswith("10")
    assert (await _thu(q))["status"] == "PAID"
    dong = await q.pool.fetchrow(
        "SELECT quantity FROM payment_bill_line WHERE source_id = $1", rx
    )
    assert Decimal(str(dong["quantity"])) == 20


async def test_c19_giam_duoc_ke_goc_giu_lan_dau_va_van_la_lay_bot(q: Quay) -> None:
    rx = await _dong_co_so(q, 10)
    svc = QuayThuocService(q.pool)
    await svc.doi_so_luong(prescription_id=rx, so_luong=20, identity=q.thu_ngan)
    await svc.doi_so_luong(prescription_id=rx, so_luong=5, identity=q.thu_ngan)
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert (d["so_ke"], d["so_ke_goc"]) == ("5", "10 viên")  # gốc không bị đè bởi 20
    assert (await _hd(q, "thuoc")).tong == 25_000
    # Cùng số hiện tại → không ghi vết giả.
    await svc.doi_so_luong(prescription_id=rx, so_luong=5, identity=q.thu_ngan)
    evs = await _su_kien(q, "medicine.counter_changed")
    assert [(e["so_luong_cu"], e["so_luong"]) for e in evs] == [
        ("10", "20"),
        ("20", "5"),
    ]
    await _thu(q)
    # Mốc so là số bác sĩ kê gốc (10) → 5 < 10 là "lấy bớt", báo CSKH như cũ.
    [bo] = await _su_kien(q, "medicine.declined")
    assert (bo["so_ke"], bo["so_mua"]) == ("10", "5")


async def test_c19_khong_hop_le_bao_ro_khong_500(q: Quay) -> None:
    rx = await _dong_co_so(q, 10)
    svc = QuayThuocService(q.pool)
    for xau in (0, "0", -3, "", None, "abc", "1e999", "999999999", float("nan")):
        with pytest.raises(ValidationError, match="Số lượng phải"):
            await svc.doi_so_luong(
                prescription_id=rx, so_luong=xau, identity=q.thu_ngan
            )
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert d["so_ke"] == "10" and d["so_luong_do_thu_ngan"] is False
    assert await _su_kien(q, "medicine.counter_changed") == []


async def test_c19_giam_khong_duoi_so_da_chon_lo(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    rx = await _dong_co_so(q, 10)
    drug = str(
        await q.pool.fetchval(
            "SELECT drug_catalog_id::text FROM prescription WHERE id = $1::uuid", rx
        )
    )
    lo = await _nhap_lo(q, drug, 100)
    svc = QuayThuocService(q.pool)
    await svc.doi_so_luong(prescription_id=rx, so_luong=15, identity=q.thu_ngan)
    await PharmacyService(q.pool).phan_lo(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=15
    )
    with pytest.raises(ValidationError, match="chọn lô nhiều hơn"):
        await svc.doi_so_luong(prescription_id=rx, so_luong=8, identity=q.thu_ngan)
    await svc.doi_so_luong(
        prescription_id=rx, so_luong=18, identity=q.thu_ngan
    )  # tăng vẫn được


async def test_con_dong_trong_thi_khong_thu_dong_khac_van_vao_tong(
    q: Quay,
) -> None:
    rx_trong, _ = await _don_trong_so_luong(q)
    rx_co = await _don(q, 4)
    drug = await _thuoc(q, ten=f"Thuốc có số {q.duoi}")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx_co, drug_catalog_id=drug
    )
    hd = await _hd(q, "thuoc")
    assert hd.tong == 20_000  # dòng trống không cộng
    with pytest.raises(ValidationError, match="Thuốc quên số lượng"):
        await _thu(q)
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=rx_trong, so_luong=3, identity=q.thu_ngan
    )
    assert (await _hd(q, "thuoc")).tong == 35_000
    assert (await _thu(q))["status"] == "PAID"


async def test_kho_tru_theo_so_cuoi_quay_dien(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    rx, drug = await _don_trong_so_luong(q)
    lo = await _nhap_lo(q, drug, 100)
    # Chưa có số lượng → kho chưa chọn lô được, và câu báo chỉ về quầy thu thuốc.
    with pytest.raises(ValidationError, match="thu ngân thuốc điền"):
        await PharmacyService(q.pool).phan_lo(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=8
        )
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=rx, so_luong=8, identity=q.thu_ngan
    )
    await PharmacyService(q.pool).phan_lo(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=8
    )
    await _thu(q)
    ban = await q.pool.fetchval(
        "SELECT coalesce(sum(t.quantity), 0) FROM inventory_txn t"
        " WHERE t.txn_type = 'SALE' AND t.drug_batch_id = $1::uuid"
        " AND t.payment_cycle_id IN (SELECT payment_cycle_id FROM payment_cycle"
        "  WHERE visit_id = $2::uuid)",
        lo,
        q.visit_id,
    )
    assert (
        abs(Decimal(str(ban))) == 8
    )  # SALE ghi số ÂM — kho trừ đúng 8, không phải 1 hay số kê cũ


async def test_hoan_tac_lan_thu_van_chay_va_dong_da_thu_khong_sua_so_luong_nua(
    q: Quay,
) -> None:
    rx, _ = await _don_trong_so_luong(q)
    svc = QuayThuocService(q.pool)
    await svc.doi_so_luong(prescription_id=rx, so_luong=5, identity=q.thu_ngan)
    cyc = (await _thu(q))["payment_cycle_id"]
    # Đã thu → khoá như mọi dòng.
    with pytest.raises(ConflictError):
        await svc.doi_so_luong(prescription_id=rx, so_luong=6, identity=q.thu_ngan)
    await _huy_phieu(q, cyc)
    # Sau hoàn tác: số đã điền còn nguyên; C19 — sửa tiếp được, tăng hay giảm.
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert (d["so_ke"], d["so_luong_do_thu_ngan"]) == ("5", True)
    await svc.doi_so_luong(prescription_id=rx, so_luong=9, identity=q.thu_ngan)
    await svc.doi_so_luong(prescription_id=rx, so_luong=4, identity=q.thu_ngan)
    assert (await _hd(q, "thuoc")).tong == 20_000
    assert (await _thu(q))["status"] == "PAID"


async def test_luot_da_ky_quay_van_dien_duoc_nhung_bac_si_sua_tay_van_bi_chan(
    q: Quay,
) -> None:
    rx, drug = await _don_trong_so_luong(q)
    rx_co = await _don(q, 10, ten="Thuốc có số")
    await q.pool.execute(
        "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid", q.visit_id
    )
    svc = QuayThuocService(q.pool)
    await svc.doi_so_luong(prescription_id=rx, so_luong=7, identity=q.thu_ngan)
    [d] = [
        x
        for x in (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
        if x["id"] == rx
    ]
    assert d["so_ke"] == "7"
    # Dòng quầy thêm cũng được ở lượt đã ký (nó không thuộc hồ sơ bác sĩ).
    kq = await svc.luu_dong_them(
        visit_id=q.visit_id,
        dong=[{"drug_catalog_id": drug, "quantity": "2 viên"}],
        identity=q.thu_ngan,
    )
    assert len(kq["them"]) == 1
    # Lưới TT13 vẫn nguyên: BÁC SĨ tự sửa số lượng (không qua quầy) → vẫn chặn.
    with pytest.raises(asyncpg.CheckViolationError, match="đã ký"):
        await q.pool.execute(
            "UPDATE prescription SET quantity = '99 viên', quantity_num = 99"
            " WHERE id = $1::uuid",
            rx_co,
        )


def test_nhan_dong_thoi_gian_noi_ro_so_cu_moi_khong_co_ten_thuoc() -> None:
    from clinicai.events.consumers.dong_thoi_gian import _nhan_rieng

    dien = _nhan_rieng(
        "medicine.counter_changed",
        {"hanh_dong": "DIEN_SO_LUONG", "so_luong": "10", "so_luong_cu": None},
    )
    assert dien == "Quầy thu thuốc điền số lượng thuốc (bác sĩ để trống): 10"
    sua = _nhan_rieng(
        "medicine.counter_changed",
        {"hanh_dong": "DIEN_SO_LUONG", "so_luong": "20", "so_luong_cu": "2"},
    )
    assert sua == "Quầy thu thuốc sửa số lượng thuốc đã điền: 2 → 20"
    # C19: bác sĩ ĐÃ kê số, quầy đặt số khác.
    c19 = _nhan_rieng(
        "medicine.counter_changed",
        {"hanh_dong": "SUA_SO_LUONG", "so_luong": "20", "so_luong_cu": "10"},
    )
    assert c19 == "Quầy thu thuốc sửa số lượng thuốc bác sĩ kê: 10 → 20"
    # Các hành động khác giữ nhãn cố định của danh mục.
    assert _nhan_rieng("medicine.counter_changed", {"hanh_dong": "BO_CHON"}) is None
