"""SINH HIỆU THEO BUỔI + dây H1 "cùng buổi thẳng dịch vụ" (27/09/2026, đợt 3).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_sinh_hieu_cung_buoi_db.py

Góp ý phòng khám: *"BN sau khi đăng kí thêm dịch vụ lần 2 trong buổi khám bị
auto chuyển sang Đo sinh hiệu → không cần đo sinh hiệu, có thể chuyển sang
phòng chuyên môn luôn"*. Chị Lan khám buổi sáng (đã đo, bác sĩ chỉ định, trả
tiền), ra về rồi quay lại quầy "đăng ký thêm" → lễ tân check-in LƯỢT MỚI cùng
ngày. Lượt mới dùng số đo của buổi (không chép số), không nằm "Chờ đo", và có
việc sẵn thì đi thẳng phòng.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import now_vn
from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.booking_service import BookingService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.sinh_hieu_buoi import (
    sinh_hieu_cua_buoi,
    sinh_hieu_cua_buoi_nhieu,
)
from clinicai.services.xem_luot_service import XemLuotService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _chon,
    _don,
    _dong_luot,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _thu,
    _thu_khoi_dieu_phoi,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclasses.dataclass
class Luot:
    appt: str
    visit: str


async def _loai_pk(pool: asyncpg.Pool) -> str:  # noqa: F811
    """Loại khám kiểu Phụ khoa: QUA TƯ VẤN (5 khoa lõi)."""
    duoi = uuid.uuid4().hex[:8]
    return str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, qua_tu_van)"
            " VALUES ($1::uuid, $2, $3, true, true) RETURNING id::text",
            CLINIC,
            f"PKB-{duoi}",
            f"Phụ khoa buổi {duoi}",
        )
    )


async def _check_in(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
    loai: str,
    *,
    chay: bool = True,
) -> Luot:
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
    if chay:
        await chay_hanh_trinh(pool)
    visit = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    return Luot(str(appt), str(visit))


async def _do(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    **so: Any,
) -> None:
    svc = LuotKhamService(pool)
    flow = await pool.fetchval(
        "SELECT vitals_status FROM encounter_flow WHERE visit_id = $1::uuid", visit
    )
    if flow == "pending":
        await svc.bat_dau_do_sinh_hieu(visit_id=visit, identity=ca.dd)
    await svc.record_vitals(
        visit_id=visit,
        raw={"systolic": 118, "diastolic": 76, **so},
        identity=ca.dd,
    )
    await chay_hanh_trinh(pool)


async def _flow(pool: asyncpg.Pool, visit: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT f.vitals_status, f.route_decision, f.route_reason,"
        " f.vitals_tu_visit_id::text AS tu, v.current_node_code AS node"
        " FROM encounter_flow f JOIN visit v ON v.visit_id = f.visit_id"
        " WHERE f.visit_id = $1::uuid",
        visit,
    )


async def _hang(pool: asyncpg.Pool, visit: str) -> dict[str, str]:  # noqa: F811
    rows = await pool.fetch(
        "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid"
        " AND status NOT IN ('left', 'cancelled')",
        visit,
    )
    return {r["lane"]: r["status"] for r in rows}


async def _tren_bang(pool: asyncpg.Pool, ca: Ca, visit: str) -> dict[str, Any]:  # noqa: F811
    """Dòng của lượt trên màn Đo sinh hiệu (điều dưỡng xem)."""
    bang = await LuotKhamService(pool).bang(identity=ca.dd)
    [dong] = [x for x in bang["luot"] if x["visit_id"] == visit]
    return dict(dong)


async def _phieu(pool: asyncpg.Pool, visit: str) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        return await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)


async def _luot_1_kham_tra_tien_roi_ve(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
) -> tuple[Luot, str]:
    """Lượt 1: đo · bác sĩ chính khám · chỉ định · trả tiền (người thu không có
    Điều phối nên chưa xếp phòng) · khách về chưa làm."""
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    _con, order = await _kham_va_chi_dinh(pool, ca, l1.visit)
    await _chon(pool, ca, l1.visit, [order])
    await _thu_khoi_dieu_phoi(pool, ca.thu_ngan)
    await _thu(pool, l1.visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    await _dong_luot(pool, l1.visit)
    return l1, order


# ── Chỉ định thêm TRONG CÙNG LƯỢT: không đụng sinh hiệu (đã đúng từ trước) ──


async def test_chi_dinh_them_cung_luot_thu_xong_co_phong_giu_sinh_hieu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    con, order = await _kham_va_chi_dinh(pool, ca, l1.visit)
    await _chon(pool, ca, l1.visit, [order])
    await _thu(pool, l1.visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"

    # Bác sĩ chỉ định THÊM trong cùng phiên → quầy thu lần 2 → tự xếp phòng.
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    them = str(kq["order_ids"][0])
    await _chon(pool, ca, l1.visit, [them])
    await _thu(pool, l1.visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, them)
    assert d["routing_status"] == "ASSIGNED" and d["visit_id"] == l1.visit
    f = await _flow(pool, l1.visit)
    assert f["vitals_status"] == "recorded" and f["tu"] is None
    assert "TU_VAN" not in await _hang(pool, l1.visit)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM visit WHERE clinic_patient_id = $1::uuid", pid
        )
        == 1
    )


# ── Lượt 2 cùng ngày: PK có chỉ định mang sang đã trả → thẳng dịch vụ ──────


async def test_luot_2_cung_ngay_pk_mang_sang_da_tra_thang_dich_vu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1, order = await _luot_1_kham_tra_tien_roi_ve(pool, ca, pid)

    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l2.visit)
    assert f["route_decision"] == "SERVICES"
    assert "cùng buổi" in f["route_reason"]
    # Không đo lại: lượt 2 nhận số của lượt 1 (truy vết), KHÔNG chép số.
    assert f["vitals_status"] == "recorded" and f["tu"] == l1.visit
    assert not await pool.fetchval(
        "SELECT count(*) FROM vital_measurement WHERE visit_id = $1::uuid", l2.visit
    )
    # Không vào tư vấn / bác sĩ; chỉ định đã trả xếp phòng ngay.
    hang = await _hang(pool, l2.visit)
    assert "TU_VAN" not in hang and "DOCTOR" not in hang
    d = await _don(pool, order)
    assert d["visit_id"] == l2.visit and d["routing_status"] == "ASSIGNED"
    # Con trỏ rời quầy Đo chỉ số.
    assert f["node"] != "LUOTKHAM-03"

    # Màn Đo sinh hiệu: không "Chờ đo" — đã đo (lượt trước).
    dong = await _tren_bang(pool, ca, l2.visit)
    assert dong["sinh_hieu_trang_thai"] == "recorded"
    assert dong["sinh_hieu"]["tam_thu"] == 118
    assert dong["sinh_hieu"]["nguon"] == "lượt trước"

    # Phiếu lượt 2 có số đo lượt 1, kèm nhãn nguồn.
    p = await _phieu(pool, l2.visit)
    assert p["sinh_hieu"]["vitals.blood_pressure"] == "118/76"
    assert p["sinh_hieu_nguon"] == "lượt trước"
    assert p["sinh_hieu_luc"] is not None

    # Xem lượt: "Đã đo (lượt trước)".
    xem = await XemLuotService(pool).doc(visit_id=l2.visit, identity=ca.le_tan)
    assert xem["hanh_chinh"]["da_do_sinh_hieu"] is True
    assert xem["hanh_chinh"]["sinh_hieu_nguon"] == "lượt trước"


async def test_luot_2_san_chau_khong_mang_sang_vao_bac_si_khong_cho_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    await _dong_luot(pool, l1.visit)

    l2 = await _check_in(pool, ca, pid, ca.loai_thu_thuat)
    f = await _flow(pool, l2.visit)
    assert f["route_decision"] == "PRIMARY"
    assert await _hang(pool, l2.visit) == {"DOCTOR": "waiting"}  # không blocked
    assert f["vitals_status"] == "recorded" and f["tu"] == l1.visit
    assert f["node"] != "LUOTKHAM-03"
    assert (await _tren_bang(pool, ca, l2.visit))["sinh_hieu"] is not None


async def test_luot_2_pk_khong_mang_sang_cho_tu_van_khong_cho_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    await _dong_luot(pool, l1.visit)

    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l2.visit)
    assert f["route_decision"] == "TU_VAN"
    assert await _hang(pool, l2.visit) == {"TU_VAN": "waiting"}  # không "chờ đo"
    assert f["node"] != "LUOTKHAM-03"


async def test_luot_dau_do_xong_con_tro_roi_quay_do_chi_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Luồng thường (lượt đầu trong ngày): check-in → con trỏ ở Đo chỉ số; đo
    xong, chỗ chờ tư vấn mở → con trỏ rời quầy (trước 27/09 kẹt tới khi tư vấn
    nhận khách)."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    assert (await _flow(pool, l1.visit))["node"] == "LUOTKHAM-03"
    await _do(pool, ca, l1.visit)
    assert await _hang(pool, l1.visit) == {"TU_VAN": "waiting"}
    assert (await _flow(pool, l1.visit))["node"] != "LUOTKHAM-03"


# ── Ca đặc biệt ──────────────────────────────────────────────────────────────


async def test_luot_1_chua_do_thi_luot_2_van_cho_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _dong_luot(pool, l1.visit)

    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "pending" and f["tu"] is None
    assert await _hang(pool, l2.visit) == {"TU_VAN": "blocked"}
    assert (await _tren_bang(pool, ca, l2.visit))["sinh_hieu"] is None  # Chờ đo
    assert f["node"] == "LUOTKHAM-03"  # vẫn ở quầy đo — đúng, chưa đo


async def _luot_1_do_luc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    pid: str,
    luc: datetime,
) -> Luot:
    """Lượt 1 check-in + một lần đo ghi ĐÚNG lúc `luc` (bảng số đo chỉ thêm,
    không sửa được giờ — nên ghi thẳng dòng có giờ), check-in trước đó 30s."""
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await pool.execute(
        "INSERT INTO vital_measurement (clinic_id, visit_id, systolic, diastolic,"
        " recorded_by, created_at) VALUES ($1::uuid, $2::uuid, 118, 76,"
        " $3::uuid, $4)",
        CLINIC,
        l1.visit,
        ca.dd.staff_id,
        luc,
    )
    await pool.execute(
        "UPDATE visit SET checked_in_at = $2 WHERE visit_id = $1::uuid",
        l1.visit,
        luc - timedelta(seconds=30),
    )
    await _dong_luot(pool, l1.visit)
    return l1


async def test_luot_1_hom_qua_2359_thi_hom_nay_phai_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    nua_dem = now_vn().replace(hour=0, minute=0, second=0, microsecond=0)
    await _luot_1_do_luc(pool, ca, pid, nua_dem - timedelta(minutes=1))

    l2 = await _check_in(pool, ca, pid, ca.loai_kham)
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "pending" and f["tu"] is None
    async with pool.acquire() as conn:
        assert await sinh_hieu_cua_buoi(conn, CLINIC, l2.visit) is None


async def test_luot_1_hom_nay_0001_thi_cung_buoi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    nua_dem = now_vn().replace(hour=0, minute=0, second=0, microsecond=0)
    if now_vn() - nua_dem < timedelta(minutes=3):
        pytest.skip("chạy sát nửa đêm giờ VN — mốc 00:01 chưa qua")
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _luot_1_do_luc(pool, ca, pid, nua_dem + timedelta(minutes=1))

    l2 = await _check_in(pool, ca, pid, ca.loai_kham)
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "recorded" and f["tu"] == l1.visit


async def test_luot_1_hoan_tac_check_in_so_do_van_la_that(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Hoàn tác check-in không làm lần đo thành không có (booking_service:
    "the patient really did have their vitals taken")."""
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    await BookingService(pool).apply_action(
        appointment_id=l1.appt, action="undo_checkin", identity=ca.le_tan
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM visit WHERE visit_id = $1::uuid", l1.visit
        )
        == "INCOMPLETE"
    )

    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "recorded" and f["tu"] == l1.visit
    assert await _hang(pool, l2.visit) == {"TU_VAN": "waiting"}


