"""Giảm giá theo TỔNG hoá đơn tại quầy thu (Tuyền chốt 09/10 + 13/10/2026) — DB thật.

* Giảm % / số tiền: sổ lần thu ghi gốc, giảm, lý do, người giảm; từng dòng ảnh
  chụp mang số SAU giảm (`line_total`) + phần giảm (`discount_allocated`) và tổng
  các phần đúng bằng tiền giảm.
* Giảm hết (100%) → lần thu 0đ ĐÃ THU, không có dòng chia hình thức, khách rời
  hàng chờ thu. Lần thu 0đ CHỈ tồn tại khi có giảm kèm lý do + người giảm — DB chặn
  mọi lần thu 0đ khác như trước.
* Dịch vụ giá 0đ vẫn bán bình thường (chốt 0đ như cũ), không dính giảm giá.
* Rác (lý do trống, NaN, vượt tổng…) → ValidationError, không ghi gì.
* Hoàn tiền dòng có giảm chỉ tới số đã thu thật; lượt đang ghi nợ vẫn giảm được
  (13/10/2026 — nợ đóng bằng lần thu có giảm, `test_cong_no_check_out_db`).
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.bao_cao_cuoi_ngay_service import (
    BaoCaoCuoiNgayService,
    csv_bao_cao,
)
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import KHONG_CON_KHOAN, PaymentService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_doi_tac_tu_thu_db import _gia, _nguoi_vai
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_quay_thu_mot_hoa_don_db import _cd, _dong, _kich_ban
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


async def _thu(
    q: Quay,
    sa: str,
    soi: str,
    hpv: str,
    *,
    loai: str | None = None,
    gia_tri: float | None = None,
    ly_do: str | None = "khách quen giảm theo chính sách",
    khoa: str | None = None,
    method: str = "CASH",
    qt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Thu hoá đơn 700k (khám 150 + SÂ 250 + Soi 300; HPV 900k khách trả đối tác).

    ``qt``: hoá đơn client đang nhìn — gửi lại cùng khoá thì client gửi đúng số cũ."""
    qt = qt or (await _dong(q))["quay_thu"]
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method=method,
        idempotency_key=khoa or f"gg-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi, hpv],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
        discount_type=loai,
        discount_value=gia_tri,
        discount_reason=ly_do,
    )


async def _cycle(pool: asyncpg.Pool, cycle_id: str) -> asyncpg.Record:
    row = await pool.fetchrow(
        "SELECT * FROM payment_cycle WHERE payment_cycle_id = $1::uuid", cycle_id
    )
    assert row is not None
    return row


async def _dong_anh(pool: asyncpg.Pool, cycle_id: str) -> list[Any]:
    rows: list[Any] = list(
        await pool.fetch(
            "SELECT * FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
            " ORDER BY unit_price",
            cycle_id,
        )
    )
    return rows


@pytest.mark.db
@pytest.mark.asyncio
async def test_giam_phan_tram_ghi_so_va_chia_dong(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10)
    assert kq["status"] == "PAID"
    c = await _cycle(pool, kq["payment_cycle_id"])
    assert (c["original_amount"], c["discount_amount"], c["amount"]) == (
        700_000,
        70_000,
        630_000,
    )
    assert c["discount_type"] == "PERCENT" and float(c["discount_value"]) == 10
    assert c["discount_reason"] == "khách quen giảm theo chính sách"
    assert str(c["discount_by"]) == q.thu_ngan.staff_id
    dong = await _dong_anh(pool, kq["payment_cycle_id"])
    # 150k / 250k / 300k giảm 10% → 15k / 25k / 30k; line_total là số SAU giảm.
    assert [(int(d["line_total"]), int(d["discount_allocated"])) for d in dong] == [
        (135_000, 15_000),
        (225_000, 25_000),
        (270_000, 30_000),
    ]
    assert sum(int(d["line_total"]) for d in dong) == c["amount"]
    # Tiền thật chỉ đi qua MỘT dòng chia hình thức bằng số phải thu.
    phan = await pool.fetch(
        "SELECT so_tien FROM payment_cycle_phan WHERE cycle_id = $1::uuid",
        kq["payment_cycle_id"],
    )
    assert [int(p["so_tien"]) for p in phan] == [630_000]


