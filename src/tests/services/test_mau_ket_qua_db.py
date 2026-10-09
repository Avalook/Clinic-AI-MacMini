"""Mẫu kết quả gắn với dịch vụ — nguồn: phiếu chỉ định giấy Dr4Women 17/08.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55474/postgres \
        poetry run pytest src/tests/services/test_mau_ket_qua_db.py
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.services.mau_ket_qua_service import MauKetQuaService
from clinicai.services.permission_service import cap_preset_mac_dinh

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _nguoi(conn: asyncpg.Connection, role: str) -> StaffIdentity:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        f"Test {role} {uuid.uuid4().hex[:6]}",
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Test",
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def test_co_du_18_mau_cua_phong_kham(pool: asyncpg.Pool) -> None:
    so = await pool.fetchval(
        "SELECT count(*) FROM ket_qua_mau WHERE clinic_id = $1::uuid AND active"
        # + mẫu siêu âm thai quý III (migration 20261009310000).
        " AND ma NOT IN ('CHUNG', 'DO_MAT_DO_XUONG', 'PHIEU_DIEU_TRI',"
        "                'SA_THAI_QUY_3')",
        CLINIC,
    )
    assert so == 18
    # + Phiếu điều trị (07/10/2026) — phiếu kết quả của chỉ định Điều trị.
    assert await pool.fetchval(
        "SELECT active FROM ket_qua_mau WHERE clinic_id = $1::uuid"
        " AND ma = 'PHIEU_DIEU_TRI'",
        CLINIC,
    )
    # + mẫu Đo mật độ xương (29/09/2026, "Kết luận nhanh") — không có PDF gốc.
    assert await pool.fetchval(
        "SELECT active FROM ket_qua_mau WHERE clinic_id = $1::uuid"
        " AND ma = 'DO_MAT_DO_XUONG'",
        CLINIC,
    )
    # + mẫu CHUNG nhập tự do (24/09/2026) cho dịch vụ chưa có mẫu riêng.
    assert await pool.fetchval(
        "SELECT active FROM ket_qua_mau WHERE clinic_id = $1::uuid AND ma = 'CHUNG'",
        CLINIC,
    )


async def test_migration_chi_gan_theo_ma_phong_kham_cua_pdf(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Gắn theo TÊN là gắn nhầm. Từ 26/09/2026 (Tuyền duyệt: theo nguồn chuẩn)
    migration tự gắn — nhưng CHỈ theo mã phòng khám (KiotViet) ghi trên từng PDF
    mẫu (`mau_ket_qua_v3.json`), không cặp nào ngoài bảng ấy."""
    import json
    from pathlib import Path

    import clinicai.phieu_kham as pk

    ghep = json.loads(
        (Path(pk.__file__).parent / "mau_ket_qua_v3.json").read_text(encoding="utf-8")
    )["mau"]
    hop_le = {(mau, kv) for mau, m in ghep.items() for kv in m["kv"]}
    # Mẫu Đo mật độ xương (migration 20260929000010, Tuyền 29/09/2026): không có
    # PDF nên không nằm trong JSON v3 — gắn theo đúng mã phòng khám của DXA.
    hop_le.add(("DO_MAT_DO_XUONG", "SP000134"))
    dong = await pool.fetch(
        "SELECT g.mau, p.ma_kiotviet FROM dich_vu_mau_ket_qua g"
        " JOIN service_price p ON p.clinic_id = g.clinic_id"
        "  AND p.service_code = g.service_code AND p.\"group\" = 'dich_vu'"
        " WHERE g.clinic_id = $1::uuid AND g.gan_boi IS NULL"
        "   AND g.mau <> 'PHIEU_DIEU_TRI'",
        CLINIC,
    )
    assert all((r["mau"], r["ma_kiotviet"]) in hop_le for r in dong)
    # Phiếu điều trị (migration 20261007620000) gắn theo MÃ dịch vụ mà loại khám
    # nhóm Điều trị trỏ tới — không cặp nào ngoài nhóm ấy.
    assert not await pool.fetchval(
        "SELECT count(*) FROM dich_vu_mau_ket_qua g"
        " WHERE g.clinic_id = $1::uuid AND g.mau = 'PHIEU_DIEU_TRI'"
        "   AND g.service_code NOT IN ("
        "       SELECT sp.service_code FROM service_type st"
        "         JOIN service_price sp ON sp.id = st.service_price_id"
        "        WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI')",
        CLINIC,
    )


