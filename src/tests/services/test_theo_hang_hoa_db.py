"""Theo hàng hoá (G5a): SQL đọc mã hàng + giảm giá trên Postgres thật, và cổng quyền."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.theo_hang_hoa_service import TheoHangHoaService
from tests.services.test_quyen_lego_man_db import _nguoi as nguoi_theo_lego
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_theo_hang_hoa_doc_ma_giam_gia_va_cong_quyen(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    quan_ly = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    duoi = uuid4().hex[:6]
    thuoc = await pool.fetchval(
        "INSERT INTO drug_catalog(clinic_id,name_base,name_raw,ma_hang,unit_price)"
        " VALUES($1::uuid,$2,$2,$3,25000) RETURNING id::text",
        quan_ly.clinic_id,
        f"Thuốc kế toán {duoi}",
        f"KT-{duoi}",
    )
    cycle, cycle_thuoc = str(uuid4()), str(uuid4())
    for cid, kind, tien in ((cycle, "dich_vu", 320000), (cycle_thuoc, "thuoc", 75000)):
        await pool.execute(
            "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,"
            "amount,status,legacy,paid_at,created_at,created_by,confirmed_by,method)"
            " VALUES($1::uuid,$2::uuid,$3::uuid,$5,$6,'PAID',true,now(),"
            "now(),$4::uuid,$4::uuid,'CASH')",
            cid,
            quan_ly.clinic_id,
            q.visit_id,
            quan_ly.staff_id,
            kind,
            tien,
        )
    # (nguồn, tên, đơn vị, SL, đơn giá, giảm đã chia, id thuốc)
    dong = (
        ("exam", f"Khám {duoi}", None, 1, 300000, 30000, None),
        ("vat_tu", f"Que thử {duoi}", "Cái", 2, 25000, 0, None),
        ("prescription", f"Thuốc kế toán {duoi}", "Hộp", 3, 25000, 0, thuoc),
    )
    for src, ten, dvt, sl, gia, giam, th in dong:
        tong = sl * gia - giam
        kind, cid = ("thuoc", cycle_thuoc) if th else ("dich_vu", cycle)
        await pool.execute(
            "INSERT INTO payment_bill_line(clinic_id,payment_cycle_id,visit_id,"
            "kind,source_type,source_id,name_snapshot,quantity,unit,unit_price,"
            "line_total,billing_owner,discount_allocated,drug_catalog_id)"
            " VALUES($1::uuid,$2::uuid,$3::uuid,$13,$4,$5,$6,$7,$8,$9,$10,"
            "'CLINIC',$11,$12::uuid)",
            quan_ly.clinic_id,
            cid,
            q.visit_id,
            src,
            f"{src}-{duoi}",
            ten,
            sl,
            dvt,
            gia,
            tong,
            giam,
            th,
            kind,
        )
    ngay = now_vn().date().isoformat()
    svc = TheoHangHoaService(pool)
    data = await svc.xem(identity=quan_ly, tu=ngay, den=ngay)
    theo_ten = {h["ten"]: h for h in data["hang_hoa"]}
    kham = theo_ten[f"Khám {duoi}"]
    assert (kham["nhom"], kham["dvt"]) == ("DICH_VU", "Lần")
    assert (kham["tien_truoc_giam"], kham["giam_gia"], kham["tien_sau_giam"]) == (
        300000,
        30000,
        270000,
    )
    assert theo_ten[f"Que thử {duoi}"]["nhom"] == "VAT_TU"
    t = theo_ten[f"Thuốc kế toán {duoi}"]
    assert (t["nhom"], t["ma"], t["so_luong"], t["tien_sau_giam"]) == (
        "THUOC",
        f"KT-{duoi}",
        3,
        75000,
    )
    # Người không có lego Kế toán / Quản lý: cùng cổng với Xuất hoá đơn → chặn.
    khac = await nguoi_theo_lego(pool, "CSKH", ["bao_cao"])
    with pytest.raises(SafetyGateError):
        await svc.xem(identity=khac, tu=ngay, den=ngay)
    # Gói Kế toán (vai tài khoản không liên quan) xem được như Quản lý.
    ke_toan = await nguoi_theo_lego(
        pool, "CSKH", ["bao_cao", "ke_toan", "ds_benh_nhan", "lich_lam_viec"]
    )
    kt = await svc.xem(identity=ke_toan, tu=ngay, den=ngay)
    assert {h["ten"] for h in kt["hang_hoa"]} == {h["ten"] for h in data["hang_hoa"]}
    # Ngày rác → mặc định, không ném.
    assert "hang_hoa" in await svc.xem(identity=quan_ly, tu="rác", den="31/02")
