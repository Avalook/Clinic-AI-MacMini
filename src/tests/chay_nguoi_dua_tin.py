"""Cho người đưa tin chạy một vòng trong bài kiểm (thay cho worker `--su-kien`).

Từ 24/09/2026 việc xếp hàng sau check-in / sinh hiệu / tư vấn KHÔNG còn chạy
ngay trong lệnh ghi: khối HÀNH TRÌNH nghe sự kiện rồi làm (chuẩn lego,
docs/CHUAN-CAM-LEGO.md). Ở máy thật, worker `--su-kien` làm việc này mỗi giây;
trong bài kiểm, gọi hàm dưới ngay sau lệnh ghi.
"""

from __future__ import annotations

from typing import Any

import asyncpg

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import HANH_TRINH
from clinicai.events.worker import lam_mot_dong


async def chay_hanh_trinh(pool: asyncpg.Pool) -> None:
    while await lam_mot_dong(pool, HANH_TRINH):
        pass


async def chay_ben_nhan(pool: asyncpg.Pool, *ben_nhan: str) -> None:
    """Chạy một vòng cho các bên nhận chỉ định (vd khối Chuông, dòng thời gian)."""
    for ten in ben_nhan:
        while await lam_mot_dong(pool, ten):
            pass


def vong_doc_chay_ngay_sau_lenh_tep(monkeypatch: Any) -> None:
    """Bài kiểm luồng cũ: coi như worker chạy khối VÒNG ĐỌC ngay sau mỗi lệnh tệp.

    Từ 24/09/2026 tải / xác nhận / thu hồi tệp KHÔNG còn gọi thẳng khối Khám —
    khối VÒNG ĐỌC nghe sự kiện rồi mở / rút chỗ chờ đọc kết quả. Các bài kiểm
    viết trước đó khẳng định vòng đọc ngay sau lệnh; bọc lệnh để chạy một vòng
    người đưa tin (y như worker `--su-kien` làm mỗi giây ở máy thật).
    """
    from clinicai.events.catalogue import VONG_DOC
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    for ten in ("tai_len", "xac_nhan_tep", "thu_hoi_tep"):
        goc = getattr(TepKetQuaService, ten)

        async def boc(
            self: TepKetQuaService, *a: Any, _goc: Any = goc, **kw: Any
        ) -> Any:
            kq = await _goc(self, *a, **kw)
            await chay_ben_nhan(self._pool, VONG_DOC)
            return kq

        monkeypatch.setattr(TepKetQuaService, ten, boc)
