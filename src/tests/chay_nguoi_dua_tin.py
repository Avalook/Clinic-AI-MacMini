"""Cho người đưa tin chạy một vòng trong bài kiểm (thay cho worker `--su-kien`).

Từ 24/09/2026 việc xếp hàng sau check-in / sinh hiệu / tư vấn KHÔNG còn chạy
ngay trong lệnh ghi: khối HÀNH TRÌNH nghe sự kiện rồi làm (chuẩn lego,
docs/CHUAN-CAM-LEGO.md). Ở máy thật, worker `--su-kien` làm việc này mỗi giây;
trong bài kiểm, gọi hàm dưới ngay sau lệnh ghi.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import DOI_TAC_NHAN_VIEC, HANH_TRINH
from clinicai.events.worker import lam_mot_dong


async def chay_het(pool: asyncpg.Pool, ben_nhan: str) -> None:
    """Chạy bên nhận tới khi hết việc — CHỊU được đồng hồ máy ảo lùi.

    Đỏ ngẫu nhiên 24/09 (bắt được sau ~12 lần chạy lặp): dòng giao vừa ghi có
    `next_attempt_at = now()`; Docker Desktop thỉnh thoảng lùi đồng hồ vài chục
    ms (memory khong-chay-gate-chong-tai-docker-desktop), nên lượt nhận ngay sau
    thấy `next_attempt_at > now()` → "hết việc" dù việc còn đó → bài đỏ oan. Máy
    thật không bị (worker chạy mỗi giây). Còn dòng PENDING chưa thử lần nào thì
    đợi một chút rồi nhận lại, tối đa ~1 giây.
    """
    for _ in range(20):
        while await lam_mot_dong(pool, ben_nhan):
            pass
        con = await pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM event_delivery WHERE consumer = $1"
            " AND status = 'PENDING' AND attempts = 0"
            " AND next_attempt_at <= now() + interval '1 second')",
            ben_nhan,
        )
        if not con:
            return
        await asyncio.sleep(0.05)


async def chay_hanh_trinh(pool: asyncpg.Pool) -> None:
    await chay_het(pool, HANH_TRINH)


async def chay_ben_nhan(pool: asyncpg.Pool, *ben_nhan: str) -> None:
    """Chạy một vòng cho các bên nhận chỉ định (vd khối Chuông, dòng thời gian)."""
    for ten in ben_nhan:
        await chay_het(pool, ten)


async def doi_tac_nhan(pool: asyncpg.Pool) -> None:
    """Chạy bên nhận "đối tác nhận việc" (nghe đã thu tiền / lấy mẫu xong)."""
    await chay_het(pool, DOI_TAC_NHAN_VIEC)


async def danh_dau_doi_tac_da_nhan(pool: asyncpg.Pool, *order_ids: str) -> None:
    """Bài kiểm BÀN đối tác (trạng thái, tệp, quyền) — không phải bài kiểm đường
    nhận việc: coi như các chỉ định đã sang bàn (24/09/2026, bàn chỉ hiện việc
    đã nhận qua sự kiện). Đường nhận thật: test_doi_tac_nhan_viec_db.py."""
    for oid in order_ids:
        await pool.execute(
            "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
            " SELECT clinic_id, id, 'BU_DU_LIEU' FROM service_order"
            " WHERE id = $1::uuid ON CONFLICT DO NOTHING",
            oid,
        )


def vong_doc_chay_ngay_sau_lenh_tep(monkeypatch: Any) -> None:
    """Bài kiểm luồng cũ: coi như worker chạy khối VÒNG ĐỌC ngay sau mỗi lệnh tệp.

    Từ 24/09/2026 tải / xác nhận / thu hồi tệp KHÔNG còn gọi thẳng khối Khám —
    khối VÒNG ĐỌC nghe sự kiện rồi mở / rút chỗ chờ đọc kết quả. Các bài kiểm
    viết trước đó khẳng định vòng đọc ngay sau lệnh; bọc lệnh để chạy một vòng
    người đưa tin (y như worker `--su-kien` làm mỗi giây ở máy thật).
    """
    from clinicai.events.catalogue import VONG_DOC
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    for ten in ("tai_len", "xac_nhan_tep", "thu_hoi_tep", "xoa_tep", "khoi_phuc_tep"):
        goc = getattr(TepKetQuaService, ten)

        async def boc(
            self: TepKetQuaService, *a: Any, _goc: Any = goc, **kw: Any
        ) -> Any:
            kq = await _goc(self, *a, **kw)
            await chay_ben_nhan(self._pool, VONG_DOC)
            return kq

        monkeypatch.setattr(TepKetQuaService, ten, boc)
