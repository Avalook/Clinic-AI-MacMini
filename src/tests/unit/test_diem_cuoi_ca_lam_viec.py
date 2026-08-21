"""Điểm cuối cho quản lý tự sửa giờ ca — GET/PATCH `/api/v1/ca-lam-viec`.

Đây là đường GHI vào cấu hình đang chạy của phòng khám, nên ba thứ phải đúng và
mỗi thứ hỏng theo một kiểu riêng:

* **Lớp gác** — sai thì Lễ tân đổi được giờ ca của cả phòng khám.
* **Phạm vi phòng khám** — `clinic_id` phải suy từ membership. Nhận từ body thì
  phòng khám A sửa được phòng khám B, và đó là lỗi hệ thống nhiều phòng khám
  nặng nhất có thể có.
* **Ghi đè cả cụm** — vá từng ca sẽ để ca cũ nằm im trong cấu hình, người sửa
  tưởng đã bỏ ca tối mà hệ vẫn xếp ca tối.
"""

from __future__ import annotations

import inspect
import json
from contextlib import asynccontextmanager
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers import config as router_config
from clinicai.api.v1.routers.config import (
    CaLamViecRequest,
    KhungCaRequest,
    doc_ca_lam_viec,
    sua_ca_lam_viec,
)


class TestLopGac:
    def test_ca_hai_diem_cuoi_deu_gac_bang_luat_dat_lich(self) -> None:
        """Cùng gác với luật đặt lịch: Trưởng ca + Quản lý, không ai khác."""
        for ham in (router_config.doc_ca_lam_viec, router_config.sua_ca_lam_viec):
            nguon = inspect.getsource(ham)
            assert "_BOOKING_POLICY_GUARD" in nguon, ham.__name__

    def test_gac_khong_gom_le_tan_hay_cskh(self) -> None:
        nguon = inspect.getsource(router_config)
        dong = next(
            d for d in nguon.splitlines() if d.startswith("_BOOKING_POLICY_GUARD =")
        )
        assert ClinicRole.MANAGEMENT.name in dong
        assert ClinicRole.TRUONG_CA.name in dong
        for cam in ("RECEPTION", "CSKH", "DOCTOR"):
            assert cam not in dong, f"{cam} không được sửa giờ ca của phòng khám"


class TestPhamViPhongKham:
    def test_clinic_id_suy_tu_membership_khong_nhan_tu_body(self) -> None:
        """Nhận `clinic_id` từ body là phòng khám A sửa được phòng khám B."""
        nguon = inspect.getsource(router_config.sua_ca_lam_viec)
        assert "identity.clinic_id" in nguon
        assert "body.clinic_id" not in nguon

        than = inspect.getsource(router_config.CaLamViecRequest)
        assert "clinic_id" not in than, "thân request không được có clinic_id"

    def test_moi_cau_sql_deu_loc_theo_clinic_id(self) -> None:
        for ham in (router_config.doc_ca_lam_viec, router_config.sua_ca_lam_viec):
            nguon = inspect.getsource(ham)
            for tu in ("FROM clinic c", "UPDATE public.clinic"):
                if tu in nguon:
                    assert "$1::uuid" in nguon, ham.__name__


class TestGhiDeCaCum:
    def test_ghi_ca_cum_ca_lam_viec_chu_khong_va_tung_ca(self) -> None:
        """`jsonb_set` vào `{ca_lam_viec}`, không vào `{ca_lam_viec,SANG}`."""
        nguon = inspect.getsource(router_config.sua_ca_lam_viec)
        assert "'{ca_lam_viec}'" in nguon
        for ma in ("{ca_lam_viec,SANG}", "{ca_lam_viec,CHIEU}", "{ca_lam_viec,TOI}"):
            assert ma not in nguon, "vá từng ca sẽ để ca cũ nằm im trong cấu hình"

    def test_co_kiem_cau_hinh_truoc_khi_ghi(self) -> None:
        nguon = inspect.getsource(router_config.sua_ca_lam_viec)
        vi_tri_kiem = nguon.find("kiem_cau_hinh_ca")
        vi_tri_ghi = nguon.find("UPDATE public.clinic")
        assert vi_tri_kiem != -1, "phải kiểm cấu hình"
        assert vi_tri_ghi != -1
        assert vi_tri_kiem < vi_tri_ghi, "phải kiểm TRƯỚC khi ghi"

    def test_khong_dung_toi_bang_lich_hen(self) -> None:
        """Thu ca lại KHÔNG được huỷ lịch cũ nằm ngoài ca.

        Phạt người dùng vì dữ liệu có trước luật là cách chắc nhất để họ không
        dám sửa cấu hình nữa.
        """
        nguon = inspect.getsource(router_config.sua_ca_lam_viec)
        for bang in ("appointment", "visit", "work_item"):
            assert bang not in nguon, f"đường sửa cấu hình không được chạm {bang}"


class TestDangDuLieu:
    def test_gio_phai_dung_dang_hh_mm(self) -> None:
        nguon = inspect.getsource(router_config.KhungCaRequest)
        assert "pattern" in nguon and r"\d{2}:\d{2}" in nguon

    def test_get_tra_kem_gio_mo_cua(self) -> None:
        """Màn hình phải cảnh báo "ca tràn ngoài giờ đóng cửa" ngay lúc gõ."""
        nguon = inspect.getsource(router_config.doc_ca_lam_viec)
        assert "gio_mo_cua" in nguon
        assert "'hours'" in nguon


