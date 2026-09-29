"""Thai kỳ từ hai ô `sk_lmp` / `sk_edd` của phiếu Sản khoa v5 (Tuyền 29/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55603/postgres \\
        .venv/bin/pytest src/tests/services/test_thai_ky_tu_phieu_sk_db.py

"Dữ liệu phải dùng được thật, GIỮ Y giao diện bản mẫu": bác sĩ gõ kinh cuối /
dự kiến sinh ngay trên phiếu → bảng `pregnancy` (mà CSKH gọi chúc mừng sinh,
luật "có thai" ở Đo sinh hiệu đọc) có thai kỳ; mở phiếu thì hai ô trống được
điền ngược từ thai kỳ. Không tạo trùng, ngày rác bỏ qua, phiếu vẫn lưu.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thai_ky_service import ThaiKyService
from tests.services.test_phieu_kham_db import (
    CLINIC,
    _luot,
    _nguoi,
    _o,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _svc(pool: asyncpg.Pool) -> PhieuKhamService:  # noqa: F811
    return PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)


async def _luu(
    pool: asyncpg.Pool,  # noqa: F811
    bs: StaffIdentity,
    visit: str,
    **o: Any,
) -> dict[str, Any]:
    return await _svc(pool).luu_luot(
        visit_id=visit,
        form_id="SK",
        du_lieu=None,
        thay_doi={k: _o(v) for k, v in o.items()},
        expected_revision=0,
        identity=bs,
    )


async def _thai_ky(pool: asyncpg.Pool, pid: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT id::text, outcome, lmp_date, edd_date, edd_nguon,"
            " xac_nhan_visit_id::text AS luot, updated_at FROM pregnancy"
            " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
            " ORDER BY created_at",
            CLINIC,
            pid,
        )
    )


async def _chuan_bi(
    pool: asyncpg.Pool,  # noqa: F811
) -> tuple[StaffIdentity, dict[str, str]]:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    return bs, luot


async def test_chi_go_kinh_cuoi_tao_thai_ky_du_kien_sinh_cong_280(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    lmp = now_vn().date() - timedelta(days=56)
    kq = await _luu(pool, bs, luot["visit"], sk_lmp=lmp.strftime("%d/%m/%Y"))
    assert kq["thai_ky"] == "tao"
    [tk] = await _thai_ky(pool, luot["patient"])
    assert tk["outcome"] == "ONGOING"
    assert tk["lmp_date"] == lmp and tk["edd_date"] == lmp + timedelta(days=280)
    assert tk["edd_nguon"] == "KY_KINH_CUOI" and tk["luot"] == luot["visit"]
    # Sổ sự kiện: ai tạo, từ phiếu khám.
    assert await pool.fetchval(
        "SELECT count(*) FROM event_log WHERE aggregate_id = $1"
        " AND event_type = 'pregnancy.created' AND source = 'api:phieu-kham'",
        tk["id"],
    )
    # Khối "Thai kỳ" (cùng nguồn) đọc được: 8 tuần.
    doc = await ThaiKyService(pool).doc(clinic_patient_id=luot["patient"], identity=bs)
    assert doc["hien_tai"]["tuoi_thai"] == {"tuan": 8, "ngay": 0}
    # Luật "có thai" ở Đo sinh hiệu / Khám đọc cùng bảng.
    assert await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pregnancy p JOIN visit v"
        " ON v.clinic_id = p.clinic_id AND v.clinic_patient_id = p.clinic_patient_id"
        " WHERE v.visit_id = $1::uuid AND p.outcome = 'ONGOING')",
        luot["visit"],
    )


async def test_luu_o_khac_khong_dong_toi_thai_ky(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lưu ô khác không ghi lại thai kỳ bằng số cũ trên phiếu (bác sĩ có thể
    vừa sửa ở khối Thai kỳ)."""
    bs, luot = await _chuan_bi(pool)
    lmp = now_vn().date() - timedelta(days=30)
    await _luu(pool, bs, luot["visit"], sk_lmp=lmp.isoformat())
    [tk] = await _thai_ky(pool, luot["patient"])
    edd_sieu_am = lmp + timedelta(days=290)
    await ThaiKyService(pool).cap_nhat(
        pregnancy_id=tk["id"],
        du_lieu={
            "du_kien_sinh": edd_sieu_am.isoformat(),
            "nguon_du_kien_sinh": "SIEU_AM",
        },
        identity=bs,
    )
    kq = await _luu(pool, bs, luot["visit"], sk_history="Nghén nhẹ")
    assert kq["thai_ky"] is None
    [sau] = await _thai_ky(pool, luot["patient"])
    assert sau["edd_date"] == edd_sieu_am and sau["edd_nguon"] == "SIEU_AM"


