"""Tin `clinicai_changes` mang id lượt (`v`) khi hàng có cột `visit_id` (16/11/2026).

VÌ SAO. Tin cũ chỉ có tên bảng + phòng khám, nên phiếu đang mở của khách B hỏi lại
mỗi khi lượt của khách A đổi. Đo prod 13–16/11: một lượt ghi kéo theo ~15 GET
trong 1,5 giây, đỉnh 443 lượt/phút/người, 1.834 lượt 429. Có `v`, hook theo một
lượt (`useNgheBang(…, { luot })`) bỏ được tin của lượt khác.

Tin vẫn NGHÈO: chỉ thêm một uuid — không dữ liệu hàng, không nội dung bệnh án.
Bảng không có cột lượt thì tin y như cũ (không `v`), và màn coi đó là "có thể là
lượt của mình" — hỏi lại như trước, không bao giờ bỏ sót.
"""

import asyncio
import json

import pytest

from clinicai.core.change_broker import CHANNEL, ChangeBroker
from tests.services.test_luot_kham_service_db import KichBan, _vao_kham

# Module ấy không có fixture `autouse` — nạp qua pytest_plugins chỉ để lấy `kb`.
pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _tin_sau_khi_ghi(kb: KichBan, sql: str, *args: object) -> dict[str, object]:
    broker = ChangeBroker("postgresql://unused")
    q = broker.subscribe(kb.bac_si.clinic_id)
    async with kb.pool.acquire() as listener:
        await listener.add_listener(CHANNEL, broker._on_notify)
        try:
            await kb.pool.execute(sql, *args)
            tin: dict[str, object] = json.loads(
                await asyncio.wait_for(q.get(), timeout=2)
            )
            return tin
        finally:
            await listener.remove_listener(CHANNEL, broker._on_notify)


async def test_bang_co_visit_id_thi_tin_mang_id_luot(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    tin = await _tin_sau_khi_ghi(
        kb, "UPDATE consultation SET updated_at = now() WHERE id = $1::uuid", phien
    )
    assert tin == {"t": "consultation", "c": kb.bac_si.clinic_id, "v": kb.visit_id}


async def test_bang_visit_lay_chinh_khoa_cua_no(kb: KichBan) -> None:
    tin = await _tin_sau_khi_ghi(
        kb,
        "UPDATE visit SET checked_in_at = checked_in_at WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    assert tin == {"t": "visit", "c": kb.bac_si.clinic_id, "v": kb.visit_id}


async def test_bang_khong_co_cot_luot_thi_tin_nhu_cu(kb: KichBan) -> None:
    """`consultation_note` không có `visit_id` → không `v`, không lộ nội dung."""
    phien = await _vao_kham(kb)
    tin = await _tin_sau_khi_ghi(
        kb,
        "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
        " recorded_by) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
        kb.bac_si.clinic_id,
        phien,
        "Nội dung khám bí mật",
        kb.thu_ky.staff_id,
    )
    assert tin == {"t": "consultation_note", "c": kb.bac_si.clinic_id}
