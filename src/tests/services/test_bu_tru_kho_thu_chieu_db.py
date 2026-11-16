"""scripts/bu-tru-kho-thu-chieu.py — bù trừ kho cho lần thu trước khi có tự giao.

Cơ sở đã tách kho: quầy 4, kho 10; khách mua 8, thu lúc CHƯA có tự giao (công tắc
tắt) → kho chưa trừ. Script (công tắc bật, như prod sau #641):
* thử khô: chạy rồi cuộn lại — in đúng 4 ở quầy + 4 ở kho, DB không đổi;
* làm thật: quầy 0, kho 6, dòng đã giao 8; chạy lại không có lần thu nào nữa;
* hoàn tác: quầy 4, kho 10, dòng về chưa giao.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from clinicai.core.clock import CLINIC_TZ
from tests.services.test_kho_quay_db import Co, _chuyen, _id_dich, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _thu
from tests.services.test_tu_giao_khi_thu_db import _da_giao, _rx, _san_kho, _ton_lo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "bu-tru-kho-thu-chieu.py"


def _chay(*them: str) -> str:
    env = {
        **os.environ,
        "PYTHONPATH": str(SCRIPT.parents[1] / "src"),
        "CLINICAI_TU_GIAO_KHI_THU": "1",
        "CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY": "0",
    }
    kq = subprocess.run(
        [sys.executable, str(SCRIPT), *them],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert kq.returncode == 0, kq.stdout + kq.stderr
    return kq.stdout


async def test_bu_tru_quay_roi_kho_thu_kho_va_hoan_tac(
    co: Co,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sid = await co.q.pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ('Quản lý thử', 'MANAGEMENT', $1::uuid, true)"
        " RETURNING id::text",
        co.loc,
    )
    await co.q.pool.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, 'MANAGEMENT', true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        co.ds.clinic_id,
        sid,
    )
    thuoc, kho = await _san_kho(co, 14)
    quay = _id_dich(await _chuyen(co, kho, 4))
    rx = await _rx(co, thuoc, 8)
    tu = (datetime.now(CLINIC_TZ) - timedelta(minutes=5)).isoformat()

    # Thu lúc prod CHƯA có tự giao → kho chưa trừ.
    monkeypatch.setenv("CLINICAI_TU_GIAO_KHI_THU", "0")
    kq = await _thu(co.q)
    assert kq["status"] == "PAID"
    assert await _da_giao(co.q, rx) == 0
    assert await _ton_lo(co, quay, kho) == [4, 10]

    chi = f"--chi-luot={co.q.visit_id}"
    ra = _chay(chi, f"--tu={tu}")
    assert "THỬ KHÔ" in ra and "lần thu còn dòng chưa giao: 1" in ra, ra
    assert "· QUAY lô " in ra and "· KHO lô " in ra and "lô DEMO*: 0" in ra, ra
    assert ": 4\n" in ra, ra
    assert await _ton_lo(co, quay, kho) == [4, 10]  # cuộn lại sạch
    assert await _da_giao(co.q, rx) == 0

    tep = tmp_path / "bu.jsonl"
    ra = _chay(chi, f"--tu={tu}", f"--luu={tep}", "--that")
    assert "lần thu đã xử lý: 1" in ra and "bỏ qua (vẫn còn nút Giao): 0" in ra, ra
    assert await _ton_lo(co, quay, kho) == [0, 6]
    assert await _da_giao(co.q, rx) == 8
    assert "lần thu còn dòng chưa giao: 0" in _chay(chi, f"--tu={tu}")

    assert "đã hoàn tác 1 lần thu" in _chay(f"--hoan-tac={tep}")
    assert await _ton_lo(co, quay, kho) == [4, 10]
    assert await _da_giao(co.q, rx) == 0
