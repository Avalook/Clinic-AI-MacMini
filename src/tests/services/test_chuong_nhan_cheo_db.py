"""Chuông NHẬN CHÉO — phòng A quên Xong (Tuyền chốt 07/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_chuong_nhan_cheo_db.py

Bên nghe `chuong_nhan_cheo`: phòng B nhận khách lúc phòng A còn ĐANG LÀM → chuông
đích danh người bấm Bắt đầu ở A + người trực A hôm nay (không trùng); lần làm
Xong / Gián đoạn / huỷ Bắt đầu → chuông tự đóng. A chỉ đang CHỜ → không chuông.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.events.catalogue import CHUONG_NHAN_CHEO
from clinicai.events.consumers import chuong_nhan_cheo as cnc
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_nhan_tai_phong_db import (  # noqa: F401
    _bat_dau,
    _cd_o,
    _nhan,
    _xong,
    bat,
)
from tests.services.test_service_routing_db import RB, rb  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _truc_phong(b: RB, room_id: str, staff_id: str) -> None:
    """Người này trực phòng hôm nay (vị trí của phòng + lịch cả ngày)."""
    ma = f"VT-{b.duoi}-{uuid.uuid4().hex[:6]}"
    await b.pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id, sort)"
        " VALUES ($1::uuid, $2, $2, 'DIEU_DUONG', $3::uuid, 1)",
        CLINIC,
        ma,
        room_id,
    )
    await b.pool.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, 'FULL', $2,"
        " $3::uuid, 'Test', 'APPROVED'"
        " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d) x",
        CLINIC,
        ma,
        staff_id,
    )


async def _chuong(b: RB, oid: str) -> list[asyncpg.Record]:
    """Chuông nhận chéo trỏ tới chỉ định này."""
    await chay_ben_nhan(b.pool, CHUONG_NHAN_CHEO)
    return list(
        await b.pool.fetch(
            "SELECT nguoi_nhan_staff_id::text AS ai, tieu_de, duong_dan, nguon_id,"
            "       da_xu_ly_luc, da_xu_ly_boi::text AS boi, ghi_chu_xu_ly"
            "  FROM thong_bao WHERE clinic_id = $1::uuid AND nguon = $2"
            "   AND duong_dan LIKE '%' || $3"
            " ORDER BY tao_luc, nguoi_nhan_staff_id",
            CLINIC,
            cnc.NGUON,
            oid,
        )
    )


async def _quen_xong(b: RB) -> tuple[str, dict[str, Any], str]:
    """A (sa1) Bắt đầu o1 rồi quên Xong; B (sa2) nhận khách + xác nhận."""
    o1 = await _cd_o(b, b.sa1)
    o2 = await _cd_o(b, b.sa2)
    await _nhan(b, b.sa1, o1)
    lam = await _bat_dau(b, o1)
    await _nhan(b, b.sa2, o2, xac_nhan=True)
    return o1, lam, o2


async def _ten(b: RB, bang: str, id_: str, cot: str = "name") -> str:
    return str(
        await b.pool.fetchval(
            f"SELECT {cot} FROM {bang} WHERE id = $1::uuid",  # noqa: S608
            id_,
        )
    )


async def test_nhan_cheo_khi_dang_lam_reo_dung_nguoi_roi_xong_tu_dong(bat: RB) -> None:  # noqa: F811
    async with bat.pool.acquire() as conn:
        dd = await _nguoi(conn, bat.loc, "NURSE_ULTRASOUND")
    # Người trực phòng A: điều dưỡng + chính bác sĩ bấm Bắt đầu (không trùng).
    await _truc_phong(bat, bat.sa1, dd.staff_id)
    await _truc_phong(bat, bat.sa1, bat.bac_si.staff_id)
    o1, lam, _ = await _quen_xong(bat)

    ds = await _chuong(bat, o1)
    assert sorted(r["ai"] for r in ds) == sorted([bat.bac_si.staff_id, dd.staff_id])
    r = ds[0]
    assert r["nguon_id"] == cnc.nguon_id(lam["attempt_id"])
    assert r["duong_dan"] == f"/phong/{bat.sa1}?chi_dinh={o1}"
    ma_khach = await bat.pool.fetchval(
        "SELECT p.patient_code FROM visit v JOIN patient p"
        "  ON p.clinic_patient_id = v.clinic_patient_id"
        " WHERE v.visit_id = $1::uuid",
        bat.visit_id,
    )
    for phan in (
        str(ma_khach),
        await _ten(bat, "clinic_room", bat.sa2),
        await _ten(bat, "clinic_room", bat.sa1),
        await _ten(bat, "service_order", o1, "service_name"),
        "bấm Xong hoặc Gián đoạn",
    ):
        assert phan in r["tieu_de"]
    assert all(x["da_xu_ly_luc"] is None for x in ds)

    # Giao tin lặp (worker chết giữa chừng, nhận lại): không nhân đôi.
    await bat.pool.execute(
        "UPDATE event_delivery SET status = 'RETRY', next_attempt_at = now(),"
        "       processed_at = NULL"
        " WHERE consumer = $1 AND event_id = (SELECT event_id FROM domain_event"
        "   WHERE aggregate_id = $2::uuid AND event_type = 'service.room_released')",
        CHUONG_NHAN_CHEO,
        o1,
    )
    assert len(await _chuong(bat, o1)) == 2

    # A bấm Xong muộn → mọi chuông của lần làm ấy tự đóng, ghi người bấm.
    await _xong(bat, o1, lam["attempt_id"])
    ds = await _chuong(bat, o1)
    assert len(ds) == 2
    assert all(x["da_xu_ly_luc"] is not None for x in ds)
    assert {x["boi"] for x in ds} == {bat.bac_si.staff_id}
    assert {x["ghi_chu_xu_ly"] for x in ds} == {"Phòng đã bấm Xong"}


async def test_gian_doan_hoac_huy_bat_dau_dong_chuong(bat: RB) -> None:  # noqa: F811
    exe = ServiceExecutionService(bat.pool)
    o1, lam, _ = await _quen_xong(bat)
    [r] = await _chuong(bat, o1)
    assert r["ai"] == bat.bac_si.staff_id and r["da_xu_ly_luc"] is None
    rev = await bat.pool.fetchval(
        "SELECT execution_revision FROM service_order WHERE id = $1::uuid", o1
    )
    await exe.huy_bat_dau(
        order_id=o1,
        attempt_id=lam["attempt_id"],
        expected_execution_revision=int(rev),
        identity=bat.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )
    [r] = await _chuong(bat, o1)
    assert r["ghi_chu_xu_ly"] == "Phòng đã huỷ Bắt đầu"

    # Khách khác: Gián đoạn cũng đóng.
    o3, lam3, _ = await _quen_xong(bat)
    [r] = await _chuong(bat, o3)
    assert r["da_xu_ly_luc"] is None
    rev = await bat.pool.fetchval(
        "SELECT execution_revision FROM service_order WHERE id = $1::uuid", o3
    )
    await exe.gian_doan(
        order_id=o3,
        attempt_id=lam3["attempt_id"],
        expected_execution_revision=int(rev),
        ly_do="EQUIPMENT_FAILURE",
        ghi_chu=None,
        identity=bat.bac_si,
        idempotency_key=str(uuid.uuid4()),
    )
    [r] = await _chuong(bat, o3)
    assert r["ghi_chu_xu_ly"] == "Phòng đã bấm Gián đoạn"


async def test_a_chi_dang_cho_thi_khong_chuong(bat: RB) -> None:  # noqa: F811
    o1 = await _cd_o(bat, bat.sa1, bat.sa2)
    await _nhan(bat, bat.sa1, o1)
    await _nhan(bat, bat.sa2, o1, xac_nhan=True)
    assert await _chuong(bat, o1) == []


async def test_lan_lam_da_dong_truoc_khi_tin_toi_thi_khong_chuong(bat: RB) -> None:  # noqa: F811
    """Tin tới trễ (A đã Xong trước khi bên nghe chạy): không réo chuyện đã xong."""
    o1, lam, _ = await _quen_xong(bat)
    await _xong(bat, o1, lam["attempt_id"])
    assert await _chuong(bat, o1) == []


async def test_nguoi_nhan_khong_trung() -> None:
    assert cnc.nguoi_nhan("a", ["b", "a", "c", "b"]) == ["a", "b", "c"]
    assert cnc.nguoi_nhan(None, ["b"]) == ["b"]
