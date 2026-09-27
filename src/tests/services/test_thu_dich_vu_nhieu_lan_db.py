"""Lifecycle v1 Slice 3 — Outstanding Bill + thu dịch vụ nhiều lần + FinanceGate.

Chạy trên Postgres dùng một lần (DATABASE_URL_TEST). Mỗi test dựng lượt, bảng giá
và chỉ định mang đuôi ngẫu nhiên (``tao_quay`` của CP1) — không đụng dữ liệu của
test khác.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import BillChangedError, ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services import finance_gate as fg
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_selection_service import ServiceSelectionService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_tien_thuoc_cp1_db import Quay, _gia_dv, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def q(pool: asyncpg.Pool) -> Quay:
    return await tao_quay(pool)


async def _cd(
    q: Quay,
    ten: str,
    gia: int | None = 200_000,
    *,
    ben: str = "CLINIC",
    selection: str | None = "SELECTED",
    exec_status: str = "authorized",
    co_gia: bool = True,
    **extra: Any,
) -> str:
    """Một chỉ định chính thức kèm dòng giá riêng (mã mang đuôi ngẫu nhiên)."""
    ma = f"{ten}-{q.duoi}-{uuid.uuid4().hex[:4]}"
    async with q.pool.acquire() as conn:
        if co_gia:
            await _gia_dv(conn, ma, f"{ten} {q.duoi}", gia, ben)
        cols = {"selection_status": selection, "exec_status": exec_status, **extra}
        names = ", ".join(cols)
        params = ", ".join(f"${i + 7}" for i in range(len(cols)))
        return str(
            await conn.fetchval(
                f"""
                INSERT INTO service_order (clinic_id, visit_id, consultation_id,
                    service_code, service_name, node_code, recorded_by,
                    authorized_by, authorized_at, {names})
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'DICHVU-SIEUAM',
                        $6::uuid, $6::uuid, now(), {params})
                RETURNING id::text
                """,  # noqa: S608 — tên cột cố định trong test
                CLINIC,
                q.visit_id,
                q.consultation_id,
                ma,
                f"{ten} {q.duoi}",
                q.bac_si.staff_id,
                *cols.values(),
            )
        )


async def _hd(q: Quay) -> Any:
    async with q.pool.acquire() as conn:
        return await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="dich_vu"
        )


def _nguon(hd: Any) -> set[tuple[str, str]]:
    return {(d.source_type, d.source_id) for d in hd.dong}


async def _thu(
    q: Quay,
    method: str = "CASH",
    *,
    key: str | None = None,
    who: StaffIdentity | None = None,
    bill_revision: str | None = None,
) -> dict[str, Any]:
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=who or q.thu_ngan,
        bill_revision=bill_revision,
        method=method,
        idempotency_key=key or f"thu-{uuid.uuid4().hex}",
    )


async def _dong_cua(q: Quay, cycle: str) -> set[tuple[str, str]]:
    rows = await q.pool.fetch(
        "SELECT source_type, source_id FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid",
        cycle,
    )
    return {(r["source_type"], r["source_id"]) for r in rows}


async def _gate(q: Quay, *ids: str) -> dict[str, fg.FinanceDecision]:
    async with q.pool.acquire() as conn:
        return await fg.states_for_orders(conn, CLINIC, list(ids))


def _exam(q: Quay) -> tuple[str, str]:
    return ("exam", f"exam-{q.visit_id}")


async def _quan_ly(q: Quay) -> StaffIdentity:
    async with q.pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        return await _nguoi(conn, loc, "MANAGEMENT")


# ---------------------------------------------------------------------------
# 1–3. Golden: lần thu #1 khám + SA, bác sĩ thêm XN, lần thu #2 chỉ XN
# ---------------------------------------------------------------------------


async def test_golden_hai_lan_thu_chi_thu_phan_con_no(q: Quay) -> None:
    sa = await _cd(q, "SA", 300_000)
    hd1 = await _hd(q)
    assert _nguon(hd1) == {_exam(q), ("service_order", sa)}
    assert hd1.tong == 150_000 + 300_000
    c1 = (await _thu(q))["payment_cycle_id"]

    # Bác sĩ thêm XN, khách chọn làm (qua ConfirmServiceSelection).
    xn = await _cd(q, "XN", 120_000, selection="PENDING")
    await ServiceSelectionService(q.pool).confirm(
        visit_id=q.visit_id,
        order_ids_seen=[xn],
        selected_order_ids=[xn],
        expected_selection_revision=0,
        identity=q.thu_ngan,
        idempotency_key=f"sel-{uuid.uuid4().hex}",
    )
    hd2 = await _hd(q)
    assert _nguon(hd2) == {("service_order", xn)}  # KHÔNG thu lại khám / SA
    assert hd2.tong == 120_000
    c2 = (await _thu(q))["payment_cycle_id"]

    cycles = await q.pool.fetch(
        "SELECT payment_cycle_id::text AS id, status, amount FROM payment_cycle"
        " WHERE visit_id = $1::uuid AND kind = 'dich_vu' ORDER BY created_at",
        q.visit_id,
    )
    assert [(r["id"], r["status"], r["amount"]) for r in cycles] == [
        (c1, "PAID", 450_000),
        (c2, "PAID", 120_000),
    ]
    assert await _dong_cua(q, c1) == {_exam(q), ("service_order", sa)}
    assert await _dong_cua(q, c2) == {("service_order", xn)}
    assert (await _hd(q)).dong == []

    # Sự thật tài chính là sổ, không phải hình chiếu: SA phủ bởi lần #1 dù
    # hình chiếu `payment` nay trỏ lần #2.
    proj = await q.pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment WHERE visit_id = $1::uuid"
        " AND kind = 'dich_vu'",
        q.visit_id,
    )
    assert proj == c2
    g = await _gate(q, sa, xn)
    assert (g[sa].finance_state, g[sa].coverage_cycle_id) == ("PAID", c1)
    assert (g[xn].finance_state, g[xn].coverage_cycle_id) == ("PAID", c2)
    assert g[sa].financially_ready and g[xn].financially_ready

    # Ảnh chụp lần #1 bất biến qua lần #2.
    assert await _dong_cua(q, c1) == {_exam(q), ("service_order", sa)}
    ev = await q.pool.fetch(
        "SELECT event_type FROM event_log WHERE payload->>'visit_id' = $1"
        " AND event_type LIKE 'payment.%' ORDER BY recorded_at",
        q.visit_id,
    )
    assert [e["event_type"] for e in ev] == ["payment.confirmed", "payment.confirmed"]


async def test_chua_chon_khong_chon_va_dong_cu_null_khong_vao_hoa_don(
    q: Quay,
) -> None:
    await _cd(q, "PEND", selection="PENDING")
    await _cd(q, "NOT", selection="NOT_SELECTED")
    await _cd(q, "LEGACY", selection=None)
    await _cd(q, "HUY", exec_status="cancelled")
    await _cd(q, "GIAN", execution_status="INTERRUPTED")
    await _cd(q, "DALAM", execution_status="COMPLETED")
    await _cd(q, "DT", ben="EXTERNAL_PARTNER", gia=None)
    hd = await _hd(q)
    assert _nguon(hd) == {_exam(q)}


# ---------------------------------------------------------------------------
# 4–5, 9–10. Lần chờ xác minh; luật thuốc không đổi
# ---------------------------------------------------------------------------


async def test_cho_xac_minh_giu_dong_va_chan_lan_thu_thu_hai(q: Quay) -> None:
    sa = await _cd(q, "SA")
    cho = await _thu(q, "QR")
    assert cho["status"] == "PENDING_VERIFICATION"
    assert await _dong_cua(q, cho["payment_cycle_id"]) == {
        _exam(q),
        ("service_order", sa),
    }
    assert (await _hd(q)).dong == []  # dòng đang chờ không còn "nợ"
    with pytest.raises(ConflictError, match="chờ xác minh"):
        await _thu(q, "CASH")
    g = await _gate(q, sa)
    assert g[sa].finance_state == "PENDING_VERIFICATION"
    assert not g[sa].financially_ready


async def test_huy_lan_cho_chua_nhan_tien_thi_no_lai(q: Quay) -> None:
    sa = await _cd(q, "SA")
    cho = (await _thu(q, "QR"))["payment_cycle_id"]
    await PaymentService(q.pool).huy_cho_xac_minh(
        payment_cycle_id=cho,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Khách không chuyển",
        identity=q.thu_ngan,
    )
    assert _nguon(await _hd(q)) == {_exam(q), ("service_order", sa)}
    assert (await _gate(q, sa))[sa].finance_state == "DUE"
    moi = (await _thu(q))["payment_cycle_id"]
    assert (await _gate(q, sa))[sa].coverage_cycle_id == moi


async def test_db_chi_mot_lan_cho_dich_vu_nhieu_lan_paid_thuoc_giu_luat_cu(
    q: Quay,
) -> None:
    async def lan(kind: str, status: str) -> None:
        await q.pool.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, created_by, paid_at,"
            " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 1000, 'r',"
            " CASE WHEN $5 = 'PAID' THEN 'CASH' ELSE 'QR' END, $5, $6::uuid,"
            " CASE WHEN $5 = 'PAID' THEN now() END,"
            " CASE WHEN $5 = 'PAID' THEN $6::uuid END)",
            str(uuid.uuid4()),
            CLINIC,
            q.visit_id,
            kind,
            status,
            q.thu_ngan.staff_id,
        )

    await lan("dich_vu", "PAID")
    await lan("dich_vu", "PAID")  # nhiều lần PAID dịch vụ: hợp lệ
    await lan("dich_vu", "PENDING_VERIFICATION")
    with pytest.raises(asyncpg.UniqueViolationError):
        await lan("dich_vu", "PENDING_VERIFICATION")
    await lan("thuoc", "PAID")
    with pytest.raises(asyncpg.UniqueViolationError):
        await lan("thuoc", "PAID")
    with pytest.raises(asyncpg.UniqueViolationError):
        await lan("thuoc", "PENDING_VERIFICATION")


# ---------------------------------------------------------------------------
# 6–8. Đồng thời và biên nhận trong giao dịch
# ---------------------------------------------------------------------------


async def test_hai_thu_ngan_cung_luc_chi_mot_lan_thu(q: Quay) -> None:
    await _cd(q, "SA")
    async with q.pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        thu_ngan_2 = await _nguoi(conn, loc, "CASHIER")
    rev = (await _hd(q)).revision
    kq = await asyncio.gather(
        _thu(q, bill_revision=rev),
        _thu(q, bill_revision=rev, who=thu_ngan_2),
        return_exceptions=True,
    )
    ok = [x for x in kq if isinstance(x, dict)]
    loi = [x for x in kq if isinstance(x, Exception)]
    assert len(ok) == 1 and len(loi) == 1
    assert isinstance(loi[0], (ValidationError, BillChangedError, ConflictError))
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid"
            " AND kind = 'dich_vu'",
            q.visit_id,
        )
        == 1
    )


async def test_chot_db_chan_phu_trung_khi_hai_giao_dich_canh_tranh(q: Quay) -> None:
    """Không qua khoá lượt: chính chốt DB phải chặn hai lần thu phủ cùng dòng."""
    sa = await _cd(q, "SA")
    c1, c2 = str(uuid.uuid4()), str(uuid.uuid4())
    a, b = await q.pool.acquire(), await q.pool.acquire()
    try:
        ta, tb = a.transaction(), b.transaction()
        await ta.start()
        await tb.start()
        for conn, cid in ((a, c1), (b, c2)):
            await conn.execute(
                "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id,"
                " kind, amount, bill_revision, method, status, created_by, paid_at,"
                " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu',"
                " 1000, 'r', 'CASH', 'PAID', $4::uuid, now(), $4::uuid)",
                cid,
                CLINIC,
                q.visit_id,
                q.thu_ngan.staff_id,
            )
        dong = (
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4, 'SA', 1, 1000, 1000, 'CLINIC')"
        )
        await a.execute(dong, CLINIC, c1, q.visit_id, sa)
        chen_b = asyncio.create_task(b.execute(dong, CLINIC, c2, q.visit_id, sa))
        await asyncio.sleep(0.3)
        assert not chen_b.done(), "giao dịch B phải chờ khoá nguồn của A"
        await ta.commit()
        with pytest.raises(asyncpg.UniqueViolationError):
            await chen_b
        await tb.rollback()
    finally:
        await q.pool.release(a)
        await q.pool.release(b)
    assert (await _gate(q, sa))[sa].coverage_cycle_id == c1


async def test_mat_phan_hoi_gui_lai_cung_khoa_tra_dung_lan_thu(q: Quay) -> None:
    await _cd(q, "SA")
    key = f"thu-{uuid.uuid4().hex}"
    r1 = await _thu(q, key=key)
    # Lần đầu đã commit: hoá đơn còn nợ nay rỗng. Gửi lại vẫn phải trả đúng lần
    # thu cũ, không báo "không còn khoản" và không tạo lần thứ hai.
    r2 = await _thu(q, key=key)
    assert r2 == r1
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        == 1
    )


async def test_cung_khoa_khac_noi_dung_bi_tu_choi(q: Quay) -> None:
    await _cd(q, "SA")
    key = f"thu-{uuid.uuid4().hex}"
    await _thu(q, key=key)
    with pytest.raises(LuotKhamConflictError) as exc:
        await _thu(q, "QR", key=key)
    assert exc.value.error_code == "IDEMPOTENCY_KEY_REUSED"


async def test_thieu_khoa_bi_tu_choi(q: Quay) -> None:
    await _cd(q, "SA")
    with pytest.raises(ValidationError, match="Idempotency-Key"):
        await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
            idempotency_key=None,
        )


# ---------------------------------------------------------------------------
# 11. Xác minh QR theo ảnh chụp, không theo hoá đơn còn nợ mới
# ---------------------------------------------------------------------------


async def test_xac_minh_lan_cho_cu_khong_lech_vi_chi_dinh_moi(q: Quay) -> None:
    sa = await _cd(q, "SA")
    cho = (await _thu(q, "QR"))["payment_cycle_id"]
    xn = await _cd(q, "XN", 90_000)  # phát sinh SAU ảnh chụp
    kq = await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=cho,
        visit_id=q.visit_id,
        kind="dich_vu",
        reference="FT123456",
        identity=q.thu_ngan,
    )
    assert kq["status"] == "PAID"
    assert kq["can_doi_soat"] is False and kq["doi_soat_ly_do"] == []
    assert _nguon(await _hd(q)) == {("service_order", xn)}
    assert (await _gate(q, sa))[sa].finance_state == "PAID"
    c2 = (await _thu(q))["payment_cycle_id"]
    assert await _dong_cua(q, c2) == {("service_order", xn)}


async def test_xac_minh_van_bat_doi_soat_khi_chinh_nguon_da_chup_doi_gia(
    q: Quay,
) -> None:
    sa = await _cd(q, "SA", 300_000)
    cho = (await _thu(q, "QR"))["payment_cycle_id"]
    await q.pool.execute(
        "UPDATE service_price SET unit_price = 350000 WHERE clinic_id = $1::uuid"
        " AND service_code = (SELECT service_code FROM service_order"
        " WHERE id = $2::uuid)",
        CLINIC,
        sa,
    )
    kq = await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=cho,
        visit_id=q.visit_id,
        kind="dich_vu",
        reference="FT654321",
        identity=q.thu_ngan,
    )
    # Tiền thật vẫn ghi đã thu theo ảnh chụp; chỉ bật đối soát như luật cũ.
    assert kq["status"] == "PAID"
    assert kq["doi_soat_ly_do"] == ["HOA_DON_DOI"]


# ---------------------------------------------------------------------------
# 12–14. Huỷ phiếu, hoàn tiền
# ---------------------------------------------------------------------------


async def test_huy_phieu_roi_thu_lai_duoc_phieu_huy_luu_doi_chieu(q: Quay) -> None:
    """Tuyền chốt 24/09/2026: thu nhầm → huỷ → thu lại; bản mới nhất thắng."""
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=c1,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Thu nhầm khách",
        identity=q.thu_ngan,
    )
    g = (await _gate(q, sa))[sa]
    assert g.finance_state == "DUE" and not g.needs_human_review
    assert (await _hd(q)).tong > 0  # khám + SA quay lại hoá đơn phải thu
    c2 = (await _thu(q))["payment_cycle_id"]
    assert c2 != c1
    g = (await _gate(q, sa))[sa]
    assert (g.finance_state, g.coverage_cycle_id) == ("PAID", c2)
    # Phiếu huỷ vẫn nằm nguyên trong sổ để đối chiếu.
    assert (
        await q.pool.fetchval(
            "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid", c1
        )
        == "VOIDED"
    )


async def test_phieu_da_co_hoan_tien_thi_khong_huy_duoc(q: Quay) -> None:
    ql = await _quan_ly(q)
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    await _hoan(q, ql, c1, await _dong_sa(q, c1, sa), 1, "CASH")
    with pytest.raises(ConflictError, match="hoàn tiền"):
        await PaymentService(q.pool).void_payment(
            payment_cycle_id=c1,
            visit_id=q.visit_id,
            kind="dich_vu",
            reason="Muốn huỷ sau khi hoàn",
            identity=ql,
        )


async def test_huy_lan_cu_giu_nghia_lan_paid_khac_va_dung_lai_hinh_chieu(
    q: Quay,
) -> None:
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    xn = await _cd(q, "XN")
    c2 = (await _thu(q))["payment_cycle_id"]
    svc = PaymentService(q.pool)

    async def proj() -> tuple[str, str]:
        r = await q.pool.fetchrow(
            "SELECT payment_cycle_id::text AS c, status FROM payment"
            " WHERE visit_id = $1::uuid AND kind = 'dich_vu'",
            q.visit_id,
        )
        return (r["c"], r["status"])

    # Huỷ lần CŨ: hình chiếu vẫn trỏ #2, XN vẫn PAID.
    await svc.void_payment(
        payment_cycle_id=c1,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Huỷ lần một",
        identity=q.thu_ngan,
    )
    assert await proj() == (c2, "PAID")
    g = await _gate(q, sa, xn)
    assert g[xn].finance_state == "PAID"
    assert g[sa].finance_state == "DUE"  # phiếu huỷ → thu lại được (24/09/2026)
    # Huỷ lần đang được trỏ khi không còn lần PAID nào khác → VOIDED.
    await svc.void_payment(
        payment_cycle_id=c2,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Huỷ lần hai",
        identity=q.thu_ngan,
    )
    assert await proj() == (c2, "VOIDED")


async def test_huy_lan_dang_tro_thi_hinh_chieu_ve_lan_paid_con_lai(q: Quay) -> None:
    await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    await _cd(q, "XN")
    c2 = (await _thu(q))["payment_cycle_id"]
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=c2,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Huỷ lần hai",
        identity=q.thu_ngan,
    )
    r = await q.pool.fetchrow(
        "SELECT payment_cycle_id::text AS c, status, amount FROM payment"
        " WHERE visit_id = $1::uuid AND kind = 'dich_vu'",
        q.visit_id,
    )
    assert (r["c"], r["status"], r["amount"]) == (c1, "PAID", 350_000)


async def _dong_sa(q: Quay, cycle: str, sa: str) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id ="
            " $1::uuid AND source_type = 'service_order' AND source_id = $2",
            cycle,
            sa,
        )
    )


async def _hoan(
    q: Quay, ql: StaffIdentity, cycle: str, line: str, so: float, pt: str
) -> str:
    kq = await HoanTienService(q.pool).tao(
        identity=ql,
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": line, "so_luong": so}],
        method=pt,
        reason="Khách không làm nữa",
    )
    return str(kq["refund_id"])


async def test_hoan_tien_cho_du_mot_phan_va_that_bai(q: Quay) -> None:
    ql = await _quan_ly(q)
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    line = await _dong_sa(q, c1, sa)

    cho = await _hoan(q, ql, c1, line, 1, "TRANSFER")
    assert (await _gate(q, sa))[sa].finance_state == "REFUND_PENDING"
    # Khoản hoàn không thành → vẫn PAID (không mất phủ).
    await HoanTienService(q.pool).dong(
        identity=ql, refund_id=cho, trang_thai="FAILED", reason="Sai số tài khoản"
    )
    assert (await _gate(q, sa))[sa].finance_state == "PAID"

    await _hoan(q, ql, c1, line, 0.5, "CASH")
    g = (await _gate(q, sa))[sa]
    assert (g.finance_state, g.reason_code) == (
        "FINANCIAL_REVIEW_REQUIRED",
        "PARTIAL_REFUND",
    )
    await _hoan(q, ql, c1, line, 0.5, "CASH")
    assert (await _gate(q, sa))[sa].finance_state == "REFUNDED"
    assert (await _hd(q)).dong == []  # đã hoàn không tự "nợ" lại


async def test_khoan_hoan_bi_huy_van_giu_paid(q: Quay) -> None:
    ql = await _quan_ly(q)
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    r = await _hoan(q, ql, c1, await _dong_sa(q, c1, sa), 1, "QR")
    await HoanTienService(q.pool).dong(
        identity=ql, refund_id=r, trang_thai="CANCELLED", reason="Khách đổi ý"
    )
    assert (await _gate(q, sa))[sa].finance_state == "PAID"


# ---------------------------------------------------------------------------
# 15–19. FinanceGate theo cấu hình giá; lịch sử thắng bảng giá mới
# ---------------------------------------------------------------------------


async def test_finance_gate_theo_cau_hinh_gia(q: Quay) -> None:
    dt = await _cd(q, "DT", None, ben="EXTERNAL_PARTNER")
    free = await _cd(q, "FREE", 0)
    thieu = await _cd(q, "THIEU", co_gia=False)
    due = await _cd(q, "DUE", 100_000)
    chua = await _cd(q, "CHUA", selection="PENDING")
    g = await _gate(q, dt, free, thieu, due, chua)
    # Đối tác tự thu (Tuyền chốt 27/09/2026, Q1): khách trả TRỰC TIẾP cho đối
    # tác → về phía phòng khám không có gì phải thu → sẵn sàng (trước:
    # EXTERNAL_PAYMENT_UNRESOLVED chặn mãi, không lệnh nào gỡ).
    assert g[dt].finance_state == "PARTNER_COLLECTS"
    assert g[dt].financially_ready
    assert not g[dt].payment_required_by_clinic
    assert g[free].finance_state == "NOT_REQUIRED" and g[free].financially_ready
    assert g[thieu].finance_state == "FINANCIAL_DATA_INCOMPLETE"
    assert g[due].finance_state == "DUE"
    assert g[due].reason_code == "SERVICE_PAYMENT_REQUIRED"
    assert g[chua].finance_state == "NOT_APPLICABLE"
    assert g[chua].reason_code == "SERVICE_NOT_SELECTED"
    # Chỉ PAID / NOT_REQUIRED / PARTNER_COLLECTS mở cửa.
    assert {o for o, d in g.items() if d.financially_ready} == {free, dt}


def test_gia_hoac_ben_thu_mau_thuan_la_chua_du_du_lieu() -> None:
    """service_price chặn trùng mã theo (clinic, group, code), nên chỉ định
    không thể có hai giá trong DB hôm nay — luật vẫn phải đúng nếu dữ liệu có."""

    def facts(gia: tuple[Any, ...], ben: tuple[str, ...]) -> fg.OrderFinanceFacts:
        return fg.OrderFinanceFacts(
            order_id="o",
            selection_status="SELECTED",
            exec_status="authorized",
            execution_status=None,
            gia=gia,
            ben_thu=ben,
            footprints=(),
            visit_allocation_unknown=False,
        )

    for gia, ben in (
        ((100, 120), ("CLINIC",)),
        ((100,), ("CLINIC", "EXTERNAL_PARTNER")),
        ((), ()),
    ):
        d = fg.derive_finance_state(facts(gia, ben))
        assert d.finance_state == "FINANCIAL_DATA_INCOMPLETE", (gia, ben)
        assert not d.financially_ready
    # 0đ là giá hợp lệ, không phải thiếu giá.
    assert fg.derive_finance_state(facts((0,), ("CLINIC",))).finance_state == (
        "NOT_REQUIRED"
    )


async def test_tien_kham_hai_bang_gia_mau_thuan_thi_chua_thu_duoc(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        await _gia_dv(conn, f"KHAM2-{q.duoi}", f"Khám thử {q.duoi}", 170_000)
    hd = await _hd(q)
    assert any("mâu thuẫn" in v for v in hd.van_de)
    assert not hd.thu_duoc


async def test_da_lam_ma_chua_co_tien_la_bat_thuong_khong_thu_bu(q: Quay) -> None:
    a = await _cd(q, "DALAM", execution_status="COMPLETED")
    phong = await q.pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid LIMIT 1", CLINIC
    )
    b = await _cd(q, "CU", exec_status="performed", room_id=phong)
    g = await _gate(q, a, b)
    assert g[a].reason_code == g[b].reason_code == "EXECUTED_WITHOUT_PAYMENT"
    assert _nguon(await _hd(q)) == {_exam(q)}


async def test_phu_trung_trong_lich_su_la_can_doi_soat(q: Quay) -> None:
    sa = await _cd(q, "SA")
    c1 = (await _thu(q))["payment_cycle_id"]
    # Dữ liệu cũ trước chốt DB: chèn thẳng một lần thu thứ hai phủ cùng SA,
    # tắt trigger trong phiên (session_replication_role) để dựng lịch sử.
    async with q.pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        c2 = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, created_by, paid_at,"
            " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 1000,"
            " 'r', 'CASH', 'PAID', $4::uuid, now(), $4::uuid)",
            c2,
            CLINIC,
            q.visit_id,
            q.thu_ngan.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4, 'SA', 1, 1000, 1000, 'CLINIC')",
            CLINIC,
            c2,
            q.visit_id,
            sa,
        )
    g = (await _gate(q, sa))[sa]
    assert (g.finance_state, g.reason_code) == (
        "FINANCIAL_REVIEW_REQUIRED",
        "MULTIPLE_SERVICE_COVERAGE",
    )
    assert c1 != c2


async def test_doi_bang_gia_sau_khi_thu_khong_dien_giai_lai(q: Quay) -> None:
    sa = await _cd(q, "SA", 300_000)
    c1 = (await _thu(q))["payment_cycle_id"]
    await q.pool.execute(
        "UPDATE service_price SET billing_owner = 'EXTERNAL_PARTNER',"
        " unit_price = NULL WHERE clinic_id = $1::uuid AND service_code ="
        " (SELECT service_code FROM service_order WHERE id = $2::uuid)",
        CLINIC,
        sa,
    )
    g = (await _gate(q, sa))[sa]
    assert (g.finance_state, g.coverage_cycle_id) == ("PAID", c1)
    assert (await _hd(q)).dong == []


async def test_tien_cu_khong_truy_duoc_thi_can_doi_soat(q: Quay) -> None:
    sa = await _cd(q, "SA")
    await q.pool.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, status, legacy, paid_at) VALUES ($1::uuid, $2::uuid, $3::uuid,"
        " 'dich_vu', 1000, 'PAID', true, now())",
        str(uuid.uuid4()),
        CLINIC,
        q.visit_id,
    )
    assert (await _gate(q, sa))[sa].reason_code == "ALLOCATION_UNKNOWN"
    with pytest.raises(ValidationError, match="đối soát"):
        await _thu(q)


# ---------------------------------------------------------------------------
# 20. Lô 30 chỉ định: đúng một truy vấn, cùng kết quả như từng cái
# ---------------------------------------------------------------------------


class _DemTruyVan:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn
        self.so = 0

    async def fetch(self, *a: Any, **kw: Any) -> Any:
        self.so += 1
        return await self._conn.fetch(*a, **kw)


async def test_lo_30_chi_dinh_mot_truy_van(q: Quay) -> None:
    ids = [await _cd(q, f"L{i}", 10_000 * (i + 1)) for i in range(30)]
    async with q.pool.acquire() as conn:
        dem = _DemTruyVan(conn)
        lo = await fg.states_for_orders(dem, CLINIC, ids)
        assert dem.so == 1
        for oid in ids:
            mot = await fg.can_start(conn, CLINIC, oid)
            assert mot == lo[oid]
    assert {d.finance_state for d in lo.values()} == {"DUE"}
