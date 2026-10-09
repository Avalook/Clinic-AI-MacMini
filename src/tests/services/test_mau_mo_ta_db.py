"""Phiếu kết quả chỉ một ô "Mô tả" — nước tiểu, monitor thai; monitor thành
nút làm thêm tại quầy (lễ tân / bàn sinh hiệu chỉ định).

Checklist phòng khám mục 1 + 4.1 (Tuyền 09/10/2026): một ô Mô tả, tuỳ chọn; bỏ
Kết luận và Đề nghị. Đo mật độ xương KHÔNG đổi (Tuyền đính chính cùng ngày).
Migration 20261009700000 (hàm `mau_mo_ta_nuoc_tieu_monitor`).

Bài nào gọi lại hàm của migration thì chạy TRONG MỘT GIAO DỊCH RỒI HUỶ: hàm
xuất bản bản mới cho mẫu của cả DB — để lại thì đổi số bản dưới chân các bài
khác.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.phieu_kham.kiem_khung_mau import kiem_khung_mau
from clinicai.phieu_kham.mau_goi_y import mau_cho_cac_dich_vu
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.mau_ket_qua_service import MauKetQuaService
from tests.services.test_form_engine_db import (
    CLINIC,
    _don_tron,
    _nguoi,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

NUOC_TIEU_MONITOR = (
    "CLS_NUOC_TIEU",
    "CLS_NUOC_TIEU_SAU_XUAT_TINH",
    "CLS_CHAY_MONITORING",
    "KV_SP000081",
)
KHUNG_MO_TA = [
    {
        "ma": "mo_ta",
        "ten": "Mô tả",
        "block": [
            {"ma": "noi_dung", "ten": "Mô tả", "kieu": "doan_van", "tuy_chon": True}
        ],
    }
]


async def _ban_dang_dung(conn: Any, form_id: str) -> Any:
    return await conn.fetchrow(
        "SELECT version, khung FROM form_definition WHERE clinic_id = $1::uuid"
        " AND form_id = $2 AND trang_thai = 'PUBLISHED'",
        CLINIC,
        form_id,
    )


async def _dv_co(conn: Any) -> list[str]:
    return [
        r["service_code"]
        for r in await conn.fetch(
            "SELECT DISTINCT service_code FROM service_price"
            " WHERE clinic_id = $1::uuid AND service_code = ANY($2::text[])",
            CLINIC,
            list(NUOC_TIEU_MONITOR),
        )
    ]


async def test_nuoc_tieu_va_monitor_chon_mau_mo_ta(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        d = await _ban_dang_dung(conn, "KQ_MO_TA")
        khung = json.loads(d["khung"])
        assert khung == KHUNG_MO_TA
        assert kiem_khung_mau(khung) == khung  # sửa trên màn không bị chặn
        assert (
            await conn.fetchval(
                "SELECT ten FROM ket_qua_mau"
                " WHERE clinic_id = $1::uuid AND ma = 'MO_TA'",
                CLINIC,
            )
            == "Kết quả (mô tả)"
        )

        co = await _dv_co(conn)
        assert {"CLS_NUOC_TIEU", "CLS_CHAY_MONITORING"} <= set(co), co
        chon = await mau_cho_cac_dich_vu(conn, clinic_id=CLINIC, service_codes=co)
        bs = await _nguoi(conn, "DOCTOR")
    for ma, kq in chon.items():
        assert kq["chon_san"] == "MO_TA", ma
        assert kq["mac_dinh"] is False, ma  # đã GẮN, không phải mặc định máy
    # Cùng luật qua API màn Mẫu kết quả / phòng dịch vụ.
    dv = await MauKetQuaService(pool).mau_cua_dich_vu(
        service_code="CLS_NUOC_TIEU", identity=bs
    )
    assert dv["chon_san"] == "MO_TA" and [m["ma"] for m in dv["mau"]] == ["MO_TA"]


async def test_monitor_thanh_nut_lam_them_va_dxa_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        nut = {
            r["service_code"]: r
            for r in await conn.fetch(
                "SELECT service_code, nhan, bat, o_tiep_don, o_sinh_hieu"
                " FROM lam_them_tai_quay WHERE clinic_id = $1::uuid"
                "   AND service_code IN ('CLS_CHAY_MONITORING', 'KV_SP000081')",
                CLINIC,
            )
        }
        co = await _dv_co(conn)
        d = await _ban_dang_dung(conn, "KQ_DO_MAT_DO_XUONG")
    for ma in {"CLS_CHAY_MONITORING", "KV_SP000081"} & set(co):
        r = nut[ma]
        assert r["bat"] and r["o_tiep_don"] and r["o_sinh_hieu"], ma
    assert "CLS_CHAY_MONITORING" in nut
    assert nut["CLS_CHAY_MONITORING"]["nhan"] == "Monitor đơn thai"
    # Đo mật độ xương giữ nguyên ba mục: Mô tả / kết quả · Kết luận · Đề nghị.
    assert [m["ma"] for m in json.loads(d["khung"])] == [
        "ket_qua",
        "ket_luan",
        "de_nghi",
    ]


async def test_hoan_tat_mo_ta_de_trong_khong_nhac_o_nao(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    svc = FormEngineService(pool)
    p = await svc.mo_phieu(service_order_id=order, form_id="KQ_MO_TA", identity=bs)
    assert p["con_trong"] == []
    xong = await svc.hoan_tat(
        phieu_id=p["id"],
        expected_revision=p["revision"],
        identity=bs,
        thuc_hien_boi=bs.staff_id,
    )
    assert xong["con_trong"] == []


async def test_chay_lai_khong_doi_gi_va_khong_de_mau_gan_tay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            # Lần đầu có thể còn việc (bài khác dựng thêm phòng khám trong cùng
            # DB); lần kế tiếp thì không còn gì.
            await conn.fetchval("SELECT public.mau_mo_ta_nuoc_tieu_monitor()")
            assert (
                await conn.fetchval("SELECT public.mau_mo_ta_nuoc_tieu_monitor()") == 0
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM form_definition WHERE clinic_id = $1::uuid"
                    " AND form_id = 'KQ_MO_TA'",
                    CLINIC,
                )
                == 1
            )

            # Quản lý gắn tay mẫu khác cho nước tiểu → chạy lại không chồng MO_TA.
            ql = await _nguoi(conn, "MANAGEMENT")
            await conn.execute(
                "DELETE FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
                " AND service_code = 'CLS_NUOC_TIEU'",
                CLINIC,
            )
            await conn.execute(
                "INSERT INTO dich_vu_mau_ket_qua"
                " (clinic_id, service_code, mau, gan_boi)"
                " VALUES ($1::uuid, 'CLS_NUOC_TIEU', 'CHUNG', $2::uuid)",
                CLINIC,
                ql.staff_id,
            )
            assert (
                await conn.fetchval("SELECT public.mau_mo_ta_nuoc_tieu_monitor()") == 0
            )
            assert [
                r["mau"]
                for r in await conn.fetch(
                    "SELECT mau FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
                    " AND service_code = 'CLS_NUOC_TIEU'",
                    CLINIC,
                )
            ] == ["CHUNG"]
        finally:
            await tr.rollback()


async def test_staging_mau_tay_thi_khong_gan_chong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Staging 09/10: Tuyền đã tạo tay mẫu KET_QUA_MO_TA gắn cho nước tiểu /
    monitor. Migration không gắn chồng MO_TA."""
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            ql = await _nguoi(conn, "MANAGEMENT")
            co = await _dv_co(conn)
            await conn.execute(
                "INSERT INTO ket_qua_mau (clinic_id, ma, nhom, ten)"
                " VALUES ($1::uuid, 'KET_QUA_MO_TA', 'Chung', 'Kết quả (mô tả)')",
                CLINIC,
            )
            await conn.execute(
                "DELETE FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
                " AND service_code = ANY($2::text[])",
                CLINIC,
                co,
            )
            await conn.execute(
                "INSERT INTO dich_vu_mau_ket_qua"
                " (clinic_id, service_code, mau, gan_boi)"
                " SELECT $1::uuid, x, 'KET_QUA_MO_TA', $2::uuid"
                "   FROM unnest($3::text[]) x",
                CLINIC,
                ql.staff_id,
                co,
            )
            await conn.fetchval("SELECT public.mau_mo_ta_nuoc_tieu_monitor()")
            gan = await conn.fetch(
                "SELECT service_code, mau FROM dich_vu_mau_ket_qua"
                " WHERE clinic_id = $1::uuid AND service_code = ANY($2::text[])",
                CLINIC,
                co,
            )
            assert {r["mau"] for r in gan} == {"KET_QUA_MO_TA"}
            assert len(gan) == len(co)
        finally:
            await tr.rollback()


