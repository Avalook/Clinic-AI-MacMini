"""PR B (26/11/2026): ô chọn kê đơn có tồn; xoá thuốc = lưu bản chụp rồi xoá, khôi phục.

Kế hoạch `docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md` mục 5, 13, 15. Tuyền đổi ý 26/11:
kê đơn GIỮ như cũ (gõ tên tự do, tên lạ tự vào danh mục, thuốc chưa giá vẫn chọn
được) — chỉ thêm tồn; xoá thuốc phải "lưu vào đâu đó trước đã rồi xoá".
Bất biến ép ở Postgres: một bản lưu chưa khôi phục cho một thuốc (UNIQUE từng phần
`uq_drug_catalog_da_xoa_chua_khoi_phuc`); xoá thuốc đã dùng bị khoá ngoại chặn.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thuoc import khoi_phuc_thuoc, xoa_thuoc
from tests.services.test_phieu_kham_db import CLINIC, _luot, _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _hau() -> str:
    return uuid.uuid4().hex[:6]


async def _thuoc(conn: asyncpg.Connection, ten: str, *, gia: int | None = 33000) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, unit_price,"
            " don_vi_ban, ma_hang) VALUES ($1::uuid, $2, $2, $3, 'hộp', $4)"
            " RETURNING id::text",
            CLINIC,
            ten,
            gia,
            f"SP-{_hau()}",
        )
    )


async def _nhap_lo(conn: asyncpg.Connection, ds: Any, thuoc: str, so: int) -> None:
    lo = await conn.fetchval(
        "INSERT INTO drug_batch (clinic_id, location_id, drug_catalog_id,"
        " batch_code, expiry_date, quantity_on_hand, unit, noi_chua, received_at,"
        " ma_tem) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, '2099-12-31', 0, 'hộp',"
        " 'QUAY', now(), 'LT' || lpad(nextval('drug_batch_tem_seq')::text, 8, '0'))"
        " RETURNING id::text",
        CLINIC,
        ds.location_id,
        thuoc,
        f"LO-{_hau()}",
    )
    await conn.execute(
        "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
        " reason, ref_type, performed_by_staff_id)"
        " VALUES ($1::uuid, $2::uuid, 'RECEIVE', $3, 'Nhập thử', 'manual', $4::uuid)",
        CLINIC,
        lo,
        so,
        ds.staff_id,
    )


def _dong(ten: str, ma: str | None = None) -> dict[str, Any]:
    return {
        "id": None,
        "drug_catalog_id": ma,
        "drug_name": ten,
        "quantity": "1 hộp",
        "dosage": "Uống",
        "caution": "",
    }


async def test_o_chon_co_ton_con_hang_truoc_khong_chan_gi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        con = await _thuoc(conn, f"Thuốc còn hàng {h}")
        het = await _thuoc(conn, f"Thuốc hết hàng {h}")
        khong_gia = await _thuoc(conn, f"Thuốc chưa giá {h}", gia=None)
        await _nhap_lo(conn, bs, con, 3)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    mau = (await svc.tham_chieu_that(identity=bs))["mau_thuoc"]
    theo = {m["drug_catalog_id"]: m for m in mau if m["drug_catalog_id"]}
    assert (theo[con]["ton_chu"], theo[con]["con_hang"]) == ("còn 3 hộp", True)
    assert (theo[het]["ton_chu"], theo[het]["con_hang"]) == ("hết hàng", False)
    assert theo[khong_gia]["gia"] is None, "thuốc chưa giá vẫn có trong ô chọn"
    con_hang = [m["con_hang"] for m in mau]
    assert con_hang == sorted(con_hang, reverse=True), "còn hàng xếp trước"


async def test_ten_la_van_tu_vao_danh_muc_nhu_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 26/11: "kệ bác sĩ muốn gõ cứ cho gõ" — đường cũ giữ nguyên."""
    ten = f"Thuốc gõ tay {_hau()}"
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    await svc.luu_don_thuoc(
        visit_id=luot["visit"], dong=[_dong(ten)], ly_do=None, identity=bs
    )
    (d,) = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert d["drug_catalog_id"] is not None and d["don_gia"] is None


