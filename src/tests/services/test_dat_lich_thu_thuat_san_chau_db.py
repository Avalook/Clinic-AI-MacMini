"""Đặt lịch có đủ Thủ thuật + Sàn chậu chuyên sâu (Tuyền 24/09/2026: "sao đặt
lịch lại chỉ có 5 dịch vụ, mình đã thêm thủ thuật và Sàn chậu chuyên sâu rồi").

Chạy lại chính migration 20260925000006 lên DB thử — đúng đường nó đi lên prod
(database đã có dữ liệu). Trên DB dựng mới, seed nạp "***#Thủ thuật" SAU
migration nên không kiểm được nếu không áp lại.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest

from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.man_dat_lich_doc import hub_dat_lich
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase/migrations/20260925000006_dat_lich_thu_thuat_san_chau.sql"
)


async def _ap_migration(pool: asyncpg.Pool) -> None:  # noqa: F811
    # Như prod: phòng khám đã tính tiền khám bằng dòng KHAM_* (migration chỉ
    # thêm giá khám cho phòng khám như vậy). Dòng mốc TẮT — không vào hoá đơn.
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, active) VALUES ($1::uuid, 'KHAM_MOC_KIEM',"
        " 'Mốc kiểm giá khám (test)', 'dich_vu', 1, false)"
        ' ON CONFLICT (clinic_id, "group", service_code) DO NOTHING',
        CLINIC,
    )
    await pool.execute(MIGRATION.read_text(encoding="utf-8"))


async def _loai(pool: asyncpg.Pool, code: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT id::text, name, is_active, form_code, di_thang_phong, qua_tu_van"
        " FROM service_type WHERE clinic_id = $1::uuid AND code = $2",
        CLINIC,
        code,
    )
    assert r is not None, f"thiếu loại khám {code}"
    return r


async def test_man_dat_lich_co_thu_thuat_va_san_chau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    await _ap_migration(pool)
    await _ap_migration(pool)  # chạy lại được
    for code, ten, phieu in (
        ("THU_THUAT", "Thủ thuật", "THU_THUAT"),
        ("SAN_CHAU", "Sàn chậu chuyên sâu", "SAN_CHAU"),
    ):
        r = await _loai(pool, code)
        assert (r["name"], r["is_active"], r["form_code"]) == (ten, True, phieu)
        # Dây H2: đi thẳng phòng, không qua tư vấn.
        assert (r["di_thang_phong"], r["qua_tu_van"]) == (True, False)
    ca = await _dung(pool)
    hub = await hub_dat_lich(pool, identity=ca.le_tan)
    ten_dv = {d["name"] for d in hub["services"]}
    assert {"Thủ thuật", "Sàn chậu chuyên sâu"} <= ten_dv
    assert "***#Thủ thuật" not in ten_dv


@pytest.mark.parametrize(
    ("code", "ten"),
    [("THU_THUAT", "Thủ thuật"), ("SAN_CHAU", "Sàn chậu chuyên sâu")],
)
async def test_khach_moi_ve_bac_si_chinh_tinh_tien_kham_dung_dong_gia(
    pool: asyncpg.Pool,  # noqa: F811
    code: str,
    ten: str,
) -> None:
    """Khách mới đặt lịch loại đi-thẳng-phòng nhưng chưa có chỉ định nào mang
    sang → rơi về bác sĩ chính → có dòng tiền khám và THU ĐƯỢC.

    V2 (30/09/2026): chưa chọn dịch vụ khám con thì tính giá mặc định của loại
    khám + cảnh báo mềm — không còn tra dòng giá trùng tên (trên prod các dòng
    ấy đã tắt), không còn khoá quầy vì "chưa chọn"."""
    await _ap_migration(pool)
    ca = await _dung(pool)
    loai = await _loai(pool, code)
    moi = await _check_in(pool, ca, await _benh_nhan(pool, ca), loai["id"])
    assert (
        await pool.fetchval(
            "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", moi
        )
        == "PRIMARY"
    )
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=moi)
    if code == "THU_THUAT":
        # Tuyền chốt 09/10/2026: Thủ thuật KHÔNG tự cộng phí khám — chỉ khi tick
        # dịch vụ khám con (`bill_service.khong_tu_cong_phi_kham`).
        assert [d for d in hd.dong if d.source_type == "exam"] == []
        return
    [kham] = [d for d in hd.dong if d.source_type == "exam"]
    assert kham.ten == f"Tiền khám {ten}"
    assert kham.don_gia is not None and kham.don_gia >= Decimal(0)
    assert not kham.van_de and not hd.van_de
    assert hd.canh_bao
