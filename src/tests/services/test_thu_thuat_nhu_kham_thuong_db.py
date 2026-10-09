"""Thủ thuật + Sàn chậu đi quy trình như 5 loại khám kia, và trạng thái khách
ĐỒNG BỘ mọi màn sau check-out (Tuyền chốt 30/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55579/postgres \\
        poetry run pytest src/tests/services/test_thu_thuat_nhu_kham_thuong_db.py

1. Migration 20261001230000 áp lên dữ liệu kiểu prod (sau 20260925000006 bật
   "đi thẳng phòng") → hai loại khám qua tư vấn, không đi thẳng; chạy lại được.
2. Lịch THỦ THUẬT / SÀN CHẬU check-in → hàng TƯ VẤN như khám thường.
3. Check-out → lịch COMPLETED trong cùng giao dịch; lưới lịch tuần, trang chủ
   (bảng trạng thái buổi khám), Quản lý khách hàng, Tiếp đón, Hành trình cùng
   nói "Đã về".
4. Backfill 20261001230100 chỉ sửa lịch lệch; chạy lần hai không đổi thêm.
5. QUYẾT ĐỊNH MỚI của Tuyền 09/10/2026 — migration 20261009500000: THỦ THUẬT
   (chỉ Thủ thuật, Sàn chậu giữ nguyên) đi thẳng, KHÔNG qua tư vấn: check-in
   không chỉ định mang sang → hàng BÁC SĨ (DOCTOR); không tự cộng phí khám,
   tick dịch vụ khám con thì có. Các bài 1–3 vẫn dựng lại trạng thái 30/09
   (`_nhu_prod`) để giữ lịch sử quyết định ấy.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services import bang_hanh_trinh_service, man_trang_chu_service
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.man_khach_hang_service import ManKhachHangService
from clinicai.services.man_trang_chu_service import ManTrangChuService
from clinicai.services.tiep_don_service import TiepDonService
from clinicai.services.week_appointments_service import WeekAppointmentsService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_MIG = Path(__file__).resolve().parents[3] / "supabase/migrations"
CU = _MIG / "20260925000006_dat_lich_thu_thuat_san_chau.sql"
MOI = _MIG / "20261001230000_thu_thuat_san_chau_nhu_kham_thuong.sql"
BACKFILL = _MIG / "20261001230100_lich_cua_luot_da_ve_dong_bo.sql"
DI_THANG_0910 = _MIG / "20261009500000_thu_thuat_di_thang_phong.sql"


async def _ap(pool: asyncpg.Pool, tep: Path) -> None:  # noqa: F811
    await pool.execute(tep.read_text(encoding="utf-8"))


async def _nhu_prod(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Đường prod: 20260925000006 (bật đi thẳng phòng) rồi bản mới."""
    await _ap(pool, CU)
    await _ap(pool, MOI)


async def _loai(pool: asyncpg.Pool, code: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT id::text, di_thang_phong, qua_tu_van, form_code"
        " FROM service_type WHERE clinic_id = $1::uuid AND code = $2",
        CLINIC,
        code,
    )
    assert r is not None
    return r


async def test_migration_dua_hai_loai_ve_nhu_kham_thuong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    await _nhu_prod(pool)
    await _ap(pool, MOI)  # chạy lại được
    for code in ("THU_THUAT", "SAN_CHAU"):
        r = await _loai(pool, code)
        assert (r["di_thang_phong"], r["qua_tu_van"]) == (False, True)
        assert r["form_code"] == code  # phiếu khám riêng vẫn giữ


@pytest.mark.parametrize("code", ["THU_THUAT", "SAN_CHAU"])
async def test_check_in_vao_hang_tu_van_nhu_kham_thuong(
    pool: asyncpg.Pool,  # noqa: F811
    code: str,
) -> None:
    await _nhu_prod(pool)
    ca = await _dung(pool)
    loai = await _loai(pool, code)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), loai["id"])
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", vid
        )
        == "TU_VAN"
    )
    hang = await pool.fetch(
        "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid", vid
    )
    # Chưa đo sinh hiệu → "chờ đo" (blocked) nhưng tư vấn vẫn nhận sớm được.
    assert [(q["lane"], q["status"]) for q in hang] == [("TU_VAN", "blocked")]


