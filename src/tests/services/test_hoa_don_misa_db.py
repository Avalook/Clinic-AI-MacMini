"""Đánh dấu "đã xuất MISA" + "có thay đổi sau khi xuất" (G5c) trên Postgres thật."""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import (
    ResourceNotFoundError,
    SafetyGateError,
    ValidationError,
)
from clinicai.services.hoa_don_cong_ty_service import HoaDonCongTyService
from clinicai.services.hoa_don_misa_doc import (
    LY_DO_NGUOI_MUA,
    LY_DO_NOI_DUNG,
)
from clinicai.services.hoa_don_misa_service import HoaDonMisaService
from clinicai.services.quay_thu_service import ma_phieu
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService
from tests.services.test_hoa_don_cong_ty_db import CT_A, _khach, _phieu
from tests.services.test_quyen_lego_man_db import _nguoi as nguoi_theo_lego
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GOI_KE_TOAN = ["bao_cao", "ke_toan", "ds_benh_nhan", "lich_lam_viec"]
HOM_NAY = now_vn().date().isoformat()


async def _hoan(pool: asyncpg.Pool, q: Any, manager: StaffIdentity, cycle: str) -> None:
    """Hoàn ĐÃ XONG 0,1 lần của dòng đầu phiếu (dòng hoá đơn bất biến — sau khi
    thu, thứ làm hoá đơn đổi là hoàn tiền / huỷ, không phải sửa dòng)."""
    async with pool.acquire() as conn, conn.transaction():
        dong, gia = await conn.fetchrow(
            "SELECT id, unit_price FROM payment_bill_line"
            " WHERE payment_cycle_id=$1::uuid ORDER BY id LIMIT 1",
            cycle,
        )
        so_tien = int(gia) // 10
        hoan = await conn.fetchval(
            "INSERT INTO payment_refund(clinic_id,visit_id,kind,payment_cycle_id,"
            "amount,status,method,reason,created_by,created_at)"
            " VALUES($1::uuid,$2::uuid,'dich_vu',$3::uuid,$4,'PENDING','CASH',"
            "'khách trả lại',$5::uuid,now()) RETURNING refund_id",
            manager.clinic_id,
            q.visit_id,
            cycle,
            so_tien,
            manager.staff_id,
        )
        await conn.execute(
            "INSERT INTO payment_refund_line(clinic_id,refund_id,payment_bill_line_id,"
            "payment_cycle_id,quantity,amount) VALUES($1::uuid,$2,$3,$4::uuid,0.1,$5)",
            manager.clinic_id,
            hoan,
            dong,
            cycle,
            so_tien,
        )
        await conn.execute(
            "UPDATE payment_refund SET status='COMPLETED',completed_at=now(),"
            "completed_by=$2::uuid WHERE refund_id=$1",
            hoan,
            manager.staff_id,
        )


async def _man_hinh(
    pool: asyncpg.Pool, who: StaffIdentity, cycles: list[str], **tham_so: Any
) -> dict[str, dict[str, Any]]:
    """Màn xuất như người dùng thấy: xem + gắn trạng thái MISA, theo phiếu."""
    data = await XuatHoaDonService(pool).xem(
        identity=who, tu=HOM_NAY, den=HOM_NAY, kem_dau_van_tay=True, **tham_so
    )
    data = await HoaDonMisaService(pool).gan_trang_thai(identity=who, data=data)
    assert "dau_van_tay" not in data  # không lộ ra trình duyệt
    theo_ma = {h["ma_phieu"]: h for h in data["hoa_don"]}
    return {c: theo_ma[ma_phieu(c)] for c in cycles}


