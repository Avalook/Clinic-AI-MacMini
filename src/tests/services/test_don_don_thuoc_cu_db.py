"""scripts/don-don-thuoc-cu.py — chạy đúng script sẽ chạy trên prod, giới hạn vào
lượt của bài (`--chi-luot`, DB test dùng chung):

* dòng CŨ chưa thu tiền → đóng là "Khách không lấy", lý do mang mã đợt;
* dòng cũ ĐÃ THU tiền thuốc → giữ nguyên (số đã tính không đổi);
* dòng tạo HÔM NAY → giữ nguyên;
* thử khô không ghi; chạy lại không đổi gì thêm; --hoan-tac mở lại đúng dòng đợt.
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

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "don-don-thuoc-cu.py"
DOT = "[DON-CU-1611]"


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


async def _dong(pool: asyncpg.Pool, rx: str) -> tuple[bool, str | None]:
    r = await pool.fetchrow(
        "SELECT closed_at IS NOT NULL AS dong, refusal_reason FROM prescription"
        " WHERE id = $1::uuid",
        rx,
    )
    return bool(r["dong"]), r["refusal_reason"]


async def _lui_ngay(pool: asyncpg.Pool, rx: str) -> None:
    await pool.execute(
        "UPDATE prescription SET created_at = now() - interval '3 days'"
        " WHERE id = $1::uuid",
        rx,
    )


async def test_don_dong_cu_chua_thu_giu_dong_da_thu_va_hom_nay(
    pool: asyncpg.Pool,
) -> None:
    # Quản lý đứng tên script (prod: "Quản lý hệ thống").
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
    await _lui_ngay(pool, rx_cu)

    q_thu = await tao_quay(pool)
    rx_thu = await _don(q_thu, 10)
    await PharmacyService(pool).xac_dinh_thuoc(
        identity=q_thu.duoc_si,
        prescription_id=rx_thu,
        drug_catalog_id=await _thuoc(q_thu),
    )
    await _thu(q_thu, "thuoc")
    await _lui_ngay(pool, rx_thu)

    q_nay = await tao_quay(pool)
    rx_nay = await _don(q_nay, 3)

    chi = f"--chi-luot={q_cu.visit_id},{q_thu.visit_id},{q_nay.visit_id}"

    ra = _chay(chi)
    assert "THỬ KHÔ" in ra and "dòng đơn sẽ đóng: 1 (1 lượt)" in ra
    assert (await _dong(pool, rx_cu))[0] is False

    ra = _chay(chi, "--that")
    assert "đã đóng 1 dòng" in ra
    dong, ly = await _dong(pool, rx_cu)
    assert dong and ly is not None and DOT in ly
    assert (await _dong(pool, rx_thu))[0] is False
    assert (await _dong(pool, rx_nay))[0] is False

    # Chạy lại: không còn ứng viên.
    assert "dòng đơn sẽ đóng: 0" in _chay(chi, "--that")

    # Hoàn tác cả đợt: mở lại đúng dòng đã đóng, có sự kiện bù.
    assert "đã mở lại 1 dòng" in _chay("--hoan-tac")
    assert await _dong(pool, rx_cu) == (False, None)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1::uuid"
            " AND event_type IN ('pharmacy.refused', 'pharmacy.refuse_undone')",
            rx_cu,
        )
        == 2
    )
