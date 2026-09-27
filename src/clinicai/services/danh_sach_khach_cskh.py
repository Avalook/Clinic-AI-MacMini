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
  * XẾP THEO HOẠT ĐỘNG GẦN NHẤT (27/09/2026 đợt 3, A6), không theo ngày tạo hồ
    sơ — xem ``HOAT_DONG_GAN_NHAT``.
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


#: HOẠT ĐỘNG GẦN NHẤT của một khách (alias `p` = patient) — khoá xếp của màn
#: Quản lý khách hàng (27/09/2026 đợt 3, A6).
#:
#: Phòng khám: *"Danh sách BN nên hiển thị ngày gần nhất bên trên"*. Bản cũ xếp
#: theo `p.created_at`: khách tạo hồ sơ từ tháng trước, hôm nay quay lại khám,
#: nằm tít trang sau. Nay lấy mốc MỚI NHẤT trong:
#:   * ngày tạo hồ sơ;
#:   * lúc ĐẶT lịch gần nhất (`appointment.created_at`) — khách vừa gọi đặt lịch
#:     hôm nay là hoạt động hôm nay, dù ngày hẹn là tuần sau;
#:   * GIỜ HẸN gần nhất ĐÃ QUA và không chết (huỷ / không đến / BS từ chối) —
#:     giờ hẹn TƯƠNG LAI không tính: một lịch tái khám ba tháng tới không được
#:     ghim khách lên đầu suốt ba tháng;
#:   * lượt khám gần nhất (`visit.created_at`).
#: `greatest` bỏ qua NULL, nên khách mới chưa có lịch/lượt rơi về ngày tạo.
#: Mỗi câu con đi index `idx_appointment_patient` / `idx_visit_patient`.
HOAT_DONG_GAN_NHAT = """
    greatest(
        p.created_at,
        (SELECT max(a.created_at) FROM appointment a
          WHERE a.clinic_id = p.clinic_id
            AND a.clinic_patient_id = p.clinic_patient_id),
        (SELECT max(a.slot_start) FROM appointment a
          WHERE a.clinic_id = p.clinic_id
            AND a.clinic_patient_id = p.clinic_patient_id
            AND a.slot_start <= now()
            AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED')),
        (SELECT max(v.created_at) FROM visit v
          WHERE v.clinic_id = p.clinic_id
            AND v.clinic_patient_id = p.clinic_patient_id)
    )
"""


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


#: Khoảng ngày tự chọn dài nhất (thanh ngày ngang, 27/09/2026). Quá thì cắt
#: về ``den`` − 366 ngày — không ném.
KHOANG_TOI_DA_NGAY = 366


def _ngay(v: Any) -> date | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        return date.fromisoformat(v.strip()[:10])
    except ValueError:
        return None


def cua_so_khoang(tu: Any, den: Any) -> tuple[datetime, datetime] | None:
    """[đầu ngày ``tu``, đầu ngày sau ``den``) theo giờ VN — khoảng tuỳ chọn của
    thanh ngày ngang (Tuyền 27/09: "xem khách hôm qua, hôm kia, tuần trước…").

    Thuần; rác → rỗng, KHÔNG ném (CLAUDE.md: ba lần 500 vì hàm ngày ném):
      * cả hai rác / rỗng → None (= không lọc theo khoảng, dùng ``ky``);
      * thiếu một đầu → khoảng một ngày của đầu còn lại;
      * ``den`` trước ``tu`` → đổi chỗ;
      * dài quá ``KHOANG_TOI_DA_NGAY`` → cắt, giữ ``den``.
    """
    a, b = _ngay(tu), _ngay(den)
    if a is None and b is None:
        return None
    a = a or b
    b = b or a
    assert a is not None and b is not None
    if b < a:
        a, b = b, a
    if (b - a).days > KHOANG_TOI_DA_NGAY:
        a = b - timedelta(days=KHOANG_TOI_DA_NGAY)
    dau = datetime(a.year, a.month, a.day, tzinfo=CLINIC_TZ)
    cuoi = datetime(b.year, b.month, b.day, tzinfo=CLINIC_TZ) + timedelta(days=1)
    return dau, cuoi


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
    tu: str | None = None,
    den: str | None = None,
) -> dict[str, Any]:
    cid = identity.clinic_id
    trang = max(1, trang)
    # Khoảng tự chọn (``tu``/``den``) thắng kỳ đặt sẵn (``ky``); rác → dùng ``ky``.
    win = cua_so_khoang(tu, den) or cua_so(ky, datetime.now(CLINIC_TZ))
    theo_hen = theo == "appt"
    t = _chuoi_tim(q)
    mau = f"%{t}%" if t else None
    rows = await pool.fetch(
        f"""
        SELECT {_COT}, hd.luc AS hoat_dong_gan_nhat, count(*) OVER () AS tong
          FROM patient p
          CROSS JOIN LATERAL (SELECT {HOAT_DONG_GAN_NHAT} AS luc) hd
         WHERE p.clinic_id = $1::uuid
           AND ($2::timestamptz IS NULL OR $4
                OR (p.created_at >= $2 AND p.created_at < $3))
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
         -- Hoạt động gần nhất lên trên; mã khách là khoá phụ để hai khách cùng
         -- mốc không đổi chỗ giữa hai lần tải → phân trang không lặp / sót.
         ORDER BY hd.luc DESC, p.clinic_patient_id
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


__all__ = [
    "HOAT_DONG_GAN_NHAT",
    "KHACH_MOT_TRANG",
    "KHOANG_TOI_DA_NGAY",
    "cua_so",
    "cua_so_khoang",
    "danh_sach_khach",
]
