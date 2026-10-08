"""Đổi cơ sở là đổi HẾT các màn danh sách vận hành (Tuyền 08/10/2026: "sang cơ
sở khác là của cơ sở đó hết, đừng sót") — nhóm A: tiếp đón, trang chủ, lịch
tuần, tiến trình lượt, hành trình, điều phối, hàng gọi số, bảng bác sĩ, hàng chờ
xếp bác sĩ, lượt đang mở.

Dựng hai cơ sở, mỗi cơ sở một khách có lịch + lượt (check-in thật) và một lịch
chưa xếp bác sĩ, một vị trí lịch làm việc gắn phòng của cơ sở ấy. Gọi TỪNG hàm
danh sách với danh tính cơ sở 1 rồi cơ sở 2: chỉ thấy của mình, không lẫn. Danh
tính không chọn cơ sở (`location_id = ""`) thấy cả hai.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.booking import cho_xep_bac_si
from clinicai.api.v1.routers.queue import get_queue
from clinicai.api.v1.routers.visit_progress import active_visits
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
from clinicai.services.booking_service import BookingService
from clinicai.services.dispatch_service import DispatchService
from clinicai.services.doctor_board_service import DoctorBoardService
from clinicai.services.man_trang_chu_service import ManTrangChuService
from clinicai.services.tiep_don_service import TiepDonService
from clinicai.services.visit_progress_service import VisitProgressService
from clinicai.services.week_appointments_service import WeekAppointmentsService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_ngay_kham_lo_hong_db import _co_so_khac
from tests.services.test_thu_tien_xep_phong_mang_sang_db import NODE, Ca, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclasses.dataclass
class CoSo:
    loc: str
    ai: StaffIdentity  # lễ tân đứng ở cơ sở này
    pid: str
    appt: str  # lịch đã check-in
    visit: str
    chua_xep: str  # lịch tương lai chưa xếp bác sĩ
    vi_tri: str  # mã vị trí lịch làm việc gắn phòng của cơ sở


async def _phong_o(conn: asyncpg.Connection, loc: str) -> str:
    """Phòng ĐANG NHẬN ở cơ sở `loc` cho node thử (check-in có chỗ xếp)."""
    rid = str(
        await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
            " true, true, 999) RETURNING id::text",
            CLINIC,
            loc,
            f"LCS-{uuid.uuid4().hex[:8]}",
            "Phòng lọc cơ sở",
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


async def _mot_co_so(pool: asyncpg.Pool, ca: Ca, loc: str, ai: StaffIdentity) -> CoSo:  # noqa: F811
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        phong = await _phong_o(conn, loc)
        pid = str(
            await conn.fetchval(
                "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
                " VALUES ($1::uuid, $2, $3, $4::uuid)"
                " RETURNING clinic_patient_id::text",
                CLINIC,
                f"LCS-{duoi}",
                f"Khách cơ sở {duoi}",
                loc,
            )
        )
        bd = datetime.now(UTC)
        appt = str(
            await conn.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, doctor_id, status)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6,"
                " $7::uuid, 'CONFIRMED') RETURNING id::text",
                CLINIC,
                pid,
                loc,
                ca.loai_kham,
                bd,
                bd + timedelta(minutes=15),
                ca.bac_si.staff_id,
            )
        )
        sau = bd + timedelta(days=2)
        chua_xep = str(
            await conn.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, status)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6,"
                " 'CONFIRMED') RETURNING id::text",
                CLINIC,
                pid,
                loc,
                ca.loai_kham,
                sau,
                sau + timedelta(minutes=15),
            )
        )
        vi_tri = f"LCS-VT-{duoi}"
        await conn.execute(
            "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
            " VALUES ($1::uuid, $2, $3, $4::uuid)",
            CLINIC,
            vi_tri,
            f"Vị trí {duoi}",
            phong,
        )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ai
    )
    await chay_hanh_trinh(pool)
    visit = str(
        await pool.fetchval(
            "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
        )
    )
    return CoSo(loc, ai, pid, appt, visit, chua_xep, vi_tri)


async def _lich_lam_viec(pool: asyncpg.Pool, cs: CoSo, thu_hai: date) -> None:  # noqa: F811
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_name, status) VALUES ($1::uuid, $2::date, $3::date, 'FULL', $4,"
        " $5, 'APPROVED')",
        CLINIC,
        thu_hai,
        datetime.now(CLINIC_TZ).date(),
        cs.vi_tri,
        f"Người đứng {cs.vi_tri}",
    )


@pytest.fixture
async def hai_co_so(pool: asyncpg.Pool) -> tuple[CoSo, CoSo, date]:  # noqa: F811
    ca = await _dung(pool)
    loc2 = await _co_so_khac(pool, ca.loc)
    a = await _mot_co_so(pool, ca, ca.loc, ca.le_tan)
    b = await _mot_co_so(
        pool, ca, loc2, dataclasses.replace(ca.le_tan, location_id=loc2)
    )
    hom_nay = datetime.now(CLINIC_TZ).date()
    thu_hai = hom_nay - timedelta(days=hom_nay.weekday())
    for cs in (a, b):
        await _lich_lam_viec(pool, cs, thu_hai)
    return a, b, thu_hai


async def _thay(
    pool: asyncpg.Pool,  # noqa: F811
    ai: StaffIdentity,
    thu_hai: date,
) -> dict[str, set[str]]:
    """Mọi id mà từng màn danh sách trả về cho danh tính `ai`."""
    hom_nay = datetime.now(CLINIC_TZ).date()
    co_so = ai.location_id or None
    thay: dict[str, set[str]] = {}

    tiep = await TiepDonService(pool).hom_nay(identity=ai)
    thay["tiep_don"] = {
        str(d["appointment_id"]) for b in tiep["buoi"] for d in b["dong"]
    }

    tc = await ManTrangChuService(pool).goi_du_lieu(
        identity=ai, week_appt=thu_hai, week_roster=thu_hai
    )
    thay["trang_chu.tuan_hen"] = {str(r["id"]) for r in tc["tuan_hen"]}
    thay["trang_chu.tien_trinh"] = {
        str(p["visit_id"]) for p in tc["tien_trinh"] if p.get("visit_id")
    }
    thay["trang_chu.trang_thai_kham"] = {
        str(d["visit_id"]) for d in tc["trang_thai_kham"]
    }
    thay["trang_chu.roster"] = {str(r["station"]) for r in tc["roster"]}

    thay["tuan"] = {
        str(r["id"])
        for r in await WeekAppointmentsService(pool).week(
            clinic_id=CLINIC, week_start=thu_hai, location_id=co_so
        )
    }
    thay["tien_trinh"] = {
        str(p.visit_id)
        for p in await VisitProgressService(pool).for_range(
            date_from=hom_nay, date_to=hom_nay, clinic_id=CLINIC, location_id=co_so
        )
        if p.visit_id
    }
    hanh_trinh = await BangHanhTrinhService(pool).hom_nay(identity=ai)
    thay["hanh_trinh"] = {
        str(x["visit_id"]) for x in _cac_dong(hanh_trinh) if x.get("visit_id")
    }
    dp = DispatchService(pool)
    thay["dieu_phoi"] = {
        str(p["visit_id"])
        for p in await dp.overview(clinic_id=CLINIC, location_id=co_so)
    }
    # Hai hàm còn lại của điều phối: chạy được với tham số cơ sở (không lỗi SQL).
    await dp.alerts(clinic_id=CLINIC, location_id=co_so)
    await dp.history(clinic_id=CLINIC, location_id=co_so)

    hang = await get_queue(date=hom_nay, identity=ai, pool=pool)
    dong_goi = hang["rows"]
    assert isinstance(dong_goi, list)
    thay["goi_so"] = {str(r["id"]) for r in dong_goi}
    thay["bac_si"] = {
        str(r["id"])
        for r in await DoctorBoardService(pool).board(
            clinic_id=CLINIC,
            start=datetime.combine(hom_nay, datetime.min.time(), tzinfo=CLINIC_TZ),
            end=datetime.combine(
                hom_nay + timedelta(days=7), datetime.min.time(), tzinfo=CLINIC_TZ
            ),
            doctor_id=None,
            location_id=co_so,
        )
    }
    cho = await cho_xep_bac_si(identity=ai, pool=pool)
    thay["cho_xep_bac_si"] = {str(r["id"]) for r in cho["items"]}
    dang_mo = await active_visits(identity=ai, pool=pool)
    thay["luot_dang_mo"] = {str(v["visit_id"]) for v in dang_mo["visits"]}
    return thay


def _cac_dong(bang: dict[str, Any]) -> list[dict[str, Any]]:
    """Bảng hành trình trả dòng theo nhóm — gom phẳng, không phụ thuộc hình."""
    ra: list[dict[str, Any]] = []

    def di(x: Any) -> None:
        if isinstance(x, dict):
            if "visit_id" in x:
                ra.append(x)
            for v in x.values():
                di(v)
        elif isinstance(x, list):
            for v in x:
                di(v)

    di(bang)
    return ra


def _cua(cs: CoSo) -> dict[str, set[str]]:
    """Id của cơ sở `cs` mà từng màn PHẢI hiện."""
    return {
        "tiep_don": {cs.appt},
        "trang_chu.tuan_hen": {cs.appt},
        "trang_chu.tien_trinh": {cs.visit},
        "trang_chu.trang_thai_kham": {cs.visit},
        "trang_chu.roster": {cs.vi_tri},
        "tuan": {cs.appt},
        "tien_trinh": {cs.visit},
        "hanh_trinh": {cs.visit},
        "dieu_phoi": {cs.visit},
        "goi_so": {cs.appt},
        "bac_si": {cs.appt},
        "cho_xep_bac_si": {cs.chua_xep},
        "luot_dang_mo": {cs.visit},
    }


async def test_moi_man_chi_hien_cua_co_so_dang_dung(
    pool: asyncpg.Pool,  # noqa: F811
    hai_co_so: tuple[CoSo, CoSo, date],
) -> None:
    a, b, thu_hai = hai_co_so
    for minh, khac in ((a, b), (b, a)):
        thay = await _thay(pool, minh.ai, thu_hai)
        for man, can in _cua(minh).items():
            assert can <= thay[man], f"{man}: cơ sở {minh.loc} không thấy của mình"
        for man, la in _cua(khac).items():
            assert not (la & thay[man]), f"{man}: cơ sở {minh.loc} thấy của {khac.loc}"


async def test_khong_chon_co_so_thay_ca_hai(
    pool: asyncpg.Pool,  # noqa: F811
    hai_co_so: tuple[CoSo, CoSo, date],
) -> None:
    """Danh tính không chọn cơ sở (`location_id = ""` → None) KHÔNG lọc — mẫu
    `coalesce(LOC, $n) IS NOT DISTINCT FROM coalesce($n, LOC)`; mẫu cũ
    `coalesce(LOC, $n) = $n` gặp $n NULL thì loại sạch mọi dòng."""
    a, b, thu_hai = hai_co_so
    thay = await _thay(pool, dataclasses.replace(a.ai, location_id=""), thu_hai)
    for cs in (a, b):
        for man, can in _cua(cs).items():
            assert can <= thay[man], f"{man}: không chọn cơ sở mà thiếu {cs.loc}"


async def test_trang_chu_dem_theo_co_so(
    pool: asyncpg.Pool,  # noqa: F811
    hai_co_so: tuple[CoSo, CoSo, date],
) -> None:
    """Ô số trang chủ: tổng hai cơ sở ≤ không chọn cơ sở, và mỗi cơ sở ≥ 1 lịch
    chưa xếp bác sĩ (của chính nó)."""
    a, b, thu_hai = hai_co_so
    so: dict[str, dict[str, Any]] = {}
    for ten, ai in (
        ("a", a.ai),
        ("b", b.ai),
        ("tat_ca", dataclasses.replace(a.ai, location_id="")),
    ):
        tc = await ManTrangChuService(pool).goi_du_lieu(
            identity=ai, week_appt=thu_hai, week_roster=thu_hai
        )
        so[ten] = {c["ma"]: c["so"] for c in tc["can_xu_ly"]}
        so[ten]["khach_moi"] = tc["so_lieu"]["khach_moi_hom_nay"]
    for ma in ("chua_xep_bac_si", "khach_moi"):
        assert so["a"][ma] >= 1 and so["b"][ma] >= 1, ma
        assert so["a"][ma] + so["b"][ma] <= so["tat_ca"][ma], ma
