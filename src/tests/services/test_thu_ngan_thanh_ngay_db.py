"""Thanh ngày ở Thu ngân dịch vụ / thuốc (02/10/2026) — máy chủ quyết ngày.

Tuyền: "thanh ngày giờ như các màn khác, để nhân viên xem lại một ngày cũ đối
soát". Bảng thu nhận `ngay` (YYYY-MM-DD giờ VN); rác → hôm nay, KHÔNG ném. Ngày
cũ: chỉ khách của ngày ấy, và vẫn thu được (không khoá).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services.cashier_board_service import (
    _SQL,
    CashierBoardService,
    khoang_ngay_xem,
)
from tests.services.test_quay_thu_mot_hoa_don_db import _kich_ban

# ── Luật thuần: ngày rác không bao giờ ném ─────────────────────────────────


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "",
        "   ",
        "rác",
        "2026-13-45",
        "2026-02-30",
        "20260929",
        "2019-12-31",
        "2026-09-2",
        "';DROP TABLE x;--",
        123,
        4.5,
        [],
        {},
        True,
        "2026/09/28",
    ],
)
def test_ngay_rac_thanh_hom_nay_khong_nem(rac: object) -> None:
    ngay, dau, cuoi = khoang_ngay_xem(rac)
    hom_nay = hom_nay_vn()
    assert ngay == hom_nay
    assert dau == datetime(hom_nay.year, hom_nay.month, hom_nay.day, tzinfo=CLINIC_TZ)
    assert cuoi - dau == timedelta(days=1)


def test_ngay_hop_le_cat_theo_gio_viet_nam() -> None:
    ngay, dau, cuoi = khoang_ngay_xem("2026-09-28")
    assert ngay == date(2026, 9, 28)
    assert dau.isoformat() == "2026-09-28T00:00:00+07:00"
    assert cuoi.isoformat() == "2026-09-29T00:00:00+07:00"


# ── Bảng thu theo ngày (DB thật) ───────────────────────────────────────────

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_bang_thu_theo_ngay_va_rac_la_hom_nay(pool: asyncpg.Pool) -> None:
    q, _sa, _soi, _hpv = await _kich_ban(pool)
    svc = CashierBoardService(pool)
    hom_nay = hom_nay_vn()
    hom_qua = hom_nay - timedelta(days=1)

    async def co_luot(ngay: object) -> dict[str, object]:
        b = await svc.board(identity=q.thu_ngan, modes=["dich_vu"], ngay=ngay)
        return {
            "co": any(i["visit_id"] == q.visit_id for i in b["items"]),
            "ngay": b["ngay"],
        }

    # Hôm nay (mặc định) và rác → cùng một bảng hôm nay, có khách vừa dựng.
    for ngay in (None, hom_nay.isoformat(), "rác", "2026-13-45", 7):
        kq = await co_luot(ngay)
        assert kq == {"co": True, "ngay": hom_nay.isoformat()}, ngay
    # Hôm qua: khách vừa dựng KHÔNG ở đó.
    assert await co_luot(hom_qua.isoformat()) == {
        "co": False,
        "ngay": hom_qua.isoformat(),
    }
    # Lùi lượt về một ngày XA, ngẫu nhiên và vắng khách (DB dùng chung đầy lượt
    # thử) → hiện ở bảng ngày ấy,
    # hết ở hôm nay, VẪN có dòng để thu (không khoá ngày cũ).
    xa = date(2021, 1, 1) + timedelta(days=uuid.uuid4().int % 365)
    await pool.execute(
        "UPDATE visit SET created_at = $2::timestamptz WHERE visit_id = $1::uuid",
        q.visit_id,
        datetime(xa.year, xa.month, xa.day, 10, tzinfo=CLINIC_TZ),
    )
    b = await svc.board(identity=q.thu_ngan, modes=["dich_vu"], ngay=xa.isoformat())
    dong = next(i for i in b["items"] if i["visit_id"] == q.visit_id)
    assert dong["hoa_don"]["dich_vu"]["dong"], "ngày cũ vẫn phải có dòng để thu"
    assert b["ngay"] == xa.isoformat() and b["hom_nay"] == hom_nay.isoformat()
    assert b["dem"]["da_thu_hom_nay"] >= 0
    # Khách tồn chưa trả tiếp tục hiện cho quầy hiện tại, kể cả chưa ghi nợ.
    assert (await co_luot(None))["co"] is True


@pytest.mark.db
@pytest.mark.asyncio
async def test_luot_ngay_cu_con_no_hien_hom_nay_khong_hien_ngay_khac(
    pool: asyncpg.Pool,
) -> None:
    """Khách tồn còn nợ/chỉ định chưa thu hiện ở quầy hiện tại.

    Xem lại một ngày cũ khác không kéo khách tồn sang ngày ấy.
    """
    q, _sa, _soi, _hpv = await _kich_ban(pool)
    svc = CashierBoardService(pool)
    xa = date(2021, 1, 1) + timedelta(days=uuid.uuid4().int % 365)
    khac = xa + timedelta(days=1)
    await pool.execute(
        "UPDATE visit SET created_at = $2::timestamptz WHERE visit_id = $1::uuid",
        q.visit_id,
        datetime(xa.year, xa.month, xa.day, 10, tzinfo=CLINIC_TZ),
    )

    async def co(ngay: object) -> bool:
        b = await svc.board(identity=q.thu_ngan, modes=["dich_vu"], ngay=ngay)
        return any(i["visit_id"] == q.visit_id for i in b["items"])

    assert await co(None) is True, "khách tồn chưa thu không mất khi đổi ngày/ca"
    no_id = await pool.fetchval(
        """
        INSERT INTO cong_no (clinic_id, visit_id, clinic_patient_id, so_tien,
                             ly_do, ghi_boi)
        SELECT clinic_id, visit_id, clinic_patient_id, 100000, 'khách hẹn trả sau', $2
          FROM visit WHERE visit_id = $1::uuid
        RETURNING id
        """,
        q.visit_id,
        q.thu_ngan.staff_id,
    )
    assert await co(None) is True, "còn nợ → lên quầy hôm nay"
    assert await co(xa.isoformat()) is True, "ngày của chính lượt vẫn thấy"
    assert await co(khac.isoformat()) is False, "ngày cũ khác: nợ không kéo sang"

    await pool.execute(
        "UPDATE cong_no SET trang_thai = 'DA_THU', thu_luc = now() WHERE id = $1",
        no_id,
    )
    # Đóng dòng công nợ không tự thanh toán các chỉ định còn chưa thu.
    assert await co(None) is True, "còn chỉ định chưa thu → vẫn ở quầy hôm nay"


@pytest.mark.db
@pytest.mark.asyncio
async def test_more_than_300_candidates_keep_old_unpaid_and_day_candidates(
    pool: asyncpg.Pool,
) -> None:
    """Lượt mới không đẩy khách tồn chưa thu ra khỏi tập dựng hoá đơn."""
    q, _sa, _soi, _hpv = await _kich_ban(pool)
    _today, start, end = khoang_ngay_xem(None)
    yesterday = start - timedelta(days=1)
    await pool.execute(
        "UPDATE visit SET created_at=$2 WHERE visit_id=$1::uuid",
        q.visit_id,
        yesterday,
    )
    async with pool.acquire() as conn:
        transaction = conn.transaction()
        await transaction.start()
        newer = await conn.fetch(
            "INSERT INTO visit(clinic_id,clinic_patient_id,location_id,created_at,"
            " exam_completed_at) SELECT clinic_id,clinic_patient_id,location_id,$2,$2"
            " FROM visit CROSS JOIN generate_series(1,301)"
            " WHERE visit_id=$1::uuid RETURNING visit_id::text",
            q.visit_id,
            start + timedelta(hours=10),
        )
        try:
            value = await conn.fetchval(
                _SQL,
                q.thu_ngan.clinic_id,
                start,
                end,
                True,
                q.thu_ngan.location_id or None,
            )
            raw = json.loads(value) if isinstance(value, str) else value
            visits = {v["visit_id"] for v in raw["visits"]}
            assert q.visit_id in visits, "khách tồn chưa thu phải được dựng hoá đơn"
            assert {r["visit_id"] for r in newer} <= visits
            value = await conn.fetchval(
                _SQL,
                q.thu_ngan.clinic_id,
                start,
                end,
                False,
                q.thu_ngan.location_id or None,
            )
            selected_day = json.loads(value) if isinstance(value, str) else value
            assert q.visit_id not in {v["visit_id"] for v in selected_day["visits"]}
        finally:
            await transaction.rollback()
