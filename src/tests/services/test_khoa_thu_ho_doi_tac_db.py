"""Khoá hành vi ĐANG ĐÚNG của sổ thu hộ đối tác trước khi đụng (ADR-0015, kế hoạch
chặng 0, PR 0.3). Hai bài này phải xanh suốt các chặng 1–4; đỏ thì sửa code, KHÔNG
sửa kỳ vọng.

(1) Ghi thu hộ chỉ vào `doi_tac_thanh_toan` — không một dòng nào ở `payment_cycle`,
    `payment`, `payment_bill_line`, `payment_refund` của lượt; số phòng khám còn phải
    thu (`hoa_don_con_no`) không đổi.
(3) Hai người ghi thu cùng một việc cùng lúc ⇒ đúng một người thắng, người kia nhận
    lỗi nghiệp vụ dễ hiểu (409), không phải lỗi unique thô (500).
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.doi_tac_service import DoiTacService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai, _viec_da_nhan
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

#: Mọi bảng tiền của phòng khám có cột visit_id — thêm bảng tiền mới thì thêm vào đây.
BANG_TIEN_PHONG_KHAM = (
    "payment_cycle",
    "payment",
    "payment_bill_line",
    "payment_refund",
)


async def _dem_tien_luot(pool: asyncpg.Pool, visit_id: str) -> dict[str, int]:
    """Số dòng mỗi bảng tiền phòng khám của MỘT lượt (DB dùng chung, test song song)."""
    return {
        bang: await pool.fetchval(
            f"SELECT count(*) FROM {bang}"  # noqa: S608 — tên bảng từ hằng ở trên
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            CLINIC,
            visit_id,
        )
        for bang in BANG_TIEN_PHONG_KHAM
    }


async def _con_no(pool: asyncpg.Pool, visit_id: str) -> tuple[int, str, list[str]]:
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit_id)
    return hd.tong, hd.revision, hd.van_de


async def _so_ghi_nhan(pool: asyncpg.Pool, oid: str) -> int:
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM doi_tac_thanh_toan"
            " WHERE service_order_id = $1::uuid AND huy_luc IS NULL",
            oid,
        )
    )


async def test_ghi_thu_ho_khong_cham_tien_phong_kham(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    dt = await _nguoi_vai(q, "PARTNER")
    tien_truoc = await _dem_tien_luot(pool, q.visit_id)
    no_truoc = await _con_no(pool, q.visit_id)

    kq = await DoiTacService(pool).ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="TRANSFER"
    )

    assert kq["already"] is False
    assert await _so_ghi_nhan(pool, oid) == 1
    assert await _dem_tien_luot(pool, q.visit_id) == tien_truoc
    assert await _con_no(pool, q.visit_id) == no_truoc


async def _cho_bi_chan_boi(pool: asyncpg.Pool, pid: int) -> None:
    """Chờ tới khi có phiên đang bị phiên `pid` chặn — chờ ĐIỀU KIỆN trong Postgres
    (`pg_blocking_pids`), không đoán bằng thời gian."""
    for _ in range(500):
        if await pool.fetchval(
            "SELECT count(*) FROM pg_stat_activity"
            " WHERE $1::int = ANY(pg_blocking_pids(pid))",
            pid,
        ):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("người ghi thứ hai không hề chờ giao dịch 1 — bài không đo gì")


async def test_hai_nguoi_ghi_thu_cung_luc_mot_nguoi_thua(pool: asyncpg.Pool) -> None:
    """Giao dịch 1 ghi thu và CHƯA commit; người thứ hai bấm ghi thu cùng việc qua
    dịch vụ; rồi commit 1. Kiểm KẾT QUẢ:
      (a) chỉ một ghi nhận còn hiệu lực — ép ở DB bằng unique một phần
          `ux_doi_tac_thanh_toan_con_hieu_luc` (bất biến ép ở DB, SO-LUAT Phần 6);
      (b) người thứ hai nhận 409 kèm câu tiếng Việt, không phải lỗi unique thô (500).
    (b) hiện ĐÚNG nhờ `FOR UPDATE OF o` trong `ghi_nhan_da_thu`: người thứ hai chờ ở
    dòng chỉ định tới khi 1 commit, rồi đọc thấy ghi nhận của 1. Thử ngược 05/11: bỏ
    dòng khoá đó thì (a) vẫn đúng (index chặn) nhưng (b) ra UniqueViolationError — vì
    vậy bài này canh cả hai."""
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    a = await _nguoi_vai(q, "PARTNER")
    b = await _nguoi_vai(q, "PARTNER")

    conn1 = await pool.acquire()
    try:
        tx1 = conn1.transaction()
        await tx1.start()
        await conn1.execute(
            "INSERT INTO doi_tac_thanh_toan (clinic_id, service_order_id, so_tien,"
            " hinh_thuc, ghi_boi)"
            " VALUES ($1::uuid, $2::uuid, 900000, 'CASH', $3::uuid)",
            CLINIC,
            oid,
            a.staff_id,
        )
        nguoi_hai = asyncio.create_task(
            DoiTacService(pool).ghi_nhan_da_thu(
                order_id=oid, identity=b, so_tien=800_000, hinh_thuc="CASH"
            )
        )
        await _cho_bi_chan_boi(pool, conn1.get_server_pid())
        await tx1.commit()
    finally:
        await pool.release(conn1)
    loi: BaseException | None = None
    try:
        await nguoi_hai
    except Exception as e:  # noqa: BLE001 — bài kiểm chính LOẠI lỗi lọt ra
        loi = e

    assert await _so_ghi_nhan(pool, oid) == 1  # (a)
    assert isinstance(loi, ConflictError), repr(loi)  # (b) — 409, không 500
    assert getattr(loi, "error_code", None) == "PARTNER_PAYMENT_EXISTS"
    assert "huỷ ghi nhận cũ" in str(loi)  # câu tiếng Việt người đọc hiểu
