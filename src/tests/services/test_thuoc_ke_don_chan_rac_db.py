"""PR B (26/11/2026): kê đơn không còn đẻ thuốc rác, ô chọn có tồn, nhờ kho, xoá thuốc.

Kế hoạch `docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md` mục 7, 12, 13, 15, 16 (PR B).
Bất biến ép ở Postgres: một yêu cầu nhờ kho đang mở cho một tên (UNIQUE từng phần
`uq_thuoc_nho_kho_dang_mo`); xoá thuốc đã dùng bị khoá ngoại RESTRICT chặn.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thuoc import nho_kho, xoa_thuoc
from clinicai.services.thuoc.goi_y import goi_y_thuoc
from tests.services.test_phieu_kham_db import CLINIC, _luot, _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _hau() -> str:
    return uuid.uuid4().hex[:6]


async def _thuoc(
    conn: asyncpg.Connection,
    ten: str,
    *,
    gia: int | None = 33000,
    don_vi: str | None = "hộp",
    biet_duoc: str | None = None,
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, unit_price,"
            " don_vi_ban, biet_duoc) VALUES ($1::uuid, $2, $2, $3, $4, $5)"
            " RETURNING id::text",
            CLINIC,
            ten,
            gia,
            don_vi,
            biet_duoc,
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


async def _so_thuoc(conn: asyncpg.Connection) -> int:
    return int(
        await conn.fetchval(
            "SELECT count(*) FROM drug_catalog WHERE clinic_id = $1::uuid", CLINIC
        )
    )


async def test_luu_ten_la_bi_tu_choi_kem_goi_y_va_khong_them_thuoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await _thuoc(conn, f"Idurat 5mg {h}", biet_duoc="Indurat 5mg / Tadalafil")
        truoc = await _so_thuoc(conn)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    with pytest.raises(ValidationError) as loi:
        await svc.luu_don_thuoc(
            visit_id=luot["visit"], dong=[_dong("Indurate")], ly_do=None, identity=bs
        )
    assert "không có trong danh mục" in str(loi.value)
    assert f"Idurat 5mg {h}" in str(loi.value), "gợi ý theo biệt dược"
    async with pool.acquire() as conn:
        assert await _so_thuoc(conn) == truoc, "lưu đơn không được tạo thuốc mới"
        so_dong = await conn.fetchval(
            "SELECT count(*) FROM prescription WHERE visit_id = $1::uuid",
            luot["visit"],
        )
    assert so_dong == 0, "cả lần lưu bị huỷ, không dòng nào lọt"

    # Tên trùng khít (khác hoa/thường, dấu cách) vẫn tự gắn đúng thuốc kho.
    await svc.luu_don_thuoc(
        visit_id=luot["visit"],
        dong=[_dong(f"  IDURAT   5MG {h.upper()} ")],
        ly_do=None,
        identity=bs,
    )
    (d,) = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert d["drug_catalog_id"] is not None
    async with pool.acquire() as conn:
        assert await _so_thuoc(conn) == truoc


async def test_goi_y_bon_ca_that_theo_ten_va_biet_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        ma = {
            "Indurate": await _thuoc(
                conn, f"Idurat 5mg {h}", biet_duoc="Indurat 5mg / Tadalafil"
            ),
            "AktiveMeno": await _thuoc(conn, f"Aktiv isoflavon {h}"),
            "vicofol": await _thuoc(conn, f"Vitcofol {h}"),
            "gynoflor": await _thuoc(conn, f"Eulac {h}", biet_duoc="Gynoflor"),
        }
        # Thuốc rác không giá khớp chữ rất sát — không được gợi ý.
        rac = await _thuoc(conn, f"Indurate 5 (D/U) {h}", gia=None, don_vi=None)
        for go, ma_dung in ma.items():
            ids = [g["drug_catalog_id"] for g in await goi_y_thuoc(conn, CLINIC, go)]
            assert ma_dung in ids, go
            assert rac not in ids
        for go in ("", "   ", "!!!@@@", "x" * 100_000, "'; DROP TABLE x; --", "\x00"):
            assert await goi_y_thuoc(conn, CLINIC, go) == [], repr(go[:10])


async def test_o_chon_chi_thuoc_kho_co_ton_va_co_gia_chon_duoc(
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
    theo = {m["drug_catalog_id"]: m for m in mau}
    assert all(m["drug_catalog_id"] for m in mau), "nhãn chưa gắn thuốc kho bị bỏ"
    assert (theo[con]["ton_chu"], theo[con]["con_hang"]) == ("còn 3 hộp", True)
    assert (theo[het]["ton_chu"], theo[het]["con_hang"]) == ("hết hàng", False)
    assert theo[het]["chon_duoc"] is True, "hết hàng vẫn kê được"
    assert theo[khong_gia]["chon_duoc"] is False
    assert "Chưa có giá" in theo[khong_gia]["ly_do_khong_chon"]
    thu_tu = [(not m["chon_duoc"], not m["con_hang"]) for m in mau]
    assert thu_tu == sorted(thu_tu), "còn hàng trước, chưa giá cuối"


async def test_xoa_thuoc_chua_dung_xoa_that_da_co_don_thi_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        ds = await _nguoi(conn, "PHARMACIST")
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        moi = await _thuoc(conn, f"Thuốc chưa dùng {h}")
        cu = await _thuoc(conn, f"Thuốc có đơn {h}")
    await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).luu_don_thuoc(
        visit_id=luot["visit"],
        dong=[_dong(f"Thuốc có đơn {h}", cu)],
        ly_do=None,
        identity=bs,
    )
    assert (await xoa_thuoc.thuoc_xoa_duoc(pool, identity=ds, thuoc_id=moi))["xoa_duoc"]
    kq = await xoa_thuoc.thuoc_xoa_duoc(pool, identity=ds, thuoc_id=cu)
    assert kq["xoa_duoc"] is False and "dòng đơn thuốc" in kq["ly_do"]
    with pytest.raises(ConflictError):
        await xoa_thuoc.xoa_thuoc(pool, identity=ds, thuoc_id=cu)

    await xoa_thuoc.xoa_thuoc(pool, identity=ds, thuoc_id=moi)
    async with pool.acquire() as conn:
        con_lai = await conn.fetchval(
            "SELECT count(*) FROM drug_catalog WHERE id = ANY($1::uuid[])", [moi, cu]
        )
        nhat_ky = await conn.fetchrow(
            "SELECT payload->>'ten' AS ten, metadata->>'clinic_staff_id' AS ai"
            " FROM event_log WHERE event_type = 'pharmacy.drug_deleted'"
            " AND aggregate_id = $1::uuid",
            moi,
        )
    assert con_lai == 1, "chỉ thuốc chưa dùng bị xoá"
    assert nhat_ky is not None and nhat_ky["ten"] == f"Thuốc chưa dùng {h}"
    assert nhat_ky["ai"] == ds.staff_id, "ghi ai xoá"


async def test_nho_kho_tao_mot_yeu_cau_mot_su_kien_xong_va_mo_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = _hau()
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        ds = await _nguoi(conn, "PHARMACIST")
    a = await nho_kho.nho_kho_them(pool, identity=bs, ten=f"  Thuốc lạ   {h} ")
    b = await nho_kho.nho_kho_them(pool, identity=bs, ten=f"THUỐC LẠ {h}")
    assert a["moi"] and not b["moi"] and a["id"] == b["id"], "trùng tên = một yêu cầu"
    async with pool.acquire() as conn:
        so_su_kien = await conn.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'pharmacy.drug_requested' AND aggregate_id = $1::uuid",
            a["id"],
        )
    assert so_su_kien == 1, "nhờ trùng không réo chuông lần nữa"
    ds_mo = await nho_kho.danh_sach_nho_kho(pool, identity=ds)
    assert any(x["id"] == a["id"] and not x["xong"] for x in ds_mo)

    await nho_kho.danh_dau_nho_kho(pool, identity=ds, yeu_cau_id=a["id"], xong=True)
    c = await nho_kho.nho_kho_them(pool, identity=bs, ten=f"Thuốc lạ {h}")
    assert c["moi"] and c["id"] != a["id"], "yêu cầu cũ xong thì nhờ lại được"
    with pytest.raises(ConflictError):
        await nho_kho.danh_dau_nho_kho(
            pool, identity=ds, yeu_cau_id=a["id"], xong=False
        )
    await nho_kho.danh_dau_nho_kho(pool, identity=ds, yeu_cau_id=c["id"], xong=True)
    await nho_kho.danh_dau_nho_kho(pool, identity=ds, yeu_cau_id=a["id"], xong=False)

    for rac in ("", "   ", "x" * 201, None):
        with pytest.raises(ValidationError):
            await nho_kho.nho_kho_them(pool, identity=bs, ten=rac)
    la = await nho_kho.nho_kho_them(
        pool, identity=bs, ten=f"@@ {h} ##", ghi_chu="y" * 9999
    )
    assert la["moi"]
