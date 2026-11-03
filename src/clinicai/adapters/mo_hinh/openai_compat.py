"""Adapter chuẩn "OpenAI Chat Completions" — MỘT adapter cho OpenAI, Gemini
(cổng tương thích), DeepSeek, Qwen, và Ollama / vLLM chạy tại chỗ.

Gọi bằng httpx (anthropic SDK đã kéo nó vào ảnh prod) thay vì thêm SDK openai:
API chỉ là một POST, thêm thư viện là thêm thứ phải ghim.

TIỀN: có `pool` thì vẫn ghi `llm_lan_goi` và chặn theo trần ngày, nhưng
`chi_phi.BANG_GIA` chỉ có giá Claude → lượt gọi hãng khác ghi token, tiền để
trống, và KHÔNG cộng vào trần. Thử model trả tiền của hãng khác thì canh số
token trên bảng chấm.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clinicai.llm import chi_phi
from clinicai.ports.mo_hinh import CongCu, GoiCongCu, KetQuaMoHinh, MoHinhError, Tin

logger = structlog.get_logger(__name__)


class _TamThoiError(Exception):
    """429 / 5xx — thử lại được."""


def dich_tin(he_thong: str, tin: Sequence[Tin]) -> list[dict[str, Any]]:
    ra: list[dict[str, Any]] = [{"role": "system", "content": he_thong}]
    for t in tin:
        if t.vai == "khach":
            ra.append({"role": "user", "content": t.noi_dung})
        elif t.vai == "tro_ly":
            m: dict[str, Any] = {"role": "assistant", "content": t.noi_dung or None}
            if t.goi_cong_cu:
                m["tool_calls"] = [
                    {
                        "id": g.ma,
                        "type": "function",
                        "function": {
                            "name": g.ten,
                            "arguments": json.dumps(g.tham_so, ensure_ascii=False),
                        },
                    }
                    for g in t.goi_cong_cu
                ]
            ra.append(m)
        else:
            ra.append({"role": "tool", "tool_call_id": t.ma_goi, "content": t.noi_dung})
    return ra


def dich_cong_cu(cong_cu: Sequence[CongCu]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": c.ten,
                "description": c.mo_ta,
                "parameters": c.tham_so,
            },
        }
        for c in cong_cu
    ]


def doc_tham_so(chuoi: Any) -> dict[str, Any]:
    """`arguments` là CHUỖI JSON do model sinh — model nhỏ hay sinh hỏng.
    Hỏng thì trả rỗng để công cụ báo thiếu tham số, không làm sập lượt."""
    if isinstance(chuoi, dict):
        return chuoi
    try:
        v = json.loads(chuoi or "{}")
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def doc_phan_hoi(body: dict[str, Any]) -> tuple[str, tuple[GoiCongCu, ...], str | None]:
    lua_chon = (body.get("choices") or [{}])[0]
    msg = lua_chon.get("message") or {}
    goi = tuple(
        GoiCongCu(
            ma=str(c.get("id") or f"goi_{i}"),
            ten=str((c.get("function") or {}).get("name") or ""),
            tham_so=doc_tham_so((c.get("function") or {}).get("arguments")),
        )
        for i, c in enumerate(msg.get("tool_calls") or [])
    )
    return str(msg.get("content") or ""), goi, lua_chon.get("finish_reason")


class MoHinhOpenAICompat:
    def __init__(
        self,
        hang: str,
        model: str,
        *,
        base_url: str,
        api_key: str | None,
        pool: Any = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.model = model
        self.ten = f"{hang}:{model}"
        self._pool = pool
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_s
        )

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        async for lan in AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((_TamThoiError, httpx.TransportError)),
        ):
            with lan:
                r = await self._http.post("/chat/completions", json=body)
                if r.status_code == 429 or r.status_code >= 500:
                    raise _TamThoiError(f"HTTP {r.status_code}")
                if r.status_code >= 400:
                    raise MoHinhError(f"HTTP {r.status_code}: {r.text[:300]}")
                data = r.json()
                return data if isinstance(data, dict) else {}
        raise MoHinhError("vòng thử lại thoát không có kết quả")

    async def tra_loi(
        self,
        *,
        he_thong: str,
        tin: Sequence[Tin],
        cong_cu: Sequence[CongCu] = (),
        max_tokens: int = 1024,
        tinh_nang: str = "tro_ly_khach",
    ) -> KetQuaMoHinh:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": dich_tin(he_thong, tin),
            "max_tokens": max_tokens,
        }
        if cong_cu:
            body["tools"] = dich_cong_cu(cong_cu)
        if self._pool is not None:
            await chi_phi.chan_neu_vuot_tran(self._pool)
        bat_dau = time.perf_counter()
        try:
            data = await self._post(body)
        except MoHinhError:
            raise
        except Exception as e:  # noqa: BLE001
            raise MoHinhError(f"{type(e).__name__}: {e}") from e
        ms = int((time.perf_counter() - bat_dau) * 1000)
        chu, goi, ly_do = doc_phan_hoi(data)
        usage = data.get("usage") or {}
        vao = int(usage.get("prompt_tokens") or 0)
        ra = int(usage.get("completion_tokens") or 0)
        lan_goi_id = None
        if self._pool is not None:
            lan_goi_id = await chi_phi.ghi_lan_goi(
                self._pool,
                tinh_nang=tinh_nang,
                model=self.ten,
                vao=vao,
                ra=ra,
                thoi_gian_ms=ms,
            )
        logger.info(
            "llm_call",
            model=self.ten,
            input_tokens=vao,
            output_tokens=ra,
            latency_ms=ms,
            stop_reason=ly_do,
        )
        return KetQuaMoHinh(
            chu=chu,
            goi_cong_cu=goi,
            model=str(data.get("model") or self.model),
            token_vao=vao,
            token_ra=ra,
            thoi_gian_ms=ms,
            lan_goi_id=lan_goi_id,
            ly_do_dung=ly_do,
        )

    async def dong(self) -> None:
        await self._http.aclose()
