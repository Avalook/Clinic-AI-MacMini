"""Ẩn khoản TỒN của cơ sở ĐÃ NGỪNG hoạt động (Tuyền 14/10/2026) — DB thật.

    scripts/test-nhanh.sh src/tests/services/test_an_ton_co_so_ngung_db.py

"Kim Ngưu không còn hoạt động": chế độ "Tất cả cơ sở" không được đếm nợ / CK chờ /
tiền thừa của cơ sở ngừng vào Việc còn tồn, Khách còn nợ, hàng chờ quầy thu —
nhưng CHỈ ẩn khỏi màn tồn đọng: sổ nợ và hoá đơn không đổi, và người dùng chủ
động chọn đúng cơ sở ngừng thì vẫn thấy đủ. "Ngừng" theo DỮ LIỆU
(`clinic_location.is_active = false`), không theo tên.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.clock import now_vn
from clinicai.events.catalogue import CONG_NO, SO_NO
from clinicai.services.bao_cao_viec_tien_service import doc_viec_tien
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.co_so_bao_cao import doc_co_so_ngung
from clinicai.services.cong_no_service import CongNoService, doc_khach_con_no
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.so_no_service import PHAI_THU, doc_so_du_mo
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    _lam_truoc_thu_sau,
    _lam_xong,
    _luot,
    _thu,
    _ve,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung
from tests.services.test_viec_ton_noi_man_db import _lui_luot

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclass
class HaiCoSo:
    ca: Ca
    chay: str  # lượt của cơ sở đang chạy
    ngung: str  # lượt của cơ sở ngừng
    loc_ngung: str
    ten_ngung: str


async def _chuyen(pool: asyncpg.Pool, visit: str, loc: str) -> None:  # noqa: F811
    await pool.execute(
        "UPDATE appointment SET location_id = $2::uuid WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        visit,
        loc,
    )
    await pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        visit,
        loc,
    )


async def _dung_hai(pool: asyncpg.Pool, *, no: bool) -> HaiCoSo:  # noqa: F811
    """Hai lượt ĐÃ VỀ còn khoản tồn (nợ ghi tay hoặc CK chưa về), lùi 3 ngày để
    chỉ lọt hàng chờ quầy bằng nhánh việc tồn (không bằng nhánh "trong ngày");
    lượt thứ hai chuyển sang một cơ sở ĐÃ NGỪNG (cơ sở mới, tên riêng)."""
    ca = await _dung(pool)
    luot_ds: list[str] = []
    for _ in range(2):
        v, o = await _luot(pool, ca)
        if no:
            await _lam_xong(pool, ca, o)
            await CongNoService(pool).ghi(
                identity=ca.le_tan, visit_id=v, ly_do="Quên ví"
            )
        else:
            await _thu(pool, ca, v, method="TRANSFER")
            await _lam_xong(pool, ca, o)
        await _ve(pool, ca, v)
        luot_ds.append(v)
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    ten = f"Cơ sở ngừng {uuid.uuid4().hex[:6]}"
    loc = str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, $3, false) RETURNING id::text",
            CLINIC,
            f"NG{uuid.uuid4().hex[:6]}",
            ten,
        )
    )
    await _chuyen(pool, luot_ds[1], loc)
    for v in luot_ds:
        await _lui_luot(pool, v, 3)
    return HaiCoSo(ca, luot_ds[0], luot_ds[1], loc, ten)


def _quan_ly(h: HaiCoSo, loc: str) -> object:
    return dataclasses.replace(
        h.ca.thu_ngan, role=ClinicRole.MANAGEMENT, location_id=loc
    )


async def _ton_hoa_don(
    pool: asyncpg.Pool,  # noqa: F811
    h: HaiCoSo,
    co_so: str | None,
) -> dict[str, object]:
    ngay = now_vn().date().isoformat()
    return await DanhSachHoaDonService(pool).xem(
        identity=_quan_ly(h, ""),  # type: ignore[arg-type]
        tu=ngay,
        den=ngay,
        co_so=co_so,
    )


async def test_viec_ton_tat_ca_khong_dem_co_so_ngung_chon_dung_thi_thay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _dung_hai(pool, no=True)
    tat_ca = await _ton_hoa_don(pool, h, None)
    luot = {t["visit_id"] for t in tat_ca["viec_ton"]}  # type: ignore[attr-defined]
    assert h.chay in luot, "cơ sở đang chạy vẫn đếm"
    assert h.ngung not in luot, "cơ sở ngừng KHÔNG đếm khi không chọn cơ sở"
    assert {"id": h.loc_ngung, "ten": h.ten_ngung} in tat_ca["co_so_ngung"]  # type: ignore[operator]
    # Số đếm trên màn = đúng số dòng đang hiện (không lệch).
    assert tat_ca["tong"]["so_viec_ton"] == len(tat_ca["viec_ton"])  # type: ignore[index,arg-type]

    # Chủ động chọn đúng cơ sở ngừng → thấy đủ khoản cũ, không còn dòng "không tính".
    rieng = await _ton_hoa_don(pool, h, h.loc_ngung)
    assert {t["visit_id"] for t in rieng["viec_ton"]} == {h.ngung}  # type: ignore[attr-defined]
    assert rieng["co_so_ngung"] == []

    # Chọn cơ sở đang chạy → chỉ cơ sở ấy.
    chay = await _ton_hoa_don(pool, h, h.ca.loc)
    ds = {t["visit_id"] for t in chay["viec_ton"]}  # type: ignore[attr-defined]
    assert h.chay in ds and h.ngung not in ds


async def test_khach_con_no_va_can_xu_ly_bo_co_so_ngung_so_no_khong_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _dung_hai(pool, no=True)
    async with pool.acquire() as conn:
        tat_ca = {r["visit_id"] for r in await doc_so_du_mo(conn, CLINIC, PHAI_THU)}
        assert h.chay in tat_ca and h.ngung not in tat_ca
        # SỔ không đổi: đọc không bỏ cơ sở ngừng vẫn còn nguyên khoản nợ.
        day_du = {
            r["visit_id"]
            for r in await doc_so_du_mo(conn, CLINIC, PHAI_THU, bo_co_so_ngung=False)
        }
        assert {h.chay, h.ngung} <= day_du
        so_dong = await conn.fetchval(
            "SELECT count(*) FROM so_no WHERE visit_id = $1::uuid", h.ngung
        )
        assert so_dong >= 1

        rieng = await doc_khach_con_no(conn, CLINIC, location_id=h.loc_ngung)
        assert rieng["so_luot"] == 1
        assert [d["visit_id"] for d in rieng["ds"]] == [h.ngung]
        # Chọn cơ sở đang chạy: không lẫn khoản của cơ sở ngừng.
        chay = await doc_khach_con_no(conn, CLINIC, location_id=h.ca.loc)
        assert h.ngung not in {d["visit_id"] for d in chay["ds"]}

        # "Tất cả" không cộng khoản của cơ sở ngừng: tổng = tổng sổ (đọc đủ) − phần
        # của cơ sở ngừng.
        tong = await doc_khach_con_no(conn, CLINIC, kem_ds=False)
        day_du_tien = sum(
            r["so_du"]
            for r in await doc_so_du_mo(conn, CLINIC, PHAI_THU, bo_co_so_ngung=False)
        )
        assert rieng["so_tien"] > 0
        assert tong["so_tien"] <= day_du_tien - rieng["so_tien"]

        vt = await doc_viec_tien(conn, CLINIC, co_so=None, loai=None)
        assert h.ngung not in {d["visit_id"] for d in vt["khach_con_no"].get("ds", [])}
        vt_ngung = await doc_viec_tien(conn, CLINIC, co_so=h.loc_ngung, loai=None)
        assert vt_ngung["khach_con_no"]["so_luot"] == 1

        assert [c["id"] for c in await doc_co_so_ngung(conn, CLINIC)].count(
            h.loc_ngung
        ) == 1


async def test_hang_cho_quay_thu_tat_ca_bo_luot_cu_cua_co_so_ngung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _dung_hai(pool, no=False)  # CK chờ xác minh, lượt cũ
    svc = CashierBoardService(pool)

    async def thay(loc: str) -> set[str]:
        bang = await svc.board(
            identity=dataclasses.replace(h.ca.thu_ngan, location_id=loc),
            modes=["dich_vu", "thuoc"],
        )
        return {i["visit_id"] for i in bang["items"]}

    tat_ca = await thay("")
    assert h.chay in tat_ca, "cơ sở đang chạy: lượt cũ còn CK chờ vẫn lên quầy"
    assert h.ngung not in tat_ca, "không chọn cơ sở: bỏ lượt cũ của cơ sở ngừng"
    # Đứng đúng cơ sở ngừng (chủ động chọn) → vẫn thấy khoản cũ để xử lý.
    assert h.ngung in await thay(h.loc_ngung)
    assert h.chay not in await thay(h.loc_ngung)
    # Cơ sở đang chạy không đổi.
    assert h.chay in await thay(h.ca.loc)


async def test_co_so_hoat_dong_lai_thi_khoan_hien_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Cờ là DỮ LIỆU: bật lại cơ sở thì khoản hiện lại, không cần đụng sổ."""
    h = await _dung_hai(pool, no=True)
    await pool.execute(
        "UPDATE clinic_location SET is_active = true WHERE id = $1::uuid",
        h.loc_ngung,
    )
    ds = {t["visit_id"] for t in (await _ton_hoa_don(pool, h, None))["viec_ton"]}  # type: ignore[attr-defined]
    assert {h.chay, h.ngung} <= ds
