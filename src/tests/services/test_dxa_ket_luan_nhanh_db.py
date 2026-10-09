"""Phiếu đo mật độ xương + "Kết luận nhanh" (Tuyền 29/09/2026).

"Ở phiếu ĐO MẬT ĐỘ XƯƠNG thì có thêm 3 checkbox: Bình thường, Tiền loãng
xương, Loãng xương, để người thao tác tích nhanh — nhớ là nó được LƯU, và IN
ra nữa." Migration 20260929000010 (hàm `dxa_ket_luan_nhanh`).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.phieu_kham.kiem_khung_mau import kiem_khung_mau
from clinicai.phieu_kham.mau_goi_y import mau_cho_dich_vu
from clinicai.services.form_engine_service import FormEngineService
from tests.services.test_form_engine_db import (
    CLINIC,
    _don_tron,
    _nguoi,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

FORM = "KQ_DO_MAT_DO_XUONG"
LUA_CHON = ["Bình thường", "Tiền loãng xương", "Loãng xương"]


async def _khung(conn: Any, form_id: str = FORM) -> list[dict[str, Any]]:
    khung: list[dict[str, Any]] = json.loads(
        await conn.fetchval(
            "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
            " AND form_id = $2 AND trang_thai = 'PUBLISHED'",
            CLINIC,
            form_id,
        )
    )
    return khung


def _o(khung: list[dict[str, Any]], ma: str) -> dict[str, Any] | None:
    return next((o for m in khung for o in m["block"] if o["ma"] == ma), None)


async def test_mau_dxa_co_o_ket_luan_nhanh_ngay_duoi_mo_ta(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    # Từ 09/10/2026 (20261009700000): một mục "Mô tả" = ô Mô tả (tuỳ chọn) + ô
    # tích ngay dưới; không còn Kết luận chữ / Đề nghị.
    khung = await _khung(pool)
    [mo_ta] = khung
    assert mo_ta["ten"] == "Mô tả"
    assert [x["ma"] for x in mo_ta["block"]] == ["noi_dung", "ket_luan_nhanh"]
    o = mo_ta["block"][1]
    assert o["ma"] == "ket_luan_nhanh" and o["ten"] == "Kết luận nhanh"
    # CHỌN MỘT (một chuỗi), vẽ thành ô tích nhanh.
    assert o["kieu"] == "chon" and o["chon"] == LUA_CHON
    assert o["hien_thi"] == "o_tick"
    assert "mac_dinh" not in o  # kết luận lâm sàng không bao giờ điền sẵn
    # Khung qua được đúng luật xuất bản — sửa mẫu ở Cài đặt không bị chặn.
    assert kiem_khung_mau(khung) == khung


async def test_mau_chung_khong_doi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Ô loãng xương KHÔNG lọt vào mẫu CHUNG (Laser, Biofeedback, thủ thuật…)."""
    assert _o(await _khung(pool, "KQ_CHUNG"), "ket_luan_nhanh") is None


async def test_dich_vu_dxa_chon_san_mau_dxa(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND ma_kiotviet = 'SP000134' AND \"group\" = 'dich_vu'",
            CLINIC,
        )
        assert dv == "CLS_DO_MAT_DO_XUONG"
        mau, chon_san = await mau_cho_dich_vu(conn, clinic_id=CLINIC, service_code=dv)
    assert chon_san == "DO_MAT_DO_XUONG"
    assert [m["ma"] for m in mau] == ["DO_MAT_DO_XUONG"]


async def test_chay_lai_khong_doi_gi(pool: asyncpg.Pool) -> None:  # noqa: F811
    # Lần đầu có thể còn việc: test khác trong cùng DB dựng thêm phòng khám
    # (hàm dựng mẫu cho MỌI phòng khám). Lần kế tiếp thì không còn gì để làm.
    await pool.fetchval("SELECT public.dxa_ket_luan_nhanh()")
    assert await pool.fetchval("SELECT public.dxa_ket_luan_nhanh()") == 0


