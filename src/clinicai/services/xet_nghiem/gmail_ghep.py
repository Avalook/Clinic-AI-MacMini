"""Tự ghép thư kết quả Gmail vào đúng CHỈ ĐỊNH — Gmail G3 + G5 (Tuyền duyệt 11/11/2026).

Chỉ thư nhận TỪ mốc `xet_nghiem_cai_dat.gmail_tu_ngay` (giờ VN) trở đi, và chỉ thư có
xác thực đúng miền người gửi (DKIM/DMARC — header From giả được), mới được xét. Còn
lại ⇒ `LUU_TRU` (chỉ ở Kho) KÈM lý do `luu_tru_vi_sao` (CHUA_DAT_MOC · TRUOC_MOC ·
KHONG_XAC_THUC · CHUA_DU_KET_QUA · PHIEU_MA_VACH · DA_CO_KET_QUA). Đặt mốc lùi ngày ở
lần quét đầu ⇒ thư cũ từ mốc được gán ngược.

G5 (11/11): ứng viên là MỌI chỉ định loại xét nghiệm lab đó làm (`ghep_khach.
doc_chi_dinh`: gán ở Cài đặt → Đối tác hoặc việc Bàn XN của lab), chỉ định trong 60
ngày TRƯỚC ngày nhận thư — không cần Bàn XN, không cần bấm Lấy mẫu (luật 05/11 "chỉ
ghép việc đã lấy mẫu" chỉ còn ở Drive).

Quyết định là MỘT hàm thuần `quyet` (test bằng bảng). Khớp tên + SĐT = luật duy nhất
`ghep_khach.khop_ds` (cùng luật Drive). Năm sinh để gỡ khi nhiều khách cùng khớp, và
(G14, 12/11) để tự gán khi SĐT lệch: `khop_ten_nam_sinh` — tên trùng nguyên + năm sinh
+ chỉ một khách tên đó + có chỉ định của lab.
Không ghép theo mã mẫu của lab, không theo mã xét nghiệm trong tên tệp. Không chắc ⇒
hàng ghép tay kèm lý do + gợi ý, KHÔNG đoán.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg
import structlog

from clinicai.services.xet_nghiem import ghep_khach
from clinicai.services.xet_nghiem.ghep_khach import UngVien, chuan
from clinicai.services.xet_nghiem.gmail_doc import DocThu, loai_dich_vu

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
    #: Chỉ khi `ly_do` = LUU_TRU: vì sao chỉ cất ở Kho (CHECK ở Postgres).
    luu_tru_vi_sao: str | None = None
    #: Tự gán KHÔNG chỉ định (`order_id` None): lượt khám để gắn tờ vào hồ sơ khách.
    appointment_id: str | None = None


def luu_tru(vi_sao: str, **goi_y: str | None) -> QuyetGmail:
    return QuyetGmail("LUU_TRU", luu_tru_vi_sao=vi_sao, **goi_y)


def quyet(
    d: DocThu, viec: list[UngVien], co_chu: bool, nhan_luc: datetime
) -> QuyetGmail:
    """HÀM THUẦN: một PDF (đã đọc theo luật lab) + các chỉ định ứng viên
    (`ghep_khach.doc_chi_dinh`, đã lọc 60 ngày trước `nhan_luc`) ⇒ quyết.

    - Không nhận ra kiểu thư ⇒ KHONG_RO_MAU_THU (người xem).
    - Kiểu nhận ra nhưng không được tự ghép (từng phần / phiếu) ⇒ LUU_TRU + lý do.
    - Thiếu tên / SĐT ⇒ KHONG_DOC_DUOC (PDF scan) hoặc KHONG_KHOP_KHACH.
    - Khớp ≠ 1 khách (sau khi gỡ bằng năm sinh) ⇒ KHONG_KHOP_KHACH / NHIEU_KHACH
      (người gọi đổi KHONG_KHOP_KHACH thành KHONG_THAY_CHI_DINH khi khách có thật).
    - Một khách: đúng 1 chỉ định chưa có tờ ⇒ TỰ GHÉP; nhiều ⇒ ONG_NHIEU_VIEC. Không
      chỉ định nào chờ: đúng 1 chỉ định CHỈ có tờ tải tay ⇒ TỰ GHÉP thêm (song song).
      Mọi chỉ định đã có tờ từ Gmail: tờ Gmail KHÔNG cũ hơn thư ⇒ thư trùng / cũ ⇒
      LUU_TRU DA_CO_KET_QUA; thư mới hơn ⇒ CO_BAN_MOI (bản sửa? người xem)."""
    if not d.kieu:
        return QuyetGmail("KHONG_RO_MAU_THU")
    if d.khong_tu_ghep:
        return luu_tru(d.khong_tu_ghep)
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
    return quyet_mot_khach(d.loai, khop, next(iter(khach)), nhan_luc)


def quyet_mot_khach(
    loai: frozenset[str], khop: list[UngVien], kh: str, nhan_luc: datetime
) -> QuyetGmail:
    """HÀM THUẦN — MỘT luật "tờ của khách `kh` vào đâu" (tự ghép G3–G7 và nút "Gán
    cho khách này" G9): `khop` = chỉ định ứng viên của ĐÚNG khách này."""
    khop = dung_loai(loai, khop)
    if not khop:  # PDF là loại khách KHÔNG có chỉ định (vd HPV mà chỉ chờ STD)
        return QuyetGmail("KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id=kh)
    # Đang chờ (chưa tờ nào) trước; không có thì chỉ định CHỈ có tờ tải tay (Tuyền
    # 11/11: tờ tay + tờ Gmail hiện song song, "Bản 2").
    for nhom in (
        [v for v in khop if not v.co_tep],
        [v for v in khop if v.co_tep and v.tep_gmail_luc is None],
    ):
        if len(nhom) == 1:
            v = nhom[0]
            return QuyetGmail(None, v.order_id, v.clinic_patient_id, v.visit_id)
        if nhom:
            return QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id=kh)
    # Mọi chỉ định của khách đã có tờ TỪ GMAIL.
    goi_y = {
        "goi_y_order_id": khop[0].order_id if len(khop) == 1 else None,
        "goi_y_clinic_patient_id": kh,
    }
    if any(v.tep_gmail_luc and v.tep_gmail_luc >= nhan_luc for v in khop):
        return luu_tru("DA_CO_KET_QUA", **goi_y)  # thư trùng / thư cũ hơn tờ Gmail
    return QuyetGmail("CO_BAN_MOI", **goi_y)


def khop_ten_nam_sinh(d: DocThu, viec: list[UngVien], so_cung_ten: int) -> str | None:
    """HÀM THUẦN (G14, Tuyền 12/11): thư KHÔNG khớp tên + SĐT ⇒ vẫn chắc là khách
    `kh` khi CẢ BỐN: tên trên phiếu TRÙNG NGUYÊN tên hồ sơ (bỏ dấu) · năm sinh trên
    phiếu = năm sinh hồ sơ · cả phòng khám chỉ MỘT khách đang dùng mang tên đó
    (`so_cung_ten`, người gọi đếm) · khách đó có chỉ định của lab này trong cửa sổ
    (`viec`). Lab ghi SĐT khác hồ sơ (số mới / số người nhà — prod 12/11: 33/59 thư chờ
    là "tên khớp, SĐT khác"). Thiếu một điều kiện ⇒ None (người gán, như cũ)."""
    t = chuan(d.ten)
    if not t or d.nam_sinh is None or so_cung_ten != 1:
        return None
    khach = {
        v.clinic_patient_id
        for v in viec
        if chuan(v.ten) == t and v.nam_sinh == d.nam_sinh
    }
    return next(iter(khach)) if len(khach) == 1 else None


def dung_loai(loai_pdf: frozenset[str], khop: list[UngVien]) -> list[UngVien]:
    """HÀM THUẦN (G7, Tuyền 11/11): chỉ định của MỘT khách khớp tên + SĐT ⇒ giữ chỉ
    định có loại xét nghiệm trùng loại đọc trong PDF (HPV vs STD của Tâm Minh). PDF
    không rõ loại ⇒ giữ hết; chỉ định không suy được loại (vd "Xét nghiệm máu") ⇒ giữ
    (không đủ căn cứ loại). Rỗng ⇒ khách không có chỉ định đúng loại này."""
    if not loai_pdf:
        return khop
    return [v for v in khop if not (dv := loai_dich_vu(v.ten_dich_vu)) or dv & loai_pdf]


def khong_thay_chi_dinh(q: QuyetGmail, khach_that: str | None) -> QuyetGmail:
    """HÀM THUẦN: `quyet` ra "không khớp khách nào" (trong số khách CÓ chỉ định) mà tên
    + SĐT vẫn khớp đúng MỘT hồ sơ khách (`gmail_luu.goi_y_khach`) ⇒ lý do thật là
    khách không có chỉ định loại này trong 60 ngày trước thư."""
    if q.ly_do != "KHONG_KHOP_KHACH" or khach_that is None:
        return q
    return replace(q, ly_do="KHONG_THAY_CHI_DINH", goi_y_clinic_patient_id=khach_that)


def gan_ho_so(q: QuyetGmail, luot: tuple[str, str] | None) -> QuyetGmail:
    """HÀM THUẦN (Tuyền 11/11): khách ĐÚNG (khớp tên + SĐT) mà không có chỉ định đúng
    loại ⇒ vẫn đưa tờ vào hồ sơ khách — gắn vào lượt khám gần nhất trước thư, KHÔNG tạo
    chỉ định (chỉ định là chuyện tiền / lượt). Không có lượt ⇒ giữ KHONG_THAY_CHI_DINH.
    Danh sách "có kết quả mà chưa có chỉ định" = tờ GMAIL có `service_order_id` NULL."""
    kh = q.goi_y_clinic_patient_id
    if q.ly_do != "KHONG_THAY_CHI_DINH" or kh is None or luot is None:
        return q
    visit_id, appointment_id = luot
    return QuyetGmail(
        None,
        clinic_patient_id=kh,
        visit_id=visit_id,
        goi_y_clinic_patient_id=kh,
        appointment_id=appointment_id,
    )


def vi_sao_khong_xet(nhan_luc: Any, moc: date | None, xac_thuc: bool) -> str | None:
    """HÀM THUẦN: vì sao thư KHÔNG được xét ghép (⇒ Lưu trữ), None = được xét."""
    if moc is None:
        return "CHUA_DAT_MOC"
    if not trong_moc(nhan_luc, moc):
        return "TRUOC_MOC"
    return None if xac_thuc else "KHONG_XAC_THUC"


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
    của tệp đối tác (`tai_len`, máy quét, nguồn GMAIL ⇒ Hợp lệ ngay từ 12/11, báo bác
    sĩ + CSKH), gắn vào dòng, phát `lab.result_arrived`.

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

    assert q.clinic_patient_id is not None
    assert q.order_id is not None or q.appointment_id is not None
    try:
        kq = await TepKetQuaService(pool).tai_len(
            identity=MayQuet(clinic_id=cid),
            clinic_patient_id=q.clinic_patient_id,
            data=data,
            ten_hien_thi=ten,
            service_order_id=q.order_id,
            # Không chỉ định ⇒ gắn vào lượt khám (hồ sơ khách), Tuyền 11/11.
            appointment_id=None if q.order_id else q.appointment_id,
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
    if q.order_id is not None:  # sự kiện việc xét nghiệm chỉ có khi có chỉ định
        await drive._phat_den(
            pool, cid, drive.Quyet(q.order_id, q.clinic_patient_id, q.visit_id, None)
        )
    return True
