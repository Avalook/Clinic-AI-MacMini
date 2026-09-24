"""Danh sách khách cho màn Quản lý khách hàng (/customers) — 24/09/2026.

Trang từng tự đọc bảng `patient` + `appointment` bằng Supabase và tự dựng bộ lọc
(kỳ, theo ngày tạo / theo ngày hẹn, tìm tên không dấu, phân trang). Nay ở đây,
lọc đúng phòng khám người gọi. Hình dạng dòng giữ nguyên như PostgREST trả
(`patient_sdt_them: [{so_dien_thoai, loai}]`) để phần vẽ không phải đổi.

Luật giữ nguyên:
  * lọc THEO NGÀY HẸN = khách có lịch trong kỳ, BỎ lịch huỷ / không đến / bác sĩ
    từ chối — huỷ lịch xong khách không còn "có hẹn";
  * kỳ theo giờ Việt Nam; tuần bắt đầu thứ Hai;
  * khách được chuông trỏ tới (`selected`) mà nằm ngoài trang thì vẫn nạp riêng
    và đặt lên đầu.
Đầu vào rác (kỳ lạ, trang âm, mã khách hỏng) → mặc định, không ném.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ

KHACH_MOT_TRANG = 50
_LICH_CHET = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"]

#: Kênh đặt · người giới thiệu · lần ĐỔI / HUỶ lịch gần nhất kèm lý do (Tuyền
#: 24/09/2026: "cần đồng bộ hiện ở những chỗ này CSKH mới biết được"). Dùng
#: chung cho danh sách khách CSKH và danh sách bệnh nhân. Alias `p` = patient.
COT_KENH_DOI_HUY = """
    p.nguoi_gioi_thieu,
    (SELECT a.booking_channel FROM appointment a
      WHERE a.clinic_id = p.clinic_id
        AND a.clinic_patient_id = p.clinic_patient_id
      ORDER BY a.created_at DESC LIMIT 1) AS kenh_dat,
    (SELECT json_build_object('loai', x.loai, 'ly_do', x.ly_do, 'ma', x.ma,
                              'luc', x.luc)
       FROM (
            SELECT 'DOI' AS loai, d.ly_do, NULL::text AS ma, d.doi_luc AS luc
              FROM appointment_doi_lich d
              JOIN appointment a
                ON a.id = d.appointment_id AND a.clinic_id = d.clinic_id
             WHERE d.clinic_id = p.clinic_id
               AND a.clinic_patient_id = p.clinic_patient_id
            UNION ALL
            SELECT 'HUY', a.cancellation_reason, a.ly_do_huy_ma, a.cancelled_at
              FROM appointment a
             WHERE a.clinic_id = p.clinic_id
               AND a.clinic_patient_id = p.clinic_patient_id
               AND a.status = 'CANCELLED'
       ) x
      ORDER BY x.luc DESC NULLS LAST LIMIT 1) AS doi_huy_gan_nhat
"""

_COT = (
    """
    p.clinic_patient_id::text AS clinic_patient_id, p.patient_code, p.full_name,
    p.date_of_birth, p.birth_year, p.phone_primary, p.phone_secondary, p.gender,
    p.ethnicity, p.nationality, p.occupation, p.patient_objection, p.address,
    p.guardian_name, p.location_id::text AS location_id, p.created_at,
    p.van_de_di_kham, p.linh_vuc, p.updated_at, p.uu_tien, p.uu_tien_ly_do,
    coalesce((
        SELECT json_agg(json_build_object('so_dien_thoai', t.so_dien_thoai,
                                          'loai', t.loai))
          FROM patient_sdt_them t
         WHERE t.clinic_patient_id = p.clinic_patient_id
    ), '[]'::json) AS patient_sdt_them,
"""
    + COT_KENH_DOI_HUY
)


def cua_so(ky: str | None, bay_gio: datetime) -> tuple[datetime, datetime] | None:
    """[đầu, cuối) theo giờ VN cho kỳ lọc; None = tất cả (kể cả kỳ rác). Thuần."""
    dau_ngay = bay_gio.astimezone(CLINIC_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if ky == "today":
        return dau_ngay, dau_ngay + timedelta(days=1)
    if ky == "week":
        dau = dau_ngay - timedelta(days=dau_ngay.weekday())
        return dau, dau + timedelta(days=7)
    if ky == "month":
        dau = dau_ngay.replace(day=1)
        sau = (dau + timedelta(days=32)).replace(day=1)
        return dau, sau
    return None


def _chuoi_tim(q: str | None) -> str:
    """Bỏ ký tự đặc biệt của ILIKE (và của bộ lọc cũ) — rác → rỗng."""
    return re.sub(r"[,()%*_\\]", " ", (q or "")).strip()


def _ma(v: str | None) -> str | None:
    try:
        return str(UUID((v or "").strip()))
    except ValueError:
        return None


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in dict(r).items():
        if k == "tong":
            continue
        if k == "patient_sdt_them":
            d[k] = json.loads(v) if isinstance(v, str) else (v or [])
        elif k == "doi_huy_gan_nhat":
            d[k] = json.loads(v) if isinstance(v, str) else v
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
        else:
            d[k] = v
    return d


async def danh_sach_khach(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    q: str | None = None,
    ky: str | None = None,
    theo: str | None = None,
    trang: int = 1,
    chon: str | None = None,
) -> dict[str, Any]:
    cid = identity.clinic_id
    trang = max(1, trang)
    win = cua_so(ky, datetime.now(CLINIC_TZ))
    theo_hen = theo == "appt"
    t = _chuoi_tim(q)
    mau = f"%{t}%" if t else None
    rows = await pool.fetch(
        f"""
        SELECT {_COT}, count(*) OVER () AS tong
          FROM patient p
         WHERE p.clinic_id = $1::uuid
           AND ($2::timestamptz IS NULL OR $4 OR p.created_at >= $2)
           AND (NOT $4 OR $2::timestamptz IS NULL OR EXISTS (
                 SELECT 1 FROM appointment a
                  WHERE a.clinic_id = p.clinic_id
                    AND a.clinic_patient_id = p.clinic_patient_id
                    AND a.slot_start >= $2 AND a.slot_start < $3
                    AND a.status <> ALL($5::text[])))
           AND ($6::text IS NULL
                OR p.full_name ILIKE $6 OR p.patient_code ILIKE $6
                OR p.sdt_tim_kiem ILIKE $6
                OR p.full_name_unaccent ILIKE
                   '%' || lower(replace(replace(f_unaccent($7), 'đ', 'd'), 'Đ', 'D'))
                   || '%')
         ORDER BY p.created_at DESC
         OFFSET $8 LIMIT $9
        """,
        cid,
        win[0] if win else None,
        win[1] if win else None,
        theo_hen,
        _LICH_CHET,
        mau,
        t,
        (trang - 1) * KHACH_MOT_TRANG,
        KHACH_MOT_TRANG,
    )
    tong = int(rows[0]["tong"]) if rows else 0
    dong = [_dong(r) for r in rows]
    ma_chon = _ma(chon)
    if ma_chon and not any(d["clinic_patient_id"] == ma_chon for d in dong):
        mot = await pool.fetchrow(
            f"SELECT {_COT} FROM patient p"
            " WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = $2::uuid",
            cid,
            ma_chon,
        )
        if mot is not None:
            dong.insert(0, _dong(mot))
    return {"rows": dong, "total": tong}


__all__ = ["KHACH_MOT_TRANG", "cua_so", "danh_sach_khach"]
