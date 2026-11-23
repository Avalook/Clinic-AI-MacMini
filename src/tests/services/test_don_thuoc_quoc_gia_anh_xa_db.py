"""Liên thông đơn thuốc quốc gia — ÁNH XẠ đơn ClinicAI → gói đơn (`doc_goi_don`).

Bác sĩ đứng tên đơn theo luật chốt 19/11 (mọi tên "bác sĩ" qua `bac_si_ky.py`):
`sql_join_bac_si_ky_luot` — người bấm Hoàn tất nếu là bác sĩ → bác sĩ chính của lượt
→ bác sĩ lịch hẹn. Người nhập dòng thuốc (TKYK/ĐD nhập hộ) KHÔNG bao giờ đứng tên.

Helper dựng dữ liệu ở đây được các tệp test hàng chờ dùng lại. Mỗi bài một CƠ SỞ
riêng (clinic_location mới) nên lượt của bài khác / seed không lọt vào.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.don_thuoc_quoc_gia.anh_xa import doc_goi_don
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_phieu_kham_db import pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _nhan_vien(
    p: asyncpg.Pool, loc: str, vai: str, cchn: str | None = None
) -> str:
    sid = await p.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active, license_number) VALUES ($1, $2, $3::uuid, true, $4)"
        " RETURNING id::text",
        f"{vai} Thử DTQG {uuid.uuid4().hex[:4]}",
        vai,
        loc,
        cchn,
    )
    await p.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        vai,
    )
    return str(sid)


async def _canh(
    p: asyncpg.Pool, *, cchn: str | None = "000123/HCM-CCHN"
) -> dict[str, Any]:
    loc = await p.fetchval(
        "INSERT INTO clinic_location (clinic_id, code, name) VALUES ($1::uuid, $2, $2)"
        " RETURNING id::text",
        CLINIC,
        f"DTQG-{uuid.uuid4().hex[:8]}",
    )
    bs = await _nhan_vien(p, loc, "DOCTOR", cchn)
    env = {
        "DTQG_BAT": "1",
        "DTQG_CLINIC_ID": CLINIC,
        "DTQG_LOCATION_ID": loc,
        "DTQG_MA_CO_SO": "79abc",
        "DTQG_GUI_TU": "2026-01-01",
        "DTQG_SO_LAN_THU": "3",
    }
    return {"loc": loc, "bs": bs, "env": env}


async def _luot(
    p: asyncpg.Pool, c: dict[str, Any], *, dong: bool = True, so_dong: int = 1
) -> str:
    """Lượt có bác sĩ chính = `c["bs"]`, chẩn đoán trên phiếu, `so_dong` dòng thuốc."""
    pid = await p.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
        " date_of_birth, gender, address) VALUES ($1::uuid, $2, 'DEMO Khách DTQG',"
        " $3::uuid, '1990-05-17', 'Nữ', 'DEMO địa chỉ')"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"DTQG-{uuid.uuid4().hex[:10]}",
        c["loc"],
    )
    vid = await p.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at,"
        " location_id, attending_doctor_id, closed_at) VALUES ($1::uuid, $2::uuid,"
        " 'IN_PROGRESS', now(), $3::uuid, $4::uuid, CASE WHEN $5 THEN now() END)"
        " RETURNING visit_id::text",
        CLINIC,
        pid,
        c["loc"],
        c["bs"],
        dong,
    )
    await p.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
        CLINIC,
        vid,
        json.dumps({"pk_dx": {"nguon": "USER", "gia_tri": "Viêm âm đạo"}}),
    )
    for i in range(so_dong):
        await _them_dong(p, c, vid, f"Thuốc {i}")
    return str(vid)


async def _them_dong(
    p: asyncpg.Pool,
    c: dict[str, Any],
    vid: str,
    ten: str,
    *,
    nguoi: str | None = None,
    nguon: str = "BAC_SI",
) -> str:
    return str(
        await p.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit,"
            " dosage_instructions, created_by, nguon)"
            " VALUES ($1::uuid, $2, $3::uuid, (SELECT clinic_patient_id FROM visit"
            " WHERE visit_id = $3::uuid), $4, '2 viên', 2, 'viên',"
            " 'Uống — sáng 1 viên', $5::uuid, $6) RETURNING id::text",
            CLINIC,
            f"dtqg-{uuid.uuid4().hex}",
            vid,
            ten,
            nguoi or c["bs"],
            nguon,
        )
    )


async def _go_het(p: asyncpg.Pool, c: dict[str, Any], vid: str) -> None:
    # Gỡ dòng như bàn khám làm: đủ dấu vết (người, lúc, lý do, lần đính chính).
    async with p.acquire() as conn, conn.transaction():
        dc = await conn.fetchval(
            "INSERT INTO prescription_correction (clinic_id, visit_id, reason,"
            " corrected_by) VALUES ($1::uuid, $2::uuid, 'Bác sĩ đổi ý, bỏ thuốc',"
            " $3::uuid) RETURNING id",
            CLINIC,
            vid,
            c["bs"],
        )
        await conn.execute(
            "UPDATE prescription p SET removed_at = d.corrected_at,"
            " removed_by = d.corrected_by, removal_reason = d.reason,"
            " removed_in_correction_id = d.id"
            " FROM prescription_correction d"
            " WHERE d.id = $2 AND p.visit_id = $1::uuid AND p.removed_at IS NULL",
            vid,
            dc,
        )


async def _goi(p: asyncpg.Pool, vid: str, **ma: str) -> Any:
    async with p.acquire() as conn:
        return (
            await doc_goi_don(conn, clinic_id=CLINIC, visit_ids=[vid], ma_lien_thong=ma)
        )[vid]


async def test_anh_xa_du_truong(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c, so_dong=2)
    # Dòng QUAY (quầy bán thêm) không phải đơn kê → không vào gói.
    await _them_dong(pool, c, vid, "Bán thêm", nguon="QUAY")
    g = await _goi(pool, vid, **{c["bs"]: "01000123HCM"})
    assert g.ma_don == "" and g.visit_id == vid and g.ngay_ke
    assert g.bac_si is not None
    assert (g.bac_si.staff_id, g.bac_si.so_chung_chi, g.bac_si.ma_lien_thong) == (
        c["bs"],
        "000123/HCM-CCHN",
        "01000123HCM",
    )
    nb = g.nguoi_benh
    assert (nb.ho_ten, nb.ngay_sinh, nb.gioi_tinh, nb.dia_chi) == (
        "DEMO Khách DTQG",
        "1990-05-17",
        "NU",
        "DEMO địa chỉ",
    )
    assert g.chan_doan == "Viêm âm đạo"
    assert [t.ten_thuoc for t in g.thuoc] == ["Thuốc 0", "Thuốc 1"]
    assert (g.thuoc[0].so_luong, g.thuoc[0].so_luong_so, g.thuoc[0].don_vi) == (
        "2 viên",
        2.0,
        "viên",
    )


async def test_go_het_thi_goi_rong(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    await _go_het(pool, c, vid)
    assert (await _goi(pool, vid)).thuoc == []


async def test_bac_si_dung_ten_qua_bac_si_ky(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Luật 19/11: người NHẬP dòng thuốc (TKYK) không đứng tên. Người bấm Hoàn tất
    là bác sĩ → họ; người bấm không phải bác sĩ → bác sĩ chính; không ai → None."""
    c = await _canh(pool)
    tkyk = await _nhan_vien(pool, c["loc"], "TKYK")
    bs_hoan_tat = await _nhan_vien(pool, c["loc"], "DOCTOR", "000999/HCM")
    vid = await _luot(pool, c, so_dong=0)
    await _them_dong(pool, c, vid, "Thuốc nhập hộ", nguoi=tkyk)

    async def hoan_tat(ai: str | None, chinh: str | None) -> str | None:
        await pool.execute(
            "UPDATE visit SET finalized_by = $2::uuid, attending_doctor_id = $3::uuid"
            " WHERE visit_id = $1::uuid",
            vid,
            ai,
            chinh,
        )
        bs = (await _goi(pool, vid)).bac_si
        return bs.staff_id if bs else None

    assert await hoan_tat(None, c["bs"]) == c["bs"]
    assert await hoan_tat(tkyk, c["bs"]) == c["bs"]
    assert await hoan_tat(bs_hoan_tat, c["bs"]) == bs_hoan_tat
    assert await hoan_tat(tkyk, None) is None
