"""Quầy gỡ dòng thuốc lệch (T3, 26/11): gán sang thuốc đúng + điền giá, đúng quyền,
hoàn tác được, đầu vào rác không 500.

Bất biến tiền nằm ở `test_gia_lap_thu_tung_dong_db`."""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import json
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.thuoc.go_dong_lech import (
    bo_gan_duoc,
    dien_gia_thuoc,
    doc_dong_lech,
    gan_thuoc_dung,
    gia_quay,
    hoan_tac_gan,
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _hd,
    _thuoc,
    q,  # noqa: F401
)
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

QUYEN = "price.medicine.manage"


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _cap_quyen_gia(q: Quay) -> None:
    await q.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, scope_type,"
        " tu_khoi, ly_do) VALUES ($1::uuid, $2::uuid, $3, 'CLINIC', 'gia_thuoc',"
        " 'test') ON CONFLICT DO NOTHING",
        CLINIC,
        q.bac_si.staff_id,
        QUYEN,
    )


async def _thuoc_dv(q: Quay, ten: str, gia: int | None, don_vi: str) -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price,"
            " don_vi_ban) VALUES ($1::uuid, $2, $2, $3, $4) RETURNING id::text",
            CLINIC,
            ten,
            gia,
            don_vi,
        )
    )


async def _rac(q: Quay) -> tuple[str, str]:
    """Dòng kê 'Pricefil' gắn thuốc rác không giá (như máy tự thêm)."""
    rx = await _don(q, 12, ten=f"Pricefil {q.duoi}")
    rac = await _thuoc(q, gia=None, ten=f"Pricefil {q.duoi}")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=rac
    )
    return rx, rac


async def _dong(q: Quay, rx: str) -> Any:
    return await q.pool.fetchrow(
        "SELECT drug_catalog_id::text AS thuoc, drug_name_raw AS ten, unit"
        " FROM prescription WHERE id = $1::uuid",
        rx,
    )


async def _vet(q: Quay, rx: str) -> list[dict[str, Any]]:
    rows = await q.pool.fetch(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'pharmacy.counter_changed' ORDER BY occurred_at",
        rx,
    )
    return [
        json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        for r in rows
    ]


# ── Gán sang thuốc đúng ─────────────────────────────────────────────────────


async def test_gan_thuoc_dung_thu_duoc_hoan_tac_tra_ve_nhu_cu(q: Quay) -> None:
    rx, rac = await _rac(q)
    assert not (await _hd(q, "thuoc")).thu_duoc
    dung = await _thuoc_dv(q, f"Pricefil 5mg {q.duoi}", 4_000, "viên")

    kq = await gan_thuoc_dung(
        q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=dung
    )
    assert kq["nhac"] is None  # "viên" có ở thuốc mới → số lượng đúng nghĩa
    d = await _dong(q, rx)
    # Chỉ đổi thuốc kho; tên + đơn vị bác sĩ gõ là hồ sơ, giữ nguyên.
    assert (d["thuoc"], d["ten"], d["unit"]) == (dung, f"Pricefil {q.duoi}", "viên")
    hd = await _hd(q, "thuoc")
    assert hd.thu_duoc and hd.tong == 12 * 4_000
    assert (await _vet(q, rx))[-1]["hanh_dong"] == "GAN_THUOC"

    lech = await doc_dong_lech(q.pool, identity=q.thu_ngan, visit_id=q.visit_id)
    assert [x["bo_gan_duoc"] for x in lech["dong"]] == [True]

    await hoan_tac_gan(q.pool, identity=q.thu_ngan, prescription_id=rx)
    d = await _dong(q, rx)
    assert (d["thuoc"], d["ten"], d["unit"]) == (rac, f"Pricefil {q.duoi}", "viên")
    assert (await _vet(q, rx))[-1]["hanh_dong"] == "BO_GAN_THUOC"
    with pytest.raises(ConflictError, match="Không có lần gán"):
        await hoan_tac_gan(q.pool, identity=q.thu_ngan, prescription_id=rx)


async def test_gan_don_vi_khong_co_o_thuoc_moi_thi_nhac_soat_so_luong(
    q: Quay,
) -> None:
    rx, _ = await _rac(q)
    dung = await _thuoc_dv(q, f"Pricefil hộp {q.duoi}", 90_000, "hộp")
    kq = await gan_thuoc_dung(
        q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=dung
    )
    assert "soát lại số lượng" in (kq["nhac"] or "")
    assert (await _dong(q, rx))["unit"] == "viên"


async def test_gan_va_hoan_tac_tren_ho_so_da_ky(q: Quay) -> None:
    """Ca thật T3: bác sĩ gõ tay, KÝ hồ sơ, rồi quầy mới gỡ — trigger
    `prescription_dinh_chinh_guard` chặn sửa tên/đơn vị tại chỗ, nên gán chỉ đổi
    thuốc kho."""
    rx, rac = await _rac(q)
    await q.pool.execute(
        "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid", q.visit_id
    )
    dung = await _thuoc_dv(q, f"Pricefil 5mg {q.duoi}", 4_000, "viên")
    await gan_thuoc_dung(
        q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=dung
    )
    assert (await _hd(q, "thuoc")).thu_duoc
    await hoan_tac_gan(q.pool, identity=q.thu_ngan, prescription_id=rx)
    assert (await _dong(q, rx))["thuoc"] == rac


async def test_gan_trung_thuoc_cu_va_sau_khi_thu_bi_tu_choi(q: Quay) -> None:
    rx, rac = await _rac(q)
    with pytest.raises(ValidationError, match="đã gắn đúng"):
        await gan_thuoc_dung(
            q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=rac
        )
    dung = await _thuoc_dv(q, f"Pricefil 5mg {q.duoi}", 4_000, "viên")
    await gan_thuoc_dung(
        q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=dung
    )
    await _thu(q)
    with pytest.raises(ConflictError, match="đã thu"):
        await hoan_tac_gan(q.pool, identity=q.thu_ngan, prescription_id=rx)


