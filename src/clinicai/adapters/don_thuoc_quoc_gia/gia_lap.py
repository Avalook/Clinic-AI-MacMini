"""Hệ thống đơn thuốc quốc gia GIẢ LẬP — cho test và staging.

Hệ thống quốc gia KHÔNG có môi trường thử công khai (tra 24/11/2026: QĐ 808, HDSD
101 trang, trang chủ đều không có), nên staging dùng bản này. Không gọi mạng. Nhớ
đơn đã nhận theo mã đơn (bộ nhớ tiến trình), cư xử như hệ thống thật ở chỗ hàng
chờ dựa vào: gửi lại cùng mã + cùng nội dung → coi là một (idempotent); cùng mã
khác nội dung → từ chối nội dung (đơn đã gửi không sửa được — QĐ 425 Điều 9).

Test bơm lỗi bằng ``hong_lan_toi`` (lỗi mạng, thử lại được) hoặc
``tu_choi_lan_toi`` (lỗi nội dung, không thử lại).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clinicai.ports.don_thuoc_quoc_gia import ChuKy, GoiDon, GuiDonError, KetQuaGui


@dataclass
class ProviderGiaLap:
    ten: str = "GIA_LAP"
    #: Mã đơn → gói đã nhận.
    da_nhan: dict[str, GoiDon] = field(default_factory=dict)
    #: Mỗi lần gọi `gui` (kể cả hỏng): mã đơn.
    loi_goi: list[str] = field(default_factory=list)
    hong_lan_toi: int = 0
    tu_choi_lan_toi: int = 0

    def thieu(self, goi: GoiDon) -> list[str]:
        # Giả lập không đòi thêm gì ngoài mức tối thiểu của TT 26.
        return []

    async def gui(self, goi: GoiDon, chu_ky: ChuKy | None) -> KetQuaGui:
        self.loi_goi.append(goi.ma_don)
        if self.hong_lan_toi > 0:
            self.hong_lan_toi -= 1
            raise GuiDonError("GIA_LAP: hết giờ chờ (giả lập lỗi mạng)")
        if self.tu_choi_lan_toi > 0:
            self.tu_choi_lan_toi -= 1
            raise GuiDonError("GIA_LAP: 422 từ chối nội dung", thu_lai=False)
        cu = self.da_nhan.get(goi.ma_don)
        if cu is not None and cu != goi:
            raise GuiDonError("GIA_LAP: mã đơn đã tồn tại", thu_lai=False)
        self.da_nhan[goi.ma_don] = goi
        return KetQuaGui(ma_tra_ve="Gửi đơn thuốc thành công (giả lập)")


@dataclass
class KhongKy:
    """Không ký: trường `signature` của API để rỗng. Bộ Y tế chưa hướng dẫn định
    dạng chữ ký trong gói API (HDSD FAQ 1.6, 1.22) — xem docs."""

    ten: str = "khong"

    async def ky(self, du_lieu: bytes) -> ChuKy | None:
        return None


__all__ = ["KhongKy", "ProviderGiaLap"]
