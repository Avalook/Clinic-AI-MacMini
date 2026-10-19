"""Quản lý danh mục tầng theo cơ sở và giữ tương thích nhãn tầng cũ."""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event


async def resolve_floor(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    location_id: str,
    floor_id: str | None,
    legacy_name: str | None,
) -> tuple[str | None, str | None]:
    """Resolve a floor ID; a legacy label creates/reactivates its floor."""
    if floor_id is None and legacy_name is None:
        return None, None
    location_exists = await conn.fetchval(
        "SELECT true FROM public.clinic_location"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid AND is_active FOR UPDATE",
        location_id,
        clinic_id,
    )
    if not location_exists:
        raise ValidationError("Không tìm thấy cơ sở đang hoạt động.")
    if floor_id is not None:
        row = await conn.fetchrow(
            "SELECT id::text, name FROM public.clinic_floor"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
            "   AND location_id = $3::uuid AND is_active FOR UPDATE",
            floor_id,
            clinic_id,
            location_id,
        )
        if row is None:
            raise ValidationError("Không tìm thấy tầng đang hoạt động tại cơ sở này.")
        if legacy_name is not None and legacy_name != row["name"]:
            raise ValidationError("Tên tầng và mã tầng không khớp nhau.")
        return row["id"], row["name"]
    if legacy_name is None:  # floor_id đã xử lý phía trên
        return None, None
    if len(legacy_name) > 40:
        raise ValidationError("Tên tầng tối đa 40 ký tự.")
    row = await conn.fetchrow(
        "SELECT id::text, name FROM public.clinic_floor"
        " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
        "   AND name = $3 AND is_active FOR UPDATE",
        clinic_id,
        location_id,
        legacy_name,
    )
    if row is not None:
        return row["id"], row["name"]
    created = await conn.fetchrow(
        """
        INSERT INTO public.clinic_floor
            (clinic_id, location_id, name, sort_order)
        VALUES ($1::uuid, $2::uuid, $3,
                coalesce((SELECT max(sort_order) + 10
                            FROM public.clinic_floor
                           WHERE location_id = $2::uuid AND is_active), 10))
        ON CONFLICT (location_id, name) DO UPDATE SET is_active = true,
            sort_order = EXCLUDED.sort_order,
            updated_at = now()
        RETURNING id::text, name
        """,
        clinic_id,
        location_id,
        legacy_name,
    )
    return created["id"], created["name"]