async def test_dd_do_lai_luot_2_moi_nhat_thang_luot_1_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    await _dong_luot(pool, l1.visit)
    l2 = await _check_in(pool, ca, pid, ca.loai_thu_thuat)

    # Đo lại ở lượt 2 — không cần [Bắt đầu] vì lượt đã "recorded".
    await _do(pool, ca, l2.visit, systolic=132, diastolic=84)
    dong = await _tren_bang(pool, ca, l2.visit)
    assert dong["sinh_hieu"]["tam_thu"] == 132
    assert dong["sinh_hieu"]["nguon"] is None
    assert (await _phieu(pool, l2.visit))["sinh_hieu"]["vitals.blood_pressure"] == (
        "132/84"
    )
    # Lượt SAU không chảy ngược vào phiếu lượt 1.
    p1 = await _phieu(pool, l1.visit)
    assert p1["sinh_hieu"]["vitals.blood_pressure"] == "118/76"
    assert p1["sinh_hieu_nguon"] is None


async def test_khach_co_thai_luot_1_thieu_can_cao_luot_2_van_cho_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)  # chưa ghi thai kỳ: đo thiếu cân/cao vẫn lưu
    await _dong_luot(pool, l1.visit)
    await pool.execute(
        "INSERT INTO pregnancy (clinic_id, clinic_patient_id, location_id, outcome)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'ONGOING')",
        CLINIC,
        pid,
        ca.loc,
    )

    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l2.visit)
    assert f["vitals_status"] == "pending" and f["tu"] is None
    assert await _hang(pool, l2.visit) == {"TU_VAN": "blocked"}


