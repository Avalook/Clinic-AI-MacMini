"""Che dữ liệu khách trên staging — hàng chờ đơn thuốc quốc gia (24/11/2026).

`dtqg_gui.goi` chụp định danh khách (họ tên, ngày sinh, CCCD, SĐT, địa chỉ, người
giám hộ); `loi_cuoi` có thể chép câu lỗi hệ thống quốc gia trả về. Bản sao prod
lên staging phải che hết. Dùng lại dữ liệu gieo + bước che của
`test_staging_che_du_lieu.py` (tệp ấy đã quá trần kích thước — không viết thêm vào).
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from tests.test_staging_che_du_lieu import (
    CCCD_THAT,
    SDT_THAT,
    TEN_NGUOI_NHA,
    TEN_THAT,
    _che,
    _gieo,
    conn,  # noqa: F401 — fixture
)


@pytest.mark.db
@pytest.mark.asyncio
async def test_che_goi_don_thuoc_quoc_gia(conn: asyncpg.Connection) -> None:  # noqa: F811
    """Trigger "không sửa sự việc" của `dtqg_gui` được tắt trong lúc che."""
    ids = await _gieo(conn)
    vid = await conn.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status)"
        " VALUES ($1::uuid, $2::uuid, 'OPEN') RETURNING visit_id::text",
        ids["clinic"],
        ids["bn"],
    )
    nb = {
        "ma_benh_nhan": "BN1",
        "ho_ten": TEN_THAT,
        "ngay_sinh": "1990-05-17",
        "nam_sinh": 1990,
        "gioi_tinh": "NU",
        "so_dinh_danh": CCCD_THAT,
        "dia_chi": "12 Phố Thật, Hà Nội",
        "dien_thoai": SDT_THAT,
        "nguoi_giam_ho": TEN_NGUOI_NHA,
    }
    await conn.execute(
        "INSERT INTO dtqg_gui (clinic_id, visit_id, phien_ban, ma_don, goi,"
        " dau_van_tay, het_luot_luc, loi_cuoi) VALUES ($1::uuid, $2::uuid, 1,"
        " '01aaa0000001-c', $3::jsonb, repeat('a', 64), now(), $4)",
        ids["clinic"],
        vid,
        json.dumps({"ma_don": "01aaa0000001-c", "nguoi_benh": nb}, ensure_ascii=False),
        f"BI_TU_CHOI_422: ['Người bệnh {TEN_THAT} thiếu ngày sinh']",
    )
    await _che(conn)
    r = await conn.fetchrow(
        "SELECT goi::text AS goi, loi_cuoi FROM dtqg_gui WHERE visit_id = $1::uuid",
        vid,
    )
    for that in (TEN_THAT, CCCD_THAT, SDT_THAT, TEN_NGUOI_NHA, "Phố Thật", "1990-05"):
        assert that not in r["goi"], that
    assert r["loi_cuoi"] == "(đã che)"