def _tim(obj: Any, khoa: str, gia_tri: str) -> dict[str, Any] | None:
    """Dòng đầu tiên (đi sâu vào list/dict) có ``obj[khoa] == gia_tri``."""
    if isinstance(obj, dict):
        if str(obj.get(khoa) or "") == gia_tri:
            return obj
        for v in obj.values():
            if (t := _tim(v, khoa, gia_tri)) is not None:
                return t
    elif isinstance(obj, list):
        for v in obj:
            if (t := _tim(v, khoa, gia_tri)) is not None:
                return t
    return None


async def _doc_moi_man(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    appt: str,
    vid: str,
) -> dict[str, str]:
    """Nhãn trạng thái của CÙNG một lịch ở mọi màn."""
    bd = await pool.fetchval(
        "SELECT slot_start FROM appointment WHERE id = $1::uuid", appt
    )
    ngay = bd.astimezone(CLINIC_TZ).date()
    tuan = await WeekAppointmentsService(pool).week(
        clinic_id=CLINIC, week_start=ngay - timedelta(days=1)
    )
    dong_tuan = _tim(tuan, "id", appt)
    assert dong_tuan is not None
    pid = await pool.fetchval(
        "SELECT clinic_patient_id::text FROM appointment WHERE id = $1::uuid", appt
    )
    cskh = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=[pid])
    dong_cskh = _tim(cskh["appts"], "id", appt)
    assert dong_cskh is not None
    trang_chu = await ManTrangChuService(pool).goi_du_lieu(
        identity=ca.le_tan, week_appt=ngay - timedelta(days=1), week_roster=ngay
    )
    dong_tc = _tim(trang_chu["trang_thai_kham"], "visit_id", vid)
    assert dong_tc is not None
    dong_tc_tuan = _tim(trang_chu["tuan_hen"], "id", appt)
    assert dong_tc_tuan is not None
    tiep_don = await TiepDonService(pool).hom_nay(identity=ca.le_tan)
    dong_td = _tim(tiep_don, "appointment_id", appt)
    assert dong_td is not None
    ht = await BangHanhTrinhService(pool).hom_nay(identity=ca.le_tan)
    dong_ht = _tim(ht["luot"], "visit_id", vid)
    assert dong_ht is not None
    return {
        "lich_tuan": dong_tuan["trang_thai"]["ma"],
        "trang_chu_tuan": dong_tc_tuan["trang_thai"]["ma"],
        "trang_chu_buoi": dong_tc["trang_thai"]["ma"],
        "cskh": dong_cskh["trang_thai"]["ma"],
        "tiep_don": dong_td["trang_thai"]["loai"],
        "hanh_trinh": dong_ht["dang_o"],
    }


