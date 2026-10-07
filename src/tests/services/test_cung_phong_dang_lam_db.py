"""Hai chỉ định CÙNG một phòng, bấm Bắt đầu DV2 khi DV1 còn đang làm (07/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_cung_phong_dang_lam_db.py

Không phải "khách ở phòng khác": không nhận chéo, không đóng hàng DV1, không nhãn
đỏ. Lần gọi thường trả 409 CUNG_PHONG_DANG_LAM (kèm tên DV1); gửi lại với
`xong_truoc` = một lệnh, cùng giao dịch: `service.completed` DV1 + `service.started`
DV2, cùng người bấm. Hoàn tác Xong DV1 vẫn chạy.
"""

from __future__ import annotations

import uuid

import pytest

from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.services.test_nhan_tai_phong_db import (  # noqa: F401
    _bat_dau,
    _cd_o,
    _loi,
    _nhan,
    _o_khach,
    _sk,
    _song,
    bat,
)
from tests.services.test_service_routing_db import RB, rb  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _bat_dau_xong_truoc(b: RB, oid: str) -> dict[str, object]:
    r = await b.pool.fetchrow(
        "SELECT execution_revision, routing_revision FROM service_order"
        " WHERE id = $1::uuid",
        oid,
    )
    assert r is not None
    return await ServiceExecutionService(b.pool).bat_dau(
        order_id=oid,
        expected_execution_revision=int(r["execution_revision"]),
        expected_routing_revision=int(r["routing_revision"]),
        identity=b.bac_si,
        idempotency_key=str(uuid.uuid4()),
        xong_truoc=True,
    )


async def test_cung_phong_hoi_roi_xong_mot_bat_dau_hai(bat: RB) -> None:  # noqa: F811
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa1)
    await _nhan(bat, bat.sa1, o1, o2)
    lam1 = await _bat_dau(bat, o1)

    loi = await _loi(_bat_dau(bat, o2), "CUNG_PHONG_DANG_LAM")
    ten1 = await bat.pool.fetchval(
        "SELECT service_name FROM service_order WHERE id = $1::uuid", o1
    )
    assert loi.chi_tiet["dich_vu"] == ten1 and loi.chi_tiet["order_id"] == o1
    # Không coi như khách ở phòng khác: hàng DV1 còn "đang làm", không rời phòng,
    # không nhãn đỏ, DV2 vẫn chờ.
    assert (await _song(bat, o1))["status"] == "serving"  # type: ignore[index]
    assert await _sk(bat, o1, "service.room_released") == []
    assert await _sk(bat, o1, "service.patient_moved") == []
    o = await _o_khach(bat, bat.sa1)
    assert (o[o1]["trang_thai"], o[o2]["trang_thai"]) == ("lam", "cho")

    kq = await _bat_dau_xong_truoc(bat, o2)
    assert kq["execution_status"] == "IN_PROGRESS"
    st = {
        r["id"]: r["execution_status"]
        for r in await bat.pool.fetch(
            "SELECT id::text, execution_status FROM service_order"
            " WHERE id = ANY($1::uuid[])",
            [o1, o2],
        )
    }
    assert st == {o1: "COMPLETED", o2: "IN_PROGRESS"}
    [xong] = await _sk(bat, o1, "service.completed")
    assert xong["attempt_id"] == lam1["attempt_id"]
    [bd] = await _sk(bat, o2, "service.started")
    assert bd["attempt_id"] == kq["attempt_id"]
    nguoi = await bat.pool.fetch(
        "SELECT DISTINCT actor_staff_id::text AS ai FROM domain_event"
        " WHERE aggregate_id = ANY($1::uuid[])"
        "   AND event_type IN ('service.completed', 'service.started')",
        [o1, o2],
    )
    assert [r["ai"] for r in nguoi] == [bat.bac_si.staff_id]
    assert await _sk(bat, o1, "service.room_released") == []

    # Hoàn tác Xong DV1: về đang làm, DV2 không bị đụng.
    await HoanTacService(bat.pool).hoan_tac_xong_dich_vu(
        order_id=o1, identity=bat.bac_si
    )
    o = await _o_khach(bat, bat.sa1)
    assert (o[o1]["trang_thai"], o[o2]["trang_thai"]) == ("lam", "lam")


async def test_khac_phong_van_theo_luat_cu(bat: RB) -> None:  # noqa: F811
    o1 = await _cd_o(bat, bat.sa1)
    o2 = await _cd_o(bat, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    await _nhan(bat, bat.sa2, o2)
    await _bat_dau(bat, o1)
    await _loi(_bat_dau(bat, o2), "PATIENT_BUSY")
