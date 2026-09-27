"""NHẬT KÝ VẬN HÀNH — ai làm gì, lúc nào, mất bao lâu (Tuyền 27/09/2026).

Tuyền: *"bắt sự kiện được mọi chỗ, từ mọi lúc: bệnh nhân A check-in lúc này do
lễ tân này; đã đo sinh hiệu lúc này do tài khoản này làm trong bao nhiêu phút,
thời gian check-in đến khi bắt đầu đo…"*.

Đọc PROJECTION `luot_dong_thoi_gian` (mỗi bước của lượt: giờ, loại việc, người
làm — do bên nhận sự kiện dựng, phát lại được). Không đọc nội dung lâm sàng.
Hai phần:
  · DÒNG SỰ KIỆN: mỗi bước + người làm + "cách bước trước của khách này".
  · CHỈ SỐ THEO LƯỢT: check-in → bắt đầu đo, thời gian đo, check-in → vào khám,
    thời gian khám, check-in → về; và trung vị cả ngày (cho quản lý thấy khâu
    nào nghẽn).
Chỉ số tính bằng HÀM THUẦN `chi_so_luot` / `trung_vi` — test không cần DB.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ, now_vn

GIOI_HAN_DONG = 2000

#: (khoá, tên, mốc đầu, mốc cuối). Mốc là event_type; lấy lần ĐẦU của mỗi loại.
CHI_SO: tuple[tuple[str, str, str, str], ...] = (
    ("cho_do", "Check-in → bắt đầu đo", "visit.checked_in", "vitals.started"),
    ("do", "Thời gian đo sinh hiệu", "vitals.started", "vitals.recorded"),
    ("cho_kham", "Check-in → vào khám", "visit.checked_in", "consultation.started"),
    ("kham", "Vào khám → khám xong", "consultation.started", "consultation.completed"),
    (
        "thu_tien",
        "Chỉ định → thu tiền DV",
        "service_order.placed",
        "payment.service_collected",
    ),
    ("tong", "Check-in → về", "visit.checked_in", "visit.checked_out"),
)


def doc_ngay(chuoi: str | None) -> date | None:
    """YYYY-MM-DD → ngày; rác / rỗng → None (không ném)."""
    try:
        return date.fromisoformat((chuoi or "").strip())
    except ValueError:
        return None


def phut(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None or b < a:
        return None
    return round((b - a).total_seconds() / 60, 1)


def chi_so_luot(moc: dict[str, datetime]) -> dict[str, float | None]:
    """HÀM THUẦN: mốc lần-đầu theo event_type → số phút từng khâu."""
    return {k: phut(moc.get(dau), moc.get(cuoi)) for k, _t, dau, cuoi in CHI_SO}


def trung_vi(luot: list[dict[str, float | None]]) -> dict[str, float | None]:
    """HÀM THUẦN: trung vị từng chỉ số trên các lượt có đủ mốc."""
    ra: dict[str, float | None] = {}
    for k, *_ in CHI_SO:
        ds = [float(v) for x in luot if (v := x.get(k)) is not None]
        ra[k] = round(float(median(ds)), 1) if ds else None
    return ra


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


async def doc_nhat_ky(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    ngay: str | None,
    tim: str | None = None,
) -> dict[str, Any]:
    """Nhật ký một ngày (mặc định hôm nay, giờ VN). `tim`: tên / mã khách."""
    d = doc_ngay(ngay) or now_vn().date()
    dau = datetime(d.year, d.month, d.day, tzinfo=CLINIC_TZ)
    cuoi = dau + timedelta(days=1)
    q = (tim or "").strip()
    rows = await pool.fetch(
        """
        SELECT t.visit_id::text AS visit_id, t.occurred_at, t.event_type, t.nhan,
               t.actor_type, s.full_name AS nguoi_lam,
               p.full_name AS khach, p.patient_code AS ma_khach,
               a.so_booking, a.so_tiep_don
          FROM luot_dong_thoi_gian t
          JOIN visit v ON v.visit_id = t.visit_id AND v.clinic_id = t.clinic_id
          JOIN patient p
            ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
          LEFT JOIN appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
          LEFT JOIN staff s ON s.id = t.actor_staff_id
         WHERE t.clinic_id = $1::uuid
           AND t.occurred_at >= $2 AND t.occurred_at < $3
           AND ($4 = '' OR p.full_name ILIKE '%' || $4 || '%'
                OR p.patient_code ILIKE '%' || $4 || '%')
         ORDER BY t.occurred_at, t.thu_tu
         LIMIT $5
        """,
        clinic_id,
        dau,
        cuoi,
        q,
        GIOI_HAN_DONG,
    )
    truoc: dict[str, datetime] = {}
    moc: dict[str, dict[str, datetime]] = {}
    khach: dict[str, dict[str, Any]] = {}
    dong: list[dict[str, Any]] = []
    for r in rows:
        vid = r["visit_id"]
        luc: datetime = r["occurred_at"]
        dong.append(
            {
                "luc": luc.isoformat(),
                "visit_id": vid,
                "khach": r["khach"],
                "ma_khach": r["ma_khach"],
                "viec": r["nhan"] or r["event_type"],
                "loai": r["event_type"],
                "nguoi_lam": r["nguoi_lam"]
                or ("Hệ thống tự động" if r["actor_type"] == "SYSTEM" else None),
                "cach_buoc_truoc_phut": phut(truoc.get(vid), luc),
            }
        )
        truoc[vid] = luc
        moc.setdefault(vid, {}).setdefault(r["event_type"], luc)
        khach.setdefault(
            vid,
            {
                "visit_id": vid,
                "khach": r["khach"],
                "ma_khach": r["ma_khach"],
                "so_booking": r["so_booking"],
                "so_tiep_don": r["so_tiep_don"],
            },
        )
    theo_luot = []
    for vid, m in moc.items():
        cs = chi_so_luot(m)
        theo_luot.append(
            {**khach[vid], "check_in": _iso(m.get("visit.checked_in")), **cs}
        )
    theo_luot.sort(key=lambda x: x["check_in"] or "")
    return {
        "ngay": d.isoformat(),
        "chi_so": [{"ma": k, "ten": t} for k, t, *_ in CHI_SO],
        "trung_vi": trung_vi(theo_luot),
        "theo_luot": theo_luot,
        "dong": list(reversed(dong)),
        "bi_cat": len(rows) >= GIOI_HAN_DONG,
        "tong_dong": len(rows),
    }
