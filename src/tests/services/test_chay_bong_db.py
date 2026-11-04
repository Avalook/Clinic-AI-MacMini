"""Chạy bóng luật "đứng đâu làm việc đó" (Tuyền 04/11/2026).

Mỗi lệnh ghi qua cổng quyền ghi một dòng `quyen_chay_bong`: luật mới sẽ cho hay
chặn, vì sao. Không đổi kết quả quyền, ghi hỏng không làm hỏng lệnh.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import chay_bong
from clinicai.permissions.can import doi_quyen
from clinicai.permissions.cua_quyen import cua_quyen
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan
from tests.services.test_quyen_theo_lich_mo_db import _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dong_cuoi(kb: KichBan, staff_id: str) -> dict[str, object]:
    r = await kb.pool.fetchrow(
        "SELECT * FROM quyen_chay_bong WHERE staff_id = $1::uuid ORDER BY id DESC"
        " LIMIT 1",
        staff_id,
    )
    assert r is not None
    return dict(r)


async def test_chay_bong_ghi_ly_do_khong_doi_ket_qua(kb: KichBan) -> None:
    ai = kb.le_tan
    async with kb.pool.acquire() as conn:
        await ve_goi_mau_cu(conn, ai)
        # Có lego tiếp đón, chưa xếp lịch: luật cũ cho, luật mới sẽ chặn.
        await doi_quyen(conn, ai, "reception.checkin.perform")
    d = await _dong_cuoi(kb, ai.staff_id)
    assert (d["nhom"], d["cho_cu"], d["cho_moi"], d["ly_do"]) == (
        "B",
        True,
        False,
        "khong_lich",
    )

    async with kb.pool.acquire() as conn:
        await _xep(conn, ai.clinic_id, kb.phong_sa, ai)
        await doi_quyen(conn, ai, "reception.checkin.perform")
        assert (await _dong_cuoi(kb, ai.staff_id))["ly_do"] == "phong_thieu"
        # Đúng phòng có chức năng (phòng dịch vụ có ghi bệnh án).
        await doi_quyen(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
        d = await _dong_cuoi(kb, ai.staff_id)
        assert (d["cho_moi"], d["ly_do"]) == (True, "dung_phong")
        assert d["phong_lich"] == [uuid.UUID(kb.phong_sa)]
        # Thực hiện ở phòng khác: luật cũ vẫn chặn y như trước, sổ ghi sai phòng.
        with pytest.raises(SafetyGateError):
            await doi_quyen(conn, ai, "service.execute.start", phong_id=kb.phong_mau)
        d = await _dong_cuoi(kb, ai.staff_id)
        assert (d["cho_cu"], d["cho_moi"], d["ly_do"]) == (False, False, "sai_phong")


async def test_ghi_bong_hong_khong_lam_hong_lenh(
    kb: KichBan, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chay_bong, "_GHI", "SELECT * FROM bang_khong_ton_tai")
    ai = kb.le_tan
    async with kb.pool.acquire() as conn, conn.transaction():
        await doi_quyen(conn, ai, "reception.checkin.perform")
        # Giao dịch của lệnh chính vẫn dùng được (lỗi nằm trong savepoint).
        assert await conn.fetchval("SELECT 1") == 1


async def test_don_cu_hon_45_ngay(kb: KichBan) -> None:
    await kb.pool.execute(
        "INSERT INTO quyen_chay_bong (clinic_id, staff_id, luc, ngay, capability,"
        " nhom, cho_cu, cho_moi, ly_do)"
        " VALUES ($1::uuid, $2::uuid, now() - interval '50 days',"
        " current_date - 50, 'x', 'A', true, true, 'nhom_a')",
        kb.le_tan.clinic_id,
        kb.le_tan.staff_id,
    )
    assert await chay_bong.don_cu(kb.pool) >= 1
    assert not await kb.pool.fetchval(
        "SELECT count(*) FROM quyen_chay_bong WHERE luc < now() - interval '45 days'"
    )


async def test_cua_router_chi_ghi_lenh_ghi(kb: KichBan) -> None:
    ai = kb.le_tan
    cua = cua_quyen("reception.checkin.perform")
    truoc = await kb.pool.fetchval("SELECT count(*) FROM quyen_chay_bong")
    await cua(identity=ai, pool=kb.pool, request=SimpleNamespace(method="GET"))
    assert await kb.pool.fetchval("SELECT count(*) FROM quyen_chay_bong") == truoc
    await cua(identity=ai, pool=kb.pool, request=SimpleNamespace(method="POST"))
    d = await _dong_cuoi(kb, ai.staff_id)
    assert (d["cong"], d["capability"]) == ("cua", "reception.checkin.perform")
