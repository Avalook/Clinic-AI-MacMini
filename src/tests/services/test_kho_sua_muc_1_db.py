"""Sửa mức 1 sau buổi mổ xẻ kho thuốc / vật tư (17/10/2026).

Mỗi bài dựng lại đúng ca đã bấm ra lỗi trên bản local:

  3  số quá lớn (nhập 1 nghìn tỷ, giá 99.999.999.999.999, đếm 1e15) → trước là 500;
  4  vật tư nhập 1 nghìn tỷ cái vẫn được ghi sổ;
  5  hạn dùng gõ sai ("31/12/2027", "2027-02-31", "sắp tới") lưu im lặng "chưa có hạn";
  6  kiểm kê ca nhận đơn vị lạ rồi "điều chỉnh" xong phiếu kẹt, không hoàn tác được.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services.pharmacy_service import SO_TOI_DA, _so
from clinicai.services.vat_tu_kho_service import (
    GIA_TOI_DA,
    SO_LUONG_TOI_DA,
    tao_phieu,
)
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import Co, _bat, _nhap_kho, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401
from tests.services.test_vat_tu_kho_db import _bo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal


# ── 3 · số quá lớn → câu tiếng Việt, không 500 ───────────────────────────


async def test_so_thuoc_tran_dung_ranh_gioi() -> None:
    assert _so(str(SO_TOI_DA), ten="Số lượng nhập") == SO_TOI_DA
    with pytest.raises(ValidationError, match="quá lớn"):
        _so(str(SO_TOI_DA + 1), ten="Số lượng nhập")
    with pytest.raises(ValidationError, match="quá lớn"):
        _so("1e15", ten="Giá nhập", cho_0=True)
    with pytest.raises(ValidationError, match="phải là một con số"):
        _so("abc", ten="Giá nhập")


async def _phieu_nhap(co: Co, drug: str, **dong: Any) -> Any:
    d: dict[str, Any] = {
        "drug_catalog_id": drug,
        "batch_code": f"SM1-{uuid.uuid4().hex[:8]}",
        "expiry_date": "2099-12-31",
        "so_luong": 5,
        "unit": "viên",
        "gia_nhap": 800,
    }
    d.update(dong)
    return await kho.tao_phieu_nhap(
        co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, dong=[d]
    )


async def test_nhap_so_luong_va_gia_khong_lo_la_cau_viet_khong_500(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    with pytest.raises(ValidationError, match="Số lượng nhập quá lớn"):
        await _phieu_nhap(co, drug, so_luong="1000000000000")
    with pytest.raises(ValidationError, match="giá nhập quá lớn"):
        await _phieu_nhap(co, drug, gia_nhap="99999999999999")
    ok = await _phieu_nhap(co, drug, so_luong=str(SO_TOI_DA), gia_nhap=0)
    assert ok["ma_phieu"].startswith("PN")


async def test_kiem_kho_dem_khong_lo_la_cau_viet_khong_500(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    lo = await _nhap_kho(co, drug, 10)
    with pytest.raises(ValidationError, match="quá lớn"):
        await kho.kiem_kho(
            co.q.pool,
            identity=co.ds,
            khoa_gui=uuid.uuid4().hex,
            dong=[{"drug_batch_id": lo, "thuc_te": "1e15"}],
        )


# ── 4 · vật tư có trần hợp lý ────────────────────────────────────────────


async def _phieu_vat_tu(pool: Any, identity: Any, vt: str, **dong: Any) -> Any:
    d: dict[str, Any] = {"vat_tu_id": vt, "den_room_id": None, "so_luong": 3}
    d.update(dong)
    return await tao_phieu(
        pool, identity=identity, khoa_gui=uuid.uuid4().hex, loai="NHAP", dong=[d]
    )


async def test_vat_tu_nhap_so_khong_lo_bi_tu_choi_co_loi(pool: Any) -> None:
    identity, vt, _rooms = await _bo(pool)
    with pytest.raises(ValidationError, match="quá lớn"):
        await _phieu_vat_tu(pool, identity, vt, so_luong="1000000000000")
    with pytest.raises(ValidationError, match="quá lớn"):
        await _phieu_vat_tu(pool, identity, vt, so_luong=SO_LUONG_TOI_DA + 1)
    with pytest.raises(ValidationError, match="quá lớn"):
        await _phieu_vat_tu(pool, identity, vt, gia_nhap=GIA_TOI_DA + 1)
    # Đúng trần vẫn nhận; số thật của phòng khám không bị cản.
    await _phieu_vat_tu(
        pool, identity, vt, so_luong=SO_LUONG_TOI_DA, gia_nhap=GIA_TOI_DA
    )
    await _phieu_vat_tu(pool, identity, vt, so_luong="2.5", gia_nhap=12000)


# ── 5 · hạn dùng gõ sai → báo lỗi, không lưu im lặng ─────────────────────


async def _han_da_luu(co: Co, ma_lo: str) -> date | None:
    han: date | None = await co.q.pool.fetchval(
        "SELECT expiry_date FROM drug_batch WHERE batch_code = $1"
        " AND location_id = $2::uuid",
        ma_lo,
        co.loc,
    )
    return han


@pytest.mark.parametrize("han", ["2027-02-31", "sắp tới", "31/02/2027", "2027/12/31"])
async def test_han_dung_go_sai_bi_tu_choi_va_khong_tao_lo(co: Co, han: str) -> None:
    drug = await _thuoc_moi(co.q)
    ma = f"HAN-{uuid.uuid4().hex[:8]}"
    with pytest.raises(ValidationError, match="Dòng 1: hạn dùng"):
        await _phieu_nhap(co, drug, batch_code=ma, expiry_date=han)
    assert await _han_da_luu(co, ma) is None
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE batch_code = $1", ma
        )
        == 0
    ), "phiếu bị từ chối thì không được tạo lô"


async def test_han_dung_dung_dinh_dang_hoac_de_trong_van_nhan(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    for han, mong in (
        ("2027-12-31", date(2027, 12, 31)),
        ("31/12/2027", date(2027, 12, 31)),  # dạng Việt Nam: trước đây lưu thành rỗng
        (None, None),
        ("", None),
        ("   ", None),
    ):
        ma = f"HAN-{uuid.uuid4().hex[:8]}"
        await _phieu_nhap(co, drug, batch_code=ma, expiry_date=han)
        assert await _han_da_luu(co, ma) == mong, f"hạn gửi {han!r}"


# ── 6 · kiểm kê ca: đơn vị lạ, và điều chỉnh không áp được dòng nào ──────


async def _mo_va_dem(co: Co, drug: str, don_vi: str, dem: int) -> dict[str, Any]:
    p = await kk.mo_phieu(
        co.q.pool,
        identity=co.ds,
        ngay=hom_nay_vn().isoformat(),
        ca="TOI",
        loai="CUOI",
    )
    return await kk.luu_dem(
        co.q.pool,
        identity=co.ds,
        phieu_id=p["id"],
        dong=[{"drug_catalog_id": drug, "don_vi": don_vi, "dem": dem}],
    )


async def test_kiem_ke_don_vi_khong_co_that_bi_tu_choi(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _nhap_kho(co, drug, 10)  # lô "viên"
    with pytest.raises(ValidationError, match="chưa có lô nào theo đơn vị “tấn”"):
        await _mo_va_dem(co, drug, "tấn", 3)
    ok = await _mo_va_dem(co, drug, "viên", 8)  # đơn vị có thật: nhận như cũ
    assert [d["dem"] for d in ok["dong"]] == [D(8)]


async def test_dieu_chinh_khong_ap_duoc_dong_nao_thi_phieu_khong_bi_danh_dau(
    co: Co,
) -> None:
    """Tách kho/quầy: lô nằm ở KHO, quầy chưa có lô nào. Đếm quầy 5 viên → lệch +5
    mà quầy không có lô để cộng → không dòng nào áp được. Trước đây phiếu vẫn bị
    đánh dấu "đã điều chỉnh" (không còn dòng sổ để hoàn tác, không làm lại được)."""
    drug = await _thuoc_moi(co.q)
    await _bat(co)  # nhập sau khi bật → vào KHO
    await _nhap_kho(co, drug, 10)
    p = await _mo_va_dem(co, drug, "viên", 5)
    xem = await kk.xem_lech(co.q.pool, identity=co.ds, phieu_id=p["id"])
    kq = await kk.chot(
        co.q.pool,
        identity=co.ds,
        phieu_id=p["id"],
        ly_do_dong=[{**d, "ly_do": "Đếm thừa"} for d in xem["dong"]],
    )
    assert kq["dong"][0]["chua_ap"] == 5  # chốt được, nhưng không báo đã khớp
    with pytest.raises(ConflictError, match="đã ghi sổ lúc chốt"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Thử"
        )
    luc = await co.q.pool.fetchval(
        "SELECT dieu_chinh_luc FROM kiem_ke_ca WHERE id = $1::uuid", p["id"]
    )
    assert luc is None, "phiếu không được kẹt ở trạng thái đã điều chỉnh"
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE ref_id = $1::uuid"
            " AND txn_type = 'ADJUST'",
            p["id"],
        )
        == 0
    )
