"""Ô tuỳ chọn + đơn vị + mẫu siêu âm thai quý III (Tuyền 09/10/2026).

Migration 20261009300000 (tuy_chon / don_vi cho mọi mẫu KQ_ đang dùng, dựng từ
khung TRONG DB) và 20261009310000 (mẫu SA_THAI_QUY_3 gắn thêm, quý II–III vẫn
chọn sẵn).

Bài nào gọi lại hàm của migration thì chạy TRONG MỘT GIAO DỊCH RỒI HUỶ: hàm
xuất bản bản mới cho mọi mẫu của cả DB — để lại thì đổi số bản dưới chân các
bài khác chạy song song.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import asyncpg
import pytest

import clinicai.phieu_kham as pk
from clinicai.phieu_kham.kiem_khung_mau import kiem_khung_mau
from clinicai.phieu_kham.mau_goi_y import mau_cho_cac_dich_vu
from clinicai.services.form_engine_service import FormEngineService
from tests.services.test_form_engine_db import (
    CLINIC,
    _don_tron,
    _nguoi,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

DON_VI_THUAN = {
    "mm",
    "cm",
    "cm/s",
    "chu kỳ/phút",
    "lần/phút",
    "điểm",
    "%",
    "ml",
    "gram",
    "grams",
}


def _cac_o(khung: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for m in khung for o in m.get("block", [])]


async def _khung_dang_dung(conn: asyncpg.Connection, form_id: str) -> Any:
    return await conn.fetchrow(
        "SELECT version, khung, xuat_ban_boi::text AS boi FROM form_definition"
        " WHERE clinic_id = $1::uuid AND form_id = $2 AND trang_thai = 'PUBLISHED'",
        CLINIC,
        form_id,
    )


async def test_mau_ket_qua_dang_dung_co_tuy_chon_va_don_vi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Sau migration: Đề nghị là ô tuỳ chọn; goi_y đơn vị thuần → don_vi; goi_y
    là gợi ý cách gõ ("tuần + ngày", "PSV cm/s | EDV cm/s | RI") thì KHÔNG."""
    async with pool.acquire() as conn:
        khung = await _khung_dang_dung(conn, "KQ_SA_THAI_QUY_23")
    o = {x["ma"]: x for x in _cac_o(json.loads(khung["khung"]))}
    assert o["de_nghi"]["tuy_chon"] is True
    assert o["duong_kinh_luong_dinh"]["don_vi"] == "mm"
    assert o["duong_kinh_luong_dinh"]["goi_y"] == "mm"  # goi_y giữ nguyên
    assert o["tim_thai"]["don_vi"] == "chu kỳ/phút"
    assert "don_vi" not in o["tuoi_thai_uoc_tinh"]  # "tuần + ngày"
    assert "don_vi" not in o["can_nang_uoc_tinh"]  # "± grams"
    assert "tuy_chon" not in o["ket_luan"]


