"""DANH SÁCH TIẾP ĐÓN hôm nay — mỗi lịch hẹn / lượt MỘT DÒNG (27/09/2026, đợt 3).

Tuyền duyệt bản mẫu 27/09: màn `/reception/queue` phần dưới bảng "Lịch hẹn hôm
nay" là MỘT danh sách chia buổi Sáng/Chiều, mỗi dòng: số booking + số check-in,
tên, loại khách, "giờ hẹn · loại khám · BS · SĐT", và một CHIP TRẠNG THÁI:

    Chưa đến · Trễ N′ · Đã check-in hh:mm · <bước tiếp> · Đang ở: <nơi> · Đã về hh:mm

Chip ấy là LUẬT (quá giờ bao lâu thì gọi là trễ, đang ở đâu, bước tiếp là gì),
nên nó được tính Ở ĐÂY bằng hàm thuần — màn chỉ tô màu theo `loai`.

CHỈ ĐỌC. Nguồn: `appointment` (lịch hôm nay, giờ VN) + `visit` (check-in / về)
+ `encounter_flow` (đo sinh hiệu) + `queue_entry` (đang ở / đang chờ ở đâu).
Không có nội dung lâm sàng. Mọi câu khoá theo `clinic_id`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.shifts import CAC_CA, NHAN_CA, Window, ca_tu_settings
from clinicai.services.bang_hanh_trinh_service import noi_hang
from clinicai.services.queue_order import VISIT_DA_RA_VE

#: Lịch còn chờ khách tới — có nút Check-in (cùng tập với bảng Lịch hẹn hôm nay).
CHO_CHECK_IN: frozenset[str] = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})

#: Lịch KHÔNG hiện trong danh sách: đã huỷ / bác sĩ từ chối (không phải khách).
AN_KHOI_DANH_SACH: tuple[str, ...] = ("CANCELLED", "DOCTOR_DECLINED")

_TRAN = 500


# ── Hàm thuần ───────────────────────────────────────────────────────────────


def _gio(moc: Any) -> str | None:
    """datetime → "hh:mm" giờ VN. Rác / thiếu / không múi giờ → None."""
    if not isinstance(moc, datetime) or moc.tzinfo is None:
        return None
    return moc.astimezone(CLINIC_TZ).strftime("%H:%M")


def phut_tre(
    gio_hen: Any, bay_gio: Any, khung_phut: Any, *, vang_lai: bool = False
) -> int | None:
    """HÀM THUẦN: khách CHƯA ĐẾN đã trễ bao nhiêu phút so với giờ hẹn.

    Trễ = đã qua HẾT khung giờ của lịch (`khung_phut` — độ dài khung áp cho
    chính lịch này, cùng nguồn `resolve_effective_cap` mà bảng gọi số dùng để
    phân "đến đúng giờ / đến trễ"). Trong khung thì chưa gọi là trễ. Con số trả
    về đếm từ GIỜ HẸN (08:30 hẹn, 08:55 chưa tới → 25).

    Không tính trễ (→ None): khách vãng lai (giờ "hẹn" của họ là lúc tạo lịch),
    chưa qua khung, thiếu độ dài khung (không có mặc định — thà không nhắc còn
    hơn nhắc sai), đầu vào rác.
    """
    if vang_lai:
        return None
    if not isinstance(gio_hen, datetime) or not isinstance(bay_gio, datetime):
        return None
    if (
        isinstance(khung_phut, bool)
        or not isinstance(khung_phut, int)
        or khung_phut <= 0
    ):
        return None
    try:
        giay = (bay_gio - gio_hen).total_seconds()
    except TypeError:  # một bên có múi giờ, một bên không
        return None
    if giay < khung_phut * 60:
        return None
    return int(giay // 60)


def buoi_cua(moc: Any, ca: Mapping[str, Window] | None) -> str | None:
    """HÀM THUẦN: mốc giờ thuộc BUỔI nào ("SANG" | "CHIEU" | "TOI").

    Theo giờ ca phòng khám khai (`core/shifts`). Mốc rơi vào khoảng nghỉ giữa
    hai ca thuộc ca SAU (khách hẹn 13:15 là khách buổi chiều); sớm hơn ca đầu
    thuộc ca đầu; muộn hơn ca cuối thuộc ca cuối. Rác → None.
    """
    if not isinstance(moc, datetime) or moc.tzinfo is None or not ca:
        return None
    cac = [m for m in CAC_CA if m in ca]
    if not cac:
        return None
    gio = moc.astimezone(CLINIC_TZ)
    phut = gio.hour * 60 + gio.minute
    for ma in cac:
        if phut < ca[ma][1]:
            return ma
    return cac[-1]


def nhan_buoi(ma: str, ca: Mapping[str, Window]) -> str:
    """ "Sáng · 08:00 – 13:00" — nhãn đầu nhóm."""
    ten = NHAN_CA.get(ma, ma)
    khung = ca.get(ma)
    if not khung:
        return ten
    lo, hi = khung
    return f"{ten} · {lo // 60:02d}:{lo % 60:02d} – {hi // 60:02d}:{hi % 60:02d}"


def loai_khach(kenh: Any, phan_loai: Any) -> str | None:
    """HÀM THUẦN: chip cạnh tên — "vãng lai" | "khám mới" | "tái khám" | None."""
    if isinstance(kenh, str) and kenh.upper() == "WALK_IN":
        return "vãng lai"
    if phan_loai == "Khám lần đầu":
        return "khám mới"
    if phan_loai == "Tái khám":
        return "tái khám"
    return None


def trang_thai(
    *,
    lich_status: Any,
    vang_lai: bool,
    gio_hen: Any,
    khung_phut: Any,
    check_in: Any,
    visit_status: Any,
    ve_luc: Any,
    vitals_status: Any,
    vitals_tu_luot_truoc: bool,
    hang: list[dict[str, Any]],
    bay_gio: Any,
) -> dict[str, str]:
    """HÀM THUẦN: chip trạng thái của một dòng tiếp đón.

    Trả ``{"loai", "nhan", "nhom"}``:
      * ``loai``  — màn tô màu theo đây: cho · tre · den · dang_o · ve · khong_den
      * ``nhan``  — chữ trên chip
      * ``nhom``  — tab lọc: ``chua_den`` · ``da_den`` · ``khac`` (không đến)

    Thứ tự ưu tiên khi khách đã check-in: đã về → đang được phục vụ ở đâu →
    đang đo sinh hiệu → "Đã check-in hh:mm · <bước tiếp>" (chờ đo trước, rồi
    chờ ở hàng nào, rồi đợi mở hàng nào).
    """
    if not isinstance(check_in, datetime):
        if lich_status == "NO_SHOW":
            return {"loai": "khong_den", "nhan": "Không đến", "nhom": "khac"}
        if lich_status in CHO_CHECK_IN or lich_status is None:
            tre = phut_tre(gio_hen, bay_gio, khung_phut, vang_lai=vang_lai)
            if tre is not None:
                return {"loai": "tre", "nhan": f"Trễ {tre}′", "nhom": "chua_den"}
            return {"loai": "cho", "nhan": "Chưa đến", "nhom": "chua_den"}
        # Lịch đã CHECKED_IN/COMPLETED mà không thấy lượt — dữ liệu lệch; nói
        # đúng điều duy nhất chắc chắn, không bịa giờ.
        return {"loai": "den", "nhan": "Đã check-in", "nhom": "da_den"}

    if isinstance(ve_luc, datetime) or visit_status in VISIT_DA_RA_VE:
        gio = _gio(ve_luc)
        chu = "Về giữa chừng" if visit_status == "INCOMPLETE" else "Đã về"
        return {"loai": "ve", "nhan": f"{chu} {gio}" if gio else chu, "nhom": "da_den"}

    hang = [q for q in hang if isinstance(q, Mapping)]
    dang = [q for q in hang if q.get("status") in ("serving", "called")]
    if dang:
        return {
            "loai": "dang_o",
            "nhan": f"Đang ở: {noi_hang(dang[0])}",
            "nhom": "da_den",
        }
    if vitals_status == "in_progress":
        return {"loai": "dang_o", "nhan": "Đang ở: đo sinh hiệu", "nhom": "da_den"}

    tiep: str | None = None
    if vitals_status == "pending" and not vitals_tu_luot_truoc:
        tiep = "chờ đo"
    else:
        cho = [q for q in hang if q.get("status") == "waiting"]
        doi = [q for q in hang if q.get("status") == "blocked"]
        if cho:
            tiep = "chờ " + noi_hang(cho[0])
        elif doi:
            tiep = "đợi " + noi_hang(doi[0])
    gio = _gio(check_in)
    nhan = f"Đã check-in {gio}" if gio else "Đã check-in"
    if tiep:
        nhan = f"{nhan} · {tiep}"
    return {"loai": "den", "nhan": nhan, "nhom": "da_den"}


# ── Đọc database ────────────────────────────────────────────────────────────

_SQL_LICH = """
WITH hom_nay AS (
    SELECT a.id, a.clinic_id, a.clinic_patient_id, a.doctor_id,
           a.service_type_id, a.status, a.booking_channel, a.slot_start,
           a.so_booking, a.so_tiep_don, a.created_at
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND a.slot_start >= $2
       AND a.slot_start <  $3
       AND a.status <> ALL($4::text[])
     ORDER BY a.slot_start, a.created_at, a.id
     LIMIT $5
),
-- "Khám lần đầu / Tái khám" — CÙNG luật với lưới lịch tuần
-- (week_appointments_service): lịch đã huỷ / không đến không tính là lần trước.
som_nhat AS (
    SELECT a.clinic_patient_id, min(a.slot_start) AS dau_tien
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND a.clinic_patient_id IN (SELECT clinic_patient_id FROM hom_nay)
       AND a.status <> ALL($6::text[])
     GROUP BY a.clinic_patient_id
)
SELECT h.id::text AS appointment_id, h.status, h.booking_channel, h.slot_start,
       h.so_booking, h.so_tiep_don,
       p.clinic_patient_id::text AS clinic_patient_id, p.full_name,
       p.patient_code, p.phone_primary, p.uu_tien, p.uu_tien_ly_do,
       st.name AS loai_kham, d.full_name AS bac_si,
       CASE WHEN h.slot_start > s.dau_tien THEN 'Tái khám'
            ELSE 'Khám lần đầu' END AS phan_loai,
       v.visit_id::text AS visit_id, v.status AS visit_status,
       v.checked_in_at, coalesce(v.closed_at, v.incomplete_at) AS ve_luc,
       f.vitals_status, (f.vitals_tu_visit_id IS NOT NULL) AS vitals_tu_luot_truoc,
       cap.slot_minutes
  FROM hom_nay h
  JOIN patient p
    ON p.clinic_patient_id = h.clinic_patient_id AND p.clinic_id = h.clinic_id
  LEFT JOIN som_nhat s ON s.clinic_patient_id = h.clinic_patient_id
  LEFT JOIN service_type st ON st.id = h.service_type_id AND st.clinic_id = h.clinic_id
  LEFT JOIN staff d ON d.id = h.doctor_id
  LEFT JOIN LATERAL (
      SELECT vi.visit_id, vi.status, vi.checked_in_at, vi.closed_at, vi.incomplete_at
        FROM visit vi
       WHERE vi.appointment_id = h.id AND vi.clinic_id = h.clinic_id
       ORDER BY vi.checked_in_at DESC NULLS LAST
       LIMIT 1
  ) v ON TRUE
  LEFT JOIN encounter_flow f
    ON f.visit_id = v.visit_id AND f.clinic_id = h.clinic_id
  -- Độ dài khung ÁP CHO CHÍNH LỊCH NÀY — cùng hàm với bảng gọi số (queue.py),
  -- để "trễ" ở đây và "đến trễ" ở bảng gọi số không thể hiểu khác nhau.
  LEFT JOIN LATERAL public.resolve_effective_cap(
      h.clinic_id, h.doctor_id, h.slot_start
  ) cap ON TRUE
 ORDER BY h.slot_start, h.created_at, h.id
