"""17 mẫu kết quả v3 theo PDF gốc + tệp theo bên (Tuyền 26/09/2026 — lát 3).

Mục dạng BẢNG (Thai A | Thai B, trái | phải) khai `cot`; giá trị một ô là
{ma_cột: giá trị} — lưu theo `ma`, không theo vị trí như bản giao diện mẫu.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.v1.routers.cskh import _ben_tep, _cach_mo_tep
from clinicai.services.form_engine_service import FormEngineService, _con_trong
from tests.services.test_form_engine_db import (
    CLINIC,
    _don_tron,
    _nguoi,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khung(pool: asyncpg.Pool, form_id: str) -> list[dict[str, Any]]:  # noqa: F811
    khung: list[dict[str, Any]] = json.loads(
        await pool.fetchval(
            "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
            " AND form_id = $2 AND trang_thai = 'PUBLISHED'",
            CLINIC,
            form_id,
        )
    )
    return khung


async def test_mau_v3_co_muc_bang_va_khong_dien_san_so_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    song = await _khung(pool, "KQ_SA_SONG_THAI_QUY_1")
    bang = [m for m in song if m.get("cot")]
    assert bang and [c["ten"] for c in bang[0]["cot"]] == ["Thai A", "Thai B"]
    # Số đo (có đơn vị) và ô trong bảng không điền sẵn.
    assert not any(b.get("mac_dinh") for m in bang for b in m["block"])
    assert not any(
        b.get("mac_dinh") for m in song for b in m["block"] if b.get("goi_y")
    )
    # Mẫu Gemini (BI-RADS) không còn trong v3.
    vu = await _khung(pool, "KQ_SA_VU")
    assert "birads" not in {b["ma"] for m in vu for b in m["block"]}
    # Mã ô duy nhất trong cả phiếu (du_lieu phẳng theo mã ô).
    for fid in ("KQ_SA_SONG_THAI_QUY_1", "KQ_SA_VU", "KQ_XN_PCR_STDS"):
        ma = [b["ma"] for m in await _khung(pool, fid) for b in m["block"]]
        assert len(ma) == len(set(ma)), fid


async def test_gan_mau_theo_ma_phong_kham_chay_lai_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan2 = await pool.fetchval("SELECT public.gan_mau_ket_qua_theo_kiotviet()")
    assert lan2 == 0


async def test_luu_o_bang_theo_ma_cot(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    svc = FormEngineService(pool)
    p = await svc.mo_phieu(
        service_order_id=order, form_id="KQ_SA_SONG_THAI_QUY_1", identity=bs
    )
    muc = next(m for m in p["khung"] if m.get("cot"))
    o = muc["block"][0]["ma"]
    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={o: {"gia_tri": {"thai_a": "45", "thai_b": "47"}, "nguon": "USER"}},
        expected_revision=p["revision"],
        identity=bs,
    )
    lai = await svc.mo_phieu(
        service_order_id=order, form_id="KQ_SA_SONG_THAI_QUY_1", identity=bs
    )
    assert lai["du_lieu"][o]["gia_tri"] == {"thai_a": "45", "thai_b": "47"}
    # Ô bảng mà mọi cột trống thì tính là chưa điền.
    trong = _con_trong(
        lai["khung"], {o: {"gia_tri": {"thai_a": "", "thai_b": ""}, "nguon": "USER"}}
    )
    assert muc["block"][0]["ten"] in trong


async def test_ben_tep_va_ten_tai_ve() -> None:
    assert _ben_tep(None) is None and _ben_tep("") is None
    assert _ben_tep("1") == 1
    for rac in ("-1", "9", "abc", "1; drop"):
        with pytest.raises(ValidationError):
            _ben_tep(rac)
    assert _cach_mo_tep("Ảnh thai A.jpg", False) == "inline"
    tai = _cach_mo_tep("Ảnh thai A.jpg", True)
    assert tai.startswith("attachment;") and "UTF-8''" in tai
    assert "\n" not in _cach_mo_tep("a\nb", True)
