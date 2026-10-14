"""Asyncpg connection pool lifecycle + FastAPI dependency."""

import asyncio
import os
from typing import AsyncGenerator

import asyncpg
import structlog
from fastapi import Request

logger = structlog.get_logger()

# App giữ sẵn tối thiểu 2, tối đa POOL_MAX_SIZE kết nối tới Postgres.
POOL_MIN_SIZE = 2


def doc_pool_max(raw: str | None) -> int:
    """Trần bể kết nối từ biến môi trường `DB_POOL_MAX`; rác / ngoài 5–40 → 20.

    Hàm thuần, không ném: một giá trị gõ sai không được làm API không khởi động
    được. 20 (14/10/2026, nâng từ 10): tối 12/10 số request chờ cùng lúc vọt lên
    hơn 270 và cả route nhẹ `/api/thong-bao` treo 18s — nghi bể 10 kết nối bị vài
    truy vấn nặng giữ hết (xem `be_ket_noi_dang_ban`). Postgres cho 100 kết nối,
    prod đang dùng ~24; API + su-kien (mỗi tiến trình một bể) + PostgREST +
    realtime + auth vẫn dưới ~65 ở mức cao nhất.
    """
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return 20
    return n if 5 <= n <= 40 else 20


# Request mượn kết nối từ bể rồi trả lại, không mở/đóng mỗi lần.
POOL_MAX_SIZE = doc_pool_max(os.environ.get("DB_POOL_MAX"))
# Mỗi câu SQL quá 15 giây sẽ bị huỷ, tránh truy vấn chạy mãi.
COMMAND_TIMEOUT = 15
STARTUP_RETRIES = 3
STARTUP_BACKOFF = 2.0  # seconds between retries

#: JIT TẮT cho mọi kết nối của ứng dụng. Ở quy mô này (bảng vài chục nghìn dòng,
#: truy vấn chạy vài chục ms) JIT không bao giờ nhanh hơn — nó chỉ tốn thêm: đo
#: 09/10/2026, câu bảng thu ngân chạy thật ~80ms nhưng LLVM biên dịch ~3,1s mỗi
#: lần (prod trung bình 4,8s, đỉnh 14s), và ba lần biên dịch song song đẩy DB
#: staging (trần 384MiB) tới OOM. Đặt ở đây, không ở `command:` của Postgres, để
#: prod, staging, CI và máy dev cùng một hành vi.
SERVER_SETTINGS = {"jit": "off"}


def thong_ke_be(pool: object) -> dict[str, int] | None:
    """Số đo bể kết nối: tổng, đang rảnh, đang bận, trần. Không có bể → None.

    Chỉ đọc bộ đếm trong bộ nhớ của asyncpg (không chạm DB), nên gọi trên mọi
    request cũng không tốn.
    """
    try:
        tong = int(pool.get_size())  # type: ignore[attr-defined]
        ranh = int(pool.get_idle_size())  # type: ignore[attr-defined]
        tran = int(pool.get_max_size())  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None
    return {"tong": tong, "ranh": ranh, "ban": max(0, tong - ranh), "tran": tran}


def be_ket_noi_dang_ban(pool: object) -> bool:
    """Bể còn chưa tới 2 kết nối rảnh — request kế tiếp sắp phải xếp hàng.

    "Bận" tính theo trần chứ không theo số đã mở: bể mở lười (2 → trần), nên
    `ranh == 0` khi mới mở 2/20 không phải là đầy.
    """
    tk = thong_ke_be(pool)
    return tk is not None and tk["tran"] - tk["ban"] <= 1


def normalize_dsn(dsn: str) -> str:
    """Strip SQLAlchemy-style '+asyncpg' driver suffix; asyncpg needs bare scheme.

    CÔNG KHAI vì có hai nơi mở kết nối, không phải một. Bể kết nối dùng nó từ
    đầu; bộ nghe LISTEN (change_broker) mở một kết nối RIÊNG và lúc đầu đọc
    thẳng DATABASE_URL — nên nó chết ngay khi khởi động với `invalid DSN: scheme
    is expected to be either "postgres"…`, vì .env của phòng khám dùng dạng
    `postgresql+asyncpg://`. Một hàm chuẩn hoá mà chỉ một trong hai chỗ gọi thì
    chưa phải chuẩn hoá.
    """
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


#: Tên cũ, giữ cho các chỗ gọi nội bộ đã có.
_normalize_dsn = normalize_dsn


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg connection pool from DATABASE_URL env var.

    Retries up to STARTUP_RETRIES times with backoff if Supabase is
    temporarily unreachable during container boot (avoids crash loop).
    """
    dsn = _normalize_dsn(os.environ["DATABASE_URL"])
    last_error: Exception | None = None

    for attempt in range(1, STARTUP_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                command_timeout=COMMAND_TIMEOUT,
                server_settings=SERVER_SETTINGS,
            )
            logger.info(
                "DB pool ready",
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                command_timeout=COMMAND_TIMEOUT,
                attempt=attempt,
            )
            return pool
        except (asyncpg.PostgresConnectionError, OSError) as exc:
            last_error = exc
            logger.warning(
                "db_pool_connect_retry",
                attempt=attempt,
                max_retries=STARTUP_RETRIES,
                error=str(exc),
            )
            if attempt < STARTUP_RETRIES:
                await asyncio.sleep(STARTUP_BACKOFF * attempt)

    # All retries exhausted — raise so the container exits (Docker restarts it).
    raise RuntimeError(
        f"Failed to create DB pool after {STARTUP_RETRIES} attempts"
    ) from last_error


async def close_pool(pool: asyncpg.Pool) -> None:
    """Close the asyncpg connection pool."""
    await pool.close()
    logger.info("DB pool closed")


async def get_db_pool(request: Request) -> AsyncGenerator[asyncpg.Pool, None]:
    """FastAPI dependency that yields the application's asyncpg pool."""
    yield request.app.state.db_pool
