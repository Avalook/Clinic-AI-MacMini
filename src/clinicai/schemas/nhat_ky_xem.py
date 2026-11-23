"""Hợp đồng cửa `GET /ops/xem-ho-so` — nhật ký ai đã xem hồ sơ khách nào.

Chỉ định danh: mã khách (không họ tên, không SĐT), loại hồ sơ, cửa API.
"""

from __future__ import annotations

from pydantic import BaseModel


class DongXemHoSo(BaseModel):
    luc: str
    nguoi_xem: str
    staff_id: str
    vai: str
    #: Tên vai tiếng Việt, máy chủ tính sẵn.
    vai_ten: str
    ma_khach: str
    loai: str
    loai_ten: str
    cua: str


class NhanVienDaXem(BaseModel):
    staff_id: str
    ten: str


class NhatKyXemHoSo(BaseModel):
    tu: str
    den: str
    dong: list[DongXemHoSo]
    #: True = còn dòng ngoài trần 500 — lọc hẹp hơn (khách / nhân viên / ngày).
    bi_cat: bool
    #: Người đã xem trong khoảng ngày — cho ô lọc "Nhân viên".
    nhan_vien: list[NhanVienDaXem]
