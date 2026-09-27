"""Phiếu khám v2 gọn (đợt 3, 27/09/2026) trên Postgres thật — migration
20260928000020 xuất bản v2, phiếu cũ ghim v1 vẫn đọc đúng.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_phieu_kham_v2_db.py

Không đếm dòng toàn bảng (database thử dùng chung với các phiên khác).
"""

from __future__ import annotations

import json
from pathlib import Path

import asyncpg
import pytest

from clinicai.core.exceptions import ValidationError
from clinicai.phieu_kham.khung import cac_o, dinh_nghia
from tests.services.test_phieu_kham_db import (
    CLINIC,
    _nguoi,
    _o,
    _svc,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GOC = Path(__file__).resolve().parents[3]
V2 = GOC / "supabase" / "migrations" / "20260928000020_phieu_kham_v2_gon.sql"
DOI = ("NT", "HMVS", "PK", "SK", "NK")


async def test_ban_dang_dung_la_v2_bang_json(pool: asyncpg.Pool) -> None:  # noqa: F811
    for f in DOI:
        dong = await pool.fetchrow(
            "SELECT version, khung, xuat_ban_boi FROM form_definition"
            " WHERE clinic_id = $1::uuid AND form_id = $2 AND trang_thai = 'PUBLISHED'",
            CLINIC,
            f,
        )
        assert dong is not None, f
        if dong["xuat_ban_boi"] is not None:
            continue  # phòng khám tự xuất bản — migration cố ý không đè
        assert dong["version"] >= 2, f
        assert json.loads(dong["khung"]) == dinh_nghia(f)["khung"], f


async def test_v1_ve_huu_van_giu_nguyen_va_ma_v1_nam_trong_v2(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    for f in DOI:
        v1 = await pool.fetchrow(
            "SELECT trang_thai, khung FROM form_definition"
            " WHERE clinic_id = $1::uuid AND form_id = $2 AND version = 1",
            CLINIC,
            f,
        )
        assert v1 is not None and v1["trang_thai"] == "RETIRED", f
        o_v1 = cac_o(json.loads(v1["khung"]))
        assert f"{f.lower()}_allergy_co" not in o_v1
        assert set(o_v1) <= set(cac_o(dinh_nghia(f)["khung"])), f


async def test_phieu_ghim_v1_doc_v1_luu_v2_nhan_o_moi(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    svc = _svc(pool)
    cu = await svc.khung_theo_ban(form_id="NT", version=1, identity=bs)
    assert "nt_allergy_co" not in cac_o(cu["khung"])
    assert cac_o(cu["khung"])["nt_allergy"]["ten"] == "Dị ứng thuốc"
    with pytest.raises(ValidationError, match="không có trong phiếu"):
        await svc.kiem_luu(
            form_id="NT",
            version=1,
            du_lieu={"nt_allergy_co": _o("nt_allergy_co_2")},
            che_do="editable",
            identity=bs,
        )
    # Dữ liệu kiểu v1 (dị ứng gõ chữ) vẫn lưu được ở phiếu v1.
    sach, _ = await svc.kiem_luu(
        form_id="NT",
        version=1,
        du_lieu={"nt_allergy": _o("Penicillin")},
        che_do="editable",
        identity=bs,
    )
    assert sach["nt_allergy"]["gia_tri"] == "Penicillin"

    moi = await svc.khung_theo_ban(form_id="NT", version=None, identity=bs)
    sach, cb = await svc.kiem_luu(
        form_id="NT",
        version=moi["version"],
        du_lieu={
            "nt_allergy_co": _o("nt_allergy_co_1"),
            "nt_allergy": _o("Penicillin"),
        },
        che_do="editable",
        identity=bs,
    )
    assert cb == [] and sach["nt_allergy_co"]["gia_tri"] == "nt_allergy_co_1"


async def test_chay_lai_migration_khong_de_ban_moi(pool: asyncpg.Pool) -> None:  # noqa: F811
    truoc = {
        r["form_id"]: r["version"]
        for r in await pool.fetch(
            "SELECT form_id, version FROM form_definition WHERE clinic_id = $1::uuid"
            " AND trang_thai = 'PUBLISHED' AND form_id = ANY($2::text[])",
            CLINIC,
            list(DOI),
        )
    }
    async with pool.acquire() as conn:
        await conn.execute(V2.read_text(encoding="utf-8"))
    sau = {
        r["form_id"]: r["version"]
        for r in await pool.fetch(
            "SELECT form_id, version FROM form_definition WHERE clinic_id = $1::uuid"
            " AND trang_thai = 'PUBLISHED' AND form_id = ANY($2::text[])",
            CLINIC,
            list(DOI),
        )
    }
    assert sau == truoc
