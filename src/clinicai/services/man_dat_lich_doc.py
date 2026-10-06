"""Dữ liệu màn ĐẶT LỊCH (/appointments) — một lần đọc ở backend (24/09/2026).

Trang từng tự đọc 6 bảng bằng Supabase VÀ tự tính "khách khám lần mấy / đang
trong chuỗi tái khám" — một luật nghiệp vụ nằm ở frontend. Luật giữ nguyên:
  * đếm lượt ĐÃ KHÁM XONG (COMPLETED) — đặt rồi huỷ thì chưa khám lần nào;
  * còn MỘT lịch chưa huỷ nối vào lượt trước (`lich_truoc_id`) là khách đang
    trong một chuỗi tái khám.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.core.trang_thai_lich import DEAD_STATUSES
from clinicai.services.danh_sach_benh_nhan_service import chuoi_tim, mau_so

#: Ô tìm khách màn Đặt lịch: trả tối đa ngần này hồ sơ khớp nhất.
TRAN_TIM = 20
#: Ô tìm ngắn hơn thế này thì không tìm (một chữ khớp gần hết 9.000 hồ sơ).
TIM_TOI_THIEU = 2
#: Ô tìm DÀI hơn thế này là rác (dán nhầm cả đoạn) → rỗng, không cắt bớt rồi
#: tìm tiếp: cắt rồi tìm là trả về một người không ai hỏi.
TIM_TOI_DA = 100


def _gia(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (datetime, date)) else v


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    return {k: _gia(v) for k, v in dict(r).items()}


def dem_lan_kham(lich: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Khách → {soLanKham, laTaiKham} (hàm thuần, test không cần database)."""
    kq: dict[str, dict[str, Any]] = {}
    for r in lich:
        o = kq.setdefault(r["clinic_patient_id"], {"soLanKham": 0, "laTaiKham": False})
        if r["status"] == "COMPLETED":
            o["soLanKham"] += 1
        if r.get("lich_truoc_id") and r["status"] != "CANCELLED":
            o["laTaiKham"] = True
    return kq


async def hub_dat_lich(
    pool: asyncpg.Pool, *, identity: StaffIdentity, bn: str | None = None
) -> dict[str, Any]:
    cid = identity.clinic_id
    dau = datetime.combine(now_vn().date(), time.min, tzinfo=CLINIC_TZ)
    cuoi = dau + timedelta(days=1)
    async with pool.acquire() as conn:
        co_so = await conn.fetch(
            "SELECT id::text, name FROM clinic_location"
            " WHERE clinic_id = $1::uuid AND is_active ORDER BY name",
            cid,
        )
        dich_vu = await conn.fetch(
            "SELECT id::text, name FROM service_type"
            " WHERE clinic_id = $1::uuid AND is_active ORDER BY name",
            cid,
        )
        tinh = await conn.fetch(
            "SELECT code, name, full_name FROM province ORDER BY name"
        )
        khach = await conn.fetch(
            """
            SELECT clinic_patient_id::text, patient_code, full_name, phone_primary,
                   sdt_tim_kiem, date_of_birth, gender, address,
                   location_id::text
              FROM patient p
             WHERE p.clinic_id = $1::uuid
               -- Hồ sơ cũ chuyển từ Notion (05/10/2026, ~8.600) chưa hoạt động
               -- trên hệ thống không chiếm 200 chỗ; khách trong `?bn=` (bấm
               -- "Đặt lịch" từ Quản lý khách hàng) thì LUÔN có, đứng đầu.
               AND (p.nguon_nhap IS NULL
                    OR p.patient_code = $2
                    OR EXISTS (SELECT 1 FROM appointment a
                                WHERE a.clinic_id = p.clinic_id
                                  AND a.clinic_patient_id = p.clinic_patient_id)
                    OR EXISTS (SELECT 1 FROM visit v
                                WHERE v.clinic_id = p.clinic_id
                                  AND v.clinic_patient_id = p.clinic_patient_id))
             ORDER BY (p.patient_code = $2) DESC NULLS LAST, p.created_at DESC
             LIMIT 200
            """,
            cid,
            (bn or "").strip() or None,
        )
        lich_hom_nay = await conn.fetch(
            """
            SELECT id::text, slot_start, status, doctor_id::text,
                   service_type_id::text, clinic_patient_id::text
              FROM appointment
             WHERE clinic_id = $1::uuid AND slot_start >= $2 AND slot_start < $3
               AND status <> ALL($4::text[])
             LIMIT 1000
            """,
            cid,
            dau,
            cuoi,
            # Trạng thái không giữ chỗ — một danh sách, ở core/trang_thai_lich.
            sorted(DEAD_STATUSES),
        )
        ma_khach = [r["clinic_patient_id"] for r in khach]
        lich_su = (
            await conn.fetch(
                """
                SELECT clinic_patient_id::text, status, lich_truoc_id::text
                  FROM appointment
                 WHERE clinic_id = $1::uuid AND clinic_patient_id = ANY($2::uuid[])
                 ORDER BY slot_start
                 LIMIT 5000
                """,
                cid,
                ma_khach,
            )
            if ma_khach
            else []
        )
    canh_bao_neu_day("dat_lich.lich_hom_nay", len(lich_hom_nay), 1000, clinic_id=cid)
    canh_bao_neu_day("dat_lich.lich_su", len(lich_su), 5000, clinic_id=cid)
    return {
        "locations": [dict(r) for r in co_so],
        "services": [dict(r) for r in dich_vu],
        "provinces": [dict(r) for r in tinh],
        "patients": [_dong(r) for r in khach],
        "appts": [_dong(r) for r in lich_hom_nay],
        "lan_kham": dem_lan_kham([dict(r) for r in lich_su]),
    }


