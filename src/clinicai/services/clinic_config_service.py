"""Cấu hình phòng khám — quản lý tự khai, không ai phải sửa code.

Yêu cầu của Quang (04/08/2026): *"cho quản lý hệ thống có thể gán cho phòng nào
là phòng siêu âm, phòng khám có mấy tầng, phòng nào là bác sĩ nào phụ trách…
lỡ họ có 2 tầng, 5 tầng thì sao"*.

BA TẦNG TÊN GỌI, và chúng lồng vào nhau — nhầm một tầng là hỏng cả mô hình:

    phòng khám (clinic)   Dr4Women            ← một quản lý, một tenant
      └ cơ sở (location)  Kim Ngưu · Hào Nam  ← toà nhà
          └ phòng (room)  KB01 · SA1 · …      ← nằm trên một TẦNG của toà đó

Mọi thứ ở đây mang `clinic_id`, và phần lớn mang cả `location_id`. Đó là điều
kiện để phòng khám thứ hai dùng chung code này mà không đụng dữ liệu của
Dr4Women — và để Dr4Women mở cơ sở thứ ba mà không phải sửa gì.

CÁI GÌ ĐƯỢC KHAI Ở ĐÂY:

    tầng của từng phòng          clinic_room.floor  (nhãn text: "1", "Trệt", "B1")
    phòng phục vụ bước nào       clinic_room_node   (phòng siêu âm = có DICHVU-SIEUAM)
    ai làm được bước nào         staff_node         (khám 5 chuyên khoa / chỉ siêu âm)

CÁI GÌ KHÔNG: số chỗ mỗi khung giờ (đã có màn luật đặt lịch), ngưỡng cảnh báo
chờ (đã có ở bảng điều phối). Gom mọi cấu hình vào một màn nghe gọn nhưng biến
nó thành nơi không ai dám bấm.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity

logger = structlog.get_logger()

#: Chỉ quản lý phòng khám. Khai cấu hình là đổi LUẬT vận hành, khác với dùng
#: hằng ngày — Trưởng ca điều phối được nhưng không đổi được sơ đồ phòng.
CONFIG_ROLES: frozenset[ClinicRole] = frozenset({ClinicRole.MANAGEMENT})


def assert_may_configure(identity: StaffIdentity) -> None:
    if identity.role not in CONFIG_ROLES:
        raise ValidationError(
            f"Vai {identity.role.value} không sửa được cấu hình phòng khám."
        )


_OVERVIEW_SQL = """
SELECT l.id                AS location_id,
       l.code              AS location_code,
       l.name              AS location_name,
       l.is_active         AS location_active,
       r.id                AS room_id,
       r.code              AS room_code,
       r.name              AS room_name,
       r.floor,
       r.capacity,
       r.is_active         AS room_active,
       r.node_code         AS primary_node,
       r.sort,
       (SELECT coalesce(array_agg(rn.node_code ORDER BY rn.node_code), '{}')
          FROM public.clinic_room_node rn WHERE rn.room_id = r.id) AS serves
  FROM public.clinic_location l
  LEFT JOIN public.clinic_room r ON r.location_id = l.id
 WHERE l.clinic_id = $1::uuid
 ORDER BY l.name, r.sort NULLS LAST, r.code
"""

_STAFF_SQL = """
SELECT s.id, s.full_name, s.short_name, s.is_active, m.role,
       l.name AS location_name,
       (SELECT coalesce(array_agg(sn.node_code ORDER BY sn.node_code), '{}')
          FROM public.staff_node sn WHERE sn.staff_id = s.id) AS nodes
  FROM public.staff s
  JOIN public.clinic_membership m
    ON m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active
  LEFT JOIN public.clinic_location l ON l.id = s.primary_location_id
 WHERE s.is_active
 ORDER BY m.role, s.full_name
