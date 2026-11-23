"""Cổng liên thông ĐƠN THUỐC QUỐC GIA (TT 26/2025/TT-BYT, 24/11/2026).

Toàn bộ hợp đồng giữa ClinicAI và Hệ thống đơn thuốc quốc gia: hai giao diện nhỏ
(gửi đơn, ký số) và vài dataclass thuần. Nghiệp vụ (hàng chờ, ánh xạ, canh gác)
chỉ phụ thuộc file này; nhà cung cấp cụ thể ở ``clinicai.adapters.don_thuoc_quoc_gia``,
chọn lúc chạy theo cấu hình.

CHỈ MỘT ĐỘNG TỪ: ``gui``. Chuẩn kết nối QĐ 808/QĐ-BYT không có API sửa / huỷ đơn,
và QĐ 425/QĐ-BYT Điều 9: đơn đã gửi "không được thay đổi và cập nhật lại" — đổi
đơn = gửi ĐƠN MỚI mã mới (hàng chờ lo việc đó).

``GoiDon`` là gói đơn CHUẨN CỦA CLINICAI — không phải định dạng API. Đổi tên trường
của API chỉ đụng adapter thật, không đụng hàng chờ hay dữ liệu đã lưu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class GuiDonError(RuntimeError):
    """Không gửi được. ``thu_lai=False`` = hệ thống quốc gia từ chối NỘI DUNG
    (thiếu trường, sai mã) — thử lại vô ích, hàng chờ dừng ngay thay vì đốt hết
    lượt thử vào cùng một câu trả lời."""

    def __init__(self, thong_bao: str, *, thu_lai: bool = True) -> None:
        super().__init__(thong_bao)
        self.thu_lai = thu_lai


@dataclass(frozen=True)
class BacSiKe:
    """Bác sĩ đứng tên đơn. Hệ thống quốc gia lấy tên + CCHN + cơ sở từ TOKEN
    đăng nhập của bác sĩ, nên gói gửi đi chỉ cần biết đăng nhập bằng ai."""

    staff_id: str
    ho_ten: str
    #: Số chứng chỉ hành nghề (`staff.license_number`).
    so_chung_chi: str | None
    #: Mã liên thông bác sĩ do donthuocquocgia.vn cấp — lấy từ cấu hình
    #: (`DTQG_BAC_SI`), ClinicAI chưa có cột.
    ma_lien_thong: str | None = None


@dataclass(frozen=True)
class NguoiBenh:
    ma_benh_nhan: str
    ho_ten: str
    #: ISO yyyy-mm-dd; chỉ có năm sinh thì None (``nam_sinh`` giữ năm).
    ngay_sinh: str | None
    nam_sinh: int | None
    #: "NAM" | "NU" | None.
    gioi_tinh: str | None
    so_dinh_danh: str | None
    dia_chi: str | None
    dien_thoai: str | None
    nguoi_giam_ho: str | None = None


@dataclass(frozen=True)
class DongThuoc:
    ten_thuoc: str
    #: Mã thuốc. QĐ 808 ghi "danh mục do Cục Quản lý dược cấp" nhưng HDSD FAQ
    #: 1.12 nói chưa có quy định chung → tạm dùng mã hàng nội bộ (`ma_hang`).
    ma_thuoc: str | None
    #: Hoạt chất chính (trường `biet_duoc` của API).
    hoat_chat: str | None
    #: Số lượng dạng chữ như trên đơn ("2 hộp") và dạng số (API đòi số).
    so_luong: str | None
    so_luong_so: float | None
    don_vi: str | None
    cach_dung: str | None
    luu_y: str | None = None


@dataclass(frozen=True)
class GoiDon:
    """Một phiên bản đơn thuốc của một lượt khám."""

    ma_don: str
    visit_id: str
    #: Lúc kê (ISO, giờ Việt Nam) — lúc lượt đóng.
    ngay_ke: str
    bac_si: BacSiKe | None
    nguoi_benh: NguoiBenh
    chan_doan: str | None
    #: Mã ICD-10 — ClinicAI CHƯA lưu (chẩn đoán là chữ tự do trên phiếu khám).
    ma_icd: list[str] = field(default_factory=list)
    loi_dan: str | None = None
    thuoc: list[DongThuoc] = field(default_factory=list)


@dataclass(frozen=True)
class ChuKy:
    """Chữ ký số (TT 26/2025 Điều 10). ``gia_tri`` là base64."""

    thuat_toan: str
    gia_tri: str
    chung_thu: str | None = None


@dataclass(frozen=True)
class KetQuaGui:
    #: Câu / mã hệ thống quốc gia trả về.
    ma_tra_ve: str | None


@runtime_checkable
class KySoDonThuoc(Protocol):
    """Điểm cắm chữ ký số. Chưa chọn nhà cung cấp — docs/LIEN-THONG-DON-THUOC.md."""

    ten: str

    async def ky(self, du_lieu: bytes) -> ChuKy | None:
        """Ký ``du_lieu`` (gói đơn đã chuẩn hoá). None = không ký."""
        ...


@runtime_checkable
class DonThuocQuocGiaProvider(Protocol):
    #: "GIA_LAP" | "THAT" — ghi vào `dtqg_gui.nha_cung_cap`.
    ten: str

    def thieu(self, goi: GoiDon) -> list[str]:
        """Trường NHÀ CUNG CẤP NÀY bắt buộc mà gói còn trống (câu người đọc hiểu).
        Khác rỗng → hàng chờ dừng đơn ấy (LOI), không gọi mạng."""
        ...

    async def gui(self, goi: GoiDon, chu_ky: ChuKy | None) -> KetQuaGui:
        """Gửi một đơn. Gửi lại CÙNG mã đơn sau một lần hết giờ chờ (mà thật ra
        đã thành công) phải được coi là thành công — adapter lo việc đó."""
        ...


__all__ = [
    "BacSiKe",
    "ChuKy",
    "DonThuocQuocGiaProvider",
    "DongThuoc",
    "GoiDon",
    "GuiDonError",
    "KetQuaGui",
    "KySoDonThuoc",
    "NguoiBenh",
]
