"""CỘT + BỘ LỌC "Phản hồi thuốc" ở bảng Danh sách khách hàng (16/10/2026).

Tuyền: phản hồi sau dùng thuốc chỉ nằm trong khung chi tiết — cho ra bảng danh
sách. Khoá ở đây: gói `man-khach-hang` trả đúng SỐ phản hồi / NGÀY gần nhất /
RÚT GỌN cho cả trang, khách không có → vắng mặt, phản hồi đã GỠ không tính, số
CÂU SQL không tăng theo số khách (một câu gộp), và bộ lọc dùng cùng luật đếm.

    scripts/test-nhanh.sh src/tests/services/test_phan_hoi_thuoc_cot_db.py
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from clinicai.services.danh_sach_khach_cskh import danh_sach_khach
from clinicai.services.man_khach_hang_service import ManKhachHangService
from clinicai.services.phan_hoi_thuoc_service import PhanHoiThuocService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_phan_hoi_thuoc_db import _ke_don, _luot_cu
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


class _KetNoiDem:
    """Bọc kết nối thật, đếm mọi lời gọi chạm database."""

    def __init__(self, conn: asyncpg.Connection, so: list[int]) -> None:
        self._conn = conn
        self._so = so

    def __getattr__(self, ten: str) -> Any:
        thuoc = getattr(self._conn, ten)
        if ten in ("fetch", "fetchrow", "fetchval", "execute"):

            async def dem(*a: Any, **k: Any) -> Any:
                self._so[0] += 1
                return await thuoc(*a, **k)

            return dem
        return thuoc


class _PoolDem:
    def __init__(self, pool: asyncpg.Pool) -> None:  # noqa: F811
        self._pool = pool
        self.so = [0]

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[_KetNoiDem]:
        async with self._pool.acquire() as conn:
            yield _KetNoiDem(conn, self.so)


async def _khach_co_luot(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Any,
    ten: str,
    *,
    so_luot: int,
) -> tuple[str, list[str]]:
    """Khách tên `ten` có `so_luot` lượt, mỗi lượt có đơn (cũ nhất trước)."""
    pid = await _benh_nhan(pool, ca)
    await pool.execute(
        "UPDATE patient SET full_name = $2 WHERE clinic_patient_id = $1::uuid",
        pid,
        ten,
    )
    luot: list[str] = []
    for i in range(so_luot):
        v = await _check_in(pool, ca, pid, ca.loai_kham)
        await _ke_don(pool, v, f"Thuốc {i}")
        if i < so_luot - 1:
            await _luot_cu(pool, v, 10 * (so_luot - i))
        luot.append(v)
    return pid, luot


async def test_cot_phan_hoi_thuoc_dem_ngay_rut_gon_va_mot_cau_gop(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    dau = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        cskh = await _nguoi(conn, ca.loc, "CSKH")
    sv = PhanHoiThuocService(pool)

    # A: hai lượt có đơn, ba phản hồi — một cái bị gỡ; cái MỚI NHẤT còn hiệu lực
    # dài, nhiều dòng (phải gộp một dòng + rút gọn).
    a, (a_cu, a_moi) = await _khach_co_luot(pool, ca, f"KH{dau} A", so_luot=2)
    p1 = await sv.ghi(
        identity=cskh, clinic_patient_id=a, visit_id=a_cu, noi_dung="Đỡ đau bụng"
    )
    bi_go = await sv.ghi(
        identity=cskh, clinic_patient_id=a, visit_id=a_moi, noi_dung="Sẽ bị gỡ"
    )
    dai = (
        "Uống thuốc xong thấy hơi buồn nôn,\n  chóng mặt nhẹ vào buổi sáng,"
        " chiều thì hết hẳn."
    )
    await sv.ghi(
        identity=cskh, clinic_patient_id=a, visit_id=a_moi, kenh="ZALO", noi_dung=dai
    )
    await sv.go(identity=cskh, phan_hoi_id=bi_go["id"])
    # Đặt mốc thời gian rõ ràng để "gần nhất" không phụ thuộc đồng hồ.
    await pool.execute(
        "UPDATE tuong_tac_cskh SET xay_ra_luc = now() - interval '5 days'"
        " WHERE id = $1::uuid",
        p1["id"],
    )

    # B: một phản hồi.
    b, (b_luot,) = await _khach_co_luot(pool, ca, f"KH{dau} B", so_luot=1)
    await sv.ghi(identity=cskh, clinic_patient_id=b, noi_dung="Ổn")
    # C: có đơn nhưng chưa phản hồi. D: chỉ có phản hồi đã gỡ.
    c, _ = await _khach_co_luot(pool, ca, f"KH{dau} C", so_luot=1)
    d, (_d_luot,) = await _khach_co_luot(pool, ca, f"KH{dau} D", so_luot=1)
    d_ph = await sv.ghi(identity=cskh, clinic_patient_id=d, noi_dung="Đã gỡ")
    await sv.go(identity=cskh, phan_hoi_id=d_ph["id"])

    ids = [a, b, c, d]
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=ids)
    theo_khach = {r["clinic_patient_id"]: r for r in goi["phan_hoi_thuoc"]}

    # Khách không phản hồi / chỉ có phản hồi đã gỡ → vắng mặt (ô trống).
    assert set(theo_khach) == {a, b}
    ra = theo_khach[a]
    assert ra["so_phan_hoi"] == 2, "phản hồi đã gỡ không được tính"
    assert ra["kenh"] == "ZALO"
    assert ra["noi_dung"].startswith("Uống thuốc xong thấy hơi buồn nôn,")
    assert ra["tom_tat"] is not None
    assert "\n" not in ra["tom_tat"] and len(ra["tom_tat"]) == 40
    assert ra["tom_tat"].endswith("…")
    assert ra["tom_tat"].startswith("Uống thuốc xong thấy hơi buồn nôn,")
    assert ra["luc"] is not None
    assert theo_khach[b]["so_phan_hoi"] == 1 and theo_khach[b]["tom_tat"] == "Ổn"

    # Ngày "gần nhất" = phản hồi mới nhất CÒN HIỆU LỰC (không phải cái 5 ngày trước,
    # cũng không phải cái đã gỡ).
    moi_nhat = await pool.fetchval(
        "SELECT max(xay_ra_luc) FROM tuong_tac_cskh WHERE clinic_patient_id = $1::uuid"
        " AND loai = 'PHAN_HOI_THUOC' AND huy_luc IS NULL",
        a,
    )
    assert ra["luc"] == moi_nhat.isoformat()

    # SỐ CÂU SQL không tăng theo số khách: một khách và bốn khách chạy cùng số lời gọi.
    mot = _PoolDem(pool)
    await ManKhachHangService(mot).goi_du_lieu(clinic_id=CLINIC, ids=[a])
    nhieu = _PoolDem(pool)
    await ManKhachHangService(nhieu).goi_du_lieu(clinic_id=CLINIC, ids=ids)
    assert nhieu.so[0] == mot.so[0] > 0, (
        f"số lời gọi database phụ thuộc số khách: 1 khách = {mot.so[0]}, "
        f"4 khách = {nhieu.so[0]}"
    )

    # Bộ lọc: cùng luật đếm — chỉ A và B (C không phản hồi, D chỉ có cái đã gỡ).
    tat = await danh_sach_khach(pool, identity=cskh, q=f"KH{dau}")
    assert {r["clinic_patient_id"] for r in tat["rows"]} == {a, b, c, d}
    bat = await danh_sach_khach(
        pool, identity=cskh, q=f"KH{dau}", co_phan_hoi_thuoc=True
    )
    assert {r["clinic_patient_id"] for r in bat["rows"]} == {a, b}
    assert bat["total"] == 2
