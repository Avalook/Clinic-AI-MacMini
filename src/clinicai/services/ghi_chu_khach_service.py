"""KHUNG PHẢI CỦA MỘT KHÁCH — ghi chú chung + tóm tắt "mọi thứ của khách".

Tuyền 27/09/2026: "khung làm việc của CSKH chưa dễ cho việc ghi chú và tự nhắc
lịch cho chính mình cho bệnh nhân này … Lễ tân cũng nên có … cần có chỗ xem hết
mọi thứ của khách đó ở màn của người đó để dễ quản lý, không miss gì."

Hai phần, cùng một cửa quyền:

* **Ghi chú** (`ghi_chu_khach`, migration 20260927000003): sổ CHỈ THÊM. Người ghi
  gỡ được dòng của chính mình (ẩn, còn dấu vết) — không ai sửa nội dung.
* **Tóm tắt**: đọc gom từ bảng sẵn có — lịch sắp tới / đã qua, lượt gần nhất,
  chỉ định chưa làm, tiền đã trả / còn phải thu, hẹn tái khám bác sĩ đặt, số ghi
  chú. Chỉ đọc; không có luật mới nào ở đây ngoài "cái gì tính là chưa làm / còn
  nợ", và hai luật ấy dùng lại đúng hàm của quầy thu (`tinh_hoa_don`).

CỬA QUYỀN: "Quản lý khách hàng" (`crm.manage`) HOẶC "Check-in khách"
(`reception.checkin.perform`) — đúng hai màn có khung này (CSKH, Tiếp đón).
Dữ liệu là thông tin VẬN HÀNH (lịch, tiền, tên dịch vụ), không có bệnh án.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import can
from clinicai.services.cskh_service import clinic_today
from clinicai.services.hen_tai_kham_service import chi_tiet_viec, tinh_trang

#: Quyền mở khung khách — có MỘT trong hai là đủ.
QUYEN_KHUNG_KHACH = ("crm.manage", "reception.checkin.perform")

_TRAN_GHI_CHU = 200
_DO_DAI_TOI_DA = 2000

#: Lịch "chết" — không còn là lịch sắp tới.
_LICH_KHONG_CON = ("CANCELLED", "NO_SHOW", "DOCTOR_DECLINED", "CHECKED_IN", "COMPLETED")
#: Chỉ định đã được cho phép làm mà chưa xong.
_CHUA_LAM = ("authorized", "assigned", "in_progress")


async def kiem_quyen_khung_khach(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> None:
    for q in QUYEN_KHUNG_KHACH:
        if await can(conn, identity, q):
            return
    raise SafetyGateError(
        "Bạn không có quyền “Quản lý khách hàng” hoặc “Check-in khách”."
    )


def lam_sach_noi_dung(raw: Any) -> str | None:
    """Nội dung ghi chú đã cắt khoảng trắng; rác / rỗng / quá dài → None. Thuần."""
    if not isinstance(raw, str):
        return None
    nd = raw.strip()
    if not 1 <= len(nd) <= _DO_DAI_TOI_DA:
        return None
    return nd


async def _kiem_khach(conn: asyncpg.Connection, clinic_id: str, pid: str) -> None:
    co = await conn.fetchval(
        "SELECT 1 FROM patient WHERE clinic_id = $1::uuid"
        " AND clinic_patient_id = $2::uuid",
        clinic_id,
        pid,
    )
    if co is None:
        raise NotFoundError("Không tìm thấy khách này.")


def _iso(v: datetime | date | None) -> str | None:
    return v.isoformat() if v is not None else None


def _so(v: Decimal | int | float | None) -> int:
    return int(v or 0)


class GhiChuKhachService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Ghi chú ────────────────────────────────────────────────────────────

    async def ghi(
        self, *, identity: StaffIdentity, clinic_patient_id: str, noi_dung: Any
    ) -> dict[str, Any]:
        nd = lam_sach_noi_dung(noi_dung)
        if nd is None:
            raise ValidationError(f"Ghi chú từ 1 đến {_DO_DAI_TOI_DA} ký tự.")
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_quyen_khung_khach(conn, identity)
            await _kiem_khach(conn, identity.clinic_id, clinic_patient_id)
            r = await conn.fetchrow(
                """
                INSERT INTO ghi_chu_khach
                    (clinic_id, clinic_patient_id, noi_dung, tao_boi_staff_id)
                VALUES ($1::uuid, $2::uuid, $3, $4::uuid)
                RETURNING id::text, tao_luc
                """,
                identity.clinic_id,
                clinic_patient_id,
                nd,
                identity.staff_id,
            )
        assert r is not None
        return {"ok": True, "id": r["id"], "tao_luc": r["tao_luc"].isoformat()}

    async def danh_sach(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await kiem_quyen_khung_khach(conn, identity)
            rows = await conn.fetch(
                """
                SELECT g.id::text AS id, g.noi_dung, g.tao_luc,
                       g.tao_boi_staff_id::text AS tao_boi,
                       s.full_name AS nguoi_ghi
                  FROM ghi_chu_khach g
                  LEFT JOIN staff s ON s.id = g.tao_boi_staff_id
                 WHERE g.clinic_id = $1::uuid
                   AND g.clinic_patient_id = $2::uuid
                   AND g.go_luc IS NULL
                 ORDER BY g.tao_luc DESC
                 LIMIT $3
                """,
                identity.clinic_id,
                clinic_patient_id,
                _TRAN_GHI_CHU,
            )
        canh_bao_neu_day("ghi_chu_khach.danh_sach", len(rows), _TRAN_GHI_CHU)
        return [
            {
                "id": r["id"],
                "noi_dung": r["noi_dung"],
                "tao_luc": r["tao_luc"].isoformat(),
                "nguoi_ghi": r["nguoi_ghi"],
                "cua_toi": r["tao_boi"] == identity.staff_id,
            }
            for r in rows
        ]

    async def go(self, *, identity: StaffIdentity, ghi_chu_id: str) -> dict[str, Any]:
        """Người ghi gỡ dòng của CHÍNH MÌNH. Một câu UPDATE có điều kiện — hai
        lần bấm trùng nhau thì lần sau không đổi gì và nhận 404, không gỡ hai lần."""
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_quyen_khung_khach(conn, identity)
            ma = await conn.fetchval(
                """
                UPDATE ghi_chu_khach
                   SET go_luc = now(), go_boi_staff_id = $3::uuid
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   AND tao_boi_staff_id = $3::uuid AND go_luc IS NULL
                RETURNING id::text
                """,
                identity.clinic_id,
                ghi_chu_id,
                identity.staff_id,
            )
        if ma is None:
            raise NotFoundError("Không tìm thấy ghi chú của bạn (hoặc đã gỡ).")
        return {"ok": True}

    # ── Tóm tắt mọi thứ của khách ─────────────────────────────────────────

    async def tom_tat(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        pid = clinic_patient_id
        # Import muộn: bill_service kéo cả chuỗi dịch vụ tiền — chỉ cần khi đọc.
        from clinicai.services.bill_service import tinh_hoa_don

        async with self._pool.acquire() as conn:
            await kiem_quyen_khung_khach(conn, identity)
            khach = await conn.fetchrow(
                """
                SELECT p.full_name, p.patient_code, p.phone_primary
                  FROM patient p
                 WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = $2::uuid
                """,
                cid,
                pid,
            )
            if khach is None:
                raise NotFoundError("Không tìm thấy khách này.")

            sap_toi = await conn.fetch(
                """
                SELECT a.id::text AS id, a.slot_start, a.status,
                       st.name AS dich_vu, d.full_name AS bac_si
                  FROM appointment a
                  LEFT JOIN service_type st ON st.id = a.service_type_id
                  LEFT JOIN staff d ON d.id = a.doctor_id
                 WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = $2::uuid
                   AND a.slot_start >= date_trunc('day', now() AT TIME ZONE
                                                  'Asia/Ho_Chi_Minh')
                                       AT TIME ZONE 'Asia/Ho_Chi_Minh'
                   AND a.status <> ALL($3::text[])
                 ORDER BY a.slot_start
                 LIMIT 5
                """,
                cid,
                pid,
                list(_LICH_KHONG_CON),
            )
            da_qua = await conn.fetch(
                """
                SELECT a.id::text AS id, a.slot_start, a.status,
                       st.name AS dich_vu, d.full_name AS bac_si,
                       a.cancellation_reason AS ly_do_huy
                  FROM appointment a
                  LEFT JOIN service_type st ON st.id = a.service_type_id
                  LEFT JOIN staff d ON d.id = a.doctor_id
                 WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = $2::uuid
                   AND (a.slot_start < now()
                        OR a.status IN ('CHECKED_IN', 'COMPLETED', 'CANCELLED',
                                        'NO_SHOW', 'DOCTOR_DECLINED'))
                 ORDER BY a.slot_start DESC
                 LIMIT 5
                """,
                cid,
                pid,
            )
            luot = await conn.fetch(
                """
                SELECT v.visit_id::text AS visit_id, v.status, v.checked_in_at,
                       v.closed_at, v.exam_completed_at,
                       st.name AS dich_vu, d.full_name AS bac_si,
                       coalesce(r.name, n.name) AS dang_o
                  FROM visit v
                  LEFT JOIN service_type st ON st.id = v.service_type_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN node_definition n
                    ON n.clinic_id = v.clinic_id AND n.code = v.current_node_code
                  LEFT JOIN clinic_room r
                    ON r.id = v.current_room_id AND r.clinic_id = v.clinic_id
                 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
                 ORDER BY coalesce(v.checked_in_at, v.created_at) DESC
                 LIMIT 5
                """,
                cid,
                pid,
            )
            chua_lam = await conn.fetch(
                """
                SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                       coalesce(o.service_name, o.service_code) AS ten,
                       o.exec_status, o.created_at, rm.name AS phong
                  FROM service_order o
                  JOIN visit v
                    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
                  LEFT JOIN clinic_room rm
                    ON rm.id = o.room_id AND rm.clinic_id = o.clinic_id
                 WHERE o.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
                   AND o.exec_status = ANY($3::text[])
                   AND coalesce(o.selection_status, 'SELECTED') <> 'NOT_SELECTED'
                 ORDER BY o.created_at DESC
                 LIMIT 20
                """,
                cid,
                pid,
                list(_CHUA_LAM),
            )
            da_tra = await conn.fetchrow(
                """
                SELECT coalesce(sum(pm.amount), 0) AS tong, count(*) AS so_lan,
                       max(pm.paid_at) AS lan_cuoi
                  FROM payment pm
                  JOIN visit v
                    ON v.visit_id = pm.visit_id AND v.clinic_id = pm.clinic_id
                 WHERE pm.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
                   AND pm.status = 'PAID' AND pm.voided_at IS NULL
                """,
                cid,
                pid,
            )
            # CÒN PHẢI THU: đúng hoá đơn quầy thu sẽ tính (`tinh_hoa_don`) cho
            # các lượt gần đây — tiền dịch vụ = hoá đơn còn nợ; tiền thuốc chỉ
            # khi lượt ấy chưa có phiếu thu thuốc.
            con_no: list[dict[str, Any]] = []
            for v in luot:
                vid = v["visit_id"]
                dv = await tinh_hoa_don(
                    conn, clinic_id=cid, visit_id=vid, kind="dich_vu"
                )
                if dv.tong > 0:
                    con_no.append(
                        {"visit_id": vid, "loai": "dich_vu", "so_tien": dv.tong}
                    )
                da_thu_thuoc = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM payment pm"
                    " WHERE pm.clinic_id = $1::uuid AND pm.visit_id = $2::uuid"
                    " AND pm.kind = 'thuoc' AND pm.status = 'PAID'"
                    " AND pm.voided_at IS NULL)",
                    cid,
                    vid,
                )
                if not da_thu_thuoc:
                    th = await tinh_hoa_don(
                        conn, clinic_id=cid, visit_id=vid, kind="thuoc"
                    )
                    if th.tong > 0:
                        con_no.append(
                            {"visit_id": vid, "loai": "thuoc", "so_tien": th.tong}
                        )
            # VIỆC TÁI KHÁM (29/09/2026): việc lượt 1 kèm đủ để gọi (bác sĩ, loại
            # khám + chẩn đoán lần trước, cần kiểm tra lại, ghi chú bác sĩ). Bỏ
            # các bản đã bị thay (bác sĩ đổi ngày / trùng việc khác) — chúng
            # chỉ là vết, nằm ở nhật ký.
            tai_kham = await conn.fetch(
                """
                SELECT n.id::text AS id, n.ngay_hen, n.han_goi, n.luot_goi,
                       n.trang_thai, n.ket_qua, n.ghi_chu, n.dong_vi,
                       n.nguon_visit_id::text AS nguon_visit_id,
                       d.full_name AS bac_si
                  FROM nhac_tai_kham n
                  LEFT JOIN visit v
                    ON v.visit_id = n.nguon_visit_id AND v.clinic_id = n.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                 WHERE n.clinic_id = $1::uuid AND n.clinic_patient_id = $2::uuid
                   AND n.luot_goi = 1
                   AND n.dong_vi IS DISTINCT FROM 'BS_DOI_NGAY'
                   AND n.dong_vi IS DISTINCT FROM 'TRUNG_VIEC'
                 ORDER BY (n.trang_thai = 'CHO_GOI') DESC, n.ngay_hen DESC
                 LIMIT 5
                """,
                cid,
                pid,
            )
            hom_nay = date.fromisoformat(clinic_today())
            chi_tiet_tk = {
                r["id"]: await chi_tiet_viec(conn, cid, r["nguon_visit_id"])
                for r in tai_kham
            }
            so_ghi_chu = await conn.fetchval(
                "SELECT count(*) FROM ghi_chu_khach WHERE clinic_id = $1::uuid"
                " AND clinic_patient_id = $2::uuid AND go_luc IS NULL",
                cid,
                pid,
            )

        return {
            "khach": {
                "id": pid,
                "ten": khach["full_name"],
                "ma": khach["patient_code"],
                "sdt": khach["phone_primary"],
            },
            "lich_sap_toi": [_lich(r) for r in sap_toi],
            "lich_da_qua": [{**_lich(r), "ly_do_huy": r["ly_do_huy"]} for r in da_qua],
            "luot_gan_nhat": [
                {
                    "visit_id": r["visit_id"],
                    "trang_thai": r["status"],
                    "check_in_luc": _iso(r["checked_in_at"]),
                    "kham_xong_luc": _iso(r["exam_completed_at"]),
                    "dong_luot_luc": _iso(r["closed_at"]),
                    "dich_vu": r["dich_vu"],
                    "bac_si": r["bac_si"],
                    "dang_o": r["dang_o"] if r["closed_at"] is None else None,
                }
                for r in luot
            ],
            "chi_dinh_chua_lam": [
                {
                    "id": r["id"],
                    "visit_id": r["visit_id"],
                    "ten": r["ten"],
                    "trang_thai": r["exec_status"],
                    "phong": r["phong"],
                    "luc": _iso(r["created_at"]),
                }
                for r in chua_lam
            ],
            "tien": {
                "da_tra": _so(da_tra["tong"]) if da_tra else 0,
                "so_lan_tra": int(da_tra["so_lan"]) if da_tra else 0,
                "tra_lan_cuoi": _iso(da_tra["lan_cuoi"]) if da_tra else None,
                "con_phai_thu": sum(x["so_tien"] for x in con_no),
                "con_phai_thu_chi_tiet": con_no,
            },
            "hen_tai_kham": [
                {
                    "id": r["id"],
                    "ngay_hen": _iso(r["ngay_hen"]),
                    "han_goi": _iso(r["han_goi"]),
                    "trang_thai": r["trang_thai"],
                    "ket_qua": r["ket_qua"],
                    "ghi_chu": r["ghi_chu"],
                    "bac_si": r["bac_si"],
                    "tinh_trang": tinh_trang(
                        r["trang_thai"], r["dong_vi"], r["han_goi"], hom_nay
                    ),
                    # Còn mở = CSKH còn phải gọi / đặt lịch (nút hiện theo cờ này).
                    "con_mo": r["trang_thai"] == "CHO_GOI",
                    "chi_tiet": chi_tiet_tk.get(r["id"]),
                }
                for r in tai_kham
            ],
            "so_ghi_chu": int(so_ghi_chu or 0),
        }


def _lich(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": r["id"],
        "luc": _iso(r["slot_start"]),
        "trang_thai": r["status"],
        "dich_vu": r["dich_vu"],
        "bac_si": r["bac_si"],
    }


__all__ = [
    "QUYEN_KHUNG_KHACH",
    "GhiChuKhachService",
    "kiem_quyen_khung_khach",
    "lam_sach_noi_dung",
]
