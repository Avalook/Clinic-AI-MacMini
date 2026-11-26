"""Dựng dữ liệu đơn vị thuốc cho test (không phải tệp test).

Từ 26/11/2026 (PR C) nhập kho chỉ theo đơn vị ĐÃ KHAI ở Danh mục — test nào nhập
"hộp" cho thuốc gốc "viên" phải khai trước, như người kho làm trên màn.
"""

from __future__ import annotations

from collections.abc import Mapping

import asyncpg


async def dat_goc_va_khai(
    pool: asyncpg.Pool, drug: str, goc: str, chi_de_nhap: Mapping[str, int]
) -> None:
    """Đặt đơn vị gốc + khai các đơn vị "chỉ để nhập" (tắt bán, chưa giá)."""
    await pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = $2 WHERE id = $1::uuid", drug, goc
    )
    await pool.executemany(
        "INSERT INTO thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so,"
        " dang_ban) SELECT clinic_id, id, $2, $3, false FROM drug_catalog"
        " WHERE id = $1::uuid",
        [(drug, dv, hs) for dv, hs in chi_de_nhap.items()],
    )
