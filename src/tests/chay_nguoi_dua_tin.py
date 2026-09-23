"""Cho người đưa tin chạy một vòng trong bài kiểm (thay cho worker `--su-kien`).

Từ 24/09/2026 việc xếp hàng sau check-in / sinh hiệu / tư vấn KHÔNG còn chạy
ngay trong lệnh ghi: khối HÀNH TRÌNH nghe sự kiện rồi làm (chuẩn lego,
docs/CHUAN-CAM-LEGO.md). Ở máy thật, worker `--su-kien` làm việc này mỗi giây;
trong bài kiểm, gọi hàm dưới ngay sau lệnh ghi.
"""

from __future__ import annotations

import asyncpg

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import HANH_TRINH
from clinicai.events.worker import lam_mot_dong


async def chay_hanh_trinh(pool: asyncpg.Pool) -> None:
    while await lam_mot_dong(pool, HANH_TRINH):
        pass