class ClinicFloorService:
    """CRUD tầng với quyền cấu hình, tenant scope và xoá mềm."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _authorize(self, identity: StaffIdentity) -> None:
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "config.clinic.manage",
                cau="Bạn không có quyền thay đổi cài đặt phòng khám.",
            )

    async def _audit(
        self,
        identity: StaffIdentity,
        *,
        action: str,
        object_id: str,
        payload: dict[str, Any],
    ) -> None:
        async with self._pool.acquire() as conn:
            await record_event(
                conn,
                event_type=f"clinic_config.{action}",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:clinic-config",
                payload={"doi_tuong_id": object_id, **payload},
            )

    async def create(
        self, *, identity: StaffIdentity, location_id: str, name: str
    ) -> dict[str, Any]:
        """Create a floor at the end of a location's stable order."""
        await self._authorize(identity)
        clean = " ".join((name or "").split())
        if not 1 <= len(clean) <= 40:
            raise ValidationError("Tên tầng phải có, tối đa 40 ký tự.")
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                location_exists = await conn.fetchval(
                    "SELECT true FROM public.clinic_location"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    "   AND is_active FOR UPDATE",
                    location_id,
                    identity.clinic_id,
                )
                if not location_exists:
                    raise ValidationError("Không tìm thấy cơ sở đang hoạt động.")
                floor_id = await conn.fetchval(
                    """
                INSERT INTO public.clinic_floor
                    (clinic_id, location_id, name, sort_order)
                VALUES ($1::uuid, $2::uuid, $3,
                       coalesce((SELECT max(sort_order) + 10
                                   FROM public.clinic_floor
                                  WHERE location_id = $2::uuid AND is_active), 10))
                RETURNING id::text
                """,
                    identity.clinic_id,
                    location_id,
                    clean,
                )
        except asyncpg.UniqueViolationError as exc:
            raise ValidationError("Cơ sở này đã có tầng cùng tên.") from exc
        await self._audit(
            identity,
            action="floor_created",
            object_id=floor_id,
            payload={"location_id": location_id, "name": clean},
        )
        return {"ok": True, "floor_id": floor_id, "name": clean}

    async def rename(
        self, *, identity: StaffIdentity, floor_id: str, name: str
    ) -> dict[str, Any]:
        """Rename a floor; a trigger keeps room labels in sync."""
        await self._authorize(identity)
        clean = " ".join((name or "").split())
        if not 1 <= len(clean) <= 40:
            raise ValidationError("Tên tầng phải có, tối đa 40 ký tự.")
        try:
            updated = await self._pool.fetchval(
                "UPDATE public.clinic_floor SET name = $3, updated_at = now()"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid RETURNING id::text",
                floor_id,
                identity.clinic_id,
                clean,
            )
        except asyncpg.UniqueViolationError as exc:
            raise ValidationError("Cơ sở này đã có tầng cùng tên.") from exc
        if updated is None:
            raise ValidationError("Không tìm thấy tầng này.")
        await self._audit(
            identity,
            action="floor_renamed",
            object_id=floor_id,
            payload={"name": clean},
        )
        return {"ok": True, "floor_id": floor_id, "name": clean}

    async def set_active(
        self, *, identity: StaffIdentity, floor_id: str, is_active: bool
    ) -> dict[str, Any]:
        """Soft-delete a floor, refusing while active rooms still use it."""
        await self._authorize(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            location_id = await conn.fetchval(
                "SELECT location_id::text FROM public.clinic_floor"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                floor_id,
                identity.clinic_id,
            )
            if location_id is None:
                raise ValidationError("Không tìm thấy tầng này.")
            await conn.fetchval(
                "SELECT true FROM public.clinic_location"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                location_id,
                identity.clinic_id,
            )
            floor = await conn.fetchrow(
                "SELECT id::text, location_id::text, is_active"
                " FROM public.clinic_floor"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                "   AND location_id = $3::uuid FOR UPDATE",
                floor_id,
                identity.clinic_id,
                location_id,
            )
            if floor is None:
                raise ValidationError("Không tìm thấy tầng này.")
            if not is_active:
                active_rooms = await conn.fetchval(
                    "SELECT count(*) FROM public.clinic_room"
                    " WHERE floor_id = $1::uuid AND clinic_id = $2::uuid AND is_active",
                    floor_id,
                    identity.clinic_id,
                )
                if active_rooms:
                    raise ValidationError(
                        f"Tầng còn {active_rooms} phòng đang hoạt động —"
                        " chuyển hoặc tắt phòng trước khi xoá tầng."
                    )
            if is_active and not floor["is_active"]:
                next_order = await conn.fetchval(
                    "SELECT coalesce(max(sort_order) + 10, 10)"
                    " FROM public.clinic_floor"
                    " WHERE location_id = $1::uuid AND is_active",
                    floor["location_id"],
                )
                await conn.execute(
                    "UPDATE public.clinic_floor"
                    " SET is_active = true, sort_order = $3, updated_at = now()"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    floor_id,
                    identity.clinic_id,
                    next_order,
                )
            else:
                await conn.execute(
                    "UPDATE public.clinic_floor SET is_active = $3, updated_at = now()"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    floor_id,
                    identity.clinic_id,
                    is_active,
                )
        await self._audit(
            identity,
            action="floor_active",
            object_id=floor_id,
            payload={"is_active": is_active},
        )
        return {"ok": True, "floor_id": floor_id, "is_active": is_active}

    async def reorder(
        self,
        *,
        identity: StaffIdentity,
        location_id: str,
        floor_ids: list[str],
    ) -> dict[str, Any]:
        """Persist the supplied floor order for one location."""
        await self._authorize(identity)
        if not floor_ids or len(floor_ids) != len(set(floor_ids)):
            raise ValidationError("Danh sách tầng phải có và không được lặp.")
        async with self._pool.acquire() as conn, conn.transaction():
            location_exists = await conn.fetchval(
                "SELECT true FROM public.clinic_location"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                "   AND is_active FOR UPDATE",
                location_id,
                identity.clinic_id,
            )
            if not location_exists:
                raise ValidationError("Không tìm thấy cơ sở đang hoạt động.")
            rows = await conn.fetch(
                "SELECT id::text FROM public.clinic_floor"
                " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
                "   AND is_active FOR UPDATE",
                identity.clinic_id,
                location_id,
            )
            if {row["id"] for row in rows} != set(floor_ids):
                raise ValidationError(
                    "Danh sách phải gồm đủ mọi tầng đang sử dụng của cơ sở."
                )
            await conn.executemany(
                "UPDATE public.clinic_floor SET sort_order = $2, updated_at = now()"
                " WHERE id = $1::uuid",
                [
                    (floor_id, (index + 1) * 10)
                    for index, floor_id in enumerate(floor_ids)
                ],
            )
        await self._audit(
            identity,
            action="floor_order",
            object_id=location_id,
            payload={"floor_ids": floor_ids},
        )
        return {"ok": True, "location_id": location_id, "floor_ids": floor_ids}


__all__ = ["ClinicFloorService", "resolve_floor"]
