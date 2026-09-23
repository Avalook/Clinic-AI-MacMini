"""Sửa kết quả mà không mất bản cũ — Schema V3 trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55487/postgres \
        poetry run pytest src/tests/services/test_sua_ket_qua_db.py

VÌ SAO BỘ NÀY QUAN TRỌNG HƠN VẺ NGOÀI CỦA NÓ. Kết quả ở phòng khám này được IN
RA GIẤY và giao cho khách. Một bản đã phát hành rồi mới phát hiện sai thì bản cũ
KHÔNG được biến mất — người bệnh đang cầm nó trên tay, và hỏi lại thì phòng khám
phải trả lời được "hôm ấy tờ giấy ghi gì".
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.services.form_engine_service import FormEngineService
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


async def _don(conn: asyncpg.Connection, bs: StaffIdentity) -> tuple[str, str]:
    """Một chỉ định có gắn mẫu kết quả tức thì. Trả (order_id, visit_id)."""
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN sửa kết quả', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"SKQ-{uuid.uuid4().hex[:9]}",
        bs.location_id,
    )
    vid = await conn.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
        " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', now()) RETURNING visit_id::text",
        CLINIC,
        pid,
    )
    con_id = await conn.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id, started_by, started_at)"
        " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
        " $3::uuid, now()) RETURNING id::text",
        CLINIC,
        vid,
        bs.staff_id,
    )
    ma_dv = f"DV{uuid.uuid4().hex[:8].upper()}"
    oid = await conn.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, recorded_by)"
        " VALUES ($1::uuid, $2::uuid, $5::uuid, $3, 'Dịch vụ test',"
        " 'DICHVU-SIEUAM', 'draft', $4::uuid) RETURNING id::text",
        CLINIC,
        vid,
        ma_dv,
        bs.staff_id,
        con_id,
    )
    await conn.execute(
        "INSERT INTO dich_vu_mau_ket_qua"
        " (clinic_id, service_code, mau, result_mode, gan_boi)"
        " VALUES ($1::uuid, $2, 'SA_VU', 'INLINE', $3::uuid)",
        CLINIC,
        ma_dv,
        bs.staff_id,
    )
    return oid, vid


async def _phieu_v1(svc: FormEngineService, bs: StaffIdentity, oid: str) -> str:
    """Phiếu đã [Hoàn tất] lần đầu, nội dung "bản một". Trả phieu_id."""
    p = await svc.mo_phieu(service_order_id=oid, form_id="KQ_SA_VU", identity=bs)
    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={"ket_luan": {"gia_tri": "bản một", "nguon": "USER"}},
        expected_revision=p["revision"],
        identity=bs,
    )
    await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=p["revision"] + 1, identity=bs
    )
    return str(p["id"])


async def _rev(pool: asyncpg.Pool, phieu_id: str) -> int:
    return int(
        await pool.fetchval(
            "SELECT revision FROM form_instance WHERE id = $1::uuid", phieu_id
        )
    )


async def _chinh_thuc(pool: asyncpg.Pool, phieu_id: str) -> dict[str, Any]:
    return dict(
        json.loads(
            await pool.fetchval(
                "SELECT du_lieu FROM form_instance WHERE id = $1::uuid", phieu_id
            )
        )
    )


async def _sua(
    svc: FormEngineService,
    pool: asyncpg.Pool,
    bs: StaffIdentity,
    phieu_id: str,
    noi_dung: str,
    ly_do: str = "Gõ nhầm kết luận",
) -> dict[str, Any]:
    await svc.mo_sua(phieu_id=phieu_id, identity=bs)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": noi_dung, "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs,
    )
    return await svc.hoan_tat(
        phieu_id=phieu_id,
        expected_revision=await _rev(pool, phieu_id),
        identity=bs,
        ly_do_sua=ly_do,
    )


# ── 1–3. Chuỗi phiên bản ───────────────────────────────────────────────────


async def test_v1_sang_v2_giu_nguyen_ban_cu(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    kq = await _sua(svc, pool, bs, phieu_id, "bản hai")
    assert kq["la_lan_sua"] is True
    assert kq["ban_thu"] == 2

    dong = await pool.fetchrow(
        "SELECT c.ban_thu, a.original_values, a.corrected_values, a.reason"
        "  FROM result_correction c"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE c.form_instance_id = $1::uuid",
        phieu_id,
    )
    assert dong is not None
    assert dong["ban_thu"] == 2
    # ẢNH CHỤP ĐẦY ĐỦ, không phải hiệu số.
    cu = json.loads(dong["original_values"])
    moi = json.loads(dong["corrected_values"])
    assert cu["du_lieu"]["ket_luan"]["gia_tri"] == "bản một"
    assert moi["du_lieu"]["ket_luan"]["gia_tri"] == "bản hai"
    assert dong["reason"] == "Gõ nhầm kết luận"
    assert (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"] == "bản hai"


async def test_v2_sang_v3_chup_dung_ban_hai(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")
    kq = await _sua(svc, pool, bs, phieu_id, "bản ba")
    assert kq["ban_thu"] == 3

    rows = await pool.fetch(
        "SELECT c.ban_thu, a.original_values FROM result_correction c"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE c.form_instance_id = $1::uuid ORDER BY c.ban_thu",
        phieu_id,
    )
    assert [r["ban_thu"] for r in rows] == [2, 3]
    # Ảnh chụp lần hai phải là BẢN HAI, không phải bản một.
    lan_hai = json.loads(rows[1]["original_values"])
    assert lan_hai["du_lieu"]["ket_luan"]["gia_tri"] == "bản hai"


async def test_doc_lai_tung_phien_ban(pool: asyncpg.Pool) -> None:
    """v1 = ảnh chụp của lần sửa v2; v2 = ảnh chụp của lần sửa v3."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")
    await _sua(svc, pool, bs, phieu_id, "bản ba")

    rows = await pool.fetch(
        "SELECT c.ban_thu, a.original_values FROM result_correction c"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE c.form_instance_id = $1::uuid ORDER BY c.ban_thu",
        phieu_id,
    )
    lich_su = {
        r["ban_thu"] - 1: json.loads(r["original_values"])["du_lieu"]["ket_luan"][
            "gia_tri"
        ]
        for r in rows
    }
    lich_su[3] = (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"]
    assert lich_su == {1: "bản một", 2: "bản hai", 3: "bản ba"}


# ── 4–5. Đua nhau và giao dịch trọn vẹn ────────────────────────────────────


async def test_hai_nguoi_sua_cung_luc_chi_mot_ban_duoc_ghi(pool: asyncpg.Pool) -> None:
    """Trigger chặn chèn bậy; khoá duy nhất mới là thứ chặn đua nhau."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, vid = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")

    # Chèn thẳng một dòng v2 thứ hai — đúng thứ hai giao dịch song song sẽ thử.
    am = await pool.fetchval(
        "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, amended_at,"
        " reason, corrected_fields, original_values, corrected_values)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, now(), 'đua',"
        "         ARRAY['ket_luan'], '{}'::jsonb, '{}'::jsonb)"
        " RETURNING amendment_id::text",
        CLINIC,
        vid,
        bs.staff_id,
    )
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 2, $4::uuid)",
            CLINIC,
            phieu_id,
            vid,
            am,
        )


async def test_thieu_ly_do_thi_khong_gi_ton_tai(pool: asyncpg.Pool) -> None:
    """Lệnh bị từ chối thì bản chính thức không đổi, lịch sử không có dòng nào."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    await svc.mo_sua(phieu_id=phieu_id, identity=bs)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản hai", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs,
    )
    with pytest.raises(ValidationError, match="lý do"):
        await svc.hoan_tat(
            phieu_id=phieu_id,
            expected_revision=await _rev(pool, phieu_id),
            identity=bs,
            ly_do_sua="   ",
        )

    assert (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"] == "bản một"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM result_correction WHERE form_instance_id = $1::uuid",
            phieu_id,
        )
        == 0
    )


