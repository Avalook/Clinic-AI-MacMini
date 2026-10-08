"""Liệu trình C2 (08/10/2026) — dữ liệu cho màn CSKH / khung khách / chip / bản in
và dọn khách thử có liệu trình.

    scripts/test-nhanh.sh src/tests/services/test_lieu_trinh_c2_db.py

Đặc tả: ``docs/KE-HOACH-LIEU-TRINH.md`` (luồng CSKH, chip phòng / tiếp đón, bản
in) + migration 20261008200000 (``don_khach_thu`` biết 4 bảng liệu trình).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from tests.services.test_lieu_trinh_db import (
    buoi_song,
    chi_dinh,
    dung_ca,
    lam_xong,
    luot,
)
from tests.services.test_lieu_trinh_tien_db import lt_da_tra_truoc
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

BANG_LIEU_TRINH = (
    "lieu_trinh",
    "lieu_trinh_lich_su",
    "lieu_trinh_buoi",
    "lieu_trinh_tra_truoc",
)


def _jsonb(v: Any) -> dict[str, Any]:
    return json.loads(v) if isinstance(v, str) else dict(v)


async def _khach_co_lieu_trinh(
    pool: asyncpg.Pool,
) -> tuple[Any, dict[str, Any], str, str]:
    """Khách có liệu trình 5 buổi, đã trả trước 3, buổi 1 (phủ) ĐÃ làm ở lượt 3.
    Trả (ca, liệu trình, lượt 3, chỉ định buổi 1)."""
    ca = await dung_ca(pool)
    lt, _lan_thu = await lt_da_tra_truoc(ca, 5, 3)
    v3 = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v3)
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"] and b["tra_truoc"] is True
    await lam_xong(ca, o)
    return ca, lt, v3, o


@pytest.mark.db
@pytest.mark.asyncio
async def test_du_lieu_man_cskh_chip_va_ban_in(pool: asyncpg.Pool) -> None:
    """Khung khách: loại khám để đặt lịch buổi kế + cờ quyền CSKH; chip theo
    lượt mang mã lượt; bản in phiếu khám có "buổi k/N" của chỉ định."""
    ca, lt, v3, o = await _khach_co_lieu_trinh(pool)

    kh = await ca.svc.theo_khach(identity=ca.cskh, clinic_patient_id=ca.khach)
    assert kh["quyen_cskh"] is True
    (x,) = kh["lieu_trinh"]
    assert x["id"] == lt["id"] and x["service_type_id"] == ca.st
    assert (x["so_buoi"], x["da_lam"], x["da_tra"], x["con_tra_truoc"]) == (5, 1, 3, 2)

    chip = await ca.svc.chip(identity=ca.le_tan, visit_ids=f"{v3},rac")
    c = chip["chi_dinh"][o]
    assert c["visit_id"] == v3 and c["lieu_trinh_id"] == lt["id"]
    assert (c["buoi_so"], c["so_buoi"], c["tra_truoc"]) == (1, 5, True)
    (k,) = chip["khach"][v3]
    assert k["con_tra_truoc"] == 2 and k["service_name"] == ca.ten

    # CSKH "đang dở": danh sách có loại khám để mở bộ đặt lịch.
    ds = await ca.svc.cskh(identity=ca.cskh, loai="dang_do", qua_ngay="0")
    mot = [d for d in ds["lieu_trinh"] if d["id"] == lt["id"]]
    assert all(d["service_type_id"] == ca.st for d in mot)

    async with pool.acquire() as conn:
        kq = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=v3)
    (dong,) = [d for d in kq if d["service_order_id"] == o]
    assert dong["dieu_tri"] is True
    assert dong["lieu_trinh"] == {"buoi_so": 1, "so_buoi": 5, "tra_truoc": True}

    # Lượt không có buổi liệu trình → None (bản in không thêm dòng).
    v4 = await luot(ca)
    o4 = await chi_dinh(ca, v4, chon="NOT_SELECTED")
    async with pool.acquire() as conn:
        kq4 = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=v4)
    (d4,) = [d for d in kq4 if d["service_order_id"] == o4]
    assert d4["lieu_trinh"] is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_don_khach_thu_co_lieu_trinh_tra_truoc_va_buoi_da_lam(
    pool: asyncpg.Pool,
) -> None:
    """Dọn khách thử có liệu trình (trả trước 3 buổi, buổi 1 đã làm) + ghi chú
    lượt: xem trước liệt kê đủ 4 bảng liệu trình; làm thật xoá sạch, lưu bản
    xoá, không trigger nào còn tắt (trước migration 20261008200000: Chốt 1 dừng
    "lieu_trinh → patient")."""
    ca, lt, v3, _o = await _khach_co_lieu_trinh(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO luot_ghi_chu (clinic_id, visit_id, phien_ban, noi_dung,"
            " ghi_boi) VALUES ($1::uuid, $2::uuid, 1, 'ghi chú thử', $3::uuid)",
            CLINIC,
            v3,
            ca.bac_si.staff_id,
        )
        xem = _jsonb(
            await conn.fetchval(
                "SELECT public.don_khach_thu($1::uuid, ARRAY[$2::uuid], false)",
                CLINIC,
                ca.khach,
            )
        )
        assert xem["lam_that"] is False
        so = xem["so_dong"]
        assert so["lieu_trinh"] == 1
        assert so["lieu_trinh_buoi"] == 1 and so["lieu_trinh_tra_truoc"] == 1
        assert so["lieu_trinh_lich_su"] >= 1 and so["luot_ghi_chu"] == 1

        async with conn.transaction():
            kq = _jsonb(
                await conn.fetchval(
                    "SELECT public.don_khach_thu($1::uuid, ARRAY[$2::uuid], true,"
                    " NULL, $3::uuid, 'Test', 'man_quan_tri')",
                    CLINIC,
                    ca.khach,
                    ca.bac_si.staff_id,
                )
            )
        assert kq["lam_that"] is True
        for bang in BANG_LIEU_TRINH:
            con = await conn.fetchval(
                f"SELECT count(*) FROM {bang} WHERE lieu_trinh_id = $1::uuid"  # noqa: S608
                if bang != "lieu_trinh"
                else "SELECT count(*) FROM lieu_trinh WHERE id = $1::uuid",
                lt["id"],
            )
            assert con == 0, bang
        luu = await conn.fetch(
            "SELECT bang, count(*) AS n FROM du_lieu_da_xoa WHERE lan_id = $1::uuid"
            " GROUP BY bang",
            kq["lan_id"],
        )
        theo = {r["bang"]: r["n"] for r in luu}
        for bang in (*BANG_LIEU_TRINH, "luot_ghi_chu", "patient", "visit"):
            assert theo.get(bang, 0) >= 1, bang
        assert not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM patient WHERE clinic_patient_id = $1::uuid)",
            ca.khach,
        )
        # Trigger chỉ-thêm của lịch sử liệu trình bật lại sau khi dọn.
        assert (
            await conn.fetchval(
                "SELECT tgenabled FROM pg_trigger"
                " WHERE tgname = 'trg_lieu_trinh_lich_su_chi_them'"
            )
            != "D"
        )
