"""Tiền khám = dịch vụ khám người khám TICK theo mã KiotViet (Tuyền 28/09/2026).

"Tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … tick để chọn loại dịch
vụ chính xác của dịch vụ khám, lúc đó tiền mới tính, không còn bịa giá nữa."
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bill_service import KHAM_CHUA_CO_GIA, tinh_hoa_don
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.phi_kham_service import PhiKhamService
from tests.services.test_luot_kham_service_db import CLINIC, KichBan, _nguoi

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


async def _dong_kham(kb: KichBan) -> list[dict[str, object]]:
    async with kb.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=kb.bac_si.clinic_id, visit_id=kb.visit_id, kind="dich_vu"
        )
    return [dict(x) for x in hd.cho_api()["dong"] if x["source_type"] == "exam"]


async def test_tick_mot_hai_dich_vu_thi_tien_kham_dung_tong(kb: KichBan) -> None:
    a = await _dich_vu_kham(kb, "Khám tư vấn viêm nhiễm phụ khoa (thử)", 300000)
    b = await _dich_vu_kham(kb, "Tư vấn chuyên sâu (thử)", 200000)
    svc = PhiKhamService(kb.pool)
    doc = await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si)
    assert {a, b} <= {x["id"] for x in doc["lua_chon"]}
    await svc.chon(visit_id=kb.visit_id, ids=[a], identity=kb.bac_si)
    dong = await _dong_kham(kb)
    assert [d["ten"] for d in dong] == ["Khám tư vấn viêm nhiễm phụ khoa (thử)"]
    assert sum(Decimal(str(d["don_gia"])) for d in dong) == 300000
    # Mỗi dịch vụ con là một nguồn thu; tổng trên hoá đơn vẫn đúng.
    await svc.chon(visit_id=kb.visit_id, ids=[a, b], identity=kb.thu_ky)
    dong = await _dong_kham(kb)
    assert sum(Decimal(str(d["don_gia"])) for d in dong) == 500000
    # Bỏ tick hết → không còn giá, dòng báo chưa chọn.
    await svc.chon(visit_id=kb.visit_id, ids=[], identity=kb.bac_si)
    assert (await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si))["da_chon"] == []


async def test_dich_vu_chua_co_gia_thi_bao_khong_doan(kb: KichBan) -> None:
    c = await _dich_vu_kham(kb, "Khám sau sinh BN cũ (thử)", None)
    await PhiKhamService(kb.pool).chon(
        visit_id=kb.visit_id, ids=[c], identity=kb.bac_si
    )
    [d] = await _dong_kham(kb)
    assert KHAM_CHUA_CO_GIA in str(d["van_de"])


async def test_khong_nhan_dich_vu_ngoai_danh_sach(kb: KichBan) -> None:
    with pytest.raises(ValidationError):
        await PhiKhamService(kb.pool).chon(
            visit_id=kb.visit_id, ids=[str(uuid.uuid4())], identity=kb.bac_si
        )


async def test_loai_di_thang_nhung_re_qua_bac_si_van_tick_duoc(kb: KichBan) -> None:
    child = await _dich_vu_kham(kb, "Khám sàn chậu qua bác sĩ (thử)", 180000)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_type SET di_thang_phong = true"
            " WHERE id = (SELECT service_type_id FROM visit WHERE visit_id = $1::uuid)",
            kb.visit_id,
        )
        await conn.execute(
            "INSERT INTO encounter_flow (clinic_id, visit_id, route_decision,"
            " route_decided_at) VALUES ($1::uuid, $2::uuid, 'PRIMARY', now())"
            " ON CONFLICT (visit_id) DO UPDATE SET route_decision = 'PRIMARY',"
            " route_decided_at = now()",
            kb.bac_si.clinic_id,
            kb.visit_id,
        )
    svc = PhiKhamService(kb.pool)
    doc = await svc.doc(visit_id=kb.visit_id, identity=kb.bac_si)
    assert doc["di_thang_phong"] is True and doc["khong_kham"] is False
    saved = await svc.chon(visit_id=kb.visit_id, ids=[child], identity=kb.bac_si)
    assert saved["da_chon"] == [child]


async def test_quan_ly_sua_gia_mac_dinh_va_co_nhat_ky(kb: KichBan) -> None:
    await _dich_vu_kham(kb, "Khám để cấu hình giá (thử)", 100000)
    async with kb.pool.acquire() as conn:
        st = await conn.fetchval(
            "SELECT coalesce(v.service_type_id, a.service_type_id)::text"
            " FROM visit v LEFT JOIN appointment a ON a.id = v.appointment_id"
            " WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
        quan_ly = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    svc = ClinicConfigService(kb.pool)
    saved = await svc.update_service_type(
        identity=quan_ly, service_type_id=str(st), gia_mac_dinh=175000
    )
    assert saved["gia_mac_dinh"] == 175000
    services = await svc.services(identity=quan_ly)
    row = next(x for x in services["items"] if x["service_type_id"] == str(st))
    assert row["gia_mac_dinh"] == 175000
    payload = await kb.pool.fetchval(
        "SELECT payload FROM event_log WHERE clinic_id = $1::uuid"
        " AND event_type = 'clinic_config.service_type_updated'"
        " AND payload->>'doi_tuong_id' = $2 ORDER BY recorded_at DESC LIMIT 1",
        CLINIC,
        str(st),
    )
    assert json.loads(payload)["gia_mac_dinh"] == 175000


async def test_chua_chon_la_khoan_chua_thu_duoc() -> None:
    from clinicai.services.bill_service import dong_kham_theo_chon

    d = dong_kham_theo_chon(
        {
            "st_id": "x",
            "name": "Phụ khoa",
            "khong_hen": False,
            "gia_mac_dinh": Decimal("125000"),
        },
        [],
    )
    assert d is not None
    assert d["gia"] == [Decimal("125000")]
    assert "van_de" not in d
    assert d["canh_bao"] == "Chưa chọn dịch vụ khám — đang tính 125.000đ"


async def test_chua_cau_hinh_gia_mac_dinh_thi_tinh_khong_dong() -> None:
    from clinicai.services.bill_service import dong_kham_theo_chon

    d = dong_kham_theo_chon({"st_id": "x", "name": "Phụ khoa", "khong_hen": False}, [])
    assert d is not None and d["gia"] == [Decimal(0)]
    assert d["canh_bao"] == "Chưa chọn dịch vụ khám — đang tính 0đ"


async def test_tap_dich_vu_con_co_nguon_thu_rieng_voi_gia_mac_dinh() -> None:
    from clinicai.services.bill_service import dong_kham_theo_chon

    goc = {"st_id": "x", "name": "Phụ khoa", "khong_hen": False}
    mac_dinh = dong_kham_theo_chon(goc, [])
    da_chon = dong_kham_theo_chon(
        goc,
        [
            {
                "id": "b",
                "name": "Khám B",
                "unit_price": Decimal(200000),
                "billing_owner": "CLINIC",
            },
            {
                "id": "a",
                "name": "Khám A",
                "unit_price": Decimal(100000),
                "billing_owner": "CLINIC",
            },
        ],
    )
    assert mac_dinh is not None and da_chon is not None
    assert {d["source_id"] for d in da_chon["dong_chon"]} == {
        "selected-a",
        "selected-b",
    }
    # Thứ tự đọc DB không được đổi định danh của từng nghĩa vụ.
    dao = dong_kham_theo_chon(
        goc,
        list(
            reversed(
                [
                    {
                        "id": "b",
                        "name": "Khám B",
                        "unit_price": Decimal(200000),
                        "billing_owner": "CLINIC",
                    },
                    {
                        "id": "a",
                        "name": "Khám A",
                        "unit_price": Decimal(100000),
                        "billing_owner": "CLINIC",
                    },
                ]
            )
        ),
    )
    assert dao is not None
    assert {d["source_id"] for d in dao["dong_chon"]} == {
        d["source_id"] for d in da_chon["dong_chon"]
    }


async def test_anh_chup_gop_cu_chi_phu_dung_dich_vu_da_thu() -> None:
    from clinicai.services.bill_service import (
        _nguon_con_duoc_legacy_phu,
        dong_kham_theo_chon,
    )

    kham = dong_kham_theo_chon(
        {"st_id": "x", "name": "Phụ khoa", "khong_hen": False},
        [
            {
                "id": "a",
                "name": "Khám A",
                "unit_price": Decimal(100000),
                "billing_owner": "CLINIC",
            },
            {
                "id": "b",
                "name": "Khám B",
                "unit_price": Decimal(200000),
                "billing_owner": "CLINIC",
            },
        ],
    )
    assert kham is not None
    assert _nguon_con_duoc_legacy_phu(
        kham, [{"name_snapshot": "Khám A", "line_total": Decimal(100000)}]
    ) == {"selected-a"}


async def test_gia_mac_dinh_tu_choi_so_le_va_khong_ghi_nhat_ky(kb: KichBan) -> None:
    await _dich_vu_kham(kb, "Khám kiểm tra giá nguyên (thử)", 100000)
    async with kb.pool.acquire() as conn:
        st = await conn.fetchval(
            "SELECT coalesce(v.service_type_id, a.service_type_id)::text"
            " FROM visit v LEFT JOIN appointment a ON a.id = v.appointment_id"
            " WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
        quan_ly = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    with pytest.raises(ValidationError, match="số nguyên"):
        await ClinicConfigService(kb.pool).update_service_type(
            identity=quan_ly,
            service_type_id=str(st),
            gia_mac_dinh=Decimal("0.5"),
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await kb.pool.execute(
            "UPDATE service_type SET gia_mac_dinh = 0.5 WHERE id = $1::uuid", st
        )


async def test_khong_duoc_doi_phi_kham_sau_checkout(kb: KichBan) -> None:
    child = await _dich_vu_kham(kb, "Khám sau checkout (thử)", 100000)
    await kb.pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", kb.visit_id
    )
    with pytest.raises(ValidationError, match="đã check-out"):
        await PhiKhamService(kb.pool).chon(
            visit_id=kb.visit_id, ids=[child], identity=kb.bac_si
        )
