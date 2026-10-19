"""Quy đổi đơn vị LÚC NHẬP kho (17/10/2026, việc A của KE-HOACH-QUY-DOI-DON-VI).

Ca đã bấm thật: Androgel nhập 6 hộp, bán theo gói → giao thuốc ghi tiền mà kho không
trừ. Giờ kho chỉ giữ MỘT đơn vị = đơn vị bán: nhập "hộp" thì đổi ngay ở cửa nhập.

Số mong đợi viết tay từ phép tính trên giấy (6 hộp × 10 = 60; 450.000đ ÷ 10 =
45.000đ), không tính lại bằng chính hàm đang thử.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_quay_db import Co, _don, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _thuoc_ban_vien(co: Co) -> str:
    """Thuốc bán theo VIÊN (đơn vị bán rõ ràng, không phụ thuộc dữ liệu mẫu)."""
    _rx, drug = await _don(co, 3)
    await co.q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = 'viên' WHERE id = $1::uuid", drug
    )
    return drug


async def _thuoc_ban_vien_khac(co: Co) -> str:
    """Thuốc thứ hai cùng phòng khám (tên khác) cho phiếu nhiều dòng."""
    ten = f"Thuốc quy đổi {uuid.uuid4().hex[:8]}"
    return str(
        await co.q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, unit_price,"
            " don_vi_ban, is_active, needs_review)"
            " SELECT clinic_id, $1, $1, 1000, 'viên', true, false"
            " FROM drug_catalog LIMIT 1 RETURNING id",
            ten,
        )
    )


def _ma() -> str:
    return f"QD-{uuid.uuid4().hex[:8]}"


async def _nhap(co: Co, drug: str, so: Any, unit: str, **kw: Any) -> dict[str, Any]:
    return await PharmacyService(co.q.pool).nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=kw.pop("batch_code", _ma()),
        expiry_date=hom_nay_vn() + timedelta(days=900),
        unit=unit,
        **kw,
    )


async def _lo(co: Co, lo_id: str) -> Any:
    return await co.q.pool.fetchrow(
        "SELECT unit, quantity_on_hand, cost_price FROM drug_batch WHERE id=$1::uuid",
        lo_id,
    )


async def _so_lo_cua_thuoc(co: Co, drug: str) -> int:
    return int(
        await co.q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE drug_catalog_id = $1::uuid", drug
        )
    )


async def test_nhap_6_hop_he_so_10_thanh_60_vien_gia_von_45000(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    kq = await _nhap(co, drug, 6, "hộp", cost_price=450000, he_so="10")
    lo = await _lo(co, kq["drug_batch_id"])
    assert (lo["unit"], lo["quantity_on_hand"], lo["cost_price"]) == (
        "viên",
        D(60),
        D(45000),
    )
    assert kq["quy_doi"]["so_luong"] == "60.000"
    # Sổ kho phải giải thích được con số: một dòng RECEIVE +60 và lý do nói rõ.
    txn = await co.q.pool.fetchrow(
        "SELECT quantity, reason FROM inventory_txn WHERE drug_batch_id = $1::uuid",
        kq["drug_batch_id"],
    )
    assert txn["quantity"] == D(60)
    assert "6 hộp × 10 = 60 viên" in txn["reason"]


async def test_he_so_duoc_nho_lan_sau_khong_phai_go_lai(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    await _nhap(co, drug, 6, "hộp", cost_price=450000, he_so="10")
    kq = await _nhap(co, drug, 2, "Hộp ", cost_price=500000)  # khác cách viết
    assert (await _lo(co, kq["drug_batch_id"]))["quantity_on_hand"] == D(20)
    assert (await _lo(co, kq["drug_batch_id"]))["cost_price"] == D(50000)
    nho = await co.q.pool.fetch(
        "SELECT don_vi, he_so FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
    )
    assert [(r["don_vi"], r["he_so"]) for r in nho] == [("hộp", D(10))]


async def test_lan_dau_thieu_he_so_thi_hoi_va_khong_tao_lo(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    with pytest.raises(ValidationError, match=r"1 hộp = \? viên"):
        await _nhap(co, drug, 6, "hộp", cost_price=450000)
    assert await _so_lo_cua_thuoc(co, drug) == 0


@pytest.mark.parametrize(
    "rac", ["0", "-3", "abc", "", "nan", "inf", "1e12", "10001", "0.0001", [], {}]
)
async def test_he_so_rac_thanh_cau_tieng_viet_khong_500(co: Co, rac: Any) -> None:
    drug = await _thuoc_ban_vien(co)
    with pytest.raises(ValidationError):
        await _nhap(co, drug, 6, "hộp", he_so=rac)
    assert await _so_lo_cua_thuoc(co, drug) == 0
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
        )
        == 0
    )


async def test_he_so_lech_hon_10_lan_phai_xac_nhan(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    await _nhap(co, drug, 1, "hộp", he_so="10")
    with pytest.raises(ValidationError, match="Đúng, hệ số này"):
        await _nhap(co, drug, 1, "hộp", he_so="500")
    assert await _so_lo_cua_thuoc(co, drug) == 1
    ok = await _nhap(co, drug, 1, "hộp", he_so="500", xac_nhan_he_so=True)
    assert (await _lo(co, ok["drug_batch_id"]))["quantity_on_hand"] == D(500)


async def test_he_so_lech_vua_phai_khong_hoi_va_cap_nhat_nho(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    await _nhap(co, drug, 1, "hộp", he_so="10")
    kq = await _nhap(co, drug, 1, "hộp", he_so="12")  # 1,2 lần < ngưỡng 10 lần
    assert (await _lo(co, kq["drug_batch_id"]))["quantity_on_hand"] == D(12)
    assert (
        await co.q.pool.fetchval(
            "SELECT he_so FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
        )
        == 12
    )


async def test_nhap_dung_don_vi_ban_thi_nguyen_trang(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    kq = await _nhap(co, drug, 7, "Viên", cost_price=1000, he_so="999")
    lo = await _lo(co, kq["drug_batch_id"])
    assert (lo["quantity_on_hand"], lo["cost_price"]) == (D(7), D(1000))
    # Gõ "Viên" → lô lưu đúng chữ của danh mục ("viên"), không để hai cách viết.
    assert lo["unit"] == "viên"
    assert "quy_doi" not in kq
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
        )
        == 0
    )


async def test_gia_von_lam_tron_dong(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    kq = await _nhap(co, drug, 1, "hộp", cost_price=100000, he_so="3")
    assert (await _lo(co, kq["drug_batch_id"]))["cost_price"] == D(33333)  # 33333,33


async def test_so_luong_sau_khi_doi_qua_lon_bi_chan(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    with pytest.raises(ValidationError):
        await _nhap(co, drug, 999_999, "hộp", he_so="9999")
    assert await _so_lo_cua_thuoc(co, drug) == 0


async def test_cong_them_vao_lo_dang_tinh_don_vi_khac_bi_chan(co: Co) -> None:
    """Lô CŨ đang tính 'hộp' (như lô mẫu trên prod): nhập '60 viên' vào đó sẽ trộn
    hai đơn vị vào một số dư — phải bị chặn."""
    drug = await _thuoc_ban_vien(co)
    ma = _ma()
    await _nhap(co, drug, 5, "viên", batch_code=ma)
    await co.q.pool.execute(
        "UPDATE drug_batch SET unit = 'hộp' WHERE batch_code = $1", ma
    )
    with pytest.raises(ConflictError, match="nhập cùng đơn vị"):
        await _nhap(co, drug, 6, "hộp", batch_code=ma, he_so="10")
    assert (
        await co.q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE batch_code = $1", ma
        )
        == 5
    )


async def test_giao_thuoc_sau_khi_quy_doi_tru_kho_dung(co: Co) -> None:
    """Gốc của lỗi: tiền vào mà kho không trừ. Nhập hộp (đổi ra viên) → giao 3 viên
    → kho phải còn 57 và đơn không còn nằm ở 'đã giao, chưa trừ kho'."""
    rx, drug = await _don(co, 3)
    await co.q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = 'viên' WHERE id = $1::uuid", drug
    )
    await _thu(co.q)
    kq = await _nhap(co, drug, 6, "hộp", cost_price=450000, he_so="10")
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(
        identity=co.ds,
        prescription_id=rx,
        drug_batch_id=kq["drug_batch_id"],
        so_luong=3,
    )
    assert (await _lo(co, kq["drug_batch_id"]))["quantity_on_hand"] == D(57)


async def test_phieu_nhap_nhieu_dong_luu_so_goc(co: Co) -> None:
    a = await _thuoc_ban_vien(co)
    b = await _thuoc_ban_vien_khac(co)
    ma_a, ma_b = _ma(), _ma()
    han = (hom_nay_vn() + timedelta(days=900)).isoformat()
    kq = await kho_thuoc_service.tao_phieu_nhap(
        co.q.pool,
        identity=co.ds,
        khoa_gui=uuid.uuid4().hex,
        dong=[
            {
                "drug_catalog_id": a,
                "batch_code": ma_a,
                "expiry_date": han,
                "so_luong": 6,
                "unit": "hộp",
                "gia_nhap": 450000,
                "he_so": "10",
            },
            {
                "drug_catalog_id": b,
                "batch_code": ma_b,
                "expiry_date": han,
                "so_luong": 5,
                "unit": "viên",
                "gia_nhap": 1000,
            },
        ],
    )
    dong = await co.q.pool.fetch(
        "SELECT stt, so_luong, gia_nhap, so_luong_goc, don_vi_goc, he_so"
        " FROM phieu_kho_dong WHERE phieu_kho_id = $1::uuid ORDER BY stt",
        kq["id"],
    )
    assert [
        (r["so_luong"], r["gia_nhap"], r["so_luong_goc"], r["don_vi_goc"], r["he_so"])
        for r in dong
    ] == [(D(60), D(45000), D(6), "hộp", D(10)), (D(5), D(1000), None, None, None)]
    assert (
        await co.q.pool.fetchval(
            "SELECT quantity_on_hand FROM drug_batch WHERE batch_code = $1", ma_a
        )
        == 60
    )


async def test_phieu_nhap_mot_dong_thieu_he_so_thi_ca_phieu_khong_vao(co: Co) -> None:
    a = await _thuoc_ban_vien(co)
    b = await _thuoc_ban_vien_khac(co)
    ma_a, ma_b = _ma(), _ma()
    han = (hom_nay_vn() + timedelta(days=900)).isoformat()
    khoa = uuid.uuid4().hex
    with pytest.raises(ValidationError, match=r"Dòng 2: .*1 hộp = \? viên"):
        await kho_thuoc_service.tao_phieu_nhap(
            co.q.pool,
            identity=co.ds,
            khoa_gui=khoa,
            dong=[
                {
                    "drug_catalog_id": a,
                    "batch_code": ma_a,
                    "expiry_date": han,
                    "so_luong": 5,
                    "unit": "viên",
                },
                {
                    "drug_catalog_id": b,
                    "batch_code": ma_b,
                    "expiry_date": han,
                    "so_luong": 6,
                    "unit": "hộp",
                },
            ],
        )
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE batch_code = ANY($1::text[])",
            [ma_a, ma_b],
        )
        == 0
    ), "một dòng hỏng thì cả phiếu không vào"
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM phieu_kho WHERE khoa_gui = $1", khoa
        )
        == 0
    )


async def test_xem_truoc_noi_ro_dong_nhap(co: Co) -> None:
    drug = await _thuoc_ban_vien(co)
    pool = co.q.pool
    chua = await kho_thuoc_service.xem_truoc_quy_doi(
        pool, identity=co.ds, drug_catalog_id=drug, unit="hộp", so_luong="6"
    )
    assert (chua["can_doi"], chua["he_so"], chua["so_luong_quy_doi"]) == (
        True,
        None,
        None,
    )
    go = await kho_thuoc_service.xem_truoc_quy_doi(
        pool, identity=co.ds, drug_catalog_id=drug, unit="hộp", he_so="10", so_luong="6"
    )
    assert go["so_luong_quy_doi"] == D(60) and go["can_xac_nhan"] is False
    # Xem trước KHÔNG được nhớ hệ số.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
        )
        == 0
    )
    cung = await kho_thuoc_service.xem_truoc_quy_doi(
        pool, identity=co.ds, drug_catalog_id=drug, unit="viên", so_luong="abc"
    )
    assert cung["can_doi"] is False
    rac = await kho_thuoc_service.xem_truoc_quy_doi(
        pool, identity=co.ds, drug_catalog_id=drug, unit="hộp", he_so="10", so_luong="x"
    )
    assert rac["so_luong_quy_doi"] is None  # số lượng rác → trả rỗng, không ném