async def test_chay_h1_hai_lan_va_phat_lai_khong_nhan_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    _l1, _order = await _luot_1_kham_tra_tien_roi_ve(pool, ca, pid)
    l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    truoc = await pool.fetch(
        "SELECT id, status FROM queue_entry WHERE visit_id = $1::uuid ORDER BY id",
        l2.visit,
    )
    async with pool.acquire() as conn, conn.transaction():
        again = await LuotKhamService(pool=None).xep_sau_check_in(  # type: ignore[arg-type]
            conn, clinic_id=CLINIC, visit_id=l2.visit
        )
    assert again is None
    await chay_hanh_trinh(pool)
    sau = await pool.fetch(
        "SELECT id, status FROM queue_entry WHERE visit_id = $1::uuid ORDER BY id",
        l2.visit,
    )
    assert [tuple(r) for r in sau] == [tuple(r) for r in truoc]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'visit.routed'"
            " AND aggregate_id = $1::uuid",
            l2.visit,
        )
        == 1
    )


async def test_khach_khac_cung_ngay_khong_dinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    khac = await _benh_nhan(pool, ca)
    lk = await _check_in(pool, ca, khac, ca.loai_kham)
    await _do(pool, ca, lk.visit)

    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, await _loai_pk(pool))
    f = await _flow(pool, l1.visit)
    assert f["vitals_status"] == "pending" and f["tu"] is None
    assert (await _tren_bang(pool, ca, l1.visit))["sinh_hieu"] is None