SA_TC = ("CLS_SIEU_AM_2D_TC_BT", "CLS_SIEU_AM_4D_TC_BT", "KV_SP000080")


async def test_sieu_am_tu_cung_chi_con_mau_phan_phu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        gan = await conn.fetch(
            "SELECT service_code, mau FROM dich_vu_mau_ket_qua"
            " WHERE clinic_id = $1::uuid AND service_code = ANY($2::text[])"
            "   AND mau IN ('SA_TC_BT', 'SA_TC_PP')",
            CLINIC,
            list(SA_TC),
        )
        assert gan, "khuôn phải có dịch vụ siêu âm tử cung gắn mẫu (seed)"
        assert {r["mau"] for r in gan} == {"SA_TC_PP"}
        # Mẫu SA_TC_BT còn nguyên — phiếu cũ ghim nó vẫn mở / in được.
        assert await _ban_dang_dung(conn, "KQ_SA_TC_BT") is not None
        ma = gan[0]["service_code"]

        tr = conn.transaction()
        await tr.start()
        try:
            assert await conn.fetchval("SELECT public.sa_tc_chi_con_phan_phu()") == 0
            # Dịch vụ chỉ gắn BT (chưa có PP): gắn PP trước, chép result_mode /
            # thu_tu, rồi mới gỡ BT.
            await conn.execute(
                "DELETE FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid"
                " AND service_code = $2 AND mau = 'SA_TC_PP'",
                CLINIC,
                ma,
            )
            await conn.execute(
                "INSERT INTO dich_vu_mau_ket_qua"
                " (clinic_id, service_code, mau, result_mode, thu_tu)"
                " VALUES ($1::uuid, $2, 'SA_TC_BT', 'LATER', 3)",
                CLINIC,
                ma,
            )
            assert await conn.fetchval("SELECT public.sa_tc_chi_con_phan_phu()") == 2
            dong = await conn.fetch(
                "SELECT mau, result_mode, thu_tu FROM dich_vu_mau_ket_qua"
                " WHERE clinic_id = $1::uuid AND service_code = $2"
                "   AND mau IN ('SA_TC_BT', 'SA_TC_PP')",
                CLINIC,
                ma,
            )
            assert [dict(r) for r in dong] == [
                {"mau": "SA_TC_PP", "result_mode": "LATER", "thu_tu": 3}
            ]
        finally:
            await tr.rollback()


