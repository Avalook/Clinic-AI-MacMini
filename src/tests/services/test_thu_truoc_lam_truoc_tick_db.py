"""THU TRƯỚC KHI LÀM + tick "Làm trước – thu sau" theo lượt (Tuyền 30/09/2026 tối).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55569/postgres \\
        .venv/bin/pytest src/tests/services/test_thu_truoc_lam_truoc_tick_db.py

V10 cho MỌI lượt làm trước, thu sau. Tuyền đổi ý: dây ``thu_truoc_khi_lam``
(mặc định BẬT) → chưa thu thì chỉ lượt được tick mới xếp phòng / bắt đầu làm.
Dây TẮT = V10.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import finance_gate
from clinicai.services.bill_service import hoa_don_con_no, tinh_hoa_don
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.lam_truoc_thu_sau import (
    CAU_DA_BAT_DAU,
    QUYEN_TICK,
    LamTruocThuSauService,
)
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _su_kien,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@asynccontextmanager
async def day_thu_truoc(pool: asyncpg.Pool, bat: bool) -> AsyncIterator[None]:  # noqa: F811
    """Đặt dây ``thu_truoc_khi_lam`` cho phòng khám thử, trả lại như cũ sau đó
    (mọi bài dùng chung một phòng khám — không để dây rò sang bài khác)."""
    cu = await pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
        " AND ma = 'thu_truoc_khi_lam'",
        CLINIC,
    )
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, 'thu_truoc_khi_lam', $2::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = EXCLUDED.gia_tri",
        CLINIC,
        json.dumps(bat),
    )
    try:
        yield
    finally:
        if cu is None:
            await pool.execute(
                "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
                " AND ma = 'thu_truoc_khi_lam'",
                CLINIC,
            )
        else:
            await pool.execute(
                "UPDATE day_nghiep_vu SET gia_tri = $2::jsonb"
                " WHERE clinic_id = $1::uuid AND ma = 'thu_truoc_khi_lam'",
                CLINIC,
                cu,
            )


async def _gate(pool: asyncpg.Pool, order: str) -> finance_gate.FinanceDecision:  # noqa: F811
    async with pool.acquire() as conn:
        g = await finance_gate.can_start(conn, CLINIC, order)
    assert g is not None
    return g


async def _bat_dau(pool: asyncpg.Pool, ca: Ca, order: str) -> dict:  # type: ignore[type-arg]  # noqa: F811
    d = await _don(pool, order)
    return await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _xong(pool: asyncpg.Pool, ca: Ca, order: str, attempt: str) -> None:  # noqa: F811
    d = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=attempt,
        expected_execution_revision=int(d["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


async def _xep_tay(pool: asyncpg.Pool, ca: Ca, order: str) -> None:  # noqa: F811
    d = await _don(pool, order)
    await ServiceRoutingService(pool).assign(
        order_id=order,
        room_id=ca.phong,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="MANUAL_CORRECTION",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )


# ── Dây BẬT (mặc định), không tick ─────────────────────────────────────────


async def test_mac_dinh_thu_truoc_chot_khong_xep_thu_xong_moi_xep_va_lam(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)

    await _chon(pool, ca, visit, [order])
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "UNASSIGNED"
    g = await _gate(pool, order)
    assert (g.finance_state, g.duoc_lam) == ("DUE", False)

    # Xếp tay cũng bị chặn, câu rõ.
    with pytest.raises(ConflictError, match="Chưa thu tiền — thu trước hoặc tick"):
        await _xep_tay(pool, ca, order)

    # Thu xong → H4 xếp, bắt đầu làm được.
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"
    bd = await _bat_dau(pool, ca, order)
    assert bd["ok"] is True


# ── Tick ────────────────────────────────────────────────────────────────────


async def test_tick_chot_luon_xep_ngay_lam_khi_chua_thu_cuoi_buoi_thu_dung_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    svc = LamTruocThuSauService(pool)

    doc = await svc.doc(visit_id=visit, identity=ca.le_tan)
    assert (doc["hien"], doc["tick_duoc"], doc["lam_truoc_thu_sau"]) == (
        True,
        True,
        False,
    )

    # Lễ tân tick — CHƯA ai chốt chỉ định: tick chốt luôn (khách làm).
    kq = await svc.dat(visit_id=visit, bat=True, identity=ca.le_tan)
    assert kq["lam_truoc_thu_sau"] is True and kq["bat_boi"] is not None
    assert kq["bat_luc"] is not None and kq["chot_thu_sau_duoc"] is True
    v = await pool.fetchrow(
        "SELECT lam_truoc_thu_sau_luc, lam_truoc_thu_sau_boi::text AS boi"
        " FROM visit WHERE visit_id = $1::uuid",
        visit,
    )
    assert v["lam_truoc_thu_sau_luc"] is not None and v["boi"] == ca.le_tan.staff_id
    assert (await _don(pool, order))["selection_status"] == "SELECTED"
    [ev] = await _su_kien(pool, "visit.defer_payment_set", visit)
    assert ev["ai"] == ca.le_tan.staff_id
    assert json.loads(ev["payload"])["so_chi_dinh_chot"] == 1
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type ="
            " 'visit.defer_payment_set' AND aggregate_id = $1",
            visit,
        )
        == 1
    )
    # Bật lần hai: không thêm sự kiện.
    await svc.dat(visit_id=visit, bat=True, identity=ca.le_tan)
    assert len(await _su_kien(pool, "visit.defer_payment_set", visit)) == 1

    # Dòng thời gian lượt có "Bật Làm trước – thu sau" + người bật.
    await chay_ben_nhan(pool, "dong_thoi_gian_luot")
    dong = await pool.fetchrow(
        "SELECT nhan, actor_staff_id::text AS ai FROM luot_dong_thoi_gian"
        " WHERE visit_id = $1::uuid AND event_type = 'visit.defer_payment_set'",
        visit,
    )
    assert dong["nhan"] == "Bật Làm trước – thu sau"
    assert dong["ai"] == ca.le_tan.staff_id

    # Dây H4 xếp ngay khi chưa thu.
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"
    g = await _gate(pool, order)
    assert (g.finance_state, g.duoc_lam) == ("DUE", True)

    async with pool.acquire() as conn:
        truoc = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert order in {x.source_id for x in truoc.dong} and truoc.tong > 0

    bd = await _bat_dau(pool, ca, order)
    await _xong(pool, ca, order, bd["attempt_id"])

    # Quầy thấy nhóm "Làm trước – thu sau": đã làm xong hết → lên đầu.
    b = await CashierBoardService(pool).board(identity=ca.thu_ngan, modes=["dich_vu"])
    [luot] = [i for i in b["items"] if i["visit_id"] == visit]
    lt = luot["lam_truoc"]
    assert lt["lam_truoc_thu_sau"] is True and lt["nhom"] == "LAM_XONG_THU_TIEN"
    [dv] = lt["dich_vu"]
    assert (dv["id"], dv["trang_thai"], dv["nhan"]) == (order, "DA_XONG", "Đã làm xong")
    assert dv["con_no"] == 300_000
    assert b["items"][0]["visit_id"] == visit

    # Bỏ tick sau khi đã làm → từ chối, câu rõ.
    with pytest.raises(ConflictError, match="Đã có dịch vụ bắt đầu làm"):
        await svc.dat(visit_id=visit, bat=False, identity=ca.le_tan)
    doc = await svc.doc(visit_id=visit, identity=ca.le_tan)
    assert (doc["bo_tick_duoc"], doc["ly_do_khong_bo"]) == (False, CAU_DA_BAT_DAU)

    # Hoá đơn vẫn còn nợ đủ; thu cuối đúng số.
    async with pool.acquire() as conn:
        sau = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert (sau.tong, sau.revision) == (truoc.tong, truoc.revision)
    await _thu(pool, visit, ca.thu_ngan)
    so_tien = await pool.fetchval(
        "SELECT amount FROM payment_cycle WHERE visit_id = $1::uuid"
        " AND kind = 'dich_vu' AND status = 'PAID'",
        visit,
    )
    assert int(so_tien) == truoc.tong
    assert (await _gate(pool, order)).finance_state == "PAID"


async def test_bo_tick_truoc_khi_lam_thi_bat_dau_bi_chan_cau_ro(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    svc = LamTruocThuSauService(pool)

    # Bác sĩ (lego Bàn khám) tick được.
    await svc.dat(visit_id=visit, bat=True, identity=ca.bac_si)
    await _xep_tay(pool, ca, order)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"

    kq = await svc.dat(visit_id=visit, bat=False, identity=ca.le_tan)
    assert kq["lam_truoc_thu_sau"] is False
    assert (
        await pool.fetchval(
            "SELECT lam_truoc_thu_sau_luc FROM visit WHERE visit_id = $1::uuid", visit
        )
        is None
    )
    [ev] = await _su_kien(pool, "visit.defer_payment_cleared", visit)
    assert ev["ai"] == ca.le_tan.staff_id

    with pytest.raises(ConflictError, match="Chưa thu tiền — thu trước hoặc tick"):
        await _bat_dau(pool, ca, order)


async def test_khong_co_quyen_thi_khong_tick_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await pool.execute(
        "UPDATE capability_grant SET revoked_at = now(), revoked_by = $2::uuid,"
        " ly_do = 'Thử: tắt hết' WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
        " AND revoked_at IS NULL",
        CLINIC,
        ca.dd.staff_id,
    )
    from clinicai.permissions import cache

    cache.quen(CLINIC, ca.dd.staff_id)
    # Còn quyền theo lịch? Người thử không có ca nào — v_quyen_thuc_te rỗng.
    co = await pool.fetchval(
        "SELECT count(*) FROM v_quyen_thuc_te WHERE clinic_id = $1::uuid"
        " AND staff_id = $2::uuid AND capability = ANY($3::text[])",
        CLINIC,
        ca.dd.staff_id,
        list(QUYEN_TICK),
    )
    if co:
        pytest.skip("người thử vẫn có quyền qua đường khác")
    with pytest.raises(SafetyGateError):
        await LamTruocThuSauService(pool).dat(visit_id=visit, bat=True, identity=ca.dd)
    doc = await LamTruocThuSauService(pool).doc(visit_id=visit, identity=ca.dd)
    assert doc["tick_duoc"] is False


# ── Dây TẮT = V10 ──────────────────────────────────────────────────────────


async def test_tat_day_nhu_v10_chot_la_xep_khong_can_tick(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, False):
        ca = await _dung(pool)
        visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
        _con, order = await _kham_va_chi_dinh(pool, ca, visit)
        await _chon(pool, ca, visit, [order])
        await chay_hanh_trinh(pool)
        assert (await _don(pool, order))["routing_status"] == "ASSIGNED"
        g = await _gate(pool, order)
        assert (g.finance_state, g.duoc_lam) == ("DUE", True)
        doc = await LamTruocThuSauService(pool).doc(visit_id=visit, identity=ca.le_tan)
        assert (doc["hien"], doc["chot_thu_sau_duoc"]) == (False, True)


# ── Mọi quầy thu hết được ─────────────────────────────────────────────────


async def test_quay_thuoc_thay_no_dich_vu_va_thu_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    async with pool.acquire() as conn:
        thuoc = await conn.fetchval(
            "INSERT INTO public.drug_catalog (clinic_id, name_base, name_raw,"
            " unit_price, is_active) VALUES ($1::uuid, $2, $2, 5000, true)"
            " RETURNING id::text",
            CLINIC,
            f"Thuốc thử {_khoa()}",
        )
        await conn.execute(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit,"
            " drug_catalog_id, drug_mapped_by, drug_mapped_at)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id,"
            " 'Thuốc thử', '2 viên', 2, 'viên', $4::uuid, $5::uuid, now()"
            " FROM visit v WHERE v.visit_id = $3::uuid",
            CLINIC,
            f"test-rx-{_khoa()}",
            visit,
            thuoc,
            ca.bac_si.staff_id,
        )
    board = CashierBoardService(pool)
    b = await board.board(identity=ca.thu_ngan, modes=["thuoc"])
    [luot] = [i for i in b["items"] if i["visit_id"] == visit]
    no_dv = luot["no_khac"]["dich_vu"]
    async with pool.acquire() as conn:
        con_no = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    # Đúng hoá đơn còn nợ của quầy dịch vụ (có siêu âm 300k).
    assert (no_dv["tong"], no_dv["revision"]) == (con_no.tong, con_no.revision)
    assert no_dv["tong"] >= 300_000

    # Quầy dịch vụ thấy nợ thuốc.
    b = await board.board(identity=ca.thu_ngan, modes=["dich_vu"])
    [luot_dv] = [i for i in b["items"] if i["visit_id"] == visit]
    assert luot_dv["no_khac"]["thuoc"]["tong"] == 10_000

    # [Thu luôn] ở quầy thuốc = đúng lệnh thu dịch vụ, cùng hoá đơn máy chủ.
    kq = await PaymentService(pool).record_payment(
        visit_id=visit,
        kind="dich_vu",
        amount=no_dv["tong"],
        bill_revision=no_dv["revision"],
        clinic_patient_id=None,
        method="CASH",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )
    assert kq["status"] == "PAID"
    async with pool.acquire() as conn:
        assert (await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)).tong == 0
        hd_thuoc = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=visit, kind="thuoc"
        )
    assert hd_thuoc.tong == 10_000
    b = await board.board(identity=ca.thu_ngan, modes=["thuoc"])
    [luot] = [i for i in b["items"] if i["visit_id"] == visit]
    assert "dich_vu" not in luot["no_khac"]
