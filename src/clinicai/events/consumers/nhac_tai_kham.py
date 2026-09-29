"""Tới hạn gọi tái khám (ngày hẹn − 7) → CHUÔNG cho người có lego CSKH.

Luật hẹn giờ: tới giờ KIỂM LẠI hiện trạng. Việc đã đóng (khách đã có lịch, bác
sĩ bỏ hẹn), ngày hẹn đã đổi so với lúc hẹn chuông, hay khách vừa đặt lịch — thì
thôi, trả False ("hết cần"). Chuông ghi cùng giao dịch với dấu XONG của cái hẹn.
"""

from __future__ import annotations

import asyncpg

from clinicai.api.identity import ClinicRole
from clinicai.events.consumers.chuong import ghi_chuong_vai
from clinicai.events.hen_gio import HenDenHan, dang_ky_loai
from clinicai.services.hen_tai_kham_service import (
    HEN_NHAC_TAI_KHAM,
    NGUON_CHUONG,
    chi_tiet_viec,
)


def noi_dung_chuong(ct: dict[str, object] | None) -> str:
    """Một dòng đủ để gọi: bác sĩ · loại khám lần trước · chẩn đoán · cần kiểm
    tra lại · ghi chú bác sĩ. Thiếu phần nào thì bỏ phần ấy."""
    if not ct:
        return "Gọi khách chốt giờ tái khám."
    phan: list[str] = []
    if ct.get("bac_si"):
        phan.append(f"BS {ct['bac_si']}")
    if ct.get("loai_kham"):
        phan.append(f"lần trước: {ct['loai_kham']}")
    if ct.get("chan_doan"):
        phan.append(f"CĐ: {ct['chan_doan']}")
    kiem = ct.get("can_kiem_tra")
    if isinstance(kiem, list) and kiem:
        phan.append("kiểm tra lại: " + ", ".join(str(k) for k in kiem))
    if ct.get("ghi_chu_bac_si"):
        phan.append(f"ghi chú BS: {ct['ghi_chu_bac_si']}")
    return ("Gọi khách chốt giờ tái khám. " + " · ".join(phan))[:1000]


async def bao_den_han(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
    viec = await conn.fetchrow(
        """
        SELECT n.id::text, n.ngay_hen, n.trang_thai, n.nguon_visit_id::text AS visit_id,
               p.clinic_patient_id::text AS pid, p.full_name, p.patient_code,
               EXISTS (
                   SELECT 1 FROM appointment a
                    WHERE a.clinic_id = n.clinic_id
                      AND a.clinic_patient_id = n.clinic_patient_id
                      AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED',
                                       'CONFIRMED', 'CHECKED_IN')
                      AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                          >= n.han_goi
               ) AS co_lich
          FROM nhac_tai_kham n
          JOIN patient p ON p.clinic_patient_id = n.clinic_patient_id
         WHERE n.clinic_id = $1::uuid AND n.id = $2::uuid
        """,
        cai_hen.clinic_id,
        cai_hen.ve_cai_gi,
    )
    if viec is None or viec["trang_thai"] != "CHO_GOI":
        return False
    if cai_hen.chi_tiet.get("ngay_hen") != viec["ngay_hen"].isoformat():
        return False
    nguoi_goi = cai_hen.chi_tiet.get("nguoi_goi")
    if viec["co_lich"] or not nguoi_goi:
        return False
    ct = await chi_tiet_viec(conn, cai_hen.clinic_id, viec["visit_id"])
    await ghi_chuong_vai(
        conn,
        clinic_id=cai_hen.clinic_id,
        vai=ClinicRole.CSKH.value,
        tieu_de=(
            f"Hẹn tái khám {viec['ngay_hen']:%d/%m} — cần gọi chốt giờ: "
            f"{viec['full_name']} ({viec['patient_code']})"
        )[:200],
        noi_dung=noi_dung_chuong(ct),
        nguon=NGUON_CHUONG,
        nguon_id=f"{viec['id']}:{viec['ngay_hen'].isoformat()}",
        duong_dan=f"/customers?selected={viec['pid']}",
        nguoi_goi=str(nguoi_goi),
    )
    return True


dang_ky_loai(HEN_NHAC_TAI_KHAM, bao_den_han)

__all__ = ["bao_den_han", "noi_dung_chuong"]
