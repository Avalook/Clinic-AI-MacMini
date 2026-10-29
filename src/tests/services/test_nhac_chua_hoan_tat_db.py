"""Nhắc lượt chưa Hoàn tất khám (Tuyền duyệt 22/10/2026).

Hoàn tất khám không phải một nút: máy tự khép lượt khi hết việc dở
(`LuotKhamService._ket_thuc_neu_xong`). Lượt chưa Hoàn tất = còn việc dở, và
nhắc phải nói ĐÚNG việc ấy. Đo prod 21/10: 22/26 lượt kẹt vì vòng đọc kết quả
chưa đóng, 4 vì phiên khám bỏ dở, 0 vì chỉ định chưa làm.

Giờ check-in đặt thẳng vào dòng (không theo đồng hồ máy) — test lấy "bây giờ +
N phút" đỏ giả sau 23:30 (CI 21/10).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.services.booking_service import BookingService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.man_trang_chu_service import ManTrangChuService
from clinicai.services.nhac_chua_hoan_tat import (
    dem_luot_chua_hoan_tat,
    doc_luot_chua_hoan_tat,
    luot_chua_hoan_tat,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _vao(pool: asyncpg.Pool, ca: Ca, *, truoc: timedelta) -> str:  # noqa: F811
    """Check-in thật (lịch hẹn của ca.bac_si), rồi lùi giờ check-in về `truoc`."""
    pid = await _benh_nhan(pool, ca)
    bd = datetime.now(UTC) - timedelta(minutes=1)
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
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca.le_tan
    )
    await chay_hanh_trinh(pool)
    vid = str(
        await pool.fetchval(
            "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
        )
    )
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - $2::interval"
        " WHERE visit_id = $1::uuid",
        vid,
        truoc,
    )
    return vid


async def _phien_chinh(pool: asyncpg.Pool, vid: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            vid,
        )
    )


async def _vong_doc(pool: asyncpg.Pool, ca: Ca, vid: str, trang_thai: str) -> None:  # noqa: F811
    """Khám xong phiên chính, mở một vòng đọc kết quả ở `trang_thai`."""
    await pool.execute(
        "UPDATE consultation SET status = 'completed', completed_at = now(),"
        " outcome = 'SERVICES', doctor_staff_id = $2::uuid"
        " WHERE visit_id = $1::uuid AND kind = 'PRIMARY'",
        vid,
        ca.bac_si.staff_id,
    )
    await pool.execute(
        "INSERT INTO review_round (clinic_id, visit_id, round_no, status, locked_by,"
        " ready_at) VALUES ($1::uuid, $2::uuid, 2, $3, $4::uuid,"
        " CASE WHEN $3 <> 'collecting' THEN now() END)",
        CLINIC,
        vid,
        trang_thai,
        ca.bac_si.staff_id,
    )


def _cua(kq: dict, vid: str) -> dict | None:  # type: ignore[type-arg]
    return next((x for x in kq["items"] if x["visit_id"] == vid), None)


async def test_qua_2_gio_chua_ai_kham_hien_cho_kham(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(hours=3))
    async with pool.acquire() as conn:
        kq = await luot_chua_hoan_tat(conn, identity=ca.bac_si)
    dong = _cua(kq, vid)
    assert dong is not None
    assert dong["ly_do"] == "cho_kham"
    assert dong["ly_do_chu"]
    assert dong["bac_si_id"] == ca.bac_si.staff_id
    # "3 giờ trước" sang ngày hôm qua nếu chạy trước 03:00 — so với ngày VN thật.
    assert dong["tu_hom_truoc"] is (dong["ngay"] < now_vn().date().isoformat())
    assert kq["pham_vi"] == "cua_toi"


async def test_moi_check_in_chua_toi_2_gio_khong_nhac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(minutes=30))
    async with pool.acquire() as conn:
        kq = await luot_chua_hoan_tat(conn, identity=ca.bac_si)
    assert _cua(kq, vid) is None


async def test_tu_hom_truoc_gan_co(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(days=1, hours=1))
    async with pool.acquire() as conn:
        dong = _cua(await luot_chua_hoan_tat(conn, identity=ca.bac_si), vid)
    assert dong is not None and dong["tu_hom_truoc"] is True


async def test_phien_kham_dang_mo_do(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(hours=3))
    await LuotKhamService(pool).start_consultation(
        consultation_id=await _phien_chinh(pool, vid), identity=ca.bac_si
    )
    async with pool.acquire() as conn:
        dong = _cua(await luot_chua_hoan_tat(conn, identity=ca.bac_si), vid)
    assert dong is not None and dong["ly_do"] == "kham_do"


@pytest.mark.parametrize(
    ("trang_thai", "ly_do"),
    [
        ("collecting", "cho_ket_qua"),
        ("ready", "cho_doc_ket_qua"),
        ("in_review", "dang_doc_do"),
    ],
)
async def test_vong_doc_ket_qua_tach_ly_do(
    pool: asyncpg.Pool,  # noqa: F811
    trang_thai: str,
    ly_do: str,
) -> None:
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(hours=3))
    await _vong_doc(pool, ca, vid, trang_thai)
    async with pool.acquire() as conn:
        dong = _cua(await luot_chua_hoan_tat(conn, identity=ca.bac_si), vid)
    assert dong is not None and dong["ly_do"] == ly_do


async def test_da_hoan_tat_hoac_da_check_out_khong_nhac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    xong = await _vao(pool, ca, truoc=timedelta(hours=3))
    ve = await _vao(pool, ca, truoc=timedelta(hours=3))
    await pool.execute(
        "UPDATE visit SET exam_completed_at = now() WHERE visit_id = $1::uuid", xong
    )
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", ve
    )
    async with pool.acquire() as conn:
        kq = await luot_chua_hoan_tat(conn, identity=ca.bac_si)
    assert _cua(kq, xong) is None
    assert _cua(kq, ve) is None


async def test_bac_si_khac_khong_thay_thu_ky_thay_cua_bac_si_minh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    # Cùng luật phạm vi với khối "Chờ bác sĩ quyết" (`cho_quyet`): thư ký đã phân
    # → khách của bác sĩ mình; người Hoàn tất được → lượt của mình.
    ca = await _dung(pool)
    vid = await _vao(pool, ca, truoc=timedelta(hours=3))
    async with pool.acquire() as conn:
        bs_khac = await _nguoi(conn, ca.loc, "DOCTOR")
        thu_ky = await _nguoi(conn, ca.loc, "TKYK")
        await conn.execute(
            "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id,"
            " phan_boi) VALUES ($1::uuid, $2::uuid, $3::uuid, $3::uuid)",
            CLINIC,
            thu_ky.staff_id,
            ca.bac_si.staff_id,
        )
        cua_bs_khac = await luot_chua_hoan_tat(conn, identity=bs_khac)
        cua_thu_ky = await luot_chua_hoan_tat(conn, identity=thu_ky)
    assert _cua(cua_bs_khac, vid) is None
    dong = _cua(cua_thu_ky, vid)
    assert cua_thu_ky["pham_vi"] == "bac_si_duoc_phan"
    assert dong is not None and dong["bac_si_ten"] == ca.bac_si.full_name


async def test_luot_dieu_tri_cho_bac_si_tuy_chon_khong_nhac(pool: asyncpg.Pool) -> None:  # noqa: F811
    # Lượt Điều trị: hàng bác sĩ là tuỳ chọn — phiên chưa ai nhận không phải việc
    # dở (cùng luật màn check-out, checkout_service ②b).
    ca = await _dung(pool)
    # Loại khám Điều trị phải trỏ một dòng giá (ràng buộc service_type_dieu_tri_co_gia).
    await pool.execute(
        "UPDATE service_type SET nhom = 'DIEU_TRI', service_price_id ="
        " (SELECT id FROM service_price WHERE clinic_id = $2::uuid"
        "   AND service_code = $3) WHERE id = $1::uuid",
        ca.loai_kham,
        CLINIC,
        ca.ma_dv,
    )
    vid = await _vao(pool, ca, truoc=timedelta(hours=3))
    async with pool.acquire() as conn:
        kq = await luot_chua_hoan_tat(conn, identity=ca.bac_si)
    assert _cua(kq, vid) is None


async def test_dem_cho_trang_chu_khop_danh_sach_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    await _vao(pool, ca, truoc=timedelta(hours=3))
    async with pool.acquire() as conn:
        # Một ảnh chụp cho cả hai câu — test khác chạy song song thêm lượt.
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            ds = await doc_luot_chua_hoan_tat(
                conn, clinic_id=CLINIC, location_id=ca.loc, bac_si=None
            )
            so = await dem_luot_chua_hoan_tat(
                conn, clinic_id=CLINIC, location_id=ca.loc
            )
    assert so == len(ds) >= 1


async def test_trang_chu_chi_quan_ly_thay_dong_dem(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    await _vao(pool, ca, truoc=timedelta(hours=3))
    async with pool.acquire() as conn:
        quan_ly = await _nguoi(conn, ca.loc, "MANAGEMENT")
    tuan = now_vn().date()

    async def _dong(ai: StaffIdentity) -> dict | None:  # type: ignore[type-arg]
        tc = await ManTrangChuService(pool).goi_du_lieu(
            identity=ai, week_appt=tuan, week_roster=tuan
        )
        return next(
            (x for x in tc["can_xu_ly"] if x["ma"] == "chua_hoan_tat_kham"), None
        )

    dong_ql = await _dong(quan_ly)
    assert dong_ql is not None and dong_ql["so"] >= 1
    assert await _dong(ca.bac_si) is None
    # Bấm dòng đếm → Bàn khám: quản lý thấy cả cơ sở (phiếu duyệt 22/10), không
    # phải "lượt của mình" như bác sĩ.
    async with pool.acquire() as conn:
        kq = await luot_chua_hoan_tat(conn, identity=quan_ly)
    assert kq["pham_vi"] == "co_so"
    assert len(kq["items"]) == dong_ql["so"]


async def test_khong_lan_sang_phong_kham_khac(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        so = await dem_luot_chua_hoan_tat(
            conn, clinic_id=str(uuid.uuid4()), location_id=None
        )
    assert so == 0