async def test_truong_ca_quan_ly_ca_kham(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        hien = await conn.fetchrow(
            "SELECT phong, tang FROM vi_tri_lam_viec"
            " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
            CLINIC,
        )
        assert hien is not None
        assert hien["phong"] and hien["tang"]
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(
                "UPDATE vi_tri_lam_viec SET phong = NULL, tang = 'Điều phối'"
                " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
                CLINIC,
            )
            truoc = await conn.fetchval(
                "SELECT room_id::text FROM vi_tri_lam_viec"
                " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
                CLINIC,
            )
            assert await conn.fetchval("SELECT public.truong_ca_quan_ly_ca_kham()")
            sau = await conn.fetchrow(
                "SELECT phong, tang, room_id::text AS room_id FROM vi_tri_lam_viec"
                " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
                CLINIC,
            )
            assert sau["phong"] == "Quản lý ca khám"
            assert sau["tang"] == "Quản lý ca khám"
            assert sau["room_id"] == truoc  # không đụng phòng thật

            # Quản lý đã đặt tay → giữ; chạy lại không đổi gì.
            await conn.execute(
                "UPDATE vi_tri_lam_viec SET phong = 'Phòng A', tang = 'Tầng 2'"
                " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
                CLINIC,
            )
            await conn.fetchval("SELECT public.truong_ca_quan_ly_ca_kham()")
            assert not await conn.fetchval("SELECT public.truong_ca_quan_ly_ca_kham()")
            tay = await conn.fetchrow(
                "SELECT phong, tang FROM vi_tri_lam_viec"
                " WHERE clinic_id = $1::uuid AND code = 'DIEU_PHOI'",
                CLINIC,
            )
            assert (tay["phong"], tay["tang"]) == ("Phòng A", "Tầng 2")
        finally:
            await tr.rollback()