@pytest.mark.db
@pytest.mark.asyncio
async def test_giam_so_tien_khong_chia_tron_van_tong_dung(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="AMOUNT", gia_tri=100_001)
    c = await _cycle(pool, kq["payment_cycle_id"])
    assert (c["discount_amount"], c["amount"]) == (100_001, 599_999)
    dong = await _dong_anh(pool, kq["payment_cycle_id"])
    # Phần dư làm tròn không bị mất: tổng phần giảm = đúng số giảm.
    assert sum(int(d["discount_allocated"]) for d in dong) == 100_001
    for d in dong:
        assert int(d["line_total"]) + int(d["discount_allocated"]) == round(
            d["quantity"] * d["unit_price"]
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_giam_het_la_lan_thu_0d_da_thu(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=100, method="TRANSFER")
    assert kq["status"] == "PAID"  # 0đ không có tiền thật → không chờ xác minh CK
    c = await _cycle(pool, kq["payment_cycle_id"])
    assert (c["amount"], c["discount_amount"], c["original_amount"]) == (
        0,
        700_000,
        700_000,
    )
    assert c["method"] == "CASH" and c["status"] == "PAID"
    n_phan = await pool.fetchval(
        "SELECT count(*) FROM payment_cycle_phan WHERE cycle_id = $1::uuid",
        kq["payment_cycle_id"],
    )
    assert n_phan == 0
    assert (
        await pool.fetchval(
            "SELECT amount FROM payment WHERE id = $1::uuid", c["payment_id"]
        )
        == 0
    )
    # Khách rời hàng chờ thu như đã thu.
    assert q.visit_id not in (await _dong(q))["_bang"]["ds_cho_thu"]
    dong = await _dong_anh(pool, kq["payment_cycle_id"])
    assert sum(int(d["line_total"]) for d in dong) == 0
    assert sum(int(d["discount_allocated"]) for d in dong) == 700_000


@pytest.mark.db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loai", "gia_tri", "ly_do"),
    [
        ("PERCENT", 10, None),  # thiếu lý do
        ("PERCENT", 10, "   "),  # lý do toàn khoảng trắng
        ("PERCENT", 10, "x" * 501),  # lý do quá dài
        ("PERCENT", 101, "vượt trăm phần"),
        ("PERCENT", 0, "giảm không đồng"),
        ("AMOUNT", -5, "giá trị âm"),
        ("AMOUNT", 700_001, "vượt tổng hoá đơn"),
        ("AMOUNT", float("nan"), "không phải số"),
        ("AMOUNT", float("inf"), "vô cực"),
        ("AMOUNT", 0.4, "làm tròn còn 0đ"),
        ("GIAM_LA", 10, "loại lạ"),
        (None, 10, "thiếu loại"),
        ("PERCENT", None, "thiếu giá trị"),
    ],
)
async def test_giam_rac_bi_tu_choi_va_khong_ghi_gi(
    pool: asyncpg.Pool, loai: str | None, gia_tri: float | None, ly_do: str | None
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    with pytest.raises(ValidationError):
        await _thu(q, sa, soi, hpv, loai=loai, gia_tri=gia_tri, ly_do=ly_do)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_gui_lai_cung_khoa_khong_giam_hai_lan(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    khoa = f"gg-lai-{uuid.uuid4().hex}"
    qt = (await _dong(q))["quay_thu"]
    a = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10, khoa=khoa, qt=qt)
    b = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10, khoa=khoa, qt=qt)
    assert a["payment_cycle_id"] == b["payment_cycle_id"]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 1
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_db_chi_cho_thu_0d_khi_co_giam_ly_do_nguoi_giam(
    pool: asyncpg.Pool,
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10)
    c = await _cycle(pool, kq["payment_cycle_id"])
    chen = (
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, bill_revision, method, status, created_by, paid_at, confirmed_by,"
        " discount_type, discount_value, discount_amount, discount_reason,"
        " discount_by, original_amount)"
        " VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 'dich_vu', $3, 'rev',"
        " 'CASH', 'PAID', $4::uuid, now(), $4::uuid, $5, $6, $7, $8, $9::uuid, $10)"
    )
    nguoi = q.thu_ngan.staff_id
    # 0đ không giảm → chặn như trước.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            chen, CLINIC, q.visit_id, 0, nguoi, None, None, 0, None, None, None
        )
    # Có giảm nhưng thiếu lý do / người giảm → chặn.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            chen, CLINIC, q.visit_id, 0, nguoi, "AMOUNT", 5, 5, "  ", nguoi, 5
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            chen, CLINIC, q.visit_id, 0, nguoi, "AMOUNT", 5, 5, "lý do", None, 5
        )
    # Số học sai: amount ≠ gốc − giảm.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            chen, CLINIC, q.visit_id, 100, nguoi, "AMOUNT", 5, 5, "lý do", nguoi, 5
        )
    # Cột giảm giá đã ghi thì không sửa được.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE payment_cycle SET discount_reason = 'đổi lý do'"
            " WHERE payment_cycle_id = $1::uuid",
            c["payment_cycle_id"],
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_dich_vu_gia_0d_van_ban_binh_thuong_va_khong_giam(
    pool: asyncpg.Pool,
) -> None:
    """Dịch vụ phòng khám thu có giá 0đ (hệ thống ghi vậy) → chốt 0đ như cũ; hoá
    đơn chỉ gồm khoản 0đ thì cũng không có gì để giảm."""
    q = await tao_quay(pool)
    await pool.execute(
        "UPDATE service_type SET di_thang_phong = true WHERE clinic_id = $1::uuid"
        " AND code = $2",
        CLINIC,
        f"KT-{q.duoi}",
    )
    await _gia(q, f"MIEN-{q.duoi}", 0, "DICHVU-SIEUAM", ben="CLINIC")
    mien = await _cd(q, f"MIEN-{q.duoi}")
    d = await _dong(q)
    assert d["quay_thu"]["tong"] == 0
    chon = {
        "order_ids_seen": [mien],
        "selected_order_ids": [mien],
        "expected_selection_revision": d["quay_thu"]["lua_chon"]["revision"],
    }

    async def thu(**giam: Any) -> dict[str, Any]:
        return await PaymentService(pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
            method="CASH",
            idempotency_key=f"gg-{uuid.uuid4().hex}",
            chon=chon,
            **giam,
        )

    # Muốn giảm trên hoá đơn 0đ: vẫn đi đường chốt 0đ, KHÔNG sinh lần thu giảm.
    kq = await thu(
        discount_type="PERCENT", discount_value=50, discount_reason="giảm thử"
    )
    assert kq["status"] == KHONG_CON_KHOAN and kq["payment_cycle_id"] is None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_hoa_don_co_dong_0d_va_dong_co_gia_giam_het(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await pool.execute(
        "UPDATE service_type SET di_thang_phong = true WHERE clinic_id = $1::uuid"
        " AND code = $2",
        CLINIC,
        f"KT-{q.duoi}",
    )
    await _gia(q, f"MIEN-{q.duoi}", 0, "DICHVU-SIEUAM", ben="CLINIC")
    await _gia(q, f"SA-{q.duoi}", 250_000, "DICHVU-SIEUAM", ben="CLINIC")
    mien = await _cd(q, f"MIEN-{q.duoi}")
    sa = await _cd(q, f"SA-{q.duoi}")
    qt = (await _dong(q))["quay_thu"]
    assert qt["tong"] == 250_000
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=f"gg-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": [mien, sa],
            "selected_order_ids": [mien, sa],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
        discount_type="PERCENT",
        discount_value=100,
        discount_reason="miễn phí cho người nhà",
    )
    dong = {
        int(d["unit_price"]): d for d in await _dong_anh(pool, kq["payment_cycle_id"])
    }
    # Dòng 0đ giữ nguyên (không nhận phần giảm); dòng 250k giảm hết.
    assert int(dong[0]["discount_allocated"]) == 0
    sa_dong = dong[250_000]
    assert (int(sa_dong["line_total"]), int(sa_dong["discount_allocated"])) == (
        0,
        250_000,
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_hoan_dong_co_giam_chi_toi_so_da_thu(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10)
    cycle = kq["payment_cycle_id"]
    dong_soi = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_id = $2",
        cycle,
        soi,
    )
    ql = await _nguoi_vai(q, "MANAGEMENT")
    svc = HoanTienService(pool)
    await svc.tao(
        identity=ql,
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong_soi, "so_luong": 1}],
        method="CASH",
        reason="khách không làm soi",
    )
    # Soi 300k đã giảm 30k → thu thật 270k → chỉ hoàn 270k, không phải 300k.
    assert (
        await pool.fetchval(
            "SELECT amount FROM payment_refund WHERE payment_cycle_id = $1::uuid",
            cycle,
        )
        == 270_000
    )
    # Hoàn lần nữa cùng dòng: hết số lượng → từ chối.
    with pytest.raises(ConflictError):
        await svc.tao(
            identity=ql,
            payment_cycle_id=cycle,
            visit_id=q.visit_id,
            kind="dich_vu",
            dong=[{"payment_bill_line_id": dong_soi, "so_luong": 1}],
            method="CASH",
            reason="hoàn lại lần hai",
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_luot_dang_ghi_no_van_giam_duoc(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    await pool.execute(
        "INSERT INTO cong_no (clinic_id, visit_id, clinic_patient_id, so_tien,"
        " ly_do, ghi_boi) SELECT $1::uuid, $2::uuid, v.clinic_patient_id, 700000,"
        " 'khách xin ghi nợ', $3::uuid FROM visit v WHERE v.visit_id = $2::uuid",
        CLINIC,
        q.visit_id,
        q.thu_ngan.staff_id,
    )
    # Bảng quầy báo lượt đang nợ — màn hiện nhãn "Đang ghi nợ".
    bang = await CashierBoardService(pool).board(identity=q.thu_ngan, modes=["dich_vu"])
    luot = next(i for i in bang["items"] if i["visit_id"] == q.visit_id)
    assert luot["quay_thu"]["dang_no"]["so_tien"] == 700_000
    assert luot["quay_thu"]["dang_no"]["ly_do"] == "khách xin ghi nợ"
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10)
    assert kq["status"] == "PAID"


@pytest.mark.db
@pytest.mark.asyncio
async def test_phieu_in_co_khoi_giam_gia_va_phieu_khong_giam_thi_khong(
    pool: asyncpg.Pool,
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    kq = await _thu(q, sa, soi, hpv, loai="PERCENT", gia_tri=10)
    phieu = await QuayThuService(pool).phieu(
        identity=q.thu_ngan, id_=kq["payment_cycle_id"]
    )
    assert phieu["tong"] == 630_000
    gg = phieu["giam_gia"]
    assert (gg["tong_goc"], gg["giam"], gg["loai"], gg["gia_tri"]) == (
        700_000,
        70_000,
        "PERCENT",
        10.0,
    )
    assert gg["ly_do"] == "khách quen giảm theo chính sách"
    # Từng dòng in là số SAU giảm → cộng lại đúng TỔNG THU.
    assert sum(d["thanh_tien"] for d in phieu["dong"]) == 630_000

    q2, sa2, soi2, hpv2 = await _kich_ban(pool)
    kq2 = await _thu(q2, sa2, soi2, hpv2)
    phieu2 = await QuayThuService(pool).phieu(
        identity=q2.thu_ngan, id_=kq2["payment_cycle_id"]
    )
    assert phieu2["giam_gia"] is None and phieu2["tong"] == 700_000


@pytest.mark.db
@pytest.mark.asyncio
async def test_bao_cao_cuoi_ngay_co_khoi_giam_gia_va_thuc_thu_khop(
    pool: asyncpg.Pool,
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    svc = BaoCaoCuoiNgayService(pool)
    truoc = await svc.bao_cao(identity=ql)
    kq = await _thu(q, sa, soi, hpv, loai="AMOUNT", gia_tri=50_000)
    sau = await svc.bao_cao(identity=ql)
    # Thực thu tăng đúng số THẬT đã thu (650k), không phải 700k.
    assert sau["tong"]["thuc_thu"] - truoc["tong"]["thuc_thu"] == 650_000
    dong = [d for d in sau["giam_gia"]["dong"] if d["id"] == kq["payment_cycle_id"]]
    assert len(dong) == 1
    d = dong[0]
    assert (d["tong_goc"], d["giam"], d["thu_that"]) == (700_000, 50_000, 650_000)
    assert d["ly_do"] and d["nguoi_giam"] and d["khach"]
    assert sau["giam_gia"]["giam"] - truoc["giam_gia"]["giam"] == 50_000
    out = csv_bao_cao(sau)
    assert "Lý do giảm" in out and "khách quen giảm theo chính sách" in out
