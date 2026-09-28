"""Xếp vào phòng hôm nay = toàn quyền của phòng ấy (Tuyền 28/09/2026).

"Được xếp vào phòng là chức năng và quyền hạn max rồi mà, lego phải thế chứ."
Lỗi thật: điều dưỡng xếp đứng Phòng thủ thuật 1 bấm "Bắt đầu" bị báo chưa có
quyền — quyền phòng chỉ đến từ lego theo kỹ năng. Nay `v_quyen_thuc_te` cộng
thêm quyền theo lịch hôm nay (migration 20260928000097).
"""

from __future__ import annotations

import pytest

from clinicai.permissions.can import can, quyen_hieu_luc
from clinicai.permissions.catalogue import MAN
from tests.services.test_luot_kham_service_db import KichBan
from tests.services.test_quyen_theo_lich_mo_db import _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_bang_tra_khop_danh_muc_lego(kb: KichBan) -> None:
    """Khối trong bảng tra SQL phải đúng khối của lego trong catalogue.py."""
    rows = await kb.pool.fetch("SELECT * FROM quyen_theo_lich_bang()")
    theo_lego: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        theo_lego.setdefault((r["tien_to"], r["lego"]), set()).add(r["work_pack"])
        if r["theo_phong"]:
            assert MAN[r["lego"]].khoi_theo_phong == r["work_pack"]
    for (_tien_to, lego), khoi in theo_lego.items():
        assert khoi == set(MAN[lego].khoi), lego


async def test_xep_vao_phong_thi_lam_duoc_o_phong_ay(kb: KichBan) -> None:
    ai = kb.le_tan  # vai lễ tân, KHÔNG có lego Phòng dịch vụ nào
    async with kb.pool.acquire() as conn:
        assert not await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
        await _xep(conn, ai.clinic_id, kb.phong_sa, ai)
        # Đúng phòng được xếp → toàn quyền phòng dịch vụ.
        assert await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
        assert await can(conn, ai, "service.execute.complete", phong_id=kb.phong_sa)
        assert await can(conn, ai, "result.review.approve")
        # Phòng khác (không xếp) → vẫn không.
        assert not await can(conn, ai, "service.execute.start", phong_id=kb.phong_mau)
        # Thanh bên thấy màn Phòng dịch vụ.
        assert "service.execute.start" in await quyen_hieu_luc(conn, ai)


async def test_lich_bi_tu_choi_khong_mo_quyen(kb: KichBan) -> None:
    ai = kb.le_tan
    async with kb.pool.acquire() as conn:
        await _xep(conn, ai.clinic_id, kb.phong_sa, ai)
        await conn.execute(
            "UPDATE work_roster SET status = 'REJECTED' WHERE staff_id = $1::uuid",
            ai.staff_id,
        )
        assert not await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