# ── Chạy thật, không chỉ đọc mã ────────────────────────────────────────────
#
# Mấy bài trên soi NGUỒN nên chúng bắt được "quên gác quyền" nhưng không bắt
# được "câu SQL sai" hay "trả sai hình dạng". Phần dưới chạy chính hai hàm ấy
# với một pool giả.

CA_DANG_DUNG = {
    "SANG": {"bat_dau": "08:00", "ket_thuc": "13:00"},
    "CHIEU": {"bat_dau": "14:00", "ket_thuc": "17:30"},
    "TOI": {"bat_dau": "17:30", "ket_thuc": "21:30"},
}
GIO_ROWS = [{"thu": t, "mo": "07:00", "dong": "22:00"} for t in range(7)]


class _Conn:
    def __init__(self, settings: object) -> None:
        self._settings = settings
        self.da_ghi: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, sql: str, *args: object) -> object:
        return self._settings

    async def fetch(self, sql: str, *args: object) -> list[Any]:
        return GIO_ROWS

    async def execute(self, sql: str, *args: object) -> None:
        self.da_ghi.append((sql, args))


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Quản lý",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _yeu_cau(**doi: dict[str, str]) -> CaLamViecRequest:
    cum = {**CA_DANG_DUNG, **doi}
    return CaLamViecRequest(
        ca_lam_viec={m: KhungCaRequest(**k) for m, k in cum.items()}
    )


@pytest.mark.asyncio
async def test_doc_tra_du_ba_ca_kem_nhan_va_gio_mo_cua() -> None:
    conn = _Conn(json.dumps({"ca_lam_viec": CA_DANG_DUNG}))
    ra = await doc_ca_lam_viec(identity=_ai(), pool=_Pool(conn))

    ca = ra["ca_lam_viec"]
    assert isinstance(ca, dict)
    assert set(ca) == {"SANG", "CHIEU", "TOI"}
    assert ca["TOI"] == {"bat_dau": "17:30", "ket_thuc": "21:30", "nhan": "Tối"}
    # Giờ mở cửa đi kèm để màn hình cảnh báo tại chỗ, không đợi bấm Lưu.
    assert isinstance(ra["gio_mo_cua"], dict)
    assert ra["gio_mo_cua"]["1"] == {"mo": "07:00", "dong": "22:00"}


@pytest.mark.asyncio
async def test_doc_khi_chua_khai_thi_tra_ca_mac_dinh_chu_khong_rong() -> None:
    """Ba ô trống trông y hệt "chưa khai ca" và mời người dùng gõ đè lên."""
    ra = await doc_ca_lam_viec(identity=_ai(), pool=_Pool(_Conn(None)))
    ca = ra["ca_lam_viec"]
    assert isinstance(ca, dict)
    assert set(ca) == {"SANG", "CHIEU", "TOI"}


@pytest.mark.asyncio
async def test_sua_hop_le_thi_ghi_dung_mot_lan_va_dung_cum() -> None:
    conn = _Conn(json.dumps({"ca_lam_viec": CA_DANG_DUNG}))
    ra = await sua_ca_lam_viec(
        body=_yeu_cau(TOI={"bat_dau": "18:00", "ket_thuc": "21:00"}),
        identity=_ai(),
        pool=_Pool(conn),
    )
    assert ra["ok"] is True
    assert len(conn.da_ghi) == 1, "chỉ ghi một lần"
    sql, args = conn.da_ghi[0]
    assert "'{ca_lam_viec}'" in sql
    ghi = json.loads(args[1])
    assert ghi["TOI"] == {"bat_dau": "18:00", "ket_thuc": "21:00"}
    assert set(ghi) == {"SANG", "CHIEU", "TOI"}, "ghi đè CẢ CỤM"


@pytest.mark.asyncio
async def test_sua_sai_thi_khong_ghi_gi_ca() -> None:
    """Từ chối mà vẫn ghi một phần là để lại cấu hình nửa vời."""
    conn = _Conn(json.dumps({"ca_lam_viec": CA_DANG_DUNG}))
    with pytest.raises(ValidationError) as e:
        await sua_ca_lam_viec(
            body=_yeu_cau(TOI={"bat_dau": "17:30", "ket_thuc": "23:00"}),
            identity=_ai(),
            pool=_Pool(conn),
        )
    assert conn.da_ghi == [], "sai thì không được ghi"
    assert "mở cửa" in str(e.value)


@pytest.mark.asyncio
async def test_ma_ca_la_thi_tu_choi() -> None:
    conn = _Conn(json.dumps({"ca_lam_viec": CA_DANG_DUNG}))
    body = CaLamViecRequest(
        ca_lam_viec={"NUA_DEM": KhungCaRequest(bat_dau="22:00", ket_thuc="23:00")}
    )
    with pytest.raises(ValidationError):
        await sua_ca_lam_viec(body=body, identity=_ai(), pool=_Pool(conn))
    assert conn.da_ghi == []


@pytest.mark.asyncio
async def test_moi_loi_hien_cung_mot_lan() -> None:
    conn = _Conn(json.dumps({"ca_lam_viec": CA_DANG_DUNG}))
    with pytest.raises(ValidationError) as e:
        await sua_ca_lam_viec(
            body=_yeu_cau(
                SANG={"bat_dau": "13:00", "ket_thuc": "08:00"},
                TOI={"bat_dau": "17:30", "ket_thuc": "23:00"},
            ),
            identity=_ai(),
            pool=_Pool(conn),
        )
    cau = str(e.value)
    assert "Sáng" in cau and "Tối" in cau, cau
    assert "\n" in cau, "nhiều lỗi thì ngăn bằng xuống dòng"
