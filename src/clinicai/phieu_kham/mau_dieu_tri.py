"""Mẫu PHIẾU ĐIỀU TRỊ (Tuyền chốt 07/10/2026) — hằng số dùng chung, không import
gì của dự án (engine phiếu kết quả, khối 2 hồ sơ và bản in cùng đọc; đặt ở
`mau_goi_y` thì vòng import khung ↔ form_engine)."""

from __future__ import annotations

#: Mẫu kết quả "Phiếu điều trị": hai ô chữ "Cảm nhận", "Vấn đề sau điều trị".
MAU_PHIEU_DIEU_TRI = "PHIEU_DIEU_TRI"

#: Biểu mẫu KHÔNG có bước "Hoàn tất": Xong dịch vụ là mốc hoàn thành, mỗi lần
#: lưu là ghi nhận (lịch sử từng bản ở `form_instance_lich_su`); bản in không
#: ghi "BẢN NHÁP"; nội dung đọc được ngay cả khi chưa ai bấm chốt.
MAU_KHONG_HOAN_TAT = frozenset({f"KQ_{MAU_PHIEU_DIEU_TRI}"})

__all__ = ["MAU_KHONG_HOAN_TAT", "MAU_PHIEU_DIEU_TRI"]