@pytest.fixture
def _khong_tran(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chạy cả bộ test thì DB thử có hàng trăm lượt HÔM NAY — trần 300 dòng
    của bảng trạng thái buổi khám cắt mất lượt vừa dựng."""
    monkeypatch.setattr(man_trang_chu_service, "_TRAN_TRANG_THAI", 100_000)
    monkeypatch.setattr(bang_hanh_trinh_service, "_TRAN_LUOT", 100_000)


@pytest.mark.parametrize("code", ["THU_THUAT", "SAN_CHAU"])
@pytest.mark.usefixtures("_khong_tran")
async def test_check_out_moi_man_cung_noi_da_ve(
    pool: asyncpg.Pool,  # noqa: F811
    code: str,
) -> None:
    await _nhu_prod(pool)
    ca = await _dung(pool)
    loai = await _loai(pool, code)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), loai["id"])
    appt = await pool.fetchval(
        "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", vid
    )

    truoc = await _doc_moi_man(pool, ca, appt, vid)
    # Còn trong phòng khám: đang chờ ở bàn tư vấn (Hành trình khách).
    assert truoc["lich_tuan"] in ("DANG_CHO", "DA_CHECK_IN")
    assert truoc["cskh"] == truoc["lich_tuan"]
    assert truoc["tiep_don"] in ("den", "dang_o")

    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=vid, override_reason="Khách về (test)"
    )
    assert (
        await pool.fetchval("SELECT status FROM appointment WHERE id = $1::uuid", appt)
        == "COMPLETED"
    )
    sau = await _doc_moi_man(pool, ca, appt, vid)
    assert sau == {
        "lich_tuan": "DA_VE",
        "trang_chu_tuan": "DA_VE",
        "trang_chu_buoi": "DA_VE",
        "cskh": "DA_VE",
        "tiep_don": "ve",
        "hanh_trinh": "Đã về",
    }


@pytest.mark.usefixtures("_khong_tran")
async def test_ve_giua_chung_cung_dong_lich(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    await _nhu_prod(pool)
    ca = await _dung(pool)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    appt = await pool.fetchval(
        "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", vid
    )
    await CheckoutService(pool).close(
        identity=ca.le_tan,
        visit_id=vid,
        incomplete=True,
        incomplete_reason="Khách bận việc (test)",
    )
    sau = await _doc_moi_man(pool, ca, appt, vid)
    assert sau["lich_tuan"] == sau["cskh"] == sau["trang_chu_buoi"] == "VE_GIUA_CHUNG"
    assert sau["tiep_don"] == "ve"


async def test_backfill_chi_sua_lich_lech_chay_lai_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    # Lượt ĐÃ VỀ theo đường cũ (check-out không đụng lịch): lịch còn CHECKED_IN.
    lech = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", lech
    )
    # Lượt còn mở — backfill không được chạm.
    mo = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)

    async def _lich(vid: str) -> str:
        return str(
            await pool.fetchval(
                "SELECT a.status FROM appointment a JOIN visit v"
                " ON v.appointment_id = a.id WHERE v.visit_id = $1::uuid",
                vid,
            )
        )

    assert await _lich(lech) == "CHECKED_IN"
    await _ap(pool, BACKFILL)
    assert await _lich(lech) == "COMPLETED"
    assert await _lich(mo) == "CHECKED_IN"
    moc = await pool.fetchval(
        "SELECT max(updated_at) FROM appointment WHERE clinic_id = $1::uuid", CLINIC
    )
    await _ap(pool, BACKFILL)  # lần hai: không còn dòng lệch
    assert (
        await pool.fetchval(
            "SELECT max(updated_at) FROM appointment WHERE clinic_id = $1::uuid",
            CLINIC,
        )
        == moc
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM appointment a JOIN visit v ON v.appointment_id = a.id"
            " WHERE a.status = 'CHECKED_IN'"
            " AND (v.closed_at IS NOT NULL OR v.status IN ('FINALIZED', 'AMENDED'))"
        )
        == 0
    )


async def test_0910_thu_thuat_di_thang_vao_hang_bac_si_khong_phi_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền chốt 09/10/2026: Thủ thuật đi thẳng, không tự cộng phí khám (khác
    quyết định 30/09 ở các bài trên — bài này áp thêm migration mới)."""
    from clinicai.services.bill_service import tinh_hoa_don
    from clinicai.services.phi_kham_service import PhiKhamService

    await _nhu_prod(pool)
    await _ap(pool, DI_THANG_0910)
    await _ap(pool, DI_THANG_0910)  # chạy lại được
    tt = await _loai(pool, "THU_THUAT")
    assert (tt["di_thang_phong"], tt["qua_tu_van"]) == (True, False)
    sc = await _loai(pool, "SAN_CHAU")
    assert (sc["di_thang_phong"], sc["qua_tu_van"]) == (False, True)

    ca = await _dung(pool)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), tt["id"])
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", vid
        )
        == "PRIMARY"
    )
    hang = await pool.fetch(
        "SELECT lane FROM queue_entry WHERE visit_id = $1::uuid"
        " AND status NOT IN ('done', 'left', 'cancelled')",
        vid,
    )
    assert [q["lane"] for q in hang] == ["DOCTOR"]

    async def _dong_kham() -> list[dict[str, Any]]:
        async with pool.acquire() as conn:
            hd = await tinh_hoa_don(
                conn, clinic_id=CLINIC, visit_id=vid, kind="dich_vu"
            )
        return [dict(x) for x in hd.cho_api()["dong"] if x["source_type"] == "exam"]

    assert await _dong_kham() == []
    # Tick dịch vụ khám con → có phí khám đúng phần đã tick.
    sp = await pool.fetchval(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, ma_kiotviet) VALUES ($1::uuid, $2, 'Khám trước thủ thuật"
        " (thử 0910)', 'dich_vu', 120000, $2) RETURNING id::text",
        CLINIC,
        f"TT0910-{vid[:8]}",
    )
    await pool.execute(
        "INSERT INTO loai_kham_phi (clinic_id, service_type_id, service_price_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        tt["id"],
        sp,
    )
    await PhiKhamService(pool).chon(visit_id=vid, ids=[sp], identity=ca.bac_si)
    [d] = await _dong_kham()
    assert int(d["don_gia"]) == 120000
