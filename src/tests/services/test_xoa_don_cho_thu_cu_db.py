"""scripts/xoa-don-cho-thu-cu.py — chạy đúng script sẽ chạy trên prod, giới hạn vào
lượt của bài (`--chi-luot`, DB test dùng chung):

* đơn CHỜ THU cũ (chưa có bill) → xoá hẳn, có bản lưu JSONL + sự kiện;
* lượt ĐÃ có bill thuốc (thu xong) → giữ nguyên, tiền không đổi;
* đơn tạo sau mốc → giữ nguyên;
* hồ sơ ĐÃ KÝ → DB từ chối xoá, script bỏ qua và báo;
* thử khô không ghi; --khoi-phuc chèn lại đúng dòng (cùng id).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import _don, _thu, _thuoc, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "xoa-don-cho-thu-cu.py"
MOC = "--truoc=2099-01-01T00:00+07:00"  # mọi đơn bài tạo đều trước mốc này


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


async def _con(pool: asyncpg.Pool, rx: str) -> bool:
    return bool(
        await pool.fetchval("SELECT 1 FROM prescription WHERE id = $1::uuid", rx)
    )


async def test_xoa_cho_thu_giu_da_thu_va_ho_so_ky(
    pool: asyncpg.Pool, tmp_path: Path
) -> None:
    q_cu = await tao_quay(pool)
    sid = await pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ('Quản lý thử', 'MANAGEMENT', $1::uuid, true)"
        " RETURNING id::text",
        q_cu.thu_ngan.location_id,
    )
    await pool.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, 'MANAGEMENT', true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        q_cu.thu_ngan.clinic_id,
        sid,
    )
    rx_cu = await _don(q_cu, 5)
    rx_cu2 = await _don(q_cu, 2)

    q_thu = await tao_quay(pool)
    rx_thu = await _don(q_thu, 10)
    await PharmacyService(pool).xac_dinh_thuoc(
        identity=q_thu.duoc_si,
        prescription_id=rx_thu,
        drug_catalog_id=await _thuoc(q_thu),
    )
    await _thu(q_thu, "thuoc")
    tien = await pool.fetchval(
        "SELECT sum(amount) FROM payment_cycle WHERE visit_id = $1::uuid",
        q_thu.visit_id,
    )

    q_ky = await tao_quay(pool)
    rx_ky = await _don(q_ky, 3)
    await pool.execute(
        "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid",
        q_ky.visit_id,
    )

    chi = f"--chi-luot={q_cu.visit_id},{q_thu.visit_id},{q_ky.visit_id}"

    # Mốc sớm → không ứng viên.
    assert "dòng đơn: 0" in _chay(chi, "--truoc=2020-01-01T00:00+07:00")

    ra = _chay(chi, MOC)
    assert "THỬ KHÔ" in ra and "dòng đơn: 3 · lượt: 2" in ra
    assert await _con(pool, rx_cu)

    tep = tmp_path / "luu.jsonl"
    ra = _chay(chi, MOC, f"--luu={tep}", "--that")
    assert "đã xoá 2 dòng" in ra, ra
    assert "bỏ qua 1 dòng" in ra and "hồ sơ đã ký" in ra
    assert not await _con(pool, rx_cu) and not await _con(pool, rx_cu2)
    assert await _con(pool, rx_ky)
    assert await _con(pool, rx_thu)
    assert (
        await pool.fetchval(
            "SELECT sum(amount) FROM payment_cycle WHERE visit_id = $1::uuid",
            q_thu.visit_id,
        )
        == tien
    )
    assert len(tep.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type = 'pharmacy.don_cu_xoa'"
            " AND aggregate_id = ANY($1::uuid[])",
            [rx_cu, rx_cu2],
        )
        == 2
    )

    # Khôi phục: đúng 2 dòng, cùng id; chạy lại không chèn trùng.
    assert "đã khôi phục 2/2" in _chay(f"--khoi-phuc={tep}")
    assert await _con(pool, rx_cu) and await _con(pool, rx_cu2)
    assert "đã khôi phục 0/2" in _chay(f"--khoi-phuc={tep}")
