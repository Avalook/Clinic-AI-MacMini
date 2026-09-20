"""Contract tiền–thuốc CP5 (19/09/2026): huỷ phiếu ≠ hoàn tiền ≠ khách trả thuốc.

Ma trận:
  R  hoàn tiền — theo dòng ảnh chụp, máy chủ tính tiền, không đụng kho;
  U  huỷ phần chưa giao — lệnh kho, cần căn cứ (huỷ phiếu / hoàn xong đủ);
  T  khách trả thuốc — trỏ DISPENSE gốc, vật lý tăng, chưa bán lại được.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _giao,
    _huy_phieu,
    _kd,
    _san_sang,
    _so_dong,
    _thu,
    _ton,
    _xac_minh,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ql(q: Quay) -> Any:
    """Quản lý — vai hoàn tiền TẠM THỜI (HOLD J4)."""
    return dataclasses.replace(
        q.thu_ngan, role=ClinicRole.MANAGEMENT, vai_tai_khoan=None
    )


async def _dong_thuoc(q: Quay, cycle: str) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
            " AND source_type = 'prescription'",
            cycle,
        )
    )


async def _hoan(
    q: Quay, cycle: str, so: Any, method: str = "CASH", kind: str = "thuoc", **kw: Any
) -> dict[str, Any]:
    dong = kw.get("dong") or [
        {"payment_bill_line_id": await _dong_thuoc(q, cycle), "so_luong": so}
    ]
    return await HoanTienService(q.pool).tao(
        identity=kw.get("identity") or _ql(q),
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind=kind,
        dong=dong,
        method=method,
        reason="Khách không lấy phần còn lại",
    )


async def _da_thu_giao(q: Quay, giao: int = 3) -> tuple[str, str, str]:
    """Đơn 10 viên × 5.000đ, thu tiền mặt, giao `giao` viên."""
    rx, _, lo = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    if giao:
        await _giao(q, rx, lo, giao)
    return rx, lo, lan


async def _huy_cg(q: Quay, rx: str) -> dict[str, Any]:
    return await PharmacyService(q.pool).huy_phan_chua_giao(
        identity=q.duoc_si, prescription_id=rx, ly_do="Khách không lấy phần còn lại"
    )


async def _xuat(q: Quay, rx: str) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT id::text FROM inventory_txn WHERE txn_type = 'DISPENSE'"
            " AND ref_id = $1::uuid ORDER BY performed_at LIMIT 1",
            rx,
        )
    )


async def _tra(q: Quay, xuat: str, so: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si, dispense_txn_id=xuat, so_luong=so, ly_do="Khách dị ứng"
    )


# ══ R — HOÀN TIỀN ═════════════════════════════════════════════════════════


async def test_r1_hoan_tien_mat_may_chu_tinh_tien_khong_dung_kho(q: Quay) -> None:
    _, lo, lan = await _da_thu_giao(q, 3)
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    kq = await _hoan(q, lan, 7)
    assert (kq["status"], kq["amount"]) == ("COMPLETED", 35_000)
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)  # không đụng kho
    # Lần thu gốc KHÔNG bị viết lại thành "chưa từng thu".
    assert (
        await q.pool.fetchval(
            "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid", lan
        )
        == "PAID"
    )


async def test_r2_hoan_vuot_so_da_thu_bi_chan_ca_o_db(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    await _hoan(q, lan, 6)
    with pytest.raises(ConflictError, match="chỉ còn hoàn được 4"):
        await _hoan(q, lan, 5)
    rid = str(uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="vượt"):
        async with q.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO payment_refund (refund_id, clinic_id, visit_id, kind,"
                    " payment_cycle_id, amount, status, method, reason, created_by)"
                    " VALUES ($1, $2, $3, 'thuoc', $4, 25000, 'PENDING', 'TRANSFER',"
                    " 'ghi thẳng', $5)",
                    rid,
                    CLINIC,
                    q.visit_id,
                    lan,
                    q.thu_ngan.staff_id,
                )
                await conn.execute(
                    "INSERT INTO payment_refund_line (clinic_id, refund_id,"
                    " payment_cycle_id, payment_bill_line_id, quantity, amount)"
                    " VALUES ($1, $2, $3, $4, 5, 25000)",
                    CLINIC,
                    rid,
                    lan,
                    await _dong_thuoc(q, lan),
                )


async def test_r2b_so_tien_phai_bang_so_luong_nhan_don_gia_va_tong_dong(
    q: Quay,
) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    dong = await _dong_thuoc(q, lan)

    async def ghi(tien_dau: int, tien_dong: int) -> None:
        rid = str(uuid.uuid4())
        async with q.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO payment_refund (refund_id, clinic_id, visit_id, kind,"
                    " payment_cycle_id, amount, status, method, reason, created_by)"
                    " VALUES ($1, $2, $3, 'thuoc', $4, $5, 'PENDING', 'TRANSFER',"
                    " 'ghi thẳng', $6)",
                    rid,
                    CLINIC,
                    q.visit_id,
                    lan,
                    tien_dau,
                    q.thu_ngan.staff_id,
                )
                await conn.execute(
                    "INSERT INTO payment_refund_line (clinic_id, refund_id,"
                    " payment_cycle_id, payment_bill_line_id, quantity, amount)"
                    " VALUES ($1, $2, $3, $4, 1, $5)",
                    CLINIC,
                    rid,
                    lan,
                    dong,
                    tien_dong,
                )

    with pytest.raises(asyncpg.CheckViolationError, match="số lượng × đơn giá"):
        await ghi(1, 1)  # 1 viên × 5.000đ ≠ 1đ
    with pytest.raises(asyncpg.CheckViolationError, match="tổng dòng"):
        await ghi(9_000, 5_000)  # đầu khoản ≠ tổng dòng (kiểm lúc commit)


async def test_r3_dong_khong_thuoc_lan_thu_hoac_doi_tac_bi_tu_choi(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    with pytest.raises(ValidationError, match="không thuộc hoá đơn"):
        await _hoan(
            q, lan, 1, dong=[{"payment_bill_line_id": str(uuid.uuid4()), "so_luong": 1}]
        )


async def test_r4_chuyen_khoan_cho_roi_xac_nhan_idempotent(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    kq = await _hoan(q, lan, 2, method="TRANSFER")
    assert kq["status"] == "PENDING"
    ht = HoanTienService(q.pool)
    for _ in range(2):  # gửi lại cùng mã → như cũ
        xn = await ht.xac_nhan(
            identity=_ql(q), refund_id=kq["refund_id"], reference="FT123"
        )
        assert xn["status"] == "COMPLETED"
    with pytest.raises(ConflictError, match="mã khác"):
        await ht.xac_nhan(identity=_ql(q), refund_id=kq["refund_id"], reference="KHAC9")
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE payment_refund SET status = 'CANCELLED' WHERE refund_id = $1::uuid",
            kq["refund_id"],
        )


async def test_r5_huy_yeu_cau_tra_lai_so_luong_that_bai_la_trang_thai_rieng(
    q: Quay,
) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    ht = HoanTienService(q.pool)
    a = await _hoan(q, lan, 10, method="QR")
    await ht.dong(
        identity=_ql(q),
        refund_id=a["refund_id"],
        trang_thai="CANCELLED",
        reason="Khách đổi ý, không cần hoàn",
    )
    b = await _hoan(q, lan, 10, method="QR")
    await ht.dong(
        identity=_ql(q),
        refund_id=b["refund_id"],
        trang_thai="FAILED",
        reason="Ngân hàng từ chối lệnh chuyển",
    )
    trang_thai = await q.pool.fetch(
        "SELECT status FROM payment_refund WHERE payment_cycle_id = $1::uuid"
        " ORDER BY created_at",
        lan,
    )
    assert [r["status"] for r in trang_thai] == ["CANCELLED", "FAILED"]
    assert (await _hoan(q, lan, 10))["status"] == "COMPLETED"


async def test_r6_hoan_duoc_lan_thu_da_huy_phieu_khong_hoan_lan_chua_tung_thu(
    q: Quay,
) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    await _huy_phieu(q, lan)
    assert (await _hoan(q, lan, 10))["status"] == "COMPLETED"
    # Lần chuyển khoản chờ rồi huỷ chờ — chưa từng thu.
    cho = await _thu(q, "QR")
    await PaymentService(q.pool).huy_cho_xac_minh(
        payment_cycle_id=cho["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Khách không chuyển",
        identity=q.thu_ngan,
    )
    with pytest.raises(ConflictError, match="chưa từng thu"):
        await _hoan(q, cho["payment_cycle_id"], 1)


async def test_r7_huy_phieu_sau_khi_da_hoan_van_duoc(q: Quay) -> None:
    _, lo, lan = await _da_thu_giao(q, 0)
    await _hoan(q, lan, 4)
    kq = await _huy_phieu(q, lan)
    assert kq["status"] == "VOIDED"
    # Huỷ phiếu đảo bán ĐÚNG MỘT LẦN, không lệ thuộc khoản hoàn.
    assert await _so_dong(q, "SALE_REVERSAL", lo) == 1
    assert await _kd(q, lo) == 100


async def test_r8_chi_vai_hoan_tam_thoi_duoc_hoan(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    with pytest.raises(SafetyGateError, match="tạm thời chỉ Quản lý"):
        await _hoan(q, lan, 1, identity=q.thu_ngan)


async def test_r9_hai_khoan_hoan_dong_thoi_khong_vuot(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    kq = await asyncio.gather(
        *(_hoan(q, lan, 10) for _ in range(4)), return_exceptions=True
    )
    assert sum(isinstance(k, dict) for k in kq) == 1
    assert (
        await q.pool.fetchval(
            "SELECT sum(l.quantity) FROM payment_refund_line l JOIN payment_refund r"
            " USING (refund_id) WHERE r.payment_cycle_id = $1::uuid",
            lan,
        )
        == 10
    )


async def test_r10_hoan_sau_dong_luot_khong_mo_lai_luot(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    await q.pool.execute(
        "UPDATE visit SET closed_at = now() - interval '1 minute'"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    await _hoan(q, lan, 2)
    # Lượt vẫn đóng — hoàn tiền không mở lại lượt (D4).
    assert await q.pool.fetchval(
        "SELECT closed_at IS NOT NULL FROM visit WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    ls = await CashierBoardService(q.pool).giao_dich(identity=_ql(q), tu=None, den=None)
    g = next(x for x in ls["giao_dich"] if x["id"] == lan)
    assert ls["co_quyen_hoan"] is True
    k = g["hoan"]["khoan_hoan"][0]
    assert (k["status"], int(k["amount"]), k["sau_khi_dong_luot"]) == (
        "COMPLETED",
        10_000,
        True,
    )
    assert g["hoan"]["dong_hoan_duoc"][0]["con_hoan"] == 8


# ══ U — HUỶ PHẦN CHƯA GIAO ═══════════════════════════════════════════════


async def test_u1_chua_hoan_thi_khong_huy_hoan_du_thi_huy_dung_mot_lan(q: Quay) -> None:
    rx, lo, lan = await _da_thu_giao(q, 3)
    assert (await _ton(q, lo), await _kd(q, lo)) == (97, 90)
    with pytest.raises(ConflictError, match="căn cứ"):
        await _huy_cg(q, rx)
    await _hoan(q, lan, 7)
    assert (await _huy_cg(q, rx))["da_huy"] == "7"
    assert (await _ton(q, lo), await _kd(q, lo)) == (97, 97)
    with pytest.raises(ConflictError, match="không còn phần"):
        await _huy_cg(q, rx)
    with pytest.raises(ConflictError, match="đã huỷ"):
        await _giao(q, rx, lo, 1)  # không giao thêm sau khi đã huỷ
    kq = await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    assert kq["dispensed_qty"] == 3


async def test_u2_hoan_thieu_thi_van_chua_huy_duoc(q: Quay) -> None:
    rx, _, lan = await _da_thu_giao(q, 3)
    await _hoan(q, lan, 5)
    with pytest.raises(ConflictError, match="căn cứ"):
        await _huy_cg(q, rx)
    # Hoàn đang chờ (chưa COMPLETED) chưa là căn cứ.
    await _hoan(q, lan, 2, method="TRANSFER")
    with pytest.raises(ConflictError, match="căn cứ"):
        await _huy_cg(q, rx)


async def test_u3_huy_phieu_sau_khi_giao_mot_phan_la_can_cu(q: Quay) -> None:
    rx, lo, lan = await _da_thu_giao(q, 3)
    await _huy_phieu(q, lan)
    assert await _so_dong(q, "SALE_REVERSAL") == 0  # huỷ phiếu không tự nhả
    # Lượt quay về "Chọn lô" — nhưng không được đóng dòng để bỏ lại 7 viên.
    for lenh in (
        PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx),
        PharmacyService(q.pool).tu_choi(
            identity=q.duoc_si, prescription_id=rx, ly_do="khách đổi ý"
        ),
    ):
        with pytest.raises(ConflictError, match="chưa giao"):
            await lenh
    await _huy_cg(q, rx)
    assert (await _ton(q, lo), await _kd(q, lo)) == (97, 97)


async def test_u4_man_nha_thuoc_bao_con_can_hoan_roi_mo_nut(q: Quay) -> None:
    rx, _, lan = await _da_thu_giao(q, 3)

    async def dong() -> dict[str, Any]:
        man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
        g = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
        return dict(g["dong"][0])

    d = await dong()
    assert (d["chua_giao"], d["can_hoan"]) == (Decimal(7), Decimal(7))
    assert not d["thao_tac"]["huy_chua_giao"] and not d["thao_tac"]["chot"]
    await _hoan(q, lan, 7)
    d = await dong()
    assert d["can_hoan"] == 0 and d["thao_tac"]["huy_chua_giao"]
    await _huy_cg(q, rx)
    d = await dong()
    assert d["chua_giao"] == 0 and d["thao_tac"]["chot"]
    # Phân lô vẫn là "đã bán" (đã giao 3, phần còn lại đã huỷ), không phải
    # "đã chọn, chưa thu" — và lượt không bị hiểu nhầm là cần đối soát.
    pl = d["phan_lo"][0]
    assert (pl["co_sale"], pl["da_ban"]) == (True, False)


# ══ T — KHÁCH TRẢ THUỐC ═══════════════════════════════════════════════════


async def test_t1_tra_tang_vat_ly_khong_tang_ban_duoc_khong_tu_hoan(q: Quay) -> None:
    rx, lo, _ = await _da_thu_giao(q, 4)
    assert (await _ton(q, lo), await _kd(q, lo)) == (96, 90)
    await _tra(q, await _xuat(q, rx), 2)
    assert (await _ton(q, lo), await _kd(q, lo)) == (98, 90)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = 'RETURN_RECEIVED'"
            " AND drug_batch_id = $1::uuid",
            lo,
        )
        == 1
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = 'ADJUST'"
            " AND drug_batch_id = $1::uuid",
            lo,
        )
        == 0
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_refund WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    )
    r = await q.pool.fetchrow(
        "SELECT disposition, allocation_id IS NOT NULL AS co_pl FROM drug_return"
        " WHERE prescription_id = $1::uuid",
        rx,
    )
    assert r["disposition"] is None and r["co_pl"]


async def test_t2_tra_vuot_so_da_xuat_bi_chan_ca_o_db(q: Quay) -> None:
    rx, _, _ = await _da_thu_giao(q, 4)
    x = await _xuat(q, rx)
    await _tra(q, x, 3)
    with pytest.raises(ValidationError, match="chỉ còn trả được 1"):
        await _tra(q, x, 2)
    with pytest.raises(asyncpg.CheckViolationError, match="vượt"):
        await q.pool.execute(
            "INSERT INTO drug_return (clinic_id, visit_id, prescription_id,"
            " original_dispense_txn_id, allocation_id, drug_batch_id, returned_qty,"
            " reason, returned_by)"
            " SELECT clinic_id, $2::uuid, ref_id, id, allocation_id, drug_batch_id, 2,"
            " 'ghi thẳng', $3::uuid FROM inventory_txn WHERE id = $1::uuid",
            x,
            q.visit_id,
            q.duoc_si.staff_id,
        )


async def test_t3_db_chan_tra_sai_nguon_va_thieu_dong_kho(q: Quay) -> None:
    rx, lo, _ = await _da_thu_giao(q, 4)
    ban = await q.pool.fetchval(
        "SELECT id::text FROM inventory_txn WHERE txn_type = 'SALE'"
        " AND drug_batch_id = $1::uuid",
        lo,
    )
    # Trỏ vào dòng SALE thay vì DISPENSE gốc.
    with pytest.raises(asyncpg.CheckViolationError, match="DISPENSE gốc"):
        await q.pool.execute(
            "INSERT INTO drug_return (clinic_id, visit_id, prescription_id,"
            " original_dispense_txn_id, allocation_id, drug_batch_id, returned_qty,"
            " reason, returned_by)"
            " SELECT clinic_id, $2::uuid, $4::uuid, id, allocation_id, drug_batch_id,"
            " 1, 'sai nguồn', $3::uuid FROM inventory_txn WHERE id = $1::uuid",
            ban,
            q.visit_id,
            q.duoc_si.staff_id,
            rx,
        )
    # Lần trả không có dòng RETURN_RECEIVED — DB từ chối lúc commit.
    with pytest.raises(asyncpg.CheckViolationError, match="thiếu dòng RETURN_RECEIVED"):
        await q.pool.execute(
            "INSERT INTO drug_return (clinic_id, visit_id, prescription_id,"
            " original_dispense_txn_id, allocation_id, drug_batch_id, returned_qty,"
            " reason, returned_by)"
            " SELECT clinic_id, $2::uuid, ref_id, id, allocation_id, drug_batch_id, 1,"
            " 'thiếu sổ', $3::uuid FROM inventory_txn WHERE id = $1::uuid",
            await _xuat(q, rx),
            q.visit_id,
            q.duoc_si.staff_id,
        )
    # Không có lệnh xử lý thuốc trả (HOLD J1/J2): dòng trả không sửa được.
    await _tra(q, await _xuat(q, rx), 1)
    with pytest.raises(asyncpg.PostgresError, match="HOLD J1/J2"):
        await q.pool.execute(
            "UPDATE drug_return SET disposition = 'RESTOCK',"
            " disposition_by = returned_by, disposition_at = now()"
            " WHERE prescription_id = $1::uuid",
            rx,
        )


async def test_t4_tra_thuoc_giao_theo_luong_cu(q: Quay) -> None:
    from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh

    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
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
    await _tra(q, await _xuat(q, rx), 3)
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 97)


async def test_t5_man_nha_thuoc_liet_ke_lan_giao_de_tra(q: Quay) -> None:
    rx, _, _ = await _da_thu_giao(q, 4)
    await _tra(q, await _xuat(q, rx), 1)
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    d = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)["dong"][0]
    assert [
        (x["so_luong"], x["da_tra"], x["con_tra"], x["thao_tac"]["tra"])
        for x in d["xuat"]
    ] == [(Decimal(4), Decimal(1), Decimal(3), True)]


async def test_t6_chuyen_khoan_xac_minh_roi_tra_khong_ban_lan_hai(q: Quay) -> None:
    """Ca 18: đổi phương thức / trả thuốc không làm bán thêm lần nữa."""
    rx, _, lo = await _san_sang(q, 10, 100)
    cho = await _thu(q, "TRANSFER")
    await _xac_minh(q, cho["payment_cycle_id"])
    await _giao(q, rx, lo, 10)
    await _tra(q, await _xuat(q, rx), 10)
    assert await _so_dong(q, "SALE", lo) == 1
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 90)


# ══ Review CP5 — P1-B: sổ hoàn không tự lệch sau commit; lineage lần trả ══


async def test_r11_them_dong_vao_khoan_hoan_da_commit_bi_chan(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    kq = await _hoan(q, lan, 2)  # 10.000đ, đã commit
    with pytest.raises(asyncpg.CheckViolationError, match="tổng dòng"):
        await q.pool.execute(
            "INSERT INTO payment_refund_line (clinic_id, refund_id, payment_cycle_id,"
            " payment_bill_line_id, quantity, amount)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 1, 5000)",
            CLINIC,
            kq["refund_id"],
            lan,
            await _dong_thuoc(q, lan),
        )
    assert (
        await q.pool.fetchval(
            "SELECT sum(amount) FROM payment_refund_line WHERE refund_id = $1::uuid",
            kq["refund_id"],
        )
        == 10_000
    )


async def test_r12_khong_them_dong_vao_khoan_hoan_da_dong(q: Quay) -> None:
    _, _, lan = await _da_thu_giao(q, 0)
    kq = await _hoan(q, lan, 2, method="QR")
    await HoanTienService(q.pool).dong(
        identity=_ql(q),
        refund_id=kq["refund_id"],
        trang_thai="CANCELLED",
        reason="Khách đổi ý, không cần hoàn",
    )
    with pytest.raises(asyncpg.CheckViolationError, match="còn mở"):
        await q.pool.execute(
            "INSERT INTO payment_refund_line (clinic_id, refund_id, payment_cycle_id,"
            " payment_bill_line_id, quantity, amount)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 1, 5000)",
            CLINIC,
            kq["refund_id"],
            lan,
            await _dong_thuoc(q, lan),
        )


async def test_t7_lan_tra_phai_dung_luot_cua_dong_don(q: Quay) -> None:
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    rx, _, _ = await _da_thu_giao(q, 4)
    khac = await tao_quay(q.pool)
    with pytest.raises(asyncpg.CheckViolationError, match="DISPENSE gốc"):
        await q.pool.execute(
            "INSERT INTO drug_return (clinic_id, visit_id, prescription_id,"
            " original_dispense_txn_id, allocation_id, drug_batch_id, returned_qty,"
            " reason, returned_by)"
            " SELECT clinic_id, $2::uuid, ref_id, id, allocation_id, drug_batch_id, 1,"
            " 'sai lượt', $3::uuid FROM inventory_txn WHERE id = $1::uuid",
            await _xuat(q, rx),
            khac.visit_id,
            q.duoc_si.staff_id,
        )
