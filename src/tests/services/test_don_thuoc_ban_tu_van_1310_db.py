"""Đơn thuốc điền tiếp ở BÀN TƯ VẤN (Tuyền 13/10/2026).

Bác sĩ chính điền dở / vội → bác sĩ tư vấn làm tiếp ĐÚNG đơn của lượt đó. Kiểm:
người có lego Tư vấn lưu được dù không đi kèm bác sĩ chính hôm nay; ghi đúng
người bấm (không "làm thay"); sự kiện mang cờ `ke_tai_tu_van`; người không có
lego Tư vấn vẫn bị cổng ca trực chặn; đọc đơn trả người kê để phiếu in chọn chân ký.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from tests.services.test_ca_truc_lam_sang_db import _noi_tai_khoan, _truc, _vi_tri
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_luot_kham_service_db import _nguoi as _nguoi_loc
from tests.services.test_phieu_kham_db import (
    _luot,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _dong(ten: str, id_: str | None = None, **them: str) -> dict[str, Any]:
    return {
        "id": id_,
        "drug_catalog_id": None,
        "drug_name": ten,
        "quantity": "1 hộp",
        "dosage": "Uống — Ngày 1 lần",
        "caution": "",
        **them,
    }


async def _canh(pool: asyncpg.Pool) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " floor, is_active, accepting, sort) VALUES ($1::uuid, $2::uuid,"
            " $3, $3, 'KHAM-PHUKHOA', '1', true, true, 999) RETURNING id::text",
            CLINIC,
            loc,
            f"P-DT-{uuid.uuid4().hex[:7]}",
        )
        bs = await _nguoi_loc(conn, loc, "DOCTOR")
        bs_tu_van = await _nguoi_loc(conn, loc, "DOCTOR")
        khong_lego = await _nguoi_loc(conn, loc, "TKYK")
        for ai in (bs, bs_tu_van, khong_lego):
            await _noi_tai_khoan(conn, ai)
        await _truc(conn, await _vi_tri(conn, phong, "BAC_SI", 1, 1), bs.staff_id)
        # TKYK này CHỈ có quyền ghi bệnh án, không có lego Tư vấn.
        await conn.execute(
            "UPDATE capability_grant SET revoked_at = now(), revoked_by = staff_id"
            " WHERE clinic_id=$1::uuid AND staff_id=$2::uuid"
            "   AND capability='clinical.intake.perform' AND revoked_at IS NULL",
            CLINIC,
            khong_lego.staff_id,
        )
        cache.quen(CLINIC, khong_lego.staff_id)
        luot = await _luot(conn, bs)
    return {
        "svc": PhieuKhamService(pool, kiem_quyen=kiem_quyen_core),
        "bs": bs,
        "tu_van": bs_tu_van,
        "khong_lego": khong_lego,
        "luot": luot["visit"],
    }


async def _su_kien(pool: asyncpg.Pool, visit: str) -> list[Any]:  # noqa: F811
    rows: list[Any] = await pool.fetch(
        "SELECT payload, actor_staff_id::text AS ai, on_behalf_of::text AS thay"
        "  FROM domain_event WHERE event_type = 'prescription.saved'"
        "   AND aggregate_id = $1::uuid ORDER BY occurred_at",
        visit,
    )
    return rows


async def test_bac_si_tu_van_dien_tiep_dung_don_cua_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    c = await _canh(pool)
    svc, visit = c["svc"], c["luot"]
    # Bác sĩ chính điền dở một thuốc.
    await svc.luu_don_thuoc(
        visit_id=visit, dong=[_dong("Duphaston")], ly_do=None, identity=c["bs"]
    )
    don = await svc.doc_don_thuoc(visit_id=visit, identity=c["bs"])
    assert len(don) == 1

    # Bác sĩ tư vấn (không trong ca của bác sĩ chính) thêm thuốc + sửa lời dặn
    # dòng cũ: vẫn MỘT đơn, không đẻ đơn thứ hai.
    sua = _dong("Duphaston", don[0]["id"], dosage="Uống — Ngày 2 lần")
    await svc.luu_don_thuoc(
        visit_id=visit,
        dong=[sua, _dong("Vitamin D3")],
        ly_do=None,
        identity=c["tu_van"],
    )
    don = await svc.doc_don_thuoc(visit_id=visit, identity=c["bs"])
    assert [d["drug_name_raw"] for d in don] == ["Duphaston", "Vitamin D3"]
    assert don[0]["dosage_instructions"] == "Uống — Ngày 2 lần"
    # Người kê = người thật kê: dòng cũ của bác sĩ chính, dòng mới của bác sĩ tư vấn.
    assert [d["nguoi_ke_id"] for d in don] == [
        c["bs"].staff_id,
        c["tu_van"].staff_id,
    ]
    assert [d["nguoi_ke_la_bac_si"] for d in don] == [True, True]


async def test_su_kien_ke_tai_tu_van_khong_lam_thay_bac_si_chinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    c = await _canh(pool)
    await c["svc"].luu_don_thuoc(
        visit_id=c["luot"], dong=[_dong("Duphaston")], ly_do=None, identity=c["bs"]
    )
    don = await c["svc"].doc_don_thuoc(visit_id=c["luot"], identity=c["bs"])
    await c["svc"].luu_don_thuoc(
        visit_id=c["luot"],
        dong=[_dong("Duphaston", don[0]["id"]), _dong("Vitamin D3")],
        ly_do=None,
        identity=c["tu_van"],
    )
    cu, moi = await _su_kien(pool, c["luot"])
    assert not json.loads(cu["payload"]).get("ke_tai_tu_van")
    assert json.loads(moi["payload"])["ke_tai_tu_van"] is True
    # Người bấm tự đứng tên, không gắn "làm thay bác sĩ chính".
    assert moi["ai"] == c["tu_van"].staff_id and moi["thay"] is None


async def test_khong_co_lego_tu_van_van_bi_cong_ca_truc_chan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    c = await _canh(pool)
    with pytest.raises(SafetyGateError, match="không được phân công đi kèm BS"):
        await c["svc"].luu_don_thuoc(
            visit_id=c["luot"],
            dong=[_dong("Duphaston")],
            ly_do=None,
            identity=c["khong_lego"],
        )
