"""Khối CHUÔNG — sự kiện nào báo cho ai (nhóm 3, Tuyền chốt 23–24/09/2026).

"Tệp kết quả phát cho bác sĩ, thư ký, điều dưỡng, CSKH — người nhận chỉnh được."

Trước đây lệnh tải tệp GỌI THẲNG `bao_ket_qua_ve` (CSKH + bác sĩ, cứng trong
code). Nay lệnh chỉ phát `result_file.uploaded`; khối này nghe rồi báo. Người
nhận là DỮ LIỆU: bảng `day_nhan_thong_bao` (vai + bác sĩ chính đích danh + bật/
tắt), quản lý chỉnh trên màn. Chưa có dòng → `MAC_DINH` bên dưới (khớp migration
20260924000004).

Chuông ghi `thong_bao` trong CHÍNH giao dịch đánh dấu DONE của người đưa tin:
chạy lại không nhân đôi (chốt "một việc đang mở một lần" của `thong_bao`).
PHÁT LẠI (`la_phat_lai`) thì im — không réo chuông cho chuyện hôm qua.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg

from clinicai.events.catalogue import CHUONG
from clinicai.events.worker import SuKienDaNhan, dang_ky


@dataclass(frozen=True)
class DayNhan:
    vai: Sequence[str]
    bac_si_chinh: bool
    bat: bool = True


#: Mặc định khi phòng khám chưa chỉnh (cùng giá trị migration đã gieo).
MAC_DINH: dict[str, DayNhan] = {
    "result_file.uploaded": DayNhan(["CSKH", "TKYK", "NURSE_ULTRASOUND"], True),
    # Tệp đối tác được xác nhận HỢP LỆ (23/09 khuya): bác sĩ chính đọc, CSKH gửi.
    "result_file.confirmed": DayNhan(["CSKH"], True),
    "result.ready": DayNhan(["TKYK"], True),
    # Kết quả đã công bố được SỬA LẠI (28/09/2026): cùng người nhận như kết quả mới.
    "result.corrected": DayNhan(["TKYK"], True),
    # Kết quả xét nghiệm nhập tay (trước 24/09 gọi thẳng: CSKH + bác sĩ).
    "lab_result.arrived": DayNhan(["CSKH"], True),
    # Việc mới sang bàn đối tác (24/09/2026).
    "partner.order_received": DayNhan(["PARTNER"], False),
}

#: Màn mở ra khi bấm chuông, theo vai nhận.
_DUONG_DAN: dict[str, str] = {
    "CSKH": "/customers",
    "TKYK": "/ban-kham",
    "DOCTOR": "/ban-kham",
    "NURSE_ULTRASOUND": "/xac-nhan-ket-qua",
    "PARTNER": "/doi-tac",
}


async def day_nhan(
    conn: asyncpg.Connection, clinic_id: str, su_kien: str
) -> DayNhan | None:
    """Ai nhận chuông của sự kiện này ở phòng khám này (None = sự kiện không réo)."""
    row = await conn.fetchrow(
        "SELECT vai, bac_si_chinh, bat FROM day_nhan_thong_bao"
        " WHERE clinic_id = $1::uuid AND su_kien = $2",
        clinic_id,
        su_kien,
    )
    if row is not None:
        return DayNhan(
            list(row["vai"] or []), bool(row["bac_si_chinh"]), bool(row["bat"])
        )
    return MAC_DINH.get(su_kien)


async def _khach_va_bac_si(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan
) -> asyncpg.Record | None:
    """Tên khách (cho tiêu đề chuông — nằm ở bảng hiện trạng, không ở sổ) + bác
    sĩ chính của lượt. Tệp chưa gắn lượt thì đi qua chính tệp."""
    visit_id = su_kien.payload.get("visit_id")
    tep_id = su_kien.payload.get("tep_id")
    lab_id = su_kien.payload.get("lab_result_id")
    return await conn.fetchrow(
        """
        SELECT p.clinic_patient_id::text AS pid, p.full_name, p.patient_code,
               coalesce(v.attending_doctor_id, a.doctor_id)::text AS bac_si_id
          FROM (SELECT $2::uuid AS visit_id, $3::uuid AS tep_id,
                       $4::uuid AS lab_id) k
          LEFT JOIN visit v
            ON v.clinic_id = $1::uuid AND v.visit_id = k.visit_id
          LEFT JOIN tep_ket_qua t
            ON t.clinic_id = $1::uuid AND t.id = k.tep_id
          LEFT JOIN lab_result l
            ON l.clinic_id = $1::uuid AND l.lab_result_id = k.lab_id
          LEFT JOIN appointment a
            ON a.clinic_id = $1::uuid
           AND a.id = coalesce(v.appointment_id, t.appointment_id, l.appointment_id)
          JOIN patient p
            ON p.clinic_id = $1::uuid
           AND p.clinic_patient_id = coalesce(
                   v.clinic_patient_id, t.clinic_patient_id, l.clinic_patient_id)
        """,
        su_kien.clinic_id,
        visit_id,
        tep_id,
        lab_id,
    )


async def bao_chuong(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    # Xác nhận tệp: chỉ HỢP LỆ là tin đáng réo — TỪ CHỐI là việc của người
    # xác nhận với đối tác, không phải của bác sĩ.
    if (
        su_kien.event_type == "result_file.confirmed"
        and su_kien.payload.get("trang_thai") != "HOP_LE"
    ):
        return
    day = await day_nhan(conn, su_kien.clinic_id, su_kien.event_type)
    if day is None or not day.bat:
        return
    # `thong_bao.nguoi_goi_staff_id` bắt buộc: người gây ra sự kiện (người tải
    # tệp, người hoàn tất phiếu). Sự kiện hệ thống không réo chuông.
    if not su_kien.actor_staff_id:
        return
    k = await _khach_va_bac_si(conn, su_kien)
    if k is None:
        return
    ten = f"{k['full_name']} ({k['patient_code']})"
    if su_kien.event_type == "result_file.uploaded":
        tieu_de = f"Tệp kết quả của {ten} đã về"
        noi_dung = (
            "Tệp của đối tác — cần xác nhận đúng người, đúng chỉ định."
            if su_kien.payload.get("cho_xac_nhan")
            else "Kết quả đã vào hồ sơ khách — mở là tự ghi đã xem."
        )
    elif su_kien.event_type == "result_file.confirmed":
        tieu_de = f"Kết quả đối tác của {ten} đã xác nhận"
        noi_dung = "Tệp hợp lệ, đã vào hồ sơ — bác sĩ đọc, CSKH gửi khách được."
    elif su_kien.event_type == "lab_result.arrived":
        tieu_de = f"Kết quả xét nghiệm của {ten} đã về"
        noi_dung = "Gửi cho khách được ngay; bác sĩ xem khi cần."
    elif su_kien.event_type == "partner.order_received":
        dv = su_kien.payload.get("service_name") or "chỉ định"
        tieu_de = f"Việc mới: {dv} — {ten}"
        ly_do = su_kien.payload.get("ly_do")
        noi_dung = (
            "Khách đã thanh toán — đối tác đến lấy mẫu."
            if ly_do == "DA_THU_TIEN"
            # Đối tác tự thu (27/09/2026): khách trả trực tiếp khi lấy mẫu.
            else "Khách đã chốt làm — đối tác đến lấy mẫu và thu tiền khách."
            if ly_do == "KHACH_DA_CHON"
            # Mẫu gửi đối tác (29/09/2026): phòng của phòng khám làm xong.
            else "Mẫu gửi đối tác — phòng khám đã có mẫu, đối tác nhận và trả kết quả."
            if ly_do == "MAU_GUI_DOI_TAC"
            else "Phòng đã lấy mẫu xong — đối tác nhận mẫu, trả kết quả."
        )
    elif su_kien.event_type == "result.corrected":
        tieu_de = f"Kết quả của {ten} đã được SỬA LẠI"
        noi_dung = "Phòng đã sửa phiếu kết quả — bác sĩ đọc lại bản mới."
    else:
        tieu_de = f"Có kết quả mới của {ten}"
        noi_dung = "Phòng đã hoàn tất phiếu kết quả."
    nguon_id = f"{su_kien.event_type}:{su_kien.aggregate_id}"
    for vai in day.vai:
        duong = _DUONG_DAN.get(vai, "/home")
        if vai == "CSKH":
            duong = f"/customers?selected={k['pid']}"
        await ghi_chuong_vai(
            conn,
            clinic_id=su_kien.clinic_id,
            vai=vai,
            tieu_de=tieu_de,
            noi_dung=noi_dung,
            nguon=(
                "doi_tac_viec"
                if su_kien.event_type == "partner.order_received"
                else "ket_qua_ve"
            ),
            nguon_id=nguon_id,
            duong_dan=duong,
            nguoi_goi=su_kien.actor_staff_id,
        )
    if day.bac_si_chinh and k["bac_si_id"]:
        await ghi_chuong_nguoi(
            conn,
            clinic_id=su_kien.clinic_id,
            nguoi_nhan=k["bac_si_id"],
            tieu_de=tieu_de,
            noi_dung=noi_dung,
            nguon="ket_qua_ve",
            nguon_id=nguon_id,
            duong_dan="/ban-kham",
            nguoi_goi=su_kien.actor_staff_id,
        )


async def ghi_chuong_vai(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    vai: str,
    tieu_de: str,
    noi_dung: str,
    nguon: str,
    nguon_id: str,
    duong_dan: str | None,
    nguoi_goi: str,
    muc_do: str = "THUONG",
) -> None:
    """Một chuông cho CẢ VAI. Việc đang mở cùng nguồn thì không tạo thêm."""
    await conn.execute(
        """
        INSERT INTO thong_bao
            (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
             duong_dan, nguoi_goi_staff_id)
        VALUES ($1::uuid, $2, $8, $3, $4, $9, $5, $6, $7::uuid)
        ON CONFLICT (clinic_id, nguon, nguon_id, vai_nhan)
            WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL
              AND vai_nhan IS NOT NULL
        DO NOTHING
        """,
        clinic_id,
        vai,
        tieu_de,
        noi_dung,
        nguon_id,
        duong_dan,
        nguoi_goi,
        muc_do,
        nguon,
    )


async def ghi_chuong_nguoi(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    nguoi_nhan: str,
    tieu_de: str,
    noi_dung: str,
    nguon: str,
    nguon_id: str,
    duong_dan: str | None,
    nguoi_goi: str,
    muc_do: str = "THUONG",
) -> None:
    """Một chuông ĐÍCH DANH một người."""
    await conn.execute(
        """
        INSERT INTO thong_bao
            (clinic_id, nguoi_nhan_staff_id, muc_do, tieu_de, noi_dung, nguon,
             nguon_id, duong_dan, nguoi_goi_staff_id)
        VALUES ($1::uuid, $2::uuid, $8, $3, $4, $9, $5, $6, $7::uuid)
        ON CONFLICT (clinic_id, nguon, nguon_id, nguoi_nhan_staff_id)
            WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL
              AND vai_nhan IS NULL
        DO NOTHING
        """,
        clinic_id,
        nguoi_nhan,
        tieu_de,
        noi_dung,
        nguon_id,
        duong_dan,
        nguoi_goi,
        muc_do,
        nguon,
    )


dang_ky(CHUONG, bao_chuong)

__all__ = [
    "MAC_DINH",
    "DayNhan",
    "bao_chuong",
    "day_nhan",
    "ghi_chuong_nguoi",
    "ghi_chuong_vai",
]
