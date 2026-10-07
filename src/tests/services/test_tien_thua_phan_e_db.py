"""PHẦN E — luật tiền khi bỏ / hoàn tác chỉ định (Tuyền chốt 06/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_tien_thua_phan_e_db.py

E2a check-out còn tiền thừa: chặn, hai lối (hoàn đúng số / giữ lại + lý do,
hoàn tác được). E2b hoàn tiền theo lego. E5 hoàn tác sau khi đã hoàn = nợ mới.
E4 Postgres không cho thu dòng của chỉ định đã huỷ, kể cả tranh chấp.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ValidationError
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.hoan_tac_service import HoanTacService, tien_thua_cua_luot
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.so_sua_chi_dinh_service import SoSuaChiDinhService
from clinicai.services.tien_thua_service import TienThuaService, bao_cao_tien_thua
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_thu_dich_vu_nhieu_lan_db import _cd, _hd, _thu
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def q(pool: asyncpg.Pool) -> Quay:
    return await tao_quay(pool)


async def _da_thu_roi_bo(q: Quay, gia: int = 300_000) -> str:
    sa = await _cd(q, "SA", gia)
    await _thu(q)
    await HoanTacService(q.pool).huy_chi_dinh(
        order_id=sa, identity=q.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    return sa


async def _chan(q: Quay) -> list[str]:
    st = await CheckoutService(q.pool).readiness(
        identity=q.thu_ngan, visit_id=q.visit_id
    )
    return [b["type"] for b in st["blockers"] if b.get("chan")]


async def _bat_bien(q: Quay) -> list[str]:
    return [
        r["loai"]
        for r in await q.pool.fetch(
            "SELECT * FROM bat_bien_tien_chi_dinh($1::uuid, $2)",
            CLINIC,
            datetime.now(UTC) - timedelta(hours=1),
        )
        if str(r["visit_id"]) == q.visit_id
    ]


async def test_e2a_checkout_con_tien_thua_chan_giu_lai_thi_qua_huy_thi_chan_lai(
    q: Quay,
) -> None:
    await _da_thu_roi_bo(q)
    assert "tien_thua" in await _chan(q)
    with pytest.raises(ValidationError, match="tiền thừa"):
        await CheckoutService(q.pool).close(
            identity=q.thu_ngan, visit_id=q.visit_id, override_reason="thử"
        )
    tt = TienThuaService(q.pool)
    with pytest.raises(ValidationError, match="lý do"):
        await tt.giu_lai(identity=q.thu_ngan, visit_id=q.visit_id, ly_do=" ")
    kq = await tt.giu_lai(
        identity=q.thu_ngan, visit_id=q.visit_id, ly_do="Khách để lại trừ lần sau"
    )
    assert kq["so_tien"] == 300_000
    assert "tien_thua" not in await _chan(q)
    # Hoàn tác "giữ lại" → chặn lại.
    await tt.huy_giu_lai(identity=q.thu_ngan, visit_id=q.visit_id)
    assert "tien_thua" in await _chan(q)
    await tt.giu_lai(identity=q.thu_ngan, visit_id=q.visit_id, ly_do="Giữ lại")
    await CheckoutService(q.pool).close(
        identity=q.thu_ngan, visit_id=q.visit_id, override_reason="thử"
    )
    with pytest.raises(ValidationError, match="check-out"):
        await tt.huy_giu_lai(identity=q.thu_ngan, visit_id=q.visit_id)


async def test_e2a_hai_may_cung_giu_lai_chi_mot_dong_hieu_luc(q: Quay) -> None:
    await _da_thu_roi_bo(q)
    tt = TienThuaService(q.pool)
    await asyncio.gather(
        *(
            tt.giu_lai(identity=q.thu_ngan, visit_id=q.visit_id, ly_do=f"máy {i}")
            for i in range(3)
        )
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM tien_thua_giu_lai WHERE visit_id = $1::uuid"
            " AND huy_luc IS NULL",
            q.visit_id,
        )
        == 1
    )


async def test_e2b_hoan_tien_thua_dung_so_theo_lego_va_bao_cao(q: Quay) -> None:
    await _da_thu_roi_bo(q, 250_000)
    hts = HoanTienService(q.pool)
    kq = await hts.hoan_tien_thua(identity=q.thu_ngan, visit_id=q.visit_id)
    assert kq["amount"] == 250_000 and len(kq["refund_ids"]) == 1
    async with q.pool.acquire() as conn:
        assert q.visit_id not in await tien_thua_cua_luot(conn, CLINIC, [q.visit_id])
        hom_nay = datetime.now(UTC).astimezone().date()
        bc = await bao_cao_tien_thua(
            conn, CLINIC, hom_nay - timedelta(days=1), hom_nay + timedelta(days=1)
        )
    assert bc["da_hoan"] >= 250_000
    assert "tien_thua" not in await _chan(q)
    # Bấm lần hai: không hoàn thêm.
    lai = await hts.hoan_tien_thua(identity=q.thu_ngan, visit_id=q.visit_id)
    assert lai["already"] is True and lai["amount"] == 0
    assert await _bat_bien(q) == []


async def test_e5_hoan_tac_bo_sau_khi_da_hoan_tien_la_no_moi(q: Quay) -> None:
    sa = await _da_thu_roi_bo(q)
    await HoanTienService(q.pool).hoan_tien_thua(
        identity=q.thu_ngan, visit_id=q.visit_id
    )
    bo = await q.pool.fetchval(
        "SELECT id::text FROM so_sua_chi_dinh WHERE service_order_id = $1::uuid"
        " AND hanh_dong = 'BO'",
        sa,
    )
    kq = await SoSuaChiDinhService(q.pool).hoan_tac(so_id=bo, identity=q.bac_si)
    moi = kq["chi_dinh_moi"]
    assert moi and moi != sa
    cu = await q.pool.fetchrow(
        "SELECT exec_status FROM service_order WHERE id = $1::uuid", sa
    )
    assert cu["exec_status"] == "cancelled", "dòng cũ giữ nguyên để đối chiếu tiền"
    # Quầy: chỉ định mới là khoản CHƯA THU (sau khi khách chọn).
    await q.pool.execute(
        "UPDATE service_order SET selection_status = 'SELECTED' WHERE id = $1::uuid",
        moi,
    )
    assert moi in {d.source_id for d in (await _hd(q)).dong}
    so = await q.pool.fetch(
        "SELECT hanh_dong, hoan_tac_cua::text, service_order_id::text, chi_tiet"
        " FROM so_sua_chi_dinh WHERE visit_id = $1::uuid ORDER BY stt",
        q.visit_id,
    )
    assert so[-1]["hanh_dong"] == "HOAN_TAC" and so[-1]["hoan_tac_cua"] == bo
    assert so[-1]["service_order_id"] == moi
    assert "KET_DA_HOAN" not in await _bat_bien(q)
    await _thu(q)
    assert (await _hd(q)).dong == []


async def test_e5_bat_bien_bat_chi_dinh_con_hieu_luc_da_hoan_het(q: Quay) -> None:
    sa = await _cd(q, "SA", 100_000)
    await _thu(q)
    line, cycle = await q.pool.fetchrow(
        "SELECT id::text, payment_cycle_id::text FROM payment_bill_line"
        " WHERE source_id = $1",
        sa,
    )
    await HoanTienService(q.pool).tao(
        identity=q.thu_ngan,
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": line, "so_luong": 1}],
        method="CASH",
        reason="Hoàn nhưng quên bỏ chỉ định",
    )
    assert "KET_DA_HOAN" in await _bat_bien(q)


async def test_e4_postgres_tu_choi_dong_thu_cua_chi_dinh_da_huy(q: Quay) -> None:
    sa = await _cd(q, "SA", 100_000, exec_status="cancelled")
    cycle = await q.pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
        " LIMIT 1",
        q.visit_id,
    )
    if cycle is None:
        await _cd(q, "XN", 50_000)
        await _thu(q)
        cycle = await q.pool.fetchval(
            "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid"
            " LIMIT 1",
            q.visit_id,
        )
    with pytest.raises(asyncpg.CheckViolationError, match="đã bỏ"):
        await q.pool.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 'service_order', $4,"
            " 'x', 1, 100000, 100000, 'CLINIC')",
            CLINIC,
            cycle,
            q.visit_id,
            sa,
        )


async def test_e4_quay_thu_va_bac_si_bo_cung_luc_khong_co_dong_thu_cho_chi_dinh_da_huy(
    q: Quay,
) -> None:
    async def _thu_tre(giay: float) -> object:
        await asyncio.sleep(giay)
        return await _thu(q)

    # Lượt lẻ cho quầy thu trễ một chút để lệnh bỏ hay giữ khoá lượt trước —
    # không trễ thì gần như lúc nào quầy cũng thắng, nhánh "bỏ trước" không
    # được thử.
    for i in range(4):
        sa = await _cd(q, "SA", 120_000)
        kq = await asyncio.gather(
            _thu_tre(0.02 if i % 2 else 0),
            HoanTacService(q.pool).huy_chi_dinh(
                order_id=sa, identity=q.bac_si, xac_nhan=True, ly_do="Đổi ý"
            ),
            return_exceptions=True,
        )
        assert not any(isinstance(k, asyncpg.PostgresError) for k in kq), kq
        # Dòng thu chỉ được có nếu nó commit TRƯỚC lệnh bỏ — khi ấy lệnh bỏ đã
        # thấy và ghi đúng số đó thành tiền thừa trên sổ. Đừng so
        # `created_at > luc`: cả hai là now() = giờ BẮT ĐẦU giao dịch, mà giao
        # dịch bỏ có thể mở trước rồi đứng chờ khoá lượt trong lúc quầy thu
        # xong → đỏ chập chờn dù tiền đúng.
        so = await q.pool.fetchrow(
            "SELECT da_thu, tien_thua FROM so_sua_chi_dinh"
            " WHERE service_order_id = $1::uuid AND hanh_dong = 'BO'",
            sa,
        )
        thu = await q.pool.fetchval(
            "SELECT coalesce(sum(line_total), 0) FROM payment_bill_line"
            " WHERE source_id = $1",
            sa,
        )
        assert (so["da_thu"], so["tien_thua"]) == (thu, thu)
    assert await _bat_bien(q) == []