# ── Ô TÌM KHÁCH trên TOÀN BỘ hồ sơ (06/10/2026) ───────────────────────────
#
# Sáng 06/10 nạp ~8.600 khách cũ từ Notion (KHACH-n / LAMSANG-n), tối cùng ngày
# họ có lượt thật. Màn chỉ nạp 200 khách mới tạo gần nhất rồi lọc trên trình
# duyệt, nên lễ tân gõ tên / số một khách cũ thì KHÔNG RA — và tạo hồ sơ trùng
# (chốt trùng SĐT ở patient_service không đỡ được khi khách đổi số / gõ sai số).
#
# Cách tìm GIỐNG HỆT màn Danh sách bệnh nhân (PR #330, `_CO_SO.khop`): tên có
# dấu / không dấu, mã BN, hoặc một phần SĐT bỏ dấu cách / chấm / gạch — cùng
# ``chuoi_tim`` + ``mau_so``. Hai màn tìm khác nhau thì lễ tân tra ra ở màn này
# mà không ra ở màn kia.
#
# Thứ tự: khớp ĐÚNG mã hoặc ĐÚNG một số điện thoại lên trước (gõ đủ số là
# đang tìm đúng một người), rồi khách có LƯỢT gần nhất (visit, hoặc lịch khách
# đã tới), rồi hồ sơ mới tạo. ``is_active`` = bỏ hồ sơ Notion đã HOÀN TÁC nạp
# (nhap_lich_su_notion ẩn chứ không xoá) — không đặt lịch cho hồ sơ đã ẩn.
#
# Lượt gần nhất tính bằng câu con theo chỉ mục (idx_visit_patient,
# idx_appointment_patient) CHỈ cho hồ sơ đã khớp ô tìm — không gộp cả bảng.
#
# Tham số: $1 clinic · $2 chuỗi tìm (đã làm sạch) · $3 mẫu ILIKE · $4 chữ số
# của ô tìm khi nó là SĐT (NULL nếu không) · $5 mẫu chỉ-số cho SĐT · $6 trần.
_TIM_SQL = """
WITH k AS (
    SELECT p.clinic_patient_id, p.patient_code, p.full_name, p.phone_primary,
           p.sdt_tim_kiem, p.date_of_birth, p.gender, p.address, p.location_id,
           p.created_at,
           coalesce(lower(p.patient_code) = lower($2)
                    OR ($4::text IS NOT NULL
                        AND $4 = ANY(string_to_array(p.sdt_tim_kiem, ' '))),
                    false) AS dung
      FROM patient p
     WHERE p.clinic_id = $1::uuid
       AND p.is_active
       AND (p.full_name ILIKE $3 OR p.patient_code ILIKE $3
            OR p.sdt_tim_kiem ILIKE $3
            OR p.full_name_unaccent ILIKE
               '%' || lower(replace(replace(f_unaccent($2), 'đ', 'd'), 'Đ', 'D'))
               || '%'
            OR ($5::text IS NOT NULL AND p.sdt_tim_kiem LIKE $5))
)
SELECT k.clinic_patient_id::text AS clinic_patient_id, k.patient_code,
       k.full_name, k.phone_primary, k.sdt_tim_kiem, k.date_of_birth, k.gender,
       k.address, k.location_id::text AS location_id
  FROM k
 ORDER BY k.dung DESC,
          greatest(
              (SELECT max(v.created_at) FROM visit v
                WHERE v.clinic_id = $1::uuid
                  AND v.clinic_patient_id = k.clinic_patient_id),
              (SELECT max(a.slot_start) FROM appointment a
                WHERE a.clinic_id = $1::uuid
                  AND a.clinic_patient_id = k.clinic_patient_id
                  AND a.status IN ('CHECKED_IN', 'COMPLETED'))
          ) DESC NULLS LAST,
          k.created_at DESC, k.clinic_patient_id
 LIMIT $6
"""

