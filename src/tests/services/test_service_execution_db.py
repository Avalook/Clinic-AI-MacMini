"""Thực hiện dịch vụ trên Postgres thật — contract EXECUTION v1.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55474/postgres \
        poetry run pytest src/tests/services/test_service_execution_db.py

Các ca ở đây là những ca contract nói rõ, và đều là chuyện xảy ra thật ở phòng
khám: máy hỏng giữa chừng, khách đổi ý ở cửa phòng, hai người cùng bấm, và một
request mạng cũ tới muộn.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.permission_service import cap_preset_mac_dinh
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.goi_mau_cu import ve_goi_mau_cu

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=6)
    yield p
    await p.close()


async def _nguoi(conn: asyncpg.Connection, role: str) -> StaffIdentity:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        f"Test {role} {uuid.uuid4().hex[:6]}",
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
        full_name="Test",
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


@dataclass
class KB:
    pool: asyncpg.Pool
    svc: ServiceExecutionService
    visit_id: str
    order_id: str
    room_id: str
    bs: StaffIdentity
    le_tan: StaffIdentity


@pytest_asyncio.fixture
async def kb(pool: asyncpg.Pool) -> KB:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        le_tan = await _nguoi(conn, "RECEPTION")
        loc = bs.location_id
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN test thực hiện', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"EX-{uuid.uuid4().hex[:10]}",
            loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', $3::uuid, now())"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
            bs.staff_id,
        )
        room = await conn.fetchval(
            "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid"
            " ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        con_id = await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
            " doctor_staff_id, started_by, started_at)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
            " $3::uuid, now()) RETURNING id::text",
            CLINIC,
            vid,
            bs.staff_id,
        )
        # Chỉ định đã qua Selection + Routing, tài chính coi như miễn thu
        # (không có giá) — phần tiền có bộ test riêng của FinanceGate.
        order_id = await conn.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status, routing_status,"
            " room_id, routing_revision, execution_status)"
            " VALUES ($1::uuid, $2::uuid, $6::uuid, $3, 'Dịch vụ test',"
            " 'DICHVU-SIEUAM', 'assigned', $4::uuid, $4::uuid, now(), 'SELECTED',"
            " 'ASSIGNED', $5::uuid, 1, 'PENDING') RETURNING id::text",
            CLINIC,
            vid,
            ma_dv,
            bs.staff_id,
            room,
            con_id,
        )
        await conn.execute(
            "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
            " ref_id, status, eligible_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
            " $3::uuid, 'SERVICE', $4::uuid, 'waiting', now())",
            CLINIC,
            vid,
            room,
            order_id,
        )
        # Đã thu tiền dịch vụ: FinanceGate là cổng thật trước khi bắt đầu, nên
        # test phải đi qua nó chứ không vòng tránh.
        cycle = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
            " amount, bill_revision, method, status, legacy, created_by, paid_at,"
            " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 300000,"
            " 'rev-test', 'CASH', 'PAID', false, $4::uuid, now(), $4::uuid)",
            cycle,
            CLINIC,
            vid,
            bs.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'dich_vu', 'service_order', $4::uuid, 'Dịch vụ test', 1, 300000,"
            " 300000, 'CLINIC')",
            CLINIC,
            cycle,
            vid,
            order_id,
        )
    return KB(pool, ServiceExecutionService(pool), vid, order_id, room, bs, le_tan)


async def _don(kb: KB) -> asyncpg.Record:
    row = await kb.pool.fetchrow(
        "SELECT execution_status, execution_revision FROM service_order"
        " WHERE id = $1::uuid",
        kb.order_id,
    )
    assert row is not None
    return row


async def _su_kien(kb: KB, ten: str) -> list[dict[str, Any]]:
    rows = await kb.pool.fetch(
        "SELECT payload FROM domain_event WHERE aggregate_id = $1::uuid"
        "   AND event_type = $2 ORDER BY recorded_at",
        kb.order_id,
        ten,
    )
    return [json.loads(r["payload"]) for r in rows]


async def test_bat_dau_tao_lan_lam_va_doi_hang_cho(kb: KB) -> None:
    kq = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["attempt_no"] == 1
    assert (await _don(kb))["execution_status"] == "IN_PROGRESS"

    hang = await kb.pool.fetchval(
        "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
    )
    assert hang == "serving"
    assert len(await _su_kien(kb, "service.started")) == 1


async def test_gui_lai_cung_khoa_khong_tao_lan_lam_thu_hai(kb: KB) -> None:
    khoa = str(uuid.uuid4())
    a = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=khoa,
    )
    b = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=khoa,
    )
    assert a == b
    so_lan = await kb.pool.fetchval(
        "SELECT count(*) FROM service_execution_attempt"
        " WHERE service_order_id = $1::uuid",
        kb.order_id,
    )
    assert so_lan == 1
    assert len(await _su_kien(kb, "service.started")) == 1


async def test_nguoi_thu_hai_bam_bat_dau_thi_bi_chan(kb: KB) -> None:
    """Hai nhân viên cùng bấm: một người thắng, người kia thấy màn đã cũ."""
    await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.bat_dau(
            order_id=kb.order_id,
            expected_execution_revision=0,
            expected_routing_revision=1,
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_xong_dong_lan_lam_va_dong_hang_cho(kb: KB) -> None:
    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    kq = await kb.svc.xong(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["execution_status"] == "COMPLETED"
    lan = await kb.pool.fetchrow(
        "SELECT status, completed_by::text AS ai FROM service_execution_attempt"
        " WHERE id = $1::uuid",
        mo["attempt_id"],
    )
    assert lan is not None and lan["status"] == "COMPLETED"
    assert lan["ai"] == kb.bs.staff_id
    hang = await kb.pool.fetchval(
        "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
    )
    assert hang == "done"
    assert len(await _su_kien(kb, "service.completed")) == 1


async def test_lenh_cu_den_muon_khong_dong_duoc_lan_lam_moi(kb: KB) -> None:
    """Máy hỏng → lần #1 dừng → lần #2 chạy → request Xong của #1 tới muộn."""
    lan1 = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    dung = await kb.svc.gian_doan(
        order_id=kb.order_id,
        attempt_id=lan1["attempt_id"],
        expected_execution_revision=lan1["execution_revision"],
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    lam_lai = await kb.svc.chuan_bi_lam_lai(
        order_id=kb.order_id,
        interrupted_attempt_id=lan1["attempt_id"],
        expected_execution_revision=dung["execution_revision"],
        ghi_chu="Đã đổi sang máy khác",
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    lan2 = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=lam_lai["execution_revision"],
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert lan2["attempt_no"] == 2

    # Request cũ của lần #1 tới muộn.
    with pytest.raises(LuotKhamConflictError) as loi:
        await kb.svc.xong(
            order_id=kb.order_id,
            attempt_id=lan1["attempt_id"],
            expected_execution_revision=lan2["execution_revision"],
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )
    assert loi.value.error_code == "EXECUTION_ATTEMPT_NOT_ACTIVE"
    assert (await _don(kb))["execution_status"] == "IN_PROGRESS"


async def test_khong_tu_lam_lai_sau_khi_gian_doan(kb: KB) -> None:
    """Gián đoạn KHÔNG tự mở lần làm mới — phải có người quyết."""
    lan1 = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    dung = await kb.svc.gian_doan(
        order_id=kb.order_id,
        attempt_id=lan1["attempt_id"],
        expected_execution_revision=lan1["execution_revision"],
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert dung["execution_status"] == "INTERRUPTED"
    # "Chờ làm" không phải giá trị lưu được — sau khi quyết làm lại thì về PENDING.
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.bat_dau(
            order_id=kb.order_id,
            expected_execution_revision=dung["execution_revision"],
            expected_routing_revision=1,
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_ly_do_khac_phai_ghi_ro(kb: KB) -> None:
    lan1 = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(ValidationError):
        await kb.svc.gian_doan(
            order_id=kb.order_id,
            attempt_id=lan1["attempt_id"],
            expected_execution_revision=lan1["execution_revision"],
            ly_do="OTHER",
            ghi_chu="   ",
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_khong_lam_khi_chua_bat_dau(kb: KB) -> None:
    kq = await kb.svc.khong_lam(
        order_id=kb.order_id,
        expected_execution_revision=0,
        ly_do="PATIENT_DECLINED_AT_ROOM",
        ghi_chu=None,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["execution_status"] == "NOT_PERFORMED"
    # Không sinh "lần làm giả".
    so_lan = await kb.pool.fetchval(
        "SELECT count(*) FROM service_execution_attempt"
        " WHERE service_order_id = $1::uuid",
        kb.order_id,
    )
    assert so_lan == 0
    hang = await kb.pool.fetchval(
        "SELECT status FROM queue_entry WHERE ref_id = $1::uuid", kb.order_id
    )
    assert hang == "done"
    assert len(await _su_kien(kb, "service.not_performed")) == 1


async def test_da_bat_dau_thi_khong_dung_duong_khong_lam(kb: KB) -> None:
    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.khong_lam(
            order_id=kb.order_id,
            expected_execution_revision=mo["execution_revision"],
            ly_do="PATIENT_DECLINED_AT_ROOM",
            ghi_chu=None,
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_le_tan_khong_bat_dau_duoc(kb: KB) -> None:
    await ve_goi_mau_cu(kb.pool, kb.le_tan)  # gói lego cũ (mở full lego 30/09)
    with pytest.raises(SafetyGateError):
        await kb.svc.bat_dau(
            order_id=kb.order_id,
            expected_execution_revision=0,
            expected_routing_revision=1,
            identity=kb.le_tan,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_man_hinh_cu_thi_bi_chan(kb: KB) -> None:
    await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(LuotKhamConflictError) as loi:
        await kb.svc.xong(
            order_id=kb.order_id,
            attempt_id=str(uuid.uuid4()),
            expected_execution_revision=0,
            identity=kb.bs,
            idempotency_key=str(uuid.uuid4()),
        )
    assert loi.value.error_code == "VERSION_CONFLICT"


# ── Câu đọc cho màn phòng ───────────────────────────────────────────────────
# Màn phòng bấm được hay không phụ thuộc hoàn toàn vào câu đọc này. Nó sai thì
# không có lỗi nào nổ — chỉ có nút bấm vào là bị từ chối, mà người làm không
# hiểu vì sao.


async def test_xem_tra_du_thu_de_bam_duoc_nam_lenh(kb: KB) -> None:
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)

    assert nhin["execution_status"] == "PENDING"
    # Hai số này là thứ khiến màn không phải đoán.
    assert nhin["execution_revision"] == 0
    assert nhin["routing_revision"] == 1
    assert nhin["lan_dang_chay"] is None
    assert nhin["lan_da_dung"] is None
    assert nhin["cac_lan"] == []
    # Lý do lấy từ máy chủ, không chép sang màn — thêm lý do mới không phải
    # sửa frontend.
    assert "PATIENT_DECLINED_AT_ROOM" in nhin["ly_do_khong_lam"]
    assert "EQUIPMENT_FAILURE" in nhin["ly_do_gian_doan"]


async def test_xem_chi_dung_lan_dang_chay_va_lan_da_dung(kb: KB) -> None:
    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
    )
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert nhin["lan_dang_chay"] is not None
    assert nhin["lan_dang_chay"]["id"] == mo["attempt_id"]
    assert nhin["lan_da_dung"] is None

    await kb.svc.gian_doan(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=nhin["execution_revision"],
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=kb.bs,
    )
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert nhin["lan_dang_chay"] is None
    # Nút "Làm lại" phải trỏ đúng lần vừa dừng, không phải lần nào khác.
    assert nhin["lan_da_dung"] is not None
    assert nhin["lan_da_dung"]["id"] == mo["attempt_id"]
    assert nhin["lan_da_dung"]["interruption_reason_code"] == "EQUIPMENT_FAILURE"
    assert len(nhin["cac_lan"]) == 1


async def test_xem_lan_lam_thu_hai_khong_de_lan_cu_thanh_lan_da_dung(kb: KB) -> None:
    """Dừng rồi làm lại: `lan_da_dung` phải hết, không thì nút Làm lại còn mãi."""
    mot = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
    )
    await kb.svc.gian_doan(
        order_id=kb.order_id,
        attempt_id=mot["attempt_id"],
        expected_execution_revision=mot["execution_revision"],
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=kb.bs,
    )
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    await kb.svc.chuan_bi_lam_lai(
        order_id=kb.order_id,
        interrupted_attempt_id=mot["attempt_id"],
        expected_execution_revision=nhin["execution_revision"],
        ghi_chu=None,
        identity=kb.bs,
    )
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    hai = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=nhin["execution_revision"],
        expected_routing_revision=1,
        identity=kb.bs,
    )

    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    assert nhin["lan_dang_chay"] is not None
    assert nhin["lan_dang_chay"]["id"] == hai["attempt_id"]
    assert nhin["lan_da_dung"] is None
    assert [lan["attempt_no"] for lan in nhin["cac_lan"]] == [1, 2]


async def test_xem_chi_dinh_khong_co_thi_bao_ro(kb: KB) -> None:
    with pytest.raises(ValidationError):
        await kb.svc.xem(order_id=str(uuid.uuid4()), identity=kb.bs)


# ── Bắt đầu phải làm nốt việc mà [Gọi vào] từng làm (23/09/2026) ────────────
# Nút [Gọi vào] đã bỏ. Nó từng dời con trỏ "khách đang ở đâu"; nếu Bắt đầu
# không làm thay thì con trỏ đứng im — đúng sự cố 17/09/2026: khám xong cả vòng
# mà trưởng ca vẫn thấy khách "đang ở Đo chỉ số", và quầy không đóng được lượt.


async def test_bat_dau_doi_con_tro_khach_dang_o_dau(kb: KB) -> None:
    truoc = await kb.pool.fetchrow(
        "SELECT current_room_id::text AS phong, current_node_code AS nut"
        "  FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    assert truoc is not None
    assert truoc["phong"] != kb.room_id, "chưa bắt đầu mà con trỏ đã ở phòng này"

    await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
    )

    sau = await kb.pool.fetchrow(
        "SELECT current_room_id::text AS phong, current_node_code AS nut"
        "  FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    assert sau is not None
    assert sau["phong"] == kb.room_id, (
        "Bắt đầu không dời con trỏ sang phòng đang làm — bảng điều phối, TV"
        " phòng chờ và bước đóng lượt đều đọc con trỏ này"
    )


async def test_khong_bat_dau_duoc_thi_con_tro_khong_nhuc_nhich(kb: KB) -> None:
    """Cùng một giao dịch: hoặc cả hai xảy ra, hoặc không gì cả."""
    truoc = await kb.pool.fetchval(
        "SELECT current_room_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    # Số revision sai → lệnh bị từ chối.
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.bat_dau(
            order_id=kb.order_id,
            expected_execution_revision=99,
            expected_routing_revision=1,
            identity=kb.bs,
        )
    sau = await kb.pool.fetchval(
        "SELECT current_room_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    assert sau == truoc, "lệnh hỏng mà con trỏ vẫn dời — giao dịch không trọn"


async def test_bac_si_chinh_thay_gio_bat_dau_va_xong_cua_phong(kb: KB) -> None:
    """Luồng chuẩn bước 8 (23/09/2026): bác sĩ chính thấy dịch vụ đang làm ở
    phòng nào, bắt đầu/xong lúc nào — nối thẳng tới giờ phòng đã bấm."""
    from clinicai.services.luot_kham_service import LuotKhamService

    async def chi_dinh() -> dict[str, Any]:
        bang = await LuotKhamService(kb.pool).bang(identity=kb.bs)
        [luot] = [x for x in bang["luot"] if x["visit_id"] == kb.visit_id]
        [cd] = [c for c in luot["chi_dinh"] if c["id"] == kb.order_id]
        return dict(cd)

    truoc = await chi_dinh()
    assert truoc["lam_bat_dau_luc"] is None and truoc["lam_trang_thai"] is None

    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    dang = await chi_dinh()
    ten_phong = await kb.pool.fetchval(
        "SELECT name FROM clinic_room WHERE id = $1::uuid", kb.room_id
    )
    assert dang["lam_trang_thai"] == "IN_PROGRESS"
    assert dang["lam_bat_dau_luc"] is not None and dang["lam_xong_luc"] is None
    assert dang["lam_phong"] == ten_phong

    await kb.svc.xong(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    xong = await chi_dinh()
    assert xong["lam_trang_thai"] == "COMPLETED"
    assert xong["lam_xong_luc"] is not None


async def test_le_tan_doi_phong_vang_hon_sau_khi_khach_tra_tien(kb: KB) -> None:
    """Luồng chuẩn bước 7 (23/09/2026): phòng đầy thì lễ tân đổi sang phòng vắng
    hơn cùng chức năng — lễ tân, điều dưỡng, thư ký, bác sĩ đều làm được, không
    riêng trưởng ca. Cửa là QUYỀN điều phối, không phải vai."""
    import inspect

    from clinicai.api.identity import get_current_identity
    from clinicai.api.v1.routers.luot_kham import assign_service_room
    from clinicai.services.clinic_config_service import ClinicConfigService
    from clinicai.services.service_routing_service import ServiceRoutingService
    from clinicai.services.xem_luot_service import XemLuotService

    # Router không còn gác vai (trước chỉ Trưởng ca / Quản lý qua được).
    cua = inspect.signature(assign_service_room).parameters["identity"].default
    assert cua.dependency is get_current_identity

    # Lượt dựng tay trong fixture: ghi đường đi như check-in thật đã làm (F2).
    await kb.pool.execute(
        "INSERT INTO encounter_flow (clinic_id, visit_id, route_decision,"
        " route_decided_at) VALUES ($1::uuid, $2::uuid, 'PRIMARY', now())"
        " ON CONFLICT (visit_id) DO UPDATE SET route_decision = 'PRIMARY',"
        " route_decided_at = now()",
        CLINIC,
        kb.visit_id,
    )
    ql = await _nguoi_quan_ly(kb)
    moi = await ClinicConfigService(kb.pool).create_room(
        identity=ql,
        location_id=kb.le_tan.location_id,
        name="Siêu âm vắng",
        node_code="DICHVU-SIEUAM",
        floor="2",
    )
    luot = await XemLuotService(kb.pool).doc(identity=kb.le_tan, visit_id=kb.visit_id)
    [dv] = [d for d in luot["dich_vu"] if d["id"] == kb.order_id]
    assert dv["doi_phong_duoc"] is True and dv["phong_id"] == kb.room_id

    kq = await ServiceRoutingService(kb.pool).assign(
        order_id=kb.order_id,
        room_id=str(moi["room_id"]),
        expected_routing_revision=dv["routing_revision"],
        reason_code="LOAD_BALANCE",
        identity=kb.le_tan,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["room_id"] == str(moi["room_id"])
    phong = await kb.pool.fetchval(
        "SELECT room_id::text FROM service_order WHERE id = $1::uuid", kb.order_id
    )
    assert phong == str(moi["room_id"])


async def _nguoi_quan_ly(kb: KB) -> StaffIdentity:
    async with kb.pool.acquire() as conn:
        return await _nguoi(conn, "MANAGEMENT")


# ── Quyền theo lịch (Tuyền duyệt 27/09/2026): dây `quyen_theo_lich` ─────────


async def _dat_day_lich(kb: KB, bat: bool) -> None:
    from clinicai.services.day_noi_service import DayNoiService

    ql = await _nguoi_quan_ly(kb)
    await DayNoiService(kb.pool).dat_day(identity=ql, ma="quyen_theo_lich", gia_tri=bat)


async def _xep_ca(kb: KB, nguoi: StaffIdentity, room_id: str) -> None:
    """Một vị trí thuộc `room_id` + ca ĐÃ DUYỆT hôm nay (giờ VN) cho `nguoi`."""
    # Mã `T-…`: quy ước vị trí do bài kiểm tạo (test_vi_tri_tu_database_db bỏ qua).
    ma = f"T-LICH-{uuid.uuid4().hex[:8]}"
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id)"
            " VALUES ($1::uuid, $2, 'Vị trí test', 'BAC_SI', $3::uuid)",
            CLINIC,
            ma,
            room_id,
        )
        await conn.execute(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
            " staff_id, staff_name, status)"
            " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, 'FULL', $2,"
            " $3::uuid, 'Test', 'APPROVED'"
            " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
            CLINIC,
            ma,
            nguoi.staff_id,
        )


async def _bat_dau(kb: KB, ai: StaffIdentity) -> dict[str, Any]:
    return await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=ai,
        idempotency_key=str(uuid.uuid4()),
    )


async def test_quyen_theo_lich_bat_ma_khong_co_ca_thi_chan_va_noi_ro(kb: KB) -> None:
    from clinicai.permissions.lich import CAU_CHAN

    # Mở full lego (30/09): ai cũng có Điều phối (được miễn) — bác sĩ ở đây
    # mang gói lego cũ để còn thấy cơ chế chặn khi quản lý bật lại dây.
    await ve_goi_mau_cu(kb.pool, kb.bs)
    await _dat_day_lich(kb, True)
    try:
        with pytest.raises(SafetyGateError) as loi:
            await _bat_dau(kb, kb.bs)
        assert CAU_CHAN in str(loi.value)
        assert (await _don(kb))["execution_status"] == "PENDING"
    finally:
        await _dat_day_lich(kb, False)


async def test_quyen_theo_lich_co_ca_dung_phong_thi_lam_duoc(kb: KB) -> None:
    await _xep_ca(kb, kb.bs, kb.room_id)
    await _dat_day_lich(kb, True)
    try:
        kq = await _bat_dau(kb, kb.bs)
        assert kq["attempt_no"] == 1
    finally:
        await _dat_day_lich(kb, False)


async def test_quyen_theo_lich_co_ca_phong_khac_van_chan(kb: KB) -> None:
    khac = await kb.pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid AND id <> $2::uuid"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
        kb.room_id,
    )
    await _xep_ca(kb, kb.bs, khac)
    await ve_goi_mau_cu(kb.pool, kb.bs)  # gói lego cũ (mở full lego 30/09)
    await _dat_day_lich(kb, True)
    try:
        with pytest.raises(SafetyGateError):
            await _bat_dau(kb, kb.bs)
    finally:
        await _dat_day_lich(kb, False)


async def test_quyen_theo_lich_nguoi_dieu_phoi_duoc_mien(kb: KB) -> None:
    ql = await _nguoi_quan_ly(kb)
    await _dat_day_lich(kb, True)
    try:
        kq = await _bat_dau(kb, ql)
        assert kq["attempt_no"] == 1
    finally:
        await _dat_day_lich(kb, False)


async def test_quyen_theo_lich_tat_thi_nhu_cu(kb: KB) -> None:
    await _dat_day_lich(kb, False)
    kq = await _bat_dau(kb, kb.bs)
    assert kq["attempt_no"] == 1


async def test_chi_co_quyen_theo_phong_van_lam_duoc(kb: KB) -> None:
    """Xếp lịch vào phòng = quyền làm dịch vụ ở ĐÚNG phòng ấy (28/09/2026).

    Lỗi thật trên prod: thư ký xếp ở Phòng thủ thuật 2 bấm "Bắt đầu" bị báo
    "chưa được cấp quyền" — lệnh hỏi quyền toàn phòng khám, không hỏi theo phòng.
    """
    async with kb.pool.acquire() as conn:
        tk = await _nguoi(conn, "RECEPTION")
        await ve_goi_mau_cu(conn, tk)  # gói lego cũ (mở full lego 30/09)
        for q in ("service.execute.start", "service.execute.complete"):
            await conn.execute(
                "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                " scope_type, scope_id, granted_by, ly_do)"
                " VALUES ($1::uuid, $2::uuid, $3, 'ROOM', $4::uuid, $2::uuid,"
                " 'test theo phòng')",
                CLINIC,
                tk.staff_id,
                q,
                kb.room_id,
            )
        khac = await conn.fetchval(
            "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid"
            " AND id <> $2::uuid ORDER BY created_at, id LIMIT 1",
            CLINIC,
            kb.room_id,
        )
    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=tk,
        idempotency_key=str(uuid.uuid4()),
    )
    assert mo["execution_status"] == "IN_PROGRESS"
    # Quyền ở phòng KHÁC thì không làm được chỉ định của phòng này.
    if khac is not None:
        async with kb.pool.acquire() as conn:
            await conn.execute(
                "UPDATE capability_grant SET scope_id = $3::uuid"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
                " AND scope_type = 'ROOM'",
                CLINIC,
                tk.staff_id,
                khac,
            )
        with pytest.raises(SafetyGateError):
            await kb.svc.xong(
                order_id=kb.order_id,
                attempt_id=mo["attempt_id"],
                expected_execution_revision=mo["execution_revision"],
                identity=tk,
                idempotency_key=str(uuid.uuid4()),
            )
