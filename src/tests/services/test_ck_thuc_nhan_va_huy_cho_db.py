"""G4d · R1 (Tuyền chốt C, 14/10/2026) — chuyển khoản ngoài đường chuẩn.

    scripts/test-nhanh.sh src/tests/services/test_ck_thuc_nhan_va_huy_cho_db.py

* Xác minh CK nhập số ngân hàng THẬT nhận (tuỳ chọn): khớp → như cũ; lệch →
  vẫn ghi đã thu theo hoá đơn, bật đối soát ``SO_TIEN_LECH``, giữ số thật nhận
  (bất biến ở Postgres).
* Lần chờ CK bị HUỶ (nhân viên tưởng chưa về) vẫn hiện ở danh sách hoá đơn và
  báo cáo ngày — không cộng vào tiền đã thu.
"""

from __future__ import annotations

from dataclasses import replace

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.payment_service import PaymentService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    _huy_cho,
    _lam_truoc_thu_sau,
    _lan_thu,
    _luot,
    _thu,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _xac_minh(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    so: object,
) -> dict[str, object]:
    cid = await _lan_thu(pool, visit, "PENDING_VERIFICATION")
    assert cid is not None
    return await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=cid,
        visit_id=visit,
        kind="dich_vu",
        reference=None,
        identity=ca.thu_ngan,
        so_tien_thuc_nhan=so,
    )


async def _lan(pool: asyncpg.Pool, visit: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT payment_cycle_id::text AS id, status, amount, so_tien_thuc_nhan,"
        " can_doi_soat, doi_soat_ly_do FROM payment_cycle"
        " WHERE visit_id = $1::uuid AND kind = 'dich_vu'",
        visit,
    )


async def test_xac_minh_khop_so_khong_doi_soat(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    kq = await _xac_minh(pool, ca, v, 300_000)
    assert kq["so_tien_chuyen_khoan"] == 300_000
    lan = await _lan(pool, v)
    assert (lan["status"], lan["so_tien_thuc_nhan"], lan["can_doi_soat"]) == (
        "PAID",
        300_000,
        False,
    )


async def test_xac_minh_khong_khai_so_nhu_cu(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    await _xac_minh(pool, ca, v, None)
    lan = await _lan(pool, v)
    assert (lan["status"], lan["so_tien_thuc_nhan"], lan["can_doi_soat"]) == (
        "PAID",
        None,
        False,
    )


async def test_xac_minh_lech_so_van_thu_va_bat_doi_soat(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách chuyển thiếu 50k: không chặn — ghi đã thu theo hoá đơn, cờ đối soát."""
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    kq = await _xac_minh(pool, ca, v, "250.000")
    assert kq["doi_soat_ly_do"] == ["SO_TIEN_LECH"]
    lan = await _lan(pool, v)
    assert lan["status"] == "PAID" and lan["amount"] == 300_000
    assert lan["so_tien_thuc_nhan"] == 250_000
    assert lan["can_doi_soat"] and list(lan["doi_soat_ly_do"]) == ["SO_TIEN_LECH"]
    # Bất biến ở Postgres: số thật nhận không sửa được sau khi đã thu.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE payment_cycle SET so_tien_thuc_nhan = 300000"
            " WHERE payment_cycle_id = $1::uuid",
            lan["id"],
        )


async def test_xac_minh_so_rac_bi_tu_choi_lan_cho_con_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    with pytest.raises(ValidationError):
        await _xac_minh(pool, ca, v, "ba trăm nghìn")
    assert (await _lan(pool, v))["status"] == "PENDING_VERIFICATION"


def _ql(ca: Ca) -> StaffIdentity:
    return replace(ca.thu_ngan, role=ClinicRole.MANAGEMENT)


async def test_lan_cho_ck_bi_huy_van_hien_khong_cong_tien(pool: asyncpg.Pool) -> None:  # noqa: F811
    """R1: NV huỷ lần chờ vì tưởng tiền chưa về → sổ vẫn còn dấu để đối chiếu."""
    ca = await _dung(pool)
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v, method="TRANSFER")
    await _huy_cho(pool, ca, v)
    hom_nay = now_vn().date().isoformat()
    ds = await DanhSachHoaDonService(pool).xem(
        identity=_ql(ca), tu=hom_nay, den=hom_nay, co_so=ca.loc
    )
    phieu = [p for k in ds["khach"] for p in k["phieu"] if p["visit_id"] == v]
    assert len(phieu) == 1
    p = phieu[0]
    assert p["trang_thai"] == "CK_DA_HUY"
    assert (p["so_tien"], p["da_thu"], p["thu_rong"], p["tong_truoc_giam"]) == (
        300_000,
        0,
        0,
        0,
    )
    assert "HUY_CHO_CK" in p["lech"]
    assert any(e["loai"] == "HUY_CHO_CK" for e in p["su_kien"])
    # Không cộng vào tiền của khách (DB test dùng chung cơ sở giữa các worker
    # song song → kiểm theo đúng khách của lượt, không theo tổng kỳ).
    khach = next(k for k in ds["khach"] if any(x["visit_id"] == v for x in k["phieu"]))
    assert (khach["da_thu"], khach["thu_rong"]) == (0, 0)
    assert "Có lần chờ chuyển khoản đã huỷ — đối chiếu sao kê" in khach["canh_bao"]
    # Lọc nhóm từ link báo cáo: chỉ phiếu huỷ lần chờ.
    loc = await DanhSachHoaDonService(pool).xem(
        identity=_ql(ca), tu=hom_nay, den=hom_nay, co_so=ca.loc, nhom="ck_da_huy"
    )
    trong_nhom = [p for k in loc["khach"] for p in k["phieu"]]
    assert v in {p["visit_id"] for p in trong_nhom}
    assert {p["trang_thai"] for p in trong_nhom} == {"CK_DA_HUY"}
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=_ql(ca), tu=hom_nay, den=hom_nay, co_so=ca.loc
    )
    assert bc["ck_cho_da_huy"]["so_lan"] >= 1
    assert bc["ck_cho_da_huy"]["tong"] >= 300_000
    assert bc["tai_chinh"]["dong_tien"]["ck_cho_da_huy"] == bc["ck_cho_da_huy"]
