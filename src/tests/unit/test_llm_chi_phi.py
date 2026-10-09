"""Đồng hồ tiền LLM — phần hàm thuần (09/10/2026)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from clinicai.llm import chi_phi
from clinicai.services import agent_tom_tat


def test_mot_trieu_token_vao_opus_la_4_usd() -> None:
    assert chi_phi.tinh_usd("claude-opus-5-5", vao=1_000_000, ra=0) == Decimal("4")
    assert chi_phi.tinh_usd("claude-opus-5-5", vao=0, ra=1_000_000) == Decimal("20")


def test_cache_doc_re_ghi_dat_hon_vao() -> None:
    g = chi_phi.gia_cua("claude-sonnet-5-5")
    assert g is not None
    assert g.doc_cache < g.vao < g.ghi_cache
    assert g.ghi_cache == g.vao * Decimal("1.25")


def test_ma_model_kem_ngay_van_khop_gia() -> None:
    assert (
        chi_phi.gia_cua("claude-haiku-4-5-20251001")
        == chi_phi.BANG_GIA["claude-haiku-4-5"]
    )


def test_model_chua_co_gia_thi_khong_doan() -> None:
    assert chi_phi.tinh_usd("gpt-9", vao=100, ra=100) is None
    assert chi_phi.tinh_usd(None, vao=100, ra=100) is None


def test_token_rac_tinh_bang_0() -> None:
    usd = chi_phi.tinh_usd("claude-opus-5-5", vao=-5, ra="abc", doc_cache=True)
    assert usd == Decimal("0")


def test_env_rac_ve_mac_dinh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TRAN_NGAY_USD", "không phải số")
    assert chi_phi.tran_ngay_usd() == Decimal("2")
    monkeypatch.setenv("LLM_TRAN_NGAY_USD", "-3")
    assert chi_phi.tran_ngay_usd() == Decimal("2")
    monkeypatch.setenv("LLM_TRAN_NGAY_USD", "0.5")
    assert chi_phi.tran_ngay_usd() == Decimal("0.5")


def test_khoa_chi_nhan_tep_khoa_that(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tep = tmp_path / "khoa"
    monkeypatch.setenv("AGENT_LLM_KEY_PATH", str(tep))
    assert agent_tom_tat.doc_khoa() is None, "không có tệp → tắt"
    tep.write_text("")
    assert agent_tom_tat.doc_khoa() is None, "tệp rỗng (staging) → tắt"
    tep.write_text("sk-staging-khong-phai-khoa-that")
    assert agent_tom_tat.doc_khoa() is None, "khoá giả → tắt"
    tep.write_text("  sk-ant-api03-" + "x" * 40 + "\n")
    assert agent_tom_tat.doc_khoa() == "sk-ant-api03-" + "x" * 40
