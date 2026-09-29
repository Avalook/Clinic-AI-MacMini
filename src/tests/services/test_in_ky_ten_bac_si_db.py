"""Mọi phiếu IN ký TÊN BÁC SĨ — trên Postgres thật (Tuyền 29/09/2026).

"Mọi phiếu in ra ký tên bác sĩ, kể cả khi điều dưỡng / thư ký thao tác hộ;
người nhập chỉ ở lịch sử. KHÔNG BAO GIỜ in tên người không phải bác sĩ ở chỗ
ký / 'bác sĩ'." Không tìm được bác sĩ → chỗ ký để TRỐNG.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bac_si_ky import bac_si_chi_dinh_hien_thi
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.service_selection_service import _CHO_QUYET_SQL
from clinicai.services.xem_luot_service import XemLuotService
from tests.services.test_form_engine_db import _don_tron
from tests.services.test_luot_kham_service_db import CLINIC, KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ten(pool: asyncpg.Pool, ai: StaffIdentity) -> str:
    return str(
        await pool.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", ai.staff_id
        )
    )


async def _chi_dinh_trong_phong(
    kb: KichBan, nguoi_ghi: StaffIdentity
) -> tuple[str, str]:
    """Chỉ định do `nguoi_ghi` ghi, ở một phòng siêu âm riêng; lượt KHÔNG có bác
    sĩ chính, không lịch hẹn. Trả (chỉ định, phòng)."""
    async with kb.pool.acquire() as conn:
        order_id = await _don_tron(conn, nguoi_ghi)
        ma = f"T-IK-{uuid.uuid4().hex[:6]}"
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
    return order_id, str(phong)


async def _xep_ngay(
    conn: asyncpg.Connection, room_id: str, ai: StaffIdentity, ngay: dt.date
) -> None:
    """Xếp `ai` ca FULL ngày `ngay` vào một vị trí mới của phòng `room_id`."""
    ma = f"T-VT-{uuid.uuid4().hex[:6]}"
    await conn.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, $2, $3::uuid)",
        CLINIC,
        ma,
        room_id,
    )
    await conn.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " VALUES ($1::uuid, $2, $3, 'FULL', $4, $5::uuid, $6, 'APPROVED')",
        CLINIC,
        ngay - dt.timedelta(days=ngay.weekday()),
        ngay,
        ma,
        ai.staff_id,
        ai.full_name,
    )


async def _hom_nay(conn: asyncpg.Connection) -> dt.date:
    d = await conn.fetchval("SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date")
    assert isinstance(d, dt.date)
    return d


async def _dd_hoan_tat(kb: KichBan, order_id: str) -> str:
    svc = FormEngineService(kb.pool)
    p = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=kb.dieu_duong
    )
    await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=p["revision"], identity=kb.dieu_duong
    )
    return str(p["id"])


async def _in(kb: KichBan, order_id: str) -> dict[str, Any]:
    return await FormEngineService(kb.pool).in_ket_qua(
        service_order_id=order_id, identity=kb.bac_si
    )


async def test_dd_hoan_tat_luot_khong_co_bac_si_thi_cho_ky_trong(kb: KichBan) -> None:
    order_id, phong = await _chi_dinh_trong_phong(kb, kb.dieu_duong)
    async with kb.pool.acquire() as conn:
        await _xep_ngay(conn, phong, kb.dieu_duong, await _hom_nay(conn))
    await _dd_hoan_tat(kb, order_id)

    ban = await _in(kb, order_id)
    ten_dd = await _ten(kb.pool, kb.dieu_duong)
    assert [p["thuc_hien"] for p in ban["phieu"]] == [None], "chỗ ký để TRỐNG"
    assert ban["bac_si_thuc_hien"] is None
    assert ban["bac_si_chi_dinh"] is None
    # Người bấm vẫn ở lịch sử, không ở chỗ ký.
    assert [p["hoan_tat_boi"] for p in ban["phieu"]] == [ten_dd]


async def test_chi_co_anh_do_dd_tai_thi_nguoi_thuc_hien_la_bac_si(kb: KichBan) -> None:
    order_id, phong = await _chi_dinh_trong_phong(kb, kb.dieu_duong)
    async with kb.pool.acquire() as conn:
        await _xep_ngay(conn, phong, kb.bs_sieu_am, await _hom_nay(conn))
        await conn.execute(
            "INSERT INTO service_execution_attempt (clinic_id, service_order_id,"
            " attempt_no, room_id_snapshot, routing_revision_snapshot, status,"
            " started_by, started_at, completed_by, completed_at)"
            " VALUES ($1::uuid, $2::uuid, 1, $3::uuid, 0, 'COMPLETED', $4::uuid,"
            " now() - interval '10 minutes', $4::uuid, now())",
            CLINIC,
            order_id,
            phong,
            kb.dieu_duong.staff_id,
        )
        benh_nhan = await conn.fetchval(
            "SELECT v.clinic_patient_id::text FROM service_order o"
            " JOIN visit v ON v.visit_id = o.visit_id WHERE o.id = $1::uuid",
            order_id,
        )
        await conn.execute(
            "INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, service_order_id,"
            " khoa, ten_hien_thi, loai_tep, mime, so_byte, sha256,"
            " tai_len_boi_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'anh.jpg', 'ANH',"
            " 'image/jpeg', 10, repeat('0', 64), $5::uuid)",
            CLINIC,
            benh_nhan,
            order_id,
            f"{CLINIC}/ket-qua/{benh_nhan}/{uuid.uuid4().hex}.jpg",
            kb.dieu_duong.staff_id,
        )

    ban = await _in(kb, order_id)
    assert ban["phieu"] == [] and len(ban["anh"]) == 1
    assert ban["bac_si_thuc_hien"] == await _ten(kb.pool, kb.bs_sieu_am)
    # Người làm (điều dưỡng) chỉ còn là dữ liệu giờ làm — màn in không ký tên ấy.
    assert ban["gio_lam"]["nguoi_lam"] == await _ten(kb.pool, kb.dieu_duong)


async def test_thu_ky_chi_dinh_thi_bs_chi_dinh_la_bac_si(kb: KichBan) -> None:
    order_id, _ = await _chi_dinh_trong_phong(kb, kb.thu_ky)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_order SET authorized_by = $2::uuid WHERE id = $1::uuid",
            order_id,
            kb.thu_ky.staff_id,
        )
        vid = await conn.fetchval(
            "UPDATE visit v SET attending_doctor_id = $2::uuid FROM service_order o"
            " WHERE o.id = $1::uuid AND v.visit_id = o.visit_id"
            " RETURNING v.visit_id::text",
            order_id,
            kb.bac_si.staff_id,
        )
        bs = await bac_si_chi_dinh_hien_thi(conn, CLINIC, order_id)
        quay = [
            r
            for r in await conn.fetch(_CHO_QUYET_SQL, CLINIC, [vid])
            if r["id"] == order_id
        ]
    ten_bs = await _ten(kb.pool, kb.bac_si)
    assert bs is not None and bs.ten == ten_bs
    assert (await _in(kb, order_id))["bac_si_chi_dinh"] == ten_bs
    # Quầy thu: nhãn "bác sĩ chỉ định" là bác sĩ; thư ký chỉ là người bấm.
    assert [(r["bac_si_chi_dinh"], r["nguoi_bam_chi_dinh"]) for r in quay] == [
        (ten_bs, await _ten(kb.pool, kb.thu_ky))
    ]


async def test_in_lai_phieu_hom_truoc_ra_bac_si_hom_lam(kb: KichBan) -> None:
    order_id, phong = await _chi_dinh_trong_phong(kb, kb.dieu_duong)
    phieu = await _dd_hoan_tat(kb, order_id)
    async with kb.pool.acquire() as conn:
        hom_nay = await _hom_nay(conn)
        hom_qua = hom_nay - dt.timedelta(days=1)
        await _xep_ngay(conn, phong, kb.bac_si_2, hom_qua)
        await _xep_ngay(conn, phong, kb.bs_sieu_am, hom_nay)
        # Phiếu cũ: hoàn tất 10:00 hôm qua, còn đứng tên điều dưỡng.
        await conn.execute(
            "UPDATE form_instance SET hoan_tat_luc = $2, thuc_hien_boi = $3::uuid"
            " WHERE id = $1::uuid",
            phieu,
            dt.datetime.combine(hom_qua, dt.time(10, 0), tzinfo=CLINIC_TZ),
            kb.dieu_duong.staff_id,
        )

    ban = await _in(kb, order_id)
    assert [p["thuc_hien"] for p in ban["phieu"]] == [
        await _ten(kb.pool, kb.bac_si_2)
    ], "bác sĩ đứng phòng HÔM LÀM, không phải bác sĩ trực hôm in"


def _tim(d: Any, khoa: str) -> list[Any]:
    if isinstance(d, dict):
        return (
            [d[khoa]] if khoa in d else [x for v in d.values() for x in _tim(v, khoa)]
        )
    if isinstance(d, list):
        return [x for v in d for x in _tim(v, khoa)]
    return []


async def test_xem_luot_nguoi_ky_la_bac_si_nguoi_bam_tach_rieng(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
            " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
            kb.visit_id,
            kb.thu_ky.staff_id,
        )
    doc = await XemLuotService(kb.pool).doc(visit_id=kb.visit_id, identity=kb.bac_si)
    assert _tim(doc, "nguoi_ky") == [await _ten(kb.pool, kb.bac_si)]
    assert _tim(doc, "nguoi_bam_ky") == [await _ten(kb.pool, kb.thu_ky)]
