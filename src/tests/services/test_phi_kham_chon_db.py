"""Tiền khám = dịch vụ khám người khám TICK theo mã KiotViet (Tuyền 28/09/2026).

"Tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … tick để chọn loại dịch
vụ chính xác của dịch vụ khám, lúc đó tiền mới tính, không còn bịa giá nữa."
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bill_service import (
    KHAM_CHUA_CHON,
    KHAM_CHUA_CO_GIA,
    tinh_hoa_don,
)
from clinicai.services.phi_kham_service import PhiKhamService
from tests.services.test_luot_kham_service_db import KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dich_vu_kham(kb: KichBan, ten: str, gia: int | None) -> str:
    """Một dịch vụ khám (mã KV giả) gắn vào loại khám của lượt thử."""
    cid = kb.bac_si.clinic_id
    async with kb.pool.acquire() as conn:
        st = await conn.fetchval(
            "SELECT coalesce(v.service_type_id, a.service_type_id)::text"
            " FROM visit v LEFT JOIN appointment a ON a.id = v.appointment_id"
            " WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
        if st is None:
            # Lượt thử chưa gắn loại khám → gắn một loại khám KHÔNG đi thẳng phòng.
            st = await conn.fetchval(
                "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
                " AND NOT coalesce(di_thang_phong, false) ORDER BY code LIMIT 1",
                cid,
            )
            await conn.execute(
                "UPDATE visit SET service_type_id = $2::uuid WHERE visit_id = $1::uuid",
                kb.visit_id,
                st,
            )
        assert st is not None
        ma = f"T{uuid.uuid4().hex[:7]}"
        sp = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, ma_kiotviet) VALUES ($1::uuid, $2, $3, 'dich_vu', $4, $2)"
            " RETURNING id::text",
            cid,
            ma,
            ten,
            gia,
        )
        await conn.execute(
            "INSERT INTO loai_kham_phi (clinic_id, service_type_id, service_price_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            cid,
            st,
            sp,
        )
        return str(sp)


async def _dong_kham(kb: KichBan) -> dict[str, object]:
    async with kb.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=kb.bac_si.clinic_id, visit_id=kb.visit_id, kind="dich_vu"
        )
    d = next(x for x in hd.cho_api()["dong"] if x["source_type"] == "exam")
    return dict(d)


async def test_tick_mot_hai_dich_vu_thi_tien_kham_dung_tong(kb: KichBan) -> None:
    a = await _dich_vu_kham(kb, "Khám tư vấn viêm nhiễm phụ khoa (thử)", 300000)
    b = await _dich_vu_kham(kb, "Tư vấn chuyên sâu (thử)", 200000)
    svc = PhiKhamService(kb.pool)
    doc = await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si)
    assert {a, b} <= {x["id"] for x in doc["lua_chon"]}
    await svc.chon(visit_id=kb.visit_id, ids=[a], identity=kb.bac_si)
    d = await _dong_kham(kb)
    assert "Khám tư vấn viêm nhiễm phụ khoa (thử)" in str(d["ten"])
    assert Decimal(str(d["don_gia"])) == 300000
    # Thư ký / quầy tick thêm → tổng hai dịch vụ, vẫn MỘT dòng tiền khám.
    await svc.chon(visit_id=kb.visit_id, ids=[a, b], identity=kb.thu_ky)
    d = await _dong_kham(kb)
    assert Decimal(str(d["don_gia"])) == 500000
    # Bỏ tick hết → không còn giá, dòng báo chưa chọn.
    await svc.chon(visit_id=kb.visit_id, ids=[], identity=kb.bac_si)
    assert (await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si))["da_chon"] == []


async def test_dich_vu_chua_co_gia_thi_bao_khong_doan(kb: KichBan) -> None:
    c = await _dich_vu_kham(kb, "Khám sau sinh BN cũ (thử)", None)
    await PhiKhamService(kb.pool).chon(
        visit_id=kb.visit_id, ids=[c], identity=kb.bac_si
    )
    d = await _dong_kham(kb)
    assert KHAM_CHUA_CO_GIA in str(d["van_de"])


async def test_khong_nhan_dich_vu_ngoai_danh_sach(kb: KichBan) -> None:
    with pytest.raises(ValidationError):
        await PhiKhamService(kb.pool).chon(
            visit_id=kb.visit_id, ids=[str(uuid.uuid4())], identity=kb.bac_si
        )


def test_chua_chon_la_khoan_chua_thu_duoc() -> None:
    from clinicai.services.bill_service import dong_kham_theo_chon

    d = dong_kham_theo_chon({"st_id": "x", "name": "Phụ khoa", "khong_hen": False}, [])
    assert d is not None and d["gia"] == [] and d["van_de"] == KHAM_CHUA_CHON