# ── 6–8. Ranh giới ép ở Postgres ───────────────────────────────────────────


async def test_phieu_phong_kham_khac_thi_postgres_tu_choi(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, vid = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    khac = await pool.fetchval(
        "SELECT id::text FROM clinic WHERE id <> $1::uuid LIMIT 1", CLINIC
    )
    if khac is None:
        pytest.skip("database thử chỉ có một phòng khám")
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 2, gen_random_uuid())",
            khac,
            phieu_id,
            vid,
        )


async def test_ban_thu_1_bi_tu_choi(pool: asyncpg.Pool) -> None:
    """v1 nằm trong form_instance — không nhân đôi sang result_correction."""
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, gen_random_uuid(), gen_random_uuid(), 1,"
            "         gen_random_uuid())",
            CLINIC,
        )


async def test_khong_sua_duoc_lich_su_da_ghi(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")

    with pytest.raises(asyncpg.PostgresError, match="chi duoc THEM"):
        await pool.execute(
            "UPDATE result_correction SET ban_thu = 9"
            " WHERE form_instance_id = $1::uuid",
            phieu_id,
        )
    with pytest.raises(asyncpg.PostgresError, match="chi duoc THEM"):
        await pool.execute(
            "DELETE FROM result_correction WHERE form_instance_id = $1::uuid",
            phieu_id,
        )


# ── 9–11. Ba ranh giới ChatGPT yêu cầu ─────────────────────────────────────


async def test_amendment_cua_luot_khac_bi_tu_choi(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, vid = await _don(conn, bs)
        _, vid_khac = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    am = await pool.fetchval(
        "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, amended_at,"
        " reason, corrected_fields, original_values, corrected_values)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, now(), 'lượt khác',"
        "         ARRAY['ket_luan'],"
        " '{}'::jsonb, '{}'::jsonb) RETURNING amendment_id::text",
        CLINIC,
        vid_khac,
        bs.staff_id,
    )
    # Khai visit_id của phiếu nhưng amendment thuộc lượt khác → FK ghép chặn.
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 2, $4::uuid)",
            CLINIC,
            phieu_id,
            vid,
            am,
        )


