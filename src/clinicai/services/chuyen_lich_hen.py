"""CHUYỂN lịch hẹn TƯƠNG LAI của sổ hẹn cũ (``lich_su_notion.lich_hen``) thành
lịch hẹn THẬT — chạy MỘT lần vào ngày cắt Notion (soạn 06/10/2026).

Phòng khám nhập Notion song song tới ngày cắt, nên lúc ấy sổ cũ còn ~1.000 lịch
hẹn từ hôm nay trở đi mà hệ thống chưa có. Bộ này đưa chúng vào hệ thống theo
ĐÚNG luật của màn Đặt lịch (gọi chính các hàm kiểm của ``BookingService``):

* Lịch CÓ GIỜ → ``appointment`` CONFIRMED (trạng thái hiện hành của lịch đã đặt;
  SCHEDULED / CSKH_CONFIRMED là trạng thái cũ), cơ sở Kim Ngưu, kênh NULL (=
  "nhân viên nhập", ghế đặt hẹn — giống màn Đặt lịch khi không chọn kênh), bác
  sĩ và loại khám ghép theo đúng bảng ghép của bộ nạp. Sổ cũ không ghi bác sĩ →
  lịch vào hàng "Chưa phân bác sĩ" (trạng thái có sẵn của hệ thống).
* Lịch CHỈ CÓ NGÀY (Notion không ghi giờ — phần lớn sổ hẹn tái khám "chờ xác
  nhận"): mặc định ra DANH SÁCH TAY. ``--khong-gio viec-goi`` thì thành MỘT việc
  gọi CSKH "mời tái khám" (``nhac_tai_kham`` lượt 1, nguồn CSKH_NHAP — đúng đường
  CSKH gõ tay ngày tái khám) để CSKH gọi chốt giờ rồi đặt lịch thật.
* Khách đã có lịch còn sống CÙNG NGÀY trên hệ thống → BỎ QUA (ghi vào báo cáo).
* SỨC CHỨA: KHÔNG tắt trigger. Tuần đã công bố lịch trực mà đầy khung →
  ``enforce_slot_capacity`` từ chối → danh sách tay. Tuần CHƯA công bố: hệ thống
  vốn NHẬN rồi đối soát lúc công bố (việc CSKH "Vượt sức chứa"); bộ này tính
  trước trần ấy — mặc định vẫn ghi như màn Đặt lịch nhưng gắn cảnh báo vào danh
  sách (``--vuot-tran bao`` thì không ghi, đưa ra danh sách tay).
* Mọi lịch không chuyển được (không giờ, không ghép được bác sĩ/loại khám, loại
  khám đã tắt, ngoài giờ ca, bác sĩ không trực, đầy khung…) → CSV cho lễ tân,
  KHÔNG bỏ sót dòng nào.

MỘT giao dịch, mặc định THỬ KHÔ (``--that`` mới ghi). Mỗi lịch ghi trong một
savepoint: lịch bị trigger từ chối không làm hỏng cả lượt. Chạy lại an toàn: lịch
đã có trong sổ ghép ``lich_su_notion.lich_hen_that`` thì bỏ qua; lịch từng vào
danh sách tay thì được thử lại (ví dụ sau khi quản lý mở thêm chỗ).
Gỡ: ``scripts/hoan-tac-lich-hen-that.sql``.

    python -m clinicai.services.chuyen_lich_hen [--that] [--csv tep.csv]
        [--khong-gio tay|viec-goi] [--vuot-tran ghi|bao] [--tu-ngay YYYY-MM-DD]
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import time as _time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.booking_service import BookingService
from clinicai.services.chuyen_luot_that import TEN_NGUOI_NHAP
from clinicai.services.clinic_policy import load_effective_policy

#: Bảng ghép tên bác sĩ / loại khám trên sổ cũ → hệ thống. CHÉP NGUYÊN từ bộ dựng
#: gói (``notion-import-20261005/claude/nhap_thu.sql``: ghep_bac_si, ghep_loai_kham)
#: để lịch hẹn ghép đúng như lượt khám đã nạp. Thêm vào đó, mọi cặp (tên cũ → id)
#: đã có trong ``lich_su_notion.luot_kham`` cũng được dùng.
GHEP_BAC_SI: dict[str, str] = {
    "BS Thành": "BS Thành",
    "BS Hằng": "BS Hằng",
    "BS Nam": "BS Nam",
    "BS Hùng": "BS Hùng",
    "BS Thiệp": "BS Thiệp",
    "BS Quyết": "BS Quyết",
    "BS Linh nam khoa": "BS Linh Nam khoa",
    "BS Q.Dũng": "BS Hoàng Quốc Dũng",
    "BS Đào": "BS Đào",
    "BS Thanh": "BS Xuân Thanh",
    "BS Thùy Linh": "BS Nguyễn Thuỳ Linh",
}
GHEP_LOAI_KHAM: dict[str, str] = {
    "Nội tiết - Tình dục": "NOI_TIET_TINH_DUC",
    "Sản 1": "SAN_1",
    "Sản 2": "SAN_2",
    "Sản 3": "SAN_3",
    "Phụ khoa": "PHU_KHOA",
    "Hiếm muộn": "HIEM_MUON",
    "Nam khoa": "NAM_KHOA",
    "NPĐH": "NPDH",
    "Hồ sơ sinh": "HO_SO_SINH",
    "Khám tiền sản": "KHAM_TIEN_SAN",
    "Tư vấn chuyên sâu": "TU_VAN_CHUYEN_SAU",
    "Khám sàn chậu": "SAN_CHAU",
    "Tiền hôn nhân": "TIEN_HON_NHAN",
    "***#Thủ thuật": "THU_THUAT",
    "FREE": "FREE",
}

#: Trạng thái sổ cũ còn hiệu lực (bộ nạp quy từ "Tình trạng khách đến" + "Tình
#: trạng CSKH": huỷ → CANCELLED, đã đến → COMPLETED, không đến → NO_SHOW).
TRANG_THAI_CON_HIEU_LUC = ("SCHEDULED", "CSKH_CONFIRMED")
#: Lịch hẹn mới vào thẳng CONFIRMED (``booking_service.initial_status``).
TRANG_THAI_LICH_MOI = "CONFIRMED"
#: Độ dài khung một lịch (bộ đếm sức chứa chỉ đo theo giờ bắt đầu).
PHUT_MOT_LICH = 15
#: Trạng thái lịch "còn sống" — cùng tập với chỉ mục uq_appointment_patient_slot_live.
LICH_SONG = ("SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN", "COMPLETED")
#: Cửa sổ gọi mời tái khám (cùng mốc T−7 của ``recall_job_service.tao_thu_cong``).
SO_NGAY_GOI_TRUOC = 7

#: Lý do → câu cho lễ tân, và có phải XỬ LÝ TAY không (False = chỉ để biết).
LY_DO: dict[str, tuple[str, bool]] = {
    "khong_gio": ("Sổ cũ chỉ ghi ngày, không có giờ hẹn — gọi khách chốt giờ rồi đặt lịch", True),
    "khong_gio_hom_nay": ("Hẹn hôm nay nhưng không có giờ — kiểm khách đã đến chưa", True),
    "khong_ghep_loai_kham": ("Loại khám trên sổ cũ không có trên hệ thống — chọn loại khám rồi đặt tay", True),
    "loai_kham_da_tat": ("Loại khám đã tắt trên hệ thống — chọn loại khám đang dùng rồi đặt tay", True),
    "khong_ghep_bac_si": ("Không ghép được bác sĩ trên sổ cũ — chọn bác sĩ rồi đặt tay", True),
    "bac_si_ngung": ("Bác sĩ trên sổ cũ đã ngừng hoạt động — chọn bác sĩ khác", True),
    "khach_an": ("Hồ sơ khách đang ẩn — mở lại hồ sơ rồi đặt tay", True),
    "ngoai_gio_ca": ("Giờ hẹn không thuộc ca làm việc nào", True),
    "bac_si_khong_truc": ("Bác sĩ không có ca trực giờ đó (tuần đã công bố lịch trực)", True),
    "bac_si_kin_gio": ("Bác sĩ đã kín lịch khung giờ đó", True),
    "luat_bac_si": ("Vướng luật bắt buộc bác sĩ cho khách mới", True),
    "day_ca": ("Khung giờ đã đầy (tuần đã công bố) — dời giờ, hoặc quản lý mở thêm chỗ rồi chạy lại", True),
    "vuot_tran_chua_cong_bo": ("Vượt trần khung giờ (tuần chưa công bố lịch trực) — chưa ghi", True),
    "loi_ghi": ("Hệ thống từ chối khi ghi — xem chi tiết", True),
    "da_co_lich_cung_ngay": ("Khách đã có lịch trên hệ thống cùng ngày — bỏ qua", False),
    "da_co_viec_goi": ("Khách đã có việc gọi mời tái khám cùng ngày hẹn — bỏ qua", False),
    "gio_da_qua": ("Giờ hẹn đã qua lúc chuyển — bỏ qua", False),
    "ghi_vuot_tran_chua_cong_bo": (
        "ĐÃ GHI nhưng vượt trần khung giờ (tuần chưa công bố) — lúc công bố sẽ thành việc CSKH 'Vượt sức chứa'",
        False,
    ),
}

COT_CSV = [
    "ly_do",
    "ly_do_chu",
    "can_xu_ly_tay",
    "chi_tiet",
    "ma_lich_cu",
    "ngay_hen",
    "gio_hen",
    "khach",
    "ma_ho_so",
    "sdt",
    "bac_si_cu",
    "loai_kham_cu",
    "tinh_trang_cskh_cu",
    "link_so_cu",
]


class _ThuKho(Exception):  # noqa: N818 — tín hiệu quay lui, không phải lỗi
    pass


@dataclass
class _KetQua:
    so: Counter[str] = field(default_factory=Counter)
    dong: list[dict[str, Any]] = field(default_factory=list)

    def ghi(self, ly_do: str, h: asyncpg.Record, chi_tiet: str = "") -> None:
        cau, tay = LY_DO[ly_do]
        self.so[ly_do] += 1
        self.dong.append(
            {
                "ly_do": ly_do,
                "ly_do_chu": cau,
                "can_xu_ly_tay": "có" if tay else "không",
                "chi_tiet": chi_tiet,
                "ma_lich_cu": h["ma"],
                "ngay_hen": h["ngay_hen"].isoformat(),
                "gio_hen": h["gio_hen"].strftime("%H:%M") if h["gio_hen"] else "",
                "khach": h["full_name"],
                "ma_ho_so": h["patient_code"],
                "sdt": h["phone_primary"] or "",
                "bac_si_cu": h["bac_si_goc"] or "",
                "loai_kham_cu": h["loai_kham_goc"] or "",
                "tinh_trang_cskh_cu": " · ".join(
                    (h["tinh_trang_cskh"] or "").split("\n")
                ).strip(),
                "link_so_cu": h["notion_url"] or "",
            }
        )


def _khong_gio(gio: time | None) -> bool:
    # Notion ghi "chỉ ngày" thành 00:00 ở một số dòng — phòng khám không mở nửa đêm.
    return gio is None or gio == time(0, 0)


async def _bang_ghep(
    conn: asyncpg.Connection, clinic: Any
) -> tuple[dict[str, asyncpg.Record], dict[str, asyncpg.Record]]:
    """Tên cũ → (id, is_active) cho bác sĩ và loại khám."""
    bac_si: dict[str, asyncpg.Record] = {}
    for r in await conn.fetch(
        """
        WITH cap AS (
            SELECT bac_si_goc AS ten, staff_id, count(*) AS so
              FROM lich_su_notion.luot_kham
             WHERE clinic_id = $1 AND bac_si_goc IS NOT NULL AND staff_id IS NOT NULL
             GROUP BY 1, 2
            UNION ALL
            SELECT g.ten, s.id, 1000000
              FROM unnest($2::text[], $3::text[]) AS g(ten, staff_ten)
              JOIN staff s ON s.full_name = g.staff_ten
             WHERE EXISTS (SELECT 1 FROM clinic_membership m
                            WHERE m.staff_id = s.id AND m.clinic_id = $1
                              AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR'))
        )
        SELECT DISTINCT ON (c.ten) c.ten, c.staff_id AS id,
               s.is_active AND EXISTS (
                   SELECT 1 FROM clinic_membership m
                    WHERE m.staff_id = s.id AND m.clinic_id = $1 AND m.is_active
                      AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')) AS dung_duoc
          FROM cap c JOIN staff s ON s.id = c.staff_id
         ORDER BY c.ten, c.so DESC
        """,
        clinic,
        list(GHEP_BAC_SI),
        list(GHEP_BAC_SI.values()),
    ):
        bac_si[r["ten"]] = r
    loai: dict[str, asyncpg.Record] = {}
    for r in await conn.fetch(
        """
        WITH cap AS (
            SELECT loai_kham_goc AS ten, service_type_id AS id, count(*) AS so
              FROM lich_su_notion.luot_kham
             WHERE clinic_id = $1 AND loai_kham_goc IS NOT NULL
               AND service_type_id IS NOT NULL
             GROUP BY 1, 2
            UNION ALL
            SELECT g.ten, st.id, 1000000
              FROM unnest($2::text[], $3::text[]) AS g(ten, ma)
              JOIN service_type st ON st.clinic_id = $1 AND st.code = g.ma
        )
        SELECT DISTINCT ON (c.ten) c.ten, c.id, st.is_active AS dung_duoc
          FROM cap c JOIN service_type st ON st.id = c.id
         ORDER BY c.ten, c.so DESC
        """,
        clinic,
        list(GHEP_LOAI_KHAM),
        list(GHEP_LOAI_KHAM.values()),
    ):
        loai[r["ten"]] = r
    return bac_si, loai


async def _co_lich_cung_ngay(
    conn: asyncpg.Connection, clinic: Any, khach: Any, ngay: date
) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM appointment
                 WHERE clinic_id = $1 AND clinic_patient_id = $2
                   AND status = ANY ($4::text[])
                   AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $3)
            """,
            clinic,
            khach,
            ngay,
            list(LICH_SONG),
        )
    )


