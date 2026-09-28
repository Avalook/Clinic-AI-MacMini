"""Trợ lý bác sĩ TRỌN QUYỀN, trên Postgres thật (Tuyền chốt 29/09/2026).

"Điều dưỡng và thư ký là TRỌN QUYỀN luôn — làm việc cho bác sĩ thật sự." Ai có
quyền Bàn khám (lego `ban_kham`, hoặc lịch hôm nay ở phòng khám) làm được như
bác sĩ: bấm tiếp phiên bác sĩ đang mở, duyệt chỉ định, Hoàn tất khám thay. Chỉ
còn chặn hai BÁC SĨ THẬT giành một lượt.

Bản in kết quả: "mặc định tên bác sĩ; trong hệ thống ghi lịch sử thì mới ghi
dòng người nhập" — điều dưỡng bấm Hoàn tất phiếu, "Bác sĩ thực hiện" là bác sĩ
đứng phòng ấy hôm nay.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.permission_service import PermissionService
from tests.services.test_form_engine_db import _don_tron
from tests.services.test_luot_kham_service_db import (
    CLINIC,
    KichBan,
    _cua,
    _hanh_trinh,
    _nguoi,
    _vao_kham,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── Bàn khám ────────────────────────────────────────────────────────────────


async def _bat_lego_ban_kham(kb: KichBan, ai: StaffIdentity) -> None:
    async with kb.pool.acquire() as conn:
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    await PermissionService(kb.pool).doi_lego(
        staff_id=ai.staff_id, ma="ban_kham", bat=True, identity=ql
    )
    async with kb.pool.acquire() as conn:
        assert await can(conn, ai, "clinical.consult.finalize")


async def _phong_kham_moi(conn: asyncpg.Connection, loc: str) -> str:
    """Một phòng khám (node KHAM-*) riêng của bài kiểm — không nhận khách, để
    không lẫn vào phòng các bài khác đang chọn."""
    ma = f"T-KB-{uuid.uuid4().hex[:6]}"
    rid = await conn.fetchval(
        "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
        " accepting, sort) VALUES ($1::uuid, $2::uuid, $3, $3, 'KHAM-PHUKHOA',"
        " false, 9999) RETURNING id::text",
        CLINIC,
        loc,
        ma,
    )
    await conn.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, 'KHAM-PHUKHOA')",
        CLINIC,
        rid,
    )
    return str(rid)


async def _xep(conn: asyncpg.Connection, room_id: str, ai: StaffIdentity) -> None:
    """Xếp `ai` cả ngày hôm nay vào một vị trí mới của phòng `room_id`."""
    ma = f"T-VT-{uuid.uuid4().hex[:6]}"
    await conn.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, $2, $3::uuid)",
        CLINIC,
        ma,
        room_id,
    )
    hom_nay = await conn.fetchval(
        "SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    )
    await conn.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " VALUES ($1::uuid, $2, $3, 'FULL', $4, $5::uuid, $6, 'APPROVED')",
        CLINIC,
        hom_nay - dt.timedelta(days=hom_nay.weekday()),
        hom_nay,
        ma,
        ai.staff_id,
        ai.full_name,
    )


async def test_thu_ky_co_lego_bam_tiep_phien_bac_si_dang_mo(kb: KichBan) -> None:
    """Lỗi 29/09: thư ký có lego Bàn khám (có quyền Hoàn tất) bị coi là "bác
    sĩ" → bấm tiếp phiên bác sĩ X đang mở bị CONSULTATION_TAKEN."""
    await _bat_lego_ban_kham(kb, kb.thu_ky)
    phien = await _vao_kham(kb)
    lai = await kb.svc.start_consultation(consultation_id=phien, identity=kb.thu_ky)
    assert lai.get("already") is True


async def test_dieu_duong_xep_lich_phong_kham_bam_tiep_va_hoan_tat(
    kb: KichBan,
) -> None:
    """Điều dưỡng KHÔNG có lego, chỉ được xếp lịch hôm nay vào phòng khám →
    có quyền Bàn khám theo lịch → bấm tiếp phiên bác sĩ và Hoàn tất khám thay.
    Phiên vẫn ghi bác sĩ của phiên; người bấm ở `completed_by`."""
    async with kb.pool.acquire() as conn:
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.dieu_duong)
        assert await can(conn, kb.dieu_duong, "clinical.consult.finalize")
    phien = await _vao_kham(kb)
    lai = await kb.svc.start_consultation(consultation_id=phien, identity=kb.dieu_duong)
    assert lai.get("already") is True
    kq = await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="NO_SERVICES",
        requirements=None,
        identity=kb.dieu_duong,
    )
    assert kq["ok"] is True
    async with kb.pool.acquire() as conn:
        c = await conn.fetchrow(
            "SELECT status, doctor_staff_id::text AS bs, completed_by::text AS boi"
            " FROM consultation WHERE id = $1::uuid",
            phien,
        )
    assert c["status"] == "completed"
    assert c["bs"] == kb.bac_si.staff_id, "phiên vẫn ghi bác sĩ của phiên"
    assert c["boi"] == kb.dieu_duong.staff_id, "người bấm ghi ở completed_by"


async def test_thu_ky_co_lego_duyet_chi_dinh_va_hoan_tat_thay(kb: KichBan) -> None:
    await _bat_lego_ban_kham(kb, kb.thu_ky)
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.thu_ky,
    )
    assert len(duyet["order_ids"]) == 1
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": duyet["order_ids"][0], "need": "PERFORMED"}],
        identity=kb.thu_ky,
    )


