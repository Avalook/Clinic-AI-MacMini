"""Đổi lịch tại chỗ — phần ĐỌC: ô giờ của popover "Đổi lịch" (Tuyền 29/09/2026).

Popover mở ngay ở dòng khách (Tiếp đón, Trang chủ, Đặt lịch): chọn ngày → mỗi
bác sĩ có ca hôm ấy một hàng ô giờ → chọn ô → [Chỉ đổi lịch] / [Đổi & Check-in].

MÁY CHỦ QUYẾT TRẠNG THÁI Ô. Số ghế đến từ CHÍNH `luoi_ngay` (cùng `quote` +
`slot_seats_ban` mà trigger dựa vào), với ``bo_qua_lich_id`` = lịch đang đổi —
lịch không chiếm ghế của chính nó. Trình duyệt chỉ tô màu theo ``trang_thai``.

Phần GHI là `BookingService.doi_lich_nhanh` (một giao dịch: đổi lịch + check-in).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.permissions.can import can
from clinicai.services.booking_service import is_walkin
from clinicai.services.capacity_service import (
    FEW_REMAINING,
    CapacityService,
    luoi_ngay,
)

#: Lý do đổi lịch cho ô chọn (Tuyền chốt 29/09/2026). Mục đầu là mặc định.
LY_DO_DOI_LICH: tuple[str, ...] = (
    "Khách đến sớm",
    "Khách xin đổi",
    "Bác sĩ đổi ca",
    "Khác…",
)

_TRUOC_KHI_DEN = frozenset({"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"})


def trang_thai_o(*, cap: int, used: int, chan: bool) -> str:
    """TRONG / IT / DAY cho một ô — theo loại ghế của CHÍNH lịch đang đổi.

    ``chan`` = trần có chặn không (tuần chưa công bố lịch trực → đặt tự do):
    không chặn thì không bao giờ "đầy", đúng như trigger.
    """
    if not chan:
        return "TRONG"
    con = cap - used
    if con <= 0:
        return "DAY"
    if con <= FEW_REMAINING:
        return "IT"
    return "TRONG"


def _hhmm(phut: int) -> str:
    return f"{phut // 60:02d}:{phut % 60:02d}"


def _luc(ngay: _date, phut: int) -> datetime:
    return datetime(ngay.year, ngay.month, ngay.day, tzinfo=CLINIC_TZ) + timedelta(
        minutes=phut
    )


def dung_hang(
    q: dict[str, Any],
    *,
    ngay: _date,
    bay_gio: datetime,
    thoi_luong: timedelta,
    walkin: bool,
    lich_hien_tai: datetime | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """(các ô giờ, ô "Ngay bây giờ") của một bác sĩ — hàm thuần, test được.

    Hôm nay: bỏ khung ĐÃ QUA (so ``slot_end`` như `_chan_dat_vao_qua_khu`),
    giữ khung đang chạy. Ô "Ngay bây giờ" chỉ có ở hôm nay; ngoài ca của bác sĩ
    thì ``ngoai_ca`` = True và chỉ đi được kèm check-in.
    """
    cap_k, used_k = (
        ("walkin_cap", "walkin_used")
        if walkin
        else (
            "regular_cap",
            "regular_used",
        )
    )
    chan = bool(q.get("walkin_chan" if walkin else "regular_chan"))
    hom_nay = ngay == bay_gio.astimezone(CLINIC_TZ).date()
    bay_gio_phut = None
    if hom_nay:
        local = bay_gio.astimezone(CLINIC_TZ)
        bay_gio_phut = local.hour * 60 + local.minute

    o: list[dict[str, Any]] = []
    dang_chay: dict[str, Any] | None = None
    for s in q.get("slots") or []:
        phut = int(s["minute_of_day"])
        dai = int(s["slot_minutes"])
        if bay_gio_phut is not None and phut + dai <= bay_gio_phut:
            continue
        bd = _luc(ngay, phut)
        tt = trang_thai_o(cap=int(s[cap_k]), used=int(s[used_k]), chan=chan)
        chay = bay_gio_phut is not None and phut <= bay_gio_phut < phut + dai
        o_moi = {
            "gio": _hhmm(phut),
            "slot_start": bd.isoformat(),
            "slot_end": (bd + thoi_luong).isoformat(),
            "trang_thai": tt,
            "con_lai": max(int(s[cap_k]) - int(s[used_k]), 0) if chan else None,
            "dang_chay": chay,
            "la_lich_hien_tai": lich_hien_tai is not None and bd == lich_hien_tai,
        }
        if chay:
            dang_chay = o_moi
        o.append(o_moi)

    ngay_bay_gio: dict[str, Any] | None = None
    if bay_gio_phut is not None and not q.get("closed", False):
        bd = bay_gio.astimezone(CLINIC_TZ).replace(second=0, microsecond=0)
        ngay_bay_gio = {
            "gio": _hhmm(bay_gio_phut),
            "slot_start": bd.isoformat(),
            "slot_end": (bd + thoi_luong).isoformat(),
            "trang_thai": dang_chay["trang_thai"] if dang_chay else "TRONG",
            # Ngoài ca của bác sĩ (ca chưa bắt đầu / nghỉ trưa): chỉ đi kèm
            # check-in — khách đang đứng ở quầy. Máy chủ chốt lại lúc ghi.
            "ngoai_ca": dang_chay is None,
            "chi_kem_check_in": dang_chay is None,
        }
    return o, ngay_bay_gio


async def o_doi_lich(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    appointment_id: str,
    ngay: str | None,
) -> dict[str, Any]:
    """Dữ liệu popover Đổi lịch của MỘT lịch hẹn cho MỘT ngày.

    Ngày hỏng / thiếu → hôm nay (không ném: ngày là dữ liệu người dùng gõ).
    Ngày đã qua → không có ô nào.
    """
    bay_gio = now_vn()
    hom_nay = bay_gio.date()
    try:
        chon = _date.fromisoformat(ngay) if ngay else hom_nay
    except (ValueError, TypeError):
        chon = hom_nay

    async with pool.acquire() as conn:
        lich = await conn.fetchrow(
            """
            SELECT a.id::text AS id, a.status, a.slot_start, a.slot_end,
                   a.doctor_id::text AS doctor_id, a.booking_channel,
                   a.clinic_patient_id::text AS clinic_patient_id,
                   p.full_name AS ten_khach,
                   d.full_name AS ten_bac_si,
                   st.name AS dich_vu
              FROM appointment a
              LEFT JOIN patient p
                ON p.clinic_patient_id = a.clinic_patient_id
               AND p.clinic_id = a.clinic_id
              LEFT JOIN staff d ON d.id = a.doctor_id
              LEFT JOIN service_type st ON st.id = a.service_type_id
             WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
            """,
            appointment_id,
            identity.clinic_id,
        )
        if lich is None:
            raise NotFoundError("Không tìm thấy lịch hẹn")
        co_quyen_check_in = await can(conn, identity, "reception.checkin.perform")
        # Bác sĩ CÓ CA ngày ấy (lịch trực đã duyệt). Chưa ai → mọi bác sĩ đang
        # làm (tuần chưa xếp ca vẫn đặt được — cùng luật `quote`).
        bac_si = await conn.fetch(
            """
            WITH bs AS (
                SELECT s.id::text AS id, s.full_name
                  FROM clinic_membership m
                  JOIN staff s ON s.id = m.staff_id AND s.is_active
                 WHERE m.clinic_id = $1::uuid AND m.is_active
                   AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
                 GROUP BY s.id, s.full_name
            ),
            co_ca AS (
                SELECT DISTINCT wr.staff_id::text AS id
                  FROM work_roster wr
                 WHERE wr.clinic_id = $1::uuid AND wr.work_date = $2
                   AND wr.status = 'APPROVED'
            )
            SELECT bs.id, bs.full_name,
                   EXISTS (SELECT 1 FROM co_ca WHERE co_ca.id = bs.id) AS co_ca,
                   EXISTS (SELECT 1 FROM co_ca) AS ngay_co_lich_truc
              FROM bs
             ORDER BY bs.full_name
            """,
            identity.clinic_id,
            chon,
        )

    bs_cu = lich["doctor_id"]
    co_lich_truc = any(r["ngay_co_lich_truc"] for r in bac_si)
    chon_bs = [r for r in bac_si if r["id"] == bs_cu or r["co_ca"] or not co_lich_truc]
    chon_bs.sort(key=lambda r: (r["id"] != bs_cu, r["full_name"] or ""))

    thoi_luong = lich["slot_end"] - lich["slot_start"]
    if thoi_luong < timedelta(minutes=5):
        thoi_luong = timedelta(minutes=15)
    walkin = is_walkin(lich["booking_channel"])
    da_qua = chon < hom_nay

    hang: list[dict[str, Any]] = []
    if not da_qua and chon_bs:
        luoi = await luoi_ngay(
            CapacityService(pool),
            clinic_id=str(identity.clinic_id),
            date=chon.isoformat(),
            doctor_ids=[r["id"] for r in chon_bs],
            bo_qua_lich_id=appointment_id,
        )
        theo_bs = {h.get("doctor_id"): h for h in luoi.get("hang", [])}
        for r in chon_bs:
            q = theo_bs.get(r["id"])
            if q is None:
                continue
            o, ngay_bay_gio = dung_hang(
                q,
                ngay=chon,
                bay_gio=bay_gio,
                thoi_luong=thoi_luong,
                walkin=walkin,
                lich_hien_tai=lich["slot_start"] if r["id"] == bs_cu else None,
            )
            ca = [
                f"{_hhmm(int(a))}–{_hhmm(int(b))}"
                for a, b in (q.get("shift_windows") or [])
            ]
            hang.append(
                {
                    "id": r["id"],
                    "ten": r["full_name"],
                    "bs_cu": r["id"] == bs_cu,
                    "ca": " · ".join(ca) or None,
                    "o": o,
                    "ngay_bay_gio": ngay_bay_gio,
                }
            )

    la_hom_nay = chon == hom_nay
    return {
        "ok": True,
        "ngay": chon.isoformat(),
        "hom_nay": hom_nay.isoformat(),
        "ngay_mai": (hom_nay + timedelta(days=1)).isoformat(),
        "la_hom_nay": la_hom_nay,
        "da_qua": da_qua,
        "lich": {
            "id": lich["id"],
            "ten_khach": lich["ten_khach"],
            "clinic_patient_id": lich["clinic_patient_id"],
            "slot_start": lich["slot_start"].isoformat(),
            "bac_si_id": bs_cu,
            "bac_si_ten": lich["ten_bac_si"],
            "dich_vu": lich["dich_vu"],
            "trang_thai": lich["status"],
        },
        # Nút "Đổi & Check-in luôn": có quyền + ngày chọn là hôm nay + khách
        # chưa check-in. Máy chủ chốt lại lúc ghi.
        "cho_check_in": bool(
            co_quyen_check_in and la_hom_nay and lich["status"] in _TRUOC_KHI_DEN
        ),
        "ly_do": list(LY_DO_DOI_LICH),
        "ly_do_mac_dinh": LY_DO_DOI_LICH[0],
        "bac_si": hang,
    }
