"""Tiến trình `worker --drive` (dịch vụ `drive-xn`, chặng 4 bàn XN + Gmail G2).

Mỗi `drive.NHIP_GIAY` (180s) một lượt `drive.mot_vong` rồi `gmail.mot_vong` (kết quả
đối tác về Gmail phòng khám; không có khoá Gmail ⇒ bỏ qua) — không bao giờ ném (mỗi đối
tác bọc riêng, lỗi ghi `drive_nhip`). Chỉ MỘT tiến trình quét: khoá tư vấn cấp phiên
trên một kết nối giữ riêng; kết nối rớt ⇒ bỏ khoá đang tưởng có, lượt sau xin lại.
Không có khoá Drive (`GOOGLE_DRIVE_SA_FILE` rỗng) ⇒ lượt nào cũng bỏ qua, nhịp tim
vẫn đập (dev/CI). Tách khỏi `worker.py` (đã quá trần kích thước).
"""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable

import structlog

from clinicai.services.xet_nghiem import drive, drive_api, gmail, gmail_api

logger = structlog.get_logger()


async def chay(beat: Callable[[], None]) -> None:
    from clinicai.core.database import close_pool, create_pool

    pool = await create_pool()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    giu = await pool.acquire()
    logger.info(
        "drive_started",
        nhip=drive.NHIP_GIAY,
        co_khoa=drive_api.co_cau_hinh(),
        co_gmail=gmail_api.co_cau_hinh(),
    )
    co_khoa = False
    try:
        while not stop.is_set():
            try:
                if not co_khoa:
                    co_khoa = bool(
                        await giu.fetchval(
                            "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
                            drive.KHOA_MOT_TIEN_TRINH,
                        )
                    )
                    if not co_khoa:
                        logger.warning("drive_tien_trinh_khac_dang_giu_khoa")
                if co_khoa:
                    ket = await drive.mot_vong(pool)
                    if ket.get("tep_moi") or ket.get("loi"):
                        logger.info("drive_vong", **ket)
                    # Gmail (G2): cùng tiến trình, cùng khoá; không bao giờ ném.
                    ket = await gmail.mot_vong(pool)
                    if ket.get("tep_moi") or ket.get("loi"):
                        logger.info("gmail_vong", **ket)
                beat()
            except Exception:
                # Mất kết nối giữ khoá ⇒ khoá phiên đã mất cùng nó: xin lại lượt sau.
                co_khoa = False
                logger.exception("drive_vong_loi")
            try:
                await asyncio.wait_for(stop.wait(), timeout=drive.NHIP_GIAY)
                break
            except TimeoutError:
                continue
    finally:
        try:
            await pool.release(giu)
        except Exception:  # noqa: BLE001 — đang tắt, không còn gì để làm
            pass
        await close_pool(pool)
        logger.info("drive_stopped")
