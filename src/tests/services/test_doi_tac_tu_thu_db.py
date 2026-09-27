"""Đối tác TỰ THU tiền (Tuyền chốt 27/09/2026, Q1 + Q2 — gói 9 đợt 3).

"Tiền dịch vụ đối tác: KHÁCH TRẢ TRỰC TIẾP cho đối tác, màn đối tác cũng phải
có ghi nhận thanh toán thực hiện." — nên:

* hoá đơn quầy chỉ cộng phần PHÒNG KHÁM; dòng đối tác hiện riêng (giá tham khảo);
* FinanceGate coi đối tác tự thu là SẴN SÀNG (không còn chặn mãi);
* lượt chỉ có dịch vụ đối tác: quầy không kẹt, check-out không đòi phiếu thu;
* đối tác tự lấy mẫu nhận việc khi khách CHỐT làm (không chờ thu tiền);
* đối tác ghi nhận / huỷ "đã thu tiền khách" — sổ riêng, một ghi nhận còn hiệu
  lực mỗi việc, khác phòng khám không thấy;
* Bảng giá: dòng `gia_tam` bỏ cờ khi quản lý sửa đơn giá; bên thu theo phòng làm.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.consumers.doi_tac import nhan_viec_doi_tac
from clinicai.events.worker import SuKienDaNhan
from clinicai.services import finance_gate
from clinicai.services.bill_service import (
    chi_doi_tac_thu_luot,
    doi_tac_da_thu,
    hoa_don_con_no,
)
from clinicai.services.checkout_service import CheckoutService, build_blockers
from clinicai.services.config_service import PriceListService
from clinicai.services.doi_tac_service import (
    DoiTacService,
    doc_hinh_thuc,
    doc_so_tien,
)
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

HPV_NODE = "DICHVU-SANGLOC-COTUCUNG"


# ---------------------------------------------------------------------------
# Hàm thuần: đầu vào rác → None, không ném
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        (900000, 900000),
        ("900.000", 900000),
        ("900,000đ", 900000),
        (" 1 200 000 vnd ", 1200000),
        (0, 0),
        (900000.0, 900000),
        (-1, None),
        ("-5", None),
        ("abc", None),
        ("", None),
        (None, None),
        (True, None),
        (1.5, None),
        (float("nan"), None),
        (float("inf"), None),
        (10**12, None),
        ([900], None),
    ],
)
def test_doc_so_tien(vao: Any, ra: int | None) -> None:
    assert doc_so_tien(vao) == ra


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("CASH", "CASH"),
        (" transfer ", "TRANSFER"),
        ("QR", None),
        ("", None),
        (None, None),
        (1, None),
    ],
)
def test_doc_hinh_thuc(vao: Any, ra: str | None) -> None:
    assert doc_hinh_thuc(vao) == ra


def test_check_out_khong_doi_phieu_thu_khi_doi_tac_tu_thu() -> None:
    goc = {"paid_service": False, "doi_tac_tu_thu": False}
    assert any(b["type"] == "unpaid_service" for b in build_blockers(goc))
    tu_thu = {"paid_service": False, "doi_tac_tu_thu": True}
    assert not any(b["type"] == "unpaid_service" for b in build_blockers(tu_thu))


def test_finance_gate_doi_tac_tu_thu_la_san_sang() -> None:
    assert finance_gate.PARTNER_COLLECTS in finance_gate.READY_STATES


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------


async def _gia(
    q: Quay, ma: str, gia: int, node: str, *, ben: str, tu_lay: bool = False
) -> None:
    await q.pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price, billing_owner, node_code, doi_tac_lay_mau)"
        " VALUES ($1::uuid, 'dich_vu', $2, $2, $3, $4, $5, $6)",
        CLINIC,
        ma,
        gia,
        ben,
        node,
        tu_lay,
    )


async def _cd(q: Quay, ma: str, node: str, exec_status: str = "authorized") -> str:
    oid = str(
        await q.pool.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $4, $5, 'authorized',"
            " $6::uuid, $6::uuid, now(), 'SELECTED') RETURNING id::text",
            CLINIC,
            q.visit_id,
            q.consultation_id,
            ma,
            node,
            q.bac_si.staff_id,
        )
    )
    if exec_status == "performed":
        await _lam_xong(q, oid)
    return oid


async def _lam_xong(q: Quay, oid: str) -> None:
    """Phòng lấy mẫu của phòng khám làm xong (cần phòng — CHECK của bảng)."""
    await q.pool.execute(
        "UPDATE service_order o SET exec_status = 'performed', finished_at = now(),"
        " room_id = (SELECT r.id FROM clinic_room r JOIN clinic_room_node rn"
        "   ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id"
        "  WHERE r.clinic_id = o.clinic_id AND rn.node_code = o.node_code"
        "    AND NOT r.la_doi_tac ORDER BY r.sort LIMIT 1)"
        " WHERE o.id = $1::uuid",
        oid,
    )


def _su_kien(ten: str, q: Quay) -> SuKienDaNhan:
    return SuKienDaNhan(
        event_id=str(uuid.uuid4()),
        event_type=ten,
        clinic_id=CLINIC,
        aggregate_id=q.visit_id,
        aggregate_version=None,
        occurred_at=None,
        seq=0,
        actor_type="HUMAN",
        actor_staff_id=q.thu_ngan.staff_id,
        payload={"visit_id": q.visit_id},
        replay_id=None,
        attempts=0,
    )


async def _nguoi_vai(q: Quay, vai: str) -> StaffIdentity:
    async with q.pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        return await _nguoi(conn, loc, vai)


async def _viec_da_nhan(q: Quay) -> str:
    """Một chỉ định HPV (khách trả đối tác) đã lấy mẫu xong + đối tác đã nhận."""
    ma = f"HPV-{q.duoi}"
    await _gia(q, ma, 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    oid = await _cd(q, ma, HPV_NODE, exec_status="performed")
    await q.pool.execute(
        "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
        " VALUES ($1::uuid, $2::uuid, 'DA_LAY_MAU')",
        CLINIC,
        oid,
    )
    return oid


@pytest.mark.db
@pytest.mark.asyncio
async def test_kham_cong_hpv_bill_chi_cong_kham(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await _gia(q, f"HPV-{q.duoi}", 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    # Tiền khám 150.000 (loại khám của lượt) + HPV đối tác 900.000.
    hpv = await _cd(q, f"HPV-{q.duoi}", HPV_NODE)
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=q.visit_id)
        g = await finance_gate.states_for_orders(conn, CLINIC, [hpv])
        chi_dt = await chi_doi_tac_thu_luot(conn, clinic_id=CLINIC, visit_id=q.visit_id)
    assert hd.tong == 150_000
    assert [d.source_id for d in hd.dong_doi_tac] == [hpv]
    api = hd.cho_api()
    assert api["tong"] == 150_000
    assert api["dong_doi_tac"][0]["thanh_tien"] == 900_000
    assert api["dong_doi_tac"][0]["doi_tac_da_thu"] is None
    assert api["chi_doi_tac_thu"] is False
    assert g[hpv].finance_state == finance_gate.PARTNER_COLLECTS
    assert g[hpv].financially_ready
    # Còn tiền khám phải thu → check-out vẫn đòi phiếu thu.
    assert chi_dt is False
    ra = await CheckoutService(pool).readiness(identity=q.thu_ngan, visit_id=q.visit_id)
    assert any(b["type"] == "unpaid_service" for b in ra["blockers"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_luot_chi_hpv_khong_ket_quay_check_out_duoc(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    # Lịch "đi thẳng phòng" (chỉ làm HPV): không có buổi khám nào để tính tiền.
    await pool.execute(
        "UPDATE service_type SET di_thang_phong = true WHERE clinic_id = $1::uuid"
        " AND code = $2",
        CLINIC,
        f"KT-{q.duoi}",
    )
    await _gia(q, f"HPV-{q.duoi}", 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    hpv = await _cd(q, f"HPV-{q.duoi}", HPV_NODE)
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=q.visit_id)
        assert hd.dong == [] and hd.tong == 0 and hd.chi_doi_tac_thu
        assert await chi_doi_tac_thu_luot(conn, clinic_id=CLINIC, visit_id=q.visit_id)
    ra = await CheckoutService(pool).readiness(identity=q.thu_ngan, visit_id=q.visit_id)
    assert not any(b["type"] == "unpaid_service" for b in ra["blockers"])

    # Điều dưỡng lấy mẫu xong ở phòng → đối tác nhận việc, không chờ thu tiền.
    await _lam_xong(q, hpv)
    async with pool.acquire() as conn, conn.transaction():
        await nhan_viec_doi_tac(conn, _su_kien("service.completed", q))
    ly_do = await pool.fetchval(
        "SELECT ly_do FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid", hpv
    )
    assert ly_do == "DA_LAY_MAU"
    # Làm xong rời hoá đơn còn nợ — check-out vẫn không đòi phiếu thu.
    ra = await CheckoutService(pool).readiness(identity=q.thu_ngan, visit_id=q.visit_id)
    assert not any(b["type"] == "unpaid_service" for b in ra["blockers"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_doi_tac_tu_lay_mau_nhan_viec_khi_khach_chot(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ma = f"PHIM-{q.duoi}"
    await _gia(
        q, ma, 1_500_000, "DICHVU-HINHANH-NGOAI", ben="EXTERNAL_PARTNER", tu_lay=True
    )
    oid = await _cd(q, ma, "DICHVU-HINHANH-NGOAI")
    su_kien = _su_kien("service_selection.confirmed", q)
    for _ in range(2):  # chạy lại được: không đẻ dòng / sự kiện thứ hai
        async with pool.acquire() as conn, conn.transaction():
            await nhan_viec_doi_tac(conn, su_kien)
    rows = await pool.fetch(
        "SELECT ly_do FROM doi_tac_nhan_viec WHERE service_order_id = $1::uuid", oid
    )
    assert [r["ly_do"] for r in rows] == ["KHACH_DA_CHON"]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'partner.order_received' AND aggregate_id = $1::uuid",
            oid,
        )
        == 1
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_ghi_nhan_va_huy_da_thu(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    dt = await _nguoi_vai(q, "PARTNER")
    svc = DoiTacService(pool)

    viec = [
        v
        for k in (await svc.viec_doi_tac(identity=dt))["khach"]
        for v in k["viec"]
        if v["chi_dinh_id"] == oid
    ][0]
    assert viec["doi_tac_thu"] is True
    assert viec["gia_tham_khao"] == 900_000
    assert viec["da_thu"] is None

    with pytest.raises(ValidationError):
        await svc.ghi_nhan_da_thu(
            order_id=oid, identity=dt, so_tien="rác", hinh_thuc="CASH"
        )
    with pytest.raises(ValidationError):
        await svc.ghi_nhan_da_thu(
            order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="QR"
        )

    kq = await svc.ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien="900.000", hinh_thuc="cash", ghi_chu="ok"
    )
    assert kq["already"] is False
    # Bấm lại cùng số = chạy lại được.
    lai = await svc.ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="CASH"
    )
    assert lai["already"] is True and lai["id"] == kq["id"]
    # Khác số → phải huỷ trước.
    with pytest.raises(ConflictError):
        await svc.ghi_nhan_da_thu(
            order_id=oid, identity=dt, so_tien=800_000, hinh_thuc="CASH"
        )
    # Hai ghi nhận còn hiệu lực bị Postgres chặn (unique một phần).
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO doi_tac_thanh_toan (clinic_id, service_order_id, so_tien,"
            " hinh_thuc, ghi_boi) VALUES ($1::uuid, $2::uuid, 1, 'CASH', $3::uuid)",
            CLINIC,
            oid,
            dt.staff_id,
        )
    viec = [
        v
        for k in (await svc.viec_doi_tac(identity=dt))["khach"]
        for v in k["viec"]
        if v["chi_dinh_id"] == oid
    ][0]
    assert viec["da_thu"]["so_tien"] == 900_000
    assert viec["da_thu"]["hinh_thuc"] == "CASH"

    # Quầy / Xem lượt đọc cùng sổ.
    async with pool.acquire() as conn:
        assert (await doi_tac_da_thu(conn, CLINIC, [oid]))[oid]["so_tien"] == 900_000

    with pytest.raises(ValidationError):
        await svc.huy_da_thu(order_id=oid, identity=dt, ly_do="  ")
    await svc.huy_da_thu(order_id=oid, identity=dt, ly_do="ghi nhầm số tiền")
    again = await svc.huy_da_thu(order_id=oid, identity=dt, ly_do="lần hai")
    assert again["already"] is True
    dong = await pool.fetchrow(
        "SELECT huy_luc, huy_boi::text, ly_do_huy FROM doi_tac_thanh_toan"
        " WHERE service_order_id = $1::uuid",
        oid,
    )
    assert dong is not None
    assert dong["huy_luc"] is not None and dong["huy_boi"] == dt.staff_id
    assert dong["ly_do_huy"] == "ghi nhầm số tiền"
    # Dòng đã huỷ không sửa, không xoá được.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "UPDATE doi_tac_thanh_toan SET so_tien = 1"
            " WHERE service_order_id = $1::uuid",
            oid,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM doi_tac_thanh_toan WHERE service_order_id = $1::uuid", oid
        )
    # Ghi lại số mới sau khi huỷ.
    await svc.ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=800_000, hinh_thuc="TRANSFER"
    )
    su_kien = [
        r["event_type"]
        for r in await pool.fetch(
            "SELECT event_type FROM domain_event WHERE aggregate_id = $1::uuid"
            " AND event_type LIKE 'partner.payment_%' ORDER BY seq",
            oid,
        )
    ]
    assert su_kien == [
        "partner.payment_recorded",
        "partner.payment_voided",
        "partner.payment_recorded",
    ]


@pytest.mark.db
@pytest.mark.asyncio
async def test_khong_phai_doi_tac_khong_ghi_duoc(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    with pytest.raises(SafetyGateError):
        await DoiTacService(pool).ghi_nhan_da_thu(
            order_id=oid, identity=q.bac_si, so_tien=1, hinh_thuc="CASH"
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_khac_phong_kham_khong_thay(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    dt = await _nguoi_vai(q, "PARTNER")
    await DoiTacService(pool).ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="CASH"
    )
    khac = str(
        await pool.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"K{q.duoi}",
        )
    )
    async with pool.acquire() as conn:
        assert await doi_tac_da_thu(conn, khac, [oid]) == {}
    dt_khac = dataclasses.replace(dt, clinic_id=khac)
    with pytest.raises(SafetyGateError):
        await DoiTacService(pool).ghi_nhan_da_thu(
            order_id=oid, identity=dt_khac, so_tien=1, hinh_thuc="CASH"
        )
    with pytest.raises(SafetyGateError):
        await DoiTacService(pool).huy_da_thu(
            order_id=oid, identity=dt_khac, ly_do="thử phá"
        )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM doi_tac_thanh_toan WHERE service_order_id = $1::uuid"
            " AND huy_luc IS NULL",
            oid,
        )
        == 1
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_bang_gia_gia_tam_va_ben_thu_theo_phong(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ma = f"KHAM-TAM-{q.duoi}"
    pid = str(
        await pool.fetchval(
            'INSERT INTO service_price (clinic_id, "group", service_code, name,'
            " unit_price, gia_tam) VALUES ($1::uuid, 'dich_vu', $2, $2, 500000, true)"
            " RETURNING id::text",
            CLINIC,
            ma,
        )
    )
    ql = await _nguoi_vai(q, "MANAGEMENT")
    svc = PriceListService(pool)
    dong = [
        r for r in await svc.list(group="dich_vu", identity=ql) if str(r["id"]) == pid
    ]
    assert dong and dong[0]["gia_tam"] is True
    # Đổi tên không bỏ cờ; sửa (hay lưu lại) đơn giá thì bỏ.
    await svc.update(price_id=pid, identity=ql, name=f"{ma} mới")
    assert await pool.fetchval(
        "SELECT gia_tam FROM service_price WHERE id = $1::uuid", pid
    )
    await svc.update(
        price_id=pid, identity=ql, unit_price=500000, unit_price_provided=True
    )
    assert not await pool.fetchval(
        "SELECT gia_tam FROM service_price WHERE id = $1::uuid", pid
    )
    # Đổi phòng làm sang bước làm bên ngoài → khách trả đối tác (theo phòng).
    await svc.update(price_id=pid, identity=ql, node_code="DICHVU-LAYMAU-MAU")
    assert (
        await pool.fetchval(
            "SELECT billing_owner FROM service_price WHERE id = $1::uuid", pid
        )
        == "EXTERNAL_PARTNER"
    )
    await svc.update(price_id=pid, identity=ql, node_code="DICHVU-SIEUAM")
    assert (
        await pool.fetchval(
            "SELECT billing_owner FROM service_price WHERE id = $1::uuid", pid
        )
        == "CLINIC"
    )
