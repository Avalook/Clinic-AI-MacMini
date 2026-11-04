"""Chức năng của phòng (Tuyền 04/11/2026) — "đứng đâu làm việc đó".

Ai xếp lịch đứng phòng P hôm nay thì có các khối của P (`phong_chuc_nang`,
`v_quyen_thuc_te` đọc). Màn Cấu trúc phòng khám tick/bỏ tick từng khối nhóm B
(việc tại chỗ, `permissions/nhom_viec.NHOM_B`). Khối ngoài nhóm B mà phòng đang
có (vd Xem nhà thuốc gieo từ bảng tra cũ) vẫn hiện để biết, không sửa ở đây.

Mọi lần đổi đều hoàn tác được (tick lại) và ghi `event_log`.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.can import doi_quyen
from clinicai.permissions.catalogue import KHOI
from clinicai.permissions.nhom_viec import KHOI_THEO_PHONG, NHOM_B
from clinicai.services.audit import record_event

QUYEN = "config.clinic.manage"

# Thứ tự hiện trên màn = thứ tự khối trong catalogue (giống màn Phân quyền).
_THU_TU = [ma for ma in KHOI if ma in NHOM_B]


async def _phong(conn: asyncpg.Connection, clinic_id: str, room_id: str) -> None:
    co = await conn.fetchval(
        "SELECT 1 FROM clinic_room WHERE id = $1::uuid AND clinic_id = $2::uuid",
        room_id,
        clinic_id,
    )
    if not co:
        raise NotFoundError("Không tìm thấy phòng này.")


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, room_id: str
) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        SELECT w.ma, w.ten, w.mo_ta, (f.work_pack IS NOT NULL) AS bat,
               coalesce(f.theo_phong, false) AS theo_phong
          FROM work_pack w
          LEFT JOIN phong_chuc_nang f
            ON f.work_pack = w.ma AND f.room_id = $1::uuid AND f.clinic_id = $2::uuid
         WHERE w.ma = ANY($3::text[]) OR f.work_pack IS NOT NULL
        """,
        room_id,
        clinic_id,
        sorted(NHOM_B),
    )
    theo_ma = {r["ma"]: r for r in rows}
    chon = [
        {
            "work_pack": ma,
            "ten": theo_ma[ma]["ten"],
            "mo_ta": theo_ma[ma]["mo_ta"],
            "bat": bool(theo_ma[ma]["bat"]),
            "chi_dung_phong": ma in KHOI_THEO_PHONG,
        }
        for ma in _THU_TU
        if ma in theo_ma
    ]
    khac = sorted(
        (
            {"work_pack": r["ma"], "ten": r["ten"]}
            for r in rows
            if r["ma"] not in NHOM_B
        ),
        key=lambda x: x["ten"],
    )
    return {"room_id": room_id, "chon": chon, "khac": khac}


async def doc_chuc_nang(
    pool: asyncpg.Pool, *, identity: StaffIdentity, room_id: str
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        await _phong(conn, identity.clinic_id, room_id)
        return await _doc(conn, identity.clinic_id, room_id)


async def doi_chuc_nang(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    room_id: str,
    work_pack: str,
    bat: bool,
) -> dict[str, Any]:
    """Tick (bat=True) / bỏ tick một khối nhóm B của phòng. Lặp lại vô hại."""
    if work_pack not in NHOM_B:
        raise ValidationError("Chức năng này không gắn theo phòng.")
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen(conn, identity, QUYEN)
        await _phong(conn, identity.clinic_id, room_id)
        if bat:
            kq = await conn.execute(
                "INSERT INTO phong_chuc_nang"
                " (clinic_id, room_id, work_pack, theo_phong, tao_boi)"
                " VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)"
                " ON CONFLICT (room_id, work_pack) DO NOTHING",
                identity.clinic_id,
                room_id,
                work_pack,
                work_pack in KHOI_THEO_PHONG,
                identity.staff_id,
            )
        else:
            kq = await conn.execute(
                "DELETE FROM phong_chuc_nang"
                " WHERE clinic_id = $1::uuid AND room_id = $2::uuid AND work_pack = $3",
                identity.clinic_id,
                room_id,
                work_pack,
            )
        if not str(kq).endswith(" 0"):
            await record_event(
                conn,
                event_type="clinic_config.phong_chuc_nang",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:clinic-config",
                payload={"doi_tuong_id": room_id, "work_pack": work_pack, "bat": bat},
            )
        ket_qua = await _doc(conn, identity.clinic_id, room_id)
    # Quyền nhớ tạm vài giây theo người — bỏ tick phải có hiệu lực ngay.
    cache.quen(identity.clinic_id)
    return ket_qua


__all__ = ["QUYEN", "doc_chuc_nang", "doi_chuc_nang"]
