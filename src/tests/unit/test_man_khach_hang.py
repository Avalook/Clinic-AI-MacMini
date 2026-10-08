"""Gói dữ liệu màn Quản lý khách hàng — một vòng thay mười (Lát 2, 22/08/2026).

Ba thứ phải đúng, mỗi thứ hỏng một kiểu riêng:

* **Gương vai hai chiều** — guard của endpoint phải khớp TỪNG VAI với
  `roles.ts` "/customers" phía frontend. Lệch là một vai thấy được màn nhưng
  màn trống dữ liệu (API chặn im lặng), hoặc một vai bị chặn màn mà gọi được
  API. Test đọc CẢ HAI file và so tập hợp.
* **Khoá phòng khám trong mọi câu SQL** — ids do máy chủ Next đưa sang, nhưng
  một id phòng khám khác lọt vào phải ra 0 dòng, không ra dữ liệu người ta.
* **Hình dạng bắt chước PostgREST** — page.tsx đọc `a.service?.name`,
  `t.staff?.full_name`; hình đổi là cả màn đổi.
"""

from __future__ import annotations

import inspect
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers import cskh as router_cskh
from clinicai.services import man_khach_hang_service as mkh
from clinicai.services.man_khach_hang_service import ManKhachHangService

_GOC = Path(__file__).resolve().parents[2]


class TestGuongVaiHaiChieu:
    def test_guard_khop_tung_vai_voi_roles_ts(self) -> None:
        """Web và API gác màn Quản lý khách hàng bằng CÙNG một quyền.

        21 lego (Tuyền 25/09/2026): quyền theo tài khoản, không theo vai — gương
        hai chiều nay là QUYỀN (`NAV_QUYEN["/customers"]` ↔ `cua_quyen(...)` của
        `_MAN_KHACH_HANG_GUARD`), không còn là tập vai. Lệch là một người thấy màn
        mà dữ liệu trống (API chặn), hoặc ngược lại.
        """
        roles_ts = (_GOC / "dashboard" / "lib" / "roles.ts").read_text(encoding="utf-8")
        khoi = re.search(r'const NAV_QUYEN[\s\S]*?"/customers": \[([^\]]+)\]', roles_ts)
        assert khoi, "không tìm thấy /customers trong NAV_QUYEN (roles.ts)"
        ben_web = set(re.findall(r'"([a-z_.]+)"', khoi.group(1)))

        nguon = inspect.getsource(router_cskh)
        khai = re.search(r"_MAN_KHACH_HANG_GUARD = cua_quyen\(([^)]+)\)", nguon)
        assert khai, "không tìm thấy guard (cua_quyen) của màn khách hàng"
        ben_api = set(re.findall(r'"([a-z_.]+)"', khai.group(1)))

        assert ben_api == ben_web == {"crm.manage"}, (
            f"hai bên lệch nhau — web: {ben_web}, api: {ben_api}."
        )


class TestKhoaPhongKham:
    def test_moi_cau_sql_deu_khoa_clinic_id(self) -> None:
        nguon = inspect.getsource(ManKhachHangService.goi_du_lieu)
        cau = re.findall(r'"""\s*(SELECT[\s\S]*?)"""', nguon)
        assert len(cau) == 10, f"phải đúng 10 câu, thấy {len(cau)}"
        for c in cau:
            assert "clinic_id = $1::uuid" in c, f"câu thiếu khoá phòng khám:\n{c[:90]}"

    def test_ids_di_bang_tham_so_khong_noi_chuoi(self) -> None:
        """Nối chuỗi ids vào SQL là mở cửa SQL injection — dù caller là máy
        chủ Next, luật vẫn là luật."""
        nguon = inspect.getsource(ManKhachHangService.goi_du_lieu)
        assert "ANY($2::uuid[])" in nguon
        assert "join(ids)" not in nguon and 'f"' not in nguon.split('"""')[1]


# ── Chạy thật với pool giả ─────────────────────────────────────────────────


