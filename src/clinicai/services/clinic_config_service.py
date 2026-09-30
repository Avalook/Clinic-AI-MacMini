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
    phòng làm dịch vụ nào        clinic_room_service (thu hẹp: Ghế ĐTT chỉ Sàn chậu)
    ai làm được bước nào         staff_node         (khám 5 chuyên khoa / chỉ siêu âm)

CÁI GÌ KHÔNG: số chỗ mỗi khung giờ (đã có màn luật đặt lịch), ngưỡng cảnh báo
chờ (đã có ở bảng điều phối). Gom mọi cấu hình vào một màn nghe gọn nhưng biến
nó thành nơi không ai dám bấm.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event

logger = structlog.get_logger()

#: Chỉ quản lý phòng khám. Khai cấu hình là đổi LUẬT vận hành, khác với dùng
#: hằng ngày — Trưởng ca điều phối được nhưng không đổi được sơ đồ phòng.
CONFIG_ROLES: frozenset[ClinicRole] = frozenset({ClinicRole.MANAGEMENT})


def assert_may_configure(identity: StaffIdentity) -> None:
    """(Cũ — OFF 25/09/2026, thay bằng quyền `config.clinic.manage` của lego
    "Cài đặt phòng khám"; xem `ClinicConfigService._duoc_cau_hinh`.)"""
    if not identity.co_vai(CONFIG_ROLES):
        raise ValidationError(
            f"Vai {identity.role.value} không sửa được cấu hình phòng khám."
        )


#: Tiền tố nhóm việc CHỌN ĐƯỢC ở khối "Phòng làm việc gì" (30/09/2026): nhóm
#: khám và nhóm dịch vụ. Node quản trị (đặt lịch, đối soát, khai lịch làm việc,
#: luồng quầy LUOTKHAM-* / THUOC-*…) KHÔNG mời thêm — chip đã gắn vẫn giữ.
TIEN_TO_CHON_DUOC = ("KHAM-", "DICHVU-")


def la_nhom_chon_duoc(code: Any) -> bool:
    """Node này có được MỜI gắn thêm vào phòng không — hàm thuần."""
    return isinstance(code, str) and code.startswith(TIEN_TO_CHON_DUOC)