async def _vuot_tran_chua_cong_bo(
    conn: asyncpg.Connection, clinic: Any, bac_si: Any, luc: datetime
) -> bool:
    """Tuần CHƯA công bố: trigger nhận mọi lịch hẹn. Tính trước, bằng CHÍNH hai
    hàm trigger dùng, xem lịch này có vượt trần khi tuần được công bố không."""
    if bac_si is None:
        return False
    return bool(
        await conn.fetchval(
            """
            WITH p AS (SELECT * FROM resolve_effective_cap($1, $2, $3)),
                 k AS (SELECT to_timestamp(floor(extract(epoch FROM $3::timestamptz)
                                   / (p.slot_minutes * 60)) * p.slot_minutes * 60) AS bd,
                              p.slot_minutes, p.regular_cap FROM p)
            SELECT NOT tuan_lich_truc_da_cong_bo($1, $3)
                   AND slot_seats_used($1, $2, k.bd,
                                       k.bd + make_interval(mins => k.slot_minutes),
                                       false, NULL) >= k.regular_cap
              FROM k
            """,
            clinic,
            bac_si,
            luc,
        )
    )


async def _chuyen(
    conn: asyncpg.Connection,
    *,
    khong_gio: str,
    vuot_tran: str,
    tu_ngay: date,
    bay_gio: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    clinic = await conn.fetchval(
        "SELECT clinic_id FROM lich_su_notion.lan_nhap WHERE hoan_tac_luc IS NULL "
        "ORDER BY id DESC LIMIT 1"
    )
    if clinic is None:
        raise SystemExit("Chưa có lần nạp lịch sử nào.")
    # Chỉ có cơ sở Kim Ngưu (Tuyền 05/10); gọi tên cho chắc nếu sau này thêm cơ sở.
    co_so = await conn.fetchval(
        "SELECT id FROM clinic_location WHERE clinic_id = $1 AND is_active"
        " ORDER BY (public.f_unaccent(lower(name)) LIKE '%kim nguu%') DESC, created_at"
        " LIMIT 1",
        clinic,
    )
    may = await conn.fetchval(
        "SELECT id FROM staff WHERE employment_type = 'SYSTEM' AND full_name = $1 LIMIT 1",
        TEN_NGUOI_NHAP,
    )
    lan = await conn.fetchval(
        "INSERT INTO lich_su_notion.lan_chuyen_lich (clinic_id, che_do) VALUES ($1, $2)"
        " RETURNING id",
        clinic,
        json.dumps({"khong_gio": khong_gio, "vuot_tran": vuot_tran, "tu_ngay": str(tu_ngay)}),
    )
    # Danh tính dựng để gọi các hàm kiểm của màn Đặt lịch — chúng chỉ đọc clinic_id.
    ai = StaffIdentity(
        staff_id=str(may or ""),
        auth_user_id="",
        full_name=TEN_NGUOI_NHAP,
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=str(clinic),
        location_id=str(co_so),
        location_name="",
    )
    # Chỉ dùng các hàm kiểm nhận `conn` (cùng giao dịch) — không đụng pool.
    dat = BookingService(conn)  # type: ignore[arg-type]
    bac_si_ghep, loai_ghep = await _bang_ghep(conn, clinic)

    hen = await conn.fetch(
        """
        SELECT h.notion_id, h.clinic_patient_id, h.ma, h.ngay_hen, h.gio_hen,
               h.loai_kham_goc, h.bac_si_goc, h.trang_thai, h.tinh_trang_cskh,
               h.notion_url, p.full_name, p.patient_code, p.phone_primary,
               p.is_active AS khach_dung_duoc
          FROM lich_su_notion.lich_hen h
          JOIN patient p ON p.clinic_patient_id = h.clinic_patient_id
         WHERE h.clinic_id = $1 AND h.ngay_hen >= $2
           AND h.trang_thai = ANY ($3::text[])
           AND NOT EXISTS (SELECT 1 FROM lich_su_notion.lich_hen_that t
                            WHERE t.notion_id = h.notion_id)
         -- Đặt trước thì giữ ghế trước: mã BOOK-n tăng theo lúc tạo trên sổ cũ.
         ORDER BY h.ngay_hen, h.gio_hen NULLS LAST,
                  nullif(regexp_replace(coalesce(h.ma, ''), '\\D', '', 'g'), '')::bigint
                      NULLS LAST, h.notion_id
        """,
        clinic,
        tu_ngay,
        list(TRANG_THAI_CON_HIEU_LUC),
    )

    kq = _KetQua()
    so_lich = so_viec = so_chua_phan_bs = 0
    for h in hen:
        if not h["khach_dung_duoc"]:
            kq.ghi("khach_an", h)
            continue
        if await _co_lich_cung_ngay(conn, clinic, h["clinic_patient_id"], h["ngay_hen"]):
            kq.ghi("da_co_lich_cung_ngay", h)
            continue

        # ── Lịch CHỈ CÓ NGÀY ──────────────────────────────────────────────
        if _khong_gio(h["gio_hen"]):
            if h["ngay_hen"] <= bay_gio.astimezone(CLINIC_TZ).date():
                kq.ghi("khong_gio_hom_nay", h)
                continue
            if khong_gio != "viec-goi":
                kq.ghi("khong_gio", h)
                continue
            ly_do = " · ".join(
                x
                for x in (
                    "Lịch hẹn cũ chưa chốt giờ — gọi khách chốt giờ rồi đặt lịch",
                    h["bac_si_goc"],
                    h["loai_kham_goc"],
                    h["ma"],
                )
                if x
            )
            hom_nay = bay_gio.astimezone(CLINIC_TZ).date()
            viec = await conn.fetchval(
                """
                INSERT INTO nhac_tai_kham (clinic_id, clinic_patient_id, luot_goi, ngay_hen,
                                           han_goi, nguon, tao_boi_staff_id, ly_do)
                VALUES ($1, $2, 1, $3::date, greatest($3::date - $4::int, $5::date), 'CSKH_NHAP', $6, $7)
                ON CONFLICT (clinic_id, clinic_patient_id, ngay_hen, luot_goi) DO NOTHING
                RETURNING id
                """,
                clinic,
                h["clinic_patient_id"],
                h["ngay_hen"],
                SO_NGAY_GOI_TRUOC,
                hom_nay,
                may,
                ly_do,
            )
            if viec is None:
                # Sổ cũ có 2 lịch cùng ngày cho một khách (vd. khám + tập sàn
                # chậu): gộp vào ĐÚNG việc gọi vừa tạo ở lần chuyển này, ghi thêm
                # dòng thứ hai. Việc gọi có từ trước (CSKH/phiếu khám) thì để nguyên.
                viec = await conn.fetchval(
                    """
                    UPDATE nhac_tai_kham n
                       SET ly_do = n.ly_do || E'\\n+ ' || $4, updated_at = now()
                     WHERE n.clinic_id = $1 AND n.clinic_patient_id = $2
                       AND n.ngay_hen = $3 AND n.luot_goi = 1 AND n.trang_thai = 'CHO_GOI'
                       AND EXISTS (SELECT 1 FROM lich_su_notion.lich_hen_that t
                                    WHERE t.nhac_tai_kham_id = n.id)
                    RETURNING n.id
                    """,
                    clinic,
                    h["clinic_patient_id"],
                    h["ngay_hen"],
                    " · ".join(x for x in (h["bac_si_goc"], h["loai_kham_goc"], h["ma"]) if x),
                )
            if viec is None:
                kq.ghi("da_co_viec_goi", h)
                continue
            await conn.execute(
                "INSERT INTO lich_su_notion.lich_hen_that (notion_id, clinic_id,"
                " lan_chuyen_lich_id, thanh, nhac_tai_kham_id) VALUES ($1, $2, $3,"
                " 'viec_goi', $4)",
                h["notion_id"],
                clinic,
                lan,
                viec,
            )
            so_viec += 1
            continue

        # ── Lịch CÓ GIỜ ───────────────────────────────────────────────────
        luc = datetime.combine(h["ngay_hen"], h["gio_hen"], tzinfo=CLINIC_TZ)
        het = luc + timedelta(minutes=PHUT_MOT_LICH)
        if het <= bay_gio:
            kq.ghi("gio_da_qua", h)
            continue
        loai = loai_ghep.get(h["loai_kham_goc"] or "")
        if loai is None:
            kq.ghi("khong_ghep_loai_kham", h)
            continue
        if not loai["dung_duoc"]:
            kq.ghi("loai_kham_da_tat", h)
            continue
        bac_si: Any = None
        if h["bac_si_goc"]:
            bs = bac_si_ghep.get(h["bac_si_goc"])
            if bs is None:
                kq.ghi("khong_ghep_bac_si", h)
                continue
            if not bs["dung_duoc"]:
                kq.ghi("bac_si_ngung", h)
                continue
            bac_si = bs["id"]
        bs_str = str(bac_si) if bac_si else None

        # Đúng các chốt của BookingService.create, cùng thứ tự.
        try:
            await dat._validate_booking_refs(
                conn,
                clinic_patient_id=str(h["clinic_patient_id"]),
                location_id=str(co_so),
                service_type_id=str(loai["id"]),
                doctor_id=bs_str,
                identity=ai,
            )
            await dat._chan_dat_ngoai_khung_ca(conn, slot_start=luc, identity=ai)
        except ValidationError as e:
            kq.ghi("ngoai_gio_ca" if "ca nào" in str(e) else "loi_ghi", h, str(e))
            continue
        if bs_str:
            cau = await dat._doctor_conflict(conn, bs_str, luc, het, ai)
            if cau:
                kq.ghi("bac_si_kin_gio", h, cau)
                continue
            cau = await dat._roster_warning(conn, bs_str, luc, ai)
            if cau and await dat._roster_is_required(conn, ai):
                kq.ghi("bac_si_khong_truc", h, cau)
                continue
        luat = await dat._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id=str(h["clinic_patient_id"]),
            service_type_id=str(loai["id"]),
            doctor_id=bs_str,
            identity=ai,
        )
        if luat and luat[1]:
            kq.ghi("luat_bac_si", h, luat[0])
            continue
        policy = await load_effective_policy(conn, str(clinic), bs_str, luc)
        cau = await dat._slot_full(conn, bs_str, luc, None, ai, policy)
        if cau:
            kq.ghi("day_ca", h, cau)
            continue
        vuot = await _vuot_tran_chua_cong_bo(conn, clinic, bac_si, luc)
        if vuot and vuot_tran == "bao":
            kq.ghi("vuot_tran_chua_cong_bo", h)
            continue

        # Ghi trong savepoint: trigger từ chối thì chỉ lịch này quay lui.
        try:
            async with conn.transaction():
                lich = await conn.fetchval(
                    """
                    INSERT INTO appointment (clinic_id, clinic_patient_id, doctor_id,
                        service_type_id, location_id, slot_start, slot_end, booking_channel,
                        status, is_walkin, notes)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, $8, false, $9)
                    RETURNING id
                    """,
                    clinic,
                    h["clinic_patient_id"],
                    bac_si,
                    loai["id"],
                    co_so,
                    luc,
                    het,
                    TRANG_THAI_LICH_MOI,
                    f"Chuyển từ sổ hẹn cũ · {h['ma']}" if h["ma"] else "Chuyển từ sổ hẹn cũ",
                )
                await conn.execute(
                    "INSERT INTO lich_su_notion.lich_hen_that (notion_id, clinic_id,"
                    " lan_chuyen_lich_id, thanh, appointment_id, trang_thai_luc_chuyen,"
                    " slot_start, doctor_id) VALUES ($1, $2, $3, 'lich_hen', $4, $5, $6, $7)",
                    h["notion_id"],
                    clinic,
                    lan,
                    lich,
                    TRANG_THAI_LICH_MOI,
                    luc,
                    bac_si,
                )
        except asyncpg.CheckViolationError as e:
            kq.ghi("day_ca" if "Khung giờ đã đầy" in str(e) else "loi_ghi", h, str(e))
            continue
        except asyncpg.PostgresError as e:
            kq.ghi("loi_ghi", h, f"{type(e).__name__}: {e}")
            continue
        so_lich += 1
        if bac_si is None:
            so_chua_phan_bs += 1
        if vuot:
            kq.ghi("ghi_vuot_tran_chua_cong_bo", h)

    so: dict[str, Any] = {
        "lan_chuyen_lich_id": lan,
        "clinic_id": str(clinic),
        "tu_ngay": tu_ngay.isoformat(),
        "che_do": {"khong_gio": khong_gio, "vuot_tran": vuot_tran},
        "lich_con_hieu_luc_chua_chuyen": len(hen),
        "thanh_lich_hen": so_lich,
        "trong_do_chua_phan_bac_si": so_chua_phan_bs,
        "thanh_viec_goi_cskh": so_viec,
        "so_viec_goi_moi": await conn.fetchval(
            "SELECT count(DISTINCT nhac_tai_kham_id) FROM lich_su_notion.lich_hen_that"
            " WHERE lan_chuyen_lich_id = $1",
            lan,
        ),
        "can_xu_ly_tay": sum(n for k, n in kq.so.items() if LY_DO[k][1]),
        "theo_ly_do": dict(sorted(kq.so.items())),
    }
    await conn.execute(
        "UPDATE lich_su_notion.lan_chuyen_lich SET so_lieu = $2 WHERE id = $1",
        lan,
        json.dumps(so, default=str),
    )
    return so, kq.dong


