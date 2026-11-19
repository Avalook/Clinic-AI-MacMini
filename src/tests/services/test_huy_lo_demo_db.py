"""scripts/huy-lo-demo.py — huỷ lô mẫu DEMO1709-* qua đúng "Huỷ thuốc" của màn.

* thử khô không ghi; làm thật: lô mẫu về 0, lô thật cùng thuốc không đổi;
* chạy lại không huỷ thêm (khoá gửi trùng theo lô);
* hoàn tác: lô mẫu về đúng số cũ; chạy lại hoàn tác không cộng thêm.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from clinicai.core.clock import hom_nay_vn
from tests.services.test_kho_quay_db import Co, _nhap_kho, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import _thuoc, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "huy-lo-demo.py"


def _chay(*them: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(SCRIPT.parents[1] / "src")}
    kq = subprocess.run(
        [sys.executable, str(SCRIPT), *them],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert kq.returncode == 0, kq.stdout + kq.stderr
    return kq.stdout


async def test_huy_lo_demo_va_hoan_tac(co: Co, tmp_path: Path) -> None:  # noqa: F811
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
    thuoc = await _thuoc(co.q)
    han = hom_nay_vn() + timedelta(days=700)
    demo = await _nhap_kho(
        co, thuoc, 20, ma=f"DEMO1709-T{uuid.uuid4().hex[:6]}", han=han
    )
    that_lo = await _nhap_kho(co, thuoc, 30, han=han)

    async def ton(lo: str) -> Decimal:
        return Decimal(
            str(
                await co.q.pool.fetchval(
                    "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
                )
            )
        )

    chi = f"--chi-lo={demo},{that_lo}"
    ra = _chay(chi)
    assert "THỬ KHÔ" in ra and "1 lô, tồn 20" in ra, ra
    assert await ton(demo) == 20

    tep = tmp_path / "huy.jsonl"
    ra = _chay(chi, f"--luu={tep}", "--that")
    assert "đã huỷ 1 lô" in ra, ra
    assert (await ton(demo), await ton(that_lo)) == (Decimal(0), Decimal(30))
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id = $1::uuid"
            " AND txn_type = 'DISCARD' AND reason LIKE '%[HUY-LO-DEMO-1611]%'",
            demo,
        )
        == 1
    )
    # Chạy lại: lô đã về 0, không còn ứng viên → không huỷ thêm.
    assert "đã huỷ 0 lô" in _chay(chi, f"--luu={tmp_path / 'lai.jsonl'}", "--that")

    assert "đã cộng lại 1 lô" in _chay(f"--hoan-tac={tep}")
    assert await ton(demo) == 20
    _chay(f"--hoan-tac={tep}")  # khoá gửi trùng: không cộng hai lần
    assert await ton(demo) == 20

    # Huỷ LẠI sau hoàn tác phải huỷ thật — staging 20/11: khoá gửi trùng của lần
    # chạy 16/11 làm 80 lô "đã huỷ" mà không ghi gì, script vẫn báo xong.
    ra = _chay(chi, f"--luu={tmp_path / 'lan2.jsonl'}", "--that")
    assert "đã huỷ 1 lô" in ra, ra
    assert await ton(demo) == 0
    # …và hoàn tác lần hai cũng phải cộng thật (khoá cố định theo lô → nhận
    # "đã làm" mà không cộng gì).
    assert "đã cộng lại 1 lô" in _chay(f"--hoan-tac={tmp_path / 'lan2.jsonl'}")
    assert await ton(demo) == 20
