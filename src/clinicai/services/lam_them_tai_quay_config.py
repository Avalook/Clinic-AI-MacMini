"""Cấu hình danh sách dịch vụ làm thêm tại quầy — phần dành cho quản lý."""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event

ORIGIN = "api:lam-them-tai-quay"
QUYEN_CAU_HINH = "config.wiring.manage"


def _ma_dich_vu(value: Any) -> str:
    ma = value.strip() if isinstance(value, str) else ""
    if not ma or len(ma) > 64:
        raise ValidationError("Mã dịch vụ không hợp lệ.")
    return ma


class LamThemCauHinhMixin:
    _pool: asyncpg.Pool
    # ── Cấu hình (quản lý) ──────────────────────────────────────────────────

    async def cau_hinh(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Danh sách nút + dịch vụ chọn được (dịch vụ ĐANG BÁN, đã gắn bước làm)."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            muc = await self._doc_muc(conn, cid)
            dich_vu = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT DISTINCT ON (s.service_code)
                           s.service_code, s.name AS ten, s.unit_price AS gia
                      FROM service_price s
                     WHERE s.clinic_id = $1::uuid AND s."group" = 'dich_vu'
                       AND s.active AND s.node_code IS NOT NULL
                     ORDER BY s.service_code, s.unit_price NULLS LAST
                    """,
                    cid,
                )
            ]
        for d in dich_vu:
            d["gia"] = int(d["gia"]) if d["gia"] is not None else None
        dich_vu.sort(key=lambda d: str(d["ten"]))
        return {"muc": muc, "dich_vu": dich_vu}

    async def luu_muc(
        self,
        *,
        identity: StaffIdentity,
        service_code: Any,
        nhan: Any = None,
        bat: Any = True,
        thu_tu: Any = None,
        o_tiep_don: Any = True,
        o_sinh_hieu: Any = True,
    ) -> dict[str, Any]:
        """Thêm hoặc sửa MỘT nút. Bật mà không hiện ở đâu → báo, không lưu câm."""
        cid = identity.clinic_id
        ma = _ma_dich_vu(service_code)
        nhan_sach = nhan.strip() if isinstance(nhan, str) and nhan.strip() else None
        if nhan_sach is not None and len(nhan_sach) > 40:
            raise ValidationError("Chữ trên nút dài tối đa 40 ký tự.")
        bat_b = bool(bat)
        tiep = bool(o_tiep_don)
        sinh = bool(o_sinh_hieu)
        if bat_b and not (tiep or sinh):
            raise ValidationError(
                "Nút đang bật phải hiện ở ít nhất một nơi (Tiếp đón hoặc Đo sinh"
                " hiệu) — không hiện ở đâu thì tắt nút."
            )
        try:
            so = int(thu_tu) if thu_tu is not None and thu_tu != "" else None
        except (TypeError, ValueError):
            raise ValidationError("Thứ tự phải là số.") from None
        if so is not None and not 0 <= so <= 9999:
            raise ValidationError("Thứ tự trong khoảng 0–9999.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            dv = await conn.fetchrow(
                """
                SELECT s.name, s.node_code FROM service_price s
                 WHERE s.clinic_id = $1::uuid AND s."group" = 'dich_vu'
                   AND s.service_code = $2 AND s.active
                 ORDER BY s.node_code NULLS LAST LIMIT 1
                """,
                cid,
                ma,
            )
            if dv is None:
                raise ValidationError(
                    "Dịch vụ này không có (hoặc đã ngừng bán) trong bảng giá."
                )
            if not dv["node_code"]:
                raise ValidationError(
                    f"“{dv['name']}” chưa gắn bước thực hiện — gắn ở bảng giá"
                    " trước rồi mới làm nút được."
                )
            if so is None:
                so = int(
                    await conn.fetchval(
                        "SELECT coalesce(max(thu_tu), 0) + 10 FROM lam_them_tai_quay"
                        " WHERE clinic_id = $1::uuid",
                        cid,
                    )
                )
            await conn.execute(
                """
                INSERT INTO lam_them_tai_quay
                    (clinic_id, service_code, nhan, bat, thu_tu, o_tiep_don,
                     o_sinh_hieu, updated_by)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::uuid)
                ON CONFLICT (clinic_id, service_code) DO UPDATE
                   SET nhan = EXCLUDED.nhan, bat = EXCLUDED.bat,
                       thu_tu = EXCLUDED.thu_tu, o_tiep_don = EXCLUDED.o_tiep_don,
                       o_sinh_hieu = EXCLUDED.o_sinh_hieu,
                       updated_by = EXCLUDED.updated_by, updated_at = now()
                """,
                cid,
                ma,
                nhan_sach,
                bat_b,
                so,
                tiep,
                sinh,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="config.desk_service_saved",
                aggregate_type="clinic",
                aggregate_id=cid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "service_code": ma,
                    "nhan": nhan_sach,
                    "bat": bat_b,
                    "thu_tu": so,
                    "o_tiep_don": tiep,
                    "o_sinh_hieu": sinh,
                },
            )
            muc = await self._doc_muc(conn, cid)
        return {"ok": True, "muc": muc}

    async def bo_muc(
        self, *, identity: StaffIdentity, service_code: Any
    ) -> dict[str, Any]:
        """Bớt nút khỏi quầy bằng tắt mềm; bật lại giữ nguyên toàn bộ cấu hình."""
        cid = identity.clinic_id
        ma = _ma_dich_vu(service_code)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            da_tat = await conn.fetchval(
                "UPDATE lam_them_tai_quay SET bat = false, updated_by = $3::uuid,"
                " updated_at = now() WHERE clinic_id = $1::uuid"
                " AND service_code = $2 RETURNING service_code",
                cid,
                ma,
                identity.staff_id,
            )
            if da_tat is None:
                raise NotFoundError("Nút này không có trong danh sách.")
            await record_event(
                conn,
                event_type="config.desk_service_removed",
                aggregate_type="clinic",
                aggregate_id=cid,
                identity=identity,
                origin=ORIGIN,
                payload={"service_code": ma, "bat": False, "co_the_bat_lai": True},
            )
            muc = await self._doc_muc(conn, cid)
        return {"ok": True, "muc": muc}

    async def doi_thu_tu(self, *, identity: StaffIdentity, muc: Any) -> dict[str, Any]:
        """Đổi thứ tự nhiều nút trong MỘT giao dịch, không để trạng thái nửa vời."""
        if not isinstance(muc, list) or not 1 <= len(muc) <= 100:
            raise ValidationError("Danh sách thứ tự không hợp lệ.")
        ds: list[tuple[str, int]] = []
        for item in muc:
            if not isinstance(item, dict):
                raise ValidationError("Danh sách thứ tự không hợp lệ.")
            ma = _ma_dich_vu(item.get("service_code"))
            gia_tri_thu_tu = item.get("thu_tu")
            if not isinstance(gia_tri_thu_tu, (int, str)) or isinstance(
                gia_tri_thu_tu, bool
            ):
                raise ValidationError("Thứ tự phải là số.")
            try:
                so = int(gia_tri_thu_tu)
            except (TypeError, ValueError):
                raise ValidationError("Thứ tự phải là số.") from None
            if not 0 <= so <= 9999:
                raise ValidationError("Thứ tự trong khoảng 0–9999.")
            ds.append((ma, so))
        if len({ma for ma, _ in ds}) != len(ds):
            raise ValidationError("Một dịch vụ chỉ được có một thứ tự.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CAU_HINH)
            da_sua = await conn.fetch(
                """
                UPDATE lam_them_tai_quay l
                   SET thu_tu = x.thu_tu, updated_by = $4::uuid, updated_at = now()
                  FROM unnest($2::text[], $3::integer[]) AS x(service_code, thu_tu)
                 WHERE l.clinic_id = $1::uuid AND l.service_code = x.service_code
                RETURNING l.service_code
                """,
                cid,
                [ma for ma, _ in ds],
                [so for _, so in ds],
                identity.staff_id,
            )
            if len(da_sua) != len(ds):
                raise NotFoundError("Có nút không còn trong danh sách — tải lại.")
            await record_event(
                conn,
                event_type="config.desk_services_reordered",
                aggregate_type="clinic",
                aggregate_id=cid,
                identity=identity,
                origin=ORIGIN,
                payload={"muc": [{"service_code": ma, "thu_tu": so} for ma, so in ds]},
            )
            ket_qua = await self._doc_muc(conn, cid)
        return {"ok": True, "muc": ket_qua}

    @staticmethod
    async def _doc_muc(conn: asyncpg.Connection, cid: str) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT l.service_code, l.nhan, l.bat, l.thu_tu, l.o_tiep_don,
                   l.o_sinh_hieu, dv.ten, dv.gia, dv.dang_ban
              FROM lam_them_tai_quay l
              LEFT JOIN LATERAL (
                   SELECT s.name AS ten, s.unit_price AS gia,
                          (s.active AND s.node_code IS NOT NULL) AS dang_ban
                     FROM service_price s
                    WHERE s.clinic_id = l.clinic_id AND s."group" = 'dich_vu'
                      AND s.service_code = l.service_code
                    ORDER BY s.active DESC LIMIT 1) dv ON true
             WHERE l.clinic_id = $1::uuid
             ORDER BY l.thu_tu, l.service_code
            """,
            cid,
        )
        return [
            {
                "service_code": r["service_code"],
                "nhan": r["nhan"],
                "nhan_hien": r["nhan"] or r["ten"] or r["service_code"],
                "ten": r["ten"],
                "gia": int(r["gia"]) if r["gia"] is not None else None,
                "bat": bool(r["bat"]),
                "thu_tu": int(r["thu_tu"]),
                "o_tiep_don": bool(r["o_tiep_don"]),
                "o_sinh_hieu": bool(r["o_sinh_hieu"]),
                # Bảng giá ngừng bán / bỏ bước làm → nút tự ẩn ở quầy.
                "dang_ban": bool(r["dang_ban"]),
            }
            for r in rows
        ]
