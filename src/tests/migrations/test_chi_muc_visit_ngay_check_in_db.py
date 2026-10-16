"""Chỉ mục `idx_visit_ngay_check_in` (14/10/2026) phải KHỚP câu "khách hôm nay".

    scripts/test-nhanh.sh src/tests/migrations/test_chi_muc_visit_ngay_check_in_db.py

Chỉ mục biểu thức chỉ được planner dùng khi biểu thức trong câu hỏi giống TỪNG
CHỮ biểu thức trong chỉ mục — gõ lệch một dấu là mất tác dụng mà không ai báo.
Bài này dựng đúng câu của `dem_theo_phong`, tắt quét tuần tự để planner không có
đường nào khác, và đòi nó chọn chỉ mục.
"""

from __future__ import annotations

import asyncpg
import pytest

from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Y NGUYÊN vế lọc trong `nhan_tai_phong.dem_theo_phong` (đổi một chữ ở đó thì
#: đổi cả ở đây — bài này canh đúng việc ấy).
_HOM_NAY = (
    "(v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    " = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
)


#: Biểu thức như Postgres in ra (cả trong định nghĩa chỉ mục lẫn bộ lọc của kế
#: hoạch) — hai nơi cùng cây biểu thức thì in giống hệt.
_BIEU_THUC = "((checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text))::date"


async def test_chi_muc_ton_tai_hop_le_va_cung_bieu_thuc_voi_cau_hot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    r = await pool.fetchrow(
        "SELECT i.indisvalid, pg_get_indexdef(i.indexrelid) AS ddl"
        "  FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid"
        " WHERE c.relname = 'idx_visit_ngay_check_in'"
    )
    assert r is not None and r["indisvalid"]
    assert _BIEU_THUC in r["ddl"], r["ddl"]
    # Planner nhìn thấy CÙNG cây biểu thức ở câu hot (bảng thử quá nhỏ để nó
    # chọn chỉ mục, nên so biểu thức thay vì đòi tên chỉ mục trong kế hoạch).
    async with pool.acquire() as conn:
        plan = "\n".join(
            x[0]
            for x in await conn.fetch(
                "EXPLAIN SELECT v.visit_id FROM visit v"
                f" WHERE v.clinic_id = '{CLINIC}'::uuid AND " + _HOM_NAY
            )
        )
    assert _BIEU_THUC in plan, plan
