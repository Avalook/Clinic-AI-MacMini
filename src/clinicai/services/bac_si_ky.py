"""Tên BÁC SĨ ở chỗ ký / chỗ "bác sĩ" — trên giấy in và trên màn.

Luật (Tuyền 29/09/2026): *mọi phiếu IN ra ký TÊN BÁC SĨ, kể cả khi điều dưỡng /
thư ký thao tác hộ; người nhập chỉ ở lịch sử.* KHÔNG BAO GIỜ in tên người không
phải bác sĩ ở chỗ ký hay ở nhãn "bác sĩ". Không tìm được bác sĩ → để TRỐNG, không
lùi về người bấm.

"Là bác sĩ" = danh tính tài khoản (`clinic_membership.role` DOCTOR /
ULTRASOUND_DOCTOR, còn hoạt động) — xem `bac_si_phu_trach.VAI_BAC_SI`. Trợ lý có
trọn quyền vẫn không thành bác sĩ trên giấy.

Hai hàm đọc (không ghi gì), cùng một nguồn SQL với các màn liệt kê:

* `bac_si_ky_in` — ai ký "Bác sĩ thực hiện" / "Người thực hiện" của một chỉ định.
  Lịch phòng tính theo NGÀY + GIỜ `luc` (lúc hoàn tất / lúc làm), không theo giờ
  in: in lại phiếu hôm trước phải ra bác sĩ hôm làm.
* `bac_si_chi_dinh_hien_thi` — "BS chỉ định": ứng viên đầu tiên là bác sĩ trong
  người duyệt, người ghi, bác sĩ chính của lượt, bác sĩ của lịch hẹn.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import NamedTuple

import asyncpg

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bac_si_phu_trach import (
    VAI_BAC_SI,
    bac_si_dang_trong_ca,
    bac_si_trong,
)


class BacSi(NamedTuple):
    id: str
    ten: str | None


_VAI_SQL = "ARRAY[" + ", ".join(f"'{v}'" for v in VAI_BAC_SI) + "]::text[]"


def sql_bac_si_dau_tien(ung_vien: Iterable[str], clinic: str) -> str:
    """Câu SQL con (dùng trong LEFT JOIN LATERAL): ``(id, full_name)`` của ỨNG
    VIÊN ĐẦU TIÊN là bác sĩ còn hoạt động của phòng khám.

    `ung_vien` là các biểu thức uuid theo thứ tự ưu tiên; `clinic` là biểu thức
    clinic_id. Không ai là bác sĩ → không dòng nào (tên để trống)."""
    ds = ", ".join(ung_vien)
    return (
        "SELECT s.id, s.full_name"
        f"  FROM unnest(ARRAY[{ds}]::uuid[]) WITH ORDINALITY AS u(id, thu_tu)"
        "  JOIN public.clinic_membership m"
        f"    ON m.clinic_id = {clinic} AND m.staff_id = u.id"
        f"   AND m.is_active AND m.role = ANY({_VAI_SQL})"
        "  JOIN public.staff s ON s.id = u.id"
        " ORDER BY u.thu_tu LIMIT 1"
    )


def _bac_si_luot_cua_chi_dinh(o: str) -> tuple[str, str]:
    """Hai biểu thức: bác sĩ chính của lượt, bác sĩ của lịch hẹn — từ chỉ định `o`."""
    luot = (
        "(SELECT vv.attending_doctor_id FROM public.visit vv"
        f"  WHERE vv.visit_id = {o}.visit_id AND vv.clinic_id = {o}.clinic_id)"
    )
    lich = (
        "(SELECT aa.doctor_id FROM public.visit vv"
        "   JOIN public.appointment aa"
        "     ON aa.id = vv.appointment_id AND aa.clinic_id = vv.clinic_id"
        f"  WHERE vv.visit_id = {o}.visit_id AND vv.clinic_id = {o}.clinic_id)"
    )
    return luot, lich


def sql_join_bac_si_chi_dinh(o: str = "o", ten: str = "bscd") -> str:
    """``LEFT JOIN LATERAL`` gắn "BS chỉ định" của chỉ định `o` vào bí danh
    `ten` (cột ``id``, ``full_name``). Thứ tự: người duyệt → người ghi → bác sĩ
    chính của lượt → bác sĩ của lịch hẹn; chỉ lấy người là bác sĩ."""
    luot, lich = _bac_si_luot_cua_chi_dinh(o)
    return (
        "LEFT JOIN LATERAL ("
        + sql_bac_si_dau_tien(
            [f"{o}.authorized_by", f"{o}.recorded_by", luot, lich], f"{o}.clinic_id"
        )
        + f") {ten} ON true"
    )


def sql_join_bac_si_ky_luot(v: str = "v", ten: str = "bsky") -> str:
    """``LEFT JOIN LATERAL`` gắn bác sĩ đứng tên HOÀN TẤT của lượt `v`: người
    bấm Hoàn tất nếu là bác sĩ → bác sĩ chính của lượt → bác sĩ của lịch hẹn."""
    lich = (
        "(SELECT aa.doctor_id FROM public.appointment aa"
        f"  WHERE aa.id = {v}.appointment_id AND aa.clinic_id = {v}.clinic_id)"
    )
    return (
        "LEFT JOIN LATERAL ("
        + sql_bac_si_dau_tien(
            [f"{v}.finalized_by", f"{v}.attending_doctor_id", lich], f"{v}.clinic_id"
        )
        + f") {ten} ON true"
    )


_BAC_SI_CHI_DINH_SQL = f"""
SELECT b.id::text AS id, b.full_name
  FROM public.service_order o
  {sql_join_bac_si_chi_dinh("o", "b")}
 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid AND b.id IS NOT NULL
