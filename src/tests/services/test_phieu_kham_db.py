"""Bảy phiếu khám trên Postgres thật — khung theo bản, cổng lưu, mang sang, kết quả.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_phieu_kham_db.py

Không bài nào tạo `form_instance` cho phiếu khám: phiếu khám gắn vào
consultation/visit và chỗ lưu ấy chưa có (INTEGRATION_BLOCKER). Không bài nào
đếm số dòng toàn bảng: database thử dùng chung với các phiên khác.
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
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.phieu_kham.khung import FORM_IDS, cac_o
from clinicai.phieu_kham.nap import nap_ban_dau
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.permission_service import cap_preset_mac_dinh
from clinicai.services.phieu_kham_service import (
    HanhDong,
    PhieuKhamService,
    chua_noi_quyen,
)

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    async with p.acquire() as conn:
        await nap_ban_dau(conn, clinic_id=CLINIC)
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


async def _luot(conn: asyncpg.Connection, bs: StaffIdentity) -> dict[str, str]:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
        " birth_year) VALUES ($1::uuid, $2, 'BN phiếu khám', $3::uuid, 1991)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"PK-{uuid.uuid4().hex[:10]}",
        bs.location_id,
    )
    vid = await conn.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
        " VALUES ($1::uuid, $2::uuid, 'IN_PROGRESS', now()) RETURNING visit_id::text",
        CLINIC,
        pid,
    )
    con = await conn.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id, started_by, started_at)"
        " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'in_progress', $3::uuid,"
        " $3::uuid, now()) RETURNING id::text",
        CLINIC,
        vid,
        bs.staff_id,
    )
    return {"patient": pid, "visit": vid, "consultation": con}


async def _chi_dinh(
    conn: asyncpg.Connection, bs: StaffIdentity, luot: dict[str, str], ma: str
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'Tên hiển thị giống nhau',"
            " 'DICHVU-SIEUAM', 'draft', $5::uuid) RETURNING id::text",
            CLINIC,
            luot["visit"],
            luot["consultation"],
            ma,
            bs.staff_id,
        )
    )


async def _chuan_bi(pool: asyncpg.Pool) -> tuple[StaffIdentity, dict[str, str]]:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    return bs, luot


async def _cho_qua(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Hệ phân quyền giả cho test: cho qua, và ghi lại đã được hỏi gì."""
    DA_HOI.append(hanh_dong)


DA_HOI: list[str] = []


def _svc(pool: asyncpg.Pool) -> PhieuKhamService:
    return PhieuKhamService(pool, kiem_quyen=_cho_qua)


def _o(v: object) -> dict[str, Any]:
    return {"gia_tri": v, "nguon": "USER"}


# ── Ca 1: nạp bảy khung ─────────────────────────────────────────────────────
async def test_bay_khung_dang_dung_va_nap_lai_khong_de(pool: asyncpg.Pool) -> None:
    rows = await pool.fetch(
        "SELECT form_id, nhom FROM form_definition WHERE clinic_id = $1::uuid"
        " AND trang_thai = 'PUBLISHED' AND form_id = ANY($2::text[])",
        CLINIC,
        list(FORM_IDS),
    )
    assert {r["form_id"] for r in rows} == set(FORM_IDS)
    assert {r["nhom"] for r in rows} == {"PHIEU_KHAM"}
    async with pool.acquire() as conn:
        assert await nap_ban_dau(conn, clinic_id=CLINIC) == []


# ── Ca 2: chưa nối quyền = chặn tất ─────────────────────────────────────────
async def test_chua_noi_quyen_thi_chan(pool: asyncpg.Pool) -> None:
    bs, luot = await _chuan_bi(pool)
    svc = PhieuKhamService(pool, kiem_quyen=chua_noi_quyen)
    with pytest.raises(SafetyGateError, match="chưa được nối"):
        await svc.dau_phieu(visit_id=luot["visit"], identity=bs)
    with pytest.raises(SafetyGateError, match="chưa được nối"):
        await svc.ket_qua_chi_dinh(visit_id=luot["visit"], identity=bs)
    with pytest.raises(SafetyGateError, match="chưa được nối"):
        await svc.khung_theo_ban(form_id="NT", version=None, identity=bs)


