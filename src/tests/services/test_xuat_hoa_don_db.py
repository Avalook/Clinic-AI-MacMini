"""Xuất hoá đơn mẫu MISA: SQL đọc ĐVT + địa chỉ / CCCD / email trên Postgres thật."""

import io
from dataclasses import replace
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
from openpyxl import load_workbook

from clinicai.api.identity import ClinicRole
from clinicai.core.clock import now_vn
from clinicai.services.quay_thu_service import ma_phieu
from clinicai.services.xuat_hoa_don_service import (
    DONG_DAU,
    XuatHoaDonService,
    xlsx_misa,
)
from tests.services.test_luot_kham_service_db import _nguoi
from tests.services.test_tien_thuoc_cp1_db import _chi_dinh, _don, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_xuat_hoa_don_doc_dvt_va_thong_tin_khach(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    cycle, huy = str(uuid4()), str(uuid4())
    for cid, status in ((cycle, "PAID"), (huy, "VOIDED")):
        await pool.execute(
            "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,"
            "amount,status,legacy,paid_at,closed_at,created_at,created_by,"
            "confirmed_by,method) VALUES($1::uuid,$2::uuid,$3::uuid,'dich_vu',"
            "350000,$5,true,now(),CASE WHEN $5='VOIDED' THEN now() END,now(),"
            "$4::uuid,$4::uuid,'TRANSFER')",
            cid,
            manager.clinic_id,
            q.visit_id,
            manager.staff_id,
            status,
        )
    for src, ten, unit, gia in (
        ("exam", "Khám phụ khoa", None, 300000),
        ("vat_tu", "Que thử", "Cái", 50000),
    ):
        await pool.execute(
            "INSERT INTO payment_bill_line(clinic_id,payment_cycle_id,visit_id,"
            "kind,source_type,source_id,name_snapshot,quantity,unit,unit_price,"
            "line_total,billing_owner) VALUES($1::uuid,$2::uuid,$3::uuid,"
            "'dich_vu',$4,'x',$5,1,$6,$7,$7,'CLINIC')",
            manager.clinic_id,
            cycle,
            q.visit_id,
            src,
            ten,
            unit,
            gia,
        )
    patient = await pool.fetchval(
        "UPDATE patient p SET address=NULL,address_detail='12 Kim Ngưu',"
        "ward_name='Phường Vĩnh Tuy',province_name='Hà Nội',"
        "national_id_number='001190000001' FROM visit v"
        " WHERE v.visit_id=$1::uuid AND p.clinic_patient_id=v.clinic_patient_id"
        " RETURNING p.clinic_patient_id",
        q.visit_id,
    )
    await pool.execute(
        "INSERT INTO patient_contact_channel(clinic_id,clinic_patient_id,"
        "channel_type,channel_value,is_primary) VALUES($1::uuid,$2,'EMAIL',"
        "'khach@example.com',true)",
        manager.clinic_id,
        patient,
    )
    day = now_vn().date().isoformat()
    data = await XuatHoaDonService(pool).xem(identity=manager, tu=day, den=day)
    ma = {h["ma_phieu"]: h for h in data["hoa_don"]}
    assert ma_phieu(huy) not in ma
    hd = ma[ma_phieu(cycle)]
    assert hd["dia_chi"] == "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội"
    assert hd["cccd"] == "001190000001" and hd["email"] == "khach@example.com"
    assert hd["hinh_thuc"] == "Chuyển khoản" and hd["ma_so_thue"] == ""
    assert [(d["ten"], d["dvt"], d["thanh_tien"]) for d in hd["dong"]] == [
        ("Khám phụ khoa", "Lần", 300000),
        ("Que thử", "Cái", 50000),
    ]
    ws: Any = load_workbook(io.BytesIO(xlsx_misa([hd]))).active
    assert ws.cell(DONG_DAU, 7).value == "khach@example.com"
    # Số thứ tự = vị trí trong file (DB chung có phiếu của bài khác) — so theo hd.
    assert [ws.cell(DONG_DAU + 1, c).value for c in (1, 13, 14, 17)] == [
        str(hd["stt"]),
        "Que thử",
        "Cái",
        50000,
    ]
    # Ngày rác → mặc định, không ném.
    assert "hoa_don" in await XuatHoaDonService(pool).xem(
        identity=manager, tu="rác", den="31/02"
    )


async def _ten(pool: asyncpg.Pool, staff_id: str) -> str:
    return str(
        await pool.fetchval("SELECT full_name FROM staff WHERE id=$1::uuid", staff_id)
    )


async def test_xuat_hoa_don_ghi_bac_si_chi_dinh_va_thuc_hien(
    pool: asyncpg.Pool,
) -> None:
    """Tuyền 19/11: mỗi dòng có bác sĩ chỉ định + bác sĩ thực hiện.

    Dịch vụ: chỉ định = `bac_si_ky.sql_join_bac_si_chi_dinh` (người duyệt → người
    ghi → BS chính của lượt → BS lịch hẹn, chỉ người LÀ bác sĩ), thực hiện =
    `bac_si_lam_id`. Khám: thực hiện = bác sĩ phiên khám chính. Thuốc: chỉ định =
    bác sĩ kê. Không bao giờ hiện tên người không phải bác sĩ; không có → trống."""
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT p.location_id::text FROM patient p JOIN visit v"
            " ON v.clinic_patient_id=p.clinic_patient_id WHERE v.visit_id=$1::uuid",
            q.visit_id,
        )
        bs_lam = await _nguoi(conn, loc, "DOCTOR")
    so_lam = await _chi_dinh(q, f"SA-{q.duoi}", "Siêu âm thử")
    so_trong = await _chi_dinh(q, f"SB-{q.duoi}", "Soi thử")
    # Thư ký / lễ tân bấm hộ: máy ghi người bấm vào authorized_by + recorded_by
    # (luật 23/09). Cột "BS chỉ định" KHÔNG được hiện tên người không phải bác sĩ
    # (luật 29/09, `bac_si_ky`) → bác sĩ của phiên khám ra chỉ định (staging
    # 19/11: "Vũ Thị Huế" — tài khoản TKYK — hiện ở cột BS chỉ định).
    so_thu_ky = await _chi_dinh(q, f"SC-{q.duoi}", "Ghế điện thử")
    await pool.execute(
        "UPDATE service_order SET authorized_by=$2::uuid, recorded_by=$2::uuid"
        " WHERE id=$1::uuid",
        so_thu_ky,
        q.thu_ngan.staff_id,
    )
    await pool.execute(
        "UPDATE service_order SET bac_si_lam_id=$2::uuid, bac_si_lam_boi=$2::uuid,"
        " bac_si_lam_luc=now() WHERE id=$1::uuid",
        so_lam,
        bs_lam.staff_id,
    )
    await pool.execute(
        "UPDATE consultation SET doctor_staff_id=$2::uuid WHERE id=$1::uuid",
        q.consultation_id,
        bs_lam.staff_id,
    )
    rx = await _don(q, ten="Thuốc kê thử")
    rx_trong = await _don(q, ten="Thuốc không ghi bác sĩ")
    await pool.execute(
        "UPDATE prescription SET bac_si_chinh_id=$2::uuid WHERE id=$1::uuid",
        rx,
        q.bac_si.staff_id,
    )
    await pool.execute(
        "UPDATE prescription SET bac_si_chinh_id=NULL WHERE id=$1::uuid", rx_trong
    )
    cycle = str(uuid4())
    await pool.execute(
        "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,"
        "amount,status,legacy,paid_at,created_at,created_by,confirmed_by,method)"
        " VALUES($1::uuid,$2::uuid,$3::uuid,'dich_vu',500,'PAID',true,now(),now(),"
        "$4::uuid,$4::uuid,'CASH')",
        cycle,
        manager.clinic_id,
        q.visit_id,
        manager.staff_id,
    )
    cycle_thuoc = str(uuid4())
    await pool.execute(
        "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,"
        "amount,status,legacy,paid_at,created_at,created_by,confirmed_by,method)"
        " VALUES($1::uuid,$2::uuid,$3::uuid,'thuoc',200,'PAID',true,now(),now(),"
        "$4::uuid,$4::uuid,'CASH')",
        cycle_thuoc,
        manager.clinic_id,
        q.visit_id,
        manager.staff_id,
    )
    for cid, kind, src, sid, ten in (
        (cycle, "dich_vu", "service_order", so_lam, "Siêu âm thử"),
        (cycle, "dich_vu", "service_order", so_trong, "Soi thử"),
        (cycle, "dich_vu", "service_order", so_thu_ky, "Ghế điện thử"),
        (cycle, "dich_vu", "exam", f"exam-{q.visit_id}", "Khám thử"),
        (cycle, "dich_vu", "vat_tu", str(uuid4()), "Que thử"),
        (cycle_thuoc, "thuoc", "prescription", rx, "Thuốc kê thử"),
        (cycle_thuoc, "thuoc", "prescription", rx_trong, "Thuốc không ghi bác sĩ"),
    ):
        await pool.execute(
            "INSERT INTO payment_bill_line(clinic_id,payment_cycle_id,visit_id,"
            "kind,source_type,source_id,name_snapshot,quantity,unit_price,"
            "line_total,billing_owner) VALUES($1::uuid,$2::uuid,$3::uuid,"
            "$7,$4,$5,$6,1,100,100,'CLINIC')",
            manager.clinic_id,
            cid,
            q.visit_id,
            src,
            sid,
            ten,
            kind,
        )
    day = now_vn().date().isoformat()
    data = await XuatHoaDonService(pool).xem(identity=manager, tu=day, den=day)
    theo_phieu = {h["ma_phieu"]: h for h in data["hoa_don"]}
    hd, hd_thuoc = theo_phieu[ma_phieu(cycle)], theo_phieu[ma_phieu(cycle_thuoc)]
    bs_cd, bs_th = (
        await _ten(pool, q.bac_si.staff_id),
        await _ten(pool, bs_lam.staff_id),
    )
    assert {
        d["ten"]: (d["bs_chi_dinh"], d["bs_thuc_hien"])
        for d in hd["dong"] + hd_thuoc["dong"]
    } == {
        "Siêu âm thử": (bs_cd, bs_th),
        "Soi thử": (bs_cd, ""),
        # Người bấm không phải bác sĩ → bác sĩ của PHIÊN KHÁM ra chỉ định (bài
        # này đặt phiên cho bs_lam), không phải người bấm, không phải BS của lượt.
        "Ghế điện thử": (bs_th, ""),
        "Khám thử": ("", bs_th),
        "Que thử": ("", ""),
        "Thuốc kê thử": (bs_cd, ""),
        "Thuốc không ghi bác sĩ": ("", ""),
    }
    ws: Any = load_workbook(io.BytesIO(xlsx_misa([hd]))).active
    hang = {
        ws.cell(r, 13).value: (ws.cell(r, 18).value, ws.cell(r, 19).value)
        for r in range(DONG_DAU, DONG_DAU + len(hd["dong"]))
    }
    assert hang["Siêu âm thử"] == (bs_cd, bs_th)
    assert hang["Khám thử"] == (None, bs_th)
