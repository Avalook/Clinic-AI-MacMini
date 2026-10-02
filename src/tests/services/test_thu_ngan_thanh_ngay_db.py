"""Thanh ngày ở Thu ngân dịch vụ / thuốc (02/10/2026) — máy chủ quyết ngày.

Tuyền: "thanh ngày giờ như các màn khác, để nhân viên xem lại một ngày cũ đối
soát". Bảng thu nhận `ngay` (YYYY-MM-DD giờ VN); rác → hôm nay, KHÔNG ném. Ngày
cũ: chỉ khách của ngày ấy, và vẫn thu được (không khoá).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services.cashier_board_service import CashierBoardService, khoang_ngay_xem
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
    # thử; bảng thu chỉ lấy 300 lượt mới nhất của ngày) → hiện ở bảng ngày ấy,
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
    assert (await co_luot(None))["co"] is False
