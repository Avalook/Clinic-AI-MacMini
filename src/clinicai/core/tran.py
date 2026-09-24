"""Trần số dòng — có trần là đúng, cắt mà im lặng là sai.

CHUYỆN ĐÃ XẢY RA (23/09/2026). Bảng "Chỉ định hôm nay" của trưởng ca cắt ở 500
dòng mà không báo gì. Nghĩa là hôm nào phòng khám đông hơn thế, trưởng ca nhìn
một bảng **thiếu người** và tưởng đã hết — khách của mình nằm ngoài trang, không
ai biết. Phát hiện tình cờ vì một bài kiểm đỏ khi database thử tích đủ dữ liệu.

LUẬT RÚT RA: mọi câu có `LIMIT` phục vụ màn hình phải **nói ra khi nó cắt**.

Có hai cách nói, chọn theo chỗ dùng:

    `dem_va_bi_cat`     màn trả về một object → thêm `tong` và `bi_cat` để màn
                        hiện "đang xem 500/612". Đây là cách TỐT NHẤT: người
                        dùng biết ngay.

    `canh_bao_neu_day`  màn trả về một danh sách trần (đổi hình dạng là phải
                        sửa cả frontend) → ít nhất phải kêu lên trong log, kèm
                        tên bảng và con số, để người trực thấy trước khi khách
                        thấy. Đây là mức TỐI THIỂU, không phải mức đủ.

Trần không phải thứ xấu: một ngày dữ liệu hỏng không được kéo sập màn hình của cả
phòng khám. Cái sai là cắt trong im lặng.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()


def canh_bao_neu_day(ten_bang: str, so_dong: int, tran: int, **ngu_canh: Any) -> bool:
    """Kêu lên khi một bảng chạm trần. Trả về True nếu đã chạm.

    Không đổi hình dạng dữ liệu trả về, nên dùng được ở mọi chỗ mà không phải
    sửa frontend cùng lúc. Đổi lại, người dùng KHÔNG thấy — chỉ log thấy. Chỗ
    nào quan trọng thì nâng lên `dem_va_bi_cat`.
    """
    if so_dong < tran:
        return False
    logger.warning(
        "bang_bi_cat",
        bang=ten_bang,
        so_dong=so_dong,
        tran=tran,
        **ngu_canh,
    )
    return True


async def dem_va_bi_cat(
    conn: asyncpg.Connection,
    *,
    cau_dem: str,
    tham_so: list[Any],
    so_dong: int,
    tran: int,
    ten_bang: str,
) -> dict[str, Any]:
    """Đếm tổng thật để màn nói được "đang xem N/M".

    Chỉ đếm khi đã chạm trần: một câu đếm thêm ở mọi lượt đọc là cái giá không
    cần trả cho ngày thường, khi bảng có ba mươi dòng.
    """
    if so_dong < tran:
        return {"tong": so_dong, "bi_cat": False}
    tong = int(await conn.fetchval(cau_dem, *tham_so) or so_dong)
    canh_bao_neu_day(ten_bang, so_dong, tran, tong=tong)
    return {"tong": tong, "bi_cat": tong > so_dong}


__all__ = ["canh_bao_neu_day", "dem_va_bi_cat"]
