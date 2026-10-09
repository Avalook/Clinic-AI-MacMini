"""Bể kết nối của ứng dụng tắt JIT (đo 09/10/2026: câu bảng thu ngân chạy thật
~80ms, JIT biên dịch ~3,1s mỗi lần; ba lần song song đẩy DB staging tới OOM)."""

from typing import Any

import asyncpg
import pytest

from clinicai.core import database


async def test_be_ket_noi_tat_jit(monkeypatch: pytest.MonkeyPatch) -> None:
    nhan: dict[str, Any] = {}

    async def gia_create_pool(**kw: Any) -> object:
        nhan.update(kw)
        return object()

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setattr(asyncpg, "create_pool", gia_create_pool)

    await database.create_pool()

    assert nhan["server_settings"]["jit"] == "off"
    assert nhan["dsn"].startswith("postgresql://")