async def test_visit_id_khong_khop_phieu_bi_tu_choi(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
        _, vid_khac = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    am = await pool.fetchval(
        "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, amended_at,"
        " reason, corrected_fields, original_values, corrected_values)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, now(), 'lệch lượt',"
        "         ARRAY['ket_luan'],"
        " '{}'::jsonb, '{}'::jsonb) RETURNING amendment_id::text",
        CLINIC,
        vid_khac,
        bs.staff_id,
    )
    with pytest.raises(asyncpg.PostgresError, match="khac luot cua phieu"):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 2, $4::uuid)",
            CLINIC,
            phieu_id,
            vid_khac,
            am,
        )


async def test_mot_amendment_khong_gan_hai_correction(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")

    am = await pool.fetchval(
        "SELECT amendment_id::text FROM result_correction"
        " WHERE form_instance_id = $1::uuid",
        phieu_id,
    )
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM result_correction"
        " WHERE form_instance_id = $1::uuid",
        phieu_id,
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 3, $4::uuid)",
            CLINIC,
            phieu_id,
            vid,
            am,
        )


async def test_mo_ra_sua_roi_khong_doi_gi(pool: asyncpg.Pool) -> None:
    """Không ghi một bản v2 giống hệt v1 — lịch sử y khoa không phải chỗ để rác."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    await svc.mo_sua(phieu_id=phieu_id, identity=bs)
    with pytest.raises(ValidationError, match="Không có gì thay đổi"):
        await svc.hoan_tat(
            phieu_id=phieu_id,
            expected_revision=await _rev(pool, phieu_id),
            identity=bs,
            ly_do_sua="Đổi ý",
        )
    assert (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"] == "bản một"


async def test_huy_sua_tra_lai_ban_chinh_thuc(pool: asyncpg.Pool) -> None:
    """Bấm [Sửa lại], gõ lung tung, rồi đổi ý — bản chính thức không suy suyển."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    await svc.mo_sua(phieu_id=phieu_id, identity=bs)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "gõ nhầm tùm lum", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs,
    )
    # NGAY CẢ KHI ĐANG GÕ DỞ, bản chính thức vẫn nguyên — đây là điều màn hình
    # hứa với người dùng, và trước 23/09 nó là lời hứa suông.
    assert (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"] == "bản một"

    await svc.huy_sua(phieu_id=phieu_id, identity=bs)
    dong = await pool.fetchrow(
        "SELECT dang_sua, du_lieu_dang_sua FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert dong is not None
    assert dong["dang_sua"] is False
    assert dong["du_lieu_dang_sua"] is None
    assert (await _chinh_thuc(pool, phieu_id))["ket_luan"]["gia_tri"] == "bản một"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM result_correction WHERE form_instance_id = $1::uuid",
            phieu_id,
        )
        == 0
    )


