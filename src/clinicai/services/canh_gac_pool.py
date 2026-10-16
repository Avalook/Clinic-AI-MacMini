"""CANH GÁC BỂ KẾT NỐI API (14/10/2026) — bể đầy thì kêu, mỗi phút một dòng tổng hợp.

Phần ĐO nằm ở `core/quan_sat.py`; đây là vòng nền trong API (không phải trong
``su-kien``: bể cần đo là bể CỦA TIẾN TRÌNH API, nằm trong bộ nhớ API) làm ba việc:
  · mỗi giây đọc số kết nối bận; bể kín 2 giây liên tiếp → log ``pool_day``;
    bận cao (>= 80% trần) liên tiếp 10 giây → log ``pool_ban_keo_dai``;
  · mỗi phút chốt cửa sổ → MỘT dòng log ``api_nhip_phut`` (số request, p50/p95/max,
    request chậm, số lần chờ mượn kết nối, độ chờ lớn nhất…);
  · phút nào bể có dấu hiệu cạn → mở cảnh báo ``POOL_API_DAY`` qua đúng cơ chế
    của bộ canh gác (``canh_bao`` → /ops "Lỗi & cảnh báo" + Telegram ops nếu có).

VÌ SAO GHI CẢNH BÁO BẰNG BỂ RIÊNG MỘT KẾT NỐI. Lúc bể chính cạn là lúc cần ghi
cảnh báo nhất; ghi qua chính bể ấy thì cảnh báo xếp hàng sau đúng đám request
đang kẹt. Bể phụ ``min_size=0`` không mở kết nối cho tới lần ghi đầu tiên.

CHỐNG NHÁY: mở ngay phút đầu có dấu hiệu (cạn pool là sự cố thật, không cần
đợi), đóng sau 3 phút liên tiếp ổn.
Không bao giờ ném. Chỉ SỐ ĐẾM — không mã khách, không nội dung.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import asyncpg
import structlog

from clinicai.core.database import (
    COMMAND_TIMEOUT,
    SERVER_SETTINGS,
    normalize_dsn,
)
from clinicai.core.quan_sat import (
    NGUONG_BAN_LIEN_TIEP_GIAY,
    NGUONG_CHO_POOL_MS,
    quan_sat,
)
from clinicai.services.canh_gac import KetQuaKiem, ap_dung

logger = structlog.get_logger()

MA = "POOL_API_DAY"
NHIP_MAU_GIAY = 1.0
NHIP_PHUT_GIAY = 60.0
SO_PHUT_ON_DE_DONG = 3
#: Ghi cảnh báo qua bể phụ: quá hạn này thì bỏ lần ghi (lần sau thử lại).
HAN_GHI_CANH_BAO_GIAY = 10.0


def danh_gia_phut(tom: dict[str, Any]) -> tuple[bool, str]:
    """HÀM THUẦN: từ tổng hợp một phút → (có dấu hiệu cạn bể?, nội dung).

    Hai dấu hiệu, KHÔNG phụ thuộc "request chậm" (chậm vì SQL chậm không phải cạn
    bể): có lần mượn kết nối phải chờ >= 2 giây, hoặc bận cao liên tiếp >= 10 giây.
    """
    p = tom["pool"]
    ly_do: list[str] = []
    if p["so_cho_qua_2s"] > 0:
        ly_do.append(
            f"{p['so_cho_qua_2s']} lần mượn kết nối phải chờ quá "
            f"{NGUONG_CHO_POOL_MS / 1000:g} giây "
            f"(lâu nhất {p['cho_max_ms'] / 1000:.1f}s)"
        )
    if p["giay_ban_cao_lien_max"] >= NGUONG_BAN_LIEN_TIEP_GIAY:
        ly_do.append(
            f"bận cao liên tiếp {p['giay_ban_cao_lien_max']} giây "
            f"(tối đa {p['ban_max']}/{p['toi_da']} kết nối)"
        )
    if not ly_do:
        return False, "Bể kết nối API bình thường."
    return True, (
        "Bể kết nối API gần/đã đầy: "
        + "; ".join(ly_do)
        + f" · phút vừa rồi {tom['so_request']} request, p95 {tom['p95_ms']:.0f}ms"
        " — xem log `pool_cho_lau` / `api_nhip_phut` của container api."
    )


class ChongNhay:
    """Mở ngay khi có dấu hiệu; đóng sau `so_phut_on` phút ổn liên tiếp."""

    def __init__(self, so_phut_on: int = SO_PHUT_ON_DE_DONG) -> None:
        self.so_phut_on = so_phut_on
        self.on_lien = 0
        self.dang_mo = False

    def cap_nhat(self, co_dau_hieu: bool) -> bool | None:
        """True = mở/cộng dồn · False = đóng · None = giữ nguyên."""
        if co_dau_hieu:
            self.on_lien = 0
            self.dang_mo = True
            return True
        self.on_lien += 1
        if self.dang_mo and self.on_lien >= self.so_phut_on:
            self.dang_mo = False
            return False
        return None


def lay_mau(pool: asyncpg.Pool) -> None:
    """Một mẫu mỗi giây. Không ném."""
    try:
        toi_da = int(pool.get_max_size())
        ban = int(pool.get_size()) - int(pool.get_idle_size())
        su_kien = quan_sat.lay_mau_pool(ban, toi_da)
        if su_kien == "day":
            logger.warning(
                "pool_day",
                ban=ban,
                toi_da=toi_da,
                dang_cho=quan_sat.dang_cho(),
                ghi_chu="bể kết nối kín từ 2 giây liên tiếp",
            )
        elif su_kien == "ban_keo_dai":
            logger.warning(
                "pool_ban_keo_dai",
                ban=ban,
                toi_da=toi_da,
                dang_cho=quan_sat.dang_cho(),
                giay=NGUONG_BAN_LIEN_TIEP_GIAY,
            )
    except Exception:  # noqa: BLE001 — đo hỏng không được làm hỏng API
        logger.exception("canh_gac_pool_lay_mau_hong")


async def chot_phut(
    pool_canh_bao: asyncpg.Pool, chong: ChongNhay
) -> dict[str, Any] | None:
    """Chốt phút: một dòng log + mở/đóng cảnh báo. Không bao giờ ném."""
    try:
        tom = quan_sat.chot_phut()
        quan_sat.phut_gan_nhat = tom
        if tom["so_request"] or tom["pool"]["so_muon"]:
            logger.info("api_nhip_phut", **tom)
        co, noi_dung = danh_gia_phut(tom)
        quyet = chong.cap_nhat(co)
        if quyet is not None:
            await asyncio.wait_for(
                ap_dung(
                    pool_canh_bao,
                    [KetQuaKiem(MA, "warning", quyet, noi_dung)],
                ),
                timeout=HAN_GHI_CANH_BAO_GIAY,
            )
        return tom
    except Exception:  # noqa: BLE001 — kể cả TimeoutError của ghi cảnh báo
        logger.exception("canh_gac_pool_chot_phut_hong")
        return None


def bat() -> bool:
    return os.environ.get("CANH_GAC_POOL", "1").strip().lower() not in (
        "0",
        "false",
        "",
    )


async def chay_nen(pool: asyncpg.Pool) -> None:
    """Vòng nền trong API: mẫu mỗi giây, chốt mỗi phút. Huỷ khi tắt app."""
    pool_canh_bao: asyncpg.Pool | None = None
    try:
        try:
            pool_canh_bao = await asyncpg.create_pool(
                dsn=normalize_dsn(os.environ["DATABASE_URL"]),
                min_size=0,
                max_size=1,
                command_timeout=COMMAND_TIMEOUT,
                server_settings=SERVER_SETTINGS,
            )
        except Exception:  # noqa: BLE001
            logger.exception("canh_gac_pool_khong_tao_duoc_pool_canh_bao")
        logger.info(
            "canh_gac_pool_bat_dau",
            toi_da=int(pool.get_max_size()),
            toi_thieu=int(pool.get_min_size()),
        )
        chong = ChongNhay()
        han_phut = time.monotonic() + NHIP_PHUT_GIAY
        while True:
            await asyncio.sleep(NHIP_MAU_GIAY)
            lay_mau(pool)
            if time.monotonic() >= han_phut:
                han_phut += NHIP_PHUT_GIAY
                # Bể phụ không dựng được thì ghi bằng bể chính (còn hơn không ghi).
                await chot_phut(pool_canh_bao or pool, chong)
    finally:
        if pool_canh_bao is not None:
            await pool_canh_bao.close()
