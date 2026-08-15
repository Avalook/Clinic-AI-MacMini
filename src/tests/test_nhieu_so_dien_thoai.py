"""Một bệnh nhân, nhiều số điện thoại (15/08/2026).

Hai nửa của tính năng, hai kiểu kiểm:

  · `them_so_dien_thoai` — chạy qua CHÍNH hàm với connection giả: chuẩn hoá
    số, chặn trùng trong chính hồ sơ, và event_log KHÔNG được chứa số đầy đủ
    (sổ thao tác sống lâu hơn mọi màn hình; 4 số cuối là đủ đối chiếu).
  · Các ĐƯỜNG TRA SỐ — kiểm bằng đọc mã nguồn: cả ba đường asyncpg
    (get_by_phone, find_phone_duplicates, MPI find_candidates) phải nhìn thấy
    bảng số-thêm. Một đường mù là "tra số nào cũng ra" đúng ở màn này sai ở
    màn kia — chính xác loại lệch mà Luật 12.2 cấm.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.services.mpi_service import MPIService
from clinicai.services.patient_service import PatientService


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="CSKH A",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> bool:
        return False


class _Conn:
    """Kịch bản: hồ sơ trả từ fetchrow, id chèn trả từ fetchval."""

    def __init__(self, *, ho_so: dict[str, Any] | None, chen_duoc: bool) -> None:
        self._ho_so = ho_so
        self._chen_duoc = chen_duoc
        self.event_sql: list[tuple[str, tuple[object, ...]]] = []
        self.chen_args: tuple[object, ...] | None = None

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchrow(self, sql: str, *args: object) -> dict[str, Any] | None:
        assert "FROM patient" in sql
        return self._ho_so

    async def fetchval(self, sql: str, *args: object) -> object:
        assert "INSERT INTO public.patient_sdt_them" in sql
        self.chen_args = args
        return "id-moi" if self._chen_duoc else None

    async def execute(self, sql: str, *args: object) -> None:
        assert "patient.phone_added" in sql
        self.event_sql.append((sql, args))


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def acquire(self) -> "_Pool":
        return self

    async def __aenter__(self) -> _Conn:
        return self._conn

    async def __aexit__(self, *_: object) -> None:
        return None


def _goi(conn: _Conn, so: str, loai: str = "CHINH") -> dict[str, Any]:
    service = PatientService(_Pool(conn))
    return asyncio.run(
        service.them_so_dien_thoai(
            clinic_patient_id="bn000000-0000-4000-8000-000000000001",
            so_dien_thoai=so,
            loai=loai,
            identity=_identity(),
        )
    )


_HO_SO = {"phone_primary": "0901111111", "phone_secondary": "0902222222"}


class TestThemSoDienThoai:
    def test_chuan_hoa_84_ve_dang_0(self) -> None:
        conn = _Conn(ho_so=_HO_SO, chen_duoc=True)
        ket = _goi(conn, "+84 903 333 333")
        assert ket["so_dien_thoai"] == "0903333333"
        assert conn.chen_args is not None and "0903333333" in conn.chen_args

    def test_so_rac_bi_chan_tu_cua(self) -> None:
        conn = _Conn(ho_so=_HO_SO, chen_duoc=True)
        with pytest.raises(ValidationError):
            _goi(conn, "12ab")
        assert conn.chen_args is None, "số rác mà vẫn chạm tới INSERT"

    def test_trung_so_tren_chinh_ho_so_thi_noi_ro(self) -> None:
        conn = _Conn(ho_so=_HO_SO, chen_duoc=True)
        with pytest.raises(ConflictError):
            _goi(conn, "0901111111")

    def test_bam_trung_hai_lan_khong_thanh_hai_dong(self) -> None:
        """ON CONFLICT trả None → báo trùng, KHÔNG ghi event cho một lần
        chèn không xảy ra."""
        conn = _Conn(ho_so=_HO_SO, chen_duoc=False)
        with pytest.raises(ConflictError):
            _goi(conn, "0903333333")
        assert conn.event_sql == []

    def test_event_log_khong_chua_so_day_du(self) -> None:
        conn = _Conn(ho_so=_HO_SO, chen_duoc=True)
        _goi(conn, "0903333333", loai="NGUOI_NHA")
        assert len(conn.event_sql) == 1
        payload = json.loads(str(conn.event_sql[0][1][2]))
        assert payload == {"loai": "NGUOI_NHA", "duoi": "3333"}
        assert "0903333333" not in str(conn.event_sql[0][1])


class TestMoiDuongTraSoDeuThaySoThem:
    """Ba đường tra số asyncpg + matches của check-duplicate."""

    @pytest.mark.parametrize(
        "ham",
        [PatientService.get_by_phone, PatientService.find_phone_duplicates],
    )
    def test_duong_tra_theo_so(self, ham: Any) -> None:
        ma = inspect.getsource(ham)
        assert "patient_sdt_them" in ma, (
            f"{ham.__name__} không nhìn thấy số thêm — màn dùng nó sẽ trả "
            "'không có ai' cho một số đang nằm trong hồ sơ"
        )

    def test_mpi_dedup_thay_so_them(self) -> None:
        ma = inspect.getsource(MPIService.find_candidates)
        assert "patient_sdt_them" in ma, (
            "dedup lúc lưu mù số thêm — khách đọc lại số phụ là hồ sơ tách đôi"
        )

    def test_check_duplicate_tra_khoa_ho_so(self) -> None:
        """Nút "thêm số cho khách này" cần `clinic_patient_id` — thiếu nó thì
        ô cảnh báo chỉ nói được, không làm được."""
        from clinicai.api.v1 import patients

        ma = inspect.getsource(patients.check_duplicate)
        assert ma.count("clinic_patient_id") >= 2, (
            "matches lẫn trung_ten đều phải mang khoá hồ sơ"
        )

    def test_ten_don_thuan_du_de_hoi_trung_ten(self) -> None:
        """Khách cũ đọc số MỚI, người trực mới kịp gõ TÊN — chưa có năm sinh.

        Bản trước đòi (tên VÀ năm) hoặc số nên đúng ca hay gặp nhất im lặng
        (Tuyền 15/08/2026). Tên đơn thuần phải đủ để đổ vào `trung_ten`; khớp
        MẠNH (matches) vẫn theo luật đường lưu, không nới."""
        from clinicai.api.v1 import patients

        ma = inspect.getsource(patients.check_duplicate)
        assert "any([phone, full_name])" in ma
        assert "any([phone, full_name and birth_year])" not in ma


class _ConnXoa:
    """DELETE trả loai của dòng vừa xoá; None = không có dòng nào."""

    def __init__(self, *, loai_xoa_duoc: str | None) -> None:
        self._loai = loai_xoa_duoc
        self.event_args: tuple[object, ...] | None = None

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchval(self, sql: str, *args: object) -> object:
        assert "DELETE FROM public.patient_sdt_them" in sql
        assert "clinic_id = $1::uuid" in sql, "xoá phải tự khoá phòng khám"
        return self._loai

    async def execute(self, sql: str, *args: object) -> None:
        assert "patient.phone_removed" in sql
        self.event_args = args


class TestXoaSoDienThoai:
    def _goi(self, conn: _ConnXoa, so: str) -> dict[str, Any]:
        service = PatientService(_Pool(conn))  # type: ignore[arg-type]
        return asyncio.run(
            service.xoa_so_dien_thoai(
                clinic_patient_id="bn000000-0000-4000-8000-000000000001",
                so_dien_thoai=so,
                identity=_identity(),
            )
        )

    def test_xoa_that_va_event_chi_ghi_4_so_cuoi(self) -> None:
        conn = _ConnXoa(loai_xoa_duoc="NGUOI_NHA")
        assert self._goi(conn, "+84903333333") == {"da_xoa": True}
        assert conn.event_args is not None
        payload = json.loads(str(conn.event_args[2]))
        assert payload == {"loai": "NGUOI_NHA", "duoi": "3333"}
        assert "0903333333" not in str(conn.event_args)

    def test_so_khong_co_trong_danh_sach_thi_noi_ro(self) -> None:
        from clinicai.core.exceptions import ResourceNotFoundError

        conn = _ConnXoa(loai_xoa_duoc=None)
        with pytest.raises(ResourceNotFoundError):
            self._goi(conn, "0909999999")
        assert conn.event_args is None, "không xoá gì thì không được ghi event"
