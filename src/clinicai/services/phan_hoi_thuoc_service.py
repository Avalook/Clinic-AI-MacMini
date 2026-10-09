"""PHẢN HỒI SAU DÙNG THUỐC — CSKH ghi, bác sĩ đọc (10/10/2026).

Khách: "CSKH ghi phản hồi sau dùng thuốc vào bước chăm sóc khách như đang làm.
Phản hồi nằm trong hồ sơ khách và quản lý khách hàng, bác sĩ mở hồ sơ là thấy,
cần tư vấn thêm thì CSKH đặt lịch khám như bình thường."

* Một phản hồi = MỘT dòng sổ chăm sóc `tuong_tac_cskh` loại ``PHAN_HOI_THUOC``,
  gắn ``visit_id`` của lượt CÓ ĐƠN THUỐC (bác sĩ kê, chưa gỡ). Không chọn lượt
  → lượt có đơn gần nhất. Nội dung bắt buộc.
* Cửa quyền = khung khách (`ghi_chu_khach_service.QUYEN_KHUNG_KHACH`).
* Hoàn tác như ghi chú khách: NGƯỜI GHI gỡ dòng của mình (`huy_luc`, còn dấu
  vết) — `tuong_tac_cskh_service.hoan_tac` cũng giữ đúng luật này.
* Bác sĩ chỉ đọc: `doc_theo_luot` gắn phản hồi vào lượt ở Bàn khám (lượt khám
  trước + popup Lịch sử khám) — người gọi tự gác quyền đọc hồ sơ.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import CskhDaLienHe
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.audit import record_event
from clinicai.services.ghi_chu_khach_service import (
    kiem_quyen_khung_khach,
    lam_sach_noi_dung,
)

LOAI = "PHAN_HOI_THUOC"
#: Kênh nhận phản hồi — tập con của KENH_HOP_LE (không có KHONG_LIEN_HE).
KENH = frozenset({"GOI", "ZALO", "SMS", "TRUC_TIEP"})
_TRAN_LUOT = 20
_TRAN_PHAN_HOI = 100

#: Lượt CÓ ĐƠN = còn ít nhất một dòng thuốc bác sĩ kê chưa gỡ.
_CO_DON_SQL = """
EXISTS (SELECT 1 FROM prescription p
         WHERE p.clinic_id = v.clinic_id AND p.visit_id = v.visit_id
           AND p.removed_at IS NULL AND p.nguon = 'BAC_SI')
"""

_PHAN_HOI_SQL = """
SELECT t.id::text AS id, t.visit_id::text AS visit_id, t.noi_dung, t.kenh,
       t.xay_ra_luc, t.nhan_vien_staff_id::text AS tao_boi,
       s.full_name AS nguoi_ghi,
       coalesce(v.checked_in_at, v.created_at) AS luot_luc
  FROM tuong_tac_cskh t
  JOIN visit v ON v.visit_id = t.visit_id AND v.clinic_id = t.clinic_id
  LEFT JOIN staff s ON s.id = t.nhan_vien_staff_id
 WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid
   AND t.loai = 'PHAN_HOI_THUOC' AND t.huy_luc IS NULL
 ORDER BY t.xay_ra_luc DESC
 LIMIT $3
