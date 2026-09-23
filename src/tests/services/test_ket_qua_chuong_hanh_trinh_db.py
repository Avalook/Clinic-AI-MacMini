"""NHÓM 3 — kết quả, chuông, lịch sử đổi lịch, bảng hành trình chung.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_ket_qua_chuong_hanh_trinh_db.py

Tuyền chốt 23–24/09/2026: tệp kết quả về → chuông cho bác sĩ, thư ký, điều
dưỡng, CSKH (người nhận chỉnh được); bác sĩ MỞ kết quả là tự ghi "đã xem"; đổi
lịch lưu lịch sử; một bảng chung cho biết mỗi khách đang ở đâu / xong gì / còn
chờ gì.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.events.catalogue import CHUONG, DONG_THOI_GIAN_LUOT
from clinicai.services.bang_hanh_trinh_service import (
    BangHanhTrinhService,
    con_cho,
    dang_o,
)
from clinicai.services.booking_service import BookingService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xem_luot_service import XemLuotService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

PDF = b"%PDF-1.4\n%%EOF\n"


@pytest.fixture
def kho_tam(monkeypatch: Any, tmp_path: pathlib.Path) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setenv("MEDIA_MIN_FREE_BYTES", "0")
    monkeypatch.delenv("MEDIA_MARKER", raising=False)


async def _tep(pool: asyncpg.Pool) -> tuple[Any, str, str, str]:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    kq = await TepKetQuaService(pool).tai_len(
        identity=ca.dd,
        clinic_patient_id=pid,
        data=PDF,
        ten_hien_thi="kq.pdf",
        service_order_id=order,
    )
    return ca, visit, order, str(kq["id"])


async def _chuong(pool: asyncpg.Pool, tep_id: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT vai_nhan, nguoi_nhan_staff_id::text AS nguoi FROM thong_bao"
            " WHERE nguon_id = $1 ORDER BY vai_nhan NULLS LAST",
            f"result_file.uploaded:{tep_id}",
        )
    )


@pytest.fixture(autouse=True)
def khong_tran(monkeypatch: Any) -> None:
    """Database thử dùng chung có hàng trăm lượt "hôm nay" — bảng hành trình có
    trần 300 lượt; bài ở đây kiểm nội dung, không kiểm trần."""
    import clinicai.services.bang_hanh_trinh_service as bht

    monkeypatch.setattr(bht, "_TRAN_LUOT", 100_000)


@pytest.mark.usefixtures("kho_tam")
async def test_tep_ve_thi_chuong_bao_du_bon_ben_theo_day(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, _order, tep = await _tep(pool)
    # Chưa chạy khối Chuông: lệnh tải KHÔNG còn gọi thẳng thông báo.
    assert await _chuong(pool, tep) == []
    await chay_ben_nhan(pool, CHUONG, DONG_THOI_GIAN_LUOT)
    rows = await _chuong(pool, tep)
    assert {r["vai_nhan"] for r in rows if r["vai_nhan"]} == {
        "CSKH",
        "TKYK",
        "NURSE_ULTRASOUND",
    }
    assert [r["nguoi"] for r in rows if r["nguoi"]] == [ca.bac_si.staff_id]
    # Dòng thời gian của lượt có "tệp kết quả đã về".
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid"
            " AND event_type = 'result_file.uploaded'",
            visit,
        )
        == 1
    )


@pytest.mark.usefixtures("kho_tam")
async def test_quan_ly_tat_day_thi_khong_reo(pool: asyncpg.Pool) -> None:  # noqa: F811
    await pool.execute(
        "INSERT INTO day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh, bat)"
        " VALUES ($1::uuid, 'result_file.uploaded', '{CSKH}', false, true)"
        " ON CONFLICT (clinic_id, su_kien) DO UPDATE SET vai = EXCLUDED.vai,"
        " bac_si_chinh = EXCLUDED.bac_si_chinh",
        CLINIC,
    )
    try:
        _ca, _visit, _order, tep = await _tep(pool)
        await chay_ben_nhan(pool, CHUONG)
        rows = await _chuong(pool, tep)
        assert [r["vai_nhan"] for r in rows] == ["CSKH"]  # chỉ CSKH, không bác sĩ
    finally:
        await pool.execute(
            "UPDATE day_nhan_thong_bao SET vai = '{CSKH,TKYK,NURSE_ULTRASOUND}',"
            " bac_si_chinh = true WHERE clinic_id = $1::uuid"
            " AND su_kien = 'result_file.uploaded'",
            CLINIC,
        )


@pytest.mark.usefixtures("kho_tam")
async def test_bac_si_mo_tep_la_tu_ghi_da_xem_cskh_mo_thi_khong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, _order, tep = await _tep(pool)
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, ca.loc, "CSKH")
    svc = TepKetQuaService(pool)
    await svc.duong_dan_de_doc(identity=cskh, tep_id=tep)
    assert (
        await pool.fetchval(
            "SELECT da_xem_luc FROM tep_ket_qua WHERE id = $1::uuid", tep
        )
        is None
    )
    await svc.duong_dan_de_doc(identity=ca.bac_si, tep_id=tep)
    await svc.duong_dan_de_doc(identity=ca.bac_si, tep_id=tep)  # lần 2 không ghi
    r = await pool.fetchrow(
        "SELECT da_xem_luc, da_xem_boi_staff_id::text AS ai FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        tep,
    )
    assert r["da_xem_luc"] is not None and r["ai"] == ca.bac_si.staff_id
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'result_file.viewed'"
            " AND aggregate_id = $1::uuid",
            tep,
        )
        == 1
    )
    b = await BangHanhTrinhService(pool).hom_nay(identity=ca.le_tan)
    [luot] = [x for x in b["luot"] if x["visit_id"] == visit]
    assert not any("chưa bác sĩ nào xem" in c for c in luot["con_cho"])


async def test_doi_lich_luu_lich_su(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    # Trong giờ ca (08:00–13:00 giờ VN), hai ngày tới.
    ngay = (datetime.now(CLINIC_TZ) + timedelta(days=2)).date()
    bd = datetime(ngay.year, ngay.month, ngay.day, 9, 0, tzinfo=CLINIC_TZ)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED') RETURNING id::text",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        bd,
        bd + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    moi = bd + timedelta(hours=1)
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, ca.loc, "CSKH")
    await BookingService(pool).apply_action(
        appointment_id=appt,
        action="reschedule",
        identity=cskh,
        slot_start=moi,
        slot_end=moi + timedelta(minutes=15),
        cancellation_reason="Khách bận buổi sáng",
    )
    r = await pool.fetchrow(
        "SELECT tu_bat_dau, den_bat_dau, ly_do, doi_boi_staff_id::text AS ai"
        " FROM appointment_doi_lich WHERE appointment_id = $1::uuid",
        appt,
    )
    assert r["tu_bat_dau"] == bd and r["den_bat_dau"] == moi
    assert r["ai"] == cskh.staff_id
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'appointment.rescheduled' AND aggregate_id = $1::uuid",
            appt,
        )
        == 1
    )


async def test_check_out_phat_su_kien_va_bang_hanh_trinh_bao_da_ve(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    b = await BangHanhTrinhService(pool).hom_nay(identity=ca.le_tan)
    [luot] = [x for x in b["luot"] if x["visit_id"] == visit]
    assert luot["dang_o"].startswith("Chờ bác sĩ")
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, override_reason="khách về"
    )
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)
    b = await BangHanhTrinhService(pool).hom_nay(identity=ca.le_tan)
    [luot] = [x for x in b["luot"] if x["visit_id"] == visit]
    assert luot["dang_o"] == "Đã về" and luot["da_ve"]
    assert "Khách đã về (check-out)" in [x["nhan"] for x in luot["da_xong"]]
    xem = await XemLuotService(pool).doc(visit_id=visit, identity=ca.le_tan)
    assert "Khách đã về (check-out)" in [x["nhan"] for x in xem["dong_thoi_gian"]]


def test_dang_o_va_con_cho_la_ham_thuan() -> None:
    luot = {"status": "IN_PROGRESS", "closed_at": None}
    hang = [
        {"lane": "DOCTOR", "status": "blocked", "phong": None, "bac_si": "A"},
        {"lane": "ROOM", "status": "serving", "phong": "SA1", "bac_si": None},
    ]
    assert dang_o(luot, hang) == "Đang ở SA1"
    assert dang_o({"status": "INCOMPLETE", "closed_at": 1}, []) == "Bỏ về giữa chừng"
    viec = con_cho(
        [{"lane": "TU_VAN", "status": "waiting", "phong": None, "bac_si": None}],
        [
            {
                "ten": "Siêu âm",
                "selection_status": "SELECTED",
                "routing_status": "UNASSIGNED",
                "execution_status": "PENDING",
                "phong": None,
                "ngoai": False,
                "ket_qua_luc": None,
            },
            {
                "ten": "Xét nghiệm",
                "selection_status": "PENDING",
                "routing_status": "UNASSIGNED",
                "execution_status": None,
                "phong": None,
                "ngoai": True,
                "ket_qua_luc": None,
            },
        ],
        2,
    )
    assert viec == [
        "Chờ bác sĩ tư vấn",
        "Chờ trả tiền / xếp phòng: Siêu âm",
        "Chờ khách chọn làm: Xét nghiệm",
        "2 tệp kết quả chưa bác sĩ nào xem",
    ]
