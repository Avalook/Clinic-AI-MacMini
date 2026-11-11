"""Gmail G6 — SPF khớp miền được nhận là xác thực; thư đã xếp oan "không xác thực" được
xét lại một lần bằng byte đã lưu (chạy thật trên DB, Gmail GIẢ).

Ca biên: thư chỉ có SPF khớp miền (HighDetect) ⇒ tự gán ngay; thư đã cất Lưu trữ
KHONG_XAC_THUC ⇒ `xet_lai` gán vào đúng chỉ định; header vẫn hỏng ⇒ để nguyên; người gửi
không còn là email đối tác ⇒ bỏ qua; chạy lại lần hai ⇒ không làm gì thêm.
"""

from __future__ import annotations

import dataclasses

import asyncpg
import pytest

from clinicai.services.xet_nghiem import gmail, gmail_xet_lai
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import (  # noqa: F401
    Ca3,
    _dong,
    _to_cua,
    c3,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

HONG = "mx.google.com; dkim=pass header.i=@lab-thu-vn.20260707.gappssmtp.com"


def _spf(c3: Ca3) -> str:  # noqa: F811
    """Khuôn HighDetect: DKIM miền mặc định Google, SPF khớp miền người gửi."""
    return HONG + f"; spf=pass smtp.mailfrom={c3.g.email}"


async def test_spf_khop_mien_thi_tu_gan_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v = await c3.viec(pool)
    mid = c3.thu(v["ten"], v["sdt"], xac_thuc=_spf(c3))
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] is None and d["tep_ket_qua_id"] is not None


async def test_xet_lai_thu_xep_oan_thi_gan_vao_dung_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v = await c3.viec(pool)
    mid = c3.thu(v["ten"], v["sdt"], xac_thuc=HONG)  # luật cũ: chỉ DKIM gappssmtp
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert (d["ly_do_cho"], d["luu_tru_vi_sao"]) == ("LUU_TRU", "KHONG_XAC_THUC")
    # Gmail đọc lại thấy SPF khớp miền (header thật vốn có — luật G3 bỏ sót).
    c3.g.thu[mid] = dataclasses.replace(c3.g.thu[mid], xac_thuc=_spf(c3))
    dem = await gmail_xet_lai.xet_lai(pool, None, CLINIC)  # type: ignore[arg-type]
    assert dem.get("tu_gan") == 1
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] is None and d["luu_tru_vi_sao"] is None
    assert [tuple(r) for r in await _to_cua(pool, v["oid"])] == [
        ("GMAIL", "CHO_XAC_NHAN")
    ]
    # Chạy lại ⇒ không còn dòng nào để xét.
    assert (await gmail_xet_lai.xet_lai(pool, None, CLINIC)).get("tu_gan") is None  # type: ignore[arg-type]


async def test_xet_lai_van_khong_xac_thuc_hoac_nguoi_gui_khac_thi_de_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v = await c3.viec(pool)
    hong = c3.thu(v["ten"], v["sdt"], xac_thuc=HONG)
    await gmail.mot_vong(pool)
    gia = c3.thu(v["ten"], v["sdt"], xac_thuc=HONG)
    await gmail.mot_vong(pool)
    # Thư thứ hai: Gmail đọc lại thấy người gửi KHÁC email đối tác ⇒ không đụng.
    c3.g.thu[gia] = dataclasses.replace(
        c3.g.thu[gia], xac_thuc=_spf(c3), tu="ke-gian@lab-thu.vn"
    )
    dem = await gmail_xet_lai.xet_lai(pool, None, CLINIC)  # type: ignore[arg-type]
    assert dem.get("van_khong_xac_thuc") == 1 and dem.get("bo_qua") == 1
    for mid in (hong, gia):
        d = await _dong(pool, mid)
        assert (d["ly_do_cho"], d["luu_tru_vi_sao"]) == ("LUU_TRU", "KHONG_XAC_THUC")
    assert await _to_cua(pool, v["oid"]) == []
