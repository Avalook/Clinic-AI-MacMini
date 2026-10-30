"""Liệu trình — chính sách tiền KHI DỪNG (Tuyền chốt 30/10/2026).

Dây nối ``lieu_trinh_dung_tinh_gia_le`` (/settings/day-noi):
  TẮT (mặc định) "Tính theo giá gói" — buổi đã làm + đang kê × đơn giá gói,
                 hoàn phần trả trước chưa dùng theo đơn giá gói;
  BẬT "Phá gói thì tính lại giá lẻ" — mọi buổi đã dùng × giá lẻ (giá bảng hiện
                 tại), hoàn = đã trả − tổng giá lẻ; âm → chỉ HIỆN số còn thiếu.
Lệnh dừng chụp chính sách lúc bấm: đổi dây giữa chừng không tính lại liệu trình
đã dừng. Giá thử: đơn giá gói ``GIA`` = 1.000đ.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from clinicai.services.lieu_trinh_tien import GIA_GOI, GIA_LE, quyet_toan_dung
from tests.services.test_lieu_trinh_db import (
    GIA,
    LT,
    chi_dinh,
    doc,
    dung_ca,
    lam_xong,
    luot,
)
from tests.services.test_lieu_trinh_tien_db import hoa_don, khoi, lt_da_tra_truoc, thu
from tests.services.test_lieu_trinh_tien_dung_db import (
    bat_bien,
    dung_lt,
    hoan,
    hoan_tac_lt,
    huy,
    mo_lai,
    so,
)
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

DAY = "lieu_trinh_dung_tinh_gia_le"


@asynccontextmanager
async def day_gia_le(pool: asyncpg.Pool, bat: bool) -> AsyncIterator[None]:
    """Đặt dây cho phòng khám thử, trả lại như cũ (mọi bài chung phòng khám)."""
    cu = await pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
        " AND ma = $2",
        CLINIC,
        DAY,
    )
    await dat_day(pool, bat)
    try:
        yield
    finally:
        if cu is None:
            await pool.execute(
                "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid AND ma = $2",
                CLINIC,
                DAY,
            )
        else:
            await dat_day(pool, json.loads(cu))


async def dat_day(pool: asyncpg.Pool, bat: bool) -> None:
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, $2, $3::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = EXCLUDED.gia_tri",
        CLINIC,
        DAY,
        json.dumps(bat),
    )


async def gia_bang(ca: LT, gia: int) -> None:
    await ca.pool.execute(
        "UPDATE service_price SET unit_price = $2 WHERE id = $1::uuid", ca.sp, gia
    )


async def lam_n(ca: LT, n: int) -> None:
    for _i in range(n):
        v = await luot(ca, dieu_tri=True)
        await lam_xong(ca, await chi_dinh(ca, v))


async def qt(ca: LT, lt_id: str) -> dict[str, Any]:
    q = (await doc(ca, lt_id))["quyet_toan"]
    assert q is not None
    return dict(q)


# ── Luật thuần ──────────────────────────────────────────────────────────────


def _qt(**kw: Any) -> dict[str, Any]:
    co_so: dict[str, Any] = {
        "chinh_sach": GIA_GOI,
        "don_gia": 100_000,
        "gia_le": 150_000,
        "phu": 0,
        "phu_chua_lam": 0,
        "le_dung": 0,
        "le_chua_lam": 0,
        "tien_tra_truoc": 0,
        "tien_le": 0,
    }
    return quyet_toan_dung(**{**co_so, **kw})


def test_quyet_toan_gia_goi() -> None:
    q = _qt(phu=2, phu_chua_lam=1, tien_tra_truoc=500_000)
    assert (q["chinh_sach"], q["gia_tri_da_dung"], q["hoan"], q["thieu"]) == (
        GIA_GOI,
        200_000,
        300_000,
        0,
    )
    assert q["cau"] == (
        "Tính theo giá gói: đã trả trước 500.000đ; đã dùng 2 buổi (1 đã làm, 1 đang"
        " kê) × 100.000đ = 200.000đ; hoàn 300.000đ. Khách không làm buổi đang kê"
        " thì huỷ chỉ định — số hoàn tự tính lại."
    )


def test_quyet_toan_gia_le_hoan_thieu_va_khong_co_gia() -> None:
    q = _qt(chinh_sach=GIA_LE, phu=5, tien_tra_truoc=1_000_000, gia_le=300_000)
    assert (q["gia_tri_da_dung"], q["hoan"], q["thieu"]) == (1_500_000, 0, 500_000)
    assert q["cau"] == (
        "Phá gói, tính lại giá lẻ: 5 buổi (5 đã làm) × 300.000đ giá lẻ ="
        " 1.500.000đ; đã trả 1.000.000đ; khách còn thiếu 500.000đ — máy không tự"
        " đòi, thu ngân quyết. Giá lẻ = giá trên bảng giá hiện tại."
    )
    q = _qt(
        chinh_sach=GIA_LE,
        phu=2,
        le_dung=1,
        tien_tra_truoc=500_000,
        tien_le=100_000,
        gia_le=130_000,
    )
    assert (q["gia_tri_da_dung"], q["hoan"]) == (390_000, 210_000)
    assert "đã trả 600.000đ (trả trước 500.000đ + thu lẻ 100.000đ)" in q["cau"]
    assert q["cau"].endswith("Bấm [Hoàn tiền] dòng trả trước: 2,1 buổi.")
    # Bảng giá không có giá → tính theo giá gói, câu nói rõ.
    q = _qt(chinh_sach=GIA_LE, gia_le=None, phu=1, tien_tra_truoc=300_000)
    assert (q["chinh_sach"], q["hoan"]) == (GIA_GOI, 200_000)
    assert q["cau"].startswith("Không có giá lẻ trên bảng giá — tính theo giá gói:")


# ── DB ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_mac_dinh_gia_goi_buoi_dang_ke_tinh_gia_goi(pool: asyncpg.Pool) -> None:
    """Mặc định: trả trước 5, làm 1, buổi 2 đang kê → hộp dừng xem trước "hoàn
    3.000đ" (buổi đang kê tính giá gói); dừng → quầy đọc đúng câu ấy; khách
    không làm buổi 2 → huỷ → hoàn 4.000đ, đúng số máy chủ cho hoàn."""
    ca = await dung_ca(pool)
    async with day_gia_le(pool, False):
        lt, _ = await lt_da_tra_truoc(ca, 10, 5)
        await lam_n(ca, 1)
        v2 = await luot(ca, dieu_tri=True)
        o2 = await chi_dinh(ca, v2)
        xem = await qt(ca, lt["id"])
        assert (xem["chinh_sach"], xem["hoan"]) == (GIA_GOI, 3 * GIA)
        assert xem["cau"].startswith(
            "Tính theo giá gói: đã trả trước 5.000đ; đã dùng 2 buổi (1 đã làm, 1"
            " đang kê) × 1.000đ = 2.000đ; hoàn 3.000đ."
        )
        await dung_lt(ca, lt["id"])
        assert (await doc(ca, lt["id"]))["chinh_sach_dung"] == GIA_GOI
        k = await khoi(ca, v2, lt["id"])
        assert k["cau_hoan"] == (
            f"{xem['cau']} Hoàn bằng [Hoàn tiền] ở tab “Đã thanh toán”."
        )
        assert k["quyet_toan"]["hoan"] == 3 * GIA
        assert (await hoa_don(ca, v2)).dong == []
        await huy(ca, o2)
        k = await khoi(ca, v2, lt["id"])
        assert (k["quyet_toan"]["hoan"], k["hoan_duoc_toi_da"]) == (4 * GIA, 4)
        await hoan(ca, k["dong_hoan_duoc"][0], 4)
        assert (await qt(ca, lt["id"]))["hoan"] == 0
        await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_pha_goi_gia_le_va_doi_cai_dat_giua_chung(pool: asyncpg.Pool) -> None:
    """Dây BẬT: trả trước 5, làm 2, giá bảng 1.300đ → 2 × 1.300 = 2.600; hoàn
    2.400đ = 2,4 buổi — máy chủ cho hoàn đúng số ấy. Tắt dây SAU khi dừng →
    liệu trình đã dừng vẫn tính giá lẻ; liệu trình dừng sau thì giá gói. Mở lại
    rồi hoàn tác mở lại → về đúng lần dừng cũ (giá lẻ)."""
    ca = await dung_ca(pool)
    async with day_gia_le(pool, True):
        lt, _ = await lt_da_tra_truoc(ca, 10, 5)
        await lam_n(ca, 2)
        await gia_bang(ca, 1_300)
        xem = await qt(ca, lt["id"])
        assert (xem["chinh_sach"], xem["gia_tri_da_dung"], xem["hoan"]) == (
            GIA_LE,
            2_600,
            2_400,
        )
        await dung_lt(ca, lt["id"])
        await dat_day(pool, False)
        q = await qt(ca, lt["id"])
        assert (q["chinh_sach"], q["hoan"]) == (GIA_LE, 2_400)
        assert q["cau"] == (
            "Phá gói, tính lại giá lẻ: 2 buổi (2 đã làm) × 1.300đ giá lẻ = 2.600đ;"
            " đã trả 5.000đ; hoàn 2.400đ. Giá lẻ = giá trên bảng giá hiện tại."
            " Bấm [Hoàn tiền] dòng trả trước: 2,4 buổi."
        )
        # Mở lại: xem trước theo dây HIỆN TẠI (đã tắt); hoàn tác mở lại → về
        # đúng lần dừng cũ, chính sách cũ.
        await mo_lai(ca, lt["id"])
        assert (await qt(ca, lt["id"]))["chinh_sach"] == GIA_GOI
        await hoan_tac_lt(ca, lt["id"])
        assert (await qt(ca, lt["id"]))["chinh_sach"] == GIA_LE

        # Liệu trình khác dừng SAU khi tắt dây → giá gói.
        ca2 = await dung_ca(pool)
        lt2, _ = await lt_da_tra_truoc(ca2, 10, 5)
        await lam_n(ca2, 2)
        await gia_bang(ca2, 1_300)
        await dung_lt(ca2, lt2["id"])
        q2 = await qt(ca2, lt2["id"])
        assert (q2["chinh_sach"], q2["hoan"]) == (GIA_GOI, 3 * GIA)

        # Máy chủ cho hoàn đúng 2,4 buổi = 2.400đ.
        v = await luot(ca, dieu_tri=True)
        k = await khoi(ca, v, lt["id"])
        (dong,) = k["dong_hoan_duoc"]
        r = await hoan(ca, dong, 2.4)  # type: ignore[arg-type]
        assert int(r["amount"]) == 2_400
        assert (await qt(ca, lt["id"]))["hoan"] == 0
        await bat_bien(ca, lt["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_pha_goi_khach_con_thieu_chi_hien_khong_tu_doi(
    pool: asyncpg.Pool,
) -> None:
    """Dây BẬT: trả trước 2, làm 2 (phủ) + buổi 3 thu lẻ đã làm, giá bảng
    2.000đ → 3 × 2.000 = 6.000; đã trả 3.000 → khách còn thiếu 3.000đ: quầy HIỆN,
    không thêm dòng nào vào hoá đơn."""
    ca = await dung_ca(pool)
    async with day_gia_le(pool, True):
        lt, _ = await lt_da_tra_truoc(ca, 5, 2)
        await lam_n(ca, 2)
        v3 = await luot(ca, dieu_tri=True)
        o3 = await chi_dinh(ca, v3)
        await thu(ca, v3)
        await lam_xong(ca, o3)
        await gia_bang(ca, 2_000)
        await dung_lt(ca, lt["id"])
        k = await khoi(ca, v3, lt["id"])
        q = k["quyet_toan"]
        assert so(q, "chinh_sach", "gia_tri_da_dung", "da_tra", "hoan", "thieu") == (
            GIA_LE,
            6_000,
            3_000,
            0,
            3_000,
        )
        assert "(trả trước 2.000đ + thu lẻ 1.000đ)" in q["cau"]
        assert "khách còn thiếu 3.000đ — máy không tự đòi, thu ngân quyết." in q["cau"]
        assert (await hoa_don(ca, v3)).dong == []
        await bat_bien(ca, lt["id"])
