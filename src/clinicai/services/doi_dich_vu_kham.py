"""Đổi DỊCH VỤ KHÁM ngay ở menu ⋯ của dòng lịch hẹn (V5, Tuyền chốt 30/09/2026).

Popover mở ở dòng khách (Tiếp đón, Trang chủ): chọn loại khám khác → [Đổi].

* **Trước check-in**: đổi `appointment.service_type_id`. Chạy lại luật "bác sĩ
  bắt buộc theo dịch vụ" (`BookingService._luat_bac_si_bat_buoc`) và kiểm bác
  sĩ của lịch còn khám ở phòng khám.
* **Sau check-in**: đổi cả `visit.service_type_id` lẫn lịch — CHỈ khi phiên
  khám chưa bắt đầu, chưa có phiếu khám của lượt, chưa thu tiền khám, chưa tick
  dịch vụ khám con. Đổi xong, khối Hành trình nghe `appointment.service_switched`
  và tính lại hàng chờ đầu tiên (`LuotKhamService.xep_lai_sau_doi_dich_vu`).

MÁY CHỦ QUYẾT được đổi hay không và vì sao (`ly_do_khong_doi` — hàm thuần, test
được); màn hình chỉ vẽ câu trả về. Phần GHI là `BookingService.doi_dich_vu_kham`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA
from clinicai.services.bill_service import _DA_PHU
from clinicai.services.dich_vu_dat_lich import COT_SQL, gom_nhom, ten_sach
from clinicai.services.lenh_kham_core import ma_uuid

#: Có MỘT trong hai quyền là đổi được (Tuyền chốt 30/09/2026): người quản lý
#: lịch hoặc người đón khách ở quầy.
QUYEN_DOI_DICH_VU_KHAM: tuple[str, ...] = (
    "booking.manage",
    "reception.checkin.perform",
)

#: Đổi TRONG HỒ SƠ KHÁM (Tuyền chốt 07/10/2026, T5): bác sĩ, điều dưỡng, thư ký
#: (khối y khoa) + trưởng ca (điều phối khách); quản lý có mọi khối.
QUYEN_DOI_TRONG_HO_SO: tuple[str, ...] = (*QUYEN_Y_KHOA, "dispatch.manage")

#: Lịch chưa tới quầy — chỉ đổi lịch, chưa có lượt khám. DOCTOR_DECLINED (bác sĩ
#: từ chối, chờ xếp người khác) cũng là lịch chưa khám.
TRUOC_CHECK_IN = frozenset(
    {"SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "DOCTOR_DECLINED"}
)

#: Lượt đã check-out (``visit.closed_at``) — mọi đường đổi dịch vụ khám.
CAU_DA_CHECK_OUT = "Lượt đã check-out — mở lại lượt trước."

_LICH_DA_XONG: dict[str, str] = {
    "COMPLETED": "Lịch đã khám xong",
    "CANCELLED": "Lịch đã huỷ",
    "NO_SHOW": "Lịch đã ghi khách không đến",
}


def ly_do_khong_doi(
    *,
    trang_thai_lich: str,
    trang_thai_luot: str | None,
    phien_da_bat_dau: bool,
    co_phieu_kham: bool,
    da_thu_tien_kham: bool,
    da_chon_dich_vu_con: bool,
    trong_ho_so: bool = False,
    da_check_out: bool = False,
) -> str | None:
    """Câu nói rõ vì sao KHÔNG đổi được dịch vụ khám; None = đổi được.

    ``trong_ho_so`` (Tuyền chốt 07/10/2026, T5): đổi ngay trong hồ sơ khám —
    phiên đã bắt đầu, đã có phiếu, đã thu tiền khám, đã tick dịch vụ con đều
    ĐỔI ĐƯỢC (phiếu cũ giữ nguyên, tick giữ nguyên, chênh tiền theo luật tiền
    thừa / nợ). Chỉ lượt đã đóng (check-out) mới không đổi ở đây.

    ``da_check_out``: check-out chỉ đặt ``visit.closed_at`` (status vẫn
    IN_PROGRESS) — đổi dịch vụ sau khi khách về là đổi phí khám, xếp lại hàng
    cho người không còn ở phòng khám (review 07/10/2026).
    """
    if trang_thai_luot is not None and da_check_out:
        return CAU_DA_CHECK_OUT
    if trong_ho_so:
        if trang_thai_luot is None:
            return "Lượt khám chưa mở — đổi dịch vụ ở dòng lịch hẹn."
        if trang_thai_luot not in ("OPEN", "IN_PROGRESS"):
            return "Lượt khám đã đóng (khách đã về) — không đổi dịch vụ khám được."
        return None
    if trang_thai_lich in TRUOC_CHECK_IN:
        return None
    if trang_thai_lich != "CHECKED_IN":
        dau = _LICH_DA_XONG.get(trang_thai_lich, "Lịch không còn hiệu lực")
        return f"{dau} — không đổi dịch vụ khám được."
    if trang_thai_luot is None:
        return "Lịch đã check-in nhưng chưa thấy lượt khám — tải lại trang rồi thử lại."
    if trang_thai_luot == "INCOMPLETE":
        return "Khách đã về giữa chừng (lượt dừng) — không đổi dịch vụ khám được."
    if trang_thai_luot not in ("OPEN", "IN_PROGRESS"):
        return "Lượt khám đã đóng — không đổi dịch vụ khám được."
    if phien_da_bat_dau:
        return (
            "Bác sĩ đã bắt đầu khám lượt này — không đổi dịch vụ khám được nữa. "
            "Cần thêm dịch vụ thì chỉ định thêm."
        )
    if co_phieu_kham:
        return "Lượt này đã có phiếu khám đang ghi — không đổi dịch vụ khám được nữa."
    if da_thu_tien_kham:
        return (
            "Tiền khám của lượt này đã thu — huỷ phiếu thu trước rồi mới đổi "
            "dịch vụ khám."
        )
    if da_chon_dich_vu_con:
        return (
            "Lượt này đã chọn dịch vụ khám con — bỏ chọn ở mục Dịch vụ khám "
            "trước rồi mới đổi loại khám."
        )
    return None


@dataclass(frozen=True)
class TrangThaiDoi:
    """Những gì cần biết để quyết đổi được hay không — một lần đọc."""

    appointment_id: str
    trang_thai_lich: str
    clinic_patient_id: str
    doctor_id: str | None
    dich_vu_id: str | None
    ten_dich_vu: str | None
    visit_id: str | None
    trang_thai_luot: str | None
    phien_da_bat_dau: bool
    co_phieu_kham: bool
    da_thu_tien_kham: bool
    da_chon_dich_vu_con: bool
    bac_si_con_kham: bool
    da_check_out: bool = False

    @property
    def sau_check_in(self) -> bool:
        return self.trang_thai_lich == "CHECKED_IN"

    def ly_do_khong_doi(self, *, trong_ho_so: bool = False) -> str | None:
        return ly_do_khong_doi(
            trang_thai_lich=self.trang_thai_lich,
            trang_thai_luot=self.trang_thai_luot,
            phien_da_bat_dau=self.phien_da_bat_dau,
            co_phieu_kham=self.co_phieu_kham,
            da_thu_tien_kham=self.da_thu_tien_kham,
            da_chon_dich_vu_con=self.da_chon_dich_vu_con,
            trong_ho_so=trong_ho_so,
            da_check_out=self.da_check_out,
        )


_DA_THU_TIEN_KHAM = _DA_PHU.format(loai="'exam'", nguon="('exam-' || v.visit_id::text)")

_TRANG_THAI_SQL = f"""
SELECT a.id::text AS appointment_id, a.status, a.clinic_patient_id::text,
       a.doctor_id::text, a.service_type_id::text AS dich_vu_id,
       st.name AS ten_dich_vu,
       v.visit_id::text, v.status AS trang_thai_luot,
       v.closed_at IS NOT NULL AS da_check_out,
       EXISTS (
           SELECT 1 FROM public.consultation c
            WHERE c.clinic_id = a.clinic_id AND c.visit_id = v.visit_id
              AND c.status NOT IN ('queued', 'cancelled')) AS phien_da_bat_dau,
       EXISTS (
           SELECT 1 FROM public.phieu_kham_luot p
            WHERE p.clinic_id = a.clinic_id AND p.visit_id = v.visit_id)
           AS co_phieu_kham,
       EXISTS (
           SELECT 1 FROM public.luot_phi_kham l
            WHERE l.clinic_id = a.clinic_id AND l.visit_id = v.visit_id
              AND l.bo_luc IS NULL) AS da_chon_dich_vu_con,
       {_DA_THU_TIEN_KHAM} AS da_thu_tien_kham,
       (a.doctor_id IS NULL OR EXISTS (
           SELECT 1 FROM public.staff s
             JOIN public.clinic_membership m ON m.staff_id = s.id
            WHERE s.id = a.doctor_id AND s.is_active
              AND m.clinic_id = a.clinic_id AND m.is_active
              AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR'))) AS bac_si_con_kham
  FROM public.appointment a
  LEFT JOIN public.service_type st
    ON st.id = a.service_type_id AND st.clinic_id = a.clinic_id
  LEFT JOIN public.visit v
    ON v.appointment_id = a.id AND v.clinic_id = a.clinic_id
 WHERE a.clinic_id = $1::uuid AND a.id = $2::uuid
"""


async def doc_trang_thai(
    conn: asyncpg.Connection, clinic_id: str, appointment_id: str
) -> TrangThaiDoi:
    r = await conn.fetchrow(_TRANG_THAI_SQL, clinic_id, appointment_id)
    if r is None:
        raise NotFoundError("Không tìm thấy lịch hẹn")
    return TrangThaiDoi(
        appointment_id=r["appointment_id"],
        trang_thai_lich=r["status"],
        clinic_patient_id=r["clinic_patient_id"],
        doctor_id=r["doctor_id"],
        dich_vu_id=r["dich_vu_id"],
        ten_dich_vu=r["ten_dich_vu"],
        visit_id=r["visit_id"],
        trang_thai_luot=r["trang_thai_luot"],
        phien_da_bat_dau=bool(r["phien_da_bat_dau"]),
        co_phieu_kham=bool(r["co_phieu_kham"]),
        da_thu_tien_kham=bool(r["da_thu_tien_kham"]),
        da_chon_dich_vu_con=bool(r["da_chon_dich_vu_con"]),
        bac_si_con_kham=bool(r["bac_si_con_kham"]),
        da_check_out=bool(r["da_check_out"]),
    )


async def o_doi_dich_vu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, appointment_id: str
) -> dict[str, Any]:
    """Gói của popover: dịch vụ hiện tại, danh sách chọn, đổi được không + vì sao.

    Mỗi lựa chọn kèm luật bác sĩ bắt buộc với bác sĩ đang xếp: ``chan`` = chọn
    là bị từ chối (câu ở ``ghi_chu``); không chặn mà vẫn vướng luật thì chỉ
    nhắc. Lệnh ghi vẫn tự kiểm lại tất cả.
    """
    # Import muộn: booking_service nhập module này (vòng nhập).
    from clinicai.services.booking_service import BookingService

    aid = ma_uuid(appointment_id, "Mã lịch hẹn không hợp lệ.")
    cid = identity.clinic_id
    luat = BookingService(pool)
    async with pool.acquire() as conn:
        tt = await doc_trang_thai(conn, cid, aid)
        # Cùng nguồn + cùng nhóm với ô chọn lúc đặt lịch (`dich_vu_dat_lich`).
        dich_vu = await conn.fetch(
            f"SELECT {COT_SQL} FROM public.service_type"
            " WHERE clinic_id = $1::uuid AND is_active AND nhom <> 'THUOC'"
            " ORDER BY thu_tu, name",
            cid,
        )
        lua_chon: list[dict[str, Any]] = []
        for d in dich_vu:
            ghi_chu: str | None = None
            chan = False
            if d["id"] != tt.dich_vu_id:
                loi = await luat._luat_bac_si_bat_buoc(
                    conn,
                    clinic_patient_id=tt.clinic_patient_id,
                    service_type_id=d["id"],
                    doctor_id=tt.doctor_id,
                    identity=identity,
                )
                if loi:
                    ghi_chu, chan = loi
            lua_chon.append(
                {
                    "id": d["id"],
                    "ten": ten_sach(d["name"]),
                    "hien_tai": d["id"] == tt.dich_vu_id,
                    "chan": chan,
                    "ghi_chu": ghi_chu,
                    "nhom": d["nhom"],
                    "form_code": d["form_code"],
                }
            )
    ly_do = tt.ly_do_khong_doi()
    if ly_do is None and not tt.bac_si_con_kham:
        ly_do = CAU_BAC_SI_NGHI
    return {
        "appointment_id": tt.appointment_id,
        "da_check_in": tt.sau_check_in,
        "dich_vu_hien_tai": (
            {"id": tt.dich_vu_id, "ten": tt.ten_dich_vu} if tt.dich_vu_id else None
        ),
        "duoc_doi": ly_do is None,
        "ly_do_khong_doi": ly_do,
        "lua_chon": lua_chon,
        # Cùng danh sách, gom theo nhóm đặt lịch (Khám · Điều trị · Khác).
        "nhom": gom_nhom(lua_chon),
    }


CAU_BAC_SI_NGHI = (
    "Bác sĩ của lịch không còn khám ở phòng khám — dùng Đổi lịch chọn bác sĩ "
    "khác trước rồi mới đổi dịch vụ."
)


__all__ = [
    "CAU_BAC_SI_NGHI",
    "QUYEN_DOI_DICH_VU_KHAM",
    "QUYEN_DOI_TRONG_HO_SO",
    "TRUOC_CHECK_IN",
    "TrangThaiDoi",
    "doc_trang_thai",
    "ly_do_khong_doi",
    "o_doi_dich_vu",
]