async def test_tich_luu_mo_lai_hoan_tat_va_in(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    svc = FormEngineService(pool)
    p = await svc.mo_phieu(service_order_id=order, form_id=FORM, identity=bs)
    assert "ket_luan_nhanh" not in p["du_lieu"]  # mở ra: chưa tích ô nào

    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={
            "ket_luan_nhanh": {"gia_tri": "Tiền loãng xương", "nguon": "USER"},
            "noi_dung": {"gia_tri": "T-score cột sống -1,8.", "nguon": "USER"},
        },
        expected_revision=p["revision"],
        identity=bs,
    )
    lai = await svc.mo_phieu(service_order_id=order, form_id=FORM, identity=bs)
    assert lai["du_lieu"]["ket_luan_nhanh"]["gia_tri"] == "Tiền loãng xương"

    # Bỏ tích (bấm lại ô đang tích) = chuỗi rỗng → tính là còn trống.
    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={
            "ket_luan_nhanh": {"gia_tri": "", "nguon": "USER"},
            "noi_dung": {"gia_tri": "T-score cột sống -1,8.", "nguon": "USER"},
        },
        expected_revision=lai["revision"],
        identity=bs,
    )
    lai = await svc.mo_phieu(service_order_id=order, form_id=FORM, identity=bs)
    assert "Kết luận nhanh" in lai["con_trong"]

    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={
            "ket_luan_nhanh": {"gia_tri": "Loãng xương", "nguon": "USER"},
            "noi_dung": {"gia_tri": "T-score cột sống -2,7.", "nguon": "USER"},
        },
        expected_revision=lai["revision"],
        identity=bs,
    )
    lai = await svc.mo_phieu(service_order_id=order, form_id=FORM, identity=bs)
    await svc.hoan_tat(
        phieu_id=p["id"],
        expected_revision=lai["revision"],
        identity=bs,
        thuc_hien_boi=bs.staff_id,
    )

    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    [to] = ban["phieu"]
    assert to["form_id"] == FORM and to["ban_nhap"] is False
    assert to["du_lieu"]["ket_luan_nhanh"]["gia_tri"] == "Loãng xương"
    # Bản in vẽ theo khung của chính phiếu: ô tích nằm trong mục Mô tả, ngay
    # dưới ô Mô tả (chuyển mục 09/10/2026 — bản in vẫn thấy nó).
    [mo_ta] = to["khung"]
    assert [o["ma"] for o in mo_ta["block"]] == ["noi_dung", "ket_luan_nhanh"]


async def test_mau_dxa_phong_kham_tu_sua_chi_duoc_them_o(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Phòng khám đã tự xuất bản mẫu DXA (thiếu ô) → hàm chỉ THÊM ô vào mục Kết
    luận ở bản mới, giữ nguyên mọi thứ khác; không có mục Kết luận thì thêm mục
    "Kết luận nhanh" ở cuối. Làm trong giao dịch rồi huỷ — không để lại gì."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "MANAGEMENT")
        tr = conn.transaction()
        await tr.start()
        try:
            for khung_cu, muc_co_o in (
                (
                    [
                        {
                            "ma": "do",
                            "ten": "Chỉ số đo",
                            "block": [
                                {"ma": "t_score", "ten": "T-score", "kieu": "text"}
                            ],
                        },
                        {
                            "ma": "ket_luan",
                            "ten": "Kết luận",
                            "block": [
                                {
                                    "ma": "ket_luan",
                                    "ten": "Kết luận",
                                    "kieu": "doan_van",
                                    "mac_dinh": "Bình thường.",
                                }
                            ],
                        },
                    ],
                    "ket_luan",
                ),
                (
                    [
                        {
                            "ma": "do",
                            "ten": "Chỉ số đo",
                            "block": [
                                {"ma": "t_score", "ten": "T-score", "kieu": "text"}
                            ],
                        }
                    ],
                    "ket_luan_nhanh",
                ),
            ):
                await conn.execute(
                    "UPDATE form_definition SET trang_thai = 'RETIRED'"
                    " WHERE clinic_id = $1::uuid AND form_id = $2"
                    "   AND trang_thai = 'PUBLISHED'",
                    CLINIC,
                    FORM,
                )
                ban_cu = await conn.fetchval(
                    "INSERT INTO form_definition (clinic_id, form_id, version, ten,"
                    " nhom, khung, trang_thai, xuat_ban_boi, xuat_ban_luc)"
                    " SELECT $1::uuid, $2, max(version) + 1, 'Mẫu tự sửa', 'X',"
                    "        $3::jsonb, 'PUBLISHED', $4::uuid, now()"
                    "   FROM form_definition WHERE clinic_id = $1::uuid"
                    "    AND form_id = $2 RETURNING version",
                    CLINIC,
                    FORM,
                    json.dumps(khung_cu, ensure_ascii=False),
                    bs.staff_id,
                )
                assert await conn.fetchval("SELECT public.dxa_ket_luan_nhanh()") >= 1
                moi = await _khung(conn)
                muc = next(m for m in moi if m["ma"] == muc_co_o)
                assert muc["block"][0]["ma"] == "ket_luan_nhanh"
                # Mọi thứ phòng khám viết giữ nguyên.
                assert moi[0] == khung_cu[0]
                if muc_co_o == "ket_luan":
                    assert muc["block"][1] == khung_cu[1]["block"][0]
                    assert len(moi) == len(khung_cu)
                else:
                    assert moi[-1]["ten"] == "Kết luận nhanh"
                    assert len(moi) == len(khung_cu) + 1
                # Bản phòng khám tự xuất bản về hưu, không bị sửa tại chỗ.
                assert (
                    await conn.fetchval(
                        "SELECT trang_thai FROM form_definition"
                        " WHERE clinic_id = $1::uuid AND form_id = $2"
                        "   AND version = $3",
                        CLINIC,
                        FORM,
                        ban_cu,
                    )
                    == "RETIRED"
                )
                assert kiem_khung_mau(moi) == moi
        finally:
            await tr.rollback()
