"""Phòng · tầng · vị trí theo bảng lịch làm việc Tuyền gửi (tuần 28/09–04/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55575/postgres \\
        poetry run pytest src/tests/services/test_phong_theo_bang_lich_db.py

Chạy lại chính migration 20261001200000 lên DB thử sau khi dựng lại trạng thái
GIỐNG PROD 30/09 (tên cũ "Kho thuốc" Tầng 1, "Phòng siêu âm 1" Tầng 2 còn bật,
vị trí T1_SA_* ở phòng siêu âm 1, Điều dưỡng Bio ở phòng Sản…) kèm một chỉ định
siêu âm CÒN MỞ xếp ở phòng siêu âm 1 — đúng đường migration đi lên prod.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.identity import vi_tri_hom_nay
from tests.services.test_phong_la_tai_nguyen_db import CLINIC, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase/migrations/20261001200000_phong_theo_bang_lich.sql"
)

# Trạng thái prod 30/09 (SELECT trên prod trước khi viết migration).
PHONG_CU = {
    "KN-TIEPDON": ("Quầy lễ tân", "Tầng 1", 10),
    "KN-QUAYTHUOC": ("Kho thuốc", "Tầng 1", 30),
    "KN-NOITIET": ("Phòng bác sĩ chính", "Tầng 1", 50),
    "KN-SA-T1": ("Phòng siêu âm 1", "Tầng 2", 60),
    "KN-SA1": ("Phòng siêu âm 2", "Tầng 2", 70),
    "KN-THUTHUAT": ("Phòng thủ thuật 1", "Tầng 3", 80),
    "KN-TTNG": ("Phòng thủ thuật 2", "Tầng 3", 90),
    "KN-SANCHAU": ("Phòng Sàn chậu", "Tầng 3", 92),
    "KN-SAN-BIO": ("Phòng Sản - Biofeedback", "Tầng 3", 94),
}
VI_TRI_CU = {
    # code: (ten, ten_ngan, tang, phong, mã phòng)
    "T1_SA_BS": ("BS siêu âm 1", "BS", "Tầng 1", "Phòng Siêu âm", "KN-SA-T1"),
    "T1_SA_DD": (
        "Điều dưỡng siêu âm 1",
        "Điều dưỡng",
        "Tầng 1",
        "Phòng Siêu âm",
        "KN-SA-T1",
    ),
    "T1_SA_TK": ("Thư ký siêu âm 1", "Thư ký", "Tầng 1", "Phòng Siêu âm", "KN-SA-T1"),
    "T4_SA_BS1": ("BS siêu âm 2", "BS 1", "Tầng 4", "Phòng siêu âm", "KN-SA1"),
    "T4_BIO_DD": (
        "Điều dưỡng Bio",
        "",
        "Tầng 4",
        "Phòng Sản - Biofeedback",
        "KN-SAN-BIO",
    ),
    "T1_TT_BS": ("BS thủ thuật", "BS", "Tầng 1", "Phòng thủ thuật", "KN-THUTHUAT"),
}


async def _phong(conn: asyncpg.Connection, code: str) -> str:
    rid = await conn.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid AND code = $2",
        CLINIC,
        code,
    )
    assert rid, f"DB thử thiếu phòng {code}"
    return str(rid)


async def _dung_nhu_prod(conn: asyncpg.Connection) -> None:
    for code, (ten, tang, sort) in PHONG_CU.items():
        await conn.execute(
            "UPDATE clinic_room SET name = $3, floor = $4, sort = $5,"
            " is_active = true, accepting = true, show_on_tv = true"
            " WHERE clinic_id = $1::uuid AND code = $2",
            CLINIC,
            code,
            ten,
            tang,
            sort,
        )
    for code, (ten, ngan, tang, phong, ma_phong) in VI_TRI_CU.items():
        await conn.execute(
            "UPDATE vi_tri_lam_viec SET ten = $3, ten_ngan = NULLIF($4, ''),"
            " tang = $5, phong = $6, room_id = $7::uuid"
            " WHERE clinic_id = $1::uuid AND code = $2",
            CLINIC,
            code,
            ten,
            ngan,
            tang,
            phong,
            await _phong(conn, ma_phong),
        )
    # Phòng cũ có một node phòng giữ lại chưa có — gộp phải chép sang.
    await conn.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, 'DICHVU-LAYMAU-MAU')"
        " ON CONFLICT DO NOTHING",
        CLINIC,
        await _phong(conn, "KN-SA-T1"),
    )
    await conn.execute(
        "DELETE FROM clinic_room_node WHERE room_id = $1::uuid"
        " AND node_code = 'DICHVU-LAYMAU-MAU'",
        await _phong(conn, "KN-SA1"),
    )
    # Kỹ năng như prod: Phụ SA trỏ cả hai phòng siêu âm, Bio trỏ phòng Sản.
    for ma, codes in (("phu_sa", ["KN-SA-T1", "KN-SA1"]), ("bio", ["KN-SAN-BIO"])):
        await conn.execute(
            "INSERT INTO ky_nang (clinic_id, ma, ten, lego, phong_ids)"
            " VALUES ($1::uuid, $2, $2, '{phong}', $3::uuid[])"
            " ON CONFLICT (clinic_id, ma) DO UPDATE SET phong_ids = EXCLUDED.phong_ids",
            CLINIC,
            ma,
            [await _phong(conn, c) for c in codes],
        )


async def _chi_dinh(
    conn: asyncpg.Connection, room: str, *, xong: bool
) -> tuple[str, str, str]:
    """Một chỉ định siêu âm xếp ở `room` (+ hàng chờ ROOM).

    Trả (visit, order, queue)."""
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ('BS gộp phòng', 'DOCTOR', $1::uuid, true)"
        " RETURNING id::text",
        loc,
    )
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN gộp phòng', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"GP-{uuid.uuid4().hex[:10]}",
        loc,
    )
    vid = await conn.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
        " attending_doctor_id, checked_in_at, current_room_id)"
        " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', $3::uuid, now(), $4::uuid)"
        " RETURNING visit_id::text",
        CLINIC,
        pid,
        sid,
        room,
    )
    con = await conn.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id, started_by, started_at)"
        " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
        " $3::uuid, now()) RETURNING id::text",
        CLINIC,
        vid,
        sid,
    )
    oid = await conn.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, recorded_by,"
        " authorized_by, authorized_at, selection_status, routing_status,"
        " room_id, phong_du_kien_id, routing_revision, execution_status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, 'SA-GOP', 'Siêu âm gộp phòng',"
        " 'DICHVU-SIEUAM', $6, $4::uuid, $4::uuid, now(), 'SELECTED', 'ASSIGNED',"
        " $5::uuid, $5::uuid, 1, $7) RETURNING id::text",
        CLINIC,
        vid,
        con,
        sid,
        room,
        "performed" if xong else "assigned",
        "COMPLETED" if xong else "PENDING",
    )
    qid = await conn.fetchval(
        "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
        " ref_id, status, eligible_at, done_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
        " $3::uuid, 'SERVICE', $4::uuid, $5, now(), $6) RETURNING id::text",
        CLINIC,
        vid,
        room,
        oid,
        "done" if xong else "waiting",
        datetime.now(UTC) if xong else None,
    )
    return str(vid), str(oid), str(qid)


async def _don_dep(conn: asyncpg.Connection, *ids: tuple[str, str, str]) -> None:
    """Không để lại khách chờ ở phòng siêu âm thật cho các bài kiểm khác."""
    for vid, oid, qid in ids:
        await conn.execute(
            "UPDATE queue_entry SET status = 'cancelled' WHERE id = $1::uuid", qid
        )
        await conn.execute(
            "UPDATE service_order SET exec_status = 'cancelled',"
            " execution_status = 'CANCELLED' WHERE id = $1::uuid"
            " AND exec_status <> 'performed'",
            oid,
        )
        await conn.execute(
            "UPDATE visit SET closed_at = now(), current_room_id = NULL"
            " WHERE visit_id = $1::uuid",
            vid,
        )
    await conn.execute(
        "DELETE FROM ky_nang WHERE clinic_id = $1::uuid AND ma IN ('phu_sa', 'bio')",
        CLINIC,
    )


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="QL bảng lịch",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=CLINIC,
        location_id="",
        location_name="",
    )


async def test_phong_vi_tri_theo_bang_va_gop_hai_phong_sieu_am(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        await _dung_nhu_prod(conn)
        sa_cu = await _phong(conn, "KN-SA-T1")
        sa_moi = await _phong(conn, "KN-SA1")
        mo = await _chi_dinh(conn, sa_cu, xong=False)
        da_xong = await _chi_dinh(conn, sa_cu, xong=True)
        truoc = await conn.fetchrow(
            "SELECT routing_revision, version FROM service_order WHERE id = $1::uuid",
            mo[1],
        )
        assert truoc is not None
        # Tenant KHÁC không có bộ phòng KN-* — migration không được đụng.
        khac = await conn.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"BL-{uuid.uuid4().hex[:8]}",
        )
        await conn.execute(
            "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, tang, sort)"
            " VALUES ($1::uuid, 'T1_SA_BS', 'BS siêu âm khác', 'Tầng 9', 1)",
            khac,
        )
    try:
        await pool.execute(MIGRATION.read_text(encoding="utf-8"))
        await pool.execute(MIGRATION.read_text(encoding="utf-8"))  # chạy lại được

        phong = {
            r["code"]: r
            for r in await pool.fetch(
                "SELECT code, name, floor, sort, is_active, accepting FROM clinic_room"
                " WHERE clinic_id = $1::uuid AND code LIKE 'KN-%'",
                CLINIC,
            )
        }
        for code, ten, tang in (
            ("KN-TIEPDON", "Quầy tiếp đón", "Tầng 1"),
            ("KN-QUAYTHUOC", "Quầy thuốc", "Tầng 2"),
            ("KN-NOITIET", "Phòng Nội tiết", "Tầng 1"),
            ("KN-THUTHUAT", "Phòng thủ thuật", "Tầng 1"),
            ("KN-TTNG", "Thủ thuật ngoài giờ", "Tầng 1"),
            ("KN-SANCHAU", "Phòng Sàn chậu", "Tầng 4"),
            ("KN-SA1", "Phòng siêu âm 2 máy", "Tầng 4"),
            ("KN-SAN-BIO", "Phòng Sản / Siêu âm", "Tầng 4"),
        ):
            assert (phong[code]["name"], phong[code]["floor"]) == (ten, tang), code
        # Thứ tự phòng = thứ tự bảng.
        thu_tu = sorted(
            (c for c in phong if phong[c]["is_active"] and c != "KN-SA2"),
            key=lambda c: phong[c]["sort"],
        )
        assert thu_tu.index("KN-TIEPDON") < thu_tu.index("KN-NOITIET")
        assert thu_tu.index("KN-TTNG") < thu_tu.index("KN-QUAYTHUOC")
        assert (
            thu_tu.index("KN-QUAYTHUOC")
            < thu_tu.index("KN-SANCHAU")
            < thu_tu.index("KN-SA1")
            < thu_tu.index("KN-SAN-BIO")
        )
        # Phòng cũ TẮT (không xoá), phòng giữ lại mở.
        assert (phong["KN-SA-T1"]["is_active"], phong["KN-SA-T1"]["accepting"]) == (
            False,
            False,
        )
        assert phong["KN-SA1"]["is_active"] and phong["KN-SA1"]["accepting"]
        # KN-SA1 làm được mọi việc KN-SA-T1 làm.
        thieu = await pool.fetch(
            "SELECT node_code FROM clinic_room_node WHERE room_id = $1::uuid"
            " EXCEPT SELECT node_code FROM clinic_room_node WHERE room_id = $2::uuid",
            sa_cu,
            sa_moi,
        )
        assert thieu == []

        # Việc CÒN MỞ sang phòng giữ lại; lịch sử giữ phòng cũ.
        o = await pool.fetchrow(
            "SELECT room_id::text, phong_du_kien_id::text, routing_revision, version"
            " FROM service_order WHERE id = $1::uuid",
            mo[1],
        )
        assert o is not None
        assert (o["room_id"], o["phong_du_kien_id"]) == (sa_moi, sa_moi)
        # Tăng đúng MỘT lần dù chạy migration hai lần.
        assert o["routing_revision"] == truoc["routing_revision"] + 1
        assert o["version"] == truoc["version"] + 1
        assert (
            await pool.fetchval(
                "SELECT room_id::text FROM queue_entry WHERE id = $1::uuid", mo[2]
            )
            == sa_moi
        )
        assert (
            await pool.fetchval(
                "SELECT current_room_id::text FROM visit WHERE visit_id = $1::uuid",
                mo[0],
            )
            == sa_moi
        )
        assert (
            await pool.fetchval(
                "SELECT room_id::text FROM service_order WHERE id = $1::uuid",
                da_xong[1],
            )
            == sa_cu
        )
        assert (
            await pool.fetchval(
                "SELECT room_id::text FROM queue_entry WHERE id = $1::uuid", da_xong[2]
            )
            == sa_cu
        )

        # Kỹ năng: Phụ SA chỉ còn phòng giữ lại; Bio thêm Sàn chậu.
        ky = {
            r["ma"]: set(r["p"])
            for r in await pool.fetch(
                "SELECT ma, phong_ids::text[] AS p FROM ky_nang"
                " WHERE clinic_id = $1::uuid AND ma IN ('phu_sa', 'bio')",
                CLINIC,
            )
        }
        assert ky["phu_sa"] == {sa_moi}
        async with pool.acquire() as conn:
            assert ky["bio"] == {
                await _phong(conn, "KN-SAN-BIO"),
                await _phong(conn, "KN-SANCHAU"),
            }

        # Vị trí: tên theo bảng, phòng thật, chữ tầng / phòng khớp.
        vt = {
            r["code"]: r
            for r in await pool.fetch(
                "SELECT v.code, v.ten, v.ten_ngan, v.tang, v.phong, v.sort,"
                " r.code AS ma FROM vi_tri_lam_viec v"
                " LEFT JOIN clinic_room r ON r.id = v.room_id"
                " WHERE v.clinic_id = $1::uuid",
                CLINIC,
            )
        }
        for code, ten, ma in (
            ("T1_SA_BS", "BS 1", "KN-SA1"),
            ("T1_SA_DD", "Điều dưỡng 1", "KN-SA1"),
            ("T1_SA_TK", "Thư ký 1", "KN-SA1"),
            ("T4_SA_BS1", "BS 2", "KN-SA1"),
            ("T4_BIO_DD", "Điều dưỡng Bio", "KN-SANCHAU"),
            ("T1_TT_BS", "BS", "KN-THUTHUAT"),
        ):
            assert (vt[code]["ten"], vt[code]["ten_ngan"], vt[code]["ma"]) == (
                ten,
                ten,
                ma,
            )
        assert (vt["T1_SA_BS"]["tang"], vt["T1_SA_BS"]["phong"]) == (
            "Tầng 4",
            "Phòng siêu âm 2 máy",
        )
        assert vt["T1_DOCHISO"]["phong"] is None
        assert vt["T1_HOIBENH"]["phong"] == "Phòng Nội tiết"
        # Thứ tự trong phòng siêu âm: BS 1 · ĐD 1 · TK 1 · BS 2 · ĐD 2 · TK 2.
        sa = ["T1_SA_BS", "T1_SA_DD", "T1_SA_TK", "T4_SA_BS1", "T4_SA_DD1", "T4_SA_TK1"]
        assert sorted(sa, key=lambda c: vt[c]["sort"]) == sa

        # Tenant khác không bị đụng.
        assert (
            await pool.fetchval(
                "SELECT ten FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid"
                " AND code = 'T1_SA_BS'",
                khac,
            )
            == "BS siêu âm khác"
        )

        # Màn Lịch làm việc: tầng + tên phòng từ PHÒNG THẬT (room_id).
        kq = await vi_tri_hom_nay(identity=_ai(), pool=pool)
        dm = {d["code"]: d for d in cast(list[dict[str, Any]], kq["danh_muc"])}
        assert (dm["T1_SA_BS"]["tang"], dm["T1_SA_BS"]["phong"]) == (
            "Tầng 4",
            "Phòng siêu âm 2 máy",
        )
        assert dm["T1_SA_BS"]["ma_phong"] == "KN-SA1"
        assert (dm["T2_TAODON"]["tang"], dm["T2_TAODON"]["phong"]) == (
            "Tầng 2",
            "Quầy thuốc",
        )
    finally:
        async with pool.acquire() as conn:
            await _don_dep(conn, mo, da_xong)
            await conn.execute(
                "DELETE FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid", khac
            )
            await conn.execute("DELETE FROM clinic WHERE id = $1::uuid", khac)


async def test_tang_tren_lich_theo_phong_that_khi_chu_cu_lech(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Cột Tầng của bảng lịch đọc `clinic_room.floor` (qua room_id), không đọc
    chữ `vi_tri_lam_viec.tang` — quản lý đổi tầng ở Cấu trúc phòng khám là lịch
    đổi theo. Vị trí không gắn phòng rơi về chữ cũ."""
    rid = await pool.fetchval(
        "SELECT id::text FROM clinic_room"
        " WHERE clinic_id = $1::uuid AND code = 'KN-THUTHUAT'",
        CLINIC,
    )
    cu = await pool.fetchval("SELECT floor FROM clinic_room WHERE id = $1::uuid", rid)
    try:
        await pool.execute(
            "UPDATE clinic_room SET floor = 'Tầng 5' WHERE id = $1::uuid", rid
        )
        kq = await vi_tri_hom_nay(identity=_ai(), pool=pool)
        dm = {d["code"]: d for d in cast(list[dict[str, Any]], kq["danh_muc"])}
        assert dm["T1_TT_BS"]["tang"] == "Tầng 5"
        # Vị trí không gắn phòng: tầng là chữ của chính vị trí, không theo phòng.
        assert dm["DIEU_PHOI"]["tang"] == "Quản lý ca khám"
    finally:
        await pool.execute(
            "UPDATE clinic_room SET floor = $2 WHERE id = $1::uuid", rid, cu
        )