"""


class ClinicConfigService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def overview(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Sơ đồ phòng khám: cơ sở → tầng → phòng, kèm bước mỗi phòng phục vụ."""
        rows = await self._pool.fetch(_OVERVIEW_SQL, identity.clinic_id)
        nodes = await self._pool.fetch(
            "SELECT code, name FROM public.node_definition"
            " WHERE clinic_id = $1::uuid ORDER BY code",
            identity.clinic_id,
        )
        return {
            "locations": _group_locations(rows),
            "nodes": [{"code": n["code"], "name": n["name"]} for n in nodes],
        }

    async def services(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Dịch vụ khám nào dùng phiếu nào.

        Trước 20260805000004 việc này do trình duyệt ĐOÁN bằng từ khoá trong
        tên dịch vụ, và 6/14 dịch vụ của Dr4Women không đoán ra — bác sĩ mở
        lượt khám thì phần phiếu ẩn hẳn, không một lời nào.
        """
        rows = await self._pool.fetch(
            "SELECT st.id, st.code, st.name, st.form_code, st.form_code_nam,"
            "       st.is_active"
            "  FROM public.service_type st"
            " WHERE st.clinic_id = $1::uuid"
            " ORDER BY st.is_active DESC, st.name",
            identity.clinic_id,
        )
        forms = await self._pool.fetch(
            "SELECT form_code, title FROM public.clinical_form_catalogue"
            " WHERE clinic_id = $1::uuid AND is_active ORDER BY form_code",
            identity.clinic_id,
        )
        return {
            "items": [
                {
                    "service_type_id": str(r["id"]),
                    "code": r["code"],
                    "name": r["name"],
                    "is_active": r["is_active"],
                    "form_code": r["form_code"],
                    #: Chỉ khai khi nội dung khám khác nhau theo giới. Hôm nay
                    #: đúng một dịch vụ: khám tiền hôn nhân.
                    "form_code_nam": r["form_code_nam"],
                }
                for r in rows
            ],
            "forms": [
                {"form_code": f["form_code"], "title": f["title"]} for f in forms
            ],
        }

    async def set_service_form(
        self,
        *,
        identity: StaffIdentity,
        service_type_id: str,
        form_code: str | None,
        form_code_nam: str | None,
    ) -> dict[str, Any]:
        """Gán phiếu khám cho một dịch vụ.

        Chuỗi rỗng = KHÔNG có phiếu, khác với "chưa khai": dịch vụ thủ thuật
        hay tư vấn vốn không cần phiếu chuyên khoa, và màn bác sĩ nói ra điều
        đó thay vì để trống.
        """
        assert_may_configure(identity)
        nu = (form_code or "").strip().upper() or None
        nam = (form_code_nam or "").strip().upper() or None
        if nam and not nu:
            raise ValidationError(
                "Khai phiếu cho bệnh nhân nam thì phải khai cả phiếu mặc định "
                "— nếu không thì bệnh nhân nữ không có phiếu nào."
            )
        try:
            name = await self._pool.fetchval(
                """
                UPDATE public.service_type
                   SET form_code = $3, form_code_nam = $4
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING name
                """,
                service_type_id,
                identity.clinic_id,
                nu,
                nam,
            )
        except asyncpg.ForeignKeyViolationError as exc:
            # Trigger `service_type_form_code_exists` nói bằng câu người đọc
            # được, kèm đúng mã sai.
            raise ValidationError(str(exc).split("\n")[0]) from exc
        if name is None:
            raise ValidationError("Không tìm thấy dịch vụ này.")
        logger.info("service_form_set", service=name, form=nu, form_nam=nam)
        return {"ok": True, "name": name, "form_code": nu, "form_code_nam": nam}

    async def staff(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Ai làm được bước nào."""
        rows = await self._pool.fetch(_STAFF_SQL, identity.clinic_id)
        return {
            "items": [
                {
                    "staff_id": str(r["id"]),
                    "full_name": r["full_name"],
                    "short_name": r["short_name"],
                    "role": r["role"],
                    "location_name": r["location_name"],
                    "nodes": list(r["nodes"] or []),
                }
                for r in rows
            ]
        }

    async def set_room_floor(
        self, *, identity: StaffIdentity, room_id: str, floor: str | None
    ) -> dict[str, Any]:
        """Đặt tầng cho một phòng. Chuỗi trắng = chưa khai, không phải tầng ''."""
        assert_may_configure(identity)
        clean = (floor or "").strip() or None
        updated = await self._pool.fetchval(
            """
            UPDATE public.clinic_room SET floor = $3, updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            RETURNING code
            """,
            room_id,
            identity.clinic_id,
            clean,
        )
        if updated is None:
            raise ValidationError("Không tìm thấy phòng này.")
        logger.info("room_floor_set", room=updated, floor=clean)
        return {"ok": True, "room_code": updated, "floor": clean}

    async def set_room_nodes(
        self, *, identity: StaffIdentity, room_id: str, node_codes: list[str]
    ) -> dict[str, Any]:
        """Phòng này phục vụ những bước nào — "phòng siêu âm" là một dòng ở đây.

        Thay TOÀN BỘ danh sách trong một transaction thay vì thêm/bớt từng cái:
        màn cấu hình gửi trạng thái người dùng nhìn thấy, và ghép từng thao tác
        lẻ là cách để hai bên lệch nhau khi mạng chập giữa chừng.
        """
        assert_may_configure(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            room = await conn.fetchrow(
                "SELECT code, node_code FROM public.clinic_room"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                room_id,
                identity.clinic_id,
            )
            if room is None:
                raise ValidationError("Không tìm thấy phòng này.")
            if room["node_code"] and room["node_code"] not in node_codes:
                # Trigger `clinic_room_primary_node_is_served` cũng chặn, nhưng
                # nó ném tên ràng buộc; ở đây nói bằng câu người vận hành đọc
                # được, và nói TRƯỚC khi xoá dòng nào.
                raise ValidationError(
                    f"Phòng {room['code']} lấy {room['node_code']} làm bước "
                    "chính — bỏ bước đó thì phải đổi bước chính trước."
                )

            await conn.execute(
                "DELETE FROM public.clinic_room_node WHERE room_id = $1::uuid",
                room_id,
            )
            if node_codes:
                await conn.executemany(
                    "INSERT INTO public.clinic_room_node"
                    " (clinic_id, room_id, node_code) VALUES ($1::uuid, $2::uuid, $3)",
                    [(identity.clinic_id, room_id, c) for c in node_codes],
                )
        logger.info("room_nodes_set", room=room["code"], n=len(node_codes))
        return {"ok": True, "room_code": room["code"], "nodes": node_codes}

    async def set_staff_nodes(
        self, *, identity: StaffIdentity, staff_id: str, node_codes: list[str]
    ) -> dict[str, Any]:
        """Người này làm được những bước nào.

        Danh sách RỖNG là hợp lệ và có nghĩa: người này không đảm nhiệm bước nào
        (lễ tân, thu ngân). Đừng đọc nó thành "chưa khai" — nếu không thì không
        ai gỡ được năng lực đã khai nhầm.
        """
        assert_may_configure(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            name = await conn.fetchval(
                "SELECT s.full_name FROM public.staff s"
                "  JOIN public.clinic_membership m ON m.staff_id = s.id"
                " WHERE s.id = $1::uuid AND m.clinic_id = $2::uuid AND m.is_active",
                staff_id,
                identity.clinic_id,
            )
            if name is None:
                raise ValidationError("Không tìm thấy nhân sự này.")

            await conn.execute(
                "DELETE FROM public.staff_node"
                " WHERE staff_id = $1::uuid AND clinic_id = $2::uuid",
                staff_id,
                identity.clinic_id,
            )
            if node_codes:
                await conn.executemany(
                    "INSERT INTO public.staff_node (clinic_id, staff_id, node_code)"
                    " VALUES ($1::uuid, $2::uuid, $3)",
                    [(identity.clinic_id, staff_id, c) for c in node_codes],
                )
        logger.info("staff_nodes_set", staff=name, n=len(node_codes))
        return {"ok": True, "full_name": name, "nodes": node_codes}


def _group_locations(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    """Gom phẳng thành cơ sở → tầng → phòng.

    Tầng gom ở đây chứ không ở SQL: thứ tự tầng suy từ `sort` của phòng đầu
    tiên trên tầng đó (xem 20260804000011 — không có cột thứ tự tầng riêng, để
    không có hai con số nói hai điều).
    """
    out: list[dict[str, Any]] = []
    by_loc: dict[str, dict[str, Any]] = {}
    for r in rows:
        lid = str(r["location_id"])
        if lid not in by_loc:
            by_loc[lid] = {
                "location_id": lid,
                "code": r["location_code"],
                "name": r["location_name"],
                "is_active": r["location_active"],
                "floors": [],
            }
            out.append(by_loc[lid])
        if r["room_id"] is None:
            continue
        # NULL = chưa khai tầng. Giữ nguyên NULL thay vì gộp vào một tầng giả:
        # "chưa khai" và "tầng 1" là hai chuyện khác nhau, và màn cấu hình cần
        # nhìn thấy cái chưa khai để đi khai.
        label = r["floor"]
        floors = by_loc[lid]["floors"]
        floor = next((f for f in floors if f["floor"] == label), None)
        if floor is None:
            floor = {"floor": label, "rooms": []}
            floors.append(floor)
        floor["rooms"].append(
            {
                "room_id": str(r["room_id"]),
                "code": r["room_code"],
                "name": r["room_name"],
                "capacity": r["capacity"],
                "is_active": r["room_active"],
                "primary_node": r["primary_node"],
                "serves": list(r["serves"] or []),
            }
        )
    return out
