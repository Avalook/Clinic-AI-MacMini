"""ConfirmServiceSelection trên Postgres thật — contract SELECTION-v1 §16.

Chạy (DB dùng một lần, đã nạp migration + seed):

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55461/postgres \\
        poetry run pytest src/tests/services/test_service_selection_db.py

Mỗi test tự dựng người, lượt và chỉ định (mã ngẫu nhiên), không cần dọn.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    LuotKhamValidationError,
)
from clinicai.services.permission_service import cap_preset_mac_dinh
from clinicai.services.service_selection_service import ServiceSelectionService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


@dataclass
class KB:
    pool: asyncpg.Pool
    svc: ServiceSelectionService
    loc: str
    visit_id: str
    consultation_id: str
    bac_si: StaffIdentity
    thu_ngan: StaffIdentity
    thu_ngan_2: StaffIdentity
    ma_sa: str


async def _nguoi(conn: asyncpg.Connection, loc: str, role: str) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _luot(conn: asyncpg.Connection, loc: str, doctor_id: str) -> tuple[str, str]:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test selection', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"SEL-{uuid.uuid4().hex[:10]}",
        loc,
    )
    vid = await conn.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
        " attending_doctor_id, checked_in_at)"
        " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', $3::uuid, now())"
        " RETURNING visit_id::text",
        CLINIC,
        pid,
        doctor_id,
    )
    con = await conn.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id, started_by, started_at)"
        " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
        " $3::uuid, now()) RETURNING id::text",
        CLINIC,
        vid,
        doctor_id,
    )
    return str(vid), str(con)


@pytest_asyncio.fixture
async def kb(pool: asyncpg.Pool) -> KB:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        vid, con = await _luot(conn, loc, bac_si.staff_id)
        ma_sa = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active AND node_code = 'DICHVU-SIEUAM'"
            " ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        return KB(
            pool=pool,
            svc=ServiceSelectionService(pool),
            loc=loc,
            visit_id=vid,
            consultation_id=con,
            bac_si=bac_si,
            thu_ngan=await _nguoi(conn, loc, "CASHIER"),
            thu_ngan_2=await _nguoi(conn, loc, "RECEPTION"),
            ma_sa=ma_sa,
        )


async def _chi_dinh(
    kb: KB,
    *,
    exec_status: str = "authorized",
    selection: str | None = "PENDING",
    visit_id: str | None = None,
    consultation_id: str | None = None,
    **extra: Any,
) -> str:
    cols = {
        "exec_status": exec_status,
        "selection_status": selection,
        **extra,
    }
    names = ", ".join(cols)
    params = ", ".join(f"${i + 7}" for i in range(len(cols)))
    authorized = exec_status not in ("draft", "cancelled")
    async with kb.pool.acquire() as conn:
        return str(
            await conn.fetchval(
                f"""
                INSERT INTO service_order
                    (clinic_id, visit_id, consultation_id, service_code,
                     service_name, node_code, recorded_by, authorized_by,
                     authorized_at, {names})
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'Siêu âm test',
                        'DICHVU-SIEUAM', $5::uuid,
                        CASE WHEN $6 THEN $5::uuid END,
                        CASE WHEN $6 THEN now() END, {params})
                RETURNING id::text
                """,  # noqa: S608 — tên cột cố định trong test
                CLINIC,
                visit_id or kb.visit_id,
                consultation_id or kb.consultation_id,
                kb.ma_sa,
                kb.bac_si.staff_id,
                authorized,
                *cols.values(),
            )
        )


async def _lan_thu(
    kb: KB,
    order_ids: list[str],
    *,
    status: str,
    paid: bool,
    with_lines: bool = True,
    legacy: bool = False,
) -> str:
    """Một lần thu dịch vụ (cycle) kèm dòng hoá đơn trỏ tới từng chỉ định."""
    cycle = str(uuid.uuid4())
    staff = kb.thu_ngan.staff_id
    closed = status in ("VOIDED", "CANCELLED")
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO payment_cycle
                (payment_cycle_id, clinic_id, visit_id, kind, amount,
                 bill_revision, method, status, legacy, created_by,
                 paid_at, confirmed_by, closed_at, closed_by, close_reason)
            VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 300000,
                    CASE WHEN $6 THEN NULL ELSE 'rev-test' END,
                    CASE WHEN $6 THEN NULL
                         WHEN $4 = 'PENDING_VERIFICATION' THEN 'QR'
                         ELSE 'CASH' END,
                    $4, $6, CASE WHEN $6 THEN NULL ELSE $5::uuid END,
                    CASE WHEN $7 THEN now() END,
                    CASE WHEN $7 THEN $5::uuid END,
                    CASE WHEN $8 THEN now() END,
                    CASE WHEN $8 THEN $5::uuid END,
                    CASE WHEN $8 THEN 'Huỷ để kiểm thử' END)
            """,
            cycle,
            CLINIC,
            kb.visit_id,
            status,
            staff,
            legacy,
            paid,
            closed,
        )
        if with_lines:
            await conn.executemany(
                """
                INSERT INTO payment_bill_line
                    (clinic_id, payment_cycle_id, visit_id, kind, source_type,
                     source_id, name_snapshot, quantity, unit_price, line_total,
                     billing_owner)
                VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 'service_order',
                        $4, 'Siêu âm test', 1, 300000, 300000, 'CLINIC')
                """,
                [(CLINIC, cycle, kb.visit_id, oid) for oid in order_ids],
            )
    return cycle


