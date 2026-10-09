"""Sửa lỗi review đợt 07/10/2026 — NHẬN KHÁCH TẠI PHÒNG, trên Postgres thật.
Mỗi bài tái hiện đúng một lỗi review (số trong tên).

    scripts/test-nhanh.sh src/tests/services/test_review_0710_nhan_tai_phong_db.py
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services import nhan_tai_phong as ntp
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhan_tai_phong_db import (  # noqa: F401
    _bat_dau,
    _cd_o,
    _cho,
    _moc,
    _nhan,
    _sk,
    _song,
    bat,
)
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _loi,
    _o,
    _paid,
    rb,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _hoan_cho(b: RB, oid: str) -> None:
    """Khoản hoàn PENDING cho dòng đã thu của chỉ định."""
    dong = await b.pool.fetchrow(
        "SELECT id, payment_cycle_id FROM payment_bill_line"
        " WHERE source_type = 'service_order' AND source_id = $1",
        oid,
    )
    assert dong is not None
    # Đầu khoản + dòng cùng giao dịch (ràng buộc "tiền đầu khoản = tổng dòng"
    # kiểm lúc commit).
    async with b.pool.acquire() as conn, conn.transaction():
        await _hoan_ghi(conn, b, dong)


async def _hoan_ghi(conn: Any, b: RB, dong: Any) -> None:
    hoan = await conn.fetchval(
        "INSERT INTO payment_refund (clinic_id, visit_id, kind, payment_cycle_id,"
        " amount, status, method, reason, created_by) VALUES ($1::uuid, $2::uuid,"
        " 'dich_vu', $3, 200000, 'PENDING', 'CASH', 'Khách đổi ý', $4::uuid)"
        " RETURNING refund_id",
        CLINIC,
        b.visit_id,
        dong["payment_cycle_id"],
        b.truong_ca.staff_id,
    )
    await conn.execute(
        "INSERT INTO payment_refund_line (clinic_id, refund_id, payment_cycle_id,"
        " payment_bill_line_id, quantity, amount) VALUES ($1::uuid, $2, $3, $4, 1,"
        " 200000)",
        CLINIC,
        hoan,
        dong["payment_cycle_id"],
        dong["id"],
    )


def _svc(b: RB) -> ntp.NhanTaiPhongService:
    return ntp.NhanTaiPhongService(b.pool)


async def _hoan_tac(b: RB, room: str, *ids: str) -> dict:  # type: ignore[type-arg]
    return await _svc(b).hoan_tac_nhan(
        visit_id=b.visit_id,
        room_id=room,
        identity=b.truong_ca,
        chi_dinh_ids=list(ids) if ids else None,
    )


# ── Lỗi 3: cổng tiền trước mọi thay đổi, kể cả chỉ định đang chờ ở phòng khác ──


async def test_3_nhan_ca_n_khong_dung_chi_dinh_tien_chan_dang_cho_phong_khac(
    bat: RB,  # noqa: F811
) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    truoc = await _song(bat, o1)
    # Đã thu rồi có khoản HOÀN đang chờ → FinanceGate REFUND_PENDING (chặn nhận).
    await _paid(bat, o1)
    await _hoan_cho(bat, o1)

    kq = await _nhan(bat, bat.sa2, xac_nhan=True)  # "Nhận cả N"
    assert kq["da_nhan"] == [o2] and kq["nhan_cheo"] is False
    assert [b["id"] for b in kq["bo_qua"]] == [o1]
    # Chỉ định của phòng một KHÔNG bị đụng: vẫn chờ ở phòng một, đúng giờ cũ,
    # không có sự kiện rời phòng nào.
    song = await _song(bat, o1)
    assert song is not None and song["room_id"] == bat.sa1
    assert truoc is not None and song["eligible_at"] == truoc["eligible_at"]
    assert (await _o(bat, o1))["room_id"] == bat.sa1
    assert await _sk(bat, o1, "service.room_released") == []

    # Bấm Nhận đúng dòng ấy → báo vì sao, không đụng gì.
    await _loi(_nhan(bat, bat.sa2, o1, xac_nhan=True), "SERVICE_FINANCE_NOT_READY")
    assert (await _song(bat, o1))["room_id"] == bat.sa1  # type: ignore[index]
    async with bat.pool.acquire() as conn:
        ds = await ntp.chi_dinh_cua_khach(conn, CLINIC, bat.sa2, [bat.visit_id])
    [c] = [c for c in ds[bat.visit_id] if c["id"] == o1]
    assert c["nhan_duoc"] is False and c["ly_do_khong_nhan"]


# ── Lỗi 4: hoàn tác nhận chéo trả về đúng hàng phòng cũ ───────────────────────


async def test_4_hoan_tac_nhan_cheo_khi_cho_ve_dung_hang_cu(
    bat: RB,  # noqa: F811
) -> None:
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    truoc = await _song(bat, o1)
    assert truoc is not None
    await _nhan(bat, bat.sa2, o1, xac_nhan=True)
    kq = await _hoan_tac(bat, bat.sa2, o1)
    assert kq["ve_phong_cu"] == [o1] and kq["ve_sap_den"] == []
    song = await _song(bat, o1)
    assert song is not None
    assert (song["room_id"], song["status"]) == (bat.sa1, "waiting")
    assert song["eligible_at"] == truoc["eligible_at"]
    o = await _o(bat, o1)
    assert (o["routing_status"], o["room_id"]) == ("ASSIGNED", bat.sa1)
    [ht] = await _sk(bat, o1, "service.room_receive_undone")
    assert ht["tra_ve_room_id"] == bat.sa1
    [nha] = await _sk(bat, o1, "service.room_released")
    [dung] = await _sk(bat, o1, "service.room_release_undone")
    assert dung["hoan_tac_event_id"] == nha["event_id"]
    assert (dung["room_id"], dung["trang_thai"]) == (bat.sa1, "waiting")
    # Sổ: Nhận ở hai + Nhả ở một đều bị hoàn tác.
    moc = {
        (r["loai_moc"], str(r["room_id"])): r["bi_hoan_tac"] for r in await _moc(bat)
    }
    assert moc[("NHA", bat.sa1)] is True
    assert moc[("NHAN", bat.sa2)] is True
    assert moc[("NHAN", bat.sa1)] is False


async def test_4_hoan_tac_nhan_cheo_khi_dang_lam_dung_lai_cho_lam(
    bat: RB,  # noqa: F811
) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    lam = await _bat_dau(bat, o1)
    dang = await bat.pool.fetchrow(
        "SELECT id, serving_at FROM queue_entry WHERE ref_id = $1::uuid"
        " AND status = 'serving'",
        o1,
    )
    assert dang is not None
    await _nhan(bat, bat.sa2, o2, xac_nhan=True)
    kq = await _hoan_tac(bat, bat.sa2, o2)
    assert kq["ve_sap_den"] == [o2]
    lai = await bat.pool.fetchrow(
        "SELECT id, status, serving_at FROM queue_entry WHERE ref_id = $1::uuid"
        " ORDER BY updated_at DESC LIMIT 1",
        o1,
    )
    assert lai is not None
    assert (lai["id"], lai["status"], lai["serving_at"]) == (
        dang["id"],
        "serving",
        dang["serving_at"],
    )
    [dung] = await _sk(bat, o1, "service.room_release_undone")
    assert (dung["trang_thai"], dung["attempt_id"]) == ("serving", lam["attempt_id"])
    assert dung["ghi_chu"] is None


# ── Lỗi 8: thứ tự thực tế không đếm lần Nhận đã hoàn tác ──────────────────────


async def test_8_thu_tu_thuc_te_bo_lan_nhan_da_hoan_tac(
    bat: RB,  # noqa: F811
) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    await _hoan_tac(bat, bat.sa1, o1)
    await _nhan(bat, bat.sa2, o2)
    [nhan] = await _sk(bat, o2, "service.routed")
    assert nhan["thu_tu_thuc_te"] == 1


# ── Lỗi 9: hoàn tác Nhận chỉ huỷ chỗ do Nhận tại phòng tạo ────────────────────


async def test_9_hoan_tac_nhan_khong_huy_cho_xep_duong_cu(
    bat: RB,  # noqa: F811
) -> None:
    # Chỗ quầy / trưởng ca xếp theo đường cũ (trước khi bật dây).
    o1 = await _cd_o(
        bat,
        bat.sa1,
        routing="ASSIGNED",
        room_id=bat.sa1,
        routing_revision=1,
        routing_nguon="quay_thu",
    )
    await bat.pool.execute(
        "INSERT INTO queue_entry (clinic_id, visit_id, lane, room_id, reason,"
        " ref_id, status, eligible_at) VALUES ($1::uuid, $2::uuid, 'ROOM',"
        " $3::uuid, 'SERVICE', $4::uuid, 'waiting', now())",
        CLINIC,
        bat.visit_id,
        bat.sa1,
        o1,
    )
    o2 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1, o2)
    kq = await _hoan_tac(bat, bat.sa1)
    assert kq["ve_sap_den"] == [o2]
    song = await _song(bat, o1)
    assert song is not None and song["status"] == "waiting"
    assert (await _o(bat, o1))["routing_status"] == "ASSIGNED"
    assert await _sk(bat, o1, "service.room_receive_undone") == []


# ── Soát thêm (lỗi 2): khách đã check-out thì phòng không Nhận nữa ────────────


async def test_2_nhan_tai_phong_tu_choi_luot_da_check_out(
    bat: RB,  # noqa: F811
) -> None:
    o1 = await _cd_o(bat, bat.sa1)
    await bat.pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", bat.visit_id
    )
    await _loi(_nhan(bat, bat.sa1, o1), "VISIT_CHECKED_OUT")
    assert await _cho(bat, o1) == []
