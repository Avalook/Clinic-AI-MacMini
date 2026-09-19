"""Contract tiền–thuốc CP3 (19/09/2026): bán thuốc lúc thu tiền thành công,
theo đúng lô dược sĩ đã chọn trước.

Ba con số mỗi test đọc lại từ DB:
  * ton  — `drug_batch.quantity_on_hand`, thuốc VẬT LÝ trên kệ;
  * kd   — `drug_batch_kha_dung()`, vật lý − đang giữ − đã bán chưa giao;
  * ban  — số dòng SALE (và SALE_REVERSAL) trong sổ.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _hd,
    _nhap_lo,
    _thuoc,
    q,  # noqa: F401
    tao_quay,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── Đọc ba con số ─────────────────────────────────────────────────────────


async def _ton(q: Quay, lo: str) -> int:
    return _nguyen(
        await q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
        )
    )


async def _kd(q: Quay, lo: str) -> int:
    return _nguyen(
        await q.pool.fetchval(
            "SELECT drug_batch_kha_dung($1::uuid, $2::uuid)", CLINIC, lo
        )
    )


def _nguyen(v: Any) -> int:
    """Số lượng trong các test này luôn nguyên; lẻ là lỗi, không làm tròn."""
    d = Decimal(str(v))
    assert d == d.to_integral_value(), d
    return int(d)


async def _so_dong(q: Quay, loai: str, lo: str | None = None) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = $1"
            " AND ($2::uuid IS NULL OR drug_batch_id = $2::uuid)"
            " AND payment_cycle_id IN (SELECT payment_cycle_id FROM payment_cycle"
            "  WHERE visit_id = $3::uuid)",
            loai,
            lo,
            q.visit_id,
        )
    )


# ── Dựng ──────────────────────────────────────────────────────────────────


async def _dong_da_xac_dinh(q: Quay, so: int = 10) -> tuple[str, str]:
    rx = await _don(q, so)
    drug = await _thuoc(q)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    return rx, drug


async def _chon(q: Quay, rx: str, lo: str, so: Any) -> str:
    kq = await PharmacyService(q.pool).phan_lo(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=so
    )
    return str(kq["allocation_id"])


async def _san_sang(q: Quay, so: int = 10, ton: int = 100) -> tuple[str, str, str]:
    """Dòng đơn `so` viên, đã xác định thuốc, lô `ton` viên, đã chọn đủ lô."""
    rx, drug = await _dong_da_xac_dinh(q, so)
    lo = await _nhap_lo(q, drug, ton)
    await _chon(q, rx, lo, so)
    return rx, drug, lo


async def _thu(q: Quay, method: str = "CASH") -> dict[str, Any]:
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="thuoc",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=(await _hd(q, "thuoc")).revision,
        method=method,
    )


async def _xac_minh(q: Quay, cycle: str, ma: str = "FT123456") -> dict[str, Any]:
    return await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="thuoc",
        reference=ma,
        identity=q.thu_ngan,
    )


async def _huy_phieu(q: Quay, cycle: str) -> dict[str, Any]:
    return await PaymentService(q.pool).void_payment(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Thu nhầm khách",
        identity=q.thu_ngan,
    )


async def _giao(q: Quay, rx: str, lo: str, so: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=so
    )


# ── Thu tiền mặt → bán đúng một lần ──────────────────────────────────────


async def test_thu_tien_mat_ban_dung_mot_lan_ton_vat_ly_khong_doi(q: Quay) -> None:
    _, _, lo = await _san_sang(q, 10, 100)
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 100)
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    assert await _so_dong(q, "SALE", lo) == 1
    # Bán không phải thuốc rời quầy: tồn vật lý giữ nguyên, khả dụng giảm.
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 90)


async def test_thu_lai_cung_hoa_don_khong_ban_lan_hai(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    a = await _thu(q)
    b = await _thu(q)
    assert a["payment_cycle_id"] == b["payment_cycle_id"]
    assert await _so_dong(q, "SALE", lo) == 1
    assert await _kd(q, lo) == 90


async def test_hai_thu_ngan_cung_bam_chi_ban_mot_lan(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    kq = await asyncio.gather(*(_thu(q) for _ in range(4)), return_exceptions=True)
    assert any(isinstance(k, dict) for k in kq)
    assert await _so_dong(q, "SALE", lo) == 1
    assert await _kd(q, lo) == 90


# ── Thiếu lô / lô sai → không thu được ────────────────────────────────────


async def test_chua_chon_lo_thi_khong_thu_duoc_tien_thuoc(q: Quay) -> None:
    await _dong_da_xac_dinh(q, 10)
    with pytest.raises(ValidationError, match="chọn lô cho 0/10"):
        await _thu(q)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    )


async def test_chon_thieu_lo_thi_khong_thu_duoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    await _chon(q, rx, await _nhap_lo(q, drug, 100), 6)
    with pytest.raises(ValidationError, match="6/10"):
        await _thu(q)


async def test_chon_hai_lo_ban_dung_tung_lo(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    x, y = await _nhap_lo(q, drug, 6), await _nhap_lo(q, drug, 50)
    await _chon(q, rx, x, 6)
    await _chon(q, rx, y, 4)
    await _thu(q)
    assert (await _kd(q, x), await _kd(q, y)) == (0, 46)
    assert (await _ton(q, x), await _ton(q, y)) == (6, 50)


async def test_lo_sai_thuoc_bi_tu_choi(q: Quay) -> None:
    rx, _ = await _dong_da_xac_dinh(q, 10)
    lo_khac = await _nhap_lo(q, await _thuoc(q, ten=f"Thuốc khác {q.duoi}"), 100)
    with pytest.raises(ValidationError, match="không phải thuốc"):
        await _chon(q, rx, lo_khac, 10)


async def test_lo_het_han_bi_tu_choi(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    cu = await _nhap_lo(q, drug, 100, han=date.today() - timedelta(days=1))
    with pytest.raises(ValidationError, match="hết hạn"):
        await _chon(q, rx, cu, 10)


async def test_lo_khong_du_kha_dung_bi_tu_choi(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    with pytest.raises(ValidationError, match="chỉ còn 4"):
        await _chon(q, rx, await _nhap_lo(q, drug, 4), 10)


async def test_don_vi_khac_bi_tu_choi(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    hop = await _nhap_lo(q, drug, 100, don_vi="hộp")
    with pytest.raises(ValidationError, match="đơn vị"):
        await _chon(q, rx, hop, 10)


async def test_don_chua_co_don_vi_thi_khong_chon_lo(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    await q.pool.execute("UPDATE prescription SET unit = NULL WHERE id = $1::uuid", rx)
    with pytest.raises(ValidationError, match="Chưa xác định đơn vị thuốc được kê"):
        await _chon(q, rx, await _nhap_lo(q, drug, 100), 10)


async def test_lo_cua_phong_kham_khac_bi_tu_choi_ca_o_db(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    khac = await q.pool.fetchval(
        "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
        " 'Asia/Ho_Chi_Minh') RETURNING id::text",
        f"X{q.duoi}",
    )
    thuoc_khac = await q.pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_base, name_raw)"
        " VALUES ($1::uuid, 'X', 'X') RETURNING id::text",
        khac,
    )
    lo_khac = await q.pool.fetchval(
        "INSERT INTO drug_batch (clinic_id, drug_catalog_id, batch_code,"
        " expiry_date, quantity_on_hand, unit)"
        " VALUES ($1::uuid, $2::uuid, $3, '2099-01-01', 0, 'viên') RETURNING id::text",
        khac,
        thuoc_khac,
        f"LX-{q.duoi}",
    )
    with pytest.raises(NotFoundError):
        await _chon(q, rx, lo_khac, 10)
    # Lách service, ghi thẳng: DB chặn (trigger đúng-thuốc hoặc khoá ngoại ghép
    # cùng phòng khám — lớp nào bắt trước cũng được, miễn không lọt).
    with pytest.raises(asyncpg.IntegrityConstraintViolationError):
        await q.pool.execute(
            "INSERT INTO prescription_allocation (clinic_id, visit_id,"
            " prescription_id, drug_catalog_id, drug_batch_id, quantity, created_by)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, 10, $6::uuid)",
            CLINIC,
            q.visit_id,
            rx,
            drug,
            lo_khac,
            q.duoc_si.staff_id,
        )


async def test_chon_lo_khong_giu_cho_nguoi_thu_sau_bi_kiem_lai(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 10)
    await _chon(q, rx, lo, 6)
    q2 = await tao_quay(q.pool)
    rx2 = await _don(q2, 6)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q2.duoc_si, prescription_id=rx2, drug_catalog_id=drug
    )
    # Chọn lô chưa giữ chỗ: khách thứ hai cũng chọn được lô ấy.
    await _chon(q2, rx2, lo, 6)
    await _thu(q)
    with pytest.raises(ValidationError, match="chỉ còn 4 khả dụng"):
        await _thu(q2)
    assert await _kd(q, lo) == 4


# ── Chuyển khoản / QR: giữ khi chờ, bán khi xác minh ───────────────────────


async def test_chuyen_khoan_cho_thi_giu_chua_ban_xac_minh_thi_ban(q: Quay) -> None:
    _, _, lo = await _san_sang(q, 10, 100)
    cho = await _thu(q, "TRANSFER")
    assert cho["status"] == "PENDING_VERIFICATION"
    assert await _so_dong(q, "SALE", lo) == 0
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 90)  # giữ kỹ thuật
    await _xac_minh(q, cho["payment_cycle_id"])
    assert await _so_dong(q, "SALE", lo) == 1
    assert (await _ton(q, lo), await _kd(q, lo)) == (
        100,
        90,
    )  # giữ → bán, không trừ hai
    await _xac_minh(q, cho["payment_cycle_id"])  # gửi lại
    assert await _so_dong(q, "SALE", lo) == 1


async def test_hai_lenh_xac_minh_dong_thoi_chi_ban_mot_lan(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    cho = await _thu(q, "QR")
    kq = await asyncio.gather(
        *(_xac_minh(q, cho["payment_cycle_id"]) for _ in range(4)),
        return_exceptions=True,
    )
    assert all(isinstance(k, dict) for k in kq), kq
    assert await _so_dong(q, "SALE", lo) == 1
    assert await _kd(q, lo) == 90


async def test_dang_giu_thi_nguoi_khac_khong_mua_het_duoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 6)
    lo = await _nhap_lo(q, drug, 10)
    await _chon(q, rx, lo, 6)
    cho = await _thu(q, "TRANSFER")
    q2 = await tao_quay(q.pool)
    rx2 = await _don(q2, 6)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q2.duoc_si, prescription_id=rx2, drug_catalog_id=drug
    )
    with pytest.raises(ValidationError, match="chỉ còn 4"):
        await _chon(q2, rx2, lo, 6)
    # Tiền về → bán được đúng phần đã giữ.
    kq = await _xac_minh(q, cho["payment_cycle_id"])
    assert kq["can_doi_soat"] is False
    assert await _kd(q, lo) == 4


async def test_huy_lan_cho_thi_bo_giu_va_giu_ke_hoach_lo(q: Quay) -> None:
    rx, _, lo = await _san_sang(q)
    cho = await _thu(q, "QR")
    await PaymentService(q.pool).huy_cho_xac_minh(
        payment_cycle_id=cho["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Khách không chuyển",
        identity=q.thu_ngan,
    )
    assert await _kd(q, lo) == 100
    rows = await q.pool.fetch(
        "SELECT payment_cycle_id, released_at IS NOT NULL AS da_go"
        " FROM prescription_allocation WHERE prescription_id = $1::uuid"
        " ORDER BY created_at",
        rx,
    )
    assert [(r["payment_cycle_id"] is None, r["da_go"]) for r in rows] == [
        (False, True),  # phần giữ của lần chờ — giữ làm lịch sử
        (True, False),  # kế hoạch lô chép lại, chưa gắn
    ]
    # Thu lại ngay được, không phải chọn lô lại.
    assert (await _thu(q))["status"] == "PAID"
    assert await _kd(q, lo) == 90


async def test_doi_lo_khi_cho_chuyen_phan_giu_nguyen_tu(q: Quay) -> None:
    rx, drug, x = await _san_sang(q, 10, 10)
    y = await _nhap_lo(q, drug, 30)
    cho = await _thu(q, "TRANSFER")
    pl = await q.pool.fetchval(
        "SELECT id::text FROM prescription_allocation WHERE prescription_id = $1::uuid"
        " AND released_at IS NULL",
        rx,
    )
    await PharmacyService(q.pool).doi_lo_khi_cho(
        identity=q.duoc_si, allocation_id=pl, drug_batch_id=y, ly_do="Lô X móp hộp"
    )
    assert (await _kd(q, x), await _kd(q, y)) == (10, 20)
    await _xac_minh(q, cho["payment_cycle_id"])
    assert (await _so_dong(q, "SALE", x), await _so_dong(q, "SALE", y)) == (0, 1)
    assert await _kd(q, y) == 20


async def test_doi_lo_khi_cho_lo_moi_khong_du_thi_khong_doi_gi(q: Quay) -> None:
    rx, drug, x = await _san_sang(q, 10, 10)
    y = await _nhap_lo(q, drug, 3)
    await _thu(q, "TRANSFER")
    pl = await q.pool.fetchval(
        "SELECT id::text FROM prescription_allocation WHERE prescription_id = $1::uuid"
        " AND released_at IS NULL",
        rx,
    )
    with pytest.raises(ValidationError, match="chỉ còn 3"):
        await PharmacyService(q.pool).doi_lo_khi_cho(
            identity=q.duoc_si, allocation_id=pl, drug_batch_id=y, ly_do="thử"
        )
    assert (await _kd(q, x), await _kd(q, y)) == (0, 3)


async def test_lo_het_han_trong_luc_cho_van_ghi_da_thu_va_can_doi_soat(
    q: Quay,
) -> None:
    """Tiền đã về thì không phủ nhận. Không bán được → PAID + đối soát, không
    ghi SALE, không giao được cho tới khi xử lý."""
    rx, _, lo = await _san_sang(q)
    cho = await _thu(q, "TRANSFER")
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date = current_date - 1 WHERE id = $1::uuid", lo
    )
    kq = await _xac_minh(q, cho["payment_cycle_id"])
    assert (kq["status"], kq["can_doi_soat"]) == ("PAID", True)
    assert await _so_dong(q, "SALE") == 0
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM event_log"
            " WHERE event_type = 'payment.sale_not_applied'"
            " AND payload->>'payment_cycle_id' = $1",
            cho["payment_cycle_id"],
        )
        == 1
    )
    with pytest.raises(ValidationError):
        await _giao(q, rx, lo, 1)


# ── Giao thuốc: vật lý giảm, khả dụng không giảm lần hai ───────────────────


async def test_giao_sau_khi_thu_ton_vat_ly_giam_kha_dung_khong_giam_lan_hai(
    q: Quay,
) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 4)
    assert (await _ton(q, lo), await _kd(q, lo)) == (96, 90)
    kq = await _giao(q, rx, lo, 6)
    assert kq["dispense_status"] == "CAP_DU"
    assert (await _ton(q, lo), await _kd(q, lo)) == (90, 90)
    # DISPENSE mang đúng phân lô + lần thu.
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = 'DISPENSE'"
            " AND drug_batch_id = $1::uuid AND allocation_id IS NOT NULL"
            " AND payment_cycle_id IS NOT NULL",
            lo,
        )
        == 2
    )


async def test_chua_thu_tien_thi_khong_giao(q: Quay) -> None:
    rx, _, lo = await _san_sang(q)
    with pytest.raises(ConflictError, match="chưa thu"):
        await _giao(q, rx, lo, 1)
    await _thu(q, "QR")  # chờ xác minh cũng chưa phải đã thu
    with pytest.raises(ConflictError, match="chưa thu"):
        await _giao(q, rx, lo, 1)


async def test_giao_vuot_so_da_ban_hoac_sai_lo_bi_tu_choi(q: Quay) -> None:
    rx, drug, lo = await _san_sang(q, 10, 100)
    khac = await _nhap_lo(q, drug, 100)
    await _thu(q)
    with pytest.raises(ValidationError, match="còn 10 chưa giao"):
        await _giao(q, rx, lo, 11)
    with pytest.raises(ValidationError, match="không nằm trong các lô đã bán"):
        await _giao(q, rx, khac, 1)
    assert await _ton(q, lo) == 100 and await _ton(q, khac) == 100


# ── Huỷ phiếu ─────────────────────────────────────────────────────────────


async def test_huy_phieu_truoc_khi_giao_dao_ban_dung_mot_lan(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    lan = await _thu(q)
    assert await _kd(q, lo) == 90
    await _huy_phieu(q, lan["payment_cycle_id"])
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 100)
    assert await _so_dong(q, "SALE_REVERSAL", lo) == 1
    await _huy_phieu(q, lan["payment_cycle_id"])  # gửi lại
    assert await _so_dong(q, "SALE_REVERSAL", lo) == 1
    assert await _kd(q, lo) == 100
    # Thu lại (lần thu mới) bán lại đúng một lần nữa, theo kế hoạch lô chép lại.
    await _thu(q)
    assert await _kd(q, lo) == 90


async def test_huy_phieu_sau_khi_giao_khong_tu_nhap_lai_kho(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    lan = await _thu(q)
    await _giao(q, rx, lo, 4)
    await _huy_phieu(q, lan["payment_cycle_id"])
    assert await _so_dong(q, "SALE_REVERSAL") == 0
    # Vật lý: 4 đã rời quầy. Khả dụng: 6 chưa giao vẫn bị giữ tới khi CP5 xử lý.
    assert (await _ton(q, lo), await _kd(q, lo)) == (96, 90)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type ="
            " 'payment.drug_return_needed' AND payload->>'payment_cycle_id' = $1",
            lan["payment_cycle_id"],
        )
        == 1
    )


async def test_lan_thu_cu_legacy_giao_theo_luong_cu(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    # Lần thu trước CP3: không có phân lô, dựng như backfill CP2 đánh dấu.
    await q.pool.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, status, legacy, paid_at, created_at)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'thuoc', 50000, 'PAID', true,"
        " now(), now())",
        str(uuid.uuid4()),
        CLINIC,
        q.visit_id,
    )
    await _giao(q, rx, lo, 3)
    assert (await _ton(q, lo), await _kd(q, lo)) == (97, 97)
    assert (
        await q.pool.fetchval(
            "SELECT allocation_id FROM inventory_txn WHERE drug_batch_id = $1::uuid"
            " AND txn_type = 'DISPENSE'",
            lo,
        )
        is None
    )


# ── Chốt ở DB ─────────────────────────────────────────────────────────────


async def test_db_chan_ban_hai_lan_go_lo_da_ban_va_xoa_phan_lo(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    lan = await _thu(q)
    ban = await q.pool.fetchrow(
        "SELECT * FROM inventory_txn WHERE txn_type = 'SALE' AND drug_batch_id ="
        " $1::uuid",
        lo,
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " ref_type, ref_id, performed_by_staff_id, payment_cycle_id,"
            " allocation_id) VALUES ($1, $2, 'SALE', $3, 'payment_cycle', $4, $5,"
            " $4, $6)",
            ban["clinic_id"],
            ban["drug_batch_id"],
            ban["quantity"],
            ban["payment_cycle_id"],
            ban["performed_by_staff_id"],
            ban["allocation_id"],
        )
    with pytest.raises(asyncpg.CheckViolationError, match="đang bán"):
        await q.pool.execute(
            "UPDATE prescription_allocation SET released_at = now(),"
            " released_by = created_by, release_reason = 'lách'"
            " WHERE id = $1::uuid",
            ban["allocation_id"],
        )
    with pytest.raises(asyncpg.PostgresError, match="không xoá"):
        await q.pool.execute(
            "DELETE FROM prescription_allocation WHERE id = $1::uuid",
            ban["allocation_id"],
        )
    # Đảo bán khi lần thu chưa huỷ phiếu: DB từ chối.
    with pytest.raises(asyncpg.CheckViolationError, match="SALE_REVERSAL"):
        await q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " ref_type, ref_id, performed_by_staff_id, payment_cycle_id,"
            " allocation_id, reverses_txn_id) VALUES ($1, $2, 'SALE_REVERSAL', $3,"
            " 'payment_cycle', $4, $5, $4, $6, $7)",
            ban["clinic_id"],
            ban["drug_batch_id"],
            -ban["quantity"],
            lan["payment_cycle_id"],
            ban["performed_by_staff_id"],
            ban["allocation_id"],
            ban["id"],
        )


async def test_bac_si_luu_lai_khong_xoa_dong_da_chon_lo(q: Quay) -> None:
    from tests.services.test_tien_thuoc_cp2_db import _luu_don

    rx, _, _ = await _san_sang(q)
    ten, sl = (
        await q.pool.fetchval(
            "SELECT drug_name_raw FROM prescription WHERE id = $1::uuid", rx
        ),
        "10 viên",
    )
    await _luu_don(
        q, [{"id": rx, "drug_name": ten, "quantity": sl, "dosage": "ngày 2 viên"}]
    )
    assert (
        await q.pool.fetchval(
            "SELECT dosage_instructions FROM prescription WHERE id = $1::uuid", rx
        )
        == "ngày 2 viên"
    )
    with pytest.raises(ConflictError, match="đã chọn lô"):
        await _luu_don(q, [])  # bỏ dòng đã chọn lô


async def test_doi_thuoc_hoac_giam_so_mua_khi_da_chon_lo_bi_chan(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10)
    ph = PharmacyService(q.pool)
    with pytest.raises(ConflictError, match="đã chọn lô"):
        await ph.xac_dinh_thuoc(
            identity=q.duoc_si,
            prescription_id=rx,
            drug_catalog_id=await _thuoc(q, ten=f"Khác {q.duoi}"),
        )
    with pytest.raises(ValidationError, match="bỏ bớt lô"):
        await ph.khai_so_luong_mua(identity=q.duoc_si, prescription_id=rx, so_luong=5)
    with pytest.raises(asyncpg.CheckViolationError, match="gỡ phân lô"):
        await q.pool.execute(
            "UPDATE prescription SET purchased_qty = 5 WHERE id = $1::uuid", rx
        )


async def test_hai_luot_cheo_lo_thu_cung_luc_khong_tac(q: Quay) -> None:
    """Lượt 1 chọn X rồi Y, lượt 2 chọn Y rồi X — khoá lô theo id nên không
    khoá chéo nhau (deadlock)."""
    rx, drug = await _dong_da_xac_dinh(q, 4)
    x, y = await _nhap_lo(q, drug, 100), await _nhap_lo(q, drug, 100)
    await _chon(q, rx, x, 2)
    await _chon(q, rx, y, 2)
    q2 = await tao_quay(q.pool)
    rx2 = await _don(q2, 4)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q2.duoc_si, prescription_id=rx2, drug_catalog_id=drug
    )
    await _chon(q2, rx2, y, 2)
    await _chon(q2, rx2, x, 2)
    for _ in range(5):
        kq = await asyncio.gather(_thu(q), _thu(q2), return_exceptions=True)
        assert all(isinstance(k, dict) for k in kq), kq
    assert (await _kd(q, x), await _kd(q, y)) == (96, 96)
