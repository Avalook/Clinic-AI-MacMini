"""Khách đã trả tiền chờ vào phòng (Tuyền 24/09/2026).

* "Thanh toán xong vẫn chỉ định [phòng] được bình thường" → bảng thu ngân
  trả `xep_phong` (đã trả, chưa bắt đầu, kèm phòng hiện tại).
* "Kể cả lễ tân không chỉ định thì khách vẫn xuất hiện ở hàng đợi và có thể
  khám ở các dịch vụ khả thi" → hàng chờ của MỌI phòng làm được (cùng cơ sở)
  có `chua_xep_phong`; phòng bấm nhận bằng lệnh xếp phòng thường.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.services import nhan_tai_phong as ntp
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.service_routing_service import (
    ServiceRoutingService,
    cho_nhan_vao_phong,
    da_tra_cho_vao_phong,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_ngay_kham_lo_hong_db import _co_so_khac
from tests.services.test_nhan_tai_phong_db import _dat_day, _tra_day
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _phong,
    _thu,
    _thu_khoi_dieu_phoi,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_khong_ai_xep_phong_thi_moi_phong_lam_duoc_deu_thay_va_nhan_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _thu_khoi_dieu_phoi(pool, ca.thu_ngan)  # H4 không xếp thay được
    # V10: người CHỐT (lễ tân) cũng không có quyền xếp — để xét đúng đường thu.
    await _thu_khoi_dieu_phoi(pool, ca.le_tan)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        phong_2 = await _phong(conn, ca.loc, uuid.uuid4().hex[:6])
        # Chưa trả tiền → chưa hiện ở phòng nào.
        assert order not in {
            k["id"] for k in await cho_nhan_vao_phong(conn, CLINIC, ca.phong)
        }
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"

    khac = await _co_so_khac(pool, ca.loc)
    async with pool.acquire() as conn:
        phong_co_so_khac = await _phong(conn, khac, uuid.uuid4().hex[:6])
        for rid in (ca.phong, phong_2):
            ds = await cho_nhan_vao_phong(conn, CLINIC, rid)
            assert order in {k["id"] for k in ds}, "phòng làm được phải thấy khách"
        # Khác cơ sở thì không (luật cơ sở giữ nguyên).
        assert order not in {
            k["id"] for k in await cho_nhan_vao_phong(conn, CLINIC, phong_co_so_khac)
        }
        [k] = [
            k
            for k in await cho_nhan_vao_phong(conn, CLINIC, phong_2)
            if k["id"] == order
        ]

    # Phòng 2 bấm nhận — người đứng phòng có khối Điều phối (điều dưỡng).
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=phong_2,
        expected_routing_revision=k["routing_revision"],
        reason_code="INITIAL_ASSIGNMENT",
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    d = await _don(pool, order)
    assert (d["routing_status"], d["room_id"]) == ("ASSIGNED", phong_2)
    assert await pool.fetchval(
        "SELECT count(*) FROM queue_entry WHERE ref_id = $1::uuid"
        " AND reason = 'SERVICE' AND room_id = $2::uuid"
        " AND status IN ('waiting', 'blocked')",
        order,
        phong_2,
    )
    async with pool.acquire() as conn:
        for rid in (ca.phong, phong_2):
            assert order not in {
                k["id"] for k in await cho_nhan_vao_phong(conn, CLINIC, rid)
            }


async def test_quay_thu_con_xep_doi_phong_sau_khi_thu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        assert visit not in await da_tra_cho_vao_phong(conn, CLINIC, [visit])
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"

    b = await CashierBoardService(pool).board(identity=ca.le_tan, modes=["dich_vu"])
    [item] = [i for i in b["items"] if i["visit_id"] == visit]
    [x] = item["xep_phong"]
    assert (x["id"], x["room_id"]) == (order, d["room_id"])

    async with pool.acquire() as conn:
        khac = await _phong(conn, ca.loc, uuid.uuid4().hex[:6])
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=khac,
        expected_routing_revision=x["routing_revision"],
        reason_code="LOAD_BALANCE",
        identity=ca.le_tan,
        idempotency_key=_khoa(),
    )
    async with pool.acquire() as conn:
        [x] = (await da_tra_cho_vao_phong(conn, CLINIC, [visit]))[visit]
    assert x["room_id"] == khac

    # Phòng đã gọi khách vào → không còn trong danh sách đổi phòng.
    await pool.execute(
        "UPDATE queue_entry SET status = 'called', called_at = now(),"
        " eligible_at = coalesce(eligible_at, now())"
        " WHERE ref_id = $1::uuid AND reason = 'SERVICE'"
        " AND status IN ('waiting', 'blocked')",
        order,
    )
    async with pool.acquire() as conn:
        assert visit not in await da_tra_cho_vao_phong(conn, CLINIC, [visit])


async def test_luot_ngay_cu_khong_hien_cho_vao_phong_o_quay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """ "Hôm nào xong hôm đó" (Tuyền 29/10/2026, "ẩn luôn"): chỉ định ngày cũ đã
    thu mà chưa làm không còn ở khối "Đã thu — chờ vào phòng" của quầy — nó ở
    khung chỉ định cũ của bàn khám. Staging 29/10: khối ấy có 78 lượt khách đã
    về từ những ngày trước."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    svc = CashierBoardService(pool)

    async def xep_phong() -> list[dict[str, object]] | None:
        b = await svc.board(identity=ca.le_tan, modes=["dich_vu"])
        dong = [i for i in b["items"] if i["visit_id"] == visit]
        return dong[0]["xep_phong"] if dong else None

    assert [x["id"] for x in (await xep_phong() or [])] == [order], "hôm nay: còn"
    # Lùi lượt về hôm qua (khách chưa về — vẫn là ứng viên của bảng hôm nay).
    await pool.execute(
        "UPDATE visit SET created_at = created_at - interval '1 day'"
        " WHERE visit_id = $1::uuid",
        visit,
    )
    assert not await xep_phong(), "ngày cũ: không còn ô xếp phòng ở quầy"


