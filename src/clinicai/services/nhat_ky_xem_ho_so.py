"""NHẬT KÝ XEM HỒ SƠ — ai đã mở hồ sơ của khách nào, lúc nào, qua cửa nào.

Một câu hỏi, một chỗ trả lời (24/11/2026). Trước đó `permissions/y_khoa.ghi_mo_ho_so`
ghi `clinical_record.opened` vào `event_log` ở 6 cửa và BỎ QUA vai lâm sàng (lý
do 24/09: sợ nhiễu). Dữ liệu sức khoẻ là dữ liệu nhạy cảm (NĐ 356/2025 Điều 4
k.2) — câu hỏi luật đặt ra là "ai đã truy cập", kể cả bác sĩ. Nay mọi lượt mở
ghi vào bảng riêng `nhat_ky_xem_ho_so` (migration 20261124010000), gộp theo khung
5 phút để chống nhiễu thay cho việc bỏ qua người.

Ba luật của file:
  1. CHỈ ĐỊNH DANH. id khách, id bản ghi, loại, mẫu đường dẫn cửa. Không tên,
     không SĐT, không nội dung — màn đọc nhật ký không được thành đường đọc hồ
     sơ thứ hai. Màn hiện MÃ khách (patient_code), không họ tên.
  2. GHI KHÔNG CHẶN NGƯỜI ĐỌC. Lỗi ghi → kho lỗi (`loi_nhom`, /ops "Lỗi & cảnh
     báo") để có người thấy, không ném ra cửa đọc. Bác sĩ đang khám mà mở bệnh
     án ra 500 vì nhật ký hỏng là tệ hơn mất một dòng nhật ký.
  3. clinic_id LẤY TỪ identity, không bao giờ từ tham số người gọi (backend bỏ
     qua RLS — xem `audit_log_service.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.core.clock import doc_ngay_xem
from clinicai.services.nhan_vai import nhan_vai

#: Loại hồ sơ — khớp CHECK `nhat_ky_xem_ho_so_loai_ck`. Đổi ở đây thì phải có
#: migration đổi CHECK (test `test_loai_khop_check` canh).
LOAI: dict[str, str] = {
    "ho_so_khach": "Hồ sơ khách (hành chính, tiền sử)",
    "lich_su_kham": "Lịch sử khám",
    "phieu_kham": "Bệnh án / phiếu khám",
    "ket_qua": "Kết quả dịch vụ / xét nghiệm",
    "tep_ket_qua": "Tệp kết quả (ảnh, video, PDF)",
    "don_thuoc": "Đơn thuốc",
    "ban_in": "Bản in",
}

KHUNG_GOP = timedelta(minutes=5)
_VN = ZoneInfo("Asia/Ho_Chi_Minh")
_MOC = datetime(2000, 1, 1, tzinfo=UTC)

#: Bộ nhớ gộp trong tiến trình: khoá → khung đã ghi. Màn tự tải lại theo tin
#: thời gian thực gọi cùng cửa nhiều lần một phút; khung đã ghi thì khỏi chạm DB.
#: Chỉ là lối tắt — chỉ mục duy nhất trong DB mới là chỗ gộp thật (nhiều tiến
#: trình API, khởi động lại…).
_DA_GHI: dict[tuple[str, ...], datetime] = {}
_TRAN_BO_NHO = 5000


def khung_cua(luc: datetime) -> datetime:
    """Khung 5 phút chứa `luc` — cùng công thức `date_bin` của cột `khung`."""
    so_khung = (luc - _MOC) // KHUNG_GOP
    return _MOC + so_khung * KHUNG_GOP


#: Tên khoá tra khách (cũng là tên tham số ở cửa: `xem(..., visit_id=…)`) → SQL.
#: Thêm một cách tra = thêm một dòng ở đây. Thứ tự = ưu tiên khi có nhiều khoá.
_SQL_TRA_KHACH: dict[str, str] = {
    "visit_id": "SELECT clinic_patient_id::text FROM visit"
    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
    "appointment_id": "SELECT clinic_patient_id::text FROM appointment"
    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
    "service_order_id": "SELECT v.clinic_patient_id::text FROM service_order so"
    " JOIN visit v ON v.visit_id = so.visit_id AND v.clinic_id = so.clinic_id"
    " WHERE so.clinic_id = $1::uuid AND so.id = $2::uuid",
    "tep_id": "SELECT clinic_patient_id::text FROM tep_ket_qua"
    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
    # Lượt khám / xét nghiệm CŨ nhập từ Notion (schema lich_su_notion).
    "luot_cu_id": "SELECT clinic_patient_id::text FROM lich_su_notion.luot_kham"
    " WHERE clinic_id = $1::uuid AND notion_id = $2::uuid",
    "xn_cu_id": "SELECT clinic_patient_id::text FROM lich_su_notion.xet_nghiem"
    " WHERE clinic_id = $1::uuid AND notion_id = $2::uuid",
    # Khoá ảnh siêu âm (chuỗi `<clinic_id>/…`) nằm trong `image_refs` của bản ghi.
    "anh_sieu_am": "SELECT clinic_patient_id::text FROM ultrasound_record"
    " WHERE clinic_id = $1::uuid AND $2 = ANY(image_refs) LIMIT 1",
}

_SQL_GHI = """
    INSERT INTO nhat_ky_xem_ho_so
        (clinic_id, staff_id, vai, clinic_patient_id, loai, doi_tuong_id,
         cua, xem_luc, khung)
    VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, $6, $7,
            COALESCE($8::timestamptz, now()), $9::timestamptz)
    ON CONFLICT DO NOTHING
