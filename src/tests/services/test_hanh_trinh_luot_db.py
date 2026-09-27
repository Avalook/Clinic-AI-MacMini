"""Đường đọc dải mốc hành trình (lát 5) trên DB thật."""

from __future__ import annotations

import asyncpg
import pytest

import clinicai.events.consumers.dong_thoi_gian  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.phieu_kham.hanh_trinh import doc_hanh_trinh
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_luot_dang_kham_co_moc_va_dang_o(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    await _kham_va_chi_dinh(pool, ca, visit)
    await chay_hanh_trinh(pool)
    # Mốc đọc projection dòng thời gian — cho bên nhận ấy chạy hết sổ.
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)
    async with pool.acquire() as conn:
        kq = await doc_hanh_trinh(conn, clinic_id=CLINIC, visit_id=visit)
    assert kq is not None
    theo = {m["ma"]: m for m in kq["moc"]}
    assert theo["CHECK_IN"]["trang_thai"] == "xong"
    assert theo["KHAM"]["trang_thai"] == "dang"
    assert [x["lan"] for x in theo["CHI_DINH"]["cac_lan"]] == [1]
    assert theo["THU_TIEN"]["trang_thai"] == "dang"
    assert isinstance(theo["CHI_DINH"]["bat"], str), "thời điểm trả về dạng ISO"
    assert kq["dang_o"]
    # Bảng "Từng dịch vụ" (27/09): mỗi chỉ định một dòng, chưa thu → CHO_THU.
    dv = kq["tung_dich_vu"]
    assert dv and all(d["trang_thai"] == "CHO_THU" for d in dv)
    assert all(d["ten"] and isinstance(d["gui"], str) for d in dv)
    assert all(d["thu"] is None and d["bat_dau"] is None for d in dv)


async def test_luot_cua_phong_kham_khac_tra_none(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        kq = await doc_hanh_trinh(
            conn,
            clinic_id=CLINIC,
            visit_id="00000000-0000-4000-8000-000000000000",
        )
    assert kq is None
