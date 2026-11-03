"""Adapter Claude — bọc `AnthropicClient` có sẵn (retry, ghi `llm_lan_goi`,
trần tiền ngày) và dịch tin trung lập sang khối `tool_use` / `tool_result`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.ports.mo_hinh import CongCu, GoiCongCu, KetQuaMoHinh, MoHinhError, Tin


def dich_tin(tin: Sequence[Tin]) -> list[dict[str, Any]]:
    """Kết quả công cụ liền nhau phải gom vào MỘT tin user — API trả 400 nếu
    tách ra (mỗi tool_use của lượt trước cần tool_result ở ngay tin sau)."""
    ra: list[dict[str, Any]] = []
    for t in tin:
        if t.vai == "khach":
            ra.append({"role": "user", "content": t.noi_dung})
        elif t.vai == "tro_ly":
            khoi: list[dict[str, Any]] = []
            if t.noi_dung:
                khoi.append({"type": "text", "text": t.noi_dung})
            for g in t.goi_cong_cu:
                khoi.append(
                    {"type": "tool_use", "id": g.ma, "name": g.ten, "input": g.tham_so}
                )
            ra.append({"role": "assistant", "content": khoi or t.noi_dung})
        else:
            kq = {"type": "tool_result", "tool_use_id": t.ma_goi, "content": t.noi_dung}
            truoc = ra[-1] if ra else None
            if (
                truoc
                and truoc["role"] == "user"
                and isinstance(truoc["content"], list)
                and truoc["content"]
                and truoc["content"][0].get("type") == "tool_result"
            ):
                truoc["content"].append(kq)
            else:
                ra.append({"role": "user", "content": [kq]})
    return ra


def dich_cong_cu(cong_cu: Sequence[CongCu]) -> list[dict[str, Any]]:
    return [
        {"name": c.ten, "description": c.mo_ta, "input_schema": c.tham_so}
        for c in cong_cu
    ]


class MoHinhAnthropic:
    def __init__(self, model: str, *, api_key: str, pool: Any = None) -> None:
        self.model = model
        self.ten = f"anthropic:{model}"
        self._client = AnthropicClient(api_key=api_key, pool=pool)

    async def tra_loi(
        self,
        *,
        he_thong: str,
        tin: Sequence[Tin],
        cong_cu: Sequence[CongCu] = (),
        max_tokens: int = 1024,
        tinh_nang: str = "tro_ly_khach",
    ) -> KetQuaMoHinh:
        try:
            r = await self._client.chat(
                messages=dich_tin(tin),
                model=self.model,
                system=he_thong,
                max_tokens=max_tokens,
                # Đời 5.5 trả 400 khi có tham số lấy mẫu — không gửi.
                temperature=None,
                tools=dich_cong_cu(cong_cu) or None,
                tinh_nang=tinh_nang,
            )
        except Exception as e:  # noqa: BLE001 — mọi lỗi SDK quy về một loại
            raise MoHinhError(f"{type(e).__name__}: {e}") from e
        return KetQuaMoHinh(
            chu=r.text,
            goi_cong_cu=tuple(
                GoiCongCu(ma=c["id"], ten=c["name"], tham_so=c["input"])
                for c in r.tool_calls
            ),
            model=r.model,
            token_vao=r.input_tokens,
            token_ra=r.output_tokens,
            thoi_gian_ms=r.latency_ms,
            lan_goi_id=r.lan_goi_id,
            ly_do_dung=r.stop_reason,
        )

    async def dong(self) -> None:
        await self._client.close()