class _Conn:
    def __init__(self, tra_loi: dict[str, list[dict[str, Any]]]) -> None:
        # khoá theo tên bảng chính trong câu SQL
        self._tra_loi = tra_loi
        self.cac_cau: list[str] = []

    async def fetch(self, sql: str, *args: object) -> list[dict[str, Any]]:
        self.cac_cau.append(sql)
        for bang, dong in self._tra_loi.items():
            if f"FROM {bang}" in sql or f"FROM {bang}\n" in sql:
                return dong
        return []


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self._conn


CLINIC = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.asyncio
async def test_hinh_dang_long_service_doctor_staff_nhu_postgrest() -> None:
    """page.tsx đọc `a.service?.name`, `a.doctor?.full_name`,
    `t.staff?.full_name` — hình phải giữ nguyên từng khoá."""
    conn = _Conn(
        {
            "appointment": [
                {
                    "clinic_patient_id": "p1",
                    "id": "a1",
                    "slot_start": "x",
                    "ten_dich_vu": "Khám phụ khoa",
                    "ten_bac_si": "BS Thành",
                }
            ],
            "tuong_tac_cskh": [
                {"id": "t1", "clinic_patient_id": "p1", "ten_nhan_vien": "Kim Tiến"}
            ],
            "hen_goi_lai": [
                {"id": "h1", "clinic_patient_id": "p1", "ten_nhan_vien": None}
            ],
        }
    )
    ra = await ManKhachHangService(_Pool(conn)).goi_du_lieu(
        clinic_id=CLINIC, ids=["p1"]
    )
    lich = ra["appts"][0]
    assert lich["service"] == {"name": "Khám phụ khoa"}
    assert lich["doctor"] == {"full_name": "BS Thành"}
    assert "ten_dich_vu" not in lich, "cột phẳng phải được gỡ sau khi lồng"
    assert ra["tuong_tac"][0]["staff"] == {"full_name": "Kim Tiến"}
    # Không có người thì staff = None — PostgREST embed trả null y như vậy,
    # và page.tsx đã có sẵn nhánh `nv?.full_name ?? null`.
    assert ra["hen_goi_lai"][0]["staff"] is None


@pytest.mark.asyncio
async def test_khong_co_khach_thi_tra_du_muoi_khoi_rong_khong_cham_db() -> None:
    conn = _Conn({})
    ra = await ManKhachHangService(_Pool(conn)).goi_du_lieu(clinic_id=CLINIC, ids=[])
    assert sorted(ra) == sorted(mkh._CAC_KHOI)
    assert all(v == [] for v in ra.values())
    assert conn.cac_cau == [], "không có khách thì không được chạm database"


@pytest.mark.asyncio
async def test_muoi_cau_chay_tren_mot_ket_noi() -> None:
    """Một request KHÔNG được ngốn nhiều kết nối của pool (trần 10) — trăm
    người mở màn cùng lúc mà mỗi người giữ mười kết nối là chết cả api."""
    conn = _Conn({})
    await ManKhachHangService(_Pool(conn)).goi_du_lieu(clinic_id=CLINIC, ids=["p1"])
    # 10 khối + 1 câu nhãn đếm lượt (services/nhan_luot.py, 08/10/2026).
    assert len(conn.cac_cau) == 11, "đúng mười một câu, cùng một kết nối"


# ── Endpoint: chặn đầu vào xấu ─────────────────────────────────────────────


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Lễ tân",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id=CLINIC,
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


@pytest.mark.asyncio
async def test_qua_60_id_thi_tu_choi() -> None:
    """Gửi cả nghìn id là dấu hiệu caller quên phân trang — chặn sớm cho lỗi
    nổi lên thay vì âm thầm quét bảng to."""
    ids = ",".join(str(uuid4()) for _ in range(61))
    with pytest.raises(ValidationError, match="60"):
        await router_cskh.man_khach_hang(ids=ids, identity=_ai(), pool=None)


@pytest.mark.asyncio
async def test_id_khong_phai_uuid_thi_tu_choi() -> None:
    with pytest.raises(ValidationError, match="không hợp lệ"):
        await router_cskh.man_khach_hang(
            ids="abc,def",
            identity=_ai(),
            pool=None,
        )
