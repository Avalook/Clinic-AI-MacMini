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
from typing import Any

import asyncpg
import pytest

import clinicai.services.doi_tac_service as doi_tac_mod
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


async def test_hai_nguoi_ghi_thu_cung_luc_mot_nguoi_thua(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    a = await _nguoi_vai(q, "PARTNER")
    b = await _nguoi_vai(q, "PARTNER")
    svc = DoiTacService(pool)

    # ÉP CHEN NHAU: người đầu đứng lại 0,3s TRONG giao dịch, ngay sau INSERT (lúc phát
    # sự kiện) — người sau chạy vào đúng khe ấy. Không ép thì người đầu thường xong
    # trước khi người sau đọc, bài xanh mà chẳng đo gì (thử ngược 05/11 đã thấy thế).
    goc = doi_tac_mod.emit_event
    da_cho = False

    async def emit_cham(*args: Any, **kwargs: Any) -> Any:
        nonlocal da_cho
        if not da_cho:
            da_cho = True
            await asyncio.sleep(0.3)
        return await goc(*args, **kwargs)

    monkeypatch.setattr(doi_tac_mod, "emit_event", emit_cham)

    # Hai số khác nhau: bấm lại CÙNG số là "đã có" (chạy lại được), không phải thua.
    kq = await asyncio.gather(
        svc.ghi_nhan_da_thu(
            order_id=oid, identity=a, so_tien=900_000, hinh_thuc="CASH"
        ),
        svc.ghi_nhan_da_thu(
            order_id=oid, identity=b, so_tien=800_000, hinh_thuc="CASH"
        ),
        return_exceptions=True,
    )

    thang = [r for r in kq if isinstance(r, dict)]
    thua = [r for r in kq if isinstance(r, BaseException)]
    assert len(thang) == 1 and thang[0]["already"] is False
    assert len(thua) == 1
    # 409 kèm câu tiếng Việt — không để UniqueViolationError thô lọt ra thành 500.
    assert isinstance(thua[0], ConflictError), repr(thua[0])
    assert await _so_ghi_nhan(pool, oid) == 1
