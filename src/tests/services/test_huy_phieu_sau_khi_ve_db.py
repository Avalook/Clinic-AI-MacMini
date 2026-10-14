"""G4d · D (Tuyền chốt 14/10/2026, cách KHÔNG khoá): huỷ phiếu SAU khi khách đã
về mà dịch vụ đã làm → không chặn lệnh huỷ; máy TỰ ghi khoản ấy thành nợ "chờ
thu hoặc miễn" (lý do huỷ + người bấm) để phòng khám xử lý sau.

    scripts/test-nhanh.sh src/tests/services/test_huy_phieu_sau_khi_ve_db.py

Trước G4d: sổ nợ (#420) đã tự thấy khoản phải thu, nhưng không có dòng công nợ
nào nói VÌ SAO / AI — việc tồn ghi "Khi về" như thể lễ tân cho về khi còn nợ.
"Miễn" = thu 0đ giảm 100% trên lượt đã ghi nợ (#415, test_giam_gia_db).
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    _huy_phieu,
    _lam_truoc_thu_sau,
    _lam_xong,
    _lech,
    _luot,
    _thu,
    _ve,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _cong_no(pool: asyncpg.Pool, visit: str) -> list[asyncpg.Record]:  # noqa: F811
    return await pool.fetch(
        "SELECT so_tien, trang_thai, ly_do FROM cong_no WHERE visit_id = $1::uuid",
        visit,
    )


async def test_huy_phieu_sau_khi_ve_tu_ghi_no_cho_xu_ly(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    await _huy_phieu(pool, ca, v)  # lý do: "Thu nhầm, huỷ phiếu"
    no = await _cong_no(pool, v)
    assert [(int(r["so_tien"]), r["trang_thai"]) for r in no] == [(300_000, "CHUA_THU")]
    assert "chờ thu hoặc miễn" in no[0]["ly_do"]
    assert "Thu nhầm, huỷ phiếu" in no[0]["ly_do"]
    assert await _lech(pool, v) == []
    # Việc tồn nói đúng vì sao (lý do huỷ), không phải "Khi về".
    async with pool.acquire() as conn:
        ton = [
            t
            for t in await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, None)
            if t.get("visit_id") == v and t["loai"] == "GHI_NO"
        ]
    assert len(ton) == 1 and ton[0]["so_tien"] == 300_000
    assert "Thu nhầm, huỷ phiếu" in str(ton[0]["mo_ta"])
    # Xử lý sau: quầy thu lại trên lượt đã đóng → hết nợ, sổ khớp.
    await _thu(pool, ca, v)
    assert await _lech(pool, v) == []
    assert [r["trang_thai"] for r in await _cong_no(pool, v)] == ["DA_THU"]


async def test_huy_phieu_luot_con_mo_khong_tu_ghi_no(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Lượt chưa check-out: cổng check-out đã hỏi nợ — huỷ rồi thu lại (đổi TM→CK…)
    vẫn như cũ, không sinh dòng công nợ."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _lam_xong(pool, ca, o)
    await _huy_phieu(pool, ca, v)
    assert await _cong_no(pool, v) == []
    await _thu(pool, ca, v, method="TRANSFER")
    assert await _cong_no(pool, v) == []


async def test_huy_phieu_sau_khi_ve_chua_lam_khong_ghi_no(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Dịch vụ chưa làm: huỷ phiếu = khách không nợ gì, không ghi công nợ."""
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _ve(pool, ca, v)
    await _huy_phieu(pool, ca, v)
    assert await _cong_no(pool, v) == []
    assert await _lech(pool, v) == []
