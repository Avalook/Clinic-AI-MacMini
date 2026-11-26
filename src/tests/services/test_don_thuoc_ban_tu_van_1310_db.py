"""Đơn thuốc điền tiếp ở BÀN TƯ VẤN (Tuyền 13/10/2026).

Bác sĩ chính điền dở / vội → bác sĩ tư vấn làm tiếp ĐÚNG đơn của lượt đó. Kiểm:
người có lego Tư vấn lưu được dù không đi kèm bác sĩ chính hôm nay; ghi đúng
người bấm (không "làm thay"); sự kiện mang cờ `ke_tai_tu_van`; người không có
lego Tư vấn vẫn bị cổng ca trực chặn; đọc đơn trả người kê để phiếu in chọn chân ký.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import ca_truc, cache
from clinicai.permissions.ca_truc import kiem_dung_ca
from clinicai.services.bac_si_phu_trach import bac_si_cua_phien
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_ca_truc_lam_sang_db import _noi_tai_khoan, _truc, _vi_tri
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_luot_kham_service_db import _nguoi as _nguoi_loc
from tests.services.test_phieu_kham_db import (
    _luot,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@asynccontextmanager
async def _ca_truc_lam_sang_bat(db_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Các bài này kiểm luật khi công tắc ca trực đang bật; trả lại cấu hình cũ."""
    cu = await db_pool.fetchval(
        "SELECT gia_tri::text FROM day_nghiep_vu"
        " WHERE clinic_id=$1::uuid AND ma='ca_truc_lam_sang'",
        CLINIC,
    )
    await db_pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, 'ca_truc_lam_sang', 'true'::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri=EXCLUDED.gia_tri",
        CLINIC,
    )
    try:
        yield
    finally:
        if cu is None:
            await db_pool.execute(
                "DELETE FROM day_nghiep_vu"
                " WHERE clinic_id=$1::uuid AND ma='ca_truc_lam_sang'",
                CLINIC,
            )
        else:
            await db_pool.execute(
                "UPDATE day_nghiep_vu SET gia_tri=$2::jsonb"
                " WHERE clinic_id=$1::uuid AND ma='ca_truc_lam_sang'",
                CLINIC,
                cu,
            )


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
    async with _ca_truc_lam_sang_bat(pool):
        c = await _canh(pool)
        async with pool.acquire() as conn:
            state = await conn.fetchrow(
                "SELECT s.auth_user_id::text AS auth_user_id,"
                "       (d.gia_tri)::boolean AS ca_bat,"
                "       v.checked_in_at < d.sua_luc AS luot_cu"
                "  FROM staff s CROSS JOIN day_nghiep_vu d"
                "  JOIN visit v ON v.clinic_id=d.clinic_id"
                " WHERE s.id=$1::uuid AND v.visit_id=$2::uuid"
                "   AND d.clinic_id=$3::uuid AND d.ma='ca_truc_lam_sang'",
                c["tu_van"].staff_id,
                c["luot"],
                CLINIC,
            )
            assert state is not None
            assert state["auth_user_id"] is not None
            assert state["ca_bat"] is True
            assert state["luot_cu"] is False
            assert c["khong_lego"].staff_id != c["bs"].staff_id
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM work_roster WHERE clinic_id=$1::uuid"
                    " AND staff_id=$2::uuid AND work_date="
                    "(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date",
                    CLINIC,
                    c["khong_lego"].staff_id,
                )
                == 0
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM ngoai_le_ca_truc WHERE clinic_id=$1::uuid"
                    " AND staff_id=$2::uuid AND bac_si_id=$3::uuid"
                    " AND ngay=(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
                    " AND huy_luc IS NULL",
                    CLINIC,
                    c["khong_lego"].staff_id,
                    c["bs"].staff_id,
                )
                == 0
            )
            assert (
                await conn.fetchval(
                    "SELECT (checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
                    " >= (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
                    " FROM visit WHERE visit_id=$1::uuid",
                    c["luot"],
                )
                is True
            )
            bac_si_id = await bac_si_cua_phien(
                conn,
                clinic_id=CLINIC,
                visit_id=c["luot"],
                nguoi_bam=c["tu_van"].staff_id,
            )
            assert bac_si_id == c["bs"].staff_id
            with pytest.raises(SafetyGateError, match="không được phân công đi kèm BS"):
                await kiem_dung_ca(conn, c["tu_van"], bac_si_id, visit_id=c["luot"])
        await c["svc"].luu_don_thuoc(
            visit_id=c["luot"],
            dong=[_dong("Duphaston")],
            ly_do=None,
            identity=c["bs"],
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
    async with _ca_truc_lam_sang_bat(pool):
        c = await _canh(pool)
        async with pool.acquire() as conn:
            state = await conn.fetchrow(
                "SELECT s.auth_user_id::text AS auth_user_id,"
                "       (d.gia_tri)::boolean AS ca_bat,"
                "       v.checked_in_at < d.sua_luc AS luot_cu"
                "  FROM staff s CROSS JOIN day_nghiep_vu d"
                "  JOIN visit v ON v.clinic_id=d.clinic_id"
                " WHERE s.id=$1::uuid AND v.visit_id=$2::uuid"
                "   AND d.clinic_id=$3::uuid AND d.ma='ca_truc_lam_sang'",
                c["khong_lego"].staff_id,
                c["luot"],
                CLINIC,
            )
            assert state is not None
            assert state["auth_user_id"] is not None
            assert state["ca_bat"] is True
            assert state["luot_cu"] is False
            assert c["khong_lego"].vai_goc.value == "TKYK"
            assert (
                await ca_truc._duoc_noi_tiep_luot_cu(conn, CLINIC, c["luot"]) is False
            )
            assert (
                await ca_truc._dang_co_ngoai_le(
                    conn, c["khong_lego"], c["bs"].staff_id, hom_nay_vn()
                )
                is False
            )
            lich = await ca_truc._lich_hom_nay(conn, CLINIC, hom_nay_vn())
            assert not ca_truc.duoc_lam_thay(
                nguoi_bam=c["khong_lego"].staff_id,
                bac_si_id=c["bs"].staff_id,
                vai_goc=c["khong_lego"].vai_goc,
                lich=lich,
            )
            bac_si_id = await bac_si_cua_phien(
                conn,
                clinic_id=CLINIC,
                visit_id=c["luot"],
                nguoi_bam=c["khong_lego"].staff_id,
            )
            assert bac_si_id == c["bs"].staff_id
            with pytest.raises(SafetyGateError, match="không được phân công đi kèm BS"):
                await kiem_dung_ca(conn, c["khong_lego"], bac_si_id, visit_id=c["luot"])
        with pytest.raises(SafetyGateError, match="không được phân công đi kèm BS"):
            await c["svc"].luu_don_thuoc(
                visit_id=c["luot"],
                dong=[_dong("Duphaston")],
                ly_do=None,
                identity=c["khong_lego"],
            )


async def test_xong_ke_don_la_moc_khong_khoa_don_va_bam_lai_khong_nhan_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    c = await _canh(pool)
    svc, visit = c["svc"], c["luot"]
    await svc.luu_don_thuoc(
        visit_id=visit, dong=[_dong("Duphaston")], ly_do=None, identity=c["bs"]
    )

    async def dem() -> int:
        return int(
            await pool.fetchval(
                "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
                " AND event_type = 'prescription.consultant_marked'",
                visit,
            )
        )

    kq = await svc.danh_dau_xong_ke_don(visit_id=visit, xong=True, identity=c["tu_van"])
    assert kq == {"ok": True, "xong": True, "da_co": False}
    kq = await svc.danh_dau_xong_ke_don(visit_id=visit, xong=True, identity=c["tu_van"])
    assert kq["da_co"] is True and await dem() == 1
    # Đã xong mà vẫn sửa / thêm thuốc được (mốc, không khoá).
    don = await svc.doc_don_thuoc(visit_id=visit, identity=c["bs"])
    await svc.luu_don_thuoc(
        visit_id=visit,
        dong=[_dong("Duphaston", don[0]["id"]), _dong("Vitamin D3")],
        ly_do=None,
        identity=c["tu_van"],
    )
    # Mở lại → sự kiện mới; chưa từng bấm mà mở lại thì không phát gì.
    await svc.danh_dau_xong_ke_don(visit_id=visit, xong=False, identity=c["tu_van"])
    assert await dem() == 2
    c2 = await _canh(pool)
    kq = await c2["svc"].danh_dau_xong_ke_don(
        visit_id=c2["luot"], xong=False, identity=c2["tu_van"]
    )
    assert kq["da_co"] is True
    # Người không ghi được phiếu thì không đánh dấu được.
    with pytest.raises(SafetyGateError):
        await svc.danh_dau_xong_ke_don(
            visit_id=visit,
            xong=True,
            identity=await _nguoi_khong_quyen(pool),
        )


async def _nguoi_khong_quyen(pool: asyncpg.Pool) -> Any:  # noqa: F811
    from tests.services.test_phieu_kham_db import _nguoi

    async with pool.acquire() as conn:
        le_tan = await _nguoi(conn, "RECEPTION")
        await ve_goi_mau_cu(conn, le_tan)
    return le_tan