async def test_go_du_kien_sinh_cap_nhat_dung_thai_ky_khong_tao_trung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    lmp = now_vn().date() - timedelta(days=70)
    await _luu(pool, bs, luot["visit"], sk_lmp=lmp.isoformat())
    edd = lmp + timedelta(days=285)
    kq = await _luu(pool, bs, luot["visit"], sk_edd=edd.isoformat())
    assert kq["thai_ky"] == "cap_nhat"
    [tk] = await _thai_ky(pool, luot["patient"])
    assert tk["lmp_date"] == lmp and tk["edd_date"] == edd and tk["edd_nguon"] == "KHAC"
    # Lượt KHÁC của cùng khách, gõ lại kinh cuối → vẫn MỘT thai kỳ.
    async with pool.acquire() as conn:
        v2 = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', now())"
            " RETURNING visit_id::text",
            CLINIC,
            luot["patient"],
        )
    lmp2 = lmp + timedelta(days=2)
    kq2 = await _luu(pool, bs, v2, sk_lmp=lmp2.isoformat())
    assert kq2["thai_ky"] == "cap_nhat"
    ds = await _thai_ky(pool, luot["patient"])
    assert len(ds) == 1
    assert ds[0]["lmp_date"] == lmp2
    # Dự kiến sinh gõ tay (Khác) không phải kinh cuối → không bị kinh cuối đè.
    assert ds[0]["edd_date"] == edd