async def test_thu_ky_mo_phien_truoc_khong_thanh_bac_si(kb: KichBan) -> None:
    """Thư ký có quyền Hoàn tất bấm Bắt đầu trên lượt CHƯA có bác sĩ → phiên
    không ghi thư ký là bác sĩ; bác sĩ thật bấm tiếp → phiên ghi bác sĩ ấy."""
    await _bat_lego_ban_kham(kb, kb.thu_ky)
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
    await kb.svc.start_consultation(consultation_id=phien, identity=kb.thu_ky)

    async def bac_si_phien() -> str | None:
        async with kb.pool.acquire() as conn:
            bs: str | None = await conn.fetchval(
                "SELECT doctor_staff_id::text FROM consultation WHERE id = $1::uuid",
                phien,
            )
        return bs

    assert await bac_si_phien() is None
    lai = await kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si)
    assert lai.get("already") is True
    assert await bac_si_phien() == kb.bac_si.staff_id


async def test_hai_bac_si_van_khong_gianh_mot_phien(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si_2)
    assert e.value.error_code == "CONSULTATION_TAKEN"
    with pytest.raises(SafetyGateError, match="Chỉ bác sĩ phụ trách"):
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="NO_SERVICES",
            requirements=None,
            identity=kb.bac_si_2,
        )


# ── Phiếu kết quả: "Bác sĩ thực hiện" mặc định = bác sĩ đứng phòng ──────────


async def _phieu_trong_phong(kb: KichBan) -> tuple[str, str, int]:
    """Một chỉ định ở phòng dịch vụ riêng + phiếu KQ đã mở. Trả (phòng, phiếu,
    revision)."""
    async with kb.pool.acquire() as conn:
        order_id = await _don_tron(conn, kb.bac_si)
        ma = f"T-DV-{uuid.uuid4().hex[:6]}"
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
    phieu = await FormEngineService(kb.pool).mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=kb.dieu_duong
    )
    return str(phong), phieu["id"], int(phieu["revision"])


async def _thuc_hien(kb: KichBan, phieu_id: str) -> tuple[str | None, str | None]:
    async with kb.pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT thuc_hien_boi::text AS lam, hoan_tat_boi::text AS bam"
            " FROM form_instance WHERE id = $1::uuid",
            phieu_id,
        )
    return r["lam"], r["bam"]


async def test_dieu_duong_hoan_tat_phieu_bac_si_dung_phong_dung_ten(
    kb: KichBan,
) -> None:
    phong, phieu, rev = await _phieu_trong_phong(kb)
    async with kb.pool.acquire() as conn:
        await _xep(conn, phong, kb.bs_sieu_am)
        await _xep(conn, phong, kb.dieu_duong)
    await FormEngineService(kb.pool).hoan_tat(
        phieu_id=phieu, expected_revision=rev, identity=kb.dieu_duong
    )
    lam, bam = await _thuc_hien(kb, phieu)
    assert lam == kb.bs_sieu_am.staff_id, "Bác sĩ thực hiện = bác sĩ đứng phòng"
    assert bam == kb.dieu_duong.staff_id, "người bấm vẫn ở lịch sử (hoan_tat_boi)"

    # Bản in: tên dưới "Bác sĩ thực hiện" là bác sĩ, không phải người bấm.
    in_ = await FormEngineService(kb.pool).in_ket_qua(
        service_order_id=await kb.pool.fetchval(
            "SELECT service_order_id::text FROM form_instance WHERE id = $1::uuid",
            phieu,
        ),
        identity=kb.bac_si,
    )
    ten_bs = await kb.pool.fetchval(
        "SELECT full_name FROM staff WHERE id = $1::uuid", kb.bs_sieu_am.staff_id
    )
    assert [p["thuc_hien"] for p in in_["phieu"]] == [ten_bs]


async def test_phong_khong_co_bac_si_thi_giu_nguoi_bam(kb: KichBan) -> None:
    phong, phieu, rev = await _phieu_trong_phong(kb)
    async with kb.pool.acquire() as conn:
        await _xep(conn, phong, kb.dieu_duong)
    await FormEngineService(kb.pool).hoan_tat(
        phieu_id=phieu, expected_revision=rev, identity=kb.dieu_duong
    )
    assert await _thuc_hien(kb, phieu) == (
        kb.dieu_duong.staff_id,
        kb.dieu_duong.staff_id,
    )


async def test_bac_si_bam_hoan_tat_la_chinh_bac_si(kb: KichBan) -> None:
    phong, phieu, rev = await _phieu_trong_phong(kb)
    async with kb.pool.acquire() as conn:
        await _xep(conn, phong, kb.bs_sieu_am)
    await FormEngineService(kb.pool).hoan_tat(
        phieu_id=phieu, expected_revision=rev, identity=kb.bac_si
    )
    lam, _ = await _thuc_hien(kb, phieu)
    assert lam == kb.bac_si.staff_id


async def test_chon_nguoi_thuc_hien_thi_giu_nguoi_duoc_chon(kb: KichBan) -> None:
    phong, phieu, rev = await _phieu_trong_phong(kb)
    async with kb.pool.acquire() as conn:
        await _xep(conn, phong, kb.bs_sieu_am)
    await FormEngineService(kb.pool).hoan_tat(
        phieu_id=phieu,
        expected_revision=rev,
        identity=kb.dieu_duong,
        thuc_hien_boi=kb.bac_si_2.staff_id,
    )
    lam, _ = await _thuc_hien(kb, phieu)
    assert lam == kb.bac_si_2.staff_id