async def test_mau_sua_tren_man_khong_bi_de_va_chay_lai_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Quản lý đã sửa mẫu trên màn (đổi tên ô, bỏ cờ): migration dựng bản mới TỪ
    BẢN CỦA QUẢN LÝ — giữ tên đã sửa, giữ người xuất bản, chỉ thêm hai cờ."""
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            ql = await _nguoi(conn, "MANAGEMENT")
            hien = await _khung_dang_dung(conn, "KQ_SA_THAI_QUY_23")
            sua = json.loads(hien["khung"])
            for m in sua:
                for o in m["block"]:
                    o.pop("tuy_chon", None)
                    o.pop("don_vi", None)
                    if o["ma"] == "duong_kinh_luong_dinh":
                        o["ten"] = "BPD (quản lý sửa trên màn)"
            # Như `FormEngineService.xuat_ban`: bản cũ về hưu, bản mới của quản lý.
            await conn.execute(
                "UPDATE form_definition SET trang_thai = 'RETIRED'"
                " WHERE clinic_id = $1::uuid AND form_id = 'KQ_SA_THAI_QUY_23'"
                "   AND trang_thai = 'PUBLISHED'",
                CLINIC,
            )
            await conn.execute(
                "INSERT INTO form_definition (clinic_id, form_id, version, ten, nhom,"
                " khung, trang_thai, tao_boi, xuat_ban_boi, xuat_ban_luc)"
                " SELECT $1::uuid, 'KQ_SA_THAI_QUY_23', $2, 'Quý II - III (sửa)', '',"
                " $3::jsonb, 'PUBLISHED', $4::uuid, $4::uuid, now()",
                CLINIC,
                hien["version"] + 1,
                json.dumps(sua, ensure_ascii=False),
                ql.staff_id,
            )

            assert await conn.fetchval("SELECT public.mau_ket_qua_tuy_chon_don_vi()")
            moi = await _khung_dang_dung(conn, "KQ_SA_THAI_QUY_23")
            assert moi["version"] == hien["version"] + 2
            assert moi["boi"] == ql.staff_id  # nội dung vẫn là của quản lý
            o = {x["ma"]: x for x in _cac_o(json.loads(moi["khung"]))}
            assert o["duong_kinh_luong_dinh"]["ten"] == "BPD (quản lý sửa trên màn)"
            assert o["duong_kinh_luong_dinh"]["don_vi"] == "mm"
            assert o["de_nghi"]["tuy_chon"] is True
            assert kiem_khung_mau(json.loads(moi["khung"])) == json.loads(moi["khung"])
            assert (
                await conn.fetchval(
                    "SELECT trang_thai FROM form_definition WHERE clinic_id = $1::uuid"
                    " AND form_id = 'KQ_SA_THAI_QUY_23' AND version = $2",
                    CLINIC,
                    hien["version"] + 1,
                )
                == "RETIRED"
            )

            # Chạy lại: khung đã đủ cờ → không ra bản mới.
            await conn.fetchval("SELECT public.mau_ket_qua_tuy_chon_don_vi()")
            lai = await _khung_dang_dung(conn, "KQ_SA_THAI_QUY_23")
            assert lai["version"] == moi["version"]
        finally:
            await tr.rollback()


async def test_hoan_tat_khong_nhac_de_nghi_va_in_co_don_vi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order_id = await _don_tron(conn, bs)
    svc = FormEngineService(pool)
    p = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_THAI_QUY_23", identity=bs
    )
    luu = await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={
            **p["du_lieu"],
            "duong_kinh_luong_dinh": {"gia_tri": "89.6", "nguon": "USER"},
        },
        expected_revision=p["revision"],
        identity=bs,
    )
    xong = await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=luu["revision"], identity=bs
    )
    # Đề nghị trống KHÔNG bị nhắc; số đo trống vẫn được nhắc (không chặn).
    assert "Đề nghị / lời dặn" not in xong["con_trong"]
    assert "Chu vi vòng đầu (HC)" in xong["con_trong"]
    assert "Đường kính lưỡng đỉnh (BPD)" not in xong["con_trong"]

    # Bản in nhận khung có `don_vi` (màn in nối " mm" — `giaKemDonVi`).
    in_ra = await svc.in_ket_qua(service_order_id=order_id, identity=bs)
    phieu = in_ra["phieu"][0]
    o = {x["ma"]: x for x in _cac_o(phieu["khung"])}
    assert o["duong_kinh_luong_dinh"]["don_vi"] == "mm"
    assert phieu["du_lieu"]["duong_kinh_luong_dinh"]["gia_tri"] == "89.6"


async def test_mau_quy_3_gan_them_va_quy_23_van_chon_san(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        k = await conn.fetchrow(
            "SELECT ten, active FROM ket_qua_mau"
            " WHERE clinic_id = $1::uuid AND ma = 'SA_THAI_QUY_3'",
            CLINIC,
        )
        assert k is not None and k["active"]
        assert k["ten"] == "Kết quả siêu âm thai quý III"
        d = await _khung_dang_dung(conn, "KQ_SA_THAI_QUY_3")
        khung = json.loads(d["khung"])
        assert [m["ten"] for m in khung] == [
            "Mô tả hình ảnh",
            "Tham số sinh học",
            "Phần phụ thai nhi",
            "Hình ảnh khác",
            "Kết luận",
        ]
        assert kiem_khung_mau(khung) == khung
        o = {x["ma"]: x for x in _cac_o(khung)}
        assert "de_nghi" not in o  # PDF không có Đề nghị
        assert o["so_luong_thai_trong_buong_tu_cung"]["don_vi"] == "thai"
        assert o["can_nang_uoc_tinh"]["don_vi"] == "grams"
        # Số đo không điền sẵn (an toàn lâm sàng như v3).
        assert not any(x.get("mac_dinh") for x in o.values() if x.get("don_vi") == "mm")
        # Khung DB = khung JSON seed (một nguồn).
        v3 = json.loads(
            (Path(pk.__file__).parent / "mau_ket_qua_v3.json").read_text("utf-8")
        )["mau"]
        assert v3["SA_THAI_QUY_3"]["khung"] == khung
        assert v3["SA_THAI_QUY_3"]["kv"] == v3["SA_THAI_QUY_23"]["kv"]

        tr = conn.transaction()
        await tr.start()
        try:
            # Gọi lại (như seed.sql) để gắn cả dịch vụ bài khác vừa gắn quý II–III.
            await conn.fetchval("SELECT public.gan_mau_sa_thai_quy_3()")
            assert await conn.fetchval("SELECT public.gan_mau_sa_thai_quy_3()") == 0
            gan = await conn.fetch(
                "SELECT service_code, mau, result_mode, thu_tu"
                "  FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
                "   AND mau IN ('SA_THAI_QUY_23', 'SA_THAI_QUY_3')",
                CLINIC,
            )
            q23 = {r["service_code"]: r for r in gan if r["mau"] == "SA_THAI_QUY_23"}
            q3 = {r["service_code"]: r for r in gan if r["mau"] == "SA_THAI_QUY_3"}
            assert q23, "khuôn phải có dịch vụ gắn quý II–III (seed)"
            assert set(q3) == set(q23)
            for ma, r in q3.items():
                assert r["result_mode"] == q23[ma]["result_mode"]
                assert r["thu_tu"] > q23[ma]["thu_tu"]

            chon = await mau_cho_cac_dich_vu(
                conn, clinic_id=CLINIC, service_codes=list(q23)
            )
            for ma, kq in chon.items():
                ds = [m["ma"] for m in kq["mau"]]
                assert "SA_THAI_QUY_3" in ds  # bác sĩ chọn được ở ô chọn mẫu
                assert kq["chon_san"] != "SA_THAI_QUY_3", ma
                assert ds.index("SA_THAI_QUY_23") < ds.index("SA_THAI_QUY_3")
            assert any(kq["chon_san"] == "SA_THAI_QUY_23" for kq in chon.values())
        finally:
            await tr.rollback()


async def test_json_seed_khop_luat_migration(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """JSON seed đã mang đúng hai cờ: qua hàm của migration không đổi gì."""
    goc = Path(pk.__file__).parent
    async with pool.acquire() as conn:
        for ten in ("mau_ket_qua_v3.json", "mau_ket_qua.json"):
            mau = json.loads((goc / ten).read_text("utf-8"))["mau"]
            for ma, m in mau.items():
                qua = json.loads(
                    await conn.fetchval(
                        "SELECT public.khung_tuy_chon_don_vi($1::jsonb)::text",
                        json.dumps(m["khung"], ensure_ascii=False),
                    )
                )
                assert qua == m["khung"], f"{ten} {ma}"
                for o in _cac_o(m["khung"]):
                    if o.get("goi_y") in DON_VI_THUAN and o["kieu"] in ("text", "so"):
                        assert o.get("don_vi") == o["goi_y"], f"{ten} {ma} {o['ma']}"
