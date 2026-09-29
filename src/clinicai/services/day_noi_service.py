"""KHỐI CHỈNH DÂY — quản lý chỉnh dây nối nghiệp vụ trên màn (nhóm 5, 24/09/2026).

Tuyền chốt: "Đường nối H1–H8 phải CUSTOM được (không khoá cứng)"; "Tuyền hỏi: có
nên xây một khối chuyên điều chỉnh khối nào nhận event nào không" → đây.

Chỉnh được (dây NGHIỆP VỤ):
  * loại khám nào qua bác sĩ tư vấn (H1), loại lịch nào đi thẳng phòng (H2);
  * bật/tắt tự xếp phòng sau khi thu tiền (H4), báo CSKH khi khách về còn việc
    (H6), số ngày kết quả đối tác quá hạn (H7), số phút nhắc check-out (H8);
  * ai nhận chuông cho sự kiện nào (vai + bác sĩ chính đích danh + bật/tắt);
  * vị trí trực: thêm, đổi tên, gắn phòng, bật/tắt.
KHOÁ trong code (dây LÕI): dòng thời gian, trách nhiệm tiền, thứ tự khoá.

Mọi lệnh hỏi QUYỀN `config.wiring.manage` trong chính giao dịch, và ghi nhật ký
thao tác (ai đổi dây nào thành gì, lúc nào).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.day_noi import DAY, doc_day

QUYEN = "config.wiring.manage"
ORIGIN = "api:day-noi"
EVENT = "config.wiring_changed"

#: Nhóm nghề của một vị trí trực (ràng buộc `vi_tri_lam_viec_nhom_check`).
NHOM_NGHE = ("BAC_SI", "DIEU_DUONG", "DOI_TAC", "CHUNG")

#: Vai được chọn làm người nhận chuông (vai nội bộ).
VAI_NHAN_DUOC: tuple[str, ...] = (
    "CSKH",
    "RECEPTION",
    "TKYK",
    "DOCTOR",
    "ULTRASOUND_DOCTOR",
    "NURSE_ULTRASOUND",
    "TRUONG_CA",
    "MANAGEMENT",
    "CASHIER",
    "PHARMACIST",
)

#: Nhãn sự kiện chuông cho màn (chỉ các sự kiện khối Chuông nghe).
NHAN_CHUONG: dict[str, str] = {
    "result_file.uploaded": "Tệp kết quả về",
    "result_file.confirmed": "Tệp kết quả đối tác được xác nhận hợp lệ",
    "result.ready": "Phòng hoàn tất phiếu kết quả",
    "result.corrected": "Phòng sửa lại phiếu kết quả đã công bố",
    "lab_result.arrived": "Kết quả xét nghiệm nhập tay về",
}


class DayNoiService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, identity: StaffIdentity) -> dict[str, Any]:
        from clinicai.events.consumers.chuong import day_nhan

        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN)
            day = [
                {
                    "ma": d.ma,
                    "nhan": d.nhan,
                    "kieu": d.kieu,
                    "gia_tri": await doc_day(conn, cid, d.ma),
                    "mac_dinh": d.mac_dinh,
                    "nho_nhat": d.nho_nhat,
                    "lon_nhat": d.lon_nhat,
                    "don_vi": d.don_vi,
                }
                for d in DAY.values()
            ]
            loai_kham = [
                dict(r)
                for r in await conn.fetch(
                    "SELECT id::text AS id, code, name, qua_tu_van, di_thang_phong"
                    " FROM service_type WHERE clinic_id = $1::uuid AND is_active"
                    " ORDER BY name",
                    cid,
                )
            ]
            chuong = []
            for su_kien, nhan in NHAN_CHUONG.items():
                d = await day_nhan(conn, cid, su_kien)
                chuong.append(
                    {
                        "su_kien": su_kien,
                        "nhan": nhan,
                        "vai": list(d.vai) if d else [],
                        "bac_si_chinh": bool(d.bac_si_chinh) if d else False,
                        "bat": bool(d.bat) if d else False,
                    }
                )
            vi_tri = [
                dict(r)
                for r in await conn.fetch(
                    "SELECT id::text AS id, code, ten, ten_ngan, tang, nhom_nghe,"
                    "       room_id::text AS room_id, is_active"
                    "  FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid"
                    " ORDER BY is_active DESC, sort, ten",
                    cid,
                )
            ]
            phong = [
                dict(r)
                for r in await conn.fetch(
                    "SELECT id::text AS id, name FROM clinic_room"
                    " WHERE clinic_id = $1::uuid AND is_active ORDER BY sort, name",
                    cid,
                )
            ]
        return {
            "day": day,
            "loai_kham": loai_kham,
            "chuong": chuong,
            "vai_nhan": list(VAI_NHAN_DUOC),
            "vi_tri": vi_tri,
            "phong": phong,
            "nhom_nghe": list(NHOM_NGHE),
        }

    async def _ghi_nhat_ky(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        payload: dict[str, Any],
    ) -> None:
        await record_event(
            conn,
            event_type=EVENT,
            aggregate_type="clinic",
            aggregate_id=identity.clinic_id,
            identity=identity,
            origin=ORIGIN,
            payload=payload,
        )

    async def dat_day(
        self, *, identity: StaffIdentity, ma: str, gia_tri: Any
    ) -> dict[str, Any]:
        day = DAY.get(ma)
        if day is None:
            raise ValidationError(f"Không có dây {ma!r}.")
        if day.kieu == "bat_tat":
            if not isinstance(gia_tri, bool):
                raise ValidationError("Dây này chỉ nhận bật / tắt.")
            moi: Any = gia_tri
        else:
            if isinstance(gia_tri, bool) or not isinstance(gia_tri, int):
                raise ValidationError("Dây này nhận một số nguyên.")
            if not day.nho_nhat <= gia_tri <= day.lon_nhat:
                raise ValidationError(
                    f"Giá trị phải từ {day.nho_nhat} đến {day.lon_nhat} {day.don_vi}."
                )
            moi = gia_tri
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN)
            cu = await doc_day(conn, identity.clinic_id, ma)
            await conn.execute(
                """
                INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri, sua_boi, sua_luc)
                VALUES ($1::uuid, $2, $3::jsonb, $4::uuid, now())
                ON CONFLICT (clinic_id, ma) DO UPDATE
                   SET gia_tri = EXCLUDED.gia_tri, sua_boi = EXCLUDED.sua_boi,
                       sua_luc = now()
                """,
                identity.clinic_id,
                ma,
                json.dumps(moi),
                identity.staff_id,
            )
            await self._ghi_nhat_ky(conn, identity, {"day": ma, "tu": cu, "thanh": moi})
        return {"ok": True, "ma": ma, "gia_tri": moi}

    async def dat_loai_kham(
        self,
        *,
        identity: StaffIdentity,
        service_type_id: str,
        qua_tu_van: bool | None = None,
        di_thang_phong: bool | None = None,
    ) -> dict[str, Any]:
        if qua_tu_van is None and di_thang_phong is None:
            raise ValidationError("Không có gì để đổi.")
        if qua_tu_van and di_thang_phong:
            raise ValidationError(
                "Một loại không vừa qua tư vấn vừa đi thẳng phòng được."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN)
            row = await conn.fetchrow(
                """
                UPDATE service_type
                   SET qua_tu_van = coalesce($3, qua_tu_van),
                       di_thang_phong = coalesce($4, di_thang_phong)
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                RETURNING id::text, name, qua_tu_van, di_thang_phong
                """,
                identity.clinic_id,
                service_type_id,
                qua_tu_van,
                di_thang_phong,
            )
            if row is None:
                raise NotFoundError("Không tìm thấy loại khám này.")
            if row["qua_tu_van"] and row["di_thang_phong"]:
                raise ValidationError(
                    "Một loại không vừa qua tư vấn vừa đi thẳng phòng được."
                )
            await self._ghi_nhat_ky(
                conn,
                identity,
                {
                    "loai_kham": row["id"],
                    "qua_tu_van": row["qua_tu_van"],
                    "di_thang_phong": row["di_thang_phong"],
                },
            )
        return {"ok": True, **dict(row)}

    async def dat_chuong(
        self,
        *,
        identity: StaffIdentity,
        su_kien: str,
        vai: list[str],
        bac_si_chinh: bool,
        bat: bool,
    ) -> dict[str, Any]:
        if su_kien not in NHAN_CHUONG:
            raise ValidationError(f"Sự kiện {su_kien!r} không có chuông.")
        la = [v for v in vai if v not in VAI_NHAN_DUOC]
        if la:
            raise ValidationError("Vai không hợp lệ: " + ", ".join(la))
        for v in vai:
            ClinicRole(v)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN)
            await conn.execute(
                """
                INSERT INTO day_nhan_thong_bao
                    (clinic_id, su_kien, vai, bac_si_chinh, bat, sua_boi, sua_luc)
                VALUES ($1::uuid, $2, $3::text[], $4, $5, $6::uuid, now())
                ON CONFLICT (clinic_id, su_kien) DO UPDATE
                   SET vai = EXCLUDED.vai, bac_si_chinh = EXCLUDED.bac_si_chinh,
                       bat = EXCLUDED.bat, sua_boi = EXCLUDED.sua_boi,
                       sua_luc = now()
                """,
                identity.clinic_id,
                su_kien,
                sorted(set(vai)),
                bac_si_chinh,
                bat,
                identity.staff_id,
            )
            await self._ghi_nhat_ky(
                conn,
                identity,
                {
                    "chuong": su_kien,
                    "vai": sorted(set(vai)),
                    "bac_si_chinh": bac_si_chinh,
                    "bat": bat,
                },
            )
        return {"ok": True}

    async def tao_vi_tri(
        self,
        *,
        identity: StaffIdentity,
        ten: str,
        nhom_nghe: str,
        ten_ngan: str | None = None,
        tang: str | None = None,
        room_id: str | None = None,
    ) -> dict[str, Any]:
        ten = (ten or "").strip()
        if not 1 <= len(ten) <= 120:
            raise ValidationError("Tên vị trí phải từ 1 đến 120 ký tự.")
        if nhom_nghe not in NHOM_NGHE:
            raise ValidationError("Nhóm nghề không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN)
            await self._kiem_phong(conn, identity.clinic_id, room_id)
            vid = await conn.fetchval(
                """
                INSERT INTO vi_tri_lam_viec
                    (clinic_id, code, ten, ten_ngan, tang, nhom_nghe, room_id, sort,
                     is_active)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::uuid,
                        coalesce((SELECT max(sort) + 1 FROM vi_tri_lam_viec
                                   WHERE clinic_id = $1::uuid), 1), true)
                RETURNING id::text
                """,
                identity.clinic_id,
                # Mã nội bộ tự sinh, không hiện — người dùng chỉ thấy tên.
                f"VT-{uuid.uuid4().hex[:8]}",
                ten,
                (ten_ngan or "").strip() or None,
                (tang or "").strip() or None,
                nhom_nghe,
                room_id,
            )
            await self._ghi_nhat_ky(conn, identity, {"vi_tri_moi": vid, "ten": ten})
        # Quyền theo lịch đọc vị trí → phòng — đổi thì quên quyền đang nhớ.
        cache.quen(identity.clinic_id)
        return {"ok": True, "id": vid}

    async def sua_vi_tri(
        self,
        *,
        identity: StaffIdentity,
        vi_tri_id: str,
        ten: str | None = None,
        ten_ngan: str | None = None,
        tang: str | None = None,
        room_id: str | None = None,
        bo_phong: bool = False,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        if ten is not None and not 1 <= len(ten.strip()) <= 120:
            raise ValidationError("Tên vị trí phải từ 1 đến 120 ký tự.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN)
            await self._kiem_phong(conn, identity.clinic_id, room_id)
            row = await conn.fetchrow(
                """
                UPDATE vi_tri_lam_viec
                   SET ten = coalesce($3, ten),
                       ten_ngan = CASE WHEN $4::text IS NULL THEN ten_ngan
                                       ELSE nullif(btrim($4), '') END,
                       tang = CASE WHEN $5::text IS NULL THEN tang
                                   ELSE nullif(btrim($5), '') END,
                       room_id = CASE WHEN $7 THEN NULL
                                      ELSE coalesce($6::uuid, room_id) END,
                       is_active = coalesce($8, is_active)
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                RETURNING id::text, ten, is_active
                """,
                identity.clinic_id,
                vi_tri_id,
                ten.strip() if ten is not None else None,
                ten_ngan,
                tang,
                room_id,
                bo_phong,
                is_active,
            )
            if row is None:
                raise NotFoundError("Không tìm thấy vị trí này.")
            await self._ghi_nhat_ky(
                conn,
                identity,
                {"vi_tri": vi_tri_id, "ten": row["ten"], "bat": row["is_active"]},
            )
        # Quyền theo lịch đọc vị trí → phòng — đổi thì quên quyền đang nhớ.
        cache.quen(identity.clinic_id)
        return {"ok": True, **dict(row)}

    @staticmethod
    async def _kiem_phong(
        conn: asyncpg.Connection, clinic_id: str, room_id: str | None
    ) -> None:
        if room_id is None:
            return
        if not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_room WHERE clinic_id = $1::uuid"
            " AND id = $2::uuid)",
            clinic_id,
            room_id,
        ):
            raise ValidationError("Phòng không thuộc phòng khám này.")


__all__ = ["NHAN_CHUONG", "QUYEN", "VAI_NHAN_DUOC", "DayNoiService"]
