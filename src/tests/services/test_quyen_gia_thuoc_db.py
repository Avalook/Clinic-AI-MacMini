"""Quyền Sửa giá thuốc (31/10/2026): ai được phép thì không lỗi, ai không được phép thì
chỉ bị chặn đúng lúc đổi giá, mọi việc khác vẫn làm được."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.catalogue import MAN
from clinicai.services.config_service import PriceListService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhieu_don_vi_ban_db import _ban, _giao, _lo, _thu, _ton
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

QUYEN = "price.medicine.manage"


async def _cap(q: Quay) -> None:  # noqa: F811
    await q.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, scope_type,"
        " tu_khoi, ly_do)"
        " VALUES ($1::uuid, $2::uuid, $3, 'CLINIC', 'gia_thuoc', 'test')"
        " ON CONFLICT DO NOTHING",
        CLINIC,
        q.bac_si.staff_id,
        QUYEN,
    )


async def _thuoc(q: Quay, *, hop: bool = True) -> str:  # noqa: F811
    """Người có quyền dựng thuốc, `q.duoc_si` là người không có quyền."""
    await _cap(q)
    kq = await PharmacyService(q.pool).luu_thuoc(
        identity=q.bac_si,
        drug_catalog_id=None,
        ten=f"Thuốc giá {uuid.uuid4().hex[:8]}",
        gia=85_000,
        don_vi_ban="gói",
        cac_don_vi=[{"don_vi": "hộp", "he_so": 30, "gia": 2_400_000}] if hop else None,
    )
    return str(kq["id"])


async def _doc(q: Quay, ma: str) -> Any:  # noqa: F811
    return await q.pool.fetchrow(
        "SELECT name_base, unit_price, cach_dung, ton_toi_thieu FROM drug_catalog"
        " WHERE id = $1::uuid",
        ma,
    )


async def _vet(q: Quay, ma: str) -> list[dict[str, Any]]:  # noqa: F811
    rows = await q.pool.fetch(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'pharmacy.price_changed' ORDER BY recorded_at",
        ma,
    )
    return [
        json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        for r in rows
    ]


async def _sua(q: Quay, ai: Any, ma: str, **kw: Any) -> dict[str, Any]:  # noqa: F811
    d = await _doc(q, ma)
    goc: dict[str, Any] = {
        "ten": d["name_base"],
        "gia": d["unit_price"],
        "don_vi_ban": "gói",
    }
    return await PharmacyService(q.pool).luu_thuoc(
        identity=ai, drug_catalog_id=ma, **{**goc, **kw}
    )


async def test_co_quyen_doi_gia_duoc_va_ghi_vet(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q)
    await _sua(q, q.bac_si, ma, gia=90_000)
    assert (await _doc(q, ma))["unit_price"] == 90_000
    vet = await _vet(q, ma)
    assert vet[-1]["gia_moi"].startswith("90000")
    assert vet[-1]["gia_cu"].startswith("85000")


async def test_khong_quyen_doi_gia_bi_chan_gia_giu_nguyen(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q)
    so_vet = len(await _vet(q, ma))
    with pytest.raises(SafetyGateError, match="không có quyền đổi giá thuốc"):
        await _sua(q, q.duoc_si, ma, gia=1)
    assert (await _doc(q, ma))["unit_price"] == 85_000
    assert len(await _vet(q, ma)) == so_vet


@pytest.mark.parametrize("gia", [85_000, "85000", 85000.0])
async def test_khong_quyen_luu_lai_gia_cu_khong_loi(q: Quay, gia: Any) -> None:  # noqa: F811
    """Form gửi kèm giá cũ: sửa cách dùng, tồn tối thiểu không được báo lỗi."""
    ma = await _thuoc(q)
    await _sua(q, q.duoc_si, ma, gia=gia, cach_dung="Ngày 1 gói", ton_toi_thieu=10)
    d = await _doc(q, ma)
    assert d["cach_dung"] == "Ngày 1 gói"
    assert d["ton_toi_thieu"] == 10
    assert d["unit_price"] == 85_000


async def test_thuoc_moi_khong_quyen_khong_gia_duoc_co_gia_bi_chan(q: Quay) -> None:  # noqa: F811
    svc = PharmacyService(q.pool)
    kq = await svc.luu_thuoc(
        identity=q.duoc_si,
        drug_catalog_id=None,
        ten=f"Thuốc mới {uuid.uuid4().hex[:8]}",
        don_vi_ban="viên",
    )
    assert (await _doc(q, str(kq["id"])))["unit_price"] is None
    with pytest.raises(SafetyGateError):
        await svc.luu_thuoc(
            identity=q.duoc_si,
            drug_catalog_id=None,
            ten=f"Thuốc mới {uuid.uuid4().hex[:8]}",
            gia=1000,
            don_vi_ban="viên",
        )


async def _don_vi(q: Quay, ma: str) -> list[dict[str, Any]]:  # noqa: F811
    return [
        dict(r)
        for r in await q.pool.fetch(
            "SELECT don_vi, he_so, gia, dang_ban, cap_nhat_luc::text AS phien"
            " FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid ORDER BY don_vi",
            ma,
        )
    ]


async def test_khong_quyen_khong_doi_duoc_gia_don_vi(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q)
    (hop,) = await _don_vi(q, ma)
    sua = [{"don_vi": "hộp", "he_so": 30, "gia": 1, "phien": hop["phien"]}]
    with pytest.raises(SafetyGateError):
        await _sua(q, q.duoc_si, ma, cac_don_vi=sua)
    assert (await _don_vi(q, ma))[0]["gia"] == 2_400_000


async def test_khong_quyen_gui_lai_don_vi_cu_khong_loi(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q)
    (hop,) = await _don_vi(q, ma)
    cu = [{"don_vi": "hộp", "he_so": 30, "gia": 2_400_000, "phien": hop["phien"]}]
    await _sua(q, q.duoc_si, ma, cach_dung="x", cac_don_vi=cu)


async def test_khong_quyen_them_don_vi_de_trong_gia_duoc(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q, hop=False)
    await _sua(q, q.duoc_si, ma, cac_don_vi=[{"don_vi": "hộp", "he_so": 10}])
    assert (await _don_vi(q, ma))[0]["gia"] == 850_000


async def test_khong_quyen_them_don_vi_tu_dat_gia_bi_chan(q: Quay) -> None:  # noqa: F811
    ma = await _thuoc(q, hop=False)
    with pytest.raises(SafetyGateError):
        await _sua(
            q, q.duoc_si, ma, cac_don_vi=[{"don_vi": "hộp", "he_so": 10, "gia": 5}]
        )
    assert await _don_vi(q, ma) == []


async def test_khong_quyen_van_ban_thu_giao_binh_thuong(q: Quay) -> None:  # noqa: F811
    """Tách quyền không được đụng tới bán thuốc, thu tiền, giao thuốc."""
    ma = await _thuoc(q)
    lo = await _lo(q, ma, 60)
    rx = await _ban(q, ma, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    assert await _ton(q, lo) == 30


async def _gia_bang(q: Quay, nhom: str) -> str:  # noqa: F811
    return str(
        await q.pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price) VALUES ($1::uuid, $2, $3, $4, 1000) RETURNING id::text",
            CLINIC,
            f"G{uuid.uuid4().hex[:10]}",
            f"Giá {uuid.uuid4().hex[:8]}",
            nhom,
        )
    )


async def test_bang_gia_thuoc_khong_co_duong_vong(q: Quay) -> None:  # noqa: F811
    ma = await _gia_bang(q, "thuoc")
    svc = PriceListService(q.pool)
    with pytest.raises(SafetyGateError):
        await svc.update(
            price_id=ma, identity=q.duoc_si, unit_price=2000, unit_price_provided=True
        )
    await svc.update(
        price_id=ma, identity=q.duoc_si, unit_price=1000, unit_price_provided=True
    )
    await _cap(q)
    await svc.update(
        price_id=ma, identity=q.bac_si, unit_price=2000, unit_price_provided=True
    )
    assert (await _vet(q, ma))[-1]["gia_moi"].startswith("2000")


async def test_bang_gia_dich_vu_khong_doi_luat(q: Quay) -> None:  # noqa: F811
    ma = await _gia_bang(q, "dich_vu")
    await PriceListService(q.pool).update(
        price_id=ma, identity=q.duoc_si, unit_price=2000, unit_price_provided=True
    )


async def test_goi_quan_ly_co_khoi_moi(q: Quay) -> None:  # noqa: F811
    """Gói Quản lý có khối mới, quyền xếp rủi ro tiền."""
    assert await q.pool.fetchval(
        "SELECT khoi @> ARRAY['gia_thuoc'] FROM quyen_preset WHERE ma = 'MANAGEMENT'"
    )
    assert (
        await q.pool.fetchval("SELECT rui_ro FROM capability WHERE ma = $1", QUYEN)
        == "financial"
    )


def test_hai_quyen_con_bat_tat_duoc_o_man_phan_quyen() -> None:
    """Khối không có dòng trong MAN thì màn Phân quyền không có công tắc."""
    assert list(MAN["gia_thuoc"].khoi) == ["gia_thuoc"]
    assert list(MAN["duyet_vat_tu"].khoi) == ["duyet_vat_tu"]
