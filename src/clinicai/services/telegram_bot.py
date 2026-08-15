"""Bot lệnh Telegram — người trực HỎI hệ thống, không chỉ nghe nó nói.

Nửa kia của kênh thông báo (Tuyền 15/08/2026: *"mọi thông tin về hệ thống
tích hợp vào bot"*). Relay đẩy tin sự kiện ra; module này nghe lệnh đi vào:

    /trangthai — khám sức khoẻ cả cụm: API (kèm database), dashboard, số sự
                 kiện đang chờ đưa tin. Gọi THẲNG endpoint /health trong mạng
                 compose — cùng nguồn mà Uptime Kuma theo dõi, nên hai bên
                 không bao giờ kể hai chuyện khác nhau.
    /homnay    — con số vận hành hôm nay: lịch còn sống, đã đến, khám xong,
                 huỷ. CHỈ CON SỐ — không tên, không SĐT: Telegram là bên thứ
                 ba (cùng luật với notification_templates).
    /giupdo    — danh sách lệnh.

AN NINH: chỉ trả lời đúng ``TELEGRAM_CHAT_ID`` đã cấu hình. Ai khác nhắn
với bot thì bị lờ đi và ghi log — bot đọc được con số vận hành của phòng
khám, không phải chỗ cho người lạ hỏi. Chữ người dùng gõ là DỮ LIỆU: chỉ so
khớp tên lệnh, không bao giờ đem đi thực thi.

Menu lệnh (setMyCommands) được đăng ký lại MỖI LẦN khởi động — bot này từng
nối một project cũ để lại menu rác; tự đăng ký lúc start thì menu luôn đúng
với code đang chạy, không phụ thuộc ai nhớ chạy lệnh tay.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

import asyncpg
import httpx
import structlog

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.providers.telegram import TELEGRAM_API

logger = structlog.get_logger()

# Long-poll getUpdates: Telegram giữ kết nối tới 25s nên vòng lặp này gần như
# realtime mà không quay tít.
POLL_TIMEOUT = 25

# Menu hiện khi người dùng bấm nút "/" — đăng ký lại mỗi lần start.
MENU_LENH = [
    {
        "command": "trangthai",
        "description": "Sức khoẻ hệ thống: API, database, dashboard",
    },
    {
        "command": "homnay",
        "description": "Con số hôm nay: lịch, đã đến, khám xong, huỷ",
    },
    {"command": "giupdo", "description": "Bot này làm được gì"},
]

# Endpoint nội bộ trong mạng compose — cùng nguồn Uptime Kuma theo dõi.
_HEALTH = {
    "API + database": "http://api:8000/health/db",
    "Dashboard": "http://dashboard:3000/health",
}


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_ids() -> set[str]:
    """TELEGRAM_CHAT_ID là danh sách phẩy — chat riêng + nhóm làm việc."""
    raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return {c.strip() for c in raw.split(",") if c.strip()}


def doc_lenh(text: str | None) -> str | None:
    """ "/trangthai@ten_bot arg" → "trangthai"; chữ thường không phải lệnh → None."""
    if not text or not text.startswith("/"):
        return None
    return text.split()[0][1:].split("@")[0].lower() or None


async def _kham_suc_khoe(pool: asyncpg.Pool, clinic_id: str) -> str:
    dong: list[str] = ["🩺 <b>Sức khoẻ hệ thống</b>"]
    # ĐI THEO CHUYỂN HƯỚNG + nhận cả họ 2xx — CÙNG LUẬT VỚI KUMA. Dashboard
    # /health trả 307 rồi mới tới 200; đo 15/08: Kuma nói Up trong khi bot
    # phán ❌ cùng một endpoint — hai người gác nói hai chuyện chỉ vì một
    # người không chịu bước qua cái biển chỉ đường.
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for ten, url in _HEALTH.items():
            try:
                r = await client.get(url)
                ok = r.is_success
            except httpx.HTTPError:
                ok = False
            dong.append(f"{'✅' if ok else '❌'} {ten}")
    try:
        async with pool.acquire() as conn:
            cho = await conn.fetchval(
                "SELECT count(*) FROM event_log "
                "WHERE clinic_id = $1::uuid AND event_published = FALSE",
                clinic_id,
            )
        dong.append(f"✅ Kênh thông báo — {cho} sự kiện đang chờ đưa tin")
    except Exception:
        dong.append("❌ Kênh thông báo — không đọc được hàng chờ")
    gio = datetime.now(CLINIC_TZ).strftime("%H:%M %d/%m")
    dong.append(f"<i>đo lúc {gio}</i>")
    return "\n".join(dong)


async def _con_so_hom_nay(pool: asyncpg.Pool, clinic_id: str) -> str:
    """Đếm theo NGÀY VN — cùng phép quy đổi múi giờ với mọi màn hình."""
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE status IN
                ('SCHEDULED','CSKH_CONFIRMED','CONFIRMED')) AS chua_den,
              count(*) FILTER (WHERE status = 'CHECKED_IN')  AS da_den,
              count(*) FILTER (WHERE status = 'COMPLETED')   AS kham_xong,
              count(*) FILTER (WHERE status = 'CANCELLED')   AS da_huy,
              count(*) FILTER (WHERE status = 'NO_SHOW')     AS khong_den
            FROM appointment
            WHERE clinic_id = $1::uuid
              AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                  = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
            """,
            clinic_id,
        )
    ngay = datetime.now(CLINIC_TZ).strftime("%d/%m")
    return (
        f"📊 <b>Hôm nay {ngay}</b>\n"
        f"🗓 Chờ đến: {r['chua_den']}\n"
        f"🏥 Đã đến (đang chờ khám): {r['da_den']}\n"
        f"✅ Khám xong: {r['kham_xong']}\n"
        f"❌ Huỷ: {r['da_huy']} · Không đến: {r['khong_den']}"
    )


