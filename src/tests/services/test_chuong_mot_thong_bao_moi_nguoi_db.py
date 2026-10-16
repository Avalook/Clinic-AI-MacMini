"""Chuông "Kiểm kê quầy thuốc có lệch" hiện 3 thông báo GIỐNG HỆT (14/10/2026).

Gốc: chuông ghi mỗi VAI một hàng (`ghi_chuong_vai`: dược sĩ, quản lý, trưởng ca —
trạng thái đọc / xử lý chung cả vai, quản lý chỉnh được người nhận). Người có
nhiều vai (quản lý đứng thêm vị trí trưởng ca…) khớp cả ba hàng cùng nội dung
nên `cua_toi` trả ba dòng giống hệt sau MỘT lần chốt.

Sửa ở chỗ ĐỌC: một sự việc = một dòng cho người xem; đóng một thì đóng các hàng
cùng sự việc mà chính người ấy cũng nhận. Cách ghi theo vai KHÔNG đổi.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import từ CP1 / G7.
import dataclasses
from typing import Any

import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.events.catalogue import CHUONG
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services.thong_bao_service import ThongBaoService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_kho_quay_db import Co, co  # noqa: F401
from tests.services.test_kiem_ke_ca_db import _dem, _mo, _thuoc_co_ton
from tests.services.test_tien_thuoc_cp1_db import q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _co_vai(ds: StaffIdentity, *vai: ClinicRole) -> StaffIdentity:
    """Cùng người, đứng thêm các vị trí → nhận chuông của nhiều vai."""
    return dataclasses.replace(ds, vai_theo_vi_tri=frozenset(vai))


async def _chot_lech(co: Co, ca: str, dem_that: int = 3) -> str:
    """Một lần chốt KIỂM KÊ CUỐI CA có lệch → một sự kiện → chuông ghi theo vai."""
    drug, _ = await _thuoc_co_ton(co, 5)
    dau = await _mo(co, "DAU", ca)
    await _dem(co, dau["id"], **{drug: 5})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=dau["id"])
    cuoi = await _mo(co, "CUOI", ca)
    await _dem(co, cuoi["id"], **{drug: dem_that})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=cuoi["id"])
    await chay_ben_nhan(co.q.pool, CHUONG)
    return str(cuoi["id"])


async def _id_cua_phieu(co: Co, *phieu: str) -> set[str]:
    """Mọi hàng chuông (mở hay đóng) của các phiếu — để lọc khỏi chuông của bài khác."""
    rows = await co.q.pool.fetch(
        "SELECT id::text FROM thong_bao WHERE nguon = 'kiem_ke_ca'"
        " AND nguon_id = ANY($1)",
        list(phieu),
    )
    return {r["id"] for r in rows}


async def _cua_toi(co: Co, ds: StaffIdentity, *phieu: str) -> list[dict[str, Any]]:
    cua_phieu = await _id_cua_phieu(co, *phieu)
    kq = await ThongBaoService(co.q.pool).cua_toi(identity=ds)
    return [t for t in kq if t["id"] in cua_phieu]


async def _hang_theo_vai(co: Co, phieu: str) -> dict[str, str]:
    rows = await co.q.pool.fetch(
        "SELECT vai_nhan, id::text FROM thong_bao WHERE nguon = 'kiem_ke_ca'"
        " AND nguon_id = $1 AND da_xu_ly_luc IS NULL",
        phieu,
    )
    return {r["vai_nhan"]: r["id"] for r in rows}


async def test_nhieu_vai_van_chi_thay_mot_chuong_moi_lan_chot(co: Co) -> None:
    phieu = await _chot_lech(co, "SANG")
    # Cách GHI không đổi: mỗi vai được chọn một hàng.
    assert set(await _hang_theo_vai(co, phieu)) >= {
        "PHARMACIST",
        "MANAGEMENT",
        "TRUONG_CA",
    }

    nhieu_vai = _co_vai(co.ds, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA)
    assert {ClinicRole.PHARMACIST, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA} <= (
        nhieu_vai.cac_vai()
    )
    thay = await _cua_toi(co, nhieu_vai, phieu)
    assert len(thay) == 1, "ba vai, một lần chốt → đúng MỘT chuông"
    assert "1 thuốc lệch" in thay[0]["noi_dung"]
    assert "rn" not in thay[0]

    # Người một vai cũng đúng một.
    assert len(await _cua_toi(co, co.ds, phieu)) == 1


async def test_hai_lan_chot_la_hai_chuong_khac_nhau(co: Co) -> None:
    p1 = await _chot_lech(co, "SANG", 3)
    p2 = await _chot_lech(co, "CHIEU", 2)
    nhieu_vai = _co_vai(co.ds, ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA)
    thay = await _cua_toi(co, nhieu_vai, p1, p2)
    assert len(thay) == 2, "gộp theo SỰ VIỆC, không gộp hai lần chốt"
    assert len(await _cua_toi(co, nhieu_vai, p1)) == 1


async def test_dong_mot_chuong_dong_cac_hang_cung_su_viec_cua_toi(co: Co) -> None:
    phieu = await _chot_lech(co, "SANG")
    # Dược sĩ + quản lý (KHÔNG có vị trí trưởng ca).
    ban = _co_vai(co.ds, ClinicRole.MANAGEMENT)
    truong_ca = dataclasses.replace(co.ds, role=ClinicRole.TRUONG_CA)
    assert ClinicRole.PHARMACIST not in truong_ca.cac_vai()

    (chuong,) = await _cua_toi(co, ban, phieu)
    kq = await ThongBaoService(co.q.pool).da_xu_ly(
        identity=ban, thong_bao_id=chuong["id"], ghi_chu=None
    )
    assert kq["ok"] is True

    # Hàng kế KHÔNG lòi ra: không còn chuông của sự việc này cho người ấy.
    assert await _cua_toi(co, ban, phieu) == []
    con_mo = await _hang_theo_vai(co, phieu)
    # Hai vai người ấy nhận đã đóng; vai trưởng ca người ấy KHÔNG nhận thì vẫn mở
    # cho người khác — không đóng hộ quá phần của mình.
    assert set(con_mo) == {"TRUONG_CA"}
    assert len(await _cua_toi(co, truong_ca, phieu)) == 1


async def test_chuong_khong_co_ma_nguon_khong_bi_gop(co: Co) -> None:
    """Hai chuông cùng chữ nhưng không có `nguon_id` là hai việc riêng."""
    for _ in range(2):
        await co.q.pool.execute(
            "INSERT INTO thong_bao (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung,"
            " nguon, nguoi_goi_staff_id) VALUES ($1::uuid, 'PHARMACIST', 'THUONG',"
            " 'Chuông thử không mã', 'giống hệt', 'thu_nghiem', $2::uuid)",
            co.ds.clinic_id,
            co.ds.staff_id,
        )
    kq = await ThongBaoService(co.q.pool).cua_toi(identity=co.ds)
    assert len([t for t in kq if t["tieu_de"] == "Chuông thử không mã"]) == 2
