"""Đồng hồ tiền LLM + tóm tắt ngày trên Postgres thật (09/10/2026).

Không gọi Anthropic thật: SDK bên trong `AnthropicClient` được thay bằng hàm giả
trả đúng hình dạng phản hồi (usage, model, stop_reason).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from clinicai.llm import chi_phi
from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.services import agent_tom_tat
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

TINH_NANG = "test_dong_ho"


def _phan_hoi(model: str = "claude-opus-5-5") -> Any:
    return SimpleNamespace(
        model=model,
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


def _client(pool: asyncpg.Pool, bat: dict[str, Any]) -> AnthropicClient:  # noqa: F811
    c = AnthropicClient(api_key="sk-ant-test", pool=pool)

    async def tao(**kwargs: Any) -> Any:
        bat.update(kwargs)
        return _phan_hoi(kwargs["model"])

    c._client = SimpleNamespace(messages=SimpleNamespace(create=tao))  # type: ignore[assignment]
    return c


async def _don(pool: asyncpg.Pool) -> None:  # noqa: F811
    await pool.execute("DELETE FROM llm_lan_goi WHERE tinh_nang = $1", TINH_NANG)


async def test_moi_lan_goi_ghi_token_va_tien_dung_gia(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bat: dict[str, Any] = {}
    await _don(pool)
    try:
        r = await _client(pool, bat).chat(
            messages=[{"role": "user", "content": "x"}],
            model="claude-opus-5-5",
            temperature=None,
            tinh_nang=TINH_NANG,
        )
        assert "temperature" not in bat, "Opus 5.5 trả 400 nếu gửi temperature"
        assert r.lan_goi_id
        dong = await pool.fetchrow(
            "SELECT * FROM llm_lan_goi WHERE id = $1::uuid", r.lan_goi_id
        )
        assert dong is not None
        assert (dong["input_tokens"], dong["output_tokens"]) == (1000, 500)
        # 1000 × 4/1M + 500 × 20/1M = 0.004 + 0.010
        assert dong["chi_phi_usd"] == Decimal("0.014000")
        so = await chi_phi.so_lieu(pool, so_ngay=1)
        assert any(m["model"] == "claude-opus-5-5" for m in so["theo_model"])
        assert so["hom_nay_usd"] >= 0.014
    finally:
        await _don(pool)


async def test_cham_tran_ngay_thi_tu_choi_goi(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bat: dict[str, Any] = {}
    await _don(pool)
    try:
        c = _client(pool, bat)
        await c.chat(
            messages=[{"role": "user", "content": "x"}],
            model="claude-opus-5-5",
            tinh_nang=TINH_NANG,
        )
        monkeypatch.setenv("LLM_TRAN_NGAY_USD", "0.000001")
        bat.clear()
        with pytest.raises(chi_phi.VuotTranChiPhiError):
            await c.chat(
                messages=[{"role": "user", "content": "x"}],
                model="claude-opus-5-5",
                tinh_nang=TINH_NANG,
            )
        assert bat == {}, "chạm trần thì KHÔNG gọi API"
    finally:
        await _don(pool)


async def test_goi_hong_van_ghi_mot_dong_loi(pool: asyncpg.Pool) -> None:  # noqa: F811
    await _don(pool)
    c = AnthropicClient(api_key="sk-ant-test", pool=pool)

    async def hong(**_: Any) -> Any:
        raise ValueError("mạng chập")

    c._client = SimpleNamespace(messages=SimpleNamespace(create=hong))  # type: ignore[assignment]
    try:
        with pytest.raises(ValueError):
            await c.chat(
                messages=[{"role": "user", "content": "x"}], tinh_nang=TINH_NANG
            )
        r = await pool.fetchrow(
            "SELECT thanh_cong, loi FROM llm_lan_goi WHERE tinh_nang = $1", TINH_NANG
        )
        assert r is not None and r["thanh_cong"] is False and "mạng chập" in r["loi"]
    finally:
        await _don(pool)


async def test_tom_tat_luu_ban_moi_nhat_va_khong_gui_ten_khach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ngay = date(2026, 1, 3)
    gui: dict[str, Any] = {}
    nhan_dinh_id = uuid4()
    ghi_chu_bi_mat = "CANARY_CHU_TU_DO: Nguyen Thi A, 0901234567, ket qua kham"
    await pool.execute(
        """
        INSERT INTO agent_nhan_dinh
            (id, clinic_id, loai, khoa, muc, noi_dung, muc_bang_chung,
             agent_version, mo_luc, danh_gia_ghi_chu)
        VALUES ($1, $2::uuid, 'phong_qua_tai', $3, 'warning',
                'Phòng có 5 người chờ.', 'quan_sat', 'test',
                '2026-01-03 08:00:00+07', $4)
        """,
        nhan_dinh_id,
        CLINIC,
        str(nhan_dinh_id),
        ghi_chu_bi_mat,
    )

    async def gia(**kwargs: Any) -> LLMResponse:
        gui.update(kwargs)
        return LLMResponse(
            text="## Tình hình hôm nay\nYên.",
            model="claude-opus-5-5",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            stop_reason="end_turn",
        )

    try:
        kq = await agent_tom_tat.tao(pool, clinic_id=CLINIC, ngay=ngay, goi=gia)
        assert kq["tu_dong"] is True and "Yên" in kq["noi_dung"]
        assert gui["temperature"] is None and gui["tinh_nang"] == "agent_tom_tat"
        noi_dung_gui = gui["messages"][0]["content"]
        assert "Phòng có 5 người chờ." in noi_dung_gui
        assert ghi_chu_bi_mat not in noi_dung_gui
        assert "ghi_chu_cham" not in noi_dung_gui, "không gửi chữ tự do cho LLM"
        assert "visit_id" not in noi_dung_gui, "chỉ gửi nội dung nhận định, không mã"
        doc = await agent_tom_tat.doc(pool, clinic_id=CLINIC, ngay=ngay)
        assert doc["tom_tat"] is not None and doc["tom_tat"]["id"] == kq["id"]
    finally:
        await pool.execute("DELETE FROM agent_nhan_dinh WHERE id = $1", nhan_dinh_id)
        await pool.execute(
            "DELETE FROM agent_tom_tat WHERE clinic_id = $1::uuid AND ngay = $2",
            CLINIC,
            ngay,
        )


async def test_khong_khoa_thi_tat_va_tu_dong_im(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setenv("AGENT_LLM_KEY_PATH", str(tmp_path / "khong-co"))
    with pytest.raises(agent_tom_tat.LlmTatError):
        await agent_tom_tat.tao(pool, clinic_id=CLINIC, ngay=date(2026, 1, 4))
    await agent_tom_tat.tu_dong(pool)  # không ném, không gọi gì
    doc = await agent_tom_tat.doc(pool, clinic_id=CLINIC, ngay=date(2026, 1, 4))
    assert doc["llm_bat"] is False and doc["tom_tat"] is None
