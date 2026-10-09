"""Báo cáo CA CỦA TÔI + thu lego Báo cáo về Quản lý / Trưởng ca (09/10/2026).

Database thật. Kịch bản: thu ngân thu tiền thuốc lúc này (ca hiện tại, cơ sở A);
một nhân viên trực đúng ca ấy ở cơ sở A xem /bao-cao-ca → số y hệt báo cáo của
Quản lý với ``ca=…&co_so=A``, không có "theo người thu" / "theo cơ sở". Ca khác,
cơ sở khác, ca rác, không có ca, ca bị từ chối → 403 (không 500).

DB dùng chung → so hai báo cáo của cùng một lượt chạy, không đếm tuyệt đối.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import CAC_CA, ca_tu_settings, khung_chot_ca
from clinicai.services.bao_cao_ca_cua_toi_service import (
    AN_VOI_NHAN_VIEN,
    BaoCaoCaCuaToiService,
)
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay
from tests.services.test_tien_thuoc_cp3_db import _san_sang
from tests.services.test_tien_thuoc_cp3_db import _thu as _thu_thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20261010300000_bao_cao_chi_quan_ly_truong_ca.sql"
)

#: Khối số liệu nhân viên ĐƯỢC thấy — phải khớp báo cáo Quản lý từng con số.
GIONG_QUAN_LY = (
    "tong",
    "theo_hinh_thuc",
    "theo_loai",
    "hang_hoa",
    "hoan_huy",
    "no_trong_ca",
    "ca",
    "co_so",
)


async def _loc(q: Quay) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT coalesce(v.location_id, a.location_id)::text FROM visit v"
            " LEFT JOIN appointment a ON a.id = v.appointment_id"
            " WHERE v.visit_id = $1::uuid",
            q.visit_id,
        )
    )


async def _xep_ca(
    pool: asyncpg.Pool,
    ai: StaffIdentity,
    shift: str,
    location_id: str | None,
    status: str = "APPROVED",
) -> None:
    """Xếp ``ai`` vào một vị trí mới (phòng thuộc ``location_id``; None = vị
    trí không gắn phòng) ca ``shift`` hôm nay."""
    ma = f"T-BCC-{uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn:
        phong = None
        if location_id is not None:
            phong = await conn.fetchval(
                "INSERT INTO clinic_room (clinic_id, location_id, code, name,"
                " node_code, accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $3,"
                " 'DICHVU-SIEUAM', false, 9999) RETURNING id::text",
                CLINIC,
                location_id,
                ma,
            )
        await conn.execute(
            "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
            " VALUES ($1::uuid, $2, $2, $3::uuid)",
            CLINIC,
            ma,
            phong,
        )
        hom_nay = await conn.fetchval(
            "SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        )
        await conn.execute(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
            " station, staff_id, staff_name, status)"
            " VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, $7, $8)",
            CLINIC,
            hom_nay - dt.timedelta(days=hom_nay.weekday()),
            hom_nay,
            shift,
            ma,
            ai.staff_id,
            ai.full_name,
            status,
        )


async def _ca_cua(pool: asyncpg.Pool, cycle_id: str) -> tuple[str, str]:
    """(ca chứa giờ thu, ngày VN) — theo giờ THẬT trong DB."""
    paid_at, settings = await pool.fetchrow(
        "SELECT pc.paid_at, c.settings FROM payment_cycle pc"
        " JOIN clinic c ON c.id = pc.clinic_id WHERE pc.payment_cycle_id = $1::uuid",
        cycle_id,
    )
    vn = paid_at.astimezone(CLINIC_TZ)
    phut = vn.hour * 60 + vn.minute
    bang = ca_tu_settings(settings)
    ca = next(
        m for m in CAC_CA if (w := khung_chot_ca(m, bang)) and w[0] <= phut < w[1]
    )
    return ca, vn.date().isoformat()


async def _no(q: Quay, ghi_boi: str) -> tuple[str, str]:
    """Một khoản nợ ghi lúc này rồi thu lại ngay + một khoản đã huỷ lúc này."""
    async with q.pool.acquire() as conn:
        kh = await conn.fetchval(
            "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        thu = await conn.fetchval(
            "INSERT INTO cong_no (clinic_id, visit_id, clinic_patient_id, so_tien,"
            " ly_do, ghi_boi, trang_thai, thu_luc) VALUES ($1::uuid, $2::uuid,"
            " $3::uuid, 120000, 'Khách chưa mang tiền', $4::uuid, 'DA_THU', now())"
            " RETURNING id::text",
            CLINIC,
            q.visit_id,
            kh,
            ghi_boi,
        )
        huy = await conn.fetchval(
            "INSERT INTO cong_no (clinic_id, visit_id, clinic_patient_id, so_tien,"
            " ly_do, ghi_boi, trang_thai, huy_luc, huy_boi, ly_do_huy)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 50000, 'Ghi nợ thử', $4::uuid,"
            " 'HUY', now(), $4::uuid, 'Bấm nhầm') RETURNING id::text",
            CLINIC,
            q.visit_id,
            kh,
            ghi_boi,
        )
    return str(thu), str(huy)


@pytest.fixture
def ca_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def test_nhan_vien_ca_minh_ra_so_y_quan_ly(
    pool: asyncpg.Pool, ca_thuoc: None
) -> None:
    q = await tao_quay(pool)
    await _san_sang(q, so=4)
    th = await _thu_thuoc(q)
    ca, ngay = await _ca_cua(pool, th["payment_cycle_id"])
    loc = await _loc(q)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    nv = await _nguoi_vai(q, "CASHIER_THUOC")
    await _xep_ca(pool, nv, ca, loc)
    thu, huy = await _no(q, q.thu_ngan.staff_id)

    cua_toi = await BaoCaoCaCuaToiService(pool).bao_cao(identity=nv)
    quan_ly = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=ql, tu=ngay, den=ngay, ca=ca, co_so=loc
    )
    assert cua_toi["ca"]["ma"] == ca and cua_toi["co_so"] == loc
    assert (cua_toi["tu"], cua_toi["den"]) == (ngay, ngay)
    for k in GIONG_QUAN_LY:
        assert cua_toi[k] == quan_ly[k], f"lệch khối {k}"
    assert cua_toi["tong"]["thu"] > 0
    # Ẩn ở MÁY CHỦ: payload không có khối nào trong danh sách ẩn.
    for k in AN_VOI_NHAN_VIEN:
        assert k in quan_ly and k not in cua_toi, k
    assert "theo_nguoi_thu" not in cua_toi and "theo_co_so" not in cua_toi
    assert cua_toi["ca_duoc_xem"] == [
        {
            "ca": ca,
            "ten": cua_toi["ca"]["ten"],
            "co_so": loc,
            "ten_co_so": cua_toi["ten_co_so"],
        }
    ]

    # Nợ trong ca: ghi mới + thu lại (cùng khoản) + huỷ, kèm tên khách.
    no = cua_toi["no_trong_ca"]
    assert thu in {d["id"] for d in no["ghi_moi"]["ds"]}
    assert thu in {d["id"] for d in no["thu_lai"]["ds"]}
    assert huy in {d["id"] for d in no["huy"]["ds"]}
    assert huy in {d["id"] for d in no["ghi_moi"]["ds"]}
    assert thu not in {d["id"] for d in no["huy"]["ds"]}
    dong = next(d for d in no["huy"]["ds"] if d["id"] == huy)
    assert dong["khach"] == "BN thử tiền thuốc" and dong["ly_do"] == "Bấm nhầm"
    # Ca khác (báo cáo Quản lý): không có hai khoản này. Cả ngày: không có khối.
    for khac in (m for m in CAC_CA if m != ca):
        o = await BaoCaoCuoiNgayService(pool).bao_cao(
            identity=ql, tu=ngay, den=ngay, ca=khac, co_so=loc
        )
        assert thu not in {d["id"] for d in o["no_trong_ca"]["ghi_moi"]["ds"]}
    ca_ngay = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ql, tu=ngay, den=ngay)
    assert ca_ngay["no_trong_ca"] is None

    # Gửi đúng ca + cơ sở cũng ra cùng số; loại "thuốc" vẫn cắt như thường.
    lai = await BaoCaoCaCuaToiService(pool).bao_cao(
        identity=nv, ca=ca.lower(), co_so=loc, loai="thuoc"
    )
    assert lai["loai"] == "thuoc" and "theo_nguoi_thu" not in lai


async def test_ca_khac_co_so_khac_ca_rac_la_403(
    pool: asyncpg.Pool, ca_thuoc: None
) -> None:
    q = await tao_quay(pool)
    loc = await _loc(q)
    nv = await _nguoi_vai(q, "RECEPTION")
    await _xep_ca(pool, nv, "SANG", loc)
    svc = BaoCaoCaCuaToiService(pool)
    for ca, co_so in (
        ("CHIEU", None),
        ("TOI", loc),
        ("SANG", str(uuid.uuid4())),
        ("SANG", "khong-phai-uuid"),
        ("ĐÊM", None),
        ("2026-01-01", "' OR 1=1 --"),
        ("x" * 500, loc),
        ("SANG", "y" * 500),
    ):
        with pytest.raises(SafetyGateError):
            await svc.bao_cao(identity=nv, ca=ca, co_so=co_so)
    ok = await svc.bao_cao(identity=nv, ca="SANG")
    assert ok["ca"]["ma"] == "SANG" and ok["co_so"] == loc


async def test_khong_co_ca_hoac_ca_bi_tu_choi_la_403(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    loc = await _loc(q)
    svc = BaoCaoCaCuaToiService(pool)
    khong_ca = await _nguoi_vai(q, "RECEPTION")
    with pytest.raises(SafetyGateError, match="không có tên trong lịch trực"):
        await svc.bao_cao(identity=khong_ca)
    bi_tu_choi = await _nguoi_vai(q, "CASHIER")
    await _xep_ca(pool, bi_tu_choi, "FULL", loc, status="REJECTED")
    with pytest.raises(SafetyGateError):
        await svc.bao_cao(identity=bi_tu_choi)


async def test_no_co_so_khac_khong_lo_trong_ca(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    loc = await _loc(q)
    nv = await _nguoi_vai(q, "RECEPTION")
    await _xep_ca(pool, nv, "FULL", loc)
    code = f"T-BCC-{uuid.uuid4().hex[:6]}"
    khac = await pool.fetchval(
        "INSERT INTO clinic_location (clinic_id, code, name)"
        " VALUES ($1::uuid, $2, $2) RETURNING id::text",
        CLINIC,
        code,
    )
    await pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        khac,
    )
    thu, huy = await _no(q, q.thu_ngan.staff_id)
    bc = await BaoCaoCaCuaToiService(pool).bao_cao(identity=nv)
    for nhom in bc["no_trong_ca"].values():
        assert not {thu, huy} & {d["id"] for d in nhom["ds"]}


async def test_lich_truc_ngay_khac_khong_mo_bao_cao(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    nv = await _nguoi_vai(q, "RECEPTION")
    await _xep_ca(pool, nv, "FULL", await _loc(q))
    await pool.execute(
        "UPDATE work_roster SET work_date = work_date - 7, week_start = week_start - 7"
        " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
        CLINIC,
        nv.staff_id,
    )
    with pytest.raises(SafetyGateError, match="không có tên trong lịch trực"):
        await BaoCaoCaCuaToiService(pool).bao_cao(identity=nv)


async def test_ca_full_xem_du_ba_ca(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    loc = await _loc(q)
    nv = await _nguoi_vai(q, "NURSE_ULTRASOUND")
    await _xep_ca(pool, nv, "FULL", loc)
    svc = BaoCaoCaCuaToiService(pool)
    for ca in CAC_CA:
        assert (await svc.bao_cao(identity=nv, ca=ca))["ca"]["ma"] == ca
    ds = (await svc.bao_cao(identity=nv))["ca_duoc_xem"]
    assert [x["ca"] for x in ds] == list(CAC_CA)


async def test_vi_tri_chua_gan_co_so(pool: asyncpg.Pool) -> None:
    """Nhiều cơ sở → từ chối, nói rõ nhờ quản lý gắn. Một cơ sở → dùng cơ sở ấy."""
    q = await tao_quay(pool)
    nv = await _nguoi_vai(q, "RECEPTION")
    await _xep_ca(pool, nv, "SANG", None)
    so_co_so = await pool.fetchval(
        "SELECT count(*) FROM clinic_location WHERE clinic_id = $1::uuid AND is_active",
        CLINIC,
    )
    svc = BaoCaoCaCuaToiService(pool)
    if so_co_so == 1:
        assert (await svc.bao_cao(identity=nv))["ca"]["ma"] == "SANG"
    else:
        with pytest.raises(SafetyGateError, match="gắn cơ sở cho vị trí"):
            await svc.bao_cao(identity=nv)


# ── Migration thu lego Báo cáo ──────────────────────────────────────────────


class _RollbackError(Exception):
    pass


async def _cap_he_thong(conn: asyncpg.Connection, ai: StaffIdentity) -> None:
    """Dòng report.view như mở full 30/09 tạo (không người cấp)."""
    await conn.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi,"
        " tu_preset, ly_do) VALUES ($1::uuid, $2::uuid, 'report.view', 'bao_cao',"
        " $3, 'Mở full lego (Tuyền 30/09/2026)') ON CONFLICT DO NOTHING",
        CLINIC,
        ai.staff_id,
        ai.role.value,
    )


async def _co_report_view(conn: asyncpg.Connection, ai: StaffIdentity) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM v_quyen_hieu_luc WHERE clinic_id ="
            " $1::uuid AND staff_id = $2::uuid AND capability = 'report.view')",
            CLINIC,
            ai.staff_id,
        )
    )


async def test_migration_thu_report_view_giu_quan_ly_truong_ca_va_cap_tay(
    pool: asyncpg.Pool,
) -> None:
    """Chạy lại migration trên dữ liệu như prod trước khi áp (mọi người có dòng mở
    full, nhóm mẫu Lễ tân còn `bao_cao`), trong giao dịch rồi huỷ."""
    q = await tao_quay(pool)
    nv = await _nguoi_vai(q, "RECEPTION")
    tay = await _nguoi_vai(q, "CSKH")
    khac = await _nguoi_vai(q, "NURSE_ULTRASOUND")
    tc = await _nguoi_vai(q, "TRUONG_CA")
    ql = await _nguoi_vai(q, "MANAGEMENT")
    sql = MIGRATION.read_text(encoding="utf-8")
    ket: dict[str, Any] = {}
    with pytest.raises(_RollbackError):
        async with pool.acquire() as conn, conn.transaction():
            for ai in (nv, tc, ql):
                await _cap_he_thong(conn, ai)
            # Quản lý tự bật lego Báo cáo cho CSKH trên /phan-quyen.
            await conn.execute(
                "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                " tu_khoi, granted_by, ly_do) VALUES ($1::uuid, $2::uuid,"
                " 'report.view', 'bao_cao', $3::uuid, 'Bật lego bao_cao')",
                CLINIC,
                tay.staff_id,
                ql.staff_id,
            )
            # Cấp theo preset không có người cấp: không phải nguồn mở full.
            await conn.execute(
                "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                " tu_khoi, ly_do) VALUES ($1::uuid, $2::uuid, 'report.view',"
                " 'bao_cao', 'Cấp theo preset khi thêm nhân sự')",
                CLINIC,
                khac.staff_id,
            )
            await conn.execute(
                "UPDATE quyen_preset SET khoi = array_append(khoi, 'bao_cao')"
                " WHERE clinic_id = $1::uuid AND ma = 'RECEPTION'"
                "   AND NOT ('bao_cao' = ANY (khoi))",
                CLINIC,
            )
            assert await _co_report_view(conn, nv)
            await conn.execute(sql)
            ket["nv"] = await _co_report_view(conn, nv)
            ket["tay"] = await _co_report_view(conn, tay)
            ket["khac"] = await _co_report_view(conn, khac)
            ket["tc"] = await _co_report_view(conn, tc)
            ket["ql"] = await _co_report_view(conn, ql)
            ket["ly_do"] = await conn.fetchval(
                "SELECT ly_do FROM capability_grant WHERE staff_id = $1::uuid"
                " AND capability = 'report.view' AND revoked_at IS NOT NULL",
                nv.staff_id,
            )
            ket["preset"] = {
                r["ma"]: "bao_cao" in r["khoi"]
                for r in await conn.fetch(
                    "SELECT ma, khoi FROM quyen_preset WHERE clinic_id = $1::uuid"
                    " AND he_thong",
                    CLINIC,
                )
            }
            # Chạy lần hai: không lỗi, không đổi gì.
            await conn.execute(sql)
            ket["nv2"] = await _co_report_view(conn, nv)
            raise _RollbackError
    assert ket["nv"] is False, "nhân viên thường mất report.view"
    assert ket["tay"] is True, "dòng Quản lý cấp tay còn nguyên"
    assert ket["khac"] is True, "nguồn preset không người cấp còn nguyên"
    assert ket["tc"] is True and ket["ql"] is True
    assert "Mở full lego" in ket["ly_do"] and "20261010300000" in ket["ly_do"]
    co = sorted(m for m, c in ket["preset"].items() if c)
    assert co == ["MANAGEMENT", "TRUONG_CA"], co
    assert ket["nv2"] is False


async def test_hoan_tien_co_trigger_bao_tin_bao_cao_ca(pool: asyncpg.Pool) -> None:
    assert await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c"
        " ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid"
        " WHERE c.relname = 'payment_refund' AND NOT t.tgisinternal"
        " AND t.tgenabled <> 'D' AND p.proname = 'notify_row_change')"
    )
