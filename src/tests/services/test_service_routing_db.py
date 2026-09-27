"""Lifecycle v1 Slice 4 — Routing chính thức trên Postgres thật.

AssignServiceRoom / InvalidateServiceRouting / gợi ý phòng theo luật, và việc
điều phối kiểu cũ không còn vượt được Selection / Finance cho chỉ định mới.

Mỗi test dựng lượt, phòng và giá riêng (mã ngẫu nhiên). Chạy với
DATABASE_URL_TEST trỏ tới database dùng một lần.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import service_routing_service as sr
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    LuotKhamValidationError,
)
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

NODE = "DICHVU-SIEUAM"


@dataclass
class RB:
    pool: asyncpg.Pool
    svc: sr.ServiceRoutingService
    loc: str
    duoi: str
    visit_id: str
    consultation_id: str
    bac_si: StaffIdentity
    truong_ca: StaffIdentity
    truong_ca_2: StaffIdentity
    le_tan: StaffIdentity
    sa1: str
    sa2: str
    tat: str
    ngung: str
    khac_node: str


async def _phong(
    conn: asyncpg.Connection,
    loc: str,
    duoi: str,
    ten: str,
    *,
    node: str = NODE,
    active: bool = True,
    accepting: bool = True,
    sort: int = 900,
) -> str:
    rid = str(
        await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
            " $6, $7, $8) RETURNING id::text",
            CLINIC,
            loc,
            f"RT-{ten}-{duoi}",
            f"{ten} {duoi}",
            node,
            active,
            accepting,
            sort,
        )
    )
    await conn.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, $3)",
        CLINIC,
        rid,
        node,
    )
    return rid


async def _luot(conn: asyncpg.Connection, loc: str, bac_si: str) -> tuple[str, str]:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test routing', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"RT-{uuid.uuid4().hex[:10]}",
        loc,
    )
    vid = str(
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at) VALUES ($1::uuid, $2::uuid,"
            " 'IN_PROGRESS', $3::uuid, now()) RETURNING visit_id::text",
            CLINIC,
            pid,
            bac_si,
        )
    )
    con = str(
        await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
            " doctor_staff_id) VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY',"
            " 'in_progress', $3::uuid) RETURNING id::text",
            CLINIC,
            vid,
            bac_si,
        )
    )
    await conn.execute(
        "INSERT INTO encounter_flow (clinic_id, visit_id, vitals_status,"
        " route_decision, route_decided_at) VALUES ($1::uuid, $2::uuid,"
        " 'recorded', 'SERVICES', now())",
        CLINIC,
        vid,
    )
    return vid, con


@pytest_asyncio.fixture
async def rb(pool: asyncpg.Pool) -> RB:
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        vid, con = await _luot(conn, loc, bac_si.staff_id)
        return RB(
            pool=pool,
            svc=sr.ServiceRoutingService(pool),
            loc=loc,
            duoi=duoi,
            visit_id=vid,
            consultation_id=con,
            bac_si=bac_si,
            truong_ca=await _nguoi(conn, loc, "TRUONG_CA"),
            truong_ca_2=await _nguoi(conn, loc, "TRUONG_CA"),
            le_tan=await _nguoi(conn, loc, "RECEPTION"),
            sa1=await _phong(conn, loc, duoi, "SA1", sort=1),
            sa2=await _phong(conn, loc, duoi, "SA2", sort=2),
            tat=await _phong(conn, loc, duoi, "TAT", active=False),
            ngung=await _phong(conn, loc, duoi, "NGUNG", accepting=False),
            khac_node=await _phong(conn, loc, duoi, "MAU", node="DICHVU-LAYMAU-MAU"),
        )


async def _cd(
    rb: RB,
    *,
    gia: int | None = 0,
    selection: str | None = "SELECTED",
    routing: str | None = "UNASSIGNED",
    visit_id: str | None = None,
    consultation_id: str | None = None,
    **extra: Any,
) -> str:
    """Chỉ định chính thức; mặc định giá 0đ (FinanceGate NOT_REQUIRED)."""
    ma = f"RT-{rb.duoi}-{uuid.uuid4().hex[:6]}"
    async with rb.pool.acquire() as conn:
        if gia is not None:
            await conn.execute(
                'INSERT INTO service_price (clinic_id, "group", service_code, name,'
                " unit_price, billing_owner, node_code) VALUES ($1::uuid,"
                " 'dich_vu', $2, $3, $4, 'CLINIC', $5)",
                CLINIC,
                ma,
                f"Siêu âm {ma}",
                gia,
                NODE,
            )
        cols = {"selection_status": selection, "routing_status": routing, **extra}
        names = ", ".join(cols)
        params = ", ".join(f"${i + 8}" for i in range(len(cols)))
        return str(
            await conn.fetchval(
                f"""
                INSERT INTO service_order (clinic_id, visit_id, consultation_id,
                    service_code, service_name, node_code, exec_status,
                    recorded_by, authorized_by, authorized_at, {names})
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'authorized',
                        $7::uuid, $7::uuid, now(), {params})
                RETURNING id::text
                """,  # noqa: S608 — tên cột cố định trong test
                CLINIC,
                visit_id or rb.visit_id,
                consultation_id or rb.consultation_id,
                ma,
                f"Siêu âm {ma}",
                NODE,
                rb.bac_si.staff_id,
                *cols.values(),
            )
        )


async def _assign(
    rb: RB,
    oid: str,
    room: str,
    rev: int,
    *,
    key: str | None = None,
    who: StaffIdentity | None = None,
    reason: str = "INITIAL_ASSIGNMENT",
    ref: str | None = None,
) -> dict[str, Any]:
    return await rb.svc.assign(
        order_id=oid,
        room_id=room,
        expected_routing_revision=rev,
        reason_code=reason,
        recommendation_ref=ref,
        identity=who or rb.truong_ca,
        idempotency_key=key or f"rt-{uuid.uuid4().hex}",
    )


async def _invalidate(
    rb: RB, oid: str, rev: int, *, key: str | None = None
) -> dict[str, Any]:
    return await rb.svc.invalidate(
        order_id=oid,
        expected_routing_revision=rev,
        reason_code="EQUIPMENT_FAILURE",
        identity=rb.truong_ca,
        idempotency_key=key or f"rt-{uuid.uuid4().hex}",
    )


async def _o(rb: RB, oid: str) -> asyncpg.Record:
    r = await rb.pool.fetchrow(
        "SELECT exec_status, room_id::text AS room_id, routing_status,"
        " routing_revision, assigned_by::text AS assigned_by FROM service_order"
        " WHERE id = $1::uuid",
        oid,
    )
    assert r is not None
    return r


async def _hang(rb: RB, oid: str) -> list[asyncpg.Record]:
    return list(
        await rb.pool.fetch(
            "SELECT id::text AS id, room_id::text AS room_id, status, eligible_at,"
            " created_at FROM queue_entry WHERE ref_id = $1::uuid"
            " AND reason = 'SERVICE' ORDER BY created_at",
            oid,
        )
    )


async def _su_kien(rb: RB, oid: str) -> list[tuple[str, dict[str, Any]]]:
    rows = await rb.pool.fetch(
        "SELECT event_type, payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND aggregate_type = 'service_order' ORDER BY recorded_at",
        oid,
    )
    return [(r["event_type"], json.loads(r["payload"])) for r in rows]


async def _loi(coro: Any, code: str) -> Any:
    with pytest.raises((LuotKhamConflictError, LuotKhamValidationError)) as exc:
        await coro
    assert exc.value.error_code == code, exc.value
    return exc.value


async def _paid(rb: RB, oid: str) -> None:
    """Dấu vết tiền PAID của phòng khám cho chỉ định (FinanceGate → PAID)."""
    async with rb.pool.acquire() as conn:
        cyc = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, created_by, paid_at,"
            " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 200000,"
            " 'r', 'CASH', 'PAID', $4::uuid, now(), $4::uuid)",
            cyc,
            CLINIC,
            rb.visit_id,
            rb.truong_ca.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4, 'SA', 1, 200000, 200000, 'CLINIC')",
            CLINIC,
            cyc,
            rb.visit_id,
            oid,
        )


# ---------------------------------------------------------------------------
# 1–3. Trạng thái đầu và xếp phòng thành công
# ---------------------------------------------------------------------------


async def test_1_chi_dinh_chinh_thuc_moi_la_unassigned_rev0(
    kb: Any,
) -> None:
    from tests.services.test_luot_kham_service_db import _vao_kham

    phien = await _vao_kham(kb)
    r = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    [oid] = r["order_ids"]
    o = await kb.pool.fetchrow(
        "SELECT selection_status, routing_status, routing_revision, room_id"
        " FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert (o["selection_status"], o["routing_status"], o["routing_revision"]) == (
        "PENDING",
        "UNASSIGNED",
        0,
    )
    assert o["room_id"] is None


async def test_2_da_thu_tien_xep_phong_thanh_cong(rb: RB) -> None:
    oid = await _cd(rb, gia=200_000)
    await _paid(rb, oid)
    r = await _assign(rb, oid, rb.sa1, 0)
    assert r == {
        "ok": True,
        "order_id": oid,
        "changed": True,
        "routing_status": "ASSIGNED",
        "room_id": rb.sa1,
        "routing_revision": 1,
        "queue_status": "waiting",
    }
    o = await _o(rb, oid)
    assert (o["routing_status"], o["room_id"], o["routing_revision"]) == (
        "ASSIGNED",
        rb.sa1,
        1,
    )
    # Hình chiếu cho reader cũ tới Slice 6.
    assert o["exec_status"] == "assigned"
    assert o["assigned_by"] == rb.truong_ca.staff_id
    [q] = await _hang(rb, oid)
    assert (q["room_id"], q["status"]) == (rb.sa1, "waiting")
    [(ev, pl)] = await _su_kien(rb, oid)
    assert ev == "service.routed"
    assert pl == {
        "visit_id": rb.visit_id,
        "from_room_id": None,
        "to_room_id": rb.sa1,
        "routing_revision": 1,
        "reason_code": "INITIAL_ASSIGNMENT",
        "recommendation_ref": None,
        # P3 (25/09/2026): nguồn của lần xếp — không truyền nguồn = "khac".
        "nguon": "khac",
    }


async def test_3_mien_phi_xep_phong_thanh_cong(rb: RB) -> None:
    oid = await _cd(rb, gia=0)
    r = await _assign(rb, oid, rb.sa1, 0)
    assert r["changed"] is True and r["routing_revision"] == 1


# ---------------------------------------------------------------------------
# 4–5. Selection + FinanceGate chặn đúng lý do
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sel", ["PENDING", "NOT_SELECTED"])
async def test_4_chua_chon_khong_xep_duoc(rb: RB, sel: str) -> None:
    oid = await _cd(rb, selection=sel)
    await _loi(_assign(rb, oid, rb.sa1, 0), "SERVICE_NOT_SELECTED")
    assert await _hang(rb, oid) == []


async def test_5_tai_chinh_chua_san_sang_giu_ly_do_chi_tiet(rb: RB) -> None:
    due = await _cd(rb, gia=100_000)
    e = await _loi(_assign(rb, due, rb.sa1, 0), "SERVICE_FINANCE_NOT_READY")
    assert e.finance_reason == "SERVICE_PAYMENT_REQUIRED"

    cho = await _cd(rb, gia=100_000)
    async with rb.pool.acquire() as conn:
        cyc = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, created_by) VALUES ($1::uuid,"
            " $2::uuid, $3::uuid, 'dich_vu', 100000, 'r', 'QR',"
            " 'PENDING_VERIFICATION', $4::uuid)",
            cyc,
            CLINIC,
            rb.visit_id,
            rb.truong_ca.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4, 'SA', 1, 100000, 100000, 'CLINIC')",
            CLINIC,
            cyc,
            rb.visit_id,
            cho,
        )
    e = await _loi(_assign(rb, cho, rb.sa1, 0), "SERVICE_FINANCE_NOT_READY")
    assert e.finance_reason == "SERVICE_PAYMENT_PENDING_VERIFICATION"

    ma_dt = f"RT-DT-{rb.duoi}"
    await rb.pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price, billing_owner, node_code) VALUES ($1::uuid, 'dich_vu', $2,"
        " 'Đối tác', NULL, 'EXTERNAL_PARTNER', $3)",
        CLINIC,
        ma_dt,
        NODE,
    )
    dt = await _cd(rb, gia=None)
    await rb.pool.execute(
        "UPDATE service_order SET service_code = $2 WHERE id = $1::uuid", dt, ma_dt
    )
    # Đối tác tự thu (Tuyền chốt 27/09/2026): khách trả thẳng đối tác → phòng
    # khám không chờ tiền, xếp phòng (lấy mẫu) được ngay.
    await _assign(rb, dt, rb.sa1, 0)
    assert [h["room_id"] for h in await _hang(rb, dt)] == [rb.sa1]
    for oid in (due, cho):
        assert await _hang(rb, oid) == []
        assert (await _o(rb, oid))["routing_revision"] == 0


# ---------------------------------------------------------------------------
# 6–10. Biên nhận, no-op cùng phòng, hai người cùng lúc, lệch phòng khám
# ---------------------------------------------------------------------------


async def test_6_cung_khoa_gui_lai_mot_lan(rb: RB) -> None:
    oid = await _cd(rb)
    key = f"rt-{uuid.uuid4().hex}"
    r1 = await _assign(rb, oid, rb.sa1, 0, key=key)
    r2 = await _assign(rb, oid, rb.sa1, 0, key=key)  # revision nay là 1 — vẫn phát lại
    assert r2 == r1
    assert len(await _hang(rb, oid)) == 1
    assert len(await _su_kien(rb, oid)) == 1
    assert (await _o(rb, oid))["routing_revision"] == 1


async def test_7_cung_khoa_khac_noi_dung(rb: RB) -> None:
    oid = await _cd(rb)
    key = f"rt-{uuid.uuid4().hex}"
    await _assign(rb, oid, rb.sa1, 0, key=key)
    await _loi(_assign(rb, oid, rb.sa2, 0, key=key), "IDEMPOTENCY_KEY_REUSED")


async def test_8_cung_phong_khoa_moi_khong_doi_gi(rb: RB) -> None:
    oid = await _cd(rb)
    await _assign(rb, oid, rb.sa1, 0)
    [q0] = await _hang(rb, oid)
    r = await _assign(rb, oid, rb.sa1, 1, reason="MANUAL_CORRECTION")
    assert r["changed"] is False and r["routing_revision"] == 1
    assert r["queue_status"] == "waiting"
    assert (await _o(rb, oid))["routing_revision"] == 1
    assert len(await _su_kien(rb, oid)) == 1
    [q1] = await _hang(rb, oid)
    assert (q1["id"], q1["eligible_at"]) == (q0["id"], q0["eligible_at"])


async def test_9_hai_nguoi_cung_revision_mot_nguoi_thang(rb: RB) -> None:
    oid = await _cd(rb)
    kq = await asyncio.gather(
        _assign(rb, oid, rb.sa1, 0, who=rb.truong_ca),
        _assign(rb, oid, rb.sa2, 0, who=rb.truong_ca_2),
        return_exceptions=True,
    )
    ok = [x for x in kq if isinstance(x, dict)]
    loi = [x for x in kq if isinstance(x, Exception)]
    assert len(ok) == 1 and len(loi) == 1
    assert isinstance(loi[0], LuotKhamConflictError)
    assert loi[0].error_code == "ROUTING_REVISION_CONFLICT"
    assert len(await _hang(rb, oid)) == 1
    assert len(await _su_kien(rb, oid)) == 1


async def test_10_chi_dinh_hoac_phong_khac_phong_kham(rb: RB) -> None:
    oid = await _cd(rb)
    # Quyền cấp theo từng phòng khám: người của phòng khám lạ bị chặn ngay ở
    # cửa quyền, trước cả khi đọc chỉ định. Ranh giới không đổi.
    khac = dataclasses.replace(rb.truong_ca, clinic_id=str(uuid.uuid4()))
    with pytest.raises(Exception, match="Không tìm thấy|chưa được cấp quyền"):
        await _assign(rb, oid, rb.sa1, 0, who=khac)
    await _loi(_assign(rb, oid, str(uuid.uuid4()), 0), "ROOM_NOT_FOUND")
    o = await _o(rb, oid)
    assert (o["routing_status"], o["routing_revision"]) == ("UNASSIGNED", 0)


# ---------------------------------------------------------------------------
# 11–13, 21. Phòng phải đủ điều kiện — kể cả khi có gợi ý
# ---------------------------------------------------------------------------


async def test_11_13_phong_khong_du_dieu_kien(rb: RB) -> None:
    oid = await _cd(rb)
    await _loi(_assign(rb, oid, rb.tat, 0), "ROOM_INACTIVE")
    await _loi(_assign(rb, oid, rb.ngung, 0), "ROOM_NOT_ACCEPTING")
    await _loi(_assign(rb, oid, rb.khac_node, 0), "ROOM_NOT_SERVING_SERVICE")
    assert await _hang(rb, oid) == []


async def test_21_goi_y_cu_khong_vuot_duoc_lenh(rb: RB) -> None:
    oid = await _cd(rb)
    goi_y = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert rb.sa1 in {c["room_id"] for c in goi_y["candidates"]}
    # Phòng đóng SAU khi gợi ý, TRƯỚC khi bấm.
    await rb.pool.execute(
        "UPDATE clinic_room SET accepting = false WHERE id = $1::uuid", rb.sa1
    )
    await _loi(
        _assign(rb, oid, rb.sa1, 0, ref=goi_y["recommendation_ref"]),
        "ROOM_NOT_ACCEPTING",
    )
    assert (await _o(rb, oid))["routing_status"] == "UNASSIGNED"


# ---------------------------------------------------------------------------
# 14–16. Đổi phòng trước khi bắt đầu: giữ tuổi chờ; sau khi gọi / bắt đầu thì không
# ---------------------------------------------------------------------------


async def test_14_doi_phong_giu_tuoi_cho(rb: RB) -> None:
    oid = await _cd(rb)
    await _assign(rb, oid, rb.sa1, 0)
    # Khách đã chờ 20 phút ở SA1.
    await rb.pool.execute(
        "UPDATE queue_entry SET eligible_at = now() - interval '20 minutes',"
        " created_at = now() - interval '20 minutes' WHERE ref_id = $1::uuid",
        oid,
    )
    [q0] = await _hang(rb, oid)
    r = await _assign(rb, oid, rb.sa2, 1, reason="LOAD_BALANCE")
    assert r["changed"] is True and r["routing_revision"] == 2
    live = [q for q in await _hang(rb, oid) if q["status"] not in ("cancelled",)]
    assert len(live) == 1
    assert live[0]["room_id"] == rb.sa2
    assert live[0]["eligible_at"] == q0["eligible_at"]
    assert live[0]["created_at"] == q0["created_at"]
    evs = await _su_kien(rb, oid)
    assert [e for e, _ in evs] == ["service.routed", "service.routed"]
    assert evs[1][1]["from_room_id"] == rb.sa1 and evs[1][1]["to_room_id"] == rb.sa2


@pytest.mark.parametrize("trang_thai", ["called", "serving"])
async def test_15_doi_phong_khi_da_goi_hoac_dang_lam_bi_tu_choi(
    rb: RB, trang_thai: str
) -> None:
    oid = await _cd(rb)
    await _assign(rb, oid, rb.sa1, 0)
    await rb.pool.execute(
        "UPDATE queue_entry SET status = $2 WHERE ref_id = $1::uuid", oid, trang_thai
    )
    await _loi(_assign(rb, oid, rb.sa2, 1), "ROOM_ALREADY_CALLED")
    o = await _o(rb, oid)
    assert (o["room_id"], o["routing_revision"]) == (rb.sa1, 1)


async def test_16_truc_thuc_hien_dang_lam_chan_ca_khi_hang_cho_trong_dung_duoc(
    rb: RB,
) -> None:
    oid = await _cd(rb)
    await _assign(rb, oid, rb.sa1, 0)
    await rb.pool.execute(
        "UPDATE service_order SET execution_status = 'IN_PROGRESS' WHERE id = $1::uuid",
        oid,
    )
    [q] = await _hang(rb, oid)
    assert q["status"] == "waiting"  # hàng chờ "trông" vẫn đổi được
    await _loi(_assign(rb, oid, rb.sa2, 1), "SERVICE_ALREADY_IN_PROGRESS")
    await _loi(_invalidate(rb, oid, 1), "SERVICE_ALREADY_IN_PROGRESS")
    await rb.pool.execute(
        "UPDATE service_order SET execution_status = 'COMPLETED' WHERE id = $1::uuid",
        oid,
    )
    await _loi(_assign(rb, oid, rb.sa2, 1), "SERVICE_EXECUTION_TERMINAL")


# ---------------------------------------------------------------------------
# 17–20. Mất hiệu lực trước khi bắt đầu, xếp lại giữ tuổi chờ
# ---------------------------------------------------------------------------


async def test_17_19_mat_hieu_luc_roi_xep_lai(rb: RB) -> None:
    oid = await _cd(rb)
    await _assign(rb, oid, rb.sa1, 0)
    await rb.pool.execute(
        "UPDATE queue_entry SET eligible_at = now() - interval '15 minutes'"
        " WHERE ref_id = $1::uuid",
        oid,
    )
    [q0] = await _hang(rb, oid)

    r = await _invalidate(rb, oid, 1)
    assert (r["routing_status"], r["room_id"], r["routing_revision"]) == (
        "REASSIGNMENT_REQUIRED",
        None,
        2,
    )
    o = await _o(rb, oid)
    assert (o["routing_status"], o["room_id"], o["routing_revision"]) == (
        "REASSIGNMENT_REQUIRED",
        None,
        2,
    )
    assert o["exec_status"] == "authorized"  # hình chiếu cũ: chưa có phòng
    # 18. Chỗ chờ ở phòng cũ hết hiệu lực — phòng cũ không gọi được khách nữa.
    [q] = await _hang(rb, oid)
    assert q["status"] == "cancelled"
    await _loi(_invalidate(rb, oid, 2), "ROUTING_ALREADY_INVALIDATED")
    ev, pl = (await _su_kien(rb, oid))[-1]
    assert ev == "service.routing_invalidated"
    assert pl == {
        "visit_id": rb.visit_id,
        "from_room_id": rb.sa1,
        "routing_revision": 2,
        "reason_code": "EQUIPMENT_FAILURE",
    }

    # 19. Xếp lại: ASSIGNED ở phòng mới, tuổi chờ giữ nguyên.
    r = await _assign(rb, oid, rb.sa2, 2, reason="EQUIPMENT_FAILURE")
    assert (r["routing_status"], r["room_id"], r["routing_revision"]) == (
        "ASSIGNED",
        rb.sa2,
        3,
    )
    live = [x for x in await _hang(rb, oid) if x["status"] != "cancelled"]
    assert len(live) == 1 and live[0]["room_id"] == rb.sa2
    assert live[0]["eligible_at"] == q0["eligible_at"]


async def test_mat_hieu_luc_chi_khi_da_xep(rb: RB) -> None:
    oid = await _cd(rb)
    await _loi(_invalidate(rb, oid, 0), "ROUTING_NOT_ASSIGNED")


async def test_ly_do_other_bi_tu_choi_vi_chua_co_cho_luu_ghi_chu(rb: RB) -> None:
    oid = await _cd(rb)
    await _loi(
        _assign(rb, oid, rb.sa1, 0, reason="OTHER"), "ROUTING_REASON_NOTE_UNSUPPORTED"
    )
    await _loi(_assign(rb, oid, rb.sa1, 0, reason="BLAH"), "ROUTING_REASON_INVALID")


# ---------------------------------------------------------------------------
# 22–25. Gợi ý phòng theo luật
# ---------------------------------------------------------------------------


async def test_22_25_goi_y_chi_phong_du_dieu_kien_va_khong_ghi_gi(rb: RB) -> None:
    oid = await _cd(rb)
    truoc = await rb.pool.fetchval("SELECT count(*) FROM event_log")
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    ids = [c["room_id"] for c in g["candidates"]]
    assert rb.sa1 in ids and rb.sa2 in ids
    assert rb.tat not in ids and rb.ngung not in ids and rb.khac_node not in ids
    assert [c["rank"] for c in g["candidates"]] == list(range(1, len(ids) + 1))
    assert g["advisor"] == "rule-v1" and g["recommendation_ref"]
    # 25. Không đổi trạng thái, không hàng chờ, không sự kiện.
    o = await _o(rb, oid)
    assert (o["routing_status"], o["routing_revision"]) == ("UNASSIGNED", 0)
    assert await _hang(rb, oid) == []
    assert await rb.pool.fetchval("SELECT count(*) FROM event_log") == truoc


def test_23_lich_truc_va_tai_chi_la_tin_hieu_xep_hang() -> None:
    def p(i: str, truc: bool, tai: int, sort: int = 1) -> sr.RoomCandidate:
        return sr.RoomCandidate(
            room_id=i, code=i, sort=sort, co_nguoi_truc=truc, tai=tai
        )

    xep = sr.rank_rooms([p("a", False, 0), p("b", True, 5), p("c", True, 1)])
    assert [c["room_id"] for c in xep] == ["c", "b", "a"]
    # Phòng không có người trực vẫn được gợi ý — không phải chốt cứng.
    assert xep[2]["reason_codes"] == ["NO_ROSTER_SIGNAL", "LOWEST_QUEUE"]
    assert "STAFF_ON_SHIFT" in xep[0]["reason_codes"]


class _DemTruyVan:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn
        self.so = 0

    async def fetch(self, *a: Any, **kw: Any) -> Any:
        self.so += 1
        return await self._conn.fetch(*a, **kw)


async def test_24_tap_phong_mot_truy_van(rb: RB) -> None:
    async with rb.pool.acquire() as conn:
        dem = _DemTruyVan(conn)
        rooms = await sr.eligible_rooms(dem, CLINIC, NODE)
    assert dem.so == 1 and len(rooms) >= 2


async def test_quyen_goi_y_va_xep(rb: RB) -> None:
    """Xếp phòng là QUYỀN, và quyền thu được thì mất ngay.

    Trước 23/09 bài này dựa vào "bác sĩ không nằm trong danh sách vai điều
    phối". Nay preset của bác sĩ CÓ khối "Điều phối khách" (Tuyền chốt: bác sĩ
    được xếp phòng), nên bài kiểm phải hỏi đúng câu nó muốn hỏi: **thu quyền
    thì không xếp được nữa**, chứ không phải "vai này thì cấm".
    """
    from clinicai.services.permission_service import PermissionService

    oid = await _cd(rb)
    # Quản lý thu khối Điều phối của bác sĩ.
    async with rb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability"
            " WHERE work_pack = 'quan_tri_quyen' ON CONFLICT DO NOTHING",
            CLINIC,
            rb.truong_ca.staff_id,
        )
    await PermissionService(rb.pool).thu_khoi(
        staff_id=rb.bac_si.staff_id, khoi="dieu_phoi", identity=rb.truong_ca
    )
    with pytest.raises(SafetyGateError):
        await _assign(rb, oid, rb.sa1, 0, who=rb.bac_si)


# ---------------------------------------------------------------------------
# 26–28. Đường cũ không vượt được Selection / Finance
# ---------------------------------------------------------------------------


async def test_26_dieu_phoi_cu_khong_vuot_duoc_cho_chi_dinh_moi(rb: RB) -> None:
    oid = await _cd(rb, selection="PENDING")
    with pytest.raises(LuotKhamConflictError) as exc:
        await LuotKhamService(rb.pool).dispatch_order(
            order_id=oid, room_id=rb.sa1, expected_version=None, identity=rb.truong_ca
        )
    assert exc.value.error_code == "LIFECYCLE_ROUTING_REQUIRED"
    assert await _hang(rb, oid) == []
    o = await _o(rb, oid)
    assert (o["exec_status"], o["room_id"]) == ("authorized", None)


async def test_27_dong_cu_van_dieu_phoi_duong_cu(rb: RB) -> None:
    oid = await _cd(rb, selection=None, routing=None)
    r = await LuotKhamService(rb.pool).dispatch_order(
        order_id=oid, room_id=rb.sa1, expected_version=None, identity=rb.truong_ca
    )
    assert r["ok"] is True
    o = await _o(rb, oid)
    assert (o["exec_status"], o["room_id"], o["routing_status"]) == (
        "assigned",
        rb.sa1,
        None,
    )


async def test_db_chan_assigned_khong_phong_va_mat_hieu_luc_con_phong(rb: RB) -> None:
    oid = await _cd(rb)
    with pytest.raises(asyncpg.CheckViolationError):
        await rb.pool.execute(
            "UPDATE service_order SET routing_status = 'ASSIGNED' WHERE id = $1::uuid",
            oid,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await rb.pool.execute(
            "UPDATE service_order SET routing_status = 'REASSIGNMENT_REQUIRED',"
            " room_id = $2::uuid WHERE id = $1::uuid",
            oid,
            rb.sa1,
        )


async def test_unassigned_co_phong_doi_tac_khong_thanh_phan_phong(rb: RB) -> None:
    """Luồng đối tác tự lấy mẫu ghi phòng đối tác lên chỉ định UNASSIGNED —
    Assign không coi đó là phân phòng: xếp phòng thật vẫn là lần đầu (rev 0→1)."""
    oid = await _cd(rb)
    await rb.pool.execute(
        "UPDATE service_order SET room_id = $2::uuid WHERE id = $1::uuid",
        oid,
        rb.sa2,
    )
    r = await _assign(rb, oid, rb.sa2, 0)
    assert (r["changed"], r["routing_revision"]) == (True, 1)
    [(_, pl)] = await _su_kien(rb, oid)
    assert pl["from_room_id"] is None


# ---------------------------------------------------------------------------
# 29. Sinh hiệu KHÔNG chặn xếp phòng (Tuyền chốt 23/09/2026)
# ---------------------------------------------------------------------------


async def test_29_chua_do_sinh_hieu_van_xep_phong_duoc(rb: RB) -> None:
    """Khách đi thẳng làm siêu âm là chuyện thường ngày — không khoá cửa."""
    from clinicai.services import luot_kham_rules as rules

    # Seam vẫn là chỗ DUY NHẤT trả lời câu hỏi này; hôm nay nó trả lời "không chặn".
    assert rules.vitals_routing_block(vitals_recorded=False) is None
    assert rules.vitals_routing_block(vitals_recorded=True) is None
    oid = await _cd(rb)
    await rb.pool.execute(
        "UPDATE encounter_flow SET vitals_status = 'pending' WHERE visit_id = $1::uuid",
        rb.visit_id,
    )
    kq = await _assign(rb, oid, rb.sa1, 0)
    assert kq["routing_status"] == "ASSIGNED"


# ---------------------------------------------------------------------------
# 30. Lỗi giữa chừng lùi hết: hàng chờ + routing + sự kiện + biên nhận
# ---------------------------------------------------------------------------


async def test_30_loi_truoc_bien_nhan_lui_het(
    rb: RB, monkeypatch: pytest.MonkeyPatch
) -> None:
    oid = await _cd(rb)

    async def hong(*_: Any, **__: Any) -> None:
        raise RuntimeError("chết trước khi ghi biên nhận")

    # Biên nhận nay ở nền chung `lenh_kham_core` (bóc 24/09) — giả lỗi ngay
    # tại chỗ khối này gọi nó.
    import clinicai.services.service_routing_service as khoi

    monkeypatch.setattr(khoi, "bien_nhan_ghi", hong)
    with pytest.raises(RuntimeError):
        await _assign(rb, oid, rb.sa1, 0)
    o = await _o(rb, oid)
    assert (o["routing_status"], o["routing_revision"], o["room_id"]) == (
        "UNASSIGNED",
        0,
        None,
    )
    assert await _hang(rb, oid) == []
    assert await _su_kien(rb, oid) == []
