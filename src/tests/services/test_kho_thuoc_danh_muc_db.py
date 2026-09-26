"""Kho thuốc — danh mục chuẩn KiotViet + dược sĩ tự sửa (Tuyền 25/09/2026).

* Danh mục phòng khám mẫu sau seed = 82 mặt hàng KiotViet + 9 thuốc chỉ có trên
  phiếu (cần soát); giá theo KiotViet; hướng dẫn theo phiếu v5.
* Một nguồn giá: `service_price` nhóm thuốc đã tắt.
* Dược sĩ thêm / sửa thuốc; màn kê đơn đọc tên, giá, hướng dẫn từ kho.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.phieu_kham_service import PhieuKhamService
from tests.services.test_phieu_kham_db import CLINIC, _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_danh_muc_chuan_kiotviet_va_mot_nguon_gia(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        # Chạy lại hàm chuẩn hoá — thuốc thêm bởi bài kiểm khác sẽ bị TẮT, đúng
        # luật "không có trong danh mục chuẩn thì tắt".
        await conn.execute("SELECT public.chuan_hoa_danh_muc_thuoc_kiotviet()")
        rows = {
            r["name_raw"]: r
            for r in await conn.fetch(
                "SELECT name_raw, unit_price, don_vi_ban, cach_dung, needs_review,"
                " ma_hang FROM drug_catalog WHERE clinic_id = $1::uuid AND is_active",
                CLINIC,
            )
        }
        gia_thuoc_cu = await conn.fetchval(
            "SELECT count(*) FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'thuoc' AND active",
            CLINIC,
        )
    assert len(rows) == 91
    assert sum(1 for r in rows.values() if r["needs_review"]) == 9
    betmiga = rows["Betmiga 50mg"]
    assert (int(betmiga["unit_price"]), betmiga["don_vi_ban"]) == (35000, "viên")
    assert betmiga["ma_hang"] == "SP000087"
    assert betmiga["cach_dung"], "hướng dẫn từ phiếu v5"
    assert rows["Follitrope"]["needs_review"], "chỉ có trên phiếu → cần soát"
    assert gia_thuoc_cu == 0, "một nguồn giá: service_price nhóm thuốc đã tắt"


async def test_duoc_si_them_sua_thuoc(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
    svc = PharmacyService(pool)
    ten = f"Thuốc thử kho {uuid.uuid4().hex[:6]}"
    kq = await svc.luu_thuoc(
        identity=ds,
        drug_catalog_id=None,
        ten=f"  {ten} ",
        gia="120000",
        don_vi_ban="hộp",
        cach_dung="Ngày uống 1 viên.",
    )
    await svc.luu_thuoc(
        identity=ds,
        drug_catalog_id=kq["id"],
        ten=ten,
        gia=0,
        don_vi_ban="hộp",
        cach_dung="Ngày uống 2 viên.",
        dang_dung=False,
    )
    dong = {d["id"]: d for d in await svc.danh_muc(identity=ds)}[kq["id"]]
    assert dong["ten"] == ten
    assert (int(dong["gia"]), dong["cach_dung"], dong["dang_dung"]) == (
        0,
        "Ngày uống 2 viên.",
        False,
    )
    assert dong["can_soat"] is False, "dược sĩ lưu = đã soát"

    with pytest.raises(ConflictError):
        await svc.luu_thuoc(identity=ds, drug_catalog_id=None, ten=ten.upper())
    for rac in ("abc", "-5", "NaN"):
        with pytest.raises(ValidationError):
            await svc.luu_thuoc(
                identity=ds, drug_catalog_id=None, ten=ten + rac, gia=rac
            )


async def test_ke_don_doc_huong_dan_tu_kho(pool: asyncpg.Pool) -> None:  # noqa: F811
    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        await conn.execute("SELECT public.chuan_hoa_danh_muc_thuoc_kiotviet()")
    ds = PharmacyService(pool)
    # Dược sĩ sửa hướng dẫn một thuốc trên phiếu → màn kê đơn đổi theo.
    utro = next(
        d
        for d in await ds.danh_muc(identity=bs)
        if d["ten"] == "Utrogestan 200" and d["dang_dung"]
    )
    await ds.luu_thuoc(
        identity=bs,
        drug_catalog_id=utro["id"],
        ten="Utrogestan 200",
        gia=utro["gia"],
        don_vi_ban=utro["don_vi_ban"],
        cach_dung="Hướng dẫn dược sĩ vừa sửa",
    )
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(identity=bs)
    mau = {m["nhan_nguon"]: m for m in tc["mau_thuoc"]}
    assert mau["Utrogestan 200 (D/U) (1v/2v)"]["dosage"] == "Hướng dẫn dược sĩ vừa sửa"
    assert mau["Utrogestan 200 (D/U) (1v/2v)"]["drug_catalog_id"] == utro["id"]
    # Mặt hàng chỉ có ở kho (không có trên phiếu) cũng chọn được.
    assert mau["King Seal"]["drug_catalog_id"] and mau["King Seal"]["gia"] == 930000
    # Mọi dòng của phiếu đều gắn được thuốc kho (không còn "chưa gắn kho").
    assert all(m["drug_catalog_id"] for m in tc["mau_thuoc"])