# ── Ca 3: cổng lưu — chế độ trước, rồi quyền, rồi khung đúng bản ────────────
async def test_cong_luu_theo_che_do(pool: asyncpg.Pool) -> None:
    bs, _ = await _chuan_bi(pool)
    svc = _svc(pool)
    ban = await svc.khung_theo_ban(form_id="HMVS", version=None, identity=bs)
    du_lieu = {
        "hmvs_reason": _o(["hmvs_reason_4", "hmvs_reason_1"]),
        "hmvs_semen_3_2": _o("15 triệu/mL"),
        "hmvs_follow_date": _o("hôm nào đó"),
    }
    for che_do in ("editable", "amendment_mode"):
        sach, cb = await svc.kiem_luu(
            form_id="HMVS",
            version=ban["version"],
            du_lieu=du_lieu,
            che_do=che_do,
            identity=bs,
        )
        assert sach["hmvs_reason"]["gia_tri"] == ["hmvs_reason_1", "hmvs_reason_4"]
        assert [c["ma"] for c in cb] == ["hmvs_follow_date"]
    DA_HOI.clear()
    with pytest.raises(ValidationError, match="chỉ còn đọc"):
        await svc.kiem_luu(
            form_id="HMVS",
            version=ban["version"],
            du_lieu=du_lieu,
            che_do="finalized_locked",
            identity=bs,
        )
    # Hồ sơ đã chốt thì dừng NGAY — chưa kịp hỏi quyền hay đọc khung.
    assert DA_HOI == []
    with pytest.raises(ValidationError, match="không hợp lệ"):
        await svc.kiem_luu(
            form_id="HMVS",
            version=ban["version"],
            du_lieu=du_lieu,
            che_do=None,
            identity=bs,
        )


async def test_cong_luu_chan_khoa_la_va_chu_thay_ma(pool: asyncpg.Pool) -> None:
    bs, _ = await _chuan_bi(pool)
    svc = _svc(pool)
    ban = await svc.khung_theo_ban(form_id="NT", version=None, identity=bs)
    for xau in ({"ly_do": _o("khoá phiếu cũ")}, {"nt_endo_hist": _o(["Tuyến giáp"])}):
        with pytest.raises(ValidationError):
            await svc.kiem_luu(
                form_id="NT",
                version=ban["version"],
                du_lieu=xau,
                che_do="editable",
                identity=bs,
            )


async def test_ma_khong_phai_phieu_kham_bi_chan(pool: asyncpg.Pool) -> None:
    bs, _ = await _chuan_bi(pool)
    with pytest.raises(ValidationError, match="không phải phiếu khám"):
        await _svc(pool).khung_theo_ban(form_id="KQ_SA_VU", version=None, identity=bs)


# ── Ca 4: bản mẫu mới không đổi khung của bản cũ ───────────────────────────
async def test_xuat_ban_v2_khong_doi_ban_cu(pool: asyncpg.Pool) -> None:
    bs, _ = await _chuan_bi(pool)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
    svc = _svc(pool)
    cu = await svc.khung_theo_ban(form_id="SAN_CHAU", version=None, identity=bs)
    khung = json.loads(json.dumps(cu["khung"]))
    ma_moi = f"sc_moi_{uuid.uuid4().hex[:6]}"
    next(m for m in khung if m["ma"] == "B")["block"].append(
        {"ma": ma_moi, "ten": "Ô thêm ở bản mới", "kieu": "text"}
    )
    await FormEngineService(pool).xuat_ban(form_id="SAN_CHAU", khung=khung, identity=ql)

    lai = await svc.khung_theo_ban(
        form_id="SAN_CHAU", version=cu["version"], identity=bs
    )
    assert ma_moi not in cac_o(lai["khung"])
    with pytest.raises(ValidationError, match="không có trong phiếu"):
        await svc.kiem_luu(
            form_id="SAN_CHAU",
            version=cu["version"],
            du_lieu={ma_moi: _o("x")},
            che_do="editable",
            identity=bs,
        )
    moi = await svc.khung_theo_ban(form_id="SAN_CHAU", version=None, identity=bs)
    assert moi["version"] > cu["version"] and ma_moi in cac_o(moi["khung"])
    await svc.kiem_luu(
        form_id="SAN_CHAU",
        version=moi["version"],
        du_lieu={ma_moi: _o("x")},
        che_do="editable",
        identity=bs,
    )