"""


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v is not None else None


def _dong(r: asyncpg.Record, staff_id: str | None) -> dict[str, Any]:
    return {
        "id": r["id"],
        "visit_id": r["visit_id"],
        "noi_dung": r["noi_dung"],
        "kenh": r["kenh"],
        "luc": _iso(r["xay_ra_luc"]),
        "luot_luc": _iso(r["luot_luc"]),
        "nguoi_ghi": r["nguoi_ghi"],
        "cua_toi": staff_id is not None and r["tao_boi"] == staff_id,
    }


async def doc_theo_luot(
    conn: asyncpg.Connection, clinic_id: str, clinic_patient_id: str
) -> dict[str, list[dict[str, Any]]]:
    """{visit_id: [phản hồi mới nhất trước]} — cho màn bác sĩ (chỉ đọc)."""
    rows = await conn.fetch(_PHAN_HOI_SQL, clinic_id, clinic_patient_id, _TRAN_PHAN_HOI)
    ra: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ra.setdefault(r["visit_id"], []).append(_dong(r, None))
    return ra


class PhanHoiThuocService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> dict[str, Any]:
        """Lượt có đơn (để chọn, mới nhất trước) + các phản hồi còn hiệu lực."""
        async with self._pool.acquire() as conn:
            await kiem_quyen_khung_khach(conn, identity)
            luot = await conn.fetch(
                f"""
                SELECT v.visit_id::text AS visit_id,
                       coalesce(v.checked_in_at, v.created_at) AS luc,
                       d.full_name AS bac_si,
                       (SELECT string_agg(coalesce(p.drug_name_raw, c.name_raw), ', '
                                          ORDER BY p.created_at)
                          FROM prescription p
                          LEFT JOIN drug_catalog c
                            ON c.id = p.drug_catalog_id AND c.clinic_id = p.clinic_id
                         WHERE p.clinic_id = v.clinic_id AND p.visit_id = v.visit_id
                           AND p.removed_at IS NULL AND p.nguon = 'BAC_SI') AS thuoc
                  FROM visit v
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
                   AND {_CO_DON_SQL}
                 ORDER BY luc DESC
                 LIMIT $3
                """,
                identity.clinic_id,
                clinic_patient_id,
                _TRAN_LUOT,
            )
            phan_hoi = await conn.fetch(
                _PHAN_HOI_SQL, identity.clinic_id, clinic_patient_id, _TRAN_PHAN_HOI
            )
        return {
            "luot_co_don": [
                {
                    "visit_id": r["visit_id"],
                    "luc": _iso(r["luc"]),
                    "bac_si": r["bac_si"],
                    "thuoc": r["thuoc"],
                }
                for r in luot
            ],
            "items": [_dong(r, identity.staff_id) for r in phan_hoi],
        }

    async def ghi(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        noi_dung: Any,
        visit_id: str | None = None,
        kenh: str = "GOI",
    ) -> dict[str, Any]:
        nd = lam_sach_noi_dung(noi_dung)
        if nd is None:
            raise ValidationError("Ghi nội dung phản hồi của khách (1–2000 ký tự).")
        if kenh not in KENH:
            raise ValidationError(f"Kênh không hợp lệ: {kenh!r}.")
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_quyen_khung_khach(conn, identity)
            co_khach = await conn.fetchval(
                "SELECT 1 FROM patient WHERE clinic_id = $1::uuid"
                " AND clinic_patient_id = $2::uuid",
                identity.clinic_id,
                clinic_patient_id,
            )
            if co_khach is None:
                raise NotFoundError("Không tìm thấy khách này.")
            # Chọn lượt: lượt gửi lên phải là của khách này VÀ có đơn; không gửi
            # → lượt có đơn gần nhất. Không lượt nào có đơn thì không có gì để
            # phản hồi — báo rõ thay vì ghi một dòng treo lơ lửng.
            luot = await conn.fetchval(
                f"""
                SELECT v.visit_id::text FROM visit v
                 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
                   AND ($3::uuid IS NULL OR v.visit_id = $3::uuid)
                   AND {_CO_DON_SQL}
                 ORDER BY coalesce(v.checked_in_at, v.created_at) DESC
                 LIMIT 1
                """,
                identity.clinic_id,
                clinic_patient_id,
                visit_id,
            )
            if luot is None:
                raise ValidationError(
                    "Lượt này không có đơn thuốc của khách."
                    if visit_id
                    else "Khách chưa có lượt khám nào có đơn thuốc."
                )
            row_id = await conn.fetchval(
                """
                INSERT INTO tuong_tac_cskh
                    (clinic_id, clinic_patient_id, visit_id, loai, kenh, ket_qua,
                     noi_dung, nhan_vien_staff_id)
                VALUES ($1::uuid, $2::uuid, $3::uuid, 'PHAN_HOI_THUOC', $4,
                        'DA_LIEN_HE', $5, $6::uuid)
                RETURNING id::text
                """,
                identity.clinic_id,
                clinic_patient_id,
                luot,
                kenh,
                nd,
                identity.staff_id,
            )
            await emit_event(
                conn,
                ten="patient.contacted",
                clinic_id=identity.clinic_id,
                aggregate_id=clinic_patient_id,
                payload=CskhDaLienHe(
                    clinic_patient_id=clinic_patient_id,
                    loai=LOAI,
                    ket_qua="DA_LIEN_HE",
                ),
                boi=nguoi(identity),
            )
        return {"ok": True, "id": row_id, "visit_id": luot}

    async def go(self, *, identity: StaffIdentity, phan_hoi_id: str) -> dict[str, Any]:
        """Người ghi gỡ phản hồi của CHÍNH MÌNH — ẩn, còn dấu vết (`huy_luc`).
        Một câu UPDATE có điều kiện: bấm trùng thì lần sau nhận 404."""
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_quyen_khung_khach(conn, identity)
            khach = await conn.fetchval(
                """
                UPDATE tuong_tac_cskh
                   SET huy_luc = now(), huy_boi_staff_id = $3::uuid
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   AND loai = 'PHAN_HOI_THUOC'
                   AND nhan_vien_staff_id = $3::uuid AND huy_luc IS NULL
                RETURNING clinic_patient_id::text
                """,
                identity.clinic_id,
                phan_hoi_id,
                identity.staff_id,
            )
            if khach is None:
                raise NotFoundError("Không tìm thấy phản hồi của bạn (hoặc đã gỡ).")
            await record_event(
                conn,
                event_type="cskh.tuong_tac_hoan_tac",
                aggregate_type="patient",
                aggregate_id=khach,
                identity=identity,
                origin="cskh.customers",
                payload={"tuong_tac_id": phan_hoi_id, "loai": LOAI},
            )
        return {"ok": True}


__all__ = ["KENH", "LOAI", "PhanHoiThuocService", "doc_theo_luot"]
