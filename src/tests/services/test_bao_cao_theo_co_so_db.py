"""Báo cáo tách theo CƠ SỞ (08/10/2026 — mở cơ sở Hào Nam), với database thật.

Kịch bản trên cùng phòng khám: cơ sở L1 (cơ sở đầu, nơi ``tao_quay`` đặt lịch)
và cơ sở mới L2.

* lượt A: ``visit.location_id`` TRỐNG, lịch hẹn ở L1 → thuộc L1 (lấy theo lịch).
* lượt B: lịch hẹn ở L1 nhưng ``visit.location_id`` = L2 → thuộc L2 (lượt thắng).
* lượt C: ``visit.location_id`` trống, lịch hẹn chuyển sang L2 → thuộc L2.

Mỗi lượt thu 150k. DB dùng chung với bài khác cùng ngày → so HIỆU (sau − trước).
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.bao_cao_cuoi_ngay_service import (
    BaoCaoCuoiNgayService,
    csv_bao_cao,
)
from clinicai.services.co_so_bao_cao import KHONG_KHOP
from clinicai.services.reports_service import ReportsService, toan_canh, tong_quan
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt, _xm

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db]  # asyncio chế độ AUTO; bài cuối là hàm thường

_KHOA = ("thu", "huy", "hoan", "thuc_thu")


def _phan(bc: dict[str, Any], loc: str | None) -> dict[str, Any]:
    return next(o for o in bc["theo_co_so"] if o["location_id"] == loc)


def _cong(bc: dict[str, Any], khoa: str) -> int:
    return sum(int(o["tong"][khoa]) for o in bc["theo_co_so"])


async def test_bao_cao_cuoi_ngay_tach_theo_co_so(pool: asyncpg.Pool) -> None:
    svc = BaoCaoCuoiNgayService(pool)
    l1 = str(
        await pool.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )
    duoi = uuid.uuid4().hex[:8]
    l2 = str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name)"
            " VALUES ($1::uuid, $2, $3) RETURNING id::text",
            CLINIC,
            f"HN-{duoi}",
            f"Hào Nam {duoi}",
        )
    )
    qa = await tao_quay(pool)
    ql = await _nguoi_vai(qa, "MANAGEMENT")
    truoc = await svc.bao_cao(identity=ql)
    truoc_1 = await svc.bao_cao(identity=ql, co_so=l1)
    assert truoc["co_so"] is None and truoc_1["co_so"] == l1
    assert truoc_1["theo_co_so"] == []
    # Cơ sở chưa có số nào vẫn hiện trong bảng tách (số 0).
    assert _phan(truoc, l2)["tong"]["thu"] == 0
    assert _phan(truoc, l2)["ten"] == f"Hào Nam {duoi}"

    await _thu_pt(qa, "CASH")
    qb = await tao_quay(pool)
    ck = await _thu_pt(qb, "TRANSFER")
    await _xm(qb, ck["payment_cycle_id"], f"FT{duoi}")
    await pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        qb.visit_id,
        l2,
    )
    qc = await tao_quay(pool)
    await _thu_pt(qc, "CASH")
    await pool.execute(
        "UPDATE appointment SET location_id = $2::uuid WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        qc.visit_id,
        l2,
    )

    sau = await svc.bao_cao(identity=ql)
    # Tổng giữ nguyên khuôn; tiền các phần cộng lại ĐÚNG BẰNG tổng.
    for k in _KHOA:
        assert _cong(sau, k) == sau["tong"][k], k
    assert (
        sum(o["khach"]["so_luot_kham"] for o in sau["theo_co_so"])
        == (sau["khach"]["so_luot_kham"])
    )
    assert sau["tong"]["thu"] - truoc["tong"]["thu"] == 450_000
    # A về L1 theo lịch hẹn; B (lượt thắng lịch) và C (theo lịch) về L2.
    assert _phan(sau, l1)["tong"]["thu"] - _phan(truoc, l1)["tong"]["thu"] == 150_000
    assert _phan(sau, l2)["tong"]["thu"] == 300_000
    assert _phan(sau, l2)["khach"]["so_luot_kham"] == 2
    ck = {o["ma"]: o["thu"] for o in _phan(sau, l2)["theo_hinh_thuc"]}
    assert (ck["CASH"], ck["TRANSFER"]) == (150_000, 150_000)

    # Lọc một cơ sở: chỉ số của cơ sở ấy, khớp đúng phần của nó khi tách.
    chi_2 = await svc.bao_cao(identity=ql, co_so=l2)
    assert chi_2["ten_co_so"] == f"Hào Nam {duoi}"
    assert {k: chi_2["tong"][k] for k in _KHOA} == {
        k: _phan(sau, l2)["tong"][k] for k in _KHOA
    }
    assert chi_2["khach"]["so_luot_kham"] == 2
    chi_1 = await svc.bao_cao(identity=ql, co_so=l1)
    assert chi_1["tong"]["thu"] - truoc_1["tong"]["thu"] == 150_000

    # CSV: khối theo cơ sở + dòng Tổng; lọc một cơ sở thì ghi tên cơ sở.
    csv = csv_bao_cao(sau)
    assert f"Hào Nam {duoi},2,2,300000,0,0,300000" in csv
    assert f"\r\nTổng,{sau['khach']['so_luot_kham']}," in csv
    assert f"Cơ sở,Hào Nam {duoi}" in csv_bao_cao(chi_2)

    # Mã cơ sở RÁC: không ném, số 0 — không lặng lẽ rơi về "tất cả".
    rac = await svc.bao_cao(identity=ql, co_so="không-phải-uuid")
    assert rac["co_so"] == KHONG_KHOP
    assert rac["tong"]["thu"] == 0 and rac["theo_co_so"] == []
    assert rac["khach"]["so_luot_kham"] == 0
    assert "Không có cơ sở này" in csv_bao_cao(rac)


async def test_bao_cao_van_hanh_loc_theo_co_so(pool: asyncpg.Pool) -> None:
    qa = await tao_quay(pool)  # lịch hẹn hôm nay ở cơ sở đầu, lượt không cơ sở
    ql = await _nguoi_vai(qa, "MANAGEMENT")
    l1 = str(
        await pool.fetchval(
            "SELECT location_id::text FROM appointment WHERE id ="
            " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
            qa.visit_id,
        )
    )
    tat_ca = await tong_quan(pool, identity=ql)
    chi_1 = await tong_quan(pool, identity=ql, location_id=l1)
    rac = await tong_quan(pool, identity=ql, location_id="rác")
    assert chi_1["hom_nay"] >= 1
    assert tat_ca["hom_nay"] >= chi_1["hom_nay"]
    assert rac["hom_nay"] == 0 and rac["theo_bac_si"] == []
    assert len(rac["theo_ngay"]) == 7

    tc_1 = await toan_canh(pool, identity=ql, location_id=l1)
    assert tc_1["counts"]["visitsToday"] >= 1  # lượt trống cơ sở → theo lịch hẹn
    tc_rac = await toan_canh(pool, identity=ql, location_id="rác")
    assert tc_rac["counts"]["visitsToday"] == 0
    assert tc_rac["staff"], "nhân sự là của cả phòng khám — không lọc"

    svc = ReportsService(pool)
    kenh = await svc.booking_channels(identity=ql, days=30, location_id="rác")
    assert all(c["count"] == 0 for c in kenh["items"])
    assert (kenh["unset"], kenh["unknown"]) == (0, 0)
    kpi = await svc.kpi_dat_lich_theo_nhan_vien(identity=ql, location_id="rác")
    assert kpi["items"] == []
    assert (await svc.kpi_dat_lich_theo_nhan_vien(identity=ql, location_id=l1))["moc"]


def test_cac_cua_bao_cao_nhan_co_so() -> None:
    from clinicai.api.v1.routers import reports

    for p in (
        "/reports/booking-channels",
        "/reports/kpi-dat-lich",
        "/reports/tong-quan",
        "/reports/toan-canh",
        "/reports/cuoi-ngay",
        "/reports/cuoi-ngay.csv",
    ):
        route = next(r for r in reports.router.routes if getattr(r, "path", "") == p)
        ten = {q.name for q in route.dependant.query_params}  # type: ignore[attr-defined]
        assert "co_so" in ten, p