async def test_dong_doi_sau_lan_gan_thi_khong_hoan_tac_nham(q: Quay) -> None:
    rx, _ = await _rac(q)
    a = await _thuoc_dv(q, f"Thuốc A {q.duoi}", 4_000, "viên")
    await gan_thuoc_dung(
        q.pool, identity=q.thu_ngan, prescription_id=rx, drug_catalog_id=a
    )
    # Nhà thuốc xác định lại thuốc kho bằng đường khác sau lần gán.
    b = await _thuoc_dv(q, f"Thuốc B {q.duoi}", 5_000, "viên")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=b
    )
    with pytest.raises(ConflictError, match="đã đổi sau lần gán"):
        await hoan_tac_gan(q.pool, identity=q.thu_ngan, prescription_id=rx)


# ── Điền giá ────────────────────────────────────────────────────────────────


# Tên bài chứa "test_quyen_gia_thuoc": conftest `_cho_qua_chot_gia_thuoc` cho qua
# chốt quyền giá ở mọi bài khác — bài này phải đi chốt THẬT.
async def test_quyen_gia_thuoc_quay_khong_quyen_nut_khoa_lenh_bi_chan(
    q: Quay,
) -> None:
    rx, rac = await _rac(q)
    # Phòng khám đã cấp quyền giá cho người khác (chưa ai được cấp thì ai cũng sửa
    # được — luật chuyển tiếp của bảng quyền).
    await _cap_quyen_gia(q)
    lech = await doc_dong_lech(q.pool, identity=q.thu_ngan, visit_id=q.visit_id)
    (d,) = lech["dong"]
    assert d["prescription_id"] == rx and d["thuoc_chua_gia"]
    assert not d["dien_gia_duoc"] and "không có quyền" in d["ly_do_khong_dien_gia"]
    with pytest.raises(SafetyGateError):
        await dien_gia_thuoc(
            q.pool, identity=q.thu_ngan, drug_catalog_id=rac, gia=35_000
        )
    assert (
        await q.pool.fetchval(
            "SELECT unit_price FROM drug_catalog WHERE id = $1::uuid", rac
        )
        is None
    )


async def test_quyen_gia_thuoc_co_quyen_dien_gia_thu_duoc(q: Quay) -> None:
    _, rac = await _rac(q)
    await _cap_quyen_gia(q)
    lech = await doc_dong_lech(q.pool, identity=q.bac_si, visit_id=q.visit_id)
    assert lech["dong"][0]["dien_gia_duoc"]
    await dien_gia_thuoc(q.pool, identity=q.bac_si, drug_catalog_id=rac, gia="35.000")
    hd = await _hd(q, "thuoc")
    assert hd.thu_duoc and hd.tong == 12 * 35_000
    gia = await q.pool.fetchval(
        "SELECT payload ->> 'gia_moi' FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'pharmacy.price_changed'",
        rac,
    )
    assert gia.startswith("35000")
    # Đã có giá thì quầy không đổi được — việc của Danh mục kho.
    with pytest.raises(ConflictError, match="đã có giá"):
        await dien_gia_thuoc(q.pool, identity=q.bac_si, drug_catalog_id=rac, gia=1)


@pytest.mark.parametrize(
    "rac_vao",
    [None, "", "abc", -5, 0, "1,5e3x", 1.5, True, "9" * 20, float("nan")]
    # Dấu sai mẫu nghìn: bỏ dấu là nhân giá 10–100 lần → phải từ chối.
    + ["35000.5", "35000,50", "35.00", "3.5.000"],
)
async def test_gia_rac_tra_cau_tieng_viet_khong_500(q: Quay, rac_vao: Any) -> None:
    _, rac = await _rac(q)
    await _cap_quyen_gia(q)
    with pytest.raises(ValidationError, match="Giá bán"):
        await dien_gia_thuoc(
            q.pool, identity=q.bac_si, drug_catalog_id=rac, gia=rac_vao
        )


async def test_dong_chi_thieu_so_luong_khong_vao_khung_go_lech(q: Quay) -> None:
    rx = await _don(q, 1, ten=f"Trống số {q.duoi}")
    co_gia = await _thuoc_dv(q, f"Có giá {q.duoi}", 4_000, "viên")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=co_gia
    )
    await q.pool.execute(
        "UPDATE prescription SET quantity = NULL, quantity_num = NULL"
        " WHERE id = $1::uuid",
        rx,
    )
    lech = await doc_dong_lech(q.pool, identity=q.thu_ngan, visit_id=q.visit_id)
    assert rx not in {d["prescription_id"] for d in lech["dong"]}


def test_gia_quay_doc_so_ham_thuan() -> None:
    assert gia_quay("35.000") == 35_000
    assert gia_quay(35000) == 35_000
    assert gia_quay("1,200,000") == 1_200_000
    assert gia_quay("35000.5") is None
    assert gia_quay("0") is None
    assert gia_quay(object()) is None


def test_bo_gan_duoc_ham_thuan() -> None:
    hien = {"thuoc": "b", "ten": "B", "don_vi": "viên"}
    assert bo_gan_duoc({"hanh_dong": "GAN_THUOC", "moi": hien}, hien)
    assert not bo_gan_duoc({"hanh_dong": "BO_GAN_THUOC", "moi": hien}, hien)
    assert not bo_gan_duoc(None, hien)
    assert not bo_gan_duoc(
        {"hanh_dong": "GAN_THUOC", "moi": {**hien, "ten": "x"}}, hien
    )