async def _confirm(
    kb: KB,
    seen: list[str],
    selected: list[str],
    rev: int,
    *,
    key: str | None = None,
    who: StaffIdentity | None = None,
    visit_id: str | None = None,
) -> dict[str, Any]:
    return await kb.svc.confirm(
        visit_id=visit_id or kb.visit_id,
        order_ids_seen=seen,
        selected_order_ids=selected,
        expected_selection_revision=rev,
        identity=who or kb.thu_ngan,
        idempotency_key=key or f"sel-{uuid.uuid4().hex}",
    )


async def _trang_thai(kb: KB, *ids: str) -> dict[str, tuple[str | None, int]]:
    async with kb.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text AS id, selection_status, version FROM service_order"
            " WHERE id = ANY($1::uuid[])",
            list(ids),
        )
    return {r["id"]: (r["selection_status"], r["version"]) for r in rows}


async def _su_kien(kb: KB) -> list[dict[str, Any]]:
    async with kb.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT payload FROM event_log WHERE aggregate_id = $1"
            " AND event_type = 'service_selection.confirmed' ORDER BY recorded_at",
            kb.visit_id,
        )
    return [json.loads(r["payload"]) for r in rows]


async def _revision(kb: KB) -> int:
    async with kb.pool.acquire() as conn:
        v = await conn.fetchval(
            "SELECT revision FROM service_selection_state WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    return int(v or 0)


async def _loi(coro: Any, code: str) -> None:
    with pytest.raises((LuotKhamConflictError, LuotKhamValidationError)) as exc:
        await coro
    assert exc.value.error_code == code


# ---------------------------------------------------------------------------


async def test_1_lan_dau_xac_nhan(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    r = await _confirm(kb, [a, b], [a], 0)
    assert r["changed"] is True and r["selection_revision"] == 1
    assert r["selected_order_ids"] == [a]
    assert r["not_selected_order_ids"] == [b]
    assert r["changed_order_ids"] == sorted([a, b])
    assert r["confirmed_by"] == kb.thu_ngan.staff_id
    st = await _trang_thai(kb, a, b)
    assert st[a] == ("SELECTED", 2) and st[b] == ("NOT_SELECTED", 2)
    assert r["order_versions"] == {a: 2, b: 2}
    [ev] = await _su_kien(kb)
    assert ev == {
        "selection_revision": 1,
        "selected_order_ids": [a],
        "not_selected_order_ids": [b],
        "changed_order_ids": sorted([a, b]),
    }
    assert await _revision(kb) == 1


async def test_2_cung_khoa_tra_lai_dung_phan_hoi(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    key = f"sel-{uuid.uuid4().hex}"
    r1 = await _confirm(kb, [a, b], [b], 0, key=key)
    # Revision nay là 1 nhưng gửi lại vẫn nhận đúng kết quả cũ.
    r2 = await _confirm(kb, [b, a], [b], 0, key=key)
    assert r2 == r1
    assert len(await _su_kien(kb)) == 1
    assert await _revision(kb) == 1


async def test_3_cung_khoa_khac_noi_dung(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    key = f"sel-{uuid.uuid4().hex}"
    await _confirm(kb, [a, b], [a], 0, key=key)
    await _loi(_confirm(kb, [a, b], [b], 0, key=key), "IDEMPOTENCY_KEY_REUSED")


async def test_thieu_khoa_gui_lai(kb: KB) -> None:
    a = await _chi_dinh(kb)
    with pytest.raises(LuotKhamValidationError) as exc:
        await kb.svc.confirm(
            visit_id=kb.visit_id,
            order_ids_seen=[a],
            selected_order_ids=[a],
            expected_selection_revision=0,
            identity=kb.thu_ngan,
            idempotency_key=None,
        )
    assert exc.value.error_code == "IDEMPOTENCY_KEY_REQUIRED"


async def test_4_hai_nguoi_cung_revision_mot_nguoi_thang(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    kq = await asyncio.gather(
        _confirm(kb, [a, b], [a], 0, who=kb.thu_ngan),
        _confirm(kb, [a, b], [b], 0, who=kb.thu_ngan_2),
        return_exceptions=True,
    )
    ok = [x for x in kq if isinstance(x, dict)]
    loi = [x for x in kq if isinstance(x, Exception)]
    assert len(ok) == 1 and len(loi) == 1
    assert isinstance(loi[0], LuotKhamConflictError)
    assert loi[0].error_code == "SELECTION_REVISION_CONFLICT"
    assert await _revision(kb) == 1
    assert len(await _su_kien(kb)) == 1


async def test_5_bac_si_them_chi_dinh_sau_khi_ui_chup(kb: KB) -> None:
    a = await _chi_dinh(kb)
    moi = await _chi_dinh(kb)  # bác sĩ vừa thêm, UI chưa thấy
    await _loi(_confirm(kb, [a], [a], 0), "SELECTION_ORDER_SET_CHANGED")
    st = await _trang_thai(kb, a, moi)
    assert st[a] == ("PENDING", 1) and st[moi] == ("PENDING", 1)
    assert await _revision(kb) == 0


async def test_6_ma_lap_lai_bi_tu_choi(kb: KB) -> None:
    a = await _chi_dinh(kb)
    await _loi(_confirm(kb, [a, a], [a], 0), "SELECTION_DUPLICATE_ORDER_ID")
    await _loi(_confirm(kb, [a], [a, a], 0), "SELECTION_DUPLICATE_ORDER_ID")


async def test_7_chon_ngoai_danh_sach_da_hoi(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    await _loi(_confirm(kb, [a], [b], 0), "SELECTION_SELECTED_NOT_IN_SEEN")


async def test_8_khong_chon_gi_la_hop_le(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    r = await _confirm(kb, [a, b], [], 0)
    assert r["selected_order_ids"] == []
    st = await _trang_thai(kb, a, b)
    assert {s for s, _ in st.values()} == {"NOT_SELECTED"}


async def test_9_doi_y_truoc_khi_thu_tien(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    await _confirm(kb, [a, b], [a, b], 0)
    r = await _confirm(kb, [a, b], [b], 1)
    assert r["selection_revision"] == 2 and r["changed_order_ids"] == [a]
    st = await _trang_thai(kb, a, b)
    assert st[a] == ("NOT_SELECTED", 3) and st[b] == ("SELECTED", 2)


async def test_10_dang_cho_xac_minh_thi_khoa(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    await _confirm(kb, [a, b], [a, b], 0)
    await _lan_thu(kb, [a], status="PENDING_VERIFICATION", paid=False)
    await _loi(_confirm(kb, [a, b], [b], 1), "SELECTION_FINANCIAL_LOCKED")
    assert (await _trang_thai(kb, a))[a][0] == "SELECTED"


async def test_11_da_nhan_tien_thi_khoa(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    await _confirm(kb, [a, b], [a, b], 0)
    await _lan_thu(kb, [a], status="PAID", paid=True)
    await _loi(_confirm(kb, [a, b], [b], 1), "SELECTION_FINANCIAL_LOCKED")
    # Chỉ định đã khoá không còn là chỉ định để quyết: bỏ nó khỏi danh sách
    # thì chỉ định còn lại vẫn đổi được.
    r = await _confirm(kb, [b], [], 1)
    assert r["not_selected_order_ids"] == [b]


async def test_11b_phieu_da_huy_khong_khoa_nua(kb: KB) -> None:
    """Tuyền chốt 24/09/2026: phiếu huỷ chỉ còn để đối chiếu — khách chọn lại được."""
    a = await _chi_dinh(kb)
    await _confirm(kb, [a], [a], 0)
    await _lan_thu(kb, [a], status="VOIDED", paid=True)
    r = await _confirm(kb, [a], [], 1)
    assert r["changed_order_ids"] == [a]


async def test_12_lan_cho_da_huy_chua_nhan_tien_khong_khoa(kb: KB) -> None:
    a = await _chi_dinh(kb)
    await _confirm(kb, [a], [a], 0)
    await _lan_thu(kb, [a], status="CANCELLED", paid=False)
    r = await _confirm(kb, [a], [], 1)
    assert r["changed_order_ids"] == [a]


async def test_13_tien_cu_khong_truy_duoc_toi_chi_dinh(kb: KB) -> None:
    a = await _chi_dinh(kb)
    await _lan_thu(kb, [], status="PAID", paid=True, with_lines=False, legacy=True)
    await _loi(_confirm(kb, [a], [a], 0), "SELECTION_PAYMENT_ALLOCATION_UNKNOWN")
    assert (await _trang_thai(kb, a))[a][0] == "PENDING"


@pytest.mark.parametrize(
    "extra",
    [
        {"exec_status": "assigned"},
        {"routing_status": "ASSIGNED"},
        {"routing_status": "REASSIGNMENT_REQUIRED"},
    ],
)
async def test_14_da_xep_phong_thi_khoa(kb: KB, extra: dict[str, Any]) -> None:
    extra = dict(extra)
    exec_status = extra.pop("exec_status", "authorized")
    room = None
    # Slice 4: ASSIGNED luôn có phòng (CHECK service_order_routing_khop_phong).
    if exec_status == "assigned" or extra.get("routing_status") == "ASSIGNED":
        async with kb.pool.acquire() as conn:
            room = await conn.fetchval(
                "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid LIMIT 1",
                CLINIC,
            )
        extra["room_id"] = room
    a = await _chi_dinh(kb, exec_status=exec_status, **extra)
    await _loi(_confirm(kb, [a], [], 0), "SELECTION_ROUTING_LOCKED")
    assert (await _trang_thai(kb, a))[a][0] == "PENDING"


@pytest.mark.parametrize(
    "extra",
    [
        {"execution_status": "IN_PROGRESS"},
        {"execution_status": "COMPLETED"},
        {"execution_status": "CANCELLED"},
        {"execution_status": "NOT_PERFORMED", "not_performed_reason": "x"},
        {"exec_status": "cancelled"},
    ],
)
async def test_15_da_bat_dau_hoac_ket_thuc_thi_khoa(
    kb: KB, extra: dict[str, Any]
) -> None:
    extra = dict(extra)
    exec_status = extra.pop("exec_status", "authorized")
    if exec_status == "authorized":
        extra.pop("not_performed_reason", None)
    a = await _chi_dinh(kb, exec_status=exec_status, **extra)
    await _loi(_confirm(kb, [a], [], 0), "SELECTION_EXECUTION_LOCKED")


async def test_16_khong_doi_gi_voi_khoa_moi(kb: KB) -> None:
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    r1 = await _confirm(kb, [a, b], [a], 0)
    r2 = await _confirm(kb, [a, b], [a], 1)
    assert r2["changed"] is False and r2["changed_order_ids"] == []
    assert r2["selection_revision"] == 1
    assert r2["order_versions"] == r1["order_versions"]
    assert r2["confirmed_at"] == r1["confirmed_at"]
    assert len(await _su_kien(kb)) == 1
    st = await _trang_thai(kb, a, b)
    assert st[a][1] == 2 and st[b][1] == 2


async def test_17_chi_dinh_luot_khac_khong_bao_gio_bi_sua(kb: KB) -> None:
    a = await _chi_dinh(kb)
    async with kb.pool.acquire() as conn:
        vid2, con2 = await _luot(conn, kb.loc, kb.bac_si.staff_id)
    la = await _chi_dinh(kb, visit_id=vid2, consultation_id=con2)
    await _loi(_confirm(kb, [a, la], [a, la], 0), "SELECTION_ORDER_SET_CHANGED")
    assert (await _trang_thai(kb, la))[la] == ("PENDING", 1)
    # Lượt của phòng khám khác không mở được dưới danh tính phòng khám này.
    # Từ 23/09/2026 lời từ chối đến SỚM HƠN: quyền cấp theo TỪNG phòng khám nên
    # người này không có quyền nào ở phòng khám lạ — chặn ngay ở cửa quyền, chưa
    # đọc tới lượt khám. Vẫn là từ chối, và ranh giới vẫn nguyên.
    khac = dataclasses.replace(kb.thu_ngan, clinic_id=str(uuid.uuid4()))
    with pytest.raises(Exception) as exc:
        await _confirm(kb, [a], [a], 0, who=khac)
    assert "Không tìm thấy" in str(exc.value) or "không có quyền" in str(exc.value)
    assert (await _trang_thai(kb, a))[a] == ("PENDING", 1)


async def test_18_loi_truoc_bien_nhan_thi_rollback_het(
    kb: KB, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = await _chi_dinh(kb)

    async def hong(*_: Any, **__: Any) -> None:
        raise RuntimeError("chết trước khi ghi biên nhận")

    # Biên nhận nay ở nền chung `lenh_kham_core` (bóc 24/09) — giả lỗi ngay
    # tại chỗ khối này gọi nó.
    import clinicai.services.service_selection_service as khoi

    monkeypatch.setattr(khoi, "bien_nhan_ghi", hong)
    with pytest.raises(RuntimeError):
        await _confirm(kb, [a], [a], 0)
    assert (await _trang_thai(kb, a))[a] == ("PENDING", 1)
    assert await _revision(kb) == 0
    assert await _su_kien(kb) == []


async def test_19_selection_va_payment_noi_tiep_qua_khoa_visit(kb: KB) -> None:
    a = await _chi_dinh(kb)
    await _confirm(kb, [a], [a], 0)
    payment_conn = await kb.pool.acquire()
    try:
        tx = payment_conn.transaction()
        await tx.start()
        # Như PaymentService.record_payment: khoá visit TRƯỚC khi chạm tiền.
        await payment_conn.execute(
            "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE OF visit",
            kb.visit_id,
        )
        task = asyncio.create_task(_confirm(kb, [a], [], 1))
        await asyncio.sleep(0.5)
        assert not task.done(), "Selection phải chờ khoá visit của Payment"
        cycle = str(uuid.uuid4())
        await payment_conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, created_by)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 300000, 'r',"
            " 'QR', 'PENDING_VERIFICATION', $4::uuid)",
            cycle,
            CLINIC,
            kb.visit_id,
            kb.thu_ngan.staff_id,
        )
        await payment_conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4, 'SA', 1, 300000, 300000, 'CLINIC')",
            CLINIC,
            cycle,
            kb.visit_id,
            a,
        )
        await tx.commit()
    finally:
        await kb.pool.release(payment_conn)
    # Sau khi Payment commit, Selection thấy lần thu và bị khoá tài chính.
    with pytest.raises(LuotKhamConflictError) as exc:
        await task
    assert exc.value.error_code == "SELECTION_FINANCIAL_LOCKED"
    assert (await _trang_thai(kb, a))[a][0] == "SELECTED"


async def test_20_duyet_chi_dinh_moi_khong_tu_xep_phong(kb: KB) -> None:
    """Chỉ định lifecycle-v1 không tự vào phòng lúc duyệt; dòng cũ (NULL) vẫn
    tự xếp như trước — đối chứng rằng điều kiện điều phối đã đủ."""
    luot = LuotKhamService(kb.pool)
    async with kb.pool.acquire() as conn:
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN test T20', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"SEL-{uuid.uuid4().hex[:10]}",
            kb.loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', $3::uuid, now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
            kb.bac_si.staff_id,
        )
    # Sinh hiệu chỉ là bước dựng. Nhóm mẫu bác sĩ không có khối Sinh hiệu
    # (CORE-B3: quyền, không vai) — quản lý cấp thêm cho bác sĩ này.
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($1::uuid, $2::uuid, 'vitals.measure', 'sinh_hieu')"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            kb.bac_si.staff_id,
        )
    await luot.bat_dau_do_sinh_hieu(visit_id=vid, identity=kb.bac_si)
    await luot.record_vitals(
        visit_id=vid, raw={"systolic": 118, "diastolic": 76}, identity=kb.bac_si
    )
    await chay_hanh_trinh(kb.pool)
    async with kb.pool.acquire() as conn:
        phien = await conn.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND round_no = 1",
            vid,
        )
    await luot.start_consultation(consultation_id=phien, identity=kb.bac_si)
    cu = await _chi_dinh(kb, selection=None, visit_id=vid, consultation_id=phien)
    r = await luot.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    [oid] = r["order_ids"]
    async with kb.pool.acquire() as conn:
        rows = {
            x["id"]: x
            for x in await conn.fetch(
                "SELECT id::text AS id, exec_status, room_id, selection_status,"
                " routing_status, execution_status,"
                " (SELECT count(*) FROM queue_entry q WHERE q.ref_id = o.id"
                "   AND q.reason = 'SERVICE') AS hang"
                " FROM service_order o WHERE id = ANY($1::uuid[])",
                [oid, cu],
            )
        }
    moi = rows[oid]
    assert moi["exec_status"] == "authorized" and moi["room_id"] is None
    assert moi["selection_status"] == "PENDING" and moi["hang"] == 0
    # Slice 4 §B: chỉ định chính thức mới chưa có phòng chính thức (UNASSIGNED,
    # revision 0). Trục execution vẫn do Slice 5 sở hữu.
    assert moi["routing_status"] == "UNASSIGNED" and moi["execution_status"] is None
    assert rows[cu]["exec_status"] == "assigned" and rows[cu]["hang"] == 1


async def test_nhap_khong_co_selection(kb: KB) -> None:
    d = await _chi_dinh(kb, exec_status="draft", selection=None)
    a = await _chi_dinh(kb)
    # Nháp không phải chỉ định để quyết — không nằm trong tập.
    await _loi(_confirm(kb, [a, d], [a], 0), "SELECTION_ORDER_SET_CHANGED")
    r = await _confirm(kb, [a], [a], 0)
    assert r["changed_order_ids"] == [a]
    assert (await _trang_thai(kb, d))[d] == (None, 1)


async def test_dong_legacy_null_duoc_chon(kb: KB) -> None:
    """Dòng cũ (NULL) vẫn quyết được — NULL không phải NOT_SELECTED."""
    a = await _chi_dinh(kb, selection=None)
    r = await _confirm(kb, [a], [a], 0)
    assert r["changed_order_ids"] == [a]


async def test_khong_con_chi_dinh_nao(kb: KB) -> None:
    await _loi(_confirm(kb, [], [], 0), "NO_SELECTABLE_ORDERS")


async def test_vai_khong_co_quyen(kb: KB) -> None:
    a = await _chi_dinh(kb)
    with pytest.raises(SafetyGateError):
        await _confirm(kb, [a], [a], 0, who=kb.bac_si)


async def test_http_endpoint_cua_vai_va_ma_loi(kb: KB) -> None:
    """Router gắn đúng đường, cửa vai ngoài chặn, mã lỗi ổn định tới thân 409."""
    import httpx

    from clinicai.api.identity import _resolve_identity
    from clinicai.core.database import get_db_pool
    from clinicai.main import app

    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    ai: dict[str, StaffIdentity] = {"x": kb.thu_ngan}
    app.dependency_overrides[get_db_pool] = lambda: kb.pool
    app.dependency_overrides[_resolve_identity] = lambda: ai["x"]
    duong = f"/api/v1/luot-kham/visits/{kb.visit_id}/service-selection/confirm"
    than = {
        "order_ids_seen": [a, b],
        "selected_order_ids": [a],
        "expected_selection_revision": 0,
    }
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.post(duong, json=than)
            assert r.status_code == 422
            assert r.json()["error"] == "IDEMPOTENCY_KEY_REQUIRED"

            h = {"Idempotency-Key": f"sel-{uuid.uuid4().hex}"}
            r = await c.post(duong, json=than, headers=h)
            assert r.status_code == 200, r.text
            assert r.json()["selection_revision"] == 1

            r = await c.post(
                duong,
                json=than,
                headers={"Idempotency-Key": f"sel-{uuid.uuid4().hex}"},
            )
            assert r.status_code == 409
            assert r.json()["error"] == "SELECTION_REVISION_CONFLICT"

            ai["x"] = kb.bac_si
            r = await c.post(duong, json=than, headers=h)
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)


@pytest.mark.parametrize(
    ("status", "paid"), [("PAID", True), ("PENDING_VERIFICATION", False)]
)
async def test_dong_doi_tac_thu_khong_khoa_selection(
    kb: KB, status: str, paid: bool
) -> None:
    """Review #178: ảnh chụp hoá đơn lưu cả dòng EXTERNAL_PARTNER (không cộng vào
    tổng phòng khám). Lần thu của phòng khám không được khoá dịch vụ đối tác thu."""
    a, b = await _chi_dinh(kb), await _chi_dinh(kb)
    await _confirm(kb, [a, b], [a, b], 0)
    cycle = await _lan_thu(kb, [b], status=status, paid=paid)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, billing_owner)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 'service_order', $4,"
            " 'Xét nghiệm đối tác', 1, 'EXTERNAL_PARTNER')",
            CLINIC,
            cycle,
            kb.visit_id,
            a,
        )
    # b có dòng phòng khám → vẫn khoá; a chỉ có dòng đối tác → còn quyết được.
    await _loi(_confirm(kb, [a, b], [a], 1), "SELECTION_FINANCIAL_LOCKED")
    r = await _confirm(kb, [a], [], 1)
    assert r["changed_order_ids"] == [a]
    assert (await _trang_thai(kb, a))[a][0] == "NOT_SELECTED"
