"""Test hoá đơn công ty + MISA (G5c) — DB thật."""

from dataclasses import replace
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.hoa_don_cong_ty_service import HoaDonCongTyService, kiem_mst
from clinicai.services.xuat_hoa_don_service import dung_hoa_don

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── Kiểm MST (hàm thuần) ────────────────────────────────────────────────────


async def test_mst_hop_le() -> None:
    assert kiem_mst("0123456789")  # 10 số
    assert kiem_mst("0123456789-001")  # 10 số + '-' + 3 số


async def test_mst_sai_chi_nhac_khong_chan() -> None:
    """MST sai → kiem_mst trả False nhưng không ném — chỉ nhắc."""
    assert not kiem_mst("012345")  # thiếu số
    assert not kiem_mst("abc")
    assert not kiem_mst("01234567890")  # 11 số
    assert not kiem_mst("0123456789-01")  # '-' + 2 số


async def test_mst_rong_ok() -> None:
    """MST rỗng = chưa điền → hợp lệ."""
    assert kiem_mst("")
    assert kiem_mst("   ")


# ── Snapshot không đổi khi sửa công ty ─────────────────────────────────────


async def test_snapshot_khong_doi_khi_sua_cong_ty(pool: asyncpg.Pool) -> None:
    """Sửa thông tin công ty sau khi ghi snapshot → snapshot cũ không đổi."""
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = HoaDonCongTyService(pool)

    # Tạo payment_cycle giả
    cycle_id = str(uuid4())
    await pool.execute(
        "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,"
        "amount,status,legacy,paid_at,closed_at,created_at,created_by,"
        "confirmed_by,method) VALUES($1,$2,$3,'dich_vu',100000,'PAID',"
        "true,now(),now(),now(),$4,$4,'CASH')",
        cycle_id,
        manager.clinic_id,
        q.visit_id,
        manager.staff_id,
    )

    # Ghi snapshot lần 1
    await svc.ghi_hoa_don_cong_ty(
        identity=manager,
        payment_cycle_id=cycle_id,
        ten_cong_ty="Công ty A",
        dia_chi_cong_ty="123 Nguyễn Trãi",
        ma_so_thue="0123456789",
        email_nhan_hd="a@company.vn",
    )

    snap1 = await svc.doc_hoa_don_cong_ty(identity=manager, payment_cycle_id=cycle_id)
    assert snap1 is not None
    assert snap1["ten_cong_ty"] == "Công ty A"

    # Cập nhật tên công ty (ghi lại snapshot mới)
    await svc.ghi_hoa_don_cong_ty(
        identity=manager,
        payment_cycle_id=cycle_id,
        ten_cong_ty="Công ty B (đổi tên)",
        dia_chi_cong_ty="456 Lê Lợi",
        ma_so_thue="0123456789",
        email_nhan_hd="b@company.vn",
    )

    snap2 = await svc.doc_hoa_don_cong_ty(identity=manager, payment_cycle_id=cycle_id)
    assert snap2 is not None
    assert snap2["ten_cong_ty"] == "Công ty B (đổi tên)"

    # Lịch sử phải ghi lại tên cũ
    lich_su = await svc.doc_lich_su(identity=manager, hoa_don_cong_ty_id=snap2["id"])
    assert len(lich_su) >= 1
    assert lich_su[0]["cu_ten"] == "Công ty A"
    assert lich_su[0]["moi_ten"] == "Công ty B (đổi tên)"


# ── Nhiều công ty / khách ────────────────────────────────────────────────────


async def test_nhieu_cong_ty_mot_khach(pool: asyncpg.Pool) -> None:
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = HoaDonCongTyService(pool)

    # Lấy clinic_patient_id từ visit
    patient_id = await pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id=$1",
        q.visit_id,
    )
    assert patient_id

    # Tạo công ty mặc định
    await svc.luu_cong_ty_khach(
        identity=manager,
        clinic_patient_id=patient_id,
        ten_cong_ty="Cty Mặc Định",
        is_mac_dinh=True,
    )
    # Tạo công ty thứ hai (không mặc định)
    await svc.luu_cong_ty_khach(
        identity=manager,
        clinic_patient_id=patient_id,
        ten_cong_ty="Cty Phụ",
        is_mac_dinh=False,
    )

    ds = await svc.doc_cong_ty_khach(identity=manager, clinic_patient_id=patient_id)
    assert len(ds) == 2
    # Cty mặc định đứng đầu
    assert ds[0]["ten_cong_ty"] == "Cty Mặc Định"
    assert ds[0]["is_mac_dinh"] is True


# ── MST sai → nhắc không chặn ───────────────────────────────────────────────


async def test_mst_sai_chi_nhac(pool: asyncpg.Pool) -> None:
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = HoaDonCongTyService(pool)

    patient_id = await pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id=$1",
        q.visit_id,
    )

    # Lưu với MST sai → không ném, có canh_bao_mst
    result = await svc.luu_cong_ty_khach(
        identity=manager,
        clinic_patient_id=patient_id,
        ten_cong_ty="Cty MST Sai",
        ma_so_thue="abc123",  # sai định dạng
    )
    assert result.get("canh_bao_mst") is not None
    assert "kiểm lại" in result["canh_bao_mst"]


