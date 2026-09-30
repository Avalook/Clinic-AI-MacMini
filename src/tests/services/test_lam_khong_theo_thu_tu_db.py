"""V4 — làm dịch vụ KHÔNG theo thứ tự (Tuyền 30/09/2026, hướng "mở hết").

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55562/postgres \
        .venv/bin/pytest src/tests/services/test_lam_khong_theo_thu_tu_db.py

Ba chuyện có thật ở phòng khám:
  * khách đang siêu âm dở ở phòng A, phòng B (lấy mẫu) rảnh và gọi khách sang —
    trước đây phòng B nhận 409 PATIENT_BUSY cứng (prod 29/09: 23 lần/ngày);
  * bấm Bắt đầu nhầm khách — cần huỷ ngay, không phải đi tìm trưởng ca;
  * Dừng → Làm lại: khách phải hiện lại ở hàng chờ của phòng.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from clinicai.services.luot_kham_service import LuotKhamConflictError
from tests.services import test_service_execution_db as _goc
from tests.services.test_service_execution_db import CLINIC, KB

# Dùng lại fixture của bộ test EXECUTION (lượt + chỉ định đã thu tiền, đã xếp
# phòng) — gán lại ở mức module để pytest thấy.
pool = _goc.pool
kb = _goc.kb

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chi_dinh_thu_hai(kb: KB) -> tuple[str, str, str]:
    """Chỉ định thứ hai của cùng lượt, xếp vào một phòng KHÁC, đã thu tiền."""
    async with kb.pool.acquire() as conn:
        phong = await conn.fetchrow(
            "SELECT id::text, name FROM clinic_room WHERE clinic_id = $1::uuid"
            "   AND id <> $2::uuid ORDER BY created_at, id LIMIT 1",
            CLINIC,
            kb.room_id,
        )
        assert phong is not None
        con_id = await conn.fetchval(
            "SELECT consultation_id::text FROM service_order WHERE id = $1::uuid",
            kb.order_id,
        )
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_order WHERE id = $1::uuid", kb.order_id
        )
        oid = await conn.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status, routing_status,"
            " room_id, routing_revision, execution_status)"
            " VALUES ($1::uuid, $2::uuid, $6::uuid, $3, 'Dịch vụ thứ hai',"
            " 'DICHVU-SIEUAM', 'assigned', $4::uuid, $4::uuid, now(), 'SELECTED',"
            " 'ASSIGNED', $5::uuid, 1, 'PENDING') RETURNING id::text",
            CLINIC,
            kb.visit_id,
            ma_dv,
            kb.bs.staff_id,
            phong["id"],
            con_id,
        )
        await conn.execute(
            "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
            " ref_id, status, eligible_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
            " $3::uuid, 'SERVICE', $4::uuid, 'waiting', now())",
            CLINIC,
            kb.visit_id,
            phong["id"],
            oid,
        )
        cycle = await conn.fetchval(
            "SELECT payment_cycle_id::text FROM payment_bill_line"
            " WHERE source_id::text = $1",
            kb.order_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4::uuid, 'Dịch vụ thứ hai', 1, 0,"
            " 0, 'CLINIC')",
            CLINIC,
            cycle,
            kb.visit_id,
            oid,
        )
    return oid, phong["id"], phong["name"]


async def _bat_dau(
    kb: KB, order_id: str, *, giai_phong: bool = False
) -> dict[str, Any]:
    rev = await kb.pool.fetchrow(
        "SELECT execution_revision, routing_revision FROM service_order"
        " WHERE id = $1::uuid",
        order_id,
    )
    assert rev is not None
    return await kb.svc.bat_dau(
        order_id=order_id,
        expected_execution_revision=int(rev["execution_revision"]),
        expected_routing_revision=int(rev["routing_revision"]),
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
        giai_phong=giai_phong,
    )


async def _trang_thai(kb: KB, order_id: str) -> tuple[str, str | None]:
    """(execution_status của chỉ định, trạng thái chỗ chờ SỐNG hoặc mới nhất)."""
    ex = await kb.pool.fetchval(
        "SELECT execution_status FROM service_order WHERE id = $1::uuid", order_id
    )
    q = await kb.pool.fetchval(
        "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
        " ORDER BY (status NOT IN ('done', 'left', 'cancelled')) DESC,"
        "          updated_at DESC LIMIT 1",
        order_id,
    )
    return str(ex), q


async def _lan(kb: KB, order_id: str) -> list[dict[str, Any]]:
    rows = await kb.pool.fetch(
        "SELECT attempt_no, status, interruption_reason_code,"
        "       interruption_reason_note FROM service_execution_attempt"
        " WHERE service_order_id = $1::uuid ORDER BY attempt_no",
        order_id,
    )
    return [dict(r) for r in rows]


async def _su_kien(kb: KB, order_id: str, ten: str) -> list[dict[str, Any]]:
    rows = await kb.pool.fetch(
        "SELECT payload FROM domain_event WHERE aggregate_id = $1::uuid"
        "   AND event_type = $2 ORDER BY recorded_at",
        order_id,
        ten,
    )
    return [json.loads(r["payload"]) for r in rows]


async def _phieu(kb: KB, order_id: str, *, revision: int) -> None:
    form = await kb.pool.fetchrow(
        "SELECT form_id, version FROM form_definition WHERE clinic_id = $1::uuid"
        " ORDER BY form_id, version LIMIT 1",
        CLINIC,
    )
    assert form is not None
    await kb.pool.execute(
        "INSERT INTO form_instance (clinic_id, service_order_id, form_id, version,"
        " revision, nhap_boi) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)",
        CLINIC,
        order_id,
        form["form_id"],
        form["version"],
        revision,
        kb.bs.staff_id,
    )


# ── (a) Chuyển khách sang phòng mình ────────────────────────────────────────


async def test_khach_dang_lam_phong_khac_thi_hoi_kem_ten_phong(kb: KB) -> None:
    b, _phong_b, _ = await _chi_dinh_thu_hai(kb)
    ten_a = await kb.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", kb.room_id
    )
    await _bat_dau(kb, kb.order_id)

    with pytest.raises(LuotKhamConflictError) as e:
        await _bat_dau(kb, b)
    assert e.value.error_code == "PATIENT_BUSY"
    assert e.value.chi_tiet is not None
    assert e.value.chi_tiet["phong"] == ten_a
    assert e.value.chi_tiet["chuyen_duoc"] is True
    assert ten_a in str(e.value)
    # Chưa đồng ý thì không đụng gì phòng kia.
    assert await _trang_thai(kb, kb.order_id) == ("IN_PROGRESS", "serving")
    assert await _trang_thai(kb, b) == ("PENDING", "blocked")


async def test_dong_y_chuyen_thi_dung_phong_kia_roi_bat_dau_o_day(kb: KB) -> None:
    b, phong_b, ten_b = await _chi_dinh_thu_hai(kb)
    await _bat_dau(kb, kb.order_id)

    kq = await _bat_dau(kb, b, giai_phong=True)

    assert kq["execution_status"] == "IN_PROGRESS"
    assert await _trang_thai(kb, b) == ("IN_PROGRESS", "serving")
    # Phòng kia: lần làm dừng có lý do, chỉ định về chờ làm, khách "đợi quay
    # lại" ở hàng phòng kia (không mất khỏi hàng).
    assert await _trang_thai(kb, kb.order_id) == ("PENDING", "blocked")
    lan = await _lan(kb, kb.order_id)
    assert lan[-1]["status"] == "INTERRUPTED"
    assert lan[-1]["interruption_reason_code"] == "PATIENT_MOVED"
    assert ten_b in (lan[-1]["interruption_reason_note"] or "")
    ev = await _su_kien(kb, kb.order_id, "service.patient_moved")
    assert len(ev) == 1
    assert ev[0]["from_room_id"] == kb.room_id
    assert ev[0]["to_room_id"] == phong_b
    assert ev[0]["to_service_order_id"] == b
    # Con trỏ "khách đang ở đâu" theo phòng mới.
    assert (
        await kb.pool.fetchval(
            "SELECT current_room_id::text FROM visit WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
        == phong_b
    )

    # Phòng mới xong → khách hiện lại ở hàng phòng cũ, làm tiếp được (lần #2).
    th = await kb.svc.xem(order_id=b, identity=kb.bs)
    await kb.svc.xong(
        order_id=b,
        attempt_id=th["lan_dang_chay"]["id"],
        expected_execution_revision=th["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert await _trang_thai(kb, kb.order_id) == ("PENDING", "waiting")
    lai = await _bat_dau(kb, kb.order_id)
    assert lai["attempt_no"] == 2


async def test_phong_kia_da_dien_phieu_thi_khong_chuyen_duoc(kb: KB) -> None:
    b, _phong_b, _ = await _chi_dinh_thu_hai(kb)
    await _bat_dau(kb, kb.order_id)
    await _phieu(kb, kb.order_id, revision=2)

    with pytest.raises(LuotKhamConflictError) as e:
        await _bat_dau(kb, b)
    assert e.value.chi_tiet is not None
    assert e.value.chi_tiet["chuyen_duoc"] is False
    with pytest.raises(LuotKhamConflictError) as e2:
        await _bat_dau(kb, b, giai_phong=True)
    assert e2.value.error_code == "PATIENT_BUSY"
    assert await _trang_thai(kb, kb.order_id) == ("IN_PROGRESS", "serving")
    assert await _su_kien(kb, kb.order_id, "service.patient_moved") == []


async def test_phieu_nhap_chua_ai_go_thi_van_chuyen_duoc(kb: KB) -> None:
    """Mở khách là màn tự mở phiếu nháp (revision 0) — chưa ai gõ, không chặn."""
    b, _phong_b, _ = await _chi_dinh_thu_hai(kb)
    await _bat_dau(kb, kb.order_id)
    await _phieu(kb, kb.order_id, revision=0)
    await _bat_dau(kb, b, giai_phong=True)
    assert await _trang_thai(kb, b) == ("IN_PROGRESS", "serving")


# ── (b) Huỷ bắt đầu nhầm ────────────────────────────────────────────────────


async def test_huy_bat_dau_nham_dua_khach_ve_hang_cho(kb: KB) -> None:
    mo = await _bat_dau(kb, kb.order_id)
    th = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert th["huy_bat_dau_duoc"] is True

    kq = await kb.svc.huy_bat_dau(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["execution_status"] == "PENDING"
    assert await _trang_thai(kb, kb.order_id) == ("PENDING", "waiting")
    lan = await _lan(kb, kb.order_id)
    assert lan[-1]["status"] == "INTERRUPTED"
    assert lan[-1]["interruption_reason_code"] == "STARTED_IN_ERROR"
    assert len(await _su_kien(kb, kb.order_id, "service.start_cancelled")) == 1
    # Chỗ chờ khác của lượt (đợi quay lại) mở ra — không còn ai 'serving'.
    assert (
        await kb.pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
            "   AND status IN ('serving', 'blocked')",
            kb.visit_id,
        )
        == 0
    )
    th = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert th["huy_bat_dau_duoc"] is False
    # Bắt đầu lại được như thường.
    assert (await _bat_dau(kb, kb.order_id))["attempt_no"] == 2


async def test_da_dien_phieu_thi_khong_huy_bat_dau_duoc(kb: KB) -> None:
    mo = await _bat_dau(kb, kb.order_id)
    await _phieu(kb, kb.order_id, revision=1)
    th = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert th["huy_bat_dau_duoc"] is False
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.huy_bat_dau(
            order_id=kb.order_id,
            attempt_id=mo["attempt_id"],
            expected_execution_revision=mo["execution_revision"],
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )
    assert e.value.error_code == "RESULT_FORM_STARTED"
    assert await _trang_thai(kb, kb.order_id) == ("IN_PROGRESS", "serving")


async def test_huy_bat_dau_khi_chua_bat_dau_thi_bao_ro(kb: KB) -> None:
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.huy_bat_dau(
            order_id=kb.order_id,
            attempt_id=str(uuid.uuid4()),
            expected_execution_revision=0,
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )
    assert e.value.error_code == "EXECUTION_STATE_INVALID"


# ── Dừng → Làm lại: khách hiện lại ở hàng chờ phòng ─────────────────────────


async def test_dung_roi_lam_lai_khach_hien_lai_hang_cho(kb: KB) -> None:
    mo = await _bat_dau(kb, kb.order_id)
    dung = await kb.svc.gian_doan(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert await _trang_thai(kb, kb.order_id) == ("INTERRUPTED", "done")
    await kb.svc.chuan_bi_lam_lai(
        order_id=kb.order_id,
        interrupted_attempt_id=mo["attempt_id"],
        expected_execution_revision=dung["execution_revision"],
        ghi_chu=None,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert await _trang_thai(kb, kb.order_id) == ("PENDING", "waiting")
    # Vẫn MỘT dòng cho chỉ định trên màn phòng (mở lại chỗ cũ, không nhân đôi).
    assert (
        await kb.pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
        )
        == 1
    )
    assert (await _bat_dau(kb, kb.order_id))["attempt_no"] == 2