"""


async def tra_khach(
    conn: asyncpg.Connection, clinic_id: str, tra: Mapping[str, str | None]
) -> str | None:
    """Khách của một bản ghi, trong ĐÚNG phòng khám. Không thấy / id rác → None."""
    for ten, sql in _SQL_TRA_KHACH.items():
        khoa = tra.get(ten)
        if khoa:
            try:
                kq = await conn.fetchval(sql, clinic_id, khoa)
            except (asyncpg.DataError, ValueError):  # id rác (không phải uuid)
                return None
            return str(kq) if kq else None
    return None


async def ghi_luot_xem(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    staff_id: str,
    vai: str,
    loai: str,
    cua: str,
    khach: str | None = None,
    tra: Mapping[str, str | None] | None = None,
    doi_tuong_id: str | None = None,
    luc: datetime | None = None,
) -> bool:
    """Ghi một lượt xem. True = có dòng mới; False = đã gộp / không rõ khách.

    `khach` biết sẵn thì truyền (khỏi một truy vấn); không thì `tra` = {tên khoá
    trong `_SQL_TRA_KHACH`: id}. Ném khi DB hỏng / khoá lạ — người gọi
    (`api/xem_ho_so.ghi_an_toan`) nuốt và đưa vào kho lỗi. `luc` chỉ để test.
    """
    tra = tra or {}
    if loai not in LOAI or not set(tra) <= set(_SQL_TRA_KHACH):
        raise ValueError(f"loai / khoá tra không hợp lệ: {loai} {sorted(tra)}")
    if doi_tuong_id is None:
        doi_tuong_id = next((v for v in tra.values() if v), None)
    khung = khung_cua(luc or datetime.now(UTC))
    # Đã thấy cùng (người, cửa, bản ghi) trong khung này → khỏi tra lẫn ghi.
    khoa_nho = (clinic_id, staff_id, loai, cua, khach or "", doi_tuong_id or "")
    if _DA_GHI.get(khoa_nho) == khung:
        return False
    async with pool.acquire() as conn:
        if khach is None:
            khach = await tra_khach(conn, clinic_id, tra)
        if not khach:
            return False
        try:
            UUID(khach)
        except ValueError:  # mã khách rác (tham số truy vấn) → không ghi
            return False
        trang_thai = await conn.execute(
            _SQL_GHI, clinic_id, staff_id, vai, khach, loai, doi_tuong_id,
            cua[:200], luc, khung,
        )  # fmt: skip
    # Chạm trần thì xoá cả bộ nhớ: chỉ tốn thêm một vòng INSERT bị ON CONFLICT
    # chặn, không sai dữ liệu — đơn giản hơn LRU.
    if len(_DA_GHI) >= _TRAN_BO_NHO:
        _DA_GHI.clear()
    _DA_GHI[khoa_nho] = khung
    return bool(trang_thai == "INSERT 0 1")


def _bien_ngay(tu: str | None, den: str | None) -> tuple[datetime, datetime]:
    """Khoảng nửa mở theo ngày Việt Nam. Ngày rác → hôm nay (không ném)."""
    hom_nay = datetime.now(_VN).date()
    d_tu = doc_ngay_xem(tu) or hom_nay
    d_den = doc_ngay_xem(den) or d_tu
    if d_den < d_tu:
        d_tu, d_den = d_den, d_tu
    # Trần 93 ngày một lần xem — đủ cho một quý, không quét cả bảng.
    d_den = min(d_den, d_tu + timedelta(days=92))
    bat_dau = datetime.combine(d_tu, time.min, tzinfo=_VN)
    ket_thuc = datetime.combine(d_den + timedelta(days=1), time.min, tzinfo=_VN)
    return bat_dau, ket_thuc


async def doc_nhat_ky_xem(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    tu: str | None = None,
    den: str | None = None,
    ma_khach: str | None = None,
    staff_id: str | None = None,
    gioi_han: int = 500,
) -> dict[str, Any]:
    """Các lượt xem trong khoảng ngày, mới trước; lọc theo mã khách / nhân viên."""
    bat_dau, ket_thuc = _bien_ngay(tu, den)
    ma = (ma_khach or "").strip() or None
    nv: str | None = None
    if staff_id:
        try:
            nv = str(UUID(staff_id))
        except ValueError:  # id rác → bỏ lọc, không ném
            nv = None
    async with pool.acquire() as conn:
        dong = await conn.fetch(
            """
            SELECT n.xem_luc, n.vai, n.loai, n.cua, n.doi_tuong_id,
                   n.staff_id::text AS staff_id, s.full_name AS nguoi_xem,
                   p.patient_code AS ma_khach
              FROM nhat_ky_xem_ho_so n
              LEFT JOIN staff s ON s.id = n.staff_id
              LEFT JOIN patient p
                ON p.clinic_patient_id = n.clinic_patient_id
               AND p.clinic_id = n.clinic_id
             WHERE n.clinic_id = $1::uuid
               AND n.xem_luc >= $2 AND n.xem_luc < $3
               AND ($4::text IS NULL OR p.patient_code = $4)
               AND ($5::uuid IS NULL OR n.staff_id = $5::uuid)
             ORDER BY n.xem_luc DESC
             LIMIT $6
            """,
            clinic_id,
            bat_dau,
            ket_thuc,
            ma,
            nv,
            gioi_han + 1,
        )
        nguoi = await conn.fetch(
            """
            SELECT DISTINCT n.staff_id::text AS staff_id, s.full_name AS ten
              FROM nhat_ky_xem_ho_so n JOIN staff s ON s.id = n.staff_id
             WHERE n.clinic_id = $1::uuid AND n.xem_luc >= $2 AND n.xem_luc < $3
             ORDER BY s.full_name
            """,
            clinic_id,
            bat_dau,
            ket_thuc,
        )
    return {
        "tu": bat_dau.date().isoformat(),
        "den": (ket_thuc - timedelta(days=1)).date().isoformat(),
        "dong": [
            {
                "luc": r["xem_luc"].isoformat(),
                "nguoi_xem": r["nguoi_xem"] or "—",
                "staff_id": r["staff_id"],
                "vai": r["vai"],
                "vai_ten": nhan_vai(r["vai"])[0] or r["vai"],
                "ma_khach": r["ma_khach"] or "(khách đã xoá)",
                "loai": r["loai"],
                "loai_ten": LOAI.get(r["loai"], r["loai"]),
                "cua": r["cua"],
            }
            for r in dong[:gioi_han]
        ],
        "bi_cat": len(dong) > gioi_han,
        "nhan_vien": [{"staff_id": r["staff_id"], "ten": r["ten"]} for r in nguoi],
    }


__all__ = ["LOAI", "doc_nhat_ky_xem", "ghi_luot_xem", "khung_cua", "tra_khach"]