async def test_kinh_cuoi_khong_de_du_kien_sinh_sieu_am(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    edd = now_vn().date() + timedelta(days=150)
    await ThaiKyService(pool).tao(
        clinic_patient_id=luot["patient"],
        visit_id=luot["visit"],
        du_lieu={"du_kien_sinh": edd.isoformat(), "nguon_du_kien_sinh": "SIEU_AM"},
        identity=bs,
    )
    lmp = now_vn().date() - timedelta(days=128)
    kq = await _luu(pool, bs, luot["visit"], sk_lmp=lmp.strftime("%d/%m/%Y"))
    assert kq["thai_ky"] == "cap_nhat"
    [tk] = await _thai_ky(pool, luot["patient"])
    assert tk["lmp_date"] == lmp
    assert tk["edd_date"] == edd and tk["edd_nguon"] == "SIEU_AM"


@pytest.mark.parametrize(
    "o",
    [
        {"sk_lmp": "hôm qua"},
        {"sk_lmp": "31/02/2026"},
        {"sk_lmp": "01/01/2020"},  # hơn 300 ngày → không phải thai đang theo dõi
        {"sk_edd": "32/13/20xx"},  # ô ngày: máy chủ để trống + cảnh báo
    ],
)
async def test_ngay_rac_bo_qua_phieu_van_luu(
    pool: asyncpg.Pool,  # noqa: F811
    o: dict[str, str],
) -> None:
    bs, luot = await _chuan_bi(pool)
    kq = await _luu(pool, bs, luot["visit"], **o)
    assert kq["ok"] and kq["revision"] == 1 and kq["thai_ky"] is None
    assert await _thai_ky(pool, luot["patient"]) == []


async def test_kinh_cuoi_tuong_lai_hoac_du_kien_sinh_truoc_kinh_cuoi_bo_qua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    mai = now_vn().date() + timedelta(days=1)
    kq = await _luu(pool, bs, luot["visit"], sk_lmp=mai.isoformat())
    assert kq["thai_ky"] is None
    lmp = now_vn().date() - timedelta(days=20)
    kq = await _luu(
        pool,
        bs,
        luot["visit"],
        sk_lmp=lmp.isoformat(),
        sk_edd=(lmp - timedelta(days=1)).isoformat(),
    )
    assert kq["thai_ky"] is None
    assert await _thai_ky(pool, luot["patient"]) == []


async def test_mo_phieu_dien_nguoc_hai_o_trong_tu_thai_ky(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    bs, luot = await _chuan_bi(pool)
    lmp = now_vn().date() - timedelta(days=42)
    edd = lmp + timedelta(days=280)
    await ThaiKyService(pool).tao(
        clinic_patient_id=luot["patient"],
        visit_id=None,
        du_lieu={
            "du_kien_sinh": edd.isoformat(),
            "kinh_cuoi": lmp.isoformat(),
            "nguon_du_kien_sinh": "KY_KINH_CUOI",
        },
        identity=bs,
    )
    kq = await _svc(pool).doc_luot(visit_id=luot["visit"], form_id="SK", identity=bs)
    assert kq["revision"] == 0  # chỉ điền vào bản trả về, không ghi phiếu
    assert kq["du_lieu"]["sk_lmp"] == {
        "gia_tri": lmp.strftime("%d/%m/%Y"),
        "nguon": "PATIENT_CONTEXT",
    }
    assert kq["du_lieu"]["sk_edd"] == {
        "gia_tri": edd.isoformat(),
        "nguon": "PATIENT_CONTEXT",
    }
    assert not await pool.fetchval(
        "SELECT count(*) FROM phieu_kham_luot WHERE visit_id = $1::uuid",
        luot["visit"],
    )
    # Ô ĐÃ có chữ thì giữ nguyên, ô trống vẫn được điền.
    await _luu(pool, bs, luot["visit"], sk_edd=(edd + timedelta(days=3)).isoformat())
    kq = await _svc(pool).doc_luot(visit_id=luot["visit"], form_id="SK", identity=bs)
    assert kq["du_lieu"]["sk_edd"]["gia_tri"] == (edd + timedelta(days=3)).isoformat()
    assert kq["du_lieu"]["sk_edd"]["nguon"] == "USER"
    assert kq["du_lieu"]["sk_lmp"]["nguon"] == "PATIENT_CONTEXT"


async def test_phieu_luot_cu_truoc_thai_ky_khong_bi_dien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Xem lại phiếu năm ngoái không bị điền thai kỳ năm nay; phiếu khác SK
    (không có hai ô) cũng không."""
    bs, luot = await _chuan_bi(pool)
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - interval '400 days'"
        " WHERE visit_id = $1::uuid",
        luot["visit"],
    )
    edd = now_vn().date() + timedelta(days=200)
    await ThaiKyService(pool).tao(
        clinic_patient_id=luot["patient"],
        visit_id=None,
        du_lieu={"du_kien_sinh": edd.isoformat(), "nguon_du_kien_sinh": "SIEU_AM"},
        identity=bs,
    )
    kq = await _svc(pool).doc_luot(visit_id=luot["visit"], form_id="SK", identity=bs)
    assert "sk_lmp" not in kq["du_lieu"] and "sk_edd" not in kq["du_lieu"]
    async with pool.acquire() as conn:
        luot2 = await _luot(conn, bs)
    await pool.execute(
        "UPDATE visit SET clinic_patient_id = $2::uuid WHERE visit_id = $1::uuid",
        luot2["visit"],
        luot["patient"],
    )
    pk = await _svc(pool).doc_luot(visit_id=luot2["visit"], form_id="PK", identity=bs)
    assert pk["du_lieu"] == {}
