"""Asyncpg connection pool lifecycle + FastAPI dependency."""

import asyncio
import os
from typing import AsyncGenerator

import asyncpg
import structlog
from fastapi import Request

logger = structlog.get_logger()

# App giữ sẵn tối thiểu 2 kết nối tới Postgres.
POOL_MIN_SIZE = 2
# Request mượn kết nối từ bể rồi trả lại, không mở/đóng mỗi lần.
#
# API: mặc định 20, đặt lại bằng biến môi trường `POOL_MAX_SIZE` (14/10/2026,
# nâng từ 10 sau sự cố tối 12/10 nghi cạn bể — một tiến trình uvicorn, 14 req/s,
# nhiều request giữ kết nối hàng trăm ms). Bể chỉ mở thêm kết nối khi có người
# chờ nên trần cao không tốn gì lúc rảnh. NGÂN SÁCH KẾT NỐI Postgres
# (max_connections=100; staging 60) — API này + checkpointer 10 + broker 1 +
# GoTrue 10 + PostgREST 10 + Realtime ~10 + su-kien/day-tep + quản trị — tính
# trong thân PR; đổi số này phải tính lại. Staging ghim 10 ở docker-compose.staging.yml.
POOL_MAX_SIZE = 20
# Các worker (su-kien, day-tep, relay…) làm việc tuần tự, dùng 1–3 kết nối:
# giữ trần cũ 10, không theo biến của API (cùng env_file nên biến ấy cũng hiện
# trong container của chúng).
WORKER_POOL_MAX_SIZE = 10
#: Giá trị `POOL_MAX_SIZE` ngoài khoảng này bị coi là gõ nhầm → dùng mặc định.
POOL_MAX_SIZE_KHOANG = (2, 60)
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


def doc_pool_max_size_api(env: str | None = None) -> int:
    """Trần kết nối của API: biến môi trường `POOL_MAX_SIZE`, không có thì mặc định 20.

    Rỗng / không phải số / ngoài `POOL_MAX_SIZE_KHOANG` → mặc định, kèm một dòng
    cảnh báo. Không ném: gõ nhầm biến môi trường không được làm API không dậy nổi.
    """
    tho = os.environ.get("POOL_MAX_SIZE", "") if env is None else env
    tho = tho.strip()
    if not tho:
        return POOL_MAX_SIZE
    lo, hi = POOL_MAX_SIZE_KHOANG
    try:
        so = int(tho)
    except ValueError:
        so = -1
    if not lo <= so <= hi:
        logger.warning(
            "pool_max_size_khong_hop_le", gia_tri=tho[:20], dung_mac_dinh=POOL_MAX_SIZE
        )
        return POOL_MAX_SIZE
    return so


async def create_pool(max_size: int | None = None) -> asyncpg.Pool:
    """Create the asyncpg connection pool from DATABASE_URL env var.

    `max_size` None = trần của worker (`WORKER_POOL_MAX_SIZE`); API truyền
    `doc_pool_max_size_api()`.

    Retries up to STARTUP_RETRIES times with backoff if Supabase is
    temporarily unreachable during container boot (avoids crash loop).
    """
    max_size = WORKER_POOL_MAX_SIZE if max_size is None else max_size
    dsn = _normalize_dsn(os.environ["DATABASE_URL"])
    last_error: Exception | None = None

    for attempt in range(1, STARTUP_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=POOL_MIN_SIZE,
                max_size=max_size,
                command_timeout=COMMAND_TIMEOUT,
                server_settings=SERVER_SETTINGS,
            )
            logger.info(
                "DB pool ready",
                min_size=POOL_MIN_SIZE,
                max_size=max_size,
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
