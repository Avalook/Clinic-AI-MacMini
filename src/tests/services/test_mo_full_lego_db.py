"""MỞ FULL LEGO cho mọi nhân sự nội bộ, trên Postgres thật (Tuyền 30/09/2026).

"Ai ở chỗ nào cũng thanh toán được, không có trong lịch cũng thao tác được" —
mọi vai nội bộ có mọi khối, trừ bốn khối chỉ Quản lý giữ (Phân quyền, Nhân sự,
Cài đặt, Danh mục & biểu mẫu). Migration 20260930900000.

Điều PHẢI GIỮ dù mở: ai đủ lego Bàn khám được suy ra vai DOCTOR ở cửa cũ, nhưng
tên KÝ trên bản in và "bác sĩ của phiên" chỉ là tài khoản có
`clinic_membership.role` DOCTOR / ULTRASOUND_DOCTOR — lễ tân bấm Hoàn tất thì
bản in KHÔNG ký tên lễ tân.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity, doc_vai_theo_lego
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import KHOI_CHI_QUAN_LY, QUYEN
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.xem_luot_service import XemLuotService
from tests.services.test_form_engine_db import _don_tron
from tests.services.test_luot_kham_service_db import (
    CLINIC,
    KichBan,
    _cua,
    _hanh_trinh,
    _nguoi,
    _vao_kham,
)
from tests.services.test_tro_ly_bac_si_tron_quyen_db import _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260930900000_mo_full_lego.sql"
)

VAI_NOI_BO = (
    "RECEPTION",
    "CASHIER",
    "CASHIER_DV",
    "CASHIER_THUOC",
    "CSKH",
    "PHARMACIST",
    "TRUONG_CA",
    "DOCTOR",
    "ULTRASOUND_DOCTOR",
    "NURSE_ULTRASOUND",
    "TKYK",
)

#: Mẫu quyền mọi người phải có sau khi mở (thu tiền DV + thuốc, khám, hoàn tất,
#: duyệt KQ, kho, điều phối, bảng giá, báo cáo…).
PHAI_CO = (
    "payment.service.collect",
    "payment.medicine.collect",
    "reception.checkin.perform",
    "clinical.consult.perform",
    "clinical.consult.finalize",
    "result.review.approve",
    "service.execute.start",
    "pharmacy.dispense",
    "dispatch.manage",
    "price.service.manage",
    "report.view",
    "booking.manage",
)
CHI_QUAN_LY = tuple(q.ma for q in QUYEN.values() if q.khoi in KHOI_CHI_QUAN_LY)


async def _ten(pool: asyncpg.Pool, ai: StaffIdentity) -> str:
    return str(
        await pool.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", ai.staff_id
        )
    )


async def _nhu_prod(pool: asyncpg.Pool, ai: StaffIdentity) -> StaffIdentity:
    """Danh tính như `_resolve_identity` dựng trên prod: kèm vai suy từ lego."""
    lego = await doc_vai_theo_lego(pool, CLINIC, ai.staff_id, ai.role)
    return replace(ai, vai_theo_lego=lego)


# ── Bộ quyền ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("vai", VAI_NOI_BO)
async def test_moi_vai_noi_bo_du_lego_tru_bon_khoi_quan_ly(
    kb: KichBan, vai: str
) -> None:
    async with kb.pool.acquire() as conn:
        ai = await _nguoi(conn, kb.location_id, vai)
        for q in PHAI_CO:
            assert await can(conn, ai, q), f"{vai} thiếu {q}"
        for q in CHI_QUAN_LY:
            assert not await can(conn, ai, q), f"{vai} không được có {q}"


async def test_quan_ly_van_giu_bon_khoi_doi_tac_chi_co_doi_tac(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
        dt = await _nguoi(conn, kb.location_id, "PARTNER")
        for q in CHI_QUAN_LY:
            assert await can(conn, ql, q)
        assert await can(conn, dt, "partner.work")
        for q in PHAI_CO:
            assert not await can(conn, dt, q), f"đối tác không được có {q}"


# ── Migration trên dữ liệu có sẵn (diễn tập, rollback) ──────────────────────


class _RollbackError(Exception):
    pass


async def test_migration_cap_bu_nguoi_cu_va_tat_quyen_theo_lich(kb: KichBan) -> None:
    """Chạy lại migration trên một tài khoản CŨ đã bị thu hết quyền + dây
    `quyen_theo_lich` đang BẬT: cấp lại đủ (ly_do để thu hồi được), không đụng
    bốn khối Quản lý, dây về TẮT. Làm trong giao dịch rồi huỷ — DB thử dùng
    chung giữa các bài."""
    sql = MIGRATION.read_text(encoding="utf-8")
    ket_qua: dict[str, Any] = {}
    with pytest.raises(_RollbackError):
        async with kb.pool.acquire() as conn, conn.transaction():
            ai = await _nguoi(conn, kb.location_id, "CASHIER_THUOC")
            await conn.execute(
                "UPDATE capability_grant SET revoked_at = now(),"
                " revoked_by = staff_id WHERE staff_id = $1::uuid"
                " AND revoked_at IS NULL",
                ai.staff_id,
            )
            await conn.execute(
                "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
                " VALUES ($1::uuid, 'quyen_theo_lich', 'true'::jsonb)"
                " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = 'true'::jsonb",
                CLINIC,
            )
            await conn.execute(sql)
            ket_qua["khoi"] = {
                r["tu_khoi"]
                for r in await conn.fetch(
                    "SELECT tu_khoi FROM capability_grant WHERE staff_id = $1::uuid"
                    " AND revoked_at IS NULL AND scope_type = 'CLINIC'"
                    " AND ly_do = 'Mở full lego (Tuyền 30/09/2026)'",
                    ai.staff_id,
                )
            }
            ket_qua["day"] = await conn.fetchval(
                "SELECT gia_tri FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
                " AND ma = 'quyen_theo_lich'",
                CLINIC,
            )
            # Chạy lần hai không lỗi, không nhân đôi dòng.
            await conn.execute(sql)
            ket_qua["so_dong"] = await conn.fetchval(
                "SELECT count(*) FROM capability_grant WHERE staff_id = $1::uuid"
                " AND revoked_at IS NULL",
                ai.staff_id,
            )
            raise _RollbackError
    so_khoi_mo = {q.khoi for q in QUYEN.values()} - KHOI_CHI_QUAN_LY
    assert ket_qua["khoi"] == so_khoi_mo
    assert ket_qua["day"] in (False, "false")
    assert ket_qua["so_dong"] == sum(
        1 for q in QUYEN.values() if q.khoi not in KHOI_CHI_QUAN_LY
    )


# ── Tên ký / bác sĩ của phiên: KHÔNG đi theo lego ───────────────────────────


async def test_le_tan_du_lego_hoan_tat_kham_ban_in_ky_ten_bac_si(kb: KichBan) -> None:
    le_tan = await _nhu_prod(kb.pool, kb.le_tan)
    assert le_tan.vai_theo_lego is not None
    # Hệ quả đã chấp nhận: đủ lego Bàn khám → vai DOCTOR ở các cửa cũ.
    assert le_tan.co_vai({ClinicRole.DOCTOR})
    async with kb.pool.acquire() as conn:
        assert await can(conn, le_tan, "clinical.consult.finalize")

    phien = await _vao_kham(kb)
    lai = await kb.svc.start_consultation(consultation_id=phien, identity=le_tan)
    assert lai.get("already") is True
    kq = await kb.svc.complete_consultation(
        consultation_id=phien, outcome="NO_SERVICES", requirements=None, identity=le_tan
    )
    assert kq["ok"] is True
    async with kb.pool.acquire() as conn:
        c = await conn.fetchrow(
            "SELECT c.doctor_staff_id::text AS bs, c.completed_by::text AS boi,"
            "       v.attending_doctor_id::text AS bs_luot"
            "  FROM consultation c JOIN visit v ON v.visit_id = c.visit_id"
            " WHERE c.id = $1::uuid",
            phien,
        )
    assert c["bs"] == kb.bac_si.staff_id, "bác sĩ của phiên vẫn là bác sĩ"
    assert c["bs_luot"] == kb.bac_si.staff_id
    assert c["boi"] == le_tan.staff_id, "người bấm chỉ ở lịch sử"

    # Bản in / xem lượt: người ký là bác sĩ, lễ tân chỉ là người bấm.
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET finalized_by = $2::uuid WHERE visit_id = $1::uuid",
            kb.visit_id,
            le_tan.staff_id,
        )
    doc = await XemLuotService(kb.pool).doc(visit_id=kb.visit_id, identity=le_tan)
    ten_le_tan = await _ten(kb.pool, le_tan)
    assert _tim(doc, "nguoi_ky") == [await _ten(kb.pool, kb.bac_si)]
    assert ten_le_tan not in _tim(doc, "nguoi_ky")
    assert _tim(doc, "nguoi_bam_ky") == [ten_le_tan]


async def test_le_tan_mo_phien_luot_chua_co_bac_si_khong_thanh_bac_si(
    kb: KichBan,
) -> None:
    """Lượt CHƯA có bác sĩ, lễ tân đủ lego bấm Bắt đầu rồi Hoàn tất → phiên và
    lượt KHÔNG ghi lễ tân là bác sĩ; chỗ ký để trống thay vì tên lễ tân."""
    le_tan = await _nhu_prod(kb.pool, kb.le_tan)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = NULL WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    phien = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["phien"][0]["id"]
    await kb.svc.start_consultation(consultation_id=phien, identity=le_tan)
    await kb.svc.complete_consultation(
        consultation_id=phien, outcome="NO_SERVICES", requirements=None, identity=le_tan
    )
    async with kb.pool.acquire() as conn:
        c = await conn.fetchrow(
            "SELECT c.doctor_staff_id::text AS bs,"
            "       v.attending_doctor_id::text AS bs_luot"
            "  FROM consultation c JOIN visit v ON v.visit_id = c.visit_id"
            " WHERE c.id = $1::uuid",
            phien,
        )
    assert c["bs"] is None and c["bs_luot"] is None
    doc = await XemLuotService(kb.pool).doc(visit_id=kb.visit_id, identity=le_tan)
    assert await _ten(kb.pool, le_tan) not in _tim(doc, "nguoi_ky")


async def test_le_tan_hoan_tat_phieu_ket_qua_ban_in_ky_bac_si_dung_phong(
    kb: KichBan,
) -> None:
    le_tan = await _nhu_prod(kb.pool, kb.le_tan)
    async with kb.pool.acquire() as conn:
        order_id = await _don_tron(conn, kb.bac_si)
        ma = f"T-MF-{uuid.uuid4().hex[:6]}"
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $3, 'DICHVU-SIEUAM',"
            " false, 9999) RETURNING id::text",
            CLINIC,
            kb.location_id,
            ma,
        )
        await conn.execute(
            "UPDATE service_order SET room_id = $2::uuid WHERE id = $1::uuid",
            order_id,
            phong,
        )
        await _xep(conn, str(phong), kb.bs_sieu_am)
    svc = FormEngineService(kb.pool)
    p = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=le_tan
    )
    await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=p["revision"], identity=le_tan
    )

    ban = await svc.in_ket_qua(service_order_id=order_id, identity=le_tan)
    ten_le_tan = await _ten(kb.pool, le_tan)
    assert [x["thuc_hien"] for x in ban["phieu"]] == [
        await _ten(kb.pool, kb.bs_sieu_am)
    ]
    assert ban["bac_si_thuc_hien"] != ten_le_tan
    assert ban["bac_si_chi_dinh"] != ten_le_tan
    # Người bấm vẫn ở lịch sử.
    assert [x["hoan_tat_boi"] for x in ban["phieu"]] == [ten_le_tan]


def _tim(d: Any, khoa: str) -> list[Any]:
    if isinstance(d, dict):
        return (
            [d[khoa]] if khoa in d else [x for v in d.values() for x in _tim(v, khoa)]
        )
    if isinstance(d, list):
        return [x for v in d for x in _tim(v, khoa)]
    return []
