"""Tick "xuất hoá đơn về công ty" Ở QUẦY THU (Tuyền 16/10/2026) trên Postgres thật.

Luật: tick theo LƯỢT (phiếu thu), không theo hồ sơ — hồ sơ chỉ giữ danh sách công
ty; lượt nào không tick vẫn xuất cá nhân. Thu ngân chỉ chọn công ty CÓ trong hồ sơ
đúng khách; tiền không đổi; gửi lại lệnh thu không làm sống lại bản chụp đã bỏ.
"""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from openpyxl import load_workbook

from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.payment import PaymentRecordRequest, _gan_cong_ty
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import ValidationError
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.hoa_don_cong_ty_service import (
    HoaDonCongTyService,
    doc_cong_ty_cho_phieu,
)
from clinicai.services.quay_thu_service import ma_phieu
from clinicai.services.xuat_hoa_don_service import (
    DONG_DAU,
    XuatHoaDonService,
    xlsx_misa,
)
from tests.services.test_quyen_lego_man_db import _nguoi as nguoi_theo_lego
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GOI_KE_TOAN = ["bao_cao", "ke_toan", "ds_benh_nhan", "lich_lam_viec"]
CT = {
    "ten_cong_ty": "Công ty TNHH Hoa Sen",
    "dia_chi_cong_ty": "99 Trần Duy Hưng, Hà Nội",
    "ma_so_thue": "0123456789",
    "email_nhan_hd": "ketoan@hoasen.vn",
}


async def _khach_va_cong_ty(
    pool: asyncpg.Pool, q: Any, manager: StaffIdentity, **ct: Any
) -> tuple[str, str]:
    pid = str(
        await pool.fetchval(
            "UPDATE patient p SET address='12 Kim Ngưu', email='ca-nhan@example.com'"
            " FROM visit v WHERE v.visit_id=$1::uuid"
            " AND p.clinic_patient_id=v.clinic_patient_id"
            " RETURNING p.clinic_patient_id::text",
            q.visit_id,
        )
    )
    kq = await HoaDonCongTyService(pool).luu_cong_ty_khach(
        identity=manager, clinic_patient_id=pid, **{**CT, **ct}
    )
    return pid, str(kq["id"])


async def _hd(pool: asyncpg.Pool, manager: StaffIdentity, cycle: str) -> dict[str, Any]:
    ngay = now_vn().date().isoformat()
    data = await XuatHoaDonService(pool).xem(identity=manager, tu=ngay, den=ngay)
    theo_ma: dict[str, dict[str, Any]] = {h["ma_phieu"]: h for h in data["hoa_don"]}
    return theo_ma[ma_phieu(cycle)]


def _cot(hd: dict[str, Any]) -> list[Any]:
    ws: Any = load_workbook(io.BytesIO(xlsx_misa([hd]))).active
    return [ws.cell(DONG_DAU, c).value for c in range(1, 18)]


