"""Người đưa tin: lấy dòng `event_delivery` chưa xong và giao cho bên nhận.

BỐN THỨ PHẢI ĐÚNG, mỗi thứ vá một kiểu hỏng đã có thật ở hệ khác:

1. NHẬN VIỆC CÓ HẠN (lease). Worker chết giữa chừng thì dòng việc phải quay lại
   hàng đợi, không nằm `IN_PROGRESS` vĩnh viễn. SQS gọi là visibility timeout,
   Camunda gọi là job timeout; ở đây là `lease_expires_at` + `thu_hoi_thue()`.

2. ĐÚNG THỨ TỰ TRONG CÙNG MỘT ĐỐI TƯỢNG. `FOR UPDATE SKIP LOCKED` cho phép hai
   worker chạy song song, và một lần thử lại đẩy sự kiện N xuống sau N+1. Nếu để
   nguyên thì màn hành trình vẽ "đã bắt đầu làm" trước "đã xếp phòng". Nên một
   dòng chỉ được nhận khi mọi sự kiện CŨ HƠN của cùng đối tượng đã DONE.

3. GHI XONG VÀ ĐÁNH DẤU XONG TRONG CÙNG MỘT GIAO DỊCH. Nếu đánh dấu DONE ở giao
   dịch khác, tiến trình chết giữa hai cái là lần sau làm lại từ đầu — với bên
   nhận chỉ ghi DB thì vô hại, nhưng chỉ khi hai việc đi chung một commit.

4. HỎNG THÌ PHẢI THẤY. Thử lại có giãn cách tăng dần và có nhiễu, tối đa 5 lần,
   rồi vào DEAD. Dòng DEAD KHÔNG bị xoá và hiện ở `v_event_delivery_suc_khoe` —
   im lặng nuốt sự kiện là kiểu hỏng tệ nhất.

GIỚI HẠN ĐÃ BIẾT: một dòng DEAD CHẶN các sự kiện sau của cùng đối tượng (luật 2).
Đó là chủ ý — thà dừng đúng chỗ còn hơn vẽ sai thứ tự — nhưng nghĩa là DEAD phải
có người xử lý, không phải để đó.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

SO_LAN_THU_TOI_DA = 5
GIAN_CACH_GOC_GIAY = 2
GIAN_CACH_TOI_DA_GIAY = 300
HAN_THUE_GIAY = 120


@dataclass(frozen=True)
class SuKienDaNhan:
    """Một sự kiện đã lấy được, kèm dòng giao của chính bên nhận này."""

    event_id: str
    event_type: str
    clinic_id: str
    aggregate_id: str
    aggregate_version: int | None
    occurred_at: Any
    #: Số thứ tự ghi vào sổ — mốc xếp thứ tự khi giờ bằng nhau.
    seq: int
    actor_type: str
    actor_staff_id: str | None
    payload: dict[str, Any]
    replay_id: str | None
    attempts: int

    @property
    def la_phat_lai(self) -> bool:
        """Phát lại/nhập lịch sử: cấm gửi thông báo ra ngoài."""
        return self.replay_id is not None


# Bên nhận nhận connection của chính giao dịch đang đánh dấu DONE.
BoXuLy = Callable[[asyncpg.Connection, SuKienDaNhan], Awaitable[None]]

_BO_XU_LY: dict[str, BoXuLy] = {}


def dang_ky(consumer: str, xu_ly: BoXuLy) -> None:
    """Khai một bên nhận. Tên phải trùng tên khai trong danh mục sự kiện."""
    _BO_XU_LY[consumer] = xu_ly


def bo_xu_ly(consumer: str) -> BoXuLy:
    try:
        return _BO_XU_LY[consumer]
    except KeyError:
        raise ValueError(
            f"Bên nhận '{consumer}' chưa đăng ký (clinicai.events.worker.dang_ky)."
        ) from None


_NHAN_MOT_DONG = """
WITH ung_vien AS (
    SELECT d.event_id
    FROM event_delivery d
    WHERE d.consumer = $1
      AND d.status IN ('PENDING', 'RETRY')
      AND d.next_attempt_at <= now()
      -- Luật 2: còn sự kiện cũ hơn của cùng đối tượng chưa xong thì chờ.
      AND NOT EXISTS (
          SELECT 1 FROM event_delivery truoc
          WHERE truoc.consumer = d.consumer
            AND truoc.aggregate_id = d.aggregate_id
            AND truoc.status <> 'DONE'
            AND truoc.aggregate_version IS NOT NULL
            AND d.aggregate_version IS NOT NULL
            AND truoc.aggregate_version < d.aggregate_version
      )
    ORDER BY d.next_attempt_at, d.aggregate_version NULLS FIRST
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE event_delivery d
SET status = 'IN_PROGRESS',
    attempts = d.attempts + 1,
    lease_expires_at = now() + make_interval(secs => $3),
    locked_by = $2
FROM ung_vien, domain_event e
WHERE d.event_id = ung_vien.event_id
  AND d.consumer = $1
  AND e.event_id = d.event_id
RETURNING d.event_id::text, e.event_type, d.clinic_id::text,
          d.aggregate_id::text, d.aggregate_version, e.occurred_at, e.seq,
          e.actor_type, e.actor_staff_id::text, e.payload, e.replay_id::text,
          d.attempts
"""


def _gian_cach(lan_thu: int) -> float:
    """Chờ tăng dần có nhiễu — nhiều worker cùng hỏng thì không dội cùng lúc."""
    cho = min(GIAN_CACH_GOC_GIAY * (2 ** max(lan_thu - 1, 0)), GIAN_CACH_TOI_DA_GIAY)
    return float(cho * random.uniform(0.9, 1.1))


async def lam_mot_dong(
    pool: asyncpg.Pool, consumer: str, *, ten_worker: str = "worker"
) -> bool:
    """Lấy và xử lý đúng một dòng. Trả về False khi hàng đợi rỗng."""
    xu_ly = bo_xu_ly(consumer)

    async with pool.acquire() as conn, conn.transaction():
        dong = await conn.fetchrow(
            _NHAN_MOT_DONG, consumer, ten_worker, float(HAN_THUE_GIAY)
        )
        if dong is None:
            return False

        su_kien = SuKienDaNhan(
            event_id=dong["event_id"],
            event_type=dong["event_type"],
            clinic_id=dong["clinic_id"],
            aggregate_id=dong["aggregate_id"],
            aggregate_version=dong["aggregate_version"],
            occurred_at=dong["occurred_at"],
            seq=int(dong["seq"]),
            actor_type=dong["actor_type"],
            actor_staff_id=dong["actor_staff_id"],
            payload=json.loads(dong["payload"]),
            replay_id=dong["replay_id"],
            attempts=dong["attempts"],
        )

    # Việc của bên nhận và việc đánh dấu DONE đi chung một giao dịch (luật 3).
    try:
        async with pool.acquire() as conn, conn.transaction():
            await xu_ly(conn, su_kien)
            await conn.execute(
                "UPDATE event_delivery SET status = 'DONE', processed_at = now(),"
                " lease_expires_at = NULL, locked_by = NULL, last_error = NULL"
                " WHERE event_id = $1::uuid AND consumer = $2",
                su_kien.event_id,
                consumer,
            )
    except Exception as loi:  # noqa: BLE001 — mọi lỗi đều phải thành RETRY/DEAD
        het_luot = su_kien.attempts >= SO_LAN_THU_TOI_DA
        await pool.execute(
            "UPDATE event_delivery"
            " SET status = $3, next_attempt_at = now() + make_interval(secs => $4),"
            "     lease_expires_at = NULL, locked_by = NULL, last_error = $5"
            " WHERE event_id = $1::uuid AND consumer = $2",
            su_kien.event_id,
            consumer,
            "DEAD" if het_luot else "RETRY",
            0.0 if het_luot else _gian_cach(su_kien.attempts),
            str(loi)[:2000],
        )
        logger.warning(
            "event_delivery_hong",
            consumer=consumer,
            event_id=su_kien.event_id,
            event_type=su_kien.event_type,
            lan_thu=su_kien.attempts,
            chet=het_luot,
            loi=str(loi)[:200],
        )
        return True

    return True


async def thu_hoi_thue(pool: asyncpg.Pool) -> int:
    """Trả về hàng đợi những dòng bị worker chết bỏ dở. Trả về số dòng thu hồi."""
    thu_hoi = await pool.fetchval(
        "WITH qua_han AS ("
        "  UPDATE event_delivery SET status = 'RETRY', next_attempt_at = now(),"
        "         lease_expires_at = NULL, locked_by = NULL,"
        "         last_error = 'worker bo do, thu hoi thue'"
        "  WHERE status = 'IN_PROGRESS' AND lease_expires_at < now()"
        "  RETURNING 1) SELECT count(*) FROM qua_han"
    )
    return int(thu_hoi or 0)


async def chay_vong(
    pool: asyncpg.Pool,
    consumer: str,
    *,
    ten_worker: str = "worker",
    nghi_khi_rong_giay: float = 1.0,
) -> None:
    """Vòng chạy mãi: làm hết hàng đợi thì nghỉ một nhịp rồi xem lại."""
    while True:
        try:
            await thu_hoi_thue(pool)
            con_viec = True
            while con_viec:
                con_viec = await lam_mot_dong(pool, consumer, ten_worker=ten_worker)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — vòng chạy không được phép chết
            logger.exception("vong_giao_tin_hong", consumer=consumer)
        await asyncio.sleep(nghi_khi_rong_giay)


__all__ = [
    "HAN_THUE_GIAY",
    "SO_LAN_THU_TOI_DA",
    "BoXuLy",
    "SuKienDaNhan",
    "bo_xu_ly",
    "chay_vong",
    "dang_ky",
    "lam_mot_dong",
    "thu_hoi_thue",
]
