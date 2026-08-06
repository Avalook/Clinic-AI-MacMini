"""Dòng sự kiện cho màn hình — thay chỗ của Supabase Realtime.

SSE CHỨ KHÔNG PHẢI WEBSOCKET. Việc cần làm ở đây là một chiều: máy chủ báo
"có gì đó vừa đổi", trình duyệt đọc lại. Không có chiều ngược. SSE đi trên HTTP
thường nên qua được Caddy và mọi proxy mà không cần cấu hình nâng cấp giao
thức, tự nối lại khi rớt (trình duyệt lo, không phải mình viết), và nhẹ hơn.
WebSocket là công cụ cho hội thoại hai chiều — dùng ở đây là trả giá cho một
chiều mình không dùng.

NỘI DUNG TIN CỐ Ý NGHÈO. Chỉ có tên bảng vừa đổi, không kèm dữ liệu. Hai lý do:
gửi dữ liệu qua đây là mở một đường đọc thứ hai nằm ngoài mọi lớp kiểm quyền
của API; và màn hình vốn đã đọc lại toàn trang, nên dữ liệu gửi kèm cũng không
ai dùng.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from clinicai.api.identity import StaffIdentity, get_current_identity

router = APIRouter()

#: Nhịp giữ nhịp. Proxy và cân bằng tải hay tự cắt một kết nối im lặng sau
#: 30–60 giây; một dòng bình luận rỗng đủ để giữ, và tốn vài byte.
HEARTBEAT_S = 20.0


@router.get("/events/stream")
async def stream(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
) -> StreamingResponse:
    """Đẩy một tin mỗi khi có thay đổi thuộc phòng khám của người đang xem."""
    broker = getattr(request.app.state, "change_broker", None)

    async def gen() -> AsyncIterator[bytes]:
        # Báo mở dòng ngay, trước khi có tin đầu tiên: trình duyệt biết kết nối
        # đã sống, và proxy nào đệm sẵn đầu ra cũng được đẩy đi.
        yield b": mo dong\n\n"

        if broker is None:
            # Không có bộ nhận tin (chưa bật, hoặc đang khởi động lại) thì đóng
            # luôn cho trình duyệt rơi về nhịp làm mới dự phòng của nó — im
            # lặng giữ một dòng chết là cách tệ hơn.
            return

        q = broker.subscribe(identity.clinic_id)
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)
                except TimeoutError:
                    yield b": nhip\n\n"
                    continue
                yield b"event: change\ndata: " + payload.encode() + b"\n\n"
        finally:
            broker.unsubscribe(identity.clinic_id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # Tắt đệm của nginx/Caddy — đệm một dòng sự kiện là biến thứ tức
            # thời thành thứ đến theo lô.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