async def chuyen(
    pool: asyncpg.Pool,
    *,
    that: bool,
    khong_gio: str = "tay",
    vuot_tran: str = "ghi",
    tu_ngay: date | None = None,
    bay_gio: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``that=False`` = thử khô: chạy hết trong giao dịch rồi quay lui. Trả (số
    liệu, các dòng cho danh sách lễ tân)."""
    if khong_gio not in ("tay", "viec-goi"):
        raise ValueError("khong_gio phải là 'tay' hoặc 'viec-goi'")
    if vuot_tran not in ("ghi", "bao"):
        raise ValueError("vuot_tran phải là 'ghi' hoặc 'bao'")
    bay_gio = bay_gio or datetime.now(CLINIC_TZ)
    tu_ngay = tu_ngay or bay_gio.astimezone(CLINIC_TZ).date()
    so: dict[str, Any] = {}
    dong: list[dict[str, Any]] = []
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                so, dong = await _chuyen(
                    conn, khong_gio=khong_gio, vuot_tran=vuot_tran, tu_ngay=tu_ngay,
                    bay_gio=bay_gio,
                )
                if not that:
                    raise _ThuKho
        except _ThuKho:
            so["thu_kho"] = True
    return so, dong


def ghi_csv(duong: Path, dong: list[dict[str, Any]]) -> None:
    """utf-8-sig để Excel mở đúng dấu tiếng Việt."""
    with duong.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COT_CSV)
        w.writeheader()
        # Việc cần xử lý tay lên trước, theo ngày hẹn.
        for d in sorted(dong, key=lambda d: (d["can_xu_ly_tay"] != "có", d["ngay_hen"], d["gio_hen"])):
            w.writerow(d)


def _tham_so(argv: list[str], ten: str, mac_dinh: str | None) -> str | None:
    return argv[argv.index(ten) + 1] if ten in argv else mac_dinh


async def _main(argv: list[str]) -> None:
    that = "--that" in argv
    khong_gio = _tham_so(argv, "--khong-gio", "tay") or "tay"
    vuot_tran = _tham_so(argv, "--vuot-tran", "ghi") or "ghi"
    tu = _tham_so(argv, "--tu-ngay", None)
    csv_ra = Path(_tham_so(argv, "--csv", None) or "lich-hen-can-xu-ly-tay.csv")
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=1)
    bd = _time.monotonic()
    try:
        so, dong = await chuyen(
            pool,
            that=that,
            khong_gio=khong_gio,
            vuot_tran=vuot_tran,
            tu_ngay=date.fromisoformat(tu) if tu else None,
        )
    finally:
        await pool.close()
    so["giay"] = round(_time.monotonic() - bd, 1)
    ghi_csv(csv_ra, dong)
    so["danh_sach"] = str(csv_ra)
    print(json.dumps(so, ensure_ascii=False, indent=1, default=str))
    print("THỬ KHÔ — chưa ghi gì. Thêm --that để ghi thật." if not that else "ĐÃ GHI.")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
