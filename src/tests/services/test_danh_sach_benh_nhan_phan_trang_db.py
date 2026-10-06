"""Danh sách bệnh nhân phân trang + tìm phía máy chủ (06/10/2026).

Sáng 06/10 nạp ~8.600 hồ sơ cũ từ Notion. Màn cũ nạp hết về trình duyệt (trần
5.000) nên phải giấu hồ sơ cũ chưa hoạt động — chỉ còn 145 hồ sơ. Canh ở đây:
  * MỌI hồ sơ vào danh sách, kể cả ``nguon_nhap='notion'`` chưa hoạt động;
  * trang 2 khác trang 1, không lặp / sót, tổng đúng;
  * tìm tên KHÔNG DẤU, mã, MỘT PHẦN số điện thoại;
  * số ở tab / ô tổng đếm trên TOÀN BỘ hồ sơ, không theo ô tìm / tab / trang;
  * tham số rác (``trang=abc``, ``trang=-1``) → mặc định, không 500.

DB test dùng chung, các test khác ghi song song vào cùng phòng khám: mọi phép
so số đếm toàn bộ chạy trong MỘT ảnh chụp (REPEATABLE READ) để không chập chờn.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.services.danh_sach_benh_nhan_service import (
    MOT_TRANG,
    DanhSachBenhNhanService,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _khach(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    ten: str,
    *,
    sdt: str | None = None,
    notion: bool = False,
) -> str:
    return str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary, nguon_nhap)"
            " VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"DSBN-{uuid.uuid4().hex[:8]}",
            ten,
            ca.loc,
            sdt,
            "notion" if notion else None,
        )
    )


async def _luot_da_xong(pool: asyncpg.Pool, ca: Ca, pid: str, ngay_truoc: int) -> None:  # noqa: F811
    bd = datetime.now(UTC) - timedelta(days=ngay_truoc)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'COMPLETED')",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        bd,
        bd + timedelta(minutes=15),
    )


def _sdt() -> str:
    return "09" + "".join(random.choice("0123456789") for _ in range(8))


def _ma(out: dict[str, Any]) -> list[str]:
    return [d["ho_so"]["clinic_patient_id"] for d in out["dong"]]


async def test_phan_trang_trang_hai_khac_trang_mot_tong_dung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    so = MOT_TRANG + 7
    cua_toi = {await _khach(pool, ca, f"Phạm Trang {duoi} {i:02d}") for i in range(so)}
    svc = DanhSachBenhNhanService(pool)

    t1 = await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}")
    t2 = await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}", trang="2")
    assert (t1["so_khop"], t1["so_trang"], t1["mot_trang"]) == (so, 2, MOT_TRANG)
    assert (t1["trang"], t2["trang"]) == (1, 2)
    assert len(t1["dong"]) == MOT_TRANG and len(t2["dong"]) == 7
    # Không lặp, không sót.
    assert not set(_ma(t1)) & set(_ma(t2))
    assert set(_ma(t1)) | set(_ma(t2)) == cua_toi

    # "Xa nhất trước" = đảo ĐÚNG thứ tự "gần nhất trước" trên toàn tập.
    x1 = await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}", sap="xa")
    x2 = await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}", sap="xa", trang=2)
    assert _ma(x1) + _ma(x2) == list(reversed(_ma(t1) + _ma(t2)))

    # Trang vượt quá → trang cuối; trang rác → trang 1, không ném.
    assert (await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}", trang="99"))[
        "trang"
    ] == 2
    for rac in ("abc", "-1", "0", "", None):
        out = await svc.lay(identity=ca.le_tan, q=f"pham trang {duoi}", trang=rac)
        assert out["trang"] == 1 and _ma(out) == _ma(t1)


async def test_tim_khong_dau_ma_va_mot_phan_so_dien_thoai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    sdt = _sdt()
    dao = await _khach(pool, ca, f"Nguyễn Thị Đào {duoi}", sdt=sdt)
    await _khach(pool, ca, f"Trần Văn Khác {duoi}", sdt=_sdt())
    svc = DanhSachBenhNhanService(pool)

    async def tim(q: str) -> list[str]:
        return _ma(await svc.lay(identity=ca.le_tan, q=q))

    assert await tim(f"nguyen thi dao {duoi}") == [dao]  # không dấu, đ → d
    assert await tim(f"Nguyễn Thị Đào {duoi}") == [dao]  # gõ có dấu
    assert dao in await tim(sdt[2:8])  # một phần số
    spaced = f"{sdt[:4]} {sdt[4:7]}.{sdt[7:]}"  # "0912 345.678"
    assert dao in await tim(spaced)
    ma = await pool.fetchval(
        "SELECT patient_code FROM patient WHERE clinic_patient_id = $1::uuid", dao
    )
    assert await tim(ma.lower()) == [dao]
    assert await tim(f"khong ai ten nay {duoi}") == []


async def test_ho_so_notion_chua_hoat_dong_co_trong_danh_sach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    cu = await _khach(pool, ca, f"Hồ Sơ Cũ {duoi}", notion=True)
    out = await DanhSachBenhNhanService(pool).lay(
        identity=ca.le_tan, q=f"ho so cu {duoi}"
    )
    assert _ma(out) == [cu]
    assert out["dong"][0]["phan_loai"] == "Chưa khám"

    # Mở thẳng bằng ``chon`` khi khách KHÔNG ở trang đang xem (ô tìm khác).
    ngoai = await DanhSachBenhNhanService(pool).lay(
        identity=ca.le_tan, q=f"khong khop {duoi}", chon=cu
    )
    assert ngoai["dong"] == []
    assert ngoai["chon"]["ho_so"]["clinic_patient_id"] == cu
    assert ngoai["chon"]["phan_loai"] == "Chưa khám"
    # Đã ở trong trang → không trả lặp ở ``chon``.
    trong = await DanhSachBenhNhanService(pool).lay(
        identity=ca.le_tan, q=f"ho so cu {duoi}", chon=cu
    )
    assert trong["chon"] is None and _ma(trong) == [cu]


async def test_loc_theo_tab_va_so_dem_tinh_tren_toan_bo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    duoi = uuid.uuid4().hex[:8]
    chua = await _khach(pool, ca, f"Đếm Tab {duoi} Chưa", notion=True)
    dau = await _khach(pool, ca, f"Đếm Tab {duoi} Đầu")
    await _luot_da_xong(pool, ca, dau, 3)
    tai = await _khach(pool, ca, f"Đếm Tab {duoi} Tái")
    await _luot_da_xong(pool, ca, tai, 40)
    await _luot_da_xong(pool, ca, tai, 2)
    svc = DanhSachBenhNhanService(pool)
    q = f"dem tab {duoi}"

    assert set(_ma(await svc.lay(identity=ca.le_tan, q=q))) == {chua, dau, tai}
    assert _ma(await svc.lay(identity=ca.le_tan, q=q, loc="chua-kham")) == [chua]
    assert _ma(await svc.lay(identity=ca.le_tan, q=q, loc="lan-dau")) == [dau]
    tk = await svc.lay(identity=ca.le_tan, q=q, loc="tai-kham")
    assert _ma(tk) == [tai]
    assert tk["dong"][0]["so_luot"] == 2 and tk["dong"][0]["phan_loai"] == "Tái khám"
    # Tab rác → tất cả.
    assert len(_ma(await svc.lay(identity=ca.le_tan, q=q, loc="rác"))) == 3

    # Số đếm toàn bộ: so với đếm độc lập bằng SQL trong CÙNG một ảnh chụp, và
    # không đổi theo ô tìm / tab / trang.
    async with pool.acquire() as conn, conn.transaction(isolation="repeatable_read"):
        mot = _MotKetNoi(conn)
        a = await DanhSachBenhNhanService(mot).lay(identity=ca.le_tan)
        b = await DanhSachBenhNhanService(mot).lay(
            identity=ca.le_tan, q=q, loc="lan-dau", trang="3"
        )
        doc_lap = await conn.fetchrow(
            """
            WITH n AS (
                SELECT p.clinic_patient_id,
                       (SELECT count(*) FROM appointment x
                         WHERE x.clinic_id = p.clinic_id
                           AND x.clinic_patient_id = p.clinic_patient_id
                           AND x.status IN ('CHECKED_IN', 'COMPLETED')) AS so,
                       EXISTS (SELECT 1 FROM appointment x
                                LEFT JOIN visit v ON v.appointment_id = x.id
                               WHERE x.clinic_id = p.clinic_id
                                 AND x.clinic_patient_id = p.clinic_patient_id
                                 AND x.status = 'CHECKED_IN'
                                 AND v.closed_at IS NULL) AS mo
                  FROM patient p WHERE p.clinic_id = $1::uuid)
            SELECT count(*) AS ho_so,
                   count(*) FILTER (WHERE mo) AS dang_mo,
                   count(*) FILTER (WHERE so = 1) AS lan_dau,
                   count(*) FILTER (WHERE so >= 2) AS tai_kham,
                   count(*) FILTER (WHERE so = 0) AS chua_kham
              FROM n
            """,
            CLINIC,
        )
    assert a["tong"] == dict(doc_lap)
    assert b["tong"] == a["tong"]
    assert a["so_khop"] == a["tong"]["ho_so"]
    assert b["so_khop"] == 1 and b["trang"] == 1


class _MotKetNoi:
    """Bọc MỘT kết nối thành thứ trông như pool — để service chạy trong giao
    dịch REPEATABLE READ của test (một ảnh chụp cho mọi câu)."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        yield self._conn

    async def fetch(self, *a: Any) -> Any:
        return await self._conn.fetch(*a)

    async def fetchrow(self, *a: Any) -> Any:
        return await self._conn.fetchrow(*a)

    async def fetchval(self, *a: Any) -> Any:
        return await self._conn.fetchval(*a)