async def test_xoa_luu_ban_chup_roi_xoa_va_khoi_phuc_y_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
        thuoc = await _thuoc(conn, f"Thuốc chưa dùng {h}")
        await conn.execute(
            "INSERT INTO thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so,"
            " gia, dang_ban) VALUES ($1::uuid, $2::uuid, 'vỉ', 0.1, 4000, true)",
            CLINIC,
            thuoc,
        )
        truoc = await conn.fetchval(
            "SELECT to_jsonb(c.*)::text FROM drug_catalog c WHERE id = $1::uuid", thuoc
        )
    assert (await xoa_thuoc.thuoc_xoa_duoc(pool, identity=ds, thuoc_id=thuoc))[
        "xoa_duoc"
    ], "đơn vị quy đổi là định nghĩa của thuốc, không phải 'đã dùng'"
    for rac in ("", "   ", None, "x" * 501):
        with pytest.raises(ValidationError):
            await xoa_thuoc.xoa_thuoc(pool, identity=ds, thuoc_id=thuoc, ly_do=rac)
    kq = await xoa_thuoc.xoa_thuoc(
        pool, identity=ds, thuoc_id=thuoc, ly_do="  Nhập trùng  "
    )
    async with pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM drug_catalog WHERE id = $1::uuid", thuoc
        )
        luu = await conn.fetchrow(
            "SELECT ly_do, xoa_boi::text, jsonb_array_length(quy_doi) AS so_qd"
            " FROM drug_catalog_da_xoa WHERE id = $1::uuid",
            kq["ban_luu_id"],
        )
        nhat_ky = await conn.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type = 'pharmacy.drug_deleted'"
            " AND aggregate_id = $1::uuid",
            thuoc,
        )
    assert (luu["ly_do"], luu["xoa_boi"], luu["so_qd"]) == (
        "Nhập trùng",
        ds.staff_id,
        1,
    )
    assert nhat_ky == 1
    ds_xoa = await khoi_phuc_thuoc.danh_sach_da_xoa(pool, identity=ds)
    assert any(x["id"] == kq["ban_luu_id"] and not x["da_khoi_phuc"] for x in ds_xoa)

    await khoi_phuc_thuoc.khoi_phuc(pool, identity=ds, ban_luu_id=kq["ban_luu_id"])
    async with pool.acquire() as conn:
        sau = await conn.fetchval(
            "SELECT to_jsonb(c.*)::text FROM drug_catalog c WHERE id = $1::uuid", thuoc
        )
        so_qd = await conn.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", thuoc
        )
    assert json.loads(sau) == json.loads(truoc), "khôi phục đúng nguyên dòng cũ"
    assert so_qd == 1
    with pytest.raises(ConflictError):
        await khoi_phuc_thuoc.khoi_phuc(pool, identity=ds, ban_luu_id=kq["ban_luu_id"])


async def test_khoi_phuc_tu_choi_khi_da_co_thuoc_trung_ten(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ten = f"Thuốc trùng {_hau()}"
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
        thuoc = await _thuoc(conn, ten)
    kq = await xoa_thuoc.xoa_thuoc(pool, identity=ds, thuoc_id=thuoc, ly_do="Thử")
    async with pool.acquire() as conn:
        await _thuoc(conn, ten)
    with pytest.raises(ConflictError, match="trùng tên"):
        await khoi_phuc_thuoc.khoi_phuc(pool, identity=ds, ban_luu_id=kq["ban_luu_id"])
    async with pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT khoi_phuc_luc IS NOT NULL FROM drug_catalog_da_xoa"
            " WHERE id = $1::uuid",
            kq["ban_luu_id"],
        ), "khôi phục hỏng thì bản lưu vẫn chưa khôi phục"


async def test_thuoc_da_co_don_thi_tu_choi_xoa_chi_tat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        cu = await _thuoc(conn, f"Thuốc có đơn {h}")
    await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).luu_don_thuoc(
        visit_id=luot["visit"],
        dong=[_dong(f"Thuốc có đơn {h}", cu)],
        ly_do=None,
        identity=bs,
    )
    kq = await xoa_thuoc.thuoc_xoa_duoc(pool, identity=ds, thuoc_id=cu)
    assert kq["xoa_duoc"] is False and "dòng đơn thuốc" in kq["ly_do"]
    with pytest.raises(ConflictError):
        await xoa_thuoc.xoa_thuoc(pool, identity=ds, thuoc_id=cu, ly_do="Thử xoá")
    async with pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT count(*) FROM drug_catalog WHERE id = $1::uuid", cu
        )
        assert not await conn.fetchval(
            "SELECT count(*) FROM drug_catalog_da_xoa WHERE drug_catalog_id = $1::uuid",
            cu,
        ), "từ chối thì không để lại bản lưu mồ côi"
