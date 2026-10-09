"""Lịch sử điều phối CHỈ còn thao tác điều phối do người bấm (Tuyền 09/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_lich_su_dieu_phoi_bam_tay_db.py

Mỗi loại sự kiện một lượt riêng, một dòng sổ; chỉ lượt có dòng bấm tay hiện ở
`DispatchService.history`. Check-in, check-out, gọi bộ phận, dây H4 tự xếp phòng
và Nhận tại phòng bình thường (không kéo từ phòng khác) không lên màn — sổ đủ vẫn
ở /audit-log (`v_audit_log`, không đổi).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.dispatch_service import DispatchService
from tests.services.test_truong_ca_3_loi_db import (  # noqa: F401
    CLINIC,
    _loc,
    _luot,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

PHONG_A = str(uuid.uuid4())
PHONG_B = str(uuid.uuid4())

#: (tên ca, event_type, aggregate_type, payload, hiện ở màn?)
CA: list[tuple[str, str, str, dict[str, Any], bool]] = [
    ("checkin", "dispatch.checkin", "visit", {"to_node": "LUOTKHAM-03"}, False),
    ("checkout", "dispatch.checkout", "visit", {"to_node": "LUOTKHAM-15"}, False),
    ("goi_bo_phan", "dispatch.alert_called", "visit", {}, False),
    ("chuyen_buoc", "dispatch.moved", "visit", {"to_node": "LUOTKHAM-15"}, True),
    ("chuyen_phong", "dispatch.transfer_room", "visit", {"to_node": "X"}, True),
    ("ap_tuyen", "dispatch.route_applied", "visit", {"template": "R1"}, True),
    ("tu_xep_doi_cu", "dispatch.assigned", "visit", {"room_id": PHONG_A}, False),
    (
        "xep_tay_doi_cu",
        "dispatch.assigned",
        "visit",
        {"room_id": PHONG_A, "bam_tay": True},
        True,
    ),
    ("h4_tu_xep", "service.routed", "service_order", {"nguon": "tu_dong"}, False),
    ("su_kien_cu_thieu_nguon", "service.routed", "service_order", {}, False),
    ("truong_ca_xep", "service.routed", "service_order", {"nguon": "truong_ca"}, True),
    ("quay_thu_doi", "service.routed", "service_order", {"nguon": "quay_thu"}, True),
    ("ban_kham_xep", "service.routed", "service_order", {"nguon": "khac"}, True),
    (
        "nhan_tai_phong",
        "service.routed",
        "service_order",
        {"nguon": "tai_phong", "to_room_id": PHONG_A},
        False,
    ),
    (
        "nhan_cheo",
        "service.routed",
        "service_order",
        {"nguon": "tai_phong", "from_room_id": PHONG_A, "to_room_id": PHONG_B},
        True,
    ),
    (
        "chuyen_khi_dang_lam",
        "service.room_transferred",
        "service_order",
        {"nguon": "truong_ca", "ly_do": "máy hỏng"},
        True,
    ),
]


async def test_chi_dong_bam_tay_hien_o_lich_su_dieu_phoi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    luot: dict[str, str] = {}
    async with pool.acquire() as conn:
        loc = await _loc(conn)
        for ten, loai, agg, payload, _hien in CA:
            vid = await _luot(conn, loc, ten=f"Khách {ten}", node="LUOTKHAM-03")
            luot[ten] = vid
            await conn.execute(
                """
                INSERT INTO event_log (clinic_id, source, aggregate_type,
                                       aggregate_id, event_type, payload, metadata)
                VALUES ($1::uuid, 'test', $2, $3::uuid, $4, $5::jsonb, '{}'::jsonb)
                """,
                CLINIC,
                agg,
                vid if agg == "visit" else str(uuid.uuid4()),
                loai,
                json.dumps({**payload, "visit_id": vid}),
            )
    rows = await DispatchService(pool).history(clinic_id=CLINIC, limit=500)
    thay = {r["visit_id"] for r in rows}
    hien = {ten for ten, *_x, h in CA if h}
    an = {ten for ten, *_x, h in CA if not h}
    assert {t for t in hien if luot[t] not in thay} == set(), "dòng bấm tay bị mất"
    assert {t for t in an if luot[t] in thay} == set(), "dòng hệ thống/thao tác lọt vào"
