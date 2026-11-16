"""scripts/chuyen-ton-quay-ve-kho.py — chạy đúng script sẽ chạy trên prod, trên
một cơ sở riêng: thử khô không ghi; làm thật đưa mọi lô quầy còn tồn về kho bằng
phiếu chuyển thường; chạy lại không lập phiếu thứ hai; phiếu hoàn tác được."""

from __future__ import annotations

# ruff: noqa: F811 — fixture q/co được import.
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from clinicai.services import kho_thuoc_service as kho
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import Co, _nhap_kho, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "chuyen-ton-quay-ve-kho.py"


def _chay(ten: str, *them: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(SCRIPT.parents[1] / "src")}
    kq = subprocess.run(
        [sys.executable, str(SCRIPT), ten, *them],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert kq.returncode == 0, kq.stdout + kq.stderr
    return kq.stdout


async def _noi(co: Co) -> list[tuple[str, int]]:
    rows = await co.q.pool.fetch(
        "SELECT noi_chua, quantity_on_hand FROM drug_batch"
        " WHERE location_id = $1::uuid AND quantity_on_hand > 0 ORDER BY 1, 2",
        co.loc,
    )
    return [(r["noi_chua"], int(r["quantity_on_hand"])) for r in rows]


async def test_chuyen_het_ton_quay_ve_kho(co: Co) -> None:  # noqa: F811
    ten = f"Tách kho thử {uuid.uuid4().hex[:8]}"
    await co.q.pool.execute(
        "UPDATE clinic_location SET name = $2 WHERE id = $1::uuid", co.loc, ten
    )
    # Script đứng tên một Quản lý đang hoạt động (prod: "Quản lý hệ thống").
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
    # Nhập TRƯỚC khi bật tách: lô nằm ở QUẦY — đúng tình trạng prod 16/11.
    a = await _thuoc_moi(co.q)
    b = await _thuoc_moi(co.q)
    await _nhap_kho(co, a, 30)
    await _nhap_kho(co, b, 12)
    await kho.dat_tach_kho_quay(co.q.pool, identity=co.ds, bat=True)
    truoc = await _noi(co)
    assert truoc == [("QUAY", 12), ("QUAY", 30)]

    ra = _chay(ten)
    assert "THỬ KHÔ" in ra and "lô sẽ chuyển về kho:    2" in ra
    assert await _noi(co) == truoc

    ra = _chay(ten, "--that")
    assert "✓ phiếu" in ra
    assert await _noi(co) == [("KHO", 12), ("KHO", 30)]
    so_phieu = await co.q.pool.fetchval(
        "SELECT count(*) FROM phieu_kho WHERE location_id = $1::uuid"
        " AND loai = 'CHUYEN'",
        co.loc,
    )
    assert so_phieu == 1

    # Chạy lại: quầy đã trống — không lập phiếu nào nữa.
    ra = _chay(ten, "--that")
    assert "lô sẽ chuyển về kho:    0" in ra
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM phieu_kho WHERE location_id = $1::uuid"
            " AND loai = 'CHUYEN'",
            co.loc,
        )
        == 1
    )

    # Hoàn tác như bấm trên màn: hàng trở lại quầy.
    pid = await co.q.pool.fetchval(
        "SELECT id::text FROM phieu_kho WHERE location_id = $1::uuid"
        " AND loai = 'CHUYEN'",
        co.loc,
    )
    await kho.hoan_tac_chuyen(
        co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=pid
    )
    assert await _noi(co) == truoc