async def test_day_nhan_tai_phong_bat_quay_khong_con_o_chon_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 29/10/2026: "khách tự đến, tự hiện ở Sắp đến tất cả các phòng rồi
    mà sao lại cho cái chọn phòng ra đây" — dây Nhận tại phòng BẬT thì quầy thu
    không còn ô chọn / hướng dẫn phòng (trước và sau khi thu); phòng vẫn thấy
    khách ở Sắp đến và tự Nhận."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    svc = CashierBoardService(pool)

    async def dong() -> dict[str, object]:
        b = await svc.board(identity=ca.le_tan, modes=["dich_vu"])
        [i] = [i for i in b["items"] if i["visit_id"] == visit]
        return i

    truoc = await dong()
    assert any(
        c.get("phong_chon_duoc") for c in (truoc["chon_dich_vu"] or {})["chi_dinh"]
    ), "dây TẮT: quầy còn ô chọn phòng"
    cu = await _dat_day(pool, "nhan_tai_phong", True)
    try:
        moi = await dong()
        assert not any(
            c.get("phong_chon_duoc") for c in (moi["chon_dich_vu"] or {})["chi_dinh"]
        ), "trước thu: hết ô hướng dẫn phòng"
        await _chon(pool, ca, visit, [order])
        await _thu(pool, visit, ca.le_tan)
        await chay_hanh_trinh(pool)
        assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
        assert not (await dong())["xep_phong"], "sau thu: hết khối chờ vào phòng"
        async with pool.acquire() as conn:
            ds = await ntp.sap_den(conn, CLINIC, ca.phong)
        assert visit in {k["visit_id"] for k in ds}, "phòng vẫn thấy ở Sắp đến"
    finally:
        await _tra_day(pool, "nhan_tai_phong", cu)
