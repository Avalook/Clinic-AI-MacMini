from datetime import date, timedelta

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.cashier_scope_service import CashierScopeService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp3_db import _san_sang, _thu
from tests.so_ck import so_ck

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_assigned_days_roster_revoke_and_quay(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    svc = CashierScopeService(pool)
    day = date(2026, 10, 12)
    roster_id = await pool.fetchval(
        """INSERT INTO work_roster
        (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)
        VALUES ($1::uuid,$2::date,$2::date,'SANG','T1_THUNGAN',
                $3::uuid,'Scope test','APPROVED') RETURNING id""",
        q.thu_ngan.clinic_id,
        day,
        q.thu_ngan.staff_id,
    )
    try:
        ds = await svc.days(q.thu_ngan, kind="dich_vu")
        assert ds["items"][0]["ngay"] == "2026-10-12"
        assert ds["items"][0]["cac_ca"] == ["SANG"]
        assert not (await svc.days(q.thu_ngan, kind="thuoc"))["items"]
        location = ds["items"][0]["co_so_ids"][0]
        scope = await svc.authorize(
            q.thu_ngan,
            tu="2026-10-12",
            den="2026-10-12",
            kind="dich_vu",
            ca="SANG",
            co_so=location,
        )
        assert scope.starts and scope.ends and scope.starts[0] < scope.ends[0]
        for kind, ca in [("thuoc", "SANG"), ("dich_vu", "TOI")]:
            with pytest.raises(SafetyGateError):
                await svc.authorize(
                    q.thu_ngan,
                    tu="2026-10-12",
                    den="2026-10-12",
                    kind=kind,
                    ca=ca,
                    co_so=location,
                )
        await pool.execute(
            "UPDATE work_roster SET status='REJECTED' WHERE id=$1", roster_id
        )
        assert not (await svc.days(q.thu_ngan, kind="dich_vu"))["items"]
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id=$1", roster_id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_history_sql_halfopen_scope_before_totals(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q, so=10)
    paid = await _thu(q)
    stamp = await pool.fetchval(
        "SELECT paid_at FROM payment_cycle WHERE payment_cycle_id=$1::uuid",
        paid["payment_cycle_id"],
    )
    day = stamp.astimezone(CLINIC_TZ).date().isoformat()
    board = CashierBoardService(pool)
    history = QuayThuService(pool)
    included = await board.giao_dich(
        identity=q.thu_ngan,
        tu=day,
        den=day,
        kind="thuoc",
        scope_starts=[stamp],
        scope_ends=[stamp + timedelta(seconds=1)],
    )
    assert paid["payment_cycle_id"] in {p["id"] for p in included["giao_dich"]}
    excluded = await board.giao_dich(
        identity=q.thu_ngan,
        tu=day,
        den=day,
        kind="thuoc",
        scope_starts=[stamp - timedelta(seconds=1)],
        scope_ends=[stamp],
    )
    assert paid["payment_cycle_id"] not in {p["id"] for p in excluded["giao_dich"]}
    included_history = await history.lich_su(
        identity=q.thu_ngan,
        tu=day,
        den=day,
        kind="thuoc",
        scope_starts=[stamp],
        scope_ends=[stamp + timedelta(seconds=1)],
    )
    assert any(
        p["id"] == paid["payment_cycle_id"]
        for g in included_history["khach"]
        for p in g["phieu"]
    )
    excluded_history = await history.lich_su(
        identity=q.thu_ngan,
        tu=day,
        den=day,
        kind="thuoc",
        scope_starts=[stamp - timedelta(seconds=1)],
        scope_ends=[stamp],
    )
    assert not any(
        p["id"] == paid["payment_cycle_id"]
        for g in excluded_history["khach"]
        for p in g["phieu"]
    )
    scope_service = CashierScopeService(pool)
    with pytest.raises(SafetyGateError):
        await scope_service.receipt(
            q.thu_ngan, id_=paid["payment_cycle_id"], loai="thu"
        )
    roster_id = await pool.fetchval(
        """INSERT INTO work_roster
            (clinic_id,week_start,work_date,shift,station,staff_id,staff_name,status)
            VALUES ($1::uuid,$2::date,$2::date,'FULL','T2_XEPTHUOC',
                    $3::uuid,'Scope receipt','APPROVED') RETURNING id""",
        q.thu_ngan.clinic_id,
        stamp.astimezone(CLINIC_TZ).date(),
        q.thu_ngan.staff_id,
    )
    try:
        assigned = await scope_service.days(q.thu_ngan, kind="thuoc")
        location = assigned["items"][0]["co_so_ids"][0]
        await pool.execute(
            "UPDATE visit SET location_id=$2::uuid WHERE visit_id=("
            "SELECT visit_id FROM payment_cycle WHERE payment_cycle_id=$1::uuid)",
            paid["payment_cycle_id"],
            location,
        )
        # Phiếu thu "ngay bây giờ": giờ chạy test quyết định nó nằm trong hay
        # ngoài khung trực (khung có khe trưa 13:00–14:00 và hết 21:30). Chạy
        # trong khe trưa từng làm test đỏ dù luật đúng (13/10). Hỏi chính dịch
        # vụ khung của ngày ấy rồi kiểm cả hai phía của luật.
        tao_luc = await pool.fetchval(
            "SELECT created_at FROM payment_cycle WHERE payment_cycle_id=$1::uuid",
            paid["payment_cycle_id"],
        )
        khung = await scope_service.authorize(
            q.thu_ngan, tu=day, den=day, kind="thuoc", ca=None, co_so=location
        )
        trong_ca = khung.starts is None or any(
            lo <= tao_luc < hi
            for lo, hi in zip(khung.starts or [], khung.ends or [], strict=True)
        )
        if trong_ca:
            await scope_service.receipt(
                q.thu_ngan, id_=paid["payment_cycle_id"], loai="thu"
            )
        else:
            with pytest.raises(SafetyGateError):
                await scope_service.receipt(
                    q.thu_ngan, id_=paid["payment_cycle_id"], loai="thu"
                )
    finally:
        await pool.execute("DELETE FROM work_roster WHERE id=$1", roster_id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_personal_history_filters_before_totals(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q, so=10)
    paid = await _thu(q)
    stamp = await pool.fetchval(
        "SELECT paid_at FROM payment_cycle WHERE payment_cycle_id=$1::uuid",
        paid["payment_cycle_id"],
    )
    day = stamp.astimezone(CLINIC_TZ).date().isoformat()
    for actor, expected in [(q.thu_ngan.staff_id, True), (q.bac_si.staff_id, False)]:
        result = await QuayThuService(pool).lich_su(
            identity=q.thu_ngan,
            tu=day,
            den=day,
            kind="thuoc",
            scope_starts=[stamp],
            scope_ends=[stamp + timedelta(seconds=1)],
            scope_actor=actor,
        )
        ids = {p["id"] for g in result["khach"] for p in g["phieu"]}
        assert (paid["payment_cycle_id"] in ids) is expected
        if not expected:
            assert not result["khach"]
            assert not result["nguoi_thu"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_confirmation_actor_and_original_both_see_receipt(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.services.payment_service import PaymentService

    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q, so=10)
    pending = await _thu(q, method="TRANSFER")
    await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=pending["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reference="Scope confirmation",
        identity=q.duoc_si,
        so_tien_thuc_nhan=await so_ck(pool, pending["payment_cycle_id"]),
    )
    row = await pool.fetchrow(
        "SELECT created_by::text,confirmed_by::text,created_at,paid_at "
        "FROM payment_cycle "
        "WHERE payment_cycle_id=$1::uuid",
        pending["payment_cycle_id"],
    )
    assert row and row["created_by"] == q.thu_ngan.staff_id
    assert row["confirmed_by"] == q.duoc_si.staff_id
    stamp = row["paid_at"]
    day = stamp.astimezone(CLINIC_TZ).date().isoformat()
    assert row["created_at"] < row["paid_at"]
    for actor, expected, moment in [
        (q.thu_ngan.staff_id, True, row["created_at"]),
        (q.duoc_si.staff_id, True, row["paid_at"]),
        (q.bac_si.staff_id, False, row["paid_at"]),
    ]:
        result = await QuayThuService(pool).lich_su(
            identity=q.thu_ngan,
            tu=day,
            den=day,
            kind="thuoc",
            scope_starts=[moment],
            scope_ends=[moment + timedelta(microseconds=1)],
            scope_actor=actor,
        )
        assert (
            pending["payment_cycle_id"]
            in {p["id"] for g in result["khach"] for p in g["phieu"]}
        ) is expected


@pytest.mark.db
@pytest.mark.asyncio
async def test_pending_old_visit_carries_to_current_counter(
    pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q, so=10)
    await pool.execute(
        "UPDATE visit SET created_at=created_at-interval '2 days' "
        "WHERE visit_id=$1::uuid",
        q.visit_id,
    )
    result = await CashierBoardService(pool).board(
        identity=q.thu_ngan,
        modes=["thuoc"],
    )
    assert q.visit_id in {item["visit_id"] for item in result["items"]}
