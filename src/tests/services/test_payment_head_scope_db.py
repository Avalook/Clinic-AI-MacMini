from datetime import datetime
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.v1.routers.quay_thuoc import SoLuongBody, doi_so_luong
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.doi_hinh_thuc_service import DoiHinhThucService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_access_service import authorize_payment, head_money_grant
from clinicai.services.payment_service import PaymentService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_head_adjustment_preserves_original_payer_and_logs_head(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = await tao_quay(pool)
    head = await _nguoi_vai(q, "TRUONG_CA")
    when = datetime(2026, 10, 12, 10, tzinfo=CLINIC_TZ)
    monkeypatch.setattr("clinicai.services.cashier_scope_service.now_vn", lambda: when)
    roster_id = await pool.fetchval(
        "INSERT INTO work_roster"
        " (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)"
        " VALUES ($1::uuid,$2::date,$2::date,'SANG','DIEU_PHOI',"
        " $3::uuid,'Head test','APPROVED') RETURNING id",
        head.clinic_id,
        when.date(),
        head.staff_id,
    )
    try:
        payment = await _thu_pt(q, "CASH")
        cycle = payment["payment_cycle_id"]
        actor = await authorize_payment(pool, head, cycle_id=cycle)
        assert head_money_grant(actor, "dich_vu", q.visit_id)
        await DoiHinhThucService(pool).doi(
            identity=actor,
            payment_cycle_id=cycle,
            hinh_thuc="TRANSFER",
            reference="HEAD-TRANSFER",
            ly_do="Sửa hình thức",
        )
        method_actor = await pool.fetchval(
            "SELECT metadata->>'clinic_staff_id' FROM event_log"
            " WHERE aggregate_id=$1::uuid"
            " AND event_type='payment.method_changed'"
            " ORDER BY occurred_at DESC LIMIT 1",
            cycle,
        )
        assert method_actor == head.staff_id
        line = await pool.fetchval(
            "SELECT id::text FROM payment_bill_line"
            " WHERE payment_cycle_id=$1::uuid LIMIT 1",
            cycle,
        )
        refund = await HoanTienService(pool).tao(
            identity=actor,
            payment_cycle_id=cycle,
            visit_id=q.visit_id,
            kind="dich_vu",
            dong=[{"payment_bill_line_id": line, "so_luong": 1}],
            method="CASH",
            reason="Trưởng ca xử lý thay",
        )
        assert (
            await pool.fetchval(
                "SELECT created_by::text FROM payment_refund WHERE refund_id=$1::uuid",
                refund["refund_id"],
            )
            == head.staff_id
        )
        assert (
            await pool.fetchval(
                "SELECT created_by::text FROM payment_cycle"
                " WHERE payment_cycle_id=$1::uuid",
                cycle,
            )
            == q.thu_ngan.staff_id
        )
        assert (
            await pool.fetchval(
                "SELECT metadata->>'clinic_staff_id' FROM event_log"
                " WHERE aggregate_id=$1::uuid AND event_type='payment.refunded'"
                " ORDER BY occurred_at DESC LIMIT 1",
                refund["refund_id"],
            )
            == head.staff_id
        )
        pending_visit = await tao_quay(pool)
        pending = await _thu_pt(pending_visit, "TRANSFER")
        pending_actor = await authorize_payment(
            pool, head, cycle_id=pending["payment_cycle_id"]
        )
        await PaymentService(pool).xac_minh_dien_tu(
            payment_cycle_id=pending["payment_cycle_id"],
            visit_id=pending_visit.visit_id,
            kind="dich_vu",
            reference="HEAD-VERIFY",
            identity=pending_actor,
        )
        assert (
            await pool.fetchval(
                "SELECT confirmed_by::text FROM payment_cycle"
                " WHERE payment_cycle_id=$1::uuid",
                pending["payment_cycle_id"],
            )
            == head.staff_id
        )
        await PaymentService(pool).hoan_tac(
            payment_cycle_id=pending["payment_cycle_id"],
            ly_do="Trưởng ca hoàn tác thay",
            identity=pending_actor,
        )
        assert (
            await pool.fetchval(
                "SELECT status FROM payment_cycle WHERE payment_cycle_id=$1::uuid",
                pending["payment_cycle_id"],
            )
            == "VOIDED"
        )
        await pool.execute(
            "UPDATE work_roster SET status='REJECTED' WHERE id=$1", roster_id
        )
        with pytest.raises(SafetyGateError):
            await authorize_payment(pool, head, cycle_id=cycle)
        assert head.cashier_head_scope is None
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id=$1", roster_id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_drug_quantity_route_requires_active_roster_and_supports_head(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = await tao_quay(pool)
    rx, _ = await _dong_da_xac_dinh(q, 10)
    head = await _nguoi_vai(q, "TRUONG_CA")
    when = datetime(2026, 10, 12, 10, tzinfo=CLINIC_TZ)
    monkeypatch.setattr("clinicai.services.cashier_scope_service.now_vn", lambda: when)
    body = SoLuongBody(prescription_id=UUID(rx), so_luong=6)
    with pytest.raises(SafetyGateError):
        await doi_so_luong(body, identity=q.thu_ngan, pool=pool)
    roster_id = await pool.fetchval(
        "INSERT INTO work_roster"
        " (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)"
        " VALUES ($1::uuid,$2::date,$2::date,'SANG','DIEU_PHOI',"
        " $3::uuid,'Head drug test','APPROVED') RETURNING id",
        head.clinic_id,
        when.date(),
        head.staff_id,
    )
    try:
        await doi_so_luong(body, identity=head, pool=pool)
        assert (
            await pool.fetchval(
                "SELECT quantity FROM prescription WHERE id=$1::uuid",
                rx,
            )
            == "6 viên"
        )
        monkeypatch.setattr(
            "clinicai.services.cashier_scope_service.now_vn",
            lambda: datetime(2026, 10, 13, 10, tzinfo=CLINIC_TZ),
        )
        with pytest.raises(SafetyGateError):
            await doi_so_luong(body, identity=head, pool=pool)
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id=$1", roster_id)
