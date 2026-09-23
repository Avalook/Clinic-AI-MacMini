"""Đưa bảy khung vào `form_definition` làm bản v1 ĐANG DÙNG.

Cùng cách 18 mẫu kết quả được dựng (migration 20260923000005): v1 PUBLISHED,
`xuat_ban_boi` để TRỐNG — khung do hệ thống trích từ tài liệu, ghi tên một
người vào đó là mạo danh rằng đã có người duyệt nội dung.

CHẠY LẠI ĐƯỢC, VÀ KHÔNG ĐÈ. Đã có bất kỳ phiên bản nào (kể cả v1 đã về hưu vì
có v2) thì không chạm: đổi nội dung là việc của `PublishFormVersion`, không
phải của lần nạp ban đầu. Nạp lại mà đè v1 là sửa tại chỗ một bản đã xuất
bản — đúng điều engine cấm.

Chỗ gọi hiện tại: chỉ test. Lên máy chủ thật thì chuyển thành một migration
dữ liệu — xem INTEGRATION_POINT trong `docs/phieu-kham/TICH-HOP.md`.
"""

from __future__ import annotations

import json

import asyncpg

from clinicai.phieu_kham.khung import NHOM, tat_ca


async def nap_ban_dau(conn: asyncpg.Connection, *, clinic_id: str) -> list[str]:
    """Nạp phiếu nào chưa có. Trả về các form_id vừa nạp."""
    moi: list[str] = []
    for dn in tat_ca():
        da_co = await conn.fetchval(
            "SELECT 1 FROM form_definition WHERE clinic_id = $1::uuid AND form_id = $2",
            clinic_id,
            dn["form_id"],
        )
        if da_co:
            continue
        await conn.execute(
            "INSERT INTO form_definition"
            " (clinic_id, form_id, version, ten, nhom, khung, trang_thai,"
            "  xuat_ban_boi, xuat_ban_luc)"
            " VALUES ($1::uuid, $2, 1, $3, $4, $5::jsonb, 'PUBLISHED', NULL, now())"
            " ON CONFLICT DO NOTHING",
            clinic_id,
            dn["form_id"],
            dn["ten"],
            NHOM,
            json.dumps(dn["khung"], ensure_ascii=False),
        )
        moi.append(dn["form_id"])
    return moi


__all__ = ["nap_ban_dau"]
