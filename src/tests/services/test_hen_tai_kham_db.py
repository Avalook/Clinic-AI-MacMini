"""Hẹn tái khám trên phiếu → việc CSKH bám theo lượt (Tuyền chốt 29/09/2026).

Bác sĩ chỉ đặt NGÀY. Kiểm: việc có hạn gọi đúng 7 ngày trước + chuông hẹn đúng
07:00 ngày ấy; nội dung việc đủ trường; sửa ngày → cùng một việc (không nhân
đôi); xoá ngày → đóng kèm lý do; sửa sau Hoàn tất vẫn áp; khách đã có lịch →
không bắt gọi; ngày rác → không ném; ca bác sĩ mới phủ lịch chờ xếp → chuông
CSKH trong app.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.events.consumers.nhac_tai_kham import bao_den_han
from clinicai.events.hen_gio import HenDenHan
from clinicai.services.config_service import RosterService
from clinicai.services.ghi_chu_khach_service import GhiChuKhachService
from clinicai.services.hen_tai_kham_service import HEN_NHAC_TAI_KHAM
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.recall_job_service import RecallJobService
from clinicai.services.thong_bao_service import ThongBaoService
from tests.services.test_phieu_kham_db import (
    CLINIC,
    _luot,
    _nguoi,
    _o,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _hom_nay() -> dt.date:
    return dt.datetime.now(CLINIC_TZ).date()


async def _luu(
    pool: asyncpg.Pool,  # noqa: F811
    bs: StaffIdentity,
    visit: str,
    thay_doi: dict[str, Any],
) -> dict[str, Any]:
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).luu_luot(
        visit_id=visit,
        form_id="PK",
        du_lieu=None,
        expected_revision=0,
        thay_doi=thay_doi,
        identity=bs,
    )


async def _viec(pool: asyncpg.Pool, visit: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT id::text, ngay_hen, han_goi, trang_thai, dong_vi, ghi_chu"
            "  FROM nhac_tai_kham WHERE nguon_visit_id = $1::uuid ORDER BY created_at",
            visit,
        )
    )


async def _hen_cho(pool: asyncpg.Pool, viec_id: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT id::text, den_gio, chi_tiet, trang_thai FROM hen_gio"
            " WHERE loai = $1 AND ve_cai_gi = $2::uuid AND trang_thai = 'CHO'",
            HEN_NHAC_TAI_KHAM,
            viec_id,
        )
    )


async def _chuan_bi(pool: asyncpg.Pool) -> tuple[StaffIdentity, dict[str, str]]:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = $2::uuid WHERE visit_id = $1::uuid",
            luot["visit"],
            bs.staff_id,
        )
    return bs, luot


async def test_chi_ngay_sinh_mot_viec_han_7_ngay_va_du_noi_dung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    v = luot["visit"]
    ngay = _hom_nay() + dt.timedelta(days=30)
    kq = await _luu(
        pool,
        bs,
        v,
        {
            "pk_dx": _o("Rối loạn nội tiết"),
            "pk_follow_tests": _o(["pk_follow_tests_1", "pk_follow_tests_3"]),
            "pk_follow_note": _o("Nhịn ăn sáng khi tới"),
            "pk_follow_date": _o(ngay.isoformat()),
        },
    )
    assert kq["hen_tai_kham"]["trang_thai"] == "CHO_GOI"
    viec = await _viec(pool, v)
    assert len(viec) == 1
    assert viec[0]["ngay_hen"] == ngay
    assert viec[0]["han_goi"] == ngay - dt.timedelta(days=7)
    # Chuông hẹn ĐÚNG 07:00 giờ VN của ngày hạn gọi (T−7).
    hen = await _hen_cho(pool, viec[0]["id"])
    assert len(hen) == 1
    moc = dt.datetime.combine(
        ngay - dt.timedelta(days=7), dt.time(7, 0), tzinfo=CLINIC_TZ
    )
    # den_gio = now() của database + khoảng tính từ đồng hồ máy chủ → lệch vài ms.
    assert abs(hen[0]["den_gio"] - moc) < dt.timedelta(seconds=5)
    # Chưa tới hạn: KHÔNG hiện ở việc CSKH (v_viec_cskh); khung khách: chưa tới hạn.
    pid = luot["patient"]
    assert not await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM v_viec_cskh WHERE clinic_patient_id = $1::uuid"
        " AND trang_thai = 'MOI_TAI_KHAM')",
        pid,
    )
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, "CSKH")
    tt = await GhiChuKhachService(pool).tom_tat(identity=cskh, clinic_patient_id=pid)
    h = tt["hen_tai_kham"][0]
    assert h["tinh_trang"] == "CHUA_TOI_HAN"
    ct = h["chi_tiet"]
    assert ct["bac_si"] and ct["chan_doan"] == "Rối loạn nội tiết"
    assert ct["can_kiem_tra"] == ["Hormone", "Siêu âm"]
    assert ct["ghi_chu_bac_si"] == "Nhịn ăn sáng khi tới"
    assert ct["ngay_kham"] == _hom_nay().isoformat()


async def test_sua_ngay_bam_theo_cung_viec_xoa_ngay_thi_huy(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    v = luot["visit"]
    d1 = _hom_nay() + dt.timedelta(days=20)
    d2 = _hom_nay() + dt.timedelta(days=40)
    await _luu(pool, bs, v, {"pk_follow_date": _o(d1.isoformat())})
    (dau,) = await _viec(pool, v)
    # Tự lưu gõ lại cùng ngày: không đổi gì.
    await _luu(pool, bs, v, {"pk_follow_date": _o(d1.isoformat()), "pk_dx": _o("x")})
    # Sửa ngày → CHÍNH việc ấy dời, hẹn chuông dời theo.
    await _luu(pool, bs, v, {"pk_follow_date": _o(d2.isoformat())})
    viec = await _viec(pool, v)
    assert [r["id"] for r in viec] == [dau["id"]]
    assert viec[0]["ngay_hen"] == d2
    assert viec[0]["han_goi"] == d2 - dt.timedelta(days=7)
    hen = await _hen_cho(pool, dau["id"])
    assert len(hen) == 1
    assert json.loads(hen[0]["chi_tiet"])["ngay_hen"] == d2.isoformat()
    # Sửa SAU Hoàn tất vẫn áp.
    await pool.execute(
        "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid", v
    )
    d3 = _hom_nay() + dt.timedelta(days=60)
    await _luu(pool, bs, v, {"pk_follow_date": _o(d3.isoformat())})
    viec = await _viec(pool, v)
    assert [(r["id"], r["ngay_hen"]) for r in viec] == [(dau["id"], d3)]
    # Bộ quét cũ chạy lại cũng không đẻ thêm việc.
    await pool.fetch(
        "SELECT * FROM public.sinh_viec_nhac_tai_kham($1::uuid, $2::date)",
        CLINIC,
        _hom_nay(),
    )
    assert len(await _viec(pool, v)) == 1
    # Xoá ngày → việc đóng kèm lý do, chuông hẹn gỡ.
    kq = await _luu(pool, bs, v, {"pk_follow_date": _o("")})
    assert kq["hen_tai_kham"]["trang_thai"] == "KHONG_HEN"
    (r,) = await _viec(pool, v)
    assert (r["trang_thai"], r["dong_vi"], r["ghi_chu"]) == (
        "KHONG_CAN",
        "BS_BO_HEN",
        "Bác sĩ bỏ hẹn tái khám",
    )
    assert await _hen_cho(pool, dau["id"]) == []
    # Đặt lại ngày → mở lại đúng việc ấy, không nhân đôi.
    await _luu(pool, bs, v, {"pk_follow_date": _o(d3.isoformat())})
    viec = await _viec(pool, v)
    assert [(r["id"], r["trang_thai"]) for r in viec] == [(dau["id"], "CHO_GOI")]
    # Lịch sử: mỗi lần đổi một dòng nhật ký, có từ → tới.
    doi = await pool.fetch(
        "SELECT payload FROM event_log WHERE event_type = 'nhac_tai_kham.hen_doi'"
        " AND aggregate_id = $1::uuid ORDER BY recorded_at, occurred_at",
        v,
    )
    buoc = [json.loads(p["payload"]) for p in doi]
    assert [(b["tu"], b["toi"]) for b in buoc] == [
        (None, d1.isoformat()),
        (d1.isoformat(), d2.isoformat()),
        (d2.isoformat(), d3.isoformat()),
        (d3.isoformat(), None),
        (None, d3.isoformat()),
    ]


async def test_toi_han_chuong_cskh_va_da_co_lich_thi_khong_bat_goi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    v, pid = luot["visit"], luot["patient"]
    # Hẹn 5 ngày nữa → hạn gọi là HÔM NAY (không đỏ quá hạn), chuông ngay.
    ngay = _hom_nay() + dt.timedelta(days=5)
    await _luu(pool, bs, v, {"pk_follow_date": _o(ngay.isoformat())})
    (viec,) = await _viec(pool, v)
    assert viec["han_goi"] == _hom_nay()
    (hen,) = await _hen_cho(pool, viec["id"])
    assert hen["den_gio"] <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    cai_hen = HenDenHan(
        id=hen["id"],
        clinic_id=CLINIC,
        loai=HEN_NHAC_TAI_KHAM,
        ve_cai_gi=viec["id"],
        correlation_id=v,
        chi_tiet=json.loads(hen["chi_tiet"]),
        so_lan_thu=1,
    )
    async with pool.acquire() as conn, conn.transaction():
        assert await bao_den_han(conn, cai_hen) is True
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, "CSKH")
    chuong = [
        c
        for c in await ThongBaoService(pool).cua_toi(identity=cskh)
        if f"{ngay:%d/%m}" in c["tieu_de"] and "cần gọi chốt giờ" in c["tieu_de"]
    ]
    assert len(chuong) >= 1 and chuong[0]["duong_dan"] == f"/customers?selected={pid}"
    # Tới hạn → hiện ở màn Nhắc tái khám, kèm chi tiết.
    ds = await RecallJobService(pool).danh_sach(identity=cskh, sinh_truoc=False)
    mine = [x for x in ds["luot1"] if x["id"] == viec["id"]]
    assert mine and mine[0]["chi_tiet"]["visit_id"] == v

    # Khách đặt lịch trong khoảng hạn gọi → việc tự đóng "đã có lịch".
    loai = await pool.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active)"
        " VALUES ($1::uuid, $2, 'Tái khám test', true) RETURNING id::text",
        CLINIC,
        f"TK-{uuid.uuid4().hex[:8]}",
    )
    bat_dau = dt.datetime.combine(ngay, dt.time(9, 0), tzinfo=CLINIC_TZ)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'CONFIRMED')",
        CLINIC,
        pid,
        bs.location_id,
        loai,
        bat_dau,
        bat_dau + dt.timedelta(minutes=15),
    )
    (r,) = await _viec(pool, v)
    assert (r["trang_thai"], r["dong_vi"]) == ("KHONG_CAN", "DA_CO_LICH")
    async with pool.acquire() as conn, conn.transaction():
        assert await bao_den_han(conn, cai_hen) is False
    tt = await GhiChuKhachService(pool).tom_tat(identity=cskh, clinic_patient_id=pid)
    assert tt["hen_tai_kham"][0]["tinh_trang"] == "DA_CO_LICH"
    # Bác sĩ đặt ngày khi khách ĐÃ có lịch → việc sinh ra đã đóng, không hẹn chuông.
    ngay2 = ngay + dt.timedelta(days=1)
    kq = await _luu(pool, bs, v, {"pk_follow_date": _o(ngay2.isoformat())})
    assert kq["hen_tai_kham"]["trang_thai"] == "DA_CO_LICH"
    assert await _hen_cho(pool, viec["id"]) == []


async def test_ngay_rac_va_ngay_da_qua_khong_nem_khong_sinh_viec(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    v = luot["visit"]
    kq = await _luu(pool, bs, v, {"pk_follow_date": _o("hôm nào đó")})
    assert kq["canh_bao"] and kq["canh_bao"][0]["ma"] == "pk_follow_date"
    assert await _viec(pool, v) == []
    kq = await _luu(pool, bs, v, {"pk_follow_date": _o("31/02/2026")})
    assert await _viec(pool, v) == []
    qua = _hom_nay() - dt.timedelta(days=2)
    kq = await _luu(pool, bs, v, {"pk_follow_date": _o(qua.isoformat())})
    assert kq["hen_tai_kham"]["trang_thai"] == "KHONG_HEN"
    assert await _viec(pool, v) == []


async def test_ca_bac_si_moi_phu_lich_cho_xep_thi_chuong_cskh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
        cskh = await _nguoi(conn, "CSKH")
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        loai = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Khám chờ xếp', true) RETURNING id::text",
            CLINIC,
            f"CX-{uuid.uuid4().hex[:8]}",
        )
        ngay = _hom_nay() + dt.timedelta(days=3)
        bat_dau = dt.datetime.combine(ngay, dt.time(9, 0), tzinfo=CLINIC_TZ)
        await conn.execute(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'CONFIRMED')",
            CLINIC,
            luot["patient"],
            bs.location_id,
            loai,
            bat_dau,
            bat_dau + dt.timedelta(minutes=15),
        )
        roster_id = str(uuid.uuid4())
        ten = f"Ca {roster_id[:6]}"
        await RosterService(pool)._bao_lich_cho_xep(
            conn,
            roster_id=roster_id,
            work_date=ngay,
            shift="FULL",
            ten_bac_si=ten,
            identity=ql,
        )
    chuong = [
        c
        for c in await ThongBaoService(pool).cua_toi(identity=cskh)
        if c["tieu_de"].startswith(f"BS {ten} có ca {ngay:%d/%m}")
    ]
    assert len(chuong) == 1
    assert "lịch đang chờ xếp" in chuong[0]["tieu_de"]
    assert "09:00" in chuong[0]["noi_dung"]
    # Sổ sự kiện vẫn giữ (đường Telegram cũ không đụng).
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log"
            " WHERE event_type = 'roster.shift_added_cho_xep'"
            " AND aggregate_id = $1::uuid",
            roster_id,
        )
        == 1
    )
