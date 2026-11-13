"""Cổng MÔ HÌNH — hợp đồng giữa trợ lý AI và bất kỳ nhà cung cấp LLM nào.

Cùng khuôn với `ports/pos.py` (ADR-0010): code nghiệp vụ chỉ biết `MoHinhPort`
và mấy dataclass dưới đây; adapter cụ thể nằm ở `clinicai.adapters.mo_hinh`,
chọn lúc chạy bằng chuỗi cấu hình (`anthropic:claude-haiku-5-5`,
`openai:…`, `ollama:qwen3`…). Đổi hãng = đổi chuỗi, không sửa bộ não.

Tin nhắn ở đây là dạng TRUNG LẬP. Mỗi hãng một cách xếp tool call / tool result
(Anthropic: khối `tool_use` + `tool_result` trong tin user; OpenAI: `tool_calls`
+ tin vai `tool`) — dịch là việc của adapter, không rò lên bộ não.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

VaiTin = Literal["khach", "tro_ly", "ket_qua_cong_cu"]


class MoHinhError(RuntimeError):
    """Gọi model không thành (mạng, khoá sai, hãng từ chối). Adapter ném cái này."""


@dataclass(frozen=True)
class CongCu:
    """Một công cụ model được gọi. ``ten`` chỉ gồm [a-zA-Z0-9_-] — cả Anthropic
    lẫn OpenAI đều từ chối dấu chấm."""

    ten: str
    mo_ta: str
    tham_so: dict[str, Any]  # JSON Schema kiểu object


@dataclass(frozen=True)
class GoiCongCu:
    ma: str
    ten: str
    tham_so: dict[str, Any]


@dataclass(frozen=True)
class Tin:
    vai: VaiTin
    noi_dung: str = ""
    goi_cong_cu: tuple[GoiCongCu, ...] = ()
    #: Chỉ cho vai `ket_qua_cong_cu`: mã lần gọi mà kết quả này trả lời.
    ma_goi: str = ""


@dataclass(frozen=True)
class KetQuaMoHinh:
    chu: str
    goi_cong_cu: tuple[GoiCongCu, ...] = ()
    model: str = ""
    token_vao: int = 0
    token_ra: int = 0
    thoi_gian_ms: int = 0
    lan_goi_id: str | None = None
    ly_do_dung: str | None = None
    them: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MoHinhPort(Protocol):
    #: "hãng:model" — in ra bảng chấm và nhật ký.
    ten: str

    async def tra_loi(
        self,
        *,
        he_thong: str,
        tin: Sequence[Tin],
        cong_cu: Sequence[CongCu] = (),
        max_tokens: int = 1024,
        tinh_nang: str = "tro_ly_khach",
    ) -> KetQuaMoHinh: ...

    async def dong(self) -> None: ...