# ── Ca 5: mang sang — lần đo mới nhất của đúng lượt ────────────────────────
async def test_mang_sang(pool: asyncpg.Pool) -> None:
    bs, luot = await _chuan_bi(pool)
    async with pool.acquire() as conn:
        for tren, duoi in ((110, 70), (128, 84)):
            await conn.execute(
                "INSERT INTO vital_measurement (clinic_id, visit_id, systolic,"
                " diastolic, pulse, recorded_by) VALUES ($1::uuid, $2::uuid, $3, $4,"
                " 80, $5::uuid)",
                CLINIC,
                luot["visit"],
                tren,
                duoi,
                bs.staff_id,
            )
        await conn.execute(
            "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
            " recorded_by) VALUES ($1::uuid, $2::uuid, 'Tư vấn ban đầu: đau hạ vị',"
            " $3::uuid)",
            CLINIC,
            luot["consultation"],
            bs.staff_id,
        )
    dau = await _svc(pool).dau_phieu(visit_id=luot["visit"], identity=bs)
    assert dau["sinh_hieu"]["vitals.blood_pressure"] == "128/84"
    assert dau["hanh_chinh"]["patient.birth_year"] == 1991
    assert [g["noi_dung"] for g in dau["tu_van"]] == ["Tư vấn ban đầu: đau hạ vị"]
    assert dau["nhan"]["vitals.weight"] == "CN"


# ── Ca 6: kết quả CLS gắn đúng service_order_id, không theo tên ────────────
async def test_ket_qua_gan_dung_chi_dinh(pool: asyncpg.Pool) -> None:
    bs, luot = await _chuan_bi(pool)
    ma = f"SA{uuid.uuid4().hex[:6].upper()}"
    async with pool.acquire() as conn:
        # Ba chỉ định CÙNG mã, CÙNG tên — chỉ khác id.
        a = await _chi_dinh(conn, bs, luot, ma)
        b = await _chi_dinh(conn, bs, luot, ma)
        c = await _chi_dinh(conn, bs, luot, ma)
        await conn.execute(
            "INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, service_order_id,"
            " khoa, ten_hien_thi, loai_tep, mime, so_byte, sha256,"
            " tai_len_boi_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'KQ đối tác.pdf', 'PDF',"
            " 'application/pdf', 10, repeat('0', 64), $5::uuid)",
            CLINIC,
            luot["patient"],
            b,
            f"test/{uuid.uuid4().hex}.pdf",
            bs.staff_id,
        )
    engine = FormEngineService(pool)
    ph = await engine.mo_phieu(service_order_id=a, form_id="KQ_SA_VU", identity=bs)
    luu = await engine.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"ket_luan": _o("BI-RADS 2")},
        expected_revision=ph["revision"],
        identity=bs,
    )
    await engine.hoan_tat(
        phieu_id=ph["id"], expected_revision=luu["revision"], identity=bs
    )

    ds = await _svc(pool).ket_qua_chi_dinh(visit_id=luot["visit"], identity=bs)
    theo = {d["service_order_id"]: d for d in ds}
    assert theo[a]["ket_qua_trang_thai"] == "CO_KET_QUA"
    assert [k["loai"] for k in theo[a]["ket_qua"]] == ["PHIEU"]
    assert theo[a]["ket_qua"][0]["du_lieu"]["ket_luan"]["gia_tri"] == "BI-RADS 2"
    assert theo[a]["ket_qua"][0]["ban_thu"] == 1
    assert [k["loai"] for k in theo[b]["ket_qua"]] == ["TEP"]
    assert theo[c]["ket_qua_trang_thai"] == "CHUA_CO" and theo[c]["ket_qua"] == []


async def test_nhap_ket_qua_chua_phai_ket_qua(pool: asyncpg.Pool) -> None:
    bs, luot = await _chuan_bi(pool)
    async with pool.acquire() as conn:
        a = await _chi_dinh(conn, bs, luot, f"SA{uuid.uuid4().hex[:6].upper()}")
    engine = FormEngineService(pool)
    ph = await engine.mo_phieu(service_order_id=a, form_id="KQ_SA_GIAP", identity=bs)
    await engine.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"ket_luan": _o("đang gõ dở")},
        expected_revision=ph["revision"],
        identity=bs,
    )
    ds = await _svc(pool).ket_qua_chi_dinh(visit_id=luot["visit"], identity=bs)
    mot = next(d for d in ds if d["service_order_id"] == a)
    assert mot["ket_qua_trang_thai"] == "DANG_NHAP"
    assert mot["ket_qua"][0]["du_lieu"] is None  # nháp không lộ nội dung
