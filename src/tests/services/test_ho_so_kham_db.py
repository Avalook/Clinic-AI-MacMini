"""Hồ sơ khám: đổi dịch vụ trong hồ sơ (T5), lượt Điều trị (T1, T2) — Tuyền
chốt 07/10/2026, trên Postgres thật."""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.services import ho_so_dich_vu
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.phieu_kham_service import PhieuKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_doi_dich_vu_kham_db import _check_in, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _loai(
    pool: asyncpg.Pool,  # noqa: F811
    ten: str,
    *,
    form: str | None = None,
    nhom: str = "KHAM",
    gia_id: str | None = None,
) -> str:
    return str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, form_code, nhom,"
            " service_price_id) VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid)"
            " RETURNING id::text",
            CLINIC,
            f"HS-{uuid.uuid4().hex[:8]}",
            ten,
            form,
            nhom,
            gia_id,
        )
    )


async def _doi_lich(pool: asyncpg.Pool, ca: dict[str, Any], dv: str) -> None:  # noqa: F811
    await pool.execute(
        "UPDATE appointment SET service_type_id = $2::uuid WHERE id = $1::uuid",
        ca["appt"],
        dv,
    )


async def _phieu(pool: asyncpg.Pool, visit: str, bs: Any) -> dict[str, Any]:  # noqa: F811
    """Phiếu Bàn khám mở (không chọn mẫu) — `doc_luot(form_id=None)`."""

    async def kiem(*_: Any) -> None:
        return None

    return await PhieuKhamService(pool, kiem_quyen=kiem).doc_luot(
        visit_id=visit, form_id=None, identity=bs
    )


async def test_doi_trong_ho_so_giu_phieu_cu_tick_va_doi_nguoc_du_du_lieu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, ca["loc"], "DOCTOR")
    pk = await _loai(pool, "Phụ khoa thử", form="PK")
    nt = await _loai(pool, "Nội tiết thử", form="NT")
    await _doi_lich(pool, ca, pk)
    visit = await _check_in(pool, ca)
    # Đã có phiếu PK (2 ô) + đã tick một dịch vụ khám con.
    await pool.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
        CLINIC,
        visit,
        json.dumps(
            {
                "pk_dx": {"nguon": "USER", "gia_tri": "Viêm âm đạo"},
                "pk_a_note": {"nguon": "USER", "gia_tri": "HA 110/70"},
                "trong": {"nguon": "USER", "gia_tri": ""},
            }
        ),
    )
    gia = await pool.fetchval(
        "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
        " AND \"group\" = 'dich_vu' AND active ORDER BY name LIMIT 1",
        CLINIC,
    )
    await pool.execute(
        "INSERT INTO luot_phi_kham (clinic_id, visit_id, service_price_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        visit,
        gia,
    )

    kq = await ho_so_dich_vu.doi(pool, identity=bs, visit_id=visit, service_type_id=nt)
    assert kq["doi"] is True
    assert (
        await pool.fetchval(
            "SELECT service_type_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
        == nt
    )
    # Phiếu theo dịch vụ HIỆN TẠI: NT trống; PK còn nguyên dòng.
    moi = await _phieu(pool, visit, bs)
    assert moi["form_id"] == "NT" and moi["du_lieu"] == {}
    hs = await ho_so_dich_vu.doc(pool, identity=bs, visit_id=visit)
    assert hs["dich_vu"]["id"] == nt and hs["doi_duoc"]
    assert [(p["form_id"], p["so_o"]) for p in hs["phieu_cu"]] == [("PK", 2)]
    [ls] = hs["lich_su_doi"]
    assert (ls["tu"], ls["sang"], ls["trong_ho_so"]) == (
        "Phụ khoa thử",
        "Nội tiết thử",
        True,
    )
    assert ls["ai"] and ls["luc"]
    # Tick dịch vụ con giữ nguyên.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM luot_phi_kham WHERE visit_id = $1::uuid"
            " AND bo_luc IS NULL",
            visit,
        )
        == 1
    )

    # Đổi ngược về: đúng phiếu cũ, đủ dữ liệu.
    await ho_so_dich_vu.doi(pool, identity=bs, visit_id=visit, service_type_id=pk)
    cu = await _phieu(pool, visit, bs)
    assert cu["form_id"] == "PK"
    assert cu["du_lieu"]["pk_dx"]["gia_tri"] == "Viêm âm đạo"
    hs2 = await ho_so_dich_vu.doc(pool, identity=bs, visit_id=visit)
    assert [p["form_id"] for p in hs2["phieu_cu"]] == ["NT"] or hs2["phieu_cu"] == []
    assert len(hs2["lich_su_doi"]) == 2


async def test_luot_dieu_tri_sinh_mot_chi_dinh_khong_phi_kham_khong_chan_ve(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from tests.chay_nguoi_dua_tin import chay_het

    ca = await _dung(pool)
    gia = await pool.fetchrow(
        "SELECT sp.id::text, sp.service_code FROM service_type st"
        " JOIN service_price sp ON sp.id = st.service_price_id"
        " WHERE st.clinic_id = $1::uuid AND st.code = 'DT_BIO'",
        CLINIC,
    )
    dt = await _loai(pool, "Bio thử", nhom="DIEU_TRI", gia_id=gia["id"])
    await _doi_lich(pool, ca, dt)
    visit = await _check_in(pool, ca)
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)

    don = await pool.fetch(
        "SELECT id::text, selection_status, routing_status, consultation_id"
        " FROM service_order WHERE visit_id = $1::uuid AND service_code = $2"
        " AND exec_status <> 'cancelled'",
        visit,
        gia["service_code"],
    )
    assert len(don) == 1
    assert don[0]["routing_status"] == "UNASSIGNED"
    assert don[0]["consultation_id"] is not None
    # Gọi lại hàm (giao lại tin) — vẫn một chỉ định.
    async with pool.acquire() as conn:
        assert (
            await ho_so_dich_vu.sinh_chi_dinh_dieu_tri(
                conn, clinic_id=CLINIC, visit_id=visit, nguoi_bam=None
            )
            is None
        )
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    # Không tự thu phí khám.
    assert not [d for d in hd.dong if d.source_type == "exam"]

    hs = await ho_so_dich_vu.doc(pool, identity=ca["bs"], visit_id=visit)
    assert hs["khach_da_dat"]["order_id"] == don[0]["id"]

    # Không ai nhận ở hàng bác sĩ → không có vướng "bác sĩ chưa khám".
    kq = await CheckoutService(pool).readiness(identity=ca["le_tan"], visit_id=visit)
    assert "exam_open" not in {b["type"] for b in kq["blockers"]}