async def test_danh_dau_xem_trang_thai_va_phat_hien_thay_doi(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    kt = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)  # kế toán = gói lego
    await _khach(pool, q)
    c1, c2, c3 = [await _phieu(pool, q, manager) for _ in range(3)]
    ct = HoaDonCongTyService(pool)
    misa = HoaDonMisaService(pool)
    await ct.ghi_hoa_don(identity=manager, payment_cycle_id=c1, **CT_A)

    truoc = await _man_hinh(pool, kt, [c1, c2, c3])
    assert all(h["misa"] is None for h in truoc.values())

    lan = await misa.danh_dau(identity=kt, tu=HOM_NAY, den=HOM_NAY, ghi_chu="Đợt 1")
    assert lan["so_hoa_don"] >= 3
    sau = await _man_hinh(pool, kt, [c1, c2, c3])
    for h in sau.values():
        assert h["misa"]["xuat_id"] == lan["id"] and not h["misa"]["co_thay_doi"]
        assert h["misa"]["xuat_boi"]

    # Sau khi xuất: c1 đổi công ty, c2 đổi dòng tiền, c3 giữ nguyên.
    await ct.ghi_hoa_don(
        identity=manager,
        payment_cycle_id=c1,
        **{**CT_A, "ma_so_thue": "9876543210"},
    )
    await _hoan(pool, q, manager, c2)
    sau = await _man_hinh(pool, kt, [c1, c2, c3])
    assert sau[c1]["misa"]["ly_do"] == [LY_DO_NGUOI_MUA]
    assert sau[c2]["misa"]["ly_do"] == [LY_DO_NOI_DUNG]
    assert sau[c3]["misa"]["co_thay_doi"] is False
    ct_tiet = await misa.doc_chi_tiet(identity=kt, xuat_id=lan["id"])
    doi = {
        h["payment_cycle_id"]: h["ly_do"]
        for h in ct_tiet["hoa_don"]
        if h["co_thay_doi"]
    }
    assert doi[c1] == [LY_DO_NGUOI_MUA] and doi[c2] == [LY_DO_NOI_DUNG]
    assert c3 not in doi
    assert ct_tiet["so_co_thay_doi"] == len(doi)

    # Thuế không phải "thay đổi sau khi xuất": gõ thuế suất tay ở màn xuất.
    dong_c3 = await pool.fetch(
        "SELECT id::text id FROM payment_bill_line WHERE payment_cycle_id=$1::uuid",
        c3,
    )
    ghi_de = {r["id"]: "8" for r in dong_c3}
    gia = await _man_hinh(pool, kt, [c3], ghi_de=ghi_de)
    assert gia[c3]["misa"]["co_thay_doi"] is False


async def test_bo_danh_dau_hoan_tac_va_lan_xuat_moi_nhat_thang(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    kt = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)  # kế toán = gói lego
    await _khach(pool, q)
    c = await _phieu(pool, q, manager)
    misa = HoaDonMisaService(pool)
    l1 = await misa.danh_dau(identity=kt, tu=HOM_NAY, den=HOM_NAY)
    l2 = await misa.danh_dau(identity=kt, tu=HOM_NAY, den=HOM_NAY)
    assert (await _man_hinh(pool, kt, [c]))[c]["misa"]["xuat_id"] == l2["id"]
    # Bỏ lần mới → hoá đơn trở về lần cũ (không mất dấu).
    await misa.huy_danh_dau(identity=kt, xuat_id=l2["id"])
    await misa.huy_danh_dau(identity=kt, xuat_id=l2["id"])  # lần hai: im lặng
    assert (await _man_hinh(pool, kt, [c]))[c]["misa"]["xuat_id"] == l1["id"]
    await misa.huy_danh_dau(identity=kt, xuat_id=l1["id"])
    assert (await _man_hinh(pool, kt, [c]))[c]["misa"] is None
    # Hoàn tác = khôi phục đúng lần đó.
    await misa.khoi_phuc(identity=kt, xuat_id=l1["id"])
    assert (await _man_hinh(pool, kt, [c]))[c]["misa"]["xuat_id"] == l1["id"]
    ds = {x["id"]: x for x in await misa.doc_danh_sach(identity=kt)}
    assert ds[l1["id"]]["huy_luc"] is None and ds[l2["id"]]["huy_luc"] is not None


