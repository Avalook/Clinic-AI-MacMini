"""Bộ lọc danh sách bệnh nhân — "khách nào khớp ô tìm + tab, trong phạm vi người gọi".

MỘT chỗ cho hai người dùng (11/11/2026): màn Danh sách bệnh nhân
(`danh_sach_benh_nhan_service`, phân trang) và file Excel địa chỉ khách
(`xuat_dia_chi_khach`). Tách khỏi tệp màn vì tệp ấy đã chạm trần 400 dòng, và để
người dùng thứ hai không phải import tên riêng (`_CO_SO`) của module khác. Đổi tham số
$1–$7 ở đây là đổi cho cả hai — bài `test_loc_khop_dung_man_danh_sach` canh.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.thu_ky_bac_si import khach_duoc_xem

#: Tab của màn (``?loc=``) → (số lượt tối thiểu, tối đa). Cùng ngưỡng với
#: ``phan_loai``. Không có / lạ = tất cả.
LOC_THEO_SO_LUOT: dict[str, tuple[int, int | None]] = {
    "lan-dau": (1, 1),
    "tai-kham": (2, None),
    "chua-kham": (0, 0),
}

# CƠ SỞ CỦA MỌI CÂU: mỗi hồ sơ người gọi được xem, kèm số lượt, đang mở, mốc
# hoạt động gần nhất (``luc``) và có khớp ô tìm + tab không (``khop``).
#
# ``luc`` = coalesce(LƯỢT gần nhất, LỊCH gần nhất, ngày tạo hồ sơ). Phòng khám
# 27/09/2026: *"Danh sách BN nên hiển thị ngày gần nhất bên trên"*. Màn lâm
# sàng nên lượt khám thật đứng trước:
#   * lượt = `visit.created_at`, hoặc giờ hẹn của lịch khách ĐÃ TỚI
#     (CHECKED_IN / COMPLETED — đúng định nghĩa "một lượt khám");
#   * lịch = lúc ĐẶT lịch gần nhất, hoặc giờ hẹn ĐÃ QUA còn sống. Giờ hẹn
#     TƯƠNG LAI không tính — tái khám ba tháng tới không ghim khách lên đầu;
#   * chưa có gì → ngày tạo hồ sơ (khách mới vẫn lên đầu ngày tạo).
# Gộp MỘT lần theo khách (``lh``/``vs``, hash join) thay vì bốn câu con cho từng
# hồ sơ như bản trước: 8.700 hồ sơ × 4 câu con mới là thứ làm chậm trang.
#
# Tham số: $1 clinic · $2 mã khách được xem (NULL = không lọc) · $3 mẫu ILIKE ·
# $4 chuỗi tìm (bỏ dấu ở SQL) · $5 mẫu chỉ-số cho SĐT · $6/$7 số lượt min/max.
CO_SO_SQL = """
WITH lh AS (
    SELECT a.clinic_patient_id,
           count(*) FILTER (WHERE a.status IN ('CHECKED_IN', 'COMPLETED'))
               AS so_luot,
           bool_or(a.status = 'CHECKED_IN' AND v.closed_at IS NULL) AS dang_mo,
           max(a.slot_start) FILTER (WHERE a.status IN ('CHECKED_IN', 'COMPLETED'))
               AS den_gan_nhat,
           max(a.created_at) AS dat_gan_nhat,
           max(a.slot_start) FILTER (
               WHERE a.slot_start <= now()
                 AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'))
               AS hen_da_qua
      FROM appointment a
      -- Một lịch có tối đa một lượt (uq_visit_appointment_id) → không nhân dòng.
      LEFT JOIN visit v
        ON v.clinic_id = a.clinic_id AND v.appointment_id = a.id
     WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id IS NOT NULL
     GROUP BY a.clinic_patient_id
), vs AS (
    SELECT v.clinic_patient_id, max(v.created_at) AS luot_gan_nhat
      FROM visit v
     WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id IS NOT NULL
     GROUP BY v.clinic_patient_id
), co_so AS (
    SELECT p.clinic_patient_id,
           coalesce(lh.so_luot, 0) AS so_luot,
           coalesce(lh.dang_mo, false) AS dang_mo,
           coalesce(greatest(vs.luot_gan_nhat, lh.den_gan_nhat),
                    greatest(lh.dat_gan_nhat, lh.hen_da_qua),
                    p.created_at) AS luc,
           ($3::text IS NULL
            OR p.full_name ILIKE $3 OR p.patient_code ILIKE $3
            OR p.sdt_tim_kiem ILIKE $3
            OR p.full_name_unaccent ILIKE
               '%' || lower(replace(replace(f_unaccent($4), 'đ', 'd'), 'Đ', 'D'))
               || '%'
            OR ($5::text IS NOT NULL AND p.sdt_tim_kiem LIKE $5))
           AND coalesce(lh.so_luot, 0) >= $6
           AND ($7::int IS NULL OR coalesce(lh.so_luot, 0) <= $7) AS khop
      FROM patient p
      LEFT JOIN lh ON lh.clinic_patient_id = p.clinic_patient_id
      LEFT JOIN vs ON vs.clinic_patient_id = p.clinic_patient_id
     WHERE p.clinic_id = $1::uuid
       AND ($2::text[] IS NULL OR p.clinic_patient_id::text = ANY($2::text[]))
)
"""


def doc_loc(v: Any) -> str | None:
    """``?loc=`` → khoá tab trong ``LOC_THEO_SO_LUOT``; lạ / rỗng → None (tất cả)."""
    k = str(v or "").strip()
    return k if k in LOC_THEO_SO_LUOT else None


def chuoi_tim(q: Any) -> str:
    """Bỏ ký tự đặc biệt của ILIKE, gộp khoảng trắng, cắt 100 ký tự. Rác → rỗng."""
    t = re.sub(r"[,()%*_\\]", " ", str(q or ""))
    return " ".join(t.split())[:100]


def mau_so(t: str) -> str | None:
    """Ô tìm CHỈ có số (kèm dấu cách / chấm / gạch / +) → mẫu tìm trong cột gộp
    mọi SĐT, bỏ dấu ngăn: "0912 345" khớp "0912345678". Dưới 3 chữ số → bỏ
    (khớp quá rộng); có chữ cái → không phải số điện thoại."""
    if not t or not re.fullmatch(r"[\d\s.+\-]+", t):
        return None
    so = re.sub(r"\D", "", t)
    return f"%{so}%" if len(so) >= 3 else None


async def bo_loc(
    pool: asyncpg.Pool, identity: StaffIdentity, *, q: Any, loc: Any
) -> tuple[Any, ...]:
    """Tham số $1–$7 của ``CO_SO_SQL``: khớp ô tìm + tab, trong phạm vi người gọi
    (thư ký y khoa chỉ khách của bác sĩ mình — ``khach_duoc_xem``)."""
    ids = await khach_duoc_xem(pool, identity)
    t = chuoi_tim(q)
    khoang = LOC_THEO_SO_LUOT.get(doc_loc(loc) or "", (0, None))
    return (
        identity.clinic_id,
        ids,
        f"%{t}%" if t else None,
        t,
        mau_so(t),
        khoang[0],
        khoang[1],
    )


__all__ = [
    "CO_SO_SQL",
    "LOC_THEO_SO_LUOT",
    "bo_loc",
    "chuoi_tim",
    "doc_loc",
    "mau_so",
]
