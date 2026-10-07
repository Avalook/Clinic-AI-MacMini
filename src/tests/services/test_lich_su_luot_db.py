"""Popup "Lịch sử khám" + `/patient-list` mở đúng khung (T7, T8 — Tuyền chốt
07/10/2026): MỌI lượt của khách, kể cả không phiếu và lượt Notion; loại dữ liệu
máy chủ quyết; ngày rác không 500."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.v1.routers.ho_so_kham import lich_su
from clinicai.services.danh_sach_benh_nhan_service import _LUOT_SQL
from clinicai.services.lich_su_luot import doc_ngay, loc
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_dich_vu_kham_db import _dung


@pytest.mark.parametrize(
    "rac", ["", "abc", "2026-13-40", "32/01/2026", None, "2026-02-30"]
)
def test_ngay_rac_tra_none(rac: Any) -> None:
    assert doc_ngay(rac) is None


def test_loc_khoang_nguoc_va_loai_dich_vu() -> None:
    ds = [
        {"ngay": "2026-10-01", "dich_vu_id": "a"},
        {"ngay": "2026-10-05", "dich_vu_id": "b"},
        {"ngay": "2026-10-09", "dich_vu_id": "a"},
    ]
    # Khoảng gõ ngược vẫn hiểu; hai đầu tính cả.
    ra = loc(ds, tu=date(2026, 10, 9), den=date(2026, 10, 5), dich_vu_id=None)
    assert [x["ngay"] for x in ra] == ["2026-10-05", "2026-10-09"]
    assert [x["ngay"] for x in loc(ds, tu=None, den=None, dich_vu_id="a")] == [
        "2026-10-01",
        "2026-10-09",
    ]


async def _luot(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    ngay_lui: int,
) -> tuple[str, str]:
    """Một lịch + lượt đã khám xong `ngay_lui` ngày trước."""
    luc = datetime.now(UTC) - timedelta(days=ngay_lui)
    appt = str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'COMPLETED')"
            " RETURNING id::text",
            CLINIC,
            ca["pid"],
            ca["loc"],
            ca["dv"],
            luc,
            luc + timedelta(minutes=15),
        )
    )
    visit = str(
        await pool.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id,"
            " location_id, service_type_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,"
            " 'IN_PROGRESS', $6) RETURNING visit_id::text",
            CLINIC,
            ca["pid"],
            appt,
            ca["loc"],
            ca["dv"],
            luc,
        )
    )
    return appt, visit


@pytest.mark.db
@pytest.mark.asyncio
async def test_lich_su_liet_ke_ca_luot_khong_phieu_va_notion(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    _, v5 = await _luot(pool, ca, 40)
    _, cu = await _luot(pool, ca, 30)
    _, trong = await _luot(pool, ca, 20)
    _, notion = await _luot(pool, ca, 10)
    await pool.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
        CLINIC,
        v5,
        json.dumps({"pk_dx": {"nguon": "USER", "gia_tri": "Viêm"}}),
    )
    await pool.execute(
        "INSERT INTO clinical_form_response (clinic_id, visit_id, service_code,"
        " form_data) VALUES ($1::uuid, $2::uuid, 'PK', '{}'::jsonb)",
        CLINIC,
        cu,
    )
    lan_nhap = await pool.fetchval(
        "INSERT INTO lich_su_notion.lan_nhap (clinic_id, goi) VALUES ($1::uuid, 'thu')"
        " RETURNING id",
        CLINIC,
    )
    nid = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO lich_su_notion.luot_kham (notion_id, clinic_id,"
        " clinic_patient_id, lan_nhap_id, ngay_kham, nguon_ngay)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, current_date - 10, 'thu')",
        nid,
        CLINIC,
        ca["pid"],
        lan_nhap,
    )
    lan_chuyen = await pool.fetchval(
        "INSERT INTO lich_su_notion.lan_chuyen (clinic_id) VALUES ($1::uuid)"
        " RETURNING id",
        CLINIC,
    )
    await pool.execute(
        "INSERT INTO lich_su_notion.luot_that (notion_id, clinic_id, lan_chuyen_id,"
        " visit_id) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
        nid,
        CLINIC,
        lan_chuyen,
        notion,
    )

    goi = await lich_su(
        clinic_patient_id=UUID(ca["pid"]),
        tu=None,
        den=None,
        dich_vu_id=None,
        identity=ca["bs"],
        pool=pool,
    )
    loai = {x["visit_id"]: x["loai_du_lieu"] for x in goi["luot"]}
    assert loai == {v5: "v5", cu: "cu", trong: "trong", notion: "notion"}
    # Mới nhất trước; ngày có khám đủ 4 ngày (lịch chấm xanh).
    assert [x["visit_id"] for x in goi["luot"]] == [notion, trong, cu, v5]
    assert len(goi["ngay_co_kham"]) == 4

    # Ngày rác: bỏ lọc, không 500.
    rac = await lich_su(
        clinic_patient_id=UUID(ca["pid"]),
        tu="abc",
        den="32/13/2026",
        dich_vu_id=None,
        identity=ca["bs"],
        pool=pool,
    )
    assert len(rac["luot"]) == 4
    # Lọc đúng một ngày.
    mot = await lich_su(
        clinic_patient_id=UUID(ca["pid"]),
        tu=goi["luot"][1]["ngay"],
        den=goi["luot"][1]["ngay"],
        dich_vu_id=None,
        identity=ca["bs"],
        pool=pool,
    )
    assert [x["visit_id"] for x in mot["luot"]] == [trong]

    # /patient-list: mỗi lượt mang visit_id + loại dữ liệu cho khung đọc.
    rows = await pool.fetch(_LUOT_SQL, CLINIC, [ca["pid"]], 50)
    theo_luot = {r["visit_id"]: r["loai_du_lieu"] for r in rows if r["visit_id"]}
    assert theo_luot == {v5: "v5", cu: "cu", trong: "trong", notion: "notion"}
