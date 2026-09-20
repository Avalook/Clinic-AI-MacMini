"""Tiền khám phòng thủ (contract tiền–thuốc CP6 bước 3, 20/09/2026).

Một lượt đã có thì LUÔN có dòng tiền khám. Không xác định được loại khám — lượt
không lịch hẹn, hay lịch hẹn không dẫn tới loại khám nào — thì hoá đơn hiện dòng
"Tiền khám" kèm vấn đề và chặn thu; không đoán loại khám, không đoán giá, không
bỏ im lặng.

Hôm nay lược đồ ép `appointment.service_type_id NOT NULL` nên nhánh "có lịch hẹn
mà không ra loại khám" không tạo được bằng dữ liệu hợp lệ. Test dưới đây vừa
ghim lược đồ ấy, vừa ép nhánh phòng thủ bằng dữ liệu hỏng trong một giao dịch
rồi huỷ — không đổi lược đồ.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

from decimal import Decimal

import pytest

from clinicai.services import bill_service as bs
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


# ── Thuần: không cần DB ────────────────────────────────────────────────────


@pytest.mark.parametrize("ten", [None, "", "   "])
def test_co_hen_ma_khong_ra_loai_kham_van_co_dong_tien_kham(ten: str | None) -> None:
    row = {"st_id": None, "name": ten, "khong_hen": False}
    kham = bs.dong_kham(row, [{"name": "Khám phụ khoa", "unit_price": 1}])
    assert kham is not None
    assert kham["ten"] == "Tiền khám"
    assert kham["ma"] is None  # không đoán loại khám
    assert kham["gia"] == []  # không đoán giá
    assert kham["van_de"] == bs.KHAM_KHONG_RO_LOAI

    hd = bs.ghep_dich_vu("v1", kham, [])
    assert [d.ten for d in hd.dong] == ["Tiền khám"]
    assert not hd.thu_duoc
    assert any("chưa xác định loại khám" in v for v in hd.van_de)


def test_khong_hen_giu_nguyen_nhan_cu() -> None:
    kham = bs.dong_kham({"st_id": None, "name": None, "khong_hen": True}, [])
    assert kham is not None
    assert kham["van_de"] == "chưa xác định loại khám (lượt không có lịch hẹn)"


def test_co_loai_kham_thi_dong_binh_thuong() -> None:
    row = {"st_id": "st1", "name": "Khám phụ khoa", "khong_hen": False}
    gia = [
        {
            "name": "khám phụ khoa",
            "unit_price": Decimal(200000),
            "billing_owner": "CLINIC",
        }
    ]
    kham = bs.dong_kham(row, gia)
    assert kham is not None
    assert "van_de" not in kham
    assert kham["ma"] == "st1"
    assert kham["gia"] == [Decimal(200000)]


def test_khong_co_luot_thi_khong_bia_dong() -> None:
    assert bs.dong_kham(None, []) is None


def test_khong_hen_nhung_co_loai_kham_thi_dong_binh_thuong() -> None:
    """Lượt không hẹn nhưng có loại khám (ví dụ vãng lai hoặc gán trên Bàn khám)
    thì dòng tiền khám phải tính bình thường, không bị gán van_de."""
    row = {"st_id": "st_pk", "name": "Khám phụ khoa", "khong_hen": True}
    gia = [
        {
            "name": "khám phụ khoa",
            "unit_price": Decimal(250000),
            "billing_owner": "CLINIC",
        }
    ]
    kham = bs.dong_kham(row, gia)
    assert kham is not None
    assert "van_de" not in kham
    assert kham["ma"] == "st_pk"
    assert kham["ten"] == "Khám phụ khoa"
    assert kham["gia"] == [Decimal(250000)]


# ── DB ─────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_luoc_do_van_ep_lich_hen_phai_co_loai_kham(q: Quay) -> None:
    nullable = await q.pool.fetchval(
        "SELECT is_nullable FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = 'appointment'"
        "   AND column_name = 'service_type_id'"
    )
    assert nullable == "NO"


@pytest.mark.db
@pytest.mark.asyncio
async def test_hoa_don_that_khong_bo_im_lang_khi_loai_kham_hong(q: Quay) -> None:
    """Loại khám của lịch hẹn mất tên (dữ liệu hỏng) → dòng tiền khám có vấn đề."""
    async with q.pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(
                "UPDATE service_type st SET name = '  '"
                "  FROM visit vi JOIN appointment a ON a.id = vi.appointment_id"
                " WHERE vi.visit_id = $1::uuid AND st.id = a.service_type_id",
                q.visit_id,
            )
            hd = await bs.tinh_hoa_don(
                conn,
                clinic_id=q.thu_ngan.clinic_id,
                visit_id=q.visit_id,
                kind="dich_vu",
            )
        finally:
            await tr.rollback()
    kham = [d for d in hd.dong if d.source_type == "exam"]
    assert len(kham) == 1
    assert kham[0].ten == "Tiền khám"
    assert kham[0].van_de and "chưa xác định loại khám" in kham[0].van_de
    assert not hd.thu_duoc