# ── HĐ công ty: H/I trống (không ghi SĐT/CCCD) ─────────────────────────────


async def test_hd_cong_ty_bo_sdt_cccd() -> None:
    """dung_hoa_don: khi có công ty, so_dien_thoai và cccd = rỗng."""
    # Xây mock data tối giản
    khach = [
        {
            "id": "k1",
            "ten": "Nguyễn Văn A",
            "ma_bn": "BN001",
            "so_dien_thoai": "0901234567",
            "phieu": [
                {
                    "id": "p1",
                    "ma": "PT001",
                    "kind": "dich_vu",
                    "thu_trong_ky": True,
                    "trang_thai": "PAID",
                    "thu_luc": "2026-10-14T10:00:00+07:00",
                    "hinh_thuc": "CASH",
                    "dong": [
                        {
                            "id": "d1",
                            "ten": "Khám phụ khoa",
                            "thanh_tien": 300000,
                            "so_luong": 1.0,
                            "giam_gia": 0,
                        }
                    ],
                    "hoan": [],
                }
            ],
        }
    ]
    them_dong: dict = {"d1": {"source_type": "exam", "unit": ""}}
    them_khach: dict = {
        "p1": {"dia_chi": "123 HN", "cccd": "001234567890", "email": ""}
    }
    # Có công ty
    them_cong_ty: dict = {
        "p1": {
            "ten_cong_ty": "Cty ABC",
            "dia_chi_cong_ty": "456 HCM",
            "ma_so_thue": "0123456789",
            "email_nhan_hd": "abc@cty.vn",
        }
    }

    hoa_don = dung_hoa_don(khach, them_dong, them_khach, them_cong_ty=them_cong_ty)
    assert len(hoa_don) == 1
    hd = hoa_don[0]
    # HĐ công ty: C=tên cty, D=địa chỉ cty, E=MST
    assert hd["ten_cong_ty"] == "Cty ABC"
    assert hd["dia_chi_cong_ty"] == "456 HCM"
    assert hd["ma_so_thue"] == "0123456789"
    assert hd["la_hd_cong_ty"] is True
    # H/I trống — bỏ SĐT/CCCD
    assert hd["so_dien_thoai"] == ""
    assert hd["cccd"] == ""


async def test_hd_ca_nhan_giu_sdt_cccd() -> None:
    """dung_hoa_don: khi không có công ty, giữ SĐT/CCCD bình thường."""
    khach = [
        {
            "id": "k2",
            "ten": "Trần Thị B",
            "ma_bn": "BN002",
            "so_dien_thoai": "0912345678",
            "phieu": [
                {
                    "id": "p2",
                    "ma": "PT002",
                    "kind": "dich_vu",
                    "thu_trong_ky": True,
                    "trang_thai": "PAID",
                    "thu_luc": "2026-10-14T11:00:00+07:00",
                    "hinh_thuc": "CASH",
                    "dong": [
                        {
                            "id": "d2",
                            "ten": "Siêu âm",
                            "thanh_tien": 200000,
                            "so_luong": 1.0,
                            "giam_gia": 0,
                        }
                    ],
                    "hoan": [],
                }
            ],
        }
    ]
    them_dong: dict = {"d2": {"source_type": "service_order", "unit": ""}}
    them_khach: dict = {
        "p2": {"dia_chi": "789 HN", "cccd": "099987654321", "email": "b@gmail.com"}
    }
    hoa_don = dung_hoa_don(khach, them_dong, them_khach, them_cong_ty=None)
    assert len(hoa_don) == 1
    hd = hoa_don[0]
    assert hd["la_hd_cong_ty"] is False
    assert hd["so_dien_thoai"] == "0912345678"
    assert hd["cccd"] == "099987654321"
    assert hd["ten_cong_ty"] == ""


# ── Đánh dấu xuất MISA ──────────────────────────────────────────────────────


async def test_danh_dau_xuat_misa(pool: asyncpg.Pool) -> None:
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = HoaDonCongTyService(pool)

    mock_hd = [
        {"stt": 1, "ma_phieu": "PT001", "tong": 500000, "ten_cong_ty": "Cty X"},
        {"stt": 2, "ma_phieu": "PT002", "tong": 300000, "ten_cong_ty": ""},
    ]
    result = await svc.danh_dau_xuat_misa(
        identity=manager,
        tu_ngay="01/10/2026",
        den_ngay="14/10/2026",
        hoa_don=mock_hd,
        ghi_chu="Xuất tháng 10",
    )
    assert result["so_hoa_don"] == 2
    assert result["tong_tien"] == 800000

    # Đọc lại danh sách
    ds = await svc.doc_misa_xuat(identity=manager)
    assert any(x["so_hoa_don"] == 2 for x in ds)


async def test_danh_dau_misa_ngay_rac_bao_loi(pool: asyncpg.Pool) -> None:
    from tests.services.test_tien_thuoc_cp1_db import tao_quay

    q = await tao_quay(pool)
    manager = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = HoaDonCongTyService(pool)

    from clinicai.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Ngày không đúng"):
        await svc.danh_dau_xuat_misa(
            identity=manager,
            tu_ngay="2026-13-45",  # rác
            den_ngay="14/10/2026",
            hoa_don=[],
        )
