"""Bản giao diện mẫu mục 12 (27/09/2026): BÁC SĨ CHÍNH sửa được ô tư vấn.

Ô chữ tự do của bác sĩ tư vấn (``noi-dung-tu-van``) trước chỉ nhận người có
khối Tư vấn (``clinical.intake.perform``). Bản mẫu: ghi chú tư vấn hiện ở khối 1
của phiếu bác sĩ chính và "bác sĩ chính sửa tiếp được" → người GHI ĐƯỢC PHIẾU
KHÁM (``clinical.record.write``) cũng ghi được. Lễ tân (không có quyền nào trong
hai) vẫn bị chặn ở máy chủ.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.permissions.can import can
from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.luot_kham_service import LuotKhamService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_bac_si_chinh_sua_duoc_o_tu_van_le_tan_thi_khong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await pool.execute(
        "UPDATE service_type SET qua_tu_van = true WHERE id = $1::uuid", ca.loai_kham
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    tu_van = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'TU_VAN'",
        visit,
    )
    assert tu_van, "khách qua tư vấn phải có phiên tư vấn"

    # Bác sĩ CHÍNH: có quyền ghi phiếu khám nhưng KHÔNG có khối Tư vấn.
    async with pool.acquire() as conn:
        bs_chinh = await _nguoi(conn, ca.loc, "DOCTOR")
        await conn.execute(
            "UPDATE capability_grant SET revoked_at = now(), revoked_by = $2::uuid"
            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
            "   AND capability = 'clinical.intake.perform' AND revoked_at IS NULL",
            CLINIC,
            bs_chinh.staff_id,
        )
        cache.quen(CLINIC, bs_chinh.staff_id)
        assert not await can(conn, bs_chinh, "clinical.intake.perform")
        assert await can(conn, bs_chinh, "clinical.record.write")
        # Lễ tân: không có quyền nào trong hai.
        assert not await can(conn, ca.le_tan, "clinical.intake.perform")
        assert not await can(conn, ca.le_tan, "clinical.record.write")

    svc = LuotKhamService(pool)
    # Phiên tư vấn CHƯA ghi chữ nào vẫn có chỗ sửa (phien_tu_van).
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    [phien] = [p for p in dau["phien_tu_van"] if p["consultation_id"] == tu_van]
    assert phien["noi_dung"] == "" and phien["nguoi"] is None

    await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van, noi_dung="Đau bụng 3 ngày", identity=ca.bac_si
    )
    kq = await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van,
        noi_dung="Đau bụng 3 ngày — BS chính bổ sung: sốt 38",
        identity=bs_chinh,
    )
    assert kq["doi"] is True

    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    [phien] = [p for p in dau["phien_tu_van"] if p["consultation_id"] == tu_van]
    assert phien["noi_dung"] == "Đau bụng 3 ngày — BS chính bổ sung: sốt 38"
    assert phien["nguoi"] == bs_chinh.full_name
    assert [g["noi_dung"] for g in dau["tu_van"] if g["consultation_id"] == tu_van] == [
        "Đau bụng 3 ngày — BS chính bổ sung: sốt 38"
    ]

    # Lịch sử: bản cũ KHÔNG bị sửa đè — mỗi lần lưu một dòng, đúng người ghi.
    ds = await pool.fetch(
        "SELECT body, recorded_by::text AS ai FROM consultation_note"
        " WHERE consultation_id = $1::uuid ORDER BY created_at, id",
        tu_van,
    )
    assert [(r["body"], r["ai"]) for r in ds] == [
        ("Đau bụng 3 ngày", ca.bac_si.staff_id),
        ("Đau bụng 3 ngày — BS chính bổ sung: sốt 38", bs_chinh.staff_id),
    ]
    nguon = await pool.fetch(
        "SELECT payload FROM event_log WHERE event_type = 'consult.note_saved'"
        "   AND payload->>'consultation_id' = $1 ORDER BY recorded_at",
        tu_van,
    )
    assert [json.loads(r["payload"])["nguon"] for r in nguon] == [
        "tu_van",
        "phieu_kham",
    ]

    # Lễ tân bị chặn ở máy chủ — không thêm dòng nào.
    with pytest.raises(SafetyGateError):
        await svc.luu_noi_dung_tu_van(
            consultation_id=tu_van, noi_dung="lễ tân sửa", identity=ca.le_tan
        )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM consultation_note WHERE consultation_id = $1::uuid",
            tu_van,
        )
        == 2
    )

    # Xoá trắng: mục "mang sang" bỏ dòng rỗng, nhưng ô sửa vẫn còn chỗ ghi lại.
    await svc.luu_noi_dung_tu_van(
        consultation_id=tu_van, noi_dung="", identity=bs_chinh
    )
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    assert not [g for g in dau["tu_van"] if g["consultation_id"] == tu_van]
    [phien] = [p for p in dau["phien_tu_van"] if p["consultation_id"] == tu_van]
    assert phien["noi_dung"] == ""
