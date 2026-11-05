"""SQL soát chặng 0 (`scripts/soat-xet-nghiem-doi-tac.sql`) phải CHẠY ĐƯỢC trên lược
đồ thật và ĐẾM ĐÚNG — Tuyền chạy nó bằng tay trên prod để quyết câu D (bàn đối tác
cũ còn ai dùng); đếm thiếu là quyết sai.

Bẫy đã cắn (05/11/2026): sự kiện `partner.*` đi qua `emit_event` nên nằm ở
`domain_event` (`actor_staff_id`), KHÔNG ở `event_log`. Bản đầu chỉ đọc `event_log`
⇒ tài khoản PARTNER vừa ghi thu vẫn hiện 0 thao tác."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from clinicai.services.doi_tac_service import DoiTacService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai, _viec_da_nhan
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
SQL = Path(__file__).resolve().parents[3] / "scripts" / "soat-xet-nghiem-doi-tac.sql"


def _cau_lenh() -> list[str]:
    """Các câu của script, bỏ lệnh riêng của psql (`\\set …`)."""
    than = "\n".join(
        d
        for d in SQL.read_text(encoding="utf-8").splitlines()
        if not d.lstrip().startswith("\\")
    )
    return [c.strip() for c in than.split(";\n") if c.strip()]


def _phan(nhan: str) -> str:
    """Câu SELECT của đúng một phần, tìm theo nhãn cột `muc` (vd "'(c) tai khoan")."""
    ds = [c for c in _cau_lenh() if nhan in c]
    assert len(ds) == 1, f"không thấy đúng một câu chứa {nhan!r}"
    return ds[0]


async def test_script_chi_doc_va_chay_duoc(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        try:
            for cau in _cau_lenh():
                await conn.execute(cau)  # lỗi cột/bảng → ném
            with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
                await conn.execute("CREATE TEMP TABLE _khong_duoc_ghi (x int)")
        finally:  # kết nối về pool — gỡ chế độ chỉ đọc của phiên
            await conn.execute("RESET default_transaction_read_only")
            await conn.execute("RESET statement_timeout")


async def test_tai_khoan_partner_vua_ghi_thu_duoc_dem_thao_tac(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    dt = await _nguoi_vai(q, "PARTNER")
    await DoiTacService(pool).ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="CASH"
    )

    dong = [
        r
        for r in await pool.fetch(_phan("'(c) tai khoan PARTNER'"))
        if r["full_name"] == dt.full_name
    ]
    assert len(dong) == 1
    assert dong[0]["so_thao_tac_30_ngay"] >= 1
    assert dong[0]["thao_tac_cuoi_30_ngay"] is not None

    loai = {r["event_type"] for r in await pool.fetch(_phan("'(c2) su kien partner"))}
    assert "partner.payment_recorded" in loai