def gom_viec_chon_duoc(
    nodes: Iterable[Mapping[str, Any]], dich_vu: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Danh sách "chọn được" cho ô thêm việc của phòng — HÀM THUẦN.

    `nodes`: {code, name}; `dich_vu`: {ma, ten, ma_kv, node, chi_lam_o}. Nhóm
    khám (KHAM-*) chọn cả nhóm; nhóm dịch vụ (DICHVU-*) chỉ hiện khi có ít nhất
    một dịch vụ đang bán — nhóm rỗng (duyệt kết quả, nhập kết quả XN…) là việc
    xử lý, không phải chỗ khách đến."""
    theo_nhom: dict[str, list[dict[str, Any]]] = {}
    for d in dich_vu:
        theo_nhom.setdefault(str(d["node"]), []).append(
            {
                "ma": d["ma"],
                "ten": d["ten"],
                "ma_kv": d.get("ma_kv"),
                "chi_lam_o": list(d.get("chi_lam_o") or []),
            }
        )
    out: list[dict[str, Any]] = []
    for n in nodes:
        code = n.get("code")
        if not la_nhom_chon_duoc(code):
            continue
        ds = sorted(theo_nhom.get(str(code), []), key=lambda x: str(x["ten"]))
        la_kham = str(code).startswith("KHAM-")
        if not la_kham and not ds:
            continue
        out.append(
            {
                "node": code,
                "ten": n.get("name") or code,
                "loai": "KHAM" if la_kham else "DICHVU",
                "dich_vu": ds,
            }
        )
    out.sort(key=lambda g: (g["loai"] != "KHAM", str(g["ten"])))
    return out


def gom_thieu_phong(
    thieu_kham: Iterable[Mapping[str, Any]], dich_vu: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Cảnh báo "Chưa có phòng nào làm" — HÀM THUẦN (30/09/2026).

    Chỉ tính việc KHÁCH ĐẾN PHÒNG: nhóm khám không phòng nào gắn (`thieu_kham`:
    {code, name}) và dịch vụ đang bán cần phòng (`dich_vu`: {ma, ten, node,
    ten_nhom, thieu}; người gọi đã bỏ dịch vụ đối tác làm trọn). Cả nhóm dịch vụ
    đều thiếu → một dòng tên nhóm; thiếu lẻ → từng dịch vụ."""
    out = [
        {"code": t["code"], "name": t["name"], "loi": "CONFIG_MISSING"}
        for t in thieu_kham
    ]
    nhom: dict[str, list[Mapping[str, Any]]] = {}
    for d in dich_vu:
        nhom.setdefault(str(d["node"]), []).append(d)
    for node in sorted(nhom):
        ds = nhom[node]
        thieu = [d for d in ds if d.get("thieu")]
        if not thieu:
            continue
        if len(thieu) == len(ds):
            out.append(
                {
                    "code": node,
                    "name": str(ds[0].get("ten_nhom") or node),
                    "loi": "CONFIG_MISSING",
                }
            )
            continue
        out.extend(
            {"code": d["ma"], "name": str(d["ten"]), "loi": "CONFIG_MISSING"}
            for d in sorted(thieu, key=lambda x: str(x["ten"]))
        )
    return out


_OVERVIEW_SQL = """
SELECT l.id                AS location_id,
       l.code              AS location_code,
       l.name              AS location_name,
       l.is_active         AS location_active,
       l.address           AS location_address,
       r.id                AS room_id,
       r.code              AS room_code,
       r.name              AS room_name,
       r.floor,
       r.capacity,
       r.is_active         AS room_active,
       r.node_code         AS primary_node,
       r.sort,
       (SELECT coalesce(array_agg(rn.node_code ORDER BY rn.node_code), '{}')
          FROM public.clinic_room_node rn WHERE rn.room_id = r.id) AS serves,
       -- Dịch vụ gắn RIÊNG cho phòng (clinic_room_service, 30/09/2026).
       (SELECT coalesce(json_agg(json_build_object(
                   'ma', s.service_code, 'ten', sp.name, 'node', sp.node_code)
                   ORDER BY sp.name), '[]'::json)
          FROM public.clinic_room_service s
          JOIN public.service_price sp
            ON sp.clinic_id = s.clinic_id AND sp."group" = 'dich_vu'
           AND sp.service_code = s.service_code
         WHERE s.room_id = r.id) AS dich_vu
  FROM public.clinic_location l
  LEFT JOIN public.clinic_room r ON r.location_id = l.id
 WHERE l.clinic_id = $1::uuid
 ORDER BY l.name, r.sort NULLS LAST, r.code
"""

_STAFF_SQL = """
SELECT s.id, s.full_name, s.short_name, s.is_active, m.role,
       l.name AS location_name,
       (SELECT coalesce(array_agg(sn.node_code ORDER BY sn.node_code), '{}')
          FROM public.staff_node sn WHERE sn.staff_id = s.id) AS nodes,
       (SELECT coalesce(array_agg(tb.bac_si_staff_id::text), '{}')
          FROM public.thu_ky_bac_si tb
         WHERE tb.clinic_id = $1::uuid AND tb.thu_ky_staff_id = s.id) AS bac_si
  FROM public.staff s
  JOIN public.clinic_membership m
    ON m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active
  LEFT JOIN public.clinic_location l ON l.id = s.primary_location_id
 WHERE s.is_active
 ORDER BY m.role, s.full_name
"""


#: Dịch vụ đang bán thuộc nhóm dịch vụ (DICHVU-*), kèm: phòng gắn riêng (nếu
#: có), cần phòng không (đối tác làm trọn thì không), và còn thiếu phòng không.
_DICH_VU_CHON_DUOC_SQL = """
SELECT sp.service_code AS ma, sp.name AS ten, sp.ma_kiotviet AS ma_kv,
       sp.node_code AS node, n.name AS ten_nhom,
       (SELECT coalesce(array_agg(coalesce(r.name, r.code)
                                  ORDER BY r.sort, r.code), '{}')
          FROM public.clinic_room_service s
          JOIN public.clinic_room r ON r.id = s.room_id AND r.clinic_id = s.clinic_id
         WHERE s.clinic_id = sp.clinic_id AND s.service_code = sp.service_code
           AND r.is_active) AS chi_lam_o,
       NOT (sp.doi_tac_lay_mau OR n.lam_ben_ngoai) AS can_phong,
       NOT EXISTS (
           SELECT 1 FROM public.clinic_room r
            WHERE r.clinic_id = sp.clinic_id AND r.is_active AND NOT r.la_doi_tac
              AND public.phong_lam_duoc(r.clinic_id, r.id, sp.node_code,
                                        sp.service_code)) AS thieu
  FROM public.service_price sp
  JOIN public.node_definition n
    ON n.clinic_id = sp.clinic_id AND n.code = sp.node_code AND n.is_active
 WHERE sp.clinic_id = $1::uuid AND sp.active AND sp."group" = 'dich_vu'
   AND sp.node_code LIKE 'DICHVU-%'
 ORDER BY sp.node_code, sp.name
"""


class ClinicConfigService:
    async def _duoc_cau_hinh(self, identity: StaffIdentity) -> None:
        """Lego 18 "Cài đặt phòng khám" (Tuyền 25/09/2026): hỏi QUYỀN, không hỏi
        vai — thu lego là thôi sửa cấu hình ngay."""
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "config.clinic.manage",
                cau="Bạn không có quyền thay đổi cài đặt phòng khám.",
            )

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _ghi_nhat_ky(
        self,
        identity: StaffIdentity,
        *,
        loai: str,
        doi_tuong_id: str,
        payload: dict[str, Any],
    ) -> None:
        """NHẬT KÝ CẤU HÌNH (15/09/2026): quản lý tự khai phòng/bước/người, nên
        phải biết ai đổi gì, lúc nào. Ghi sau khi lệnh cấu hình đã xong."""
        async with self._pool.acquire() as conn:
            await record_event(
                conn,
                event_type=f"clinic_config.{loai}",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:clinic-config",
                payload={"doi_tuong_id": doi_tuong_id, **payload},
            )

    async def overview(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Sơ đồ phòng khám: cơ sở → tầng → phòng, kèm bước mỗi phòng phục vụ."""
        rows = await self._pool.fetch(_OVERVIEW_SQL, identity.clinic_id)
        nodes = await self._pool.fetch(
            "SELECT code, name FROM public.node_definition"
            " WHERE clinic_id = $1::uuid ORDER BY code",
            identity.clinic_id,
        )
        dich_vu = await self._pool.fetch(_DICH_VU_CHON_DUOC_SQL, identity.clinic_id)
        # CONFIG_MISSING (30/09/2026): chỉ việc KHÁCH ĐẾN PHÒNG — dịch vụ đang
        # bán mà không phòng nội bộ đang bật nào làm được (cùng luật
        # `phong_lam_duoc` với xếp phòng), và nhóm khám không phòng nào gắn.
        # Không tính node quản trị hay dịch vụ đối tác làm trọn. Không tự tạo
        # phòng: báo để quản lý cấu hình.
        thieu_kham = await self._pool.fetch(
            """
            SELECT n.code, n.name FROM public.node_definition n
             WHERE n.clinic_id = $1::uuid AND n.code LIKE 'KHAM-%'
               AND n.is_active
               AND NOT EXISTS (
                     SELECT 1 FROM public.clinic_room_node rn
                       JOIN public.clinic_room r ON r.id = rn.room_id
                      WHERE rn.clinic_id = n.clinic_id AND rn.node_code = n.code
                        AND r.is_active AND NOT r.la_doi_tac)
             ORDER BY n.code
            """,
            identity.clinic_id,
        )
        return {
            "locations": _group_locations(rows),
            "nodes": [{"code": n["code"], "name": n["name"]} for n in nodes],
            # Ô thêm việc của phòng — máy chủ quyết cái gì chọn được.
            "viec_chon_duoc": gom_viec_chon_duoc(
                [dict(n) for n in nodes], [dict(d) for d in dich_vu]
            ),
            "config_missing": gom_thieu_phong(
                [dict(t) for t in thieu_kham],
                [dict(d) for d in dich_vu if d["can_phong"]],
            ),
        }

    async def services(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Dịch vụ khám nào dùng phiếu nào.

        Trước 20260805000004 việc này do trình duyệt ĐOÁN bằng từ khoá trong
        tên dịch vụ, và 6/14 dịch vụ của Dr4Women không đoán ra — bác sĩ mở
        lượt khám thì phần phiếu ẩn hẳn, không một lời nào.
        """
        rows = await self._pool.fetch(
            "SELECT st.id, st.code, st.name, st.form_code, st.form_code_nam,"
            "       st.is_active, st.gia_mac_dinh"
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
                    "gia_mac_dinh": int(r.get("gia_mac_dinh") or 0),
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
        await self._duoc_cau_hinh(identity)
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
        await self._ghi_nhat_ky(
            identity,
            loai="service_form",
            doi_tuong_id=service_type_id,
            payload={"form_code": nu, "form_code_nam": nam},
        )
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
                    "bac_si": list(r["bac_si"] or []),
                    "nodes": list(r["nodes"] or []),
                }
                for r in rows
            ]
        }

    async def set_room_floor(
        self, *, identity: StaffIdentity, room_id: str, floor: str | None
    ) -> dict[str, Any]:
        """Đặt tầng cho một phòng. Chuỗi trắng = chưa khai, không phải tầng ''."""
        await self._duoc_cau_hinh(identity)
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
        await self._ghi_nhat_ky(
            identity, loai="room_floor", doi_tuong_id=room_id, payload={"floor": clean}
        )
        return {"ok": True, "room_code": updated, "floor": clean}

    # ── Phòng là TÀI NGUYÊN (CORE-C, 23/09/2026) ─────────────────────────────
    # Định danh phòng là `room_id`. Tên chỉ để hiển thị — đổi "Siêu âm 1" thành
    # "Phòng Hoa" không đụng tới lịch trực, hàng chờ hay quyền. `code` là mã NỘI
    # BỘ tự sinh cho phòng mới, không ai phải gõ, không nghĩa nghiệp vụ.

    async def create_room(
        self,
        *,
        identity: StaffIdentity,
        location_id: str,
        name: str,
        node_code: str,
        floor: str | None = None,
    ) -> dict[str, Any]:
        """Thêm phòng. Phải chọn luôn bước chính (bảng bắt buộc): "phòng này làm
        việc gì" — thêm bước khác sau ở danh sách bước phục vụ."""
        await self._duoc_cau_hinh(identity)
        ten = " ".join((name or "").split())
        if not ten or len(ten) > 80:
            raise ValidationError("Tên phòng phải có, tối đa 80 ký tự.")
        tang = (floor or "").strip() or None
        async with self._pool.acquire() as conn, conn.transaction():
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.clinic_location"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid)",
                location_id,
                identity.clinic_id,
            ):
                raise ValidationError("Không tìm thấy cơ sở này.")
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.node_definition"
                " WHERE clinic_id = $1::uuid AND code = $2)",
                identity.clinic_id,
                node_code,
            ):
                raise ValidationError(f"Không có bước “{node_code}”.")
            room_id = await conn.fetchval(
                """
                INSERT INTO public.clinic_room
                    (clinic_id, location_id, code, name, node_code, floor, sort)
                SELECT $1::uuid, $2::uuid,
                       'P-' || upper(substr(md5(gen_random_uuid()::text), 1, 8)),
                       $3, $4, $5,
                       coalesce((SELECT max(sort) FROM public.clinic_room
                                  WHERE location_id = $2::uuid), 0) + 10
                RETURNING id::text
                """,
                identity.clinic_id,
                location_id,
                ten,
                node_code,
                tang,
            )
            await conn.execute(
                "INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)"
                " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
                identity.clinic_id,
                room_id,
                node_code,
            )
        await self._ghi_nhat_ky(
            identity,
            loai="room_created",
            doi_tuong_id=room_id,
            payload={"name": ten, "node_code": node_code, "floor": tang},
        )
        return {"ok": True, "room_id": room_id}

    async def rename_room(
        self, *, identity: StaffIdentity, room_id: str, name: str
    ) -> dict[str, Any]:
        """Đổi TÊN hiển thị. `room_id` giữ nguyên nên lịch trực, hàng chờ, chỉ
        định đã xếp vào phòng này không mất gì."""
        await self._duoc_cau_hinh(identity)
        ten = " ".join((name or "").split())
        if not ten or len(ten) > 80:
            raise ValidationError("Tên phòng phải có, tối đa 80 ký tự.")
        cu = await self._pool.fetchval(
            """
            WITH cu AS (SELECT name FROM public.clinic_room
                         WHERE id = $1::uuid AND clinic_id = $2::uuid)
            UPDATE public.clinic_room r SET name = $3, updated_at = now()
              FROM cu WHERE r.id = $1::uuid AND r.clinic_id = $2::uuid
            RETURNING cu.name
            """,
            room_id,
            identity.clinic_id,
            ten,
        )
        if cu is None:
            raise ValidationError("Không tìm thấy phòng này.")
        await self._ghi_nhat_ky(
            identity,
            loai="room_renamed",
            doi_tuong_id=room_id,
            payload={"tu": cu, "thanh": ten},
        )
        return {"ok": True, "room_id": room_id, "name": ten}

    async def set_room_active(
        self, *, identity: StaffIdentity, room_id: str, is_active: bool
    ) -> dict[str, Any]:
        """Bật/tắt phòng. Tắt chứ không xoá: lịch sử khám ở phòng này còn trỏ
        vào nó. Không tắt được khi còn khách đang chờ/đang làm trong phòng."""
        await self._duoc_cau_hinh(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            room = await conn.fetchrow(
                "SELECT id FROM public.clinic_room"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                room_id,
                identity.clinic_id,
            )
            if room is None:
                raise ValidationError("Không tìm thấy phòng này.")
            if not is_active:
                con_khach = await conn.fetchval(
                    "SELECT count(*) FROM public.queue_entry"
                    " WHERE clinic_id = $1::uuid AND room_id = $2::uuid"
                    "   AND status IN ('waiting', 'called', 'serving')",
                    identity.clinic_id,
                    room_id,
                )
                if con_khach:
                    raise ValidationError(
                        f"Phòng còn {con_khach} khách đang chờ/đang làm —"
                        " chuyển khách sang phòng khác trước khi tắt."
                    )
            await conn.execute(
                "UPDATE public.clinic_room SET is_active = $3, updated_at = now()"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                room_id,
                identity.clinic_id,
                is_active,
            )
        await self._ghi_nhat_ky(
            identity,
            loai="room_active",
            doi_tuong_id=room_id,
            payload={"is_active": is_active},
        )
        # Quyền theo lịch đọc phòng/node/vị trí — đổi thì quên quyền đang nhớ.
        cache.quen(identity.clinic_id)
        return {"ok": True, "room_id": room_id, "is_active": is_active}

    async def set_room_flags(
        self,
        *,
        identity: StaffIdentity,
        room_id: str,
        la_doi_tac: bool | None = None,
        accepting: bool | None = None,
    ) -> dict[str, Any]:
        """Phòng là phòng ĐỐI TÁC hay không · phòng đang NHẬN khách hay tạm ngừng.

        Trước 24/09/2026 hai cờ này chỉ đổi được bằng SQL (mô phỏng buổi khám bắt
        được). Tạm ngừng ≠ tắt phòng: tạm ngừng chỉ thôi nhận khách MỚI (tự xếp
        bỏ qua phòng này), khách đang chờ vẫn làm tiếp; tắt phòng mới cần hàng
        chờ trống.
        """
        await self._duoc_cau_hinh(identity)
        if la_doi_tac is None and accepting is None:
            raise ValidationError("Không có gì để đổi.")
        async with self._pool.acquire() as conn, conn.transaction():
            room = await conn.fetchrow(
                "SELECT la_doi_tac, accepting FROM public.clinic_room"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                room_id,
                identity.clinic_id,
            )
            if room is None:
                raise ValidationError("Không tìm thấy phòng này.")
            moi = {
                "la_doi_tac": room["la_doi_tac"] if la_doi_tac is None else la_doi_tac,
                "accepting": room["accepting"] if accepting is None else accepting,
            }
            await conn.execute(
                "UPDATE public.clinic_room SET la_doi_tac = $3, accepting = $4,"
                " updated_at = now() WHERE id = $1::uuid AND clinic_id = $2::uuid",
                room_id,
                identity.clinic_id,
                moi["la_doi_tac"],
                moi["accepting"],
            )
        await self._ghi_nhat_ky(
            identity, loai="room_flags", doi_tuong_id=room_id, payload=moi
        )
        # Quyền theo lịch đọc phòng/node/vị trí — đổi thì quên quyền đang nhớ.
        cache.quen(identity.clinic_id)
        return {"ok": True, "room_id": room_id, **moi}

    # ── Cơ sở ─────────────────────────────────────────────────────────────
    async def create_location(
        self, *, identity: StaffIdentity, name: str, address: str | None = None
    ) -> dict[str, Any]:
        """Thêm cơ sở. Tên tự do; mã nội bộ tự sinh, không ai phải gõ."""
        await self._duoc_cau_hinh(identity)
        ten = " ".join((name or "").split())
        if not ten or len(ten) > 120:
            raise ValidationError("Tên cơ sở phải có, tối đa 120 ký tự.")
        dia_chi = " ".join((address or "").split()) or None
        loc_id = await self._pool.fetchval(
            """
            INSERT INTO public.clinic_location (clinic_id, code, name, address,
                                                is_active)
            VALUES ($1::uuid,
                    'CS-' || upper(substr(md5(gen_random_uuid()::text), 1, 8)),
                    $2, $3, true)
            RETURNING id::text
            """,
            identity.clinic_id,
            ten,
            dia_chi,
        )
        await self._ghi_nhat_ky(
            identity,
            loai="location_created",
            doi_tuong_id=str(loc_id),
            payload={"name": ten, "address": dia_chi},
        )
        return {"ok": True, "location_id": str(loc_id), "name": ten}

    async def update_location(
        self,
        *,
        identity: StaffIdentity,
        location_id: str,
        name: str | None = None,
        address: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """Đổi tên / địa chỉ / bật-tắt cơ sở. Tắt chứ không xoá — lịch sử khám
        còn trỏ vào nó. Không tắt được khi cơ sở còn phòng đang bật."""
        await self._duoc_cau_hinh(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            cu = await conn.fetchrow(
                "SELECT name, address, is_active FROM public.clinic_location"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                location_id,
                identity.clinic_id,
            )
            if cu is None:
                raise ValidationError("Không tìm thấy cơ sở này.")
            ten = cu["name"] if name is None else " ".join(name.split())
            if not ten or len(ten) > 120:
                raise ValidationError("Tên cơ sở phải có, tối đa 120 ký tự.")
            dia_chi = (
                cu["address"]
                if address is None
                else (" ".join(address.split()) or None)
            )
            bat = bool(cu["is_active"]) if is_active is None else is_active
            if not bat:
                con_phong = await conn.fetchval(
                    "SELECT count(*) FROM public.clinic_room"
                    " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
                    "   AND is_active",
                    identity.clinic_id,
                    location_id,
                )
                if con_phong:
                    raise ValidationError(
                        f"Cơ sở còn {con_phong} phòng đang bật — tắt các phòng"
                        " trước khi tắt cơ sở."
                    )
            await conn.execute(
                "UPDATE public.clinic_location SET name = $3, address = $4,"
                " is_active = $5 WHERE id = $1::uuid AND clinic_id = $2::uuid",
                location_id,
                identity.clinic_id,
                ten,
                dia_chi,
                bat,
            )
        moi = {"name": ten, "address": dia_chi, "is_active": bat}
        await self._ghi_nhat_ky(
            identity, loai="location_updated", doi_tuong_id=location_id, payload=moi
        )
        return {"ok": True, "location_id": location_id, **moi}

    # ── Loại dịch vụ khám (service_type) ─────────────────────────────────
    async def create_service_type(
        self,
        *,
        identity: StaffIdentity,
        name: str,
        default_duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Thêm loại khám. Qua tư vấn / đi thẳng phòng chỉnh ở màn Dây nối."""
        await self._duoc_cau_hinh(identity)
        ten = " ".join((name or "").split())
        if not ten or len(ten) > 120:
            raise ValidationError("Tên dịch vụ phải có, tối đa 120 ký tự.")
        st_id = await self._pool.fetchval(
            """
            INSERT INTO public.service_type (clinic_id, code, name,
                                             default_duration_minutes, is_active)
            VALUES ($1::uuid,
                    'DV-' || upper(substr(md5(gen_random_uuid()::text), 1, 8)),
                    $2, $3, true)
            RETURNING id::text
            """,
            identity.clinic_id,
            ten,
            default_duration_minutes,
        )
        await self._ghi_nhat_ky(
            identity,
            loai="service_type_created",
            doi_tuong_id=str(st_id),
            payload={"name": ten, "default_duration_minutes": default_duration_minutes},
        )
        return {"ok": True, "service_type_id": str(st_id), "name": ten}

    async def update_service_type(
        self,
        *,
        identity: StaffIdentity,
        service_type_id: str,
        name: str | None = None,
        default_duration_minutes: int | None = None,
        is_active: bool | None = None,
        gia_mac_dinh: Any | None = None,
    ) -> dict[str, Any]:
        """Đổi tên / thời lượng / bật-tắt loại khám. Tắt chứ không xoá: lịch
        hẹn cũ vẫn trỏ vào nó; tắt rồi thì không đặt lịch MỚI được."""
        await self._duoc_cau_hinh(identity)
        if gia_mac_dinh is not None and (
            isinstance(gia_mac_dinh, bool)
            or not isinstance(gia_mac_dinh, int)
            or not 0 <= gia_mac_dinh <= 1_000_000_000
        ):
            raise ValidationError(
                "Giá mặc định phải là số nguyên từ 0 đến 1.000.000.000đ."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            cu = await conn.fetchrow(
                "SELECT name, default_duration_minutes, is_active, gia_mac_dinh"
                "  FROM public.service_type"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                service_type_id,
                identity.clinic_id,
            )
            if cu is None:
                raise ValidationError("Không tìm thấy dịch vụ này.")
            ten = cu["name"] if name is None else " ".join(name.split())
            if not ten or len(ten) > 120:
                raise ValidationError("Tên dịch vụ phải có, tối đa 120 ký tự.")
            phut = (
                cu["default_duration_minutes"]
                if default_duration_minutes is None
                else default_duration_minutes
            )
            bat = bool(cu["is_active"]) if is_active is None else is_active
            gia = (
                (cu.get("gia_mac_dinh") or 0) if gia_mac_dinh is None else gia_mac_dinh
            )
            await conn.execute(
                "UPDATE public.service_type SET name = $3,"
                " default_duration_minutes = $4, is_active = $5, gia_mac_dinh = $6"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                service_type_id,
                identity.clinic_id,
                ten,
                phut,
                bat,
                gia,
            )
            moi = {
                "name": ten,
                "default_duration_minutes": phut,
                "is_active": bat,
                "gia_mac_dinh": int(gia),
            }
            # Giá ảnh hưởng trực tiếp số tiền: thay đổi và dấu kiểm toán phải
            # cùng thành công hoặc cùng lùi.
            await record_event(
                conn,
                event_type="clinic_config.service_type_updated",
                aggregate_type="clinic",
                aggregate_id=identity.clinic_id,
                identity=identity,
                origin="api:clinic-config",
                payload={"doi_tuong_id": service_type_id, **moi},
            )
        return {"ok": True, "service_type_id": service_type_id, **moi}

    async def set_room_nodes(
        self, *, identity: StaffIdentity, room_id: str, node_codes: list[str]
    ) -> dict[str, Any]:
        """Phòng này phục vụ những bước nào — "phòng siêu âm" là một dòng ở đây.

        Thay TOÀN BỘ danh sách trong một transaction thay vì thêm/bớt từng cái:
        màn cấu hình gửi trạng thái người dùng nhìn thấy, và ghép từng thao tác
        lẻ là cách để hai bên lệch nhau khi mạng chập giữa chừng.
        """
        await self._duoc_cau_hinh(identity)
        async with self._pool.acquire() as conn, conn.transaction():
            room = await conn.fetchrow(
                "SELECT code, node_code FROM public.clinic_room"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                room_id,
                identity.clinic_id,
            )
            if room is None:
                raise ValidationError("Không tìm thấy phòng này.")
            cu = {
                str(x["node_code"])
                for x in await conn.fetch(
                    "SELECT node_code FROM public.clinic_room_node"
                    " WHERE clinic_id = $1::uuid AND room_id = $2::uuid",
                    identity.clinic_id,
                    room_id,
                )
            }
            moi = [c for c in node_codes if c not in cu and not la_nhom_chon_duoc(c)]
            if moi:
                # Ô thêm việc chỉ mời nhóm khám / nhóm dịch vụ (30/09/2026);
                # node quản trị đã gắn từ trước thì giữ được, không thêm mới.
                raise ValidationError(
                    f"Không gắn được việc quản trị vào phòng: {', '.join(moi)}."
                    " Phòng chỉ nhận nhóm khám, nhóm dịch vụ hoặc từng dịch vụ."
                )
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
        await self._ghi_nhat_ky(
            identity,
            loai="room_nodes",
            doi_tuong_id=room_id,
            payload={"nodes": sorted(node_codes)},
        )
        # Quyền theo lịch đọc phòng/node/vị trí — đổi thì quên quyền đang nhớ.
        cache.quen(identity.clinic_id)
        return {"ok": True, "room_code": room["code"], "nodes": node_codes}

    async def set_room_services(
        self, *, identity: StaffIdentity, room_id: str, service_codes: list[str]
    ) -> dict[str, Any]:
        """Phòng làm những DỊCH VỤ LẺ nào (30/09/2026) — lớp thu hẹp trên node.

        Dịch vụ có dòng ở đây thì CHỈ các phòng được gắn làm được (luật
        `phong_lam_duoc`). Danh sách ĐẦY ĐỦ như `set_room_nodes`: dòng không còn
        trong danh sách thì bỏ, dòng mới thì thêm (dòng giữ nguyên giữ người /
        giờ gắn cũ).
        """
        await self._duoc_cau_hinh(identity)
        ma = sorted({c.strip() for c in service_codes if isinstance(c, str)} - {""})
        async with self._pool.acquire() as conn, conn.transaction():
            room = await conn.fetchrow(
                "SELECT code FROM public.clinic_room"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                room_id,
                identity.clinic_id,
            )
            if room is None:
                raise ValidationError("Không tìm thấy phòng này.")
            hop_le = {
                str(r["service_code"])
                for r in await conn.fetch(
                    "SELECT service_code FROM public.service_price"
                    " WHERE clinic_id = $1::uuid AND \"group\" = 'dich_vu'"
                    "   AND active AND node_code LIKE 'DICHVU-%'"
                    "   AND service_code = ANY($2::text[])",
                    identity.clinic_id,
                    ma,
                )
            }
            la = [c for c in ma if c not in hop_le]
            if la:
                raise ValidationError(
                    f"Không gắn được: {', '.join(la)} — không phải dịch vụ đang"
                    " bán thuộc nhóm dịch vụ."
                )
            await conn.execute(
                "DELETE FROM public.clinic_room_service"
                " WHERE clinic_id = $1::uuid AND room_id = $2::uuid"
                "   AND NOT (service_code = ANY($3::text[]))",
                identity.clinic_id,
                room_id,
                ma,
            )
            if ma:
                await conn.executemany(
                    "INSERT INTO public.clinic_room_service"
                    " (clinic_id, room_id, service_code, created_by)"
                    " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)"
                    " ON CONFLICT DO NOTHING",
                    [(identity.clinic_id, room_id, c, identity.staff_id) for c in ma],
                )
        logger.info("room_services_set", room=room["code"], n=len(ma))
        await self._ghi_nhat_ky(
            identity,
            loai="room_services",
            doi_tuong_id=room_id,
            payload={"services": ma},
        )
        return {"ok": True, "room_code": room["code"], "service_codes": ma}

    async def set_staff_nodes(
        self, *, identity: StaffIdentity, staff_id: str, node_codes: list[str]
    ) -> dict[str, Any]:
        """Người này làm được những bước nào.

        Danh sách RỖNG là hợp lệ và có nghĩa: người này không đảm nhiệm bước nào
        (lễ tân, thu ngân). Đừng đọc nó thành "chưa khai" — nếu không thì không
        ai gỡ được năng lực đã khai nhầm.
        """
        await self._duoc_cau_hinh(identity)
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
        await self._ghi_nhat_ky(
            identity,
            loai="staff_nodes",
            doi_tuong_id=staff_id,
            payload={"nodes": sorted(node_codes)},
        )
        return {"ok": True, "full_name": name, "nodes": node_codes}


def _json_list(v: Any) -> list[dict[str, Any]]:
    """json_agg qua asyncpg về dạng chuỗi (không codec json) — đọc cả hai dạng."""
    if isinstance(v, str):
        v = json.loads(v)
    return [dict(x) for x in v] if isinstance(v, list) else []


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
                "address": dict(r).get("location_address"),
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
                "dich_vu": _json_list(dict(r).get("dich_vu")),
            }
        )
    return out