# Ký tự điều khiển (kể cả NUL — Postgres không nhận NUL trong text, để lọt là
# 500) thành dấu cách trước khi làm sạch.
_DIEU_KHIEN = re.compile(r"[\x00-\x1f\x7f]")


def doc_o_tim(q: Any) -> str | None:
    """``?q=`` → chuỗi tìm đã làm sạch, hoặc None (= trả rỗng, không tìm).

    Rác → None, không ném: rỗng · toàn ký tự ILIKE / điều khiển · dài quá
    ``TIM_TOI_DA`` · ngắn hơn ``TIM_TOI_THIEU`` sau khi làm sạch."""
    tho = str(q or "")
    if len(tho) > TIM_TOI_DA:
        return None
    t = chuoi_tim(_DIEU_KHIEN.sub(" ", tho))
    return t if len(t) >= TIM_TOI_THIEU else None


async def tim_khach(
    pool: asyncpg.Pool, *, identity: StaffIdentity, q: Any
) -> dict[str, Any]:
    """Tìm khách cho ô "Tìm kiếm khách hàng có sẵn" của màn Đặt lịch.

    Trả cùng hình dạng với ``hub_dat_lich`` (``patients`` + ``lan_kham``) để
    trình duyệt dùng lại đúng chỗ vẽ thẻ khách / nhãn "khám lần mấy"."""
    t = doc_o_tim(q)
    if t is None:
        return {"patients": [], "lan_kham": {}}
    mau = mau_so(t)
    chu_so = re.sub(r"\D", "", t) if mau else None
    cid = identity.clinic_id
    async with pool.acquire() as conn:
        khach = await conn.fetch(_TIM_SQL, cid, t, f"%{t}%", chu_so, mau, TRAN_TIM)
        ma_khach = [r["clinic_patient_id"] for r in khach]
        lich_su = (
            await conn.fetch(
                """
                SELECT clinic_patient_id::text, status, lich_truoc_id::text
                  FROM appointment
                 WHERE clinic_id = $1::uuid AND clinic_patient_id = ANY($2::uuid[])
                 ORDER BY slot_start
                 LIMIT 5000
                """,
                cid,
                ma_khach,
            )
            if ma_khach
            else []
        )
    canh_bao_neu_day("dat_lich.tim_khach.lich_su", len(lich_su), 5000, clinic_id=cid)
    return {
        "patients": [_dong(r) for r in khach],
        "lan_kham": dem_lan_kham([dict(r) for r in lich_su]),
    }


__all__ = ["dem_lan_kham", "doc_o_tim", "hub_dat_lich", "tim_khach"]
