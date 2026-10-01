"""Các bên nhận sự kiện. Thêm một bên nhận = thêm một file ở đây + một dòng
trong danh mục sự kiện. KHÔNG sửa module phát."""

from clinicai.events.consumers import (
    chuong,
    cong_no,
    doi_tac,
    dong_thoi_gian,
    hanh_trinh,
    nhac_tai_kham,
    nhac_viec,
    trach_nhiem,
    vong_doc,
)

__all__ = [
    "chuong",
    "cong_no",
    "doi_tac",
    "dong_thoi_gian",
    "hanh_trinh",
    "nhac_tai_kham",
    "nhac_viec",
    "trach_nhiem",
    "vong_doc",
]