def _giup_do() -> str:
    return (
        "🤖 <b>Theo dõi Clinic</b> — bot của hệ ClinicAI\n\n"
        "Tin tự động: 📅 lịch mới · ❌ huỷ · 🔁 đổi lịch · ⚠️ xoá ca bác sĩ\n\n"
        "Lệnh tra cứu:\n"
        "/trangthai — sức khoẻ API, database, dashboard\n"
        "/homnay — con số lịch hẹn hôm nay\n\n"
        "Bot không bao giờ gửi tên đầy đủ kèm SĐT khách — tra chi tiết thì "
        "vào hệ thống."
    )


async def _tra_loi(pool: asyncpg.Pool, clinic_id: str, lenh: str) -> str | None:
    if lenh == "trangthai":
        return await _kham_suc_khoe(pool, clinic_id)
    if lenh == "homnay":
        return await _con_so_hom_nay(pool, clinic_id)
    if lenh in ("giupdo", "start", "help", "commands"):
        return _giup_do()
    return None  # lệnh lạ: im lặng — menu đã kể đủ những gì bot biết


async def _gui(client: httpx.AsyncClient, chat_id: str, text: str) -> None:
    # Trả lời về ĐÚNG kênh vừa hỏi — hỏi trong nhóm mà đáp vào chat riêng
    # thì cả nhóm tưởng bot chết.
    await client.post(
        f"{TELEGRAM_API}/bot{_token()}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


async def _dang_ky_menu(client: httpx.AsyncClient) -> None:
    """Ghi đè menu lệnh — dọn rác của project cũ, tự lành sau mỗi lần deploy."""
    r = await client.post(
        f"{TELEGRAM_API}/bot{_token()}/setMyCommands",
        json={"commands": MENU_LENH},
    )
    logger.info("bot_menu_registered", ok=r.status_code == 200)


async def _offset_bo_ton_dong(client: httpx.AsyncClient) -> int:
    """Bỏ qua lệnh gõ TRƯỚC khi bot khởi động — trả lời một câu hỏi của hôm
    qua bằng số liệu hôm nay là đưa tin sai mà không ai biết."""
    r = await client.get(
        f"{TELEGRAM_API}/bot{_token()}/getUpdates", params={"timeout": 0}
    )
    ket = r.json().get("result", []) if r.status_code == 200 else []
    return (ket[-1]["update_id"] + 1) if ket else 0


async def bot_lenh_loop(
    pool: asyncpg.Pool, clinic_id: str, stop: asyncio.Event
) -> None:
    """Vòng nghe lệnh — chạy song song với vòng relay trong cùng process."""
    if not _token() or not _chat_ids():
        logger.info("bot_lenh_skipped", reason="thiếu TELEGRAM_BOT_TOKEN/CHAT_ID")
        return
    kenh_duoc_phep = _chat_ids()
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10) as client:
        await _dang_ky_menu(client)
        offset = await _offset_bo_ton_dong(client)
        logger.info("bot_lenh_started")
        while not stop.is_set():
            try:
                r = await client.get(
                    f"{TELEGRAM_API}/bot{_token()}/getUpdates",
                    params={"timeout": POLL_TIMEOUT, "offset": offset},
                )
                if r.status_code != 200:
                    await asyncio.sleep(5)
                    continue
                for u in r.json().get("result", []):
                    offset = u["update_id"] + 1
                    msg: dict[str, Any] = u.get("message") or {}
                    chat = str((msg.get("chat") or {}).get("id", ""))
                    if chat not in kenh_duoc_phep:
                        # Người lạ nhắn với bot: lờ đi, chỉ ghi vết.
                        logger.warning("bot_lenh_nguoi_la", chat_id=chat)
                        continue
                    lenh = doc_lenh(msg.get("text"))
                    if lenh is None:
                        continue
                    tra_loi = await _tra_loi(pool, clinic_id, lenh)
                    if tra_loi:
                        await _gui(client, chat, tra_loi)
            except httpx.HTTPError:
                await asyncio.sleep(5)
            except Exception:
                logger.exception("bot_lenh_error")
                await asyncio.sleep(5)
    logger.info("bot_lenh_stopped")