"""

_SQL_HANG = """
SELECT q.visit_id::text AS visit_id, q.lane, q.status,
       r.name AS phong, d.full_name AS bac_si
  FROM queue_entry q
  LEFT JOIN clinic_room r ON r.id = q.room_id
  LEFT JOIN staff d ON d.id = q.doctor_staff_id
 WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
   AND q.status IN ('blocked', 'waiting', 'called', 'serving')
 ORDER BY q.eligible_at NULLS LAST, q.created_at
"""


def _dau_ngay(ngay: date) -> datetime:
    return datetime.combine(ngay, time.min, tzinfo=CLINIC_TZ)


def dung_dong(
    r: Mapping[str, Any], hang: list[dict[str, Any]], bay_gio: datetime
) -> dict[str, Any]:
    """Một hàng database → một dòng danh sách (thuần — test không cần DB)."""
    vang_lai = str(r.get("booking_channel") or "").upper() == "WALK_IN"
    check_in = r.get("checked_in_at")
    tt = trang_thai(
        lich_status=r.get("status"),
        vang_lai=vang_lai,
        gio_hen=r.get("slot_start"),
        khung_phut=r.get("slot_minutes"),
        check_in=check_in,
        visit_status=r.get("visit_status"),
        ve_luc=r.get("ve_luc"),
        vitals_status=r.get("vitals_status"),
        vitals_tu_luot_truoc=bool(r.get("vitals_tu_luot_truoc")),
        hang=hang,
        bay_gio=bay_gio,
    )
    return {
        "appointment_id": r.get("appointment_id"),
        "visit_id": r.get("visit_id"),
        "clinic_patient_id": r.get("clinic_patient_id"),
        "ten": r.get("full_name"),
        "ma_khach": r.get("patient_code"),
        "sdt": r.get("phone_primary"),
        "so_booking": r.get("so_booking"),
        "so_tiep_don": r.get("so_tiep_don"),
        "gio_hen": _gio(r.get("slot_start")),
        "loai_kham": r.get("loai_kham"),
        "bac_si": r.get("bac_si"),
        "loai_khach": loai_khach(r.get("booking_channel"), r.get("phan_loai")),
        "uu_tien": bool(r.get("uu_tien")),
        "uu_tien_ly_do": r.get("uu_tien_ly_do"),
        # Vãng lai xếp theo giờ CHECK-IN (giờ "hẹn" của họ là lúc tạo lịch).
        "moc_xep": (
            check_in
            if vang_lai and isinstance(check_in, datetime)
            else r.get("slot_start")
        ),
        "trang_thai": tt,
        "check_in_duoc": tt["nhom"] == "chua_den" and r.get("status") in CHO_CHECK_IN,
        "check_out_duoc": bool(r.get("visit_id")) and tt["loai"] in ("den", "dang_o"),
    }


def gom_theo_buoi(
    dong: list[dict[str, Any]], ca: Mapping[str, Window]
) -> list[dict[str, Any]]:
    """HÀM THUẦN: chia dòng theo buổi, trong buổi xếp theo mốc (rồi số booking).

    Dòng không xác định được buổi (mốc rác) rơi vào buổi đầu — không bao giờ
    biến mất khỏi danh sách. `moc_xep` bị bỏ khỏi dòng trả về.
    """
    cac = [m for m in CAC_CA if m in ca] or ["SANG"]
    theo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in dong:
        theo[buoi_cua(d.get("moc_xep"), ca) or cac[0]].append(d)

    def khoa(d: dict[str, Any]) -> tuple[float, int]:
        moc = d.get("moc_xep")
        ts = (
            moc.timestamp()
            if isinstance(moc, datetime) and moc.tzinfo
            else float("inf")
        )
        so = d.get("so_booking")
        return ts, so if isinstance(so, int) and not isinstance(so, bool) else 1 << 30

    ket: list[dict[str, Any]] = []
    for ma in cac:
        if not theo.get(ma):
            continue
        ket.append(
            {
                "ma": ma,
                "nhan": nhan_buoi(ma, ca),
                "dong": [
                    {k: v for k, v in d.items() if k != "moc_xep"}
                    for d in sorted(theo[ma], key=khoa)
                ],
            }
        )
    return ket


class TiepDonService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def hom_nay(
        self,
        *,
        identity: StaffIdentity,
        ngay: date | None = None,
        bay_gio: datetime | None = None,
    ) -> dict[str, Any]:
        """Danh sách tiếp đón của một ngày (mặc định hôm nay, giờ VN).

        Quyền do router gác (`reception.checkin.perform` — lego Tiếp đón khách).
        """
        bay_gio = bay_gio or now_vn()
        ngay = ngay or bay_gio.astimezone(CLINIC_TZ).date()
        dau = _dau_ngay(ngay)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            settings = await conn.fetchval(
                "SELECT settings FROM clinic WHERE id = $1::uuid", cid
            )
            rows = [
                dict(r)
                for r in await conn.fetch(
                    _SQL_LICH,
                    cid,
                    dau,
                    dau + timedelta(days=1),
                    list(AN_KHOI_DANH_SACH),
                    _TRAN,
                    ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"],
                )
            ]
            ids = [r["visit_id"] for r in rows if r["visit_id"]]
            hang: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                for q in await conn.fetch(_SQL_HANG, cid, ids):
                    hang[q["visit_id"]].append(dict(q))
        ca = ca_tu_settings(settings)
        dong = [dung_dong(r, hang.get(r["visit_id"] or "", []), bay_gio) for r in rows]
        return {
            "ngay": ngay.isoformat(),
            "buoi": gom_theo_buoi(dong, ca),
            "dem": {
                "tat_ca": len(dong),
                "chua_den": sum(d["trang_thai"]["nhom"] == "chua_den" for d in dong),
                "da_den": sum(d["trang_thai"]["nhom"] == "da_den" for d in dong),
            },
            "bi_cat": len(rows) >= _TRAN,
        }


__all__ = [
    "TiepDonService",
    "buoi_cua",
    "dung_dong",
    "gom_theo_buoi",
    "loai_khach",
    "nhan_buoi",
    "phut_tre",
    "trang_thai",
]