# ── 13–15. Quyền phát hành thuộc TỪNG BẢN ──────────────────────────────────
# Đây là nhóm ca quan trọng nhất của cả bộ: nó canh đúng chuyện "bác sĩ sửa
# xong, bản mới KHÔNG được gửi đi chỉ vì bản cũ từng được duyệt".


async def _duyet(
    pool: asyncpg.Pool, bs: StaffIdentity, phieu_id: str, ban: int
) -> None:
    await pool.execute(
        "INSERT INTO form_result_release"
        " (clinic_id, form_instance_id, ban_thu, released_by)"
        " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
        CLINIC,
        phieu_id,
        ban,
        bs.staff_id,
    )


async def test_ban_moi_khong_thua_quyen_phat_hanh_cua_ban_cu(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    await _duyet(pool, bs, phieu_id, 1)
    await _sua(svc, pool, bs, phieu_id, "bản hai")

    ds = [
        r["ban_thu"]
        for r in await pool.fetch(
            "SELECT ban_thu FROM form_result_release"
            " WHERE form_instance_id = $1::uuid ORDER BY ban_thu",
            phieu_id,
        )
    ]
    # v1 CÒN NGUYÊN: sự thật "v1 từng được duyệt" không bị xoá đi đâu cả.
    # v2 CHƯA CÓ: bản mới phải đi qua duyệt lại.
    assert ds == [1]


async def test_duyet_ban_moi_thi_ca_hai_cung_ton_tai(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    await _duyet(pool, bs, phieu_id, 1)
    await _sua(svc, pool, bs, phieu_id, "bản hai")
    await _duyet(pool, bs, phieu_id, 2)

    ds = [
        r["ban_thu"]
        for r in await pool.fetch(
            "SELECT ban_thu FROM form_result_release"
            " WHERE form_instance_id = $1::uuid ORDER BY ban_thu",
            phieu_id,
        )
    ]
    assert ds == [1, 2]


async def test_khong_duyet_duoc_ban_chua_ton_tai(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    with pytest.raises(asyncpg.PostgresError, match="chua ton tai"):
        await _duyet(pool, bs, phieu_id, 99)


async def test_khong_chen_duoc_ban_nhay_coc(pool: asyncpg.Pool) -> None:
    """Mới có v1 mà chèn thẳng v4 — trigger chặn, không nhờ Python nhớ."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, vid = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)

    am = await pool.fetchval(
        "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, amended_at,"
        " reason, corrected_fields, original_values, corrected_values)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, now(), 'nhảy cóc',"
        "         ARRAY['ket_luan'], '{}'::jsonb, '{}'::jsonb)"
        " RETURNING amendment_id::text",
        CLINIC,
        vid,
        bs.staff_id,
    )
    with pytest.raises(asyncpg.PostgresError, match="lien mach"):
        await pool.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 4, $4::uuid)",
            CLINIC,
            phieu_id,
            vid,
            am,
        )


# ── 17–18. Nháp KHÔNG được chạm gì thuộc bản chính thức ────────────────────
# Đây là loại lỗi tệ nhất của cả lát: nội dung v1 còn nguyên, nhưng TÊN NGƯỜI
# NHẬP v1 âm thầm thành người đang gõ v2. Hồ sơ nói sai về ai đã làm, mà không
# ai bấm nút nào.


async def test_go_nhap_khong_doi_metadata_cua_ban_chinh_thuc(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, "DOCTOR")
        bs_b = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs_a)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs_a, oid)

    truoc = await pool.fetchrow(
        "SELECT du_lieu, nhap_boi::text, thuc_hien_boi::text,"
        "       hoan_tat_boi::text, hoan_tat_luc"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert truoc is not None

    # NGƯỜI B mở ra sửa và gõ — đúng tình huống điều dưỡng sửa hộ bác sĩ.
    await svc.mo_sua(phieu_id=phieu_id, identity=bs_b)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "B đang gõ dở", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs_b,
        thuc_hien_boi=bs_b.staff_id,
    )

    sau = await pool.fetchrow(
        "SELECT du_lieu, nhap_boi::text, thuc_hien_boi::text,"
        "       hoan_tat_boi::text, hoan_tat_luc, du_lieu_dang_sua"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert sau is not None
    # Người xem v1 thấy NGUYÊN nội dung VÀ nguyên metadata của v1.
    assert sau["du_lieu"] == truoc["du_lieu"]
    assert sau["nhap_boi"] == truoc["nhap_boi"], "nhập bởi của v1 bị đổi"
    assert sau["thuc_hien_boi"] == truoc["thuc_hien_boi"], "thực hiện bởi bị đổi"
    assert sau["hoan_tat_boi"] == truoc["hoan_tat_boi"]
    assert sau["hoan_tat_luc"] == truoc["hoan_tat_luc"]
    # Nội dung B gõ nằm trong bản nháp, không ở đâu khác.
    assert json.loads(sau["du_lieu_dang_sua"])["ket_luan"]["gia_tri"] == "B đang gõ dở"


async def test_xac_nhan_sua_moi_cap_nhat_metadata(pool: asyncpg.Pool) -> None:
    """Metadata bản chính thức chỉ đổi khi lần sửa được XÁC NHẬN."""
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, "DOCTOR")
        bs_b = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs_a)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs_a, oid)

    await _sua(svc, pool, bs_b, phieu_id, "bản hai")

    dong = await pool.fetchrow(
        "SELECT f.hoan_tat_boi::text, a.amended_by::text"
        "  FROM form_instance f"
        "  JOIN result_correction c ON c.form_instance_id = f.id"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE f.id = $1::uuid",
        phieu_id,
    )
    assert dong is not None
    assert dong["hoan_tat_boi"] == bs_b.staff_id
    # Ai chịu trách nhiệm cho LẦN SỬA nằm ở visit_amendment, không suy từ ai gõ.
    assert dong["amended_by"] == bs_b.staff_id


# ── 19–20. Ba người, ba vai ────────────────────────────────────────────────
# Điều dưỡng C gõ bản sửa · bác sĩ B vẫn là người thực hiện · bác sĩ D bấm xác
# nhận. Hệ thống phải phân biệt được cả ba, và KHÔNG được suy vai nào từ vai
# nào — contract Form Engine: người gõ là nhật ký, người thực hiện là dữ liệu
# nghiệp vụ, người xác nhận là người chịu trách nhiệm cho lần sửa.


async def test_ba_nguoi_ba_vai_trong_mot_lan_sua(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        dd_a = await _nguoi(conn, "NURSE_ULTRASOUND")  # gõ v1
        bs_b = await _nguoi(conn, "DOCTOR")  # thực hiện, cả v1 lẫn v2
        dd_c = await _nguoi(conn, "NURSE_ULTRASOUND")  # gõ v2
        bs_d = await _nguoi(conn, "DOCTOR")  # bấm [Xác nhận sửa]
        oid, _ = await _don(conn, dd_a)
    svc = FormEngineService(pool)

    # v1: A gõ, B thực hiện.
    p = await svc.mo_phieu(service_order_id=oid, form_id="KQ_SA_VU", identity=dd_a)
    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={"ket_luan": {"gia_tri": "bản một", "nguon": "USER"}},
        expected_revision=p["revision"],
        identity=dd_a,
        thuc_hien_boi=bs_b.staff_id,
    )
    await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=p["revision"] + 1, identity=dd_a
    )
    phieu_id = str(p["id"])

    v1 = await pool.fetchrow(
        "SELECT nhap_boi::text, thuc_hien_boi::text, hoan_tat_boi::text"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert v1 is not None
    assert v1["nhap_boi"] == dd_a.staff_id
    assert v1["thuc_hien_boi"] == bs_b.staff_id

    # C mở ra sửa và gõ. TRƯỚC KHI XÁC NHẬN, metadata v1 phải nguyên vẹn.
    await svc.mo_sua(phieu_id=phieu_id, identity=dd_c)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản hai", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=dd_c,
    )
    giua_chung = await pool.fetchrow(
        "SELECT nhap_boi::text, thuc_hien_boi::text, nhap_boi_dang_sua::text,"
        "       thuc_hien_boi_dang_sua::text"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert giua_chung is not None
    assert giua_chung["nhap_boi"] == dd_a.staff_id, "người nhập v1 bị đổi"
    assert giua_chung["thuc_hien_boi"] == bs_b.staff_id, "người thực hiện v1 bị đổi"
    # Người gõ nháp KHÔNG bị đánh mất — nó nằm ở cột nháp.
    assert giua_chung["nhap_boi_dang_sua"] == dd_c.staff_id
    # Người thực hiện của bản nháp mặc định giữ nguyên B.
    assert giua_chung["thuc_hien_boi_dang_sua"] == bs_b.staff_id

    # D bấm xác nhận.
    await svc.hoan_tat(
        phieu_id=phieu_id,
        expected_revision=await _rev(pool, phieu_id),
        identity=bs_d,
        ly_do_sua="Sửa kết luận theo hội chẩn",
    )

    sau = await pool.fetchrow(
        "SELECT f.nhap_boi::text, f.thuc_hien_boi::text, f.hoan_tat_boi::text,"
        "       f.nhap_boi_dang_sua, f.thuc_hien_boi_dang_sua, f.du_lieu_dang_sua,"
        "       a.amended_by::text"
        "  FROM form_instance f"
        "  JOIN result_correction c ON c.form_instance_id = f.id"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE f.id = $1::uuid",
        phieu_id,
    )
    assert sau is not None
    assert sau["nhap_boi"] == dd_c.staff_id, "người GÕ bản hai phải là C"
    assert sau["thuc_hien_boi"] == bs_b.staff_id, "người THỰC HIỆN vẫn là B"
    assert sau["hoan_tat_boi"] == bs_d.staff_id, "người BẤM xác nhận là D"
    assert sau["amended_by"] == bs_d.staff_id, "người chịu trách nhiệm sửa là D"
    # Dọn sạch nháp.
    assert sau["nhap_boi_dang_sua"] is None
    assert sau["thuc_hien_boi_dang_sua"] is None
    assert sau["du_lieu_dang_sua"] is None


async def test_doi_nguoi_thuc_hien_trong_luc_sua_khong_mat(
    pool: asyncpg.Pool,
) -> None:
    """Tải lại trang giữa chừng không được mất lựa chọn — tự lưu là tự lưu CẢ phiếu."""
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, "DOCTOR")
        bs_moi = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs_a)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs_a, oid)

    await svc.mo_sua(phieu_id=phieu_id, identity=bs_a)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản hai", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs_a,
        thuc_hien_boi=bs_moi.staff_id,
    )
    # Tải lại trang = mở lại phiếu.
    lai = await svc.mo_phieu(service_order_id=oid, form_id="KQ_SA_VU", identity=bs_a)
    assert lai["thuc_hien_boi"] == bs_moi.staff_id
    assert lai["du_lieu"]["ket_luan"]["gia_tri"] == "bản hai"


# ── 21–23. Metadata phải theo từng phiên bản, không chỉ bản hiện hành ──────
# v1→v2 nhìn rất đẹp, và chỉ vỡ ở v3: lúc ấy `form_instance` mang metadata của
# v3, và câu "ai nhập v2, ai thực hiện v2" không còn chỗ nào trả lời — trừ khi
# ảnh chụp là CẢ PHIÊN BẢN chứ không chỉ phần chữ.


async def test_qua_ba_doi_van_dung_lai_du_metadata(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        a = await _nguoi(conn, "NURSE_ULTRASOUND")
        b = await _nguoi(conn, "DOCTOR")
        c = await _nguoi(conn, "NURSE_ULTRASOUND")
        d = await _nguoi(conn, "DOCTOR")
        e = await _nguoi(conn, "NURSE_ULTRASOUND")
        f = await _nguoi(conn, "DOCTOR")
        g = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, a)
    svc = FormEngineService(pool)

    # v1: A gõ, B thực hiện, A chốt.
    p = await svc.mo_phieu(service_order_id=oid, form_id="KQ_SA_VU", identity=a)
    await svc.luu_nhap(
        phieu_id=p["id"],
        du_lieu={"ket_luan": {"gia_tri": "bản một", "nguon": "USER"}},
        expected_revision=p["revision"],
        identity=a,
        thuc_hien_boi=b.staff_id,
    )
    await svc.hoan_tat(
        phieu_id=p["id"], expected_revision=p["revision"] + 1, identity=a
    )
    phieu_id = str(p["id"])

    # v2: C gõ, B vẫn thực hiện, D chốt.
    await svc.mo_sua(phieu_id=phieu_id, identity=c)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản hai", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=c,
    )
    await svc.hoan_tat(
        phieu_id=phieu_id,
        expected_revision=await _rev(pool, phieu_id),
        identity=d,
        ly_do_sua="Sửa lần một",
    )

    # v3: E gõ, đổi người thực hiện sang F, G chốt.
    await svc.mo_sua(phieu_id=phieu_id, identity=e)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản ba", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=e,
        thuc_hien_boi=f.staff_id,
    )
    await svc.hoan_tat(
        phieu_id=phieu_id,
        expected_revision=await _rev(pool, phieu_id),
        identity=g,
        ly_do_sua="Sửa lần hai",
    )

    rows = await pool.fetch(
        "SELECT c.ban_thu, a.original_values FROM result_correction c"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE c.form_instance_id = $1::uuid ORDER BY c.ban_thu",
        phieu_id,
    )
    v1 = json.loads(rows[0]["original_values"])
    v2 = json.loads(rows[1]["original_values"])

    # v1 dựng lại được ĐỦ: nội dung + ai nhập + ai thực hiện + ai chốt.
    assert v1["du_lieu"]["ket_luan"]["gia_tri"] == "bản một"
    assert v1["nhap_boi"] == a.staff_id
    assert v1["thuc_hien_boi"] == b.staff_id
    assert v1["hoan_tat_boi"] == a.staff_id

    # v2 cũng vậy — dù `form_instance` giờ đã mang metadata của v3.
    assert v2["du_lieu"]["ket_luan"]["gia_tri"] == "bản hai"
    assert v2["nhap_boi"] == c.staff_id
    assert v2["thuc_hien_boi"] == b.staff_id
    assert v2["hoan_tat_boi"] == d.staff_id

    hien = await pool.fetchrow(
        "SELECT nhap_boi::text, thuc_hien_boi::text, hoan_tat_boi::text"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert hien is not None
    assert (hien["nhap_boi"], hien["thuc_hien_boi"], hien["hoan_tat_boi"]) == (
        e.staff_id,
        f.staff_id,
        g.staff_id,
    )


async def test_chi_doi_nguoi_thuc_hien_van_la_mot_lan_sua(pool: asyncpg.Pool) -> None:
    """Đổi "ai làm siêu âm này" là sửa dữ liệu nghiệp vụ, dù không đổi chữ nào."""
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, "DOCTOR")
        bs_moi = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs_a)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs_a, oid)

    await svc.mo_sua(phieu_id=phieu_id, identity=bs_a)
    # KHÔNG đổi một chữ nào, chỉ đổi người thực hiện.
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản một", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=bs_a,
        thuc_hien_boi=bs_moi.staff_id,
    )
    # Vẫn phải có lý do.
    with pytest.raises(ValidationError, match="lý do"):
        await svc.hoan_tat(
            phieu_id=phieu_id,
            expected_revision=await _rev(pool, phieu_id),
            identity=bs_a,
        )
    kq = await svc.hoan_tat(
        phieu_id=phieu_id,
        expected_revision=await _rev(pool, phieu_id),
        identity=bs_a,
        ly_do_sua="Ghi nhầm người thực hiện",
    )
    assert kq["ban_thu"] == 2

    dong = await pool.fetchrow(
        "SELECT a.corrected_fields, a.original_values, a.corrected_values"
        "  FROM result_correction c"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE c.form_instance_id = $1::uuid",
        phieu_id,
    )
    assert dong is not None
    assert "thuc_hien_boi" in list(dong["corrected_fields"])
    assert json.loads(dong["original_values"])["thuc_hien_boi"] == bs_a.staff_id
    assert json.loads(dong["corrected_values"])["thuc_hien_boi"] == bs_moi.staff_id


async def test_chi_doi_nguoi_go_thi_van_la_khong_co_gi(pool: asyncpg.Pool) -> None:
    """Ai ngồi gõ là nhật ký, không phải nội dung chuyên môn."""
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, "DOCTOR")
        dd_khac = await _nguoi(conn, "NURSE_ULTRASOUND")
        oid, _ = await _don(conn, bs_a)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs_a, oid)

    # Người KHÁC mở ra và gõ lại y hệt nội dung cũ, không đổi người thực hiện.
    await svc.mo_sua(phieu_id=phieu_id, identity=dd_khac)
    await svc.luu_nhap(
        phieu_id=phieu_id,
        du_lieu={"ket_luan": {"gia_tri": "bản một", "nguon": "USER"}},
        expected_revision=await _rev(pool, phieu_id),
        identity=dd_khac,
    )
    with pytest.raises(ValidationError, match="Không có gì thay đổi"):
        await svc.hoan_tat(
            phieu_id=phieu_id,
            expected_revision=await _rev(pool, phieu_id),
            identity=dd_khac,
            ly_do_sua="Không có gì",
        )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM result_correction WHERE form_instance_id = $1::uuid",
            phieu_id,
        )
        == 0
    )


async def test_moc_chot_trong_anh_chup_dung_bang_moc_trong_phieu(
    pool: asyncpg.Pool,
) -> None:
    """MỘT sự việc thì MỘT mốc thời gian.

    Ảnh chụp bản mới phải mang đúng `hoan_tat_luc` mà Postgres vừa ghi vào
    `form_instance`, không phải một giờ Python tự lấy. Hai mốc lệch nhau cho
    cùng một việc là không ai biết mốc nào mới là lúc kết quả được chốt.
    """
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        oid, _ = await _don(conn, bs)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    await _sua(svc, pool, bs, phieu_id, "bản hai")

    dong = await pool.fetchrow(
        "SELECT f.hoan_tat_luc, a.corrected_values, a.original_values"
        "  FROM form_instance f"
        "  JOIN result_correction c ON c.form_instance_id = f.id"
        "  JOIN visit_amendment a ON a.amendment_id = c.amendment_id"
        " WHERE f.id = $1::uuid",
        phieu_id,
    )
    assert dong is not None
    trong_anh = json.loads(dong["corrected_values"])["hoan_tat_luc"]
    assert trong_anh is not None, "ảnh chụp bản mới thiếu mốc chốt"
    assert trong_anh == dong["hoan_tat_luc"].isoformat()
    # Bản cũ giữ mốc chốt CỦA NÓ, không phải mốc vừa rồi.
    assert json.loads(dong["original_values"])["hoan_tat_luc"] != trong_anh
