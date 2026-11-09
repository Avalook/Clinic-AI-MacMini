"""Tự ghép thư kết quả Gmail vào đúng việc — Gmail G3 (luật Tuyền duyệt 09/11/2026).

Chỉ thư nhận TỪ mốc `xet_nghiem_cai_dat.gmail_tu_ngay` (giờ VN) trở đi, và chỉ thư có
xác thực đúng miền người gửi (DKIM/DMARC — header From giả được), mới được xét. Thư
trước mốc / không xác thực / Greenlab "Chưa đủ kết quả" / phiếu mã vạch ⇒ `LUU_TRU`
(chỉ ở Kho) như G2. Mốc chỉ áp cho thư NHẬN SAU khi đặt mốc; thư đã vào Kho trước đó
không được xét lại tự động.

Quyết định là MỘT hàm thuần `quyet` (test bằng bảng). Khớp tên + SĐT = luật duy nhất
`ghep_khach.khop_ds` (cùng luật Drive). Năm sinh chỉ để gỡ khi nhiều khách cùng khớp.
Không ghép theo mã mẫu của lab, không theo mã xét nghiệm trong tên tệp. Không chắc ⇒
hàng ghép tay kèm lý do + gợi ý, KHÔNG đoán.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg
import structlog

from clinicai.services.xet_nghiem import ghep_khach
from clinicai.services.xet_nghiem.ghep_khach import UngVien
from clinicai.services.xet_nghiem.gmail_doc import DocThu

logger = structlog.get_logger()

_VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class QuyetGmail:
    """`ly_do` None = TỰ GHÉP vào `order_id`; còn lại = mã lý do chờ (`drive_tep`)."""

    ly_do: str | None
    order_id: str | None = None
    clinic_patient_id: str | None = None
    visit_id: str | None = None
    goi_y_order_id: str | None = None
    goi_y_clinic_patient_id: str | None = None


LUU_TRU: Final = QuyetGmail("LUU_TRU")


def quyet(d: DocThu, viec: list[UngVien], co_chu: bool) -> QuyetGmail:
    """HÀM THUẦN: một PDF (đã đọc theo luật lab) + các việc của đối tác
    (`ghep_khach.doc_viec`) ⇒ quyết.

    - Không nhận ra kiểu thư ⇒ KHONG_KHOP_KHACH (ghép tay — người xem).
    - Kiểu nhận ra nhưng không được tự ghép (từng phần / phiếu) ⇒ LUU_TRU.
    - Thiếu tên / SĐT ⇒ KHONG_DOC_DUOC (PDF scan) hoặc KHONG_KHOP_KHACH.
    - Khớp ≠ 1 khách (sau khi gỡ bằng năm sinh) ⇒ KHONG_KHOP_KHACH / NHIEU_KHACH.
    - Một khách: đúng 1 việc đang chờ kết quả ⇒ TỰ GHÉP; nhiều ⇒ ONG_NHIEU_VIEC; chưa
      lấy mẫu ⇒ CHUA_LAY_MAU; đã có tờ ⇒ CO_BAN_MOI (gợi ý việc khi đúng một)."""
    if not d.kieu:
        return QuyetGmail("KHONG_KHOP_KHACH")
    if not d.tu_ghep_duoc:
        return LUU_TRU
    if not d.ten or not d.sdt:
        return QuyetGmail("KHONG_DOC_DUOC" if not co_chu else "KHONG_KHOP_KHACH")
    khop = ghep_khach.khop_ds(f"{d.ten}\n{d.sdt}", viec)
    if len({v.clinic_patient_id for v in khop}) > 1 and d.nam_sinh is not None:
        # Năm sinh chỉ để GỠ; lọc mà không còn ai (hồ sơ thiếu năm sinh) ⇒ giữ nguyên
        # ⇒ NHIEU_KHACH (người chọn), không được rơi thành "không khớp ai".
        loc = [v for v in khop if v.nam_sinh == d.nam_sinh]
        khop = loc or khop
    khach = {v.clinic_patient_id for v in khop}
    if not khach:
        return QuyetGmail("KHONG_KHOP_KHACH")
    if len(khach) > 1:
        return QuyetGmail("NHIEU_KHACH")
    kh = next(iter(khach))
    cho = [v for v in khop if v.dang_cho]
    if len(cho) == 1:
        v = cho[0]
        return QuyetGmail(None, v.order_id, v.clinic_patient_id, v.visit_id)
    if cho:
        return QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id=kh)
    for ma, nhom in (
        ("CHUA_LAY_MAU", [v for v in khop if not v.da_lay_mau and not v.co_tep]),
        ("CO_BAN_MOI", [v for v in khop if v.co_tep]),
    ):
        if nhom:
            return QuyetGmail(
                ma,
                goi_y_order_id=nhom[0].order_id if len(nhom) == 1 else None,
                goi_y_clinic_patient_id=kh,
            )
    return QuyetGmail("KHONG_KHOP_KHACH", goi_y_clinic_patient_id=kh)


def trong_moc(nhan_luc: Any, moc: date | None) -> bool:
    """Thư nhận (giờ VN) từ mốc trở đi? Không mốc ⇒ False (chưa tự ghép thư nào)."""
    if moc is None or nhan_luc is None:
        return False
    try:
        return bool(nhan_luc.astimezone(_VN).date() >= moc)
    except (AttributeError, ValueError):
        return False


async def danh_loi_tep(pool: asyncpg.Pool, cid: str, dong_id: str) -> None:
    """Tự ghép hỏng ⇒ dòng sang LOI_TEP (hàng ghép tay có lý do), không mất thư. Dòng
    đã có tờ / đã từ chối thì để nguyên."""
    await pool.execute(
        "UPDATE drive_tep SET ly_do_cho = 'LOI_TEP' WHERE clinic_id = $1::uuid"
        " AND id = $2::uuid AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
        cid,
        dong_id,
    )


async def gan_tu_dong(
    pool: asyncpg.Pool, cid: str, dong_id: str, q: QuyetGmail, data: bytes, ten: str
) -> bool:
    """Dòng thư đã ghi (cùng giao dịch cả thư) ⇒ tạo tờ kết quả qua ĐÚNG lõi tải lên
    của tệp đối tác (`tai_len`, máy quét, nguồn GMAIL ⇒ CHO_XAC_NHAN, báo bác sĩ +
    CSKH), gắn vào dòng, phát `lab.result_arrived`.

    Dòng đã hiện ở hàng ghép tay từ lúc commit ⇒ giữ CÙNG khoá của Gán tay / Từ chối
    (`ghep_tay.khoa_tep`) và đọc lại dòng TRONG khoá: người đã xử lý trước thì thôi,
    không tạo tờ thứ hai."""
    from clinicai.services.xet_nghiem import ghep_tay

    async with ghep_tay.khoa_tep(pool, dong_id):
        con = await pool.fetchval(
            "SELECT tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL FROM drive_tep"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            dong_id,
        )
        if not con:
            return False
        return await _gan_trong_khoa(pool, cid, dong_id, q, data, ten)


async def _gan_trong_khoa(
    pool: asyncpg.Pool, cid: str, dong_id: str, q: QuyetGmail, data: bytes, ten: str
) -> bool:
    from clinicai.services.nguon_tep import MayQuet
    from clinicai.services.tep_ket_qua_service import TepKetQuaService
    from clinicai.services.xet_nghiem import drive

    assert q.order_id is not None and q.clinic_patient_id is not None
    try:
        kq = await TepKetQuaService(pool).tai_len(
            identity=MayQuet(clinic_id=cid),
            clinic_patient_id=q.clinic_patient_id,
            data=data,
            ten_hien_thi=ten,
            service_order_id=q.order_id,
            la_tep_doi_tac=True,
            tu_drive=True,
            tu_gmail=True,
        )
    except Exception as e:  # noqa: BLE001 — tệp hỏng / quá lớn ⇒ ghép tay
        logger.warning("gmail_tu_ghep_loi", drive_tep_id=dong_id, loai=type(e).__name__)
        await danh_loi_tep(pool, cid, dong_id)
        return False
    n = await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = $3::uuid, ghep_luc = now()"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid"
        "   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
        cid,
        dong_id,
        str(kq["id"]),
    )
    if n != "UPDATE 1":
        # Không thể xảy ra trong khoá (mọi lệnh ghi dòng này đều giữ nó). Máy không có
        # quyền "Từ chối tờ" để tự bù ⇒ không báo bác sĩ, để log cho người xem.
        logger.error("gmail_tu_ghep_lech", drive_tep_id=dong_id, tep_id=str(kq["id"]))
        return False
    await drive._phat_den(
        pool, cid, drive.Quyet(q.order_id, q.clinic_patient_id, q.visit_id, None)
    )
    return True
