"""Các bên nhận sự kiện. Thêm một bên nhận = thêm một file ở đây + một dòng
trong danh mục sự kiện. KHÔNG sửa module phát."""

from clinicai.events.consumers import dong_thoi_gian, hanh_trinh, trach_nhiem

__all__ = ["dong_thoi_gian", "hanh_trinh", "trach_nhiem"]
