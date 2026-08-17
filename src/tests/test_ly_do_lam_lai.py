"""Lý do làm lại — ghi SAU hoàn tác, tuỳ chọn (Đặng Dương 17/08/2026).

Giữ chốt của Quang 10/08 (hoàn tác một-cú-bấm, không hộp xác nhận): lý do
là cửa mở SAU cho người cần báo cáo, không phải rào chắn trước. Vì thế
service CHỈ nhận vào dòng ĐÃ hoàn tác — "lý do làm lại" trên một dòng còn
hiệu lực là câu vô nghĩa.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH A",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _Pool:
    def __init__(self, *, ghi_duoc: bool) -> None:
        self._ghi_duoc = ghi_duoc
        self.sql: str | None = None
        self.args: tuple[object, ...] | None = None

    async def fetchval(self, sql: str, *args: object) -> object:
        self.sql = sql
        self.args = args
        return "id" if self._ghi_duoc else None


def _goi(pool: _Pool, ly_do: str) -> dict[str, Any]:
    service = TuongTacCskhService(pool)
    return asyncio.run(
        service.ghi_ly_do_hoan_tac(
            identity=_identity(),
            tuong_tac_id="tt000000-0000-4000-8000-000000000001",
            ly_do=ly_do,
        )
    )


def test_chi_ghi_vao_dong_da_hoan_tac_va_tu_khoa_phong_kham() -> None:
    pool = _Pool(ghi_duoc=True)
    assert _goi(pool, "  bấm nhầm khách  ") == {"ok": True}
    assert pool.sql is not None
    assert "huy_luc IS NOT NULL" in pool.sql, (
        "dòng còn hiệu lực mà nhận lý do làm lại là câu vô nghĩa"
    )
    assert "clinic_id = $2::uuid" in pool.sql
    assert pool.args is not None and pool.args[2] == "bấm nhầm khách"


def test_dong_chua_hoan_tac_thi_bao_ro() -> None:
    with pytest.raises(NotFoundError):
        _goi(_Pool(ghi_duoc=False), "khách đổi ý")


@pytest.mark.parametrize("ly_do", ["", "   ", "x" * 501])
def test_ly_do_rong_hoac_qua_dai_bi_chan(ly_do: str) -> None:
    pool = _Pool(ghi_duoc=True)
    with pytest.raises(ValidationError):
        _goi(pool, ly_do)
    assert pool.sql is None, "chặn từ cửa thì không được chạm database"
