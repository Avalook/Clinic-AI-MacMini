"""Nghe thay đổi từ Postgres bằng LISTEN/NOTIFY, phát lại cho các màn đang mở.

VÌ SAO KHÔNG DÙNG REALTIME CỦA SUPABASE NỮA.

Realtime đọc nhật ký WAL qua một *replication slot*, và tạo slot cần quyền
REPLICATION. Database cho thuê không cấp quyền đó — đã đo trên Viettel IDC
06/08/2026: `pg_create_logical_replication_slot` bị từ chối. Không phải trục
trặc cấu hình, là chính sách, và AWS RDS hay Azure cũng vậy.

`LISTEN`/`NOTIFY` thì là SQL thường: KHÔNG đòi quyền nào. Nó chạy trên database
cho thuê, trên Postgres tự cài, ở đâu cũng được — nên chọn nó là bỏ được một
ràng buộc về nhà cung cấp, không phải một mẹo lách.

VÀ NÓ ĐI ÍT CHẶNG HƠN. Đường cũ: ghi → WAL → dịch vụ Realtime giải mã →
websocket. Đường này: ghi → NOTIFY (bắn đúng lúc COMMIT) → SSE. Thứ đang ghi dữ
liệu chính là thứ biết có gì đổi; bản cũ để nó im lặng rồi cử một dịch vụ khác
đi đọc lại nhật ký để đoán ra điều đó.

NHIỀU BẢN API CHẠY SONG SONG VẪN ĐÚNG. NOTIFY phát tới MỌI kết nối đang LISTEN,
nên mỗi bản API tự nhận và tự phát cho màn hình nối vào nó. Không cần thêm
RabbitMQ hay Redis ở giữa — khác với cách đẩy tin trong bộ nhớ của một tiến
trình, thứ chỉ đúng khi có đúng một bản.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

#: Tên kênh, phải khớp hàm trigger trong migration.
CHANNEL = "clinicai_changes"

#: Hàng đợi mỗi màn hình. NHỎ CÓ CHỦ Ý: nội dung mỗi tin không quan trọng, màn
#: hình chỉ cần biết "có gì đó đổi" rồi tự đọc lại. Đầy thì bỏ tin mới — một
#: màn hình chậm không được phép làm nghẽn các màn khác, và bỏ tin ở đây vô hại
#: vì tin sau cũng nói đúng điều ấy.
QUEUE_SIZE = 8

#: Nối lại sau bao lâu khi kết nối nghe bị rớt.
RECONNECT_DELAY_S = 3.0


class ChangeBroker:
    """Một kết nối LISTEN, phát lại cho nhiều màn hình."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: asyncpg.Connection | None = None
        self._task: asyncio.Task[None] | None = None
        # clinic_id → các hàng đợi đang mở của phòng khám đó.
        self._subs: dict[str, set[asyncio.Queue[str]]] = {}
        self._stopping = False

    # -- vòng đời ----------------------------------------------------------
    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="change-broker")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._conn is not None and not self._conn.is_closed():
            await self._conn.close()
        self._conn = None

    async def _run(self) -> None:
        """Giữ một kết nối LISTEN, tự nối lại khi rớt.

        KẾT NỐI RIÊNG, KHÔNG LẤY TỪ BỂ CHUNG. Một kết nối đang LISTEN bị giữ
        suốt đời tiến trình; mượn nó từ bể là vĩnh viễn bớt một chỗ của những
        truy vấn thật, và asyncpg cũng không hứa trả lại đúng kết nối ấy.
        """
        while not self._stopping:
            try:
                self._conn = await asyncpg.connect(self._dsn)
                await self._conn.add_listener(CHANNEL, self._on_notify)
                logger.info("change_broker_listening", channel=CHANNEL)
                # Ngồi im cho tới khi bị huỷ hoặc kết nối chết.
                while not self._stopping and not self._conn.is_closed():
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # Database khởi động lại, mạng chớp — không được làm chết API.
                # Màn hình vẫn có nhịp làm mới dự phòng của riêng nó.
                logger.warning("change_broker_lost", error=str(exc))
            finally:
                if self._conn is not None and not self._conn.is_closed():
                    await self._conn.close()
                self._conn = None
            if not self._stopping:
                await asyncio.sleep(RECONNECT_DELAY_S)

    # -- nhận và phát ------------------------------------------------------
    def _on_notify(
        self, _conn: object, _pid: int, _channel: str, payload: str
    ) -> None:
        """asyncpg gọi hàm này ĐỒNG BỘ trên event loop.

        Nên ở đây không được `await` gì cả, và không được để một màn hình chậm
        giữ chân cả tiến trình — vì thế dùng put_nowait rồi bỏ qua khi đầy.
        """
        try:
            data: dict[str, Any] = json.loads(payload)
            clinic_id = str(data.get("c") or "")
        except (ValueError, TypeError):
            logger.warning("change_broker_bad_payload", payload=payload[:200])
            return
        if not clinic_id:
            return
        for q in self._subs.get(clinic_id, ()):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    # -- đăng ký -----------------------------------------------------------
    def subscribe(self, clinic_id: str) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subs.setdefault(clinic_id, set()).add(q)
        return q

    def unsubscribe(self, clinic_id: str, q: asyncio.Queue[str]) -> None:
        bucket = self._subs.get(clinic_id)
        if not bucket:
            return
        bucket.discard(q)
        if not bucket:
            self._subs.pop(clinic_id, None)

    @property
    def listener_count(self) -> int:
        return sum(len(v) for v in self._subs.values())