async def test_rac_va_quyen(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    kt = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)  # kế toán = gói lego
    await _khach(pool, q)
    await _phieu(pool, q, manager)
    misa = HoaDonMisaService(pool)
    for tu, den in (("rác", HOM_NAY), (HOM_NAY, "31/02/2026"), (None, None), ("", "")):
        with pytest.raises(ValidationError):
            await misa.danh_dau(identity=kt, tu=tu, den=den)
    with pytest.raises(ValidationError):
        await misa.danh_dau(identity=kt, tu="2026-10-14", den="2026-10-01")
    with pytest.raises(ValidationError):
        await misa.danh_dau(identity=kt, tu=HOM_NAY, den=HOM_NAY, ghi_chu="x" * 501)
    with pytest.raises(ValidationError):  # khoảng không có hoá đơn
        await misa.danh_dau(identity=kt, tu="2001-01-01", den="2001-01-02")
    for sai in ("rác", "", str(uuid4())):
        with pytest.raises((ValidationError, ResourceNotFoundError)):
            await misa.doc_chi_tiet(identity=kt, xuat_id=sai)
    with pytest.raises(ValidationError):
        await misa.huy_danh_dau(identity=kt, xuat_id="rác")
    with pytest.raises(ResourceNotFoundError):
        await misa.huy_danh_dau(identity=kt, xuat_id=str(uuid4()))

    # Quyền = lego: gói báo cáo không có quyền kế toán bị chặn mọi lệnh ghi / danh sách.
    khong = await nguoi_theo_lego(pool, "CSKH", ["bao_cao", "ds_benh_nhan"])
    for goi in (
        misa.danh_dau(identity=khong, tu=HOM_NAY, den=HOM_NAY),
        misa.huy_danh_dau(identity=khong, xuat_id=str(uuid4())),
        misa.khoi_phuc(identity=khong, xuat_id=str(uuid4())),
        misa.doc_danh_sach(identity=khong),
        misa.doc_chi_tiet(identity=khong, xuat_id=str(uuid4())),
    ):
        with pytest.raises(SafetyGateError):
            await goi
    ke_toan = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)
    lan = await misa.danh_dau(identity=ke_toan, tu=HOM_NAY, den=HOM_NAY)
    assert lan["so_hoa_don"] >= 1


async def test_bam_ngau_nhien_20_chuoi_x_10_buoc_khop_mo_hinh(
    pool: asyncpg.Pool,
) -> None:
    """Mỗi lần xuất nhớ trạng thái (công ty, tổng) của 3 phiếu lúc xuất. Sau MỖI
    bước màn xuất phải nói đúng: lần xuất mới nhất chưa bỏ, và có đổi hay không."""
    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    kt = await nguoi_theo_lego(pool, "CSKH", GOI_KE_TOAN)  # kế toán = gói lego
    await _khach(pool, q)
    ct, misa = HoaDonCongTyService(pool), HoaDonMisaService(pool)
    rng = random.Random(14_10_2026)
    for _ in range(20):
        cycles = [await _phieu(pool, q, manager, 100_000) for _ in range(3)]
        hien: dict[str, tuple[Any, int]] = {
            c: (None, 0) for c in cycles
        }  # (công ty, số lần hoàn)
        lan_xuat: list[dict[str, Any]] = []  # {id, huy, trang_thai}
        for _ in range(10):
            op = rng.choice(["xuat", "huy", "khoi_phuc", "cong_ty", "tien", "tien"])
            c = rng.choice(cycles)
            if op == "xuat":
                r = await misa.danh_dau(identity=kt, tu=HOM_NAY, den=HOM_NAY)
                lan_xuat.append({"id": r["id"], "huy": False, "tt": dict(hien)})
            elif op == "huy" and lan_xuat:
                x = rng.choice(lan_xuat)
                await misa.huy_danh_dau(identity=kt, xuat_id=x["id"])
                x["huy"] = True
            elif op == "khoi_phuc" and lan_xuat:
                x = rng.choice(lan_xuat)
                await misa.khoi_phuc(identity=kt, xuat_id=x["id"])
                x["huy"] = False
            elif op == "cong_ty":
                moi = {**CT_A, "ten_cong_ty": rng.choice(["Alpha", "Beta", "Gamma"])}
                await ct.ghi_hoa_don(identity=manager, payment_cycle_id=c, **moi)
                hien[c] = (moi["ten_cong_ty"], hien[c][1])
            elif op == "tien" and hien[c][1] < 5:
                await _hoan(pool, q, manager, c)
                hien[c] = (hien[c][0], hien[c][1] + 1)
            man = await _man_hinh(pool, kt, cycles)
            dang_hieu_luc = [x for x in lan_xuat if not x["huy"]]
            for cy in cycles:
                misa_cy = man[cy]["misa"]
                if not dang_hieu_luc:
                    assert misa_cy is None
                    continue
                moi_nhat = dang_hieu_luc[-1]
                assert misa_cy is not None and misa_cy["xuat_id"] == moi_nhat["id"]
                da_xuat = moi_nhat["tt"][cy]
                assert misa_cy["co_thay_doi"] is (da_xuat != hien[cy]), (
                    da_xuat,
                    hien[cy],
                )