async def test_tick_theo_luot_khong_theo_ho_so(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    manager = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    pid, ct_id = await _khach_va_cong_ty(pool, q, manager)
    svc = HoaDonCongTyService(pool)

    # Lượt thu 1: tick → xuất về công ty. Thu ngân (không phải Kế toán) làm được.
    c1 = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    tien = int(
        await pool.fetchval(
            "SELECT amount FROM payment_cycle WHERE payment_cycle_id=$1::uuid", c1
        )
    )
    kq = await svc.gan_khi_thu(
        identity=q.thu_ngan, payment_cycle_id=c1, khach_cong_ty_id=ct_id
    )
    assert kq == {"ok": True, "payment_cycle_id": c1, "doi": True}
    hd = await _hd(pool, manager, c1)
    cot = _cot(hd)
    ten_khach = hd["ten_khach"]
    # C tên cty · D địa chỉ cty · E MST · F KHÁCH THẬT · G email cty · H/I trống.
    assert cot[2:9] == [
        CT["ten_cong_ty"],
        CT["dia_chi_cong_ty"],
        CT["ma_so_thue"],
        ten_khach,
        CT["email_nhan_hd"],
        None,
        None,
    ]
    assert hd["tong"] == tien  # tiền không đổi
    assert "ca-nhan@example.com" not in repr(cot) and "Kim Ngưu" not in repr(cot)

    # Lượt thu 2 CỦA CÙNG KHÁCH (hồ sơ vẫn có công ty) — không tick → cá nhân.
    c2 = str(uuid4())
    await pool.execute(
        "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,amount,"
        "status,legacy,paid_at,created_at,created_by,confirmed_by,method)"
        " VALUES($1::uuid,$2::uuid,$3::uuid,'dich_vu',50000,'PAID',true,now(),now(),"
        "$4::uuid,$4::uuid,'CASH')",
        c2,
        manager.clinic_id,
        q.visit_id,
        manager.staff_id,
    )
    await pool.execute(
        "INSERT INTO payment_bill_line(clinic_id,payment_cycle_id,visit_id,kind,"
        "source_type,source_id,name_snapshot,quantity,unit,unit_price,line_total,"
        "billing_owner) VALUES($1::uuid,$2::uuid,$3::uuid,'dich_vu','exam',$4,'Khám',"
        "1,NULL,50000,50000,'CLINIC')",
        manager.clinic_id,
        c2,
        q.visit_id,
        f"x-{uuid4().hex[:6]}",
    )
    hd2 = await _hd(pool, manager, c2)
    cot2 = _cot(hd2)
    assert hd2["la_hd_cong_ty"] is False
    assert cot2[2] is None and cot2[5] == ten_khach  # C trống, F khách thật
    assert cot2[3] == "12 Kim Ngưu" and cot2[6] == "ca-nhan@example.com"
    async with pool.acquire() as conn:
        assert await doc_cong_ty_cho_phieu(conn, manager.clinic_id, [c2]) == {}

    # Sửa công ty trong hồ sơ KHÔNG đổi bản chụp lượt 1.
    await svc.luu_cong_ty_khach(
        identity=manager,
        clinic_patient_id=pid,
        id_=ct_id,
        **{**CT, "ten_cong_ty": "Tên mới"},
    )
    assert _cot(await _hd(pool, manager, c1))[2] == CT["ten_cong_ty"]


async def test_chon_sai_cong_ty_bi_tu_choi_va_gui_lai_khong_song_lai(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    q2 = await tao_quay(pool)  # khách khác
    manager = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    _, ct_id = await _khach_va_cong_ty(pool, q, manager)
    _, ct_khac = await _khach_va_cong_ty(pool, q2, manager, ten_cong_ty="Cty khác")
    svc = HoaDonCongTyService(pool)
    c1 = (await _thu_pt(q, "CASH"))["payment_cycle_id"]

    # Công ty của KHÁCH KHÁC / id rác / công ty đã ẩn → từ chối, không ghi nửa chừng.
    for xau in (ct_khac, "rác", str(uuid4())):
        with pytest.raises(ValidationError):
            await svc.gan_khi_thu(
                identity=q.thu_ngan, payment_cycle_id=c1, khach_cong_ty_id=xau
            )
    assert not await pool.fetchval(
        "SELECT 1 FROM hoa_don_cong_ty WHERE payment_cycle_id=$1::uuid", c1
    )

    # Tick rồi Kế toán BỎ chọn; gửi lại cùng lệnh thu (replay) KHÔNG làm sống lại.
    await svc.gan_khi_thu(
        identity=q.thu_ngan, payment_cycle_id=c1, khach_cong_ty_id=ct_id
    )
    await svc.bo_hoa_don(identity=manager, payment_cycle_id=c1)
    lai = await svc.gan_khi_thu(
        identity=q.thu_ngan, payment_cycle_id=c1, khach_cong_ty_id=ct_id
    )
    assert lai["doi"] is False
    assert (await _hd(pool, manager, c1))["la_hd_cong_ty"] is False

    # Công ty bị ẩn khỏi hồ sơ thì không chọn được nữa.
    await svc.an_cong_ty_khach(identity=manager, id_=ct_id, an=True)
    with pytest.raises(ValidationError):
        await svc.gan_khi_thu(
            identity=q.thu_ngan, payment_cycle_id=c1, khach_cong_ty_id=ct_id
        )


async def test_router_gan_cong_ty_tra_cau_bao_khi_loi_khong_nem(
    pool: asyncpg.Pool,
) -> None:
    """Tiền ĐÃ ghi → công ty gắn lỗi chỉ trả `cong_ty_loi`, lệnh thu không thất bại."""
    q = await tao_quay(pool)
    manager = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    _, ct_id = await _khach_va_cong_ty(pool, q, manager)
    c1 = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    body = PaymentRecordRequest(
        visit_id=UUID(q.visit_id), kind="dich_vu", cong_ty_id=UUID(ct_id)
    )
    ok = await _gan_cong_ty(pool, q.thu_ngan, body, {"payment_cycle_id": c1})
    assert ok == {"cong_ty": {"gan": True}}
    sai = PaymentRecordRequest(
        visit_id=UUID(q.visit_id), kind="dich_vu", cong_ty_id=uuid4()
    )
    kq = await _gan_cong_ty(pool, q.thu_ngan, sai, {"payment_cycle_id": c1})
    assert "cong_ty_loi" in kq
    # Không tick / lệnh 0đ (không có phiếu) → không làm gì.
    khong = PaymentRecordRequest(visit_id=UUID(q.visit_id), kind="dich_vu")
    assert await _gan_cong_ty(pool, q.thu_ngan, khong, {"payment_cycle_id": c1}) == {}
    assert await _gan_cong_ty(pool, q.thu_ngan, body, {"payment_cycle_id": None}) == {}


async def test_bang_quay_thu_hien_cong_ty_cua_khach(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    manager = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    pid, _ = await _khach_va_cong_ty(pool, q, manager)
    ban = await CashierBoardService(pool).board(identity=q.thu_ngan, modes=["dich_vu"])
    item = next(i for i in ban["items"] if i["visit_id"] == q.visit_id)
    assert [c["ten_cong_ty"] for c in item["cong_ty"]] == [CT["ten_cong_ty"]]
    assert item["clinic_patient_id"] == pid