async def test_quan_ly_gan_duoc_va_bac_si_doc_duoc(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        quan_ly = await _nguoi(conn, "MANAGEMENT")
        bac_si = await _nguoi(conn, "DOCTOR")
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active ORDER BY service_code LIMIT 1",
            CLINIC,
        )

    svc = MauKetQuaService(pool)
    kq = await svc.gan(service_code=ma_dv, mau="SA_VU", identity=quan_ly)
    assert kq["moi"] is True

    doc = await svc.mau_cua_dich_vu(service_code=ma_dv, identity=bac_si)
    assert [m["ma"] for m in doc["mau"]] == ["SA_VU"]

    # Gắn lại không nhân đôi.
    lai = await svc.gan(service_code=ma_dv, mau="SA_VU", identity=quan_ly)
    assert lai["moi"] is False

    await svc.go(service_code=ma_dv, mau="SA_VU", identity=quan_ly)
    # Gỡ hết mẫu → KHÔNG còn "trống": máy chọn mặc định (CHUNG nhập tự do, hoặc
    # mẫu gợi ý), đánh dấu `mac_dinh` (01/10/2026).
    sau = await svc.mau_cua_dich_vu(service_code=ma_dv, identity=bac_si)
    assert sau["mac_dinh"] is True
    assert sau["chon_san"] in {m["ma"] for m in sau["mau"]}
    assert "CHUNG" in {m["ma"] for m in sau["mau"]}


async def test_bac_si_khong_gan_duoc_mau(pool: asyncpg.Pool) -> None:
    """Đọc thì được, gắn thì phải có quyền quản lý danh mục."""
    async with pool.acquire() as conn:
        bac_si = await _nguoi(conn, "DOCTOR")
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active ORDER BY service_code LIMIT 1",
            CLINIC,
        )
    with pytest.raises(SafetyGateError):
        await MauKetQuaService(pool).gan(
            service_code=ma_dv, mau="SA_VU", identity=bac_si
        )


async def test_khong_gan_cho_dich_vu_khong_co_that(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        quan_ly = await _nguoi(conn, "MANAGEMENT")
    with pytest.raises(ValidationError):
        await MauKetQuaService(pool).gan(
            service_code="KHONG-CO-MA-NAY", mau="SA_VU", identity=quan_ly
        )


async def test_khong_gan_mau_khong_co_that(pool: asyncpg.Pool) -> None:
    """Mẫu lạ bị Postgres chặn bằng khoá ngoại, không cần kiểm tay."""
    async with pool.acquire() as conn:
        quan_ly = await _nguoi(conn, "MANAGEMENT")
        ma_dv = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active ORDER BY service_code LIMIT 1",
            CLINIC,
        )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await MauKetQuaService(pool).gan(
            service_code=ma_dv, mau="MAU_KHONG_CO", identity=quan_ly
        )


async def test_de_xuat_chi_goi_y_chu_khong_tu_gan(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        quan_ly = await _nguoi(conn, "MANAGEMENT")

    ket_qua = await MauKetQuaService(pool).de_xuat(identity=quan_ly)
    truoc = await pool.fetchval(
        "SELECT count(*) FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid", CLINIC
    )
    assert "de_xuat" in ket_qua
    # Gọi đề xuất KHÔNG được tạo dòng gắn nào.
    sau = await pool.fetchval(
        "SELECT count(*) FROM dich_vu_mau_ket_qua WHERE clinic_id = $1::uuid", CLINIC
    )
    assert truoc == sau