"""

# Bác sĩ của lượt (không tính người chỉ định) — bậc 3 của `bac_si_ky_in`: bác sĩ
# chính của lượt → bác sĩ lịch hẹn → rồi mới tới bác sĩ đã chỉ định.
_luot, _lich = _bac_si_luot_cua_chi_dinh("o")
_BAC_SI_LUOT_ROI_CHI_DINH_SQL = f"""
SELECT b.id::text AS id, b.full_name
  FROM public.service_order o
  LEFT JOIN LATERAL ({
    sql_bac_si_dau_tien(
        [_luot, _lich, "o.authorized_by", "o.recorded_by"], "o.clinic_id"
    )
}) b ON true
 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid AND b.id IS NOT NULL
"""

# Bác sĩ đứng PHÒNG của chỉ định theo lịch NGÀY `$4` (không phải hôm nay).
_BAC_SI_DUNG_PHONG_NGAY_SQL = f"""
SELECT w.staff_id::text AS id, w.station, w.shift, w.status, c.settings
  FROM public.service_order o
  JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = o.clinic_id AND v.room_id = o.room_id
  JOIN public.work_roster w
    ON w.clinic_id = v.clinic_id AND w.station = v.code
  JOIN public.clinic_membership m
    ON m.clinic_id = w.clinic_id AND m.staff_id = w.staff_id
   AND m.is_active AND m.role = ANY({_VAI_SQL})
  JOIN public.clinic c ON c.id = o.clinic_id
 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
   AND w.status <> 'REJECTED'
   AND w.work_date = $3::date
 ORDER BY array_position(ARRAY['SANG', 'CHIEU', 'TOI', 'FULL'], w.shift),
          v.sort NULLS LAST, w.station, w.staff_id
"""


async def _ten(conn: asyncpg.Connection, staff_id: str) -> BacSi:
    ten = await conn.fetchval(
        "SELECT full_name FROM public.staff WHERE id = $1::uuid", staff_id
    )
    return BacSi(staff_id, ten)


async def bac_si_ky_in(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    service_order_id: str,
    nguoi_bam: Iterable[str | None] | str | None,
    luc: datetime | None,
) -> BacSi | None:
    """Bác sĩ ký "Bác sĩ thực hiện" / "Người thực hiện" của chỉ định — hoặc None.

    1. Người thực hiện / người bấm (`nguoi_bam`, theo thứ tự) là bác sĩ → họ.
    2. Phòng của chỉ định có ĐÚNG MỘT bác sĩ đang trong ca lúc `luc` (lịch của
       NGÀY `luc`, giờ `luc` — không phải giờ in) → bác sĩ ấy.
    3. Bác sĩ chính của lượt → bác sĩ của lịch hẹn → bác sĩ đã chỉ định (người
       duyệt, người ghi) — người đầu tiên là bác sĩ.
    4. Không ai → None: chỗ ký để TRỐNG. Không bao giờ lùi về người bấm.
    """
    ds = [nguoi_bam] if isinstance(nguoi_bam, str) or nguoi_bam is None else nguoi_bam
    ung_vien = [str(x) for x in ds if x]
    if ung_vien:
        la_bs = await bac_si_trong(conn, clinic_id, ung_vien)
        for ai in ung_vien:
            if ai in la_bs:
                return await _ten(conn, ai)
    if luc is not None:
        gio = luc.astimezone(CLINIC_TZ)
        rows = await conn.fetch(
            _BAC_SI_DUNG_PHONG_NGAY_SQL, clinic_id, service_order_id, gio.date()
        )
        if rows:
            trong_ca = bac_si_dang_trong_ca(
                [
                    (r["id"], str(r["station"]), str(r["shift"]), str(r["status"]))
                    for r in rows
                ],
                gio.hour * 60 + gio.minute,
                rows[0]["settings"],
            )
            if len(trong_ca) == 1:
                return await _ten(conn, trong_ca[0])
    r = await conn.fetchrow(_BAC_SI_LUOT_ROI_CHI_DINH_SQL, clinic_id, service_order_id)
    return BacSi(r["id"], r["full_name"]) if r else None


async def bac_si_chi_dinh_hien_thi(
    conn: asyncpg.Connection, clinic_id: str, service_order_id: str
) -> BacSi | None:
    """ "BS chỉ định" của chỉ định: ứng viên đầu tiên là bác sĩ trong người duyệt,
    người ghi, bác sĩ chính của lượt, bác sĩ lịch hẹn. Không ai → None."""
    r = await conn.fetchrow(_BAC_SI_CHI_DINH_SQL, clinic_id, service_order_id)
    return BacSi(r["id"], r["full_name"]) if r else None


__all__ = [
    "BacSi",
    "bac_si_chi_dinh_hien_thi",
    "bac_si_ky_in",
    "sql_bac_si_dau_tien",
    "sql_join_bac_si_chi_dinh",
    "sql_join_bac_si_ky_luot",
]
