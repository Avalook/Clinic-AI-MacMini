"""NHÓM 2 — dây H4 (thu tiền → tự xếp phòng) và H2 (mang chỉ định chưa làm sang
lượt mới). docs/BAN-DO-DAY-NOI-LEGO.md "Bản chốt 24/09".

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_thu_tien_xep_phong_mang_sang_db.py

Chị Lan khám, bác sĩ chỉ định siêu âm, chị xuống lễ tân trả tiền NGAY lúc phiên
bác sĩ còn mở (không đợi "khám xong"). Tiền nhận xong → khối Hành trình xếp chị
vào phòng siêu âm thay cho người vừa thu, bằng quyền của người ấy. Lần sau chị
đến làm thủ thuật đã hẹn: chỉ định cũ đi theo chị sang lượt mới.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.booking_service import BookingService
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
from clinicai.services.service_selection_service import (
    ServiceSelectionService,
    cho_khach_quyet,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

NODE = "DICHVU-SIEUAM"


def _khoa() -> str:
    return f"nhom2-{uuid.uuid4().hex}"


@dataclasses.dataclass
class Ca:
    loc: str
    le_tan: StaffIdentity
    thu_ngan: StaffIdentity
    bac_si: StaffIdentity
    dd: StaffIdentity
    loai_kham: str
    loai_thu_thuat: str
    ma_dv: str
    phong: str


async def _dung(pool: asyncpg.Pool) -> Ca:  # noqa: F811
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ten_kham = f"Khám nhóm hai {duoi}"
        loai_kham = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, $3, true) RETURNING id::text",
            CLINIC,
            f"KN2-{duoi}",
            ten_kham,
        )
        loai_tt = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active,"
            " di_thang_phong) VALUES ($1::uuid, $2, $3, true, true)"
            " RETURNING id::text",
            CLINIC,
            f"TT2-{duoi}",
            f"Thủ thuật hẹn {duoi}",
        )
        # Giá tiền khám (khớp theo TÊN loại khám — luật hoá đơn) + giá dịch vụ.
        await conn.execute(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price) VALUES ($1::uuid, $2, $3, 'dich_vu', 150000)",
            CLINIC,
            f"GK2-{duoi}",
            ten_kham,
        )
        ma_dv = f"SA2-{duoi}"
        await conn.execute(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, node_code) VALUES ($1::uuid, $2, $3, 'dich_vu', 300000,"
            " $4)",
            CLINIC,
            ma_dv,
            f"Siêu âm nhóm hai {duoi}",
            NODE,
        )
        phong = await _phong(conn, loc, duoi)
        return Ca(
            loc=loc,
            le_tan=await _nguoi(conn, loc, "RECEPTION"),
            thu_ngan=await _nguoi(conn, loc, "CASHIER"),
            bac_si=await _nguoi(conn, loc, "DOCTOR"),
            dd=await _nguoi(conn, loc, "NURSE_ULTRASOUND"),
            loai_kham=str(loai_kham),
            loai_thu_thuat=str(loai_tt),
            ma_dv=ma_dv,
            phong=phong,
        )


async def _phong(conn: asyncpg.Connection, loc: str, duoi: str) -> str:
    rid = str(
        await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
            " true, true, 999) RETURNING id::text",
            CLINIC,
            loc,
            f"N2-{uuid.uuid4().hex[:6]}-{duoi}",
            f"Phòng thử nhóm hai {duoi}",
            NODE,
        )
    )
    await conn.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, $3)",
        CLINIC,
        rid,
        NODE,
    )
    return rid


async def _benh_nhan(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'Chị Lan', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"LAN2-{uuid.uuid4().hex[:8]}",
            ca.loc,
        )
    )


async def _check_in(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
    loai: str,
) -> str:
    bd = datetime.now(UTC) + timedelta(minutes=30)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED') RETURNING id::text",
        CLINIC,
        pid,
        ca.loc,
        loai,
        bd,
        bd + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca.le_tan
    )
    await chay_hanh_trinh(pool)
    return str(
        await pool.fetchval(
            "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
        )
    )


async def _kham_va_chi_dinh(pool: asyncpg.Pool, ca: Ca, visit: str) -> tuple[str, str]:  # noqa: F811
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    return con, str(kq["order_ids"][0])


async def _chon(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    chon: list[str],
) -> None:
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    thay = [c["id"] for c in cho["chi_dinh"]]
    await ServiceSelectionService(pool).confirm(
        visit_id=visit,
        order_ids_seen=thay,
        selected_order_ids=chon,
        expected_selection_revision=int(cho["revision"]),
        identity=ca.le_tan,
        idempotency_key=_khoa(),
    )


async def _thu(pool: asyncpg.Pool, visit: str, ai: StaffIdentity) -> None:  # noqa: F811
    await PaymentService(pool).record_payment(
        visit_id=visit,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ai,
        idempotency_key=_khoa(),
    )


async def _don(pool: asyncpg.Pool, order: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT visit_id::text AS visit_id, routing_status, room_id::text AS room_id,"
        " routing_revision, execution_revision, assigned_by::text AS assigned_by,"
        " mang_tu_visit_id::text AS mang_tu, selection_status, exec_status"
        " FROM service_order WHERE id = $1::uuid",
        order,
    )


async def _su_kien(pool: asyncpg.Pool, ten: str, agg: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT payload, actor_staff_id::text AS ai, aggregate_version"
            " FROM domain_event WHERE event_type = $1 AND aggregate_id = $2::uuid"
            " ORDER BY seq",
            ten,
            agg,
        )
    )


async def _dong_luot(pool: asyncpg.Pool, visit: str) -> None:  # noqa: F811
    """Khách về (bỏ về giữa chừng) — mọi chỗ chờ kết thúc, lượt đóng."""
    await pool.execute(
        "UPDATE queue_entry SET status = 'left' WHERE visit_id = $1::uuid"
        " AND status IN ('blocked', 'waiting', 'called', 'serving')",
        visit,
    )
    await pool.execute(
        "UPDATE visit SET status = 'INCOMPLETE', closed_at = now(),"
        " incomplete_reason = 'Khách về, hẹn hôm khác làm'"
        " WHERE visit_id = $1::uuid",
        visit,
    )


# ── H4 ──────────────────────────────────────────────────────────────────────


async def test_h4_tra_tien_luc_bac_si_con_kham_roi_tu_xep_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])

    # Phiên bác sĩ còn mở — vẫn thu được tiền dịch vụ.
    await _thu(pool, visit, ca.le_tan)
    cycle = await pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
        " AND kind = 'dich_vu' AND status = 'PAID'",
        visit,
    )
    [thu] = await _su_kien(pool, "payment.service_collected", cycle)
    assert json.loads(thu["payload"])["order_ids"] == [order]
    assert thu["ai"] == ca.le_tan.staff_id
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"

    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED" and d["room_id"] is not None
    assert d["assigned_by"] == ca.le_tan.staff_id  # thay người vừa thu
    [xep] = await _su_kien(pool, "service.routed", order)
    assert json.loads(xep["payload"])["tu_dong"] is True
    assert xep["ai"] == ca.le_tan.staff_id
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid AND lane = 'ROOM'"
            " AND status IN ('blocked', 'waiting')",
            order,
        )
        == 1
    )

    # Phòng bắt đầu làm được: sổ sự kiện của chỉ định là MỘT dãy số (trước bản
    # vá, "đã chỉ định" số 1 và "bắt đầu làm" số 1 đụng nhau → Postgres chặn).
    await LuotKhamService(pool).kham_xong(consultation_id=con, identity=ca.bac_si)
    await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    so = [
        r["aggregate_version"]
        for r in await pool.fetch(
            "SELECT aggregate_version FROM domain_event WHERE aggregate_id = $1::uuid"
            " ORDER BY seq",
            order,
        )
    ]
    assert so == [1, 2, 3]  # placed · routed · started


async def test_nguoi_thu_khong_co_quyen_dieu_phoi_thi_de_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Thu ngân (preset CASHIER) không có khối Điều phối → Hành trình không xếp
    thay — để người có quyền xếp tay, không mượn quyền "hệ thống"."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
    assert await _su_kien(pool, "service.routed", order) == []


async def test_doi_phong_sau_khi_tu_xep_lan_sau_de_lan_truoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    khac = ca.phong if d["room_id"] != ca.phong else None
    if khac is None:
        async with pool.acquire() as conn:
            khac = await _phong(conn, ca.loc, uuid.uuid4().hex[:6])
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=khac,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="LOAD_BALANCE",
        identity=ca.le_tan,
        idempotency_key=_khoa(),
    )
    assert (await _don(pool, order))["room_id"] == khac
    xep = await _su_kien(pool, "service.routed", order)
    assert [json.loads(x["payload"])["tu_dong"] for x in xep] == [True, False]


async def test_tien_thuoc_van_cho_kham_xong(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    with pytest.raises(ConflictError, match="khám xong"):
        await PaymentService(pool).record_payment(
            visit_id=visit,
            kind="thuoc",
            amount=None,
            clinic_patient_id=None,
            identity=ca.le_tan,
        )


async def test_quay_thu_ngan_hien_khach_truoc_kham_xong_va_thu_nhieu_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    board = CashierBoardService(pool)

    b = await board.board(identity=ca.le_tan, modes=["dich_vu"])
    [luot] = [i for i in b["items"] if i["visit_id"] == visit]
    assert [c["id"] for c in luot["chon_dich_vu"]["chi_dinh"]] == [order]
    # Chưa chọn thì chỉ định chưa vào hoá đơn — chỉ có tiền khám.
    assert len(luot["hoa_don"]["dich_vu"]["dong"]) == 1

    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    b = await board.board(identity=ca.le_tan, modes=["dich_vu"])
    assert {"visit_id": visit, "kind": "dich_vu"} in b["paid"]

    # Bác sĩ chỉ định thêm SAU lần thu đầu → còn khoản mới, thu lần hai.
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    moi = str(kq["order_ids"][0])
    await _chon(pool, ca, visit, [moi])
    b = await board.board(identity=ca.le_tan, modes=["dich_vu"])
    [luot] = [i for i in b["items"] if i["visit_id"] == visit]
    assert {"visit_id": visit, "kind": "dich_vu"} not in b["paid"]
    assert [d["source_id"] for d in luot["hoa_don"]["dich_vu"]["dong"]] == [moi]
    await _thu(pool, visit, ca.le_tan)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid"
            " AND kind = 'dich_vu' AND status = 'PAID'",
            visit,
        )
        == 2
    )


# ── H2 ──────────────────────────────────────────────────────────────────────


async def test_h2_da_tra_chua_lam_mang_sang_luot_moi_khong_thu_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    cu = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, cu)
    await _chon(pool, ca, cu, [order])
    await _thu(pool, cu, ca.thu_ngan)  # thu ngân: không tự xếp
    await chay_hanh_trinh(pool)
    await _dong_luot(pool, cu)  # khách về, chưa làm siêu âm

    moi = await _check_in(pool, ca, pid, ca.loai_kham)
    d = await _don(pool, order)
    assert d["visit_id"] == moi and d["mang_tu"] == cu
    [mang] = await _su_kien(pool, "service_order.carried_over", order)
    assert json.loads(mang["payload"])["da_thu_tien"] is True
    # Đã trả → vào thẳng hàng phòng, thay người check-in (lễ tân).
    assert d["routing_status"] == "ASSIGNED"
    assert d["assigned_by"] == ca.le_tan.staff_id
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=moi)
    assert order not in [x.source_id for x in hd.dong]  # không thu lại


async def test_h2_lich_thu_thuat_mang_chi_dinh_chua_tra_di_thang_dich_vu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    cu = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, cu)
    await _dong_luot(pool, cu)  # hẹn hôm khác làm, chưa trả

    moi = await _check_in(pool, ca, pid, ca.loai_thu_thuat)
    assert (await _don(pool, order))["visit_id"] == moi
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", moi
        )
        == "SERVICES"
    )
    assert not await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
        " AND lane IN ('DOCTOR', 'TU_VAN')",
        moi,
    )
    # Không có tiền khám: khách không khám, chỉ làm thủ thuật.
    await _chon(pool, ca, moi, [order])
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=moi)
    assert [x.source_id for x in hd.dong] == [order]
    b = await CashierBoardService(pool).board(identity=ca.le_tan, modes=["dich_vu"])
    assert any(i["visit_id"] == moi for i in b["items"])

    await _thu(pool, moi, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"


async def test_h2_lich_thu_thuat_khong_co_gi_mang_sang_ve_bac_si_chinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    moi = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_thu_thuat)
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", moi
        )
        == "PRIMARY"
    )
    assert await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
        " AND lane = 'DOCTOR'",
        moi,
    )


async def test_kham_thuong_khong_mang_chi_dinh_chua_tra(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    cu = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, cu)
    await _dong_luot(pool, cu)
    await _check_in(pool, ca, pid, ca.loai_kham)
    assert (await _don(pool, order))["visit_id"] == cu


async def test_lich_thu_thuat_hoi_lai_ca_chi_dinh_hom_truoc_khach_khong_lam(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Ngoài đời "hẹn hôm khác làm" là một cú bỏ tick ở quầy (NOT_SELECTED).
    Hôm khách quay lại theo lịch thủ thuật, chỉ định ấy phải hiện lại để hỏi."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    cu = await _check_in(pool, ca, pid, ca.loai_kham)
    con, bo = await _kham_va_chi_dinh(pool, ca, cu)
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    chua_quyet = str(kq["order_ids"][0])
    await _chon(pool, ca, cu, [chua_quyet])  # bỏ tick "bo"
    await pool.execute(
        "UPDATE service_order SET selection_status = 'PENDING' WHERE id = $1::uuid",
        chua_quyet,
    )
    await _dong_luot(pool, cu)

    moi = await _check_in(pool, ca, pid, ca.loai_thu_thuat)
    for o in (bo, chua_quyet):
        d = await _don(pool, o)
        assert d["visit_id"] == moi and d["selection_status"] == "PENDING"

    # Chạy lại lệnh: không mang lần hai, không sự kiện thứ hai.
    async with pool.acquire() as conn, conn.transaction():
        again = await ChiDinhService.mang_sang_luot_moi(
            conn, clinic_id=CLINIC, visit_id=moi
        )
    assert again == []
    assert len(await _su_kien(pool, "service_order.carried_over", bo)) == 1


# ── Đợi quay lại ────────────────────────────────────────────────────────────


async def test_phong_lam_khi_phien_bac_si_con_mo_roi_khach_quay_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Luồng chuẩn bước 7–8: chỉ định đi chỗ khác = ĐỢI QUAY LẠI, không phải
    khám xong. Phòng Bắt đầu được khi phiên bác sĩ còn mở; làm xong khách về
    hàng bác sĩ; bác sĩ bấm Bắt đầu lần nữa là khám tiếp."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)

    async def hang_bac_si() -> str:
        return str(
            await pool.fetchval(
                "SELECT status FROM queue_entry WHERE visit_id = $1::uuid"
                " AND lane = 'DOCTOR' AND status NOT IN ('left', 'cancelled')",
                visit,
            )
        )

    assert await hang_bac_si() == "serving"
    d = await _don(pool, order)
    mo = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert await hang_bac_si() == "blocked"  # đợi quay lại
    assert (
        await pool.fetchval("SELECT status FROM consultation WHERE id = $1::uuid", con)
        == "in_progress"
    )

    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert await hang_bac_si() == "waiting"  # đã quay lại

    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    assert await hang_bac_si() == "serving"  # khám tiếp


async def test_phong_bam_bat_dau_xong_thi_cot_cu_exec_status_di_theo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bấm thật 23/09 22:00: phòng bấm Xong mà Bàn khám vẫn ghi "Chờ ở phòng",
    không hiện nút xem kết quả — Bàn khám, trưởng ca, xem lượt còn đọc
    `exec_status`. Đường làm mới phải kéo cột cũ theo."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["exec_status"] == "assigned"

    d = await _don(pool, order)
    mo = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert (await _don(pool, order))["exec_status"] == "in_progress"

    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    sau = await pool.fetchrow(
        "SELECT exec_status, performed_by::text AS ai FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    assert sau["exec_status"] == "performed"
    assert sau["ai"] == ca.dd.staff_id


async def test_bac_si_hoan_tat_truoc_roi_phong_xong_thi_vong_doc_mo_hoac_khep_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lỗi thật 24/09: đường làm MỚI (phòng [Xong]) không chạy lại vòng đọc /
    điều kiện khép lượt — chỉ lối gọi thẳng cũ mới chạy. Bác sĩ Hoàn tất khi
    khách còn đi làm dịch vụ, phòng xong sau → không ai khép lượt, quầy chờ mãi.
    Nay khối VÒNG ĐỌC nghe `service.completed`."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    d = await _don(pool, order)
    mo = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=ca.dd,
        idempotency_key=_khoa(),
    )

    async def vong() -> list[str]:
        return [
            str(r["status"])
            for r in await pool.fetch(
                "SELECT status FROM review_round WHERE visit_id = $1::uuid", visit
            )
        ]

    assert await vong() == ["collecting"]  # lệnh [Xong] không tự chạy vòng đọc
    await chay_ben_nhan(pool, "vong_doc_luot_kham")
    assert await vong() == ["ready"]
    # Bác sĩ chính có chỗ chờ "đọc kết quả" (REVIEW) trong hàng của mình.
    assert await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
        " AND reason = 'REVIEW' AND status IN ('waiting', 'blocked')",
        visit,
    )


async def test_luot_khep_han_phat_visit_exam_completed_dung_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Mốc "khám xong hẳn" là sự kiện: quầy / nhà thuốc / nhắc check-out cắm
    vào đây. Phát đúng một lần dù điều kiện khép được kiểm nhiều lần."""
    from tests.chay_nguoi_dua_tin import chay_ben_nhan

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )
    await LuotKhamService(pool).sau_khi_co_ket_qua(
        order_id=str(uuid.uuid4()), identity=ca.bac_si
    )
    await chay_ben_nhan(pool, "vong_doc_luot_kham")
    su_kien = await _su_kien(pool, "visit.exam_completed", visit)
    assert len(su_kien) == 1
    assert json.loads(su_kien[0]["payload"]) == {"visit_id": visit}


async def test_truong_ca_thay_chi_dinh_doi_moi_doi_phong_duoc_bang_khoi_chung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Trưởng ca (`/truong-ca`) đổi phòng chỉ định đời mới bằng khối chung
    `DoiPhong` (`xep-phong-v1`) — cần `selection_status`, `routing_revision`
    và `doi_phong_duoc` cùng luật với Bàn khám (24/09)."""
    from clinicai.services.dispatch_service import DispatchService

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    [dong] = [
        d
        for d in await DispatchService(pool).chi_dinh(clinic_id=CLINIC, visit_id=visit)
        if d["id"] == order
    ]
    assert dong["selection_status"] == "SELECTED"
    assert dong["doi_phong_duoc"] is True
    assert dong["routing_revision"] >= 1
