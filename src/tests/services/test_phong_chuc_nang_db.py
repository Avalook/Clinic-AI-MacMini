"""Chức năng của phòng — "đứng đâu làm việc đó" (Tuyền 04/11/2026).

Migration 20261104800000: `v_quyen_thuc_te` đọc `phong_chuc_nang` thay bảng tra
tiền tố. Ngày đầu phải y hệt — bài đầu so hai cách trên toàn bộ phòng của DB.
"""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache, nhom_viec
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import KHOI
from clinicai.services import phong_chuc_nang_service
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan, _nguoi
from tests.services.test_quyen_theo_lich_mo_db import _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

# Cách CŨ (bản 20260929000001): việc của phòng × bảng tra, tiền tố dài nhất,
# + phòng đối tác. Chép nguyên để so.
_CU = """
WITH khop AS (
    SELECT DISTINCT ON (rn.room_id, rn.node_code) rn.room_id, b.tien_to
      FROM clinic_room_node rn
      JOIN (SELECT DISTINCT tien_to FROM quyen_theo_lich_bang()) b
        ON rn.node_code LIKE b.tien_to || '%'
     ORDER BY rn.room_id, rn.node_code, length(b.tien_to) DESC
)
SELECT DISTINCT k.room_id, b.work_pack, b.theo_phong
  FROM khop k JOIN quyen_theo_lich_bang() b ON b.tien_to = k.tien_to
UNION
SELECT r.id, 'doi_tac', false FROM clinic_room r WHERE r.la_doi_tac
"""


async def test_gieo_san_y_het_bang_tra_cu(kb: KichBan) -> None:
    cu = {tuple(r) for r in await kb.pool.fetch(_CU)}
    moi = {
        tuple(r)
        for r in await kb.pool.fetch(
            "SELECT room_id, work_pack, theo_phong FROM phong_chuc_nang"
        )
    }
    assert cu, "DB test phải có phòng gắn việc"
    assert moi == cu


async def test_phong_moi_gan_viec_thi_tick_san(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        room = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code)"
            " VALUES ($1::uuid, $2::uuid, 'T-PCN-1', 'Quầy thử', 'LUOTKHAM-01')"
            " RETURNING id::text",
            kb.le_tan.clinic_id,
            kb.location_id,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " SELECT clinic_id, $1::uuid, 'LUOTKHAM-01' FROM clinic_room"
            "  WHERE id = $1::uuid",
            room,
        )
        co = {
            r["work_pack"]
            for r in await conn.fetch(
                "SELECT work_pack FROM phong_chuc_nang WHERE room_id = $1::uuid", room
            )
        }
    assert co == {
        "tiep_don",
        "thu_tien_dv",
        "chon_dich_vu",
        "dieu_phoi",
        "thu_tien_thuoc",
    }


async def test_bo_tick_thi_mat_quyen_tick_lai_thi_co(kb: KichBan) -> None:
    ai = kb.le_tan
    async with kb.pool.acquire() as conn:
        await ve_goi_mau_cu(conn, ai)
        await _xep(conn, ai.clinic_id, kb.phong_sa, ai)
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    async with kb.pool.acquire() as conn:
        assert await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
    kq = await phong_chuc_nang_service.doi_chuc_nang(
        kb.pool, identity=ql, room_id=kb.phong_sa, work_pack="thuc_hien", bat=False
    )
    assert not next(c for c in kq["chon"] if c["work_pack"] == "thuc_hien")["bat"]
    cache.quen_het()
    async with kb.pool.acquire() as conn:
        assert not await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
    await phong_chuc_nang_service.doi_chuc_nang(
        kb.pool, identity=ql, room_id=kb.phong_sa, work_pack="thuc_hien", bat=True
    )
    async with kb.pool.acquire() as conn:
        assert await can(conn, ai, "service.execute.start", phong_id=kb.phong_sa)
        # Tick lại vẫn chỉ đúng phòng ấy.
        assert not await can(conn, ai, "service.execute.start", phong_id=kb.phong_mau)


async def test_doi_chuc_nang_ngoai_nhom_b_bi_tu_choi(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    with pytest.raises(ValidationError):
        await phong_chuc_nang_service.doi_chuc_nang(
            kb.pool, identity=ql, room_id=kb.phong_sa, work_pack="bao_cao", bat=True
        )
    with pytest.raises(SafetyGateError):
        await phong_chuc_nang_service.doi_chuc_nang(
            kb.pool,
            identity=kb.le_tan,
            room_id=kb.phong_sa,
            work_pack="kham",
            bat=True,
        )


async def test_doc_chuc_nang_co_nhan_tieng_viet(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        ql = await _nguoi(conn, kb.location_id, "MANAGEMENT")
    kq = await phong_chuc_nang_service.doc_chuc_nang(
        kb.pool, identity=ql, room_id=kb.phong_sa
    )
    ma = [c["work_pack"] for c in kq["chon"]]
    assert set(ma) == set(nhom_viec.NHOM_B)
    thuc_hien = next(c for c in kq["chon"] if c["work_pack"] == "thuc_hien")
    assert thuc_hien["ten"] == KHOI["thuc_hien"].ten and thuc_hien["chi_dung_phong"]


async def test_ba_nhom_khong_chong_nhau() -> None:
    assert not nhom_viec.NHOM_A & nhom_viec.NHOM_B
    assert nhom_viec.NHOM_A | nhom_viec.NHOM_B <= set(KHOI)
    assert nhom_viec.nhom_cua("bao_cao") == "C"
    assert nhom_viec.nhom_cua("khong_co") == "?"