async def test_phong_kham_khac_khong_doc_duoc_sinh_hieu_buoi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit)
    khac = str(uuid.uuid4())
    async with pool.acquire() as conn:
        assert await sinh_hieu_cua_buoi(conn, CLINIC, l1.visit) is not None
        assert await sinh_hieu_cua_buoi(conn, khac, l1.visit) is None
        assert await sinh_hieu_cua_buoi_nhieu(conn, khac, [l1.visit]) == {}
        assert await sinh_hieu_cua_buoi_nhieu(conn, CLINIC, []) == {}


async def test_tat_day_cung_buoi_ve_hanh_vi_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, 'h1_cung_buoi_thang_dich_vu', 'false'::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = 'false'::jsonb",
        CLINIC,
    )
    try:
        ca = await _dung(pool)
        pid = await _benh_nhan(pool, ca)
        await _luot_1_kham_tra_tien_roi_ve(pool, ca, pid)
        l2 = await _check_in(pool, ca, pid, await _loai_pk(pool))
        f = await _flow(pool, l2.visit)
        assert f["route_decision"] == "TU_VAN"
        assert f["vitals_status"] == "pending" and f["tu"] is None
        # Như trước 27/09: chờ đo rồi mới tư vấn (chỉ định đã trả vẫn tự xếp
        # phòng — dây H2/H4 không đổi).
        assert (await _hang(pool, l2.visit))["TU_VAN"] == "blocked"
        assert (await _tren_bang(pool, ca, l2.visit))["sinh_hieu"] is None
    finally:
        await pool.execute(
            "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
            " AND ma = 'h1_cung_buoi_thang_dich_vu'",
            CLINIC,
        )
