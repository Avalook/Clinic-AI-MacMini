"""KHUNG PHẢI CỦA KHÁCH (Tuyền 27/09/2026) — ghi chú chung, tóm tắt mọi thứ của
khách, và thanh ngày ngang (``tu``/``den``) của danh sách khách.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55530/postgres \\
        poetry run pytest src/tests/services/test_ghi_chu_khach_db.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.danh_sach_khach_cskh import (
    KHOANG_TOI_DA_NGAY,
    cua_so_khoang,
    danh_sach_khach,
)
from clinicai.services.ghi_chu_khach_service import (
    GhiChuKhachService,
    lam_sach_noi_dung,
)
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

# ── Hàm thuần: đầu vào rác → rỗng, không ném ─────────────────────────────


def test_cua_so_khoang_rac_tra_rong_khong_nem() -> None:
    cac_rac: list[object] = [None, "", "   ", "rác", "2026-13-45", "27/09/2026"]
    cac_rac += [123, [], {}]
    for rac in cac_rac:
        assert cua_so_khoang(rac, rac) is None


def test_cua_so_khoang_mot_ngay_va_doi_cho() -> None:
    mot = cua_so_khoang("2026-09-26", "2026-09-26")
    assert mot == (
        datetime(2026, 9, 26, tzinfo=CLINIC_TZ),
        datetime(2026, 9, 27, tzinfo=CLINIC_TZ),
    )
    # Thiếu một đầu → khoảng một ngày của đầu còn lại.
    assert cua_so_khoang("2026-09-26", "rác") == mot
    assert cua_so_khoang(None, "2026-09-26T10:00:00") == mot
    # Ngược chiều → đổi chỗ.
    assert cua_so_khoang("2026-09-27", "2026-09-20") == (
        datetime(2026, 9, 20, tzinfo=CLINIC_TZ),
        datetime(2026, 9, 28, tzinfo=CLINIC_TZ),
    )


def test_cua_so_khoang_cat_khoang_qua_dai() -> None:
    dau, cuoi = cua_so_khoang("2020-01-01", "2026-09-27") or (None, None)
    assert cuoi == datetime(2026, 9, 28, tzinfo=CLINIC_TZ)
    assert dau is not None and cuoi is not None
    assert (cuoi - dau).days == KHOANG_TOI_DA_NGAY + 1


def test_lam_sach_noi_dung() -> None:
    assert lam_sach_noi_dung("  khách dặn gọi sau 17h ") == "khách dặn gọi sau 17h"
    cac_rac: list[object] = [None, "", "   ", 5, "x" * 2001, ["a"]]
    for rac in cac_rac:
        assert lam_sach_noi_dung(rac) is None


# ── Database ─────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_ghi_xem_go_ghi_chu(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    sv = GhiChuKhachService(pool)
    moi = await sv.ghi(
        identity=ca.le_tan, clinic_patient_id=pid, noi_dung="  Khách dặn gọi sau 17h "
    )
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, ca.loc, "CSKH")
    await sv.ghi(identity=cskh, clinic_patient_id=pid, noi_dung="Đã hẹn tái khám")

    ds = await sv.danh_sach(identity=cskh, clinic_patient_id=pid)
    assert [g["noi_dung"] for g in ds] == ["Đã hẹn tái khám", "Khách dặn gọi sau 17h"]
    assert [g["cua_toi"] for g in ds] == [True, False]
    assert ds[1]["nguoi_ghi"] == ca.le_tan.full_name

    # Người khác KHÔNG gỡ được dòng của lễ tân.
    with pytest.raises(NotFoundError):
        await sv.go(identity=cskh, ghi_chu_id=moi["id"])
    await sv.go(identity=ca.le_tan, ghi_chu_id=moi["id"])
    # Gỡ lần hai: không còn gì để gỡ.
    with pytest.raises(NotFoundError):
        await sv.go(identity=ca.le_tan, ghi_chu_id=moi["id"])
    ds = await sv.danh_sach(identity=cskh, clinic_patient_id=pid)
    assert [g["noi_dung"] for g in ds] == ["Đã hẹn tái khám"]
    # Dòng gỡ vẫn còn, kèm dấu vết.
    vet = await pool.fetchrow(
        "SELECT go_luc, go_boi_staff_id::text AS ai FROM ghi_chu_khach"
        " WHERE id = $1::uuid",
        moi["id"],
    )
    assert vet is not None and vet["go_luc"] is not None
    assert vet["ai"] == ca.le_tan.staff_id


@pytest.mark.db
@pytest.mark.asyncio
async def test_ghi_chu_rac_va_khach_la_va_khong_quyen(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    sv = GhiChuKhachService(pool)
    with pytest.raises(ValidationError):
        await sv.ghi(identity=ca.le_tan, clinic_patient_id=pid, noi_dung="   ")
    with pytest.raises(NotFoundError):
        await sv.ghi(
            identity=ca.le_tan, clinic_patient_id=str(uuid.uuid4()), noi_dung="a"
        )
    async with pool.acquire() as conn:
        duoc_si = await _nguoi(conn, ca.loc, "PHARMACIST")
        await ve_goi_mau_cu(conn, duoc_si)  # gói lego cũ (mở full lego 30/09)
    with pytest.raises(SafetyGateError):
        await sv.ghi(identity=duoc_si, clinic_patient_id=pid, noi_dung="a")
    with pytest.raises(SafetyGateError):
        await sv.tom_tat(identity=duoc_si, clinic_patient_id=pid)


@pytest.mark.db
@pytest.mark.asyncio
async def test_tom_tat_moi_thu_cua_khach(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    # Lượt hôm nay: khám + chỉ định, khách chọn làm, CHƯA thu.
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    # Lịch sắp tới (tuần sau) + hẹn tái khám bác sĩ đặt.
    tuan_sau = datetime.combine(
        now_vn().date() + timedelta(days=7), time(9, 0), tzinfo=CLINIC_TZ
    )
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'SCHEDULED')",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        tuan_sau,
        tuan_sau + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    ngay_hen = now_vn().date() + timedelta(days=30)
    await pool.execute(
        "INSERT INTO nhac_tai_kham (clinic_id, clinic_patient_id, luot_goi,"
        " ngay_hen, han_goi, nguon_visit_id) VALUES ($1::uuid, $2::uuid, 1, $3,"
        " $4, $5::uuid)",
        CLINIC,
        pid,
        ngay_hen,
        ngay_hen - timedelta(days=7),
        visit,
    )
    sv = GhiChuKhachService(pool)
    await sv.ghi(identity=ca.le_tan, clinic_patient_id=pid, noi_dung="VIP")

    tt = await sv.tom_tat(identity=ca.le_tan, clinic_patient_id=pid)
    assert tt["khach"]["id"] == pid
    assert [x["luc"][:10] for x in tt["lich_sap_toi"]] == [tuan_sau.date().isoformat()]
    assert tt["luot_gan_nhat"][0]["visit_id"] == visit
    assert [c["id"] for c in tt["chi_dinh_chua_lam"]] == [order]
    assert tt["tien"]["da_tra"] == 0
    assert tt["tien"]["con_phai_thu"] > 0
    assert {x["loai"] for x in tt["tien"]["con_phai_thu_chi_tiet"]} == {"dich_vu"}
    assert tt["hen_tai_kham"][0]["ngay_hen"] == ngay_hen.isoformat()
    assert tt["hen_tai_kham"][0]["bac_si"] == ca.bac_si.full_name
    assert tt["so_ghi_chu"] == 1

    # Thu xong: hết nợ dịch vụ, có tiền đã trả.
    await _thu(pool, visit, ca.le_tan)
    tt = await sv.tom_tat(identity=ca.le_tan, clinic_patient_id=pid)
    assert tt["tien"]["da_tra"] > 0
    assert tt["tien"]["con_phai_thu"] == 0

    with pytest.raises(NotFoundError):
        await sv.tom_tat(identity=ca.le_tan, clinic_patient_id=str(uuid.uuid4()))


@pytest.mark.db
@pytest.mark.asyncio
async def test_danh_sach_khach_theo_khoang_ngay(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    hom_qua = await pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
        " created_at) VALUES ($1::uuid, $2, $3, $4::uuid, now() - interval '1 day')"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"KNG-{duoi}-1",
        f"Khoảng {duoi} Hôm qua",
        ca.loc,
    )
    hom_nay = await pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, $3, $4::uuid) RETURNING clinic_patient_id::text",
        CLINIC,
        f"KNG-{duoi}-2",
        f"Khoảng {duoi} Hôm nay",
        ca.loc,
    )
    ngay = now_vn().date()
    qua = (ngay - timedelta(days=1)).isoformat()
    kq = await danh_sach_khach(pool, identity=ca.le_tan, q=duoi, tu=qua, den=qua)
    assert [r["clinic_patient_id"] for r in kq["rows"]] == [hom_qua]
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, q=duoi, tu=qua, den=ngay.isoformat()
    )
    assert {r["clinic_patient_id"] for r in kq["rows"]} == {hom_qua, hom_nay}
    # Khoảng thắng kỳ đặt sẵn; khoảng rác thì dùng kỳ.
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, q=duoi, ky="today", tu=qua, den=qua
    )
    assert [r["clinic_patient_id"] for r in kq["rows"]] == [hom_qua]
    kq = await danh_sach_khach(
        pool, identity=ca.le_tan, q=duoi, ky="today", tu="rác", den="??"
    )
    assert [r["clinic_patient_id"] for r in kq["rows"]] == [hom_nay]
    # Theo ngày hẹn cũng nhận khoảng.
    kq = await danh_sach_khach(
        pool,
        identity=ca.le_tan,
        q=duoi,
        theo="appt",
        tu=date(2000, 1, 1).isoformat(),
        den=date(2000, 1, 2).isoformat(),
    )
    assert kq["rows"] == []
