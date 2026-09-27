"""Bản in + ảnh kết quả — đợt 3 (27/09/2026), góp ý phòng khám:

· "In phiếu vẫn thấy báo Dịch vụ chưa hoàn tất dù xong rồi" (B11): mở khách
  tự tạo phiếu nháp của mẫu chọn sẵn; đổi mẫu rồi Hoàn tất thì nháp cũ vẫn bị
  in kèm "BẢN NHÁP". Có READY thì chỉ in READY; mở lại khách ở phòng mở phiếu
  READY chứ không phải nháp cũ.
· "Doppler âm vật không có hiển thị ảnh" / "Không hiển thị ảnh ở SA" (B7):
  đọc + liệt kê tệp theo LEGO (không chỉ vai); DICOM không phải ảnh xem được;
  tệp tải ở màn Khách hàng chưa gắn chỉ định vẫn hiện ở khối 2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.api.exceptions import ValidationError as ApiValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_tep_chua_gan
from clinicai.services.form_engine_service import (
    FormEngineService,
    chon_phieu_de_in,
    la_anh_xem_duoc,
)
from clinicai.services.service_execution_service import phieu_chua_hoan_tat
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_form_engine_db import CLINIC, _don_tron, _nguoi
from tests.services.test_service_execution_db import (  # noqa: F401
    KB,
    kb,
    pool,
)

# ── Hàm thuần ─────────────────────────────────────────────────────────────────

_T0 = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def _p(form: str, tt: str, tao: int, xong: int | None = None) -> dict[str, object]:
    return {
        "form_id": form,
        "trang_thai": tt,
        "tao_luc": _T0 + timedelta(minutes=tao),
        "hoan_tat_luc": _T0 + timedelta(minutes=xong) if xong is not None else None,
    }


def test_co_ready_thi_chi_in_ready() -> None:
    nhap = _p("KQ_CHUNG", "DRAFT", 0)
    sa = _p("KQ_SA_TC_BT", "READY", 5, 20)
    assert [r["form_id"] for r in chon_phieu_de_in([nhap, sa])] == ["KQ_SA_TC_BT"]


def test_hai_mau_cung_ready_in_ca_hai_moi_hoan_tat_truoc() -> None:
    a = _p("KQ_SA_TC_BT", "READY", 0, 10)
    b = _p("KQ_SA_TC_PP", "READY", 5, 30)
    nhap = _p("KQ_CHUNG", "DRAFT", 1)
    assert [r["form_id"] for r in chon_phieu_de_in([a, nhap, b])] == [
        "KQ_SA_TC_PP",
        "KQ_SA_TC_BT",
    ]


def test_chi_co_nhap_thi_in_nhap_moi_tao_truoc() -> None:
    a = _p("KQ_CHUNG", "DRAFT", 0)
    b = _p("KQ_SA_VU", "DRAFT", 7)
    assert [r["form_id"] for r in chon_phieu_de_in([a, b])] == ["KQ_SA_VU", "KQ_CHUNG"]


def test_khong_phieu_nao_thi_rong() -> None:
    assert chon_phieu_de_in([]) == []


def test_trang_thai_la_coi_nhu_nhap() -> None:
    """Trạng thái lạ không được lọt thành "chính thức"."""
    la = _p("KQ_CHUNG", "???", 0)
    assert chon_phieu_de_in([la]) == [la]


def test_dicom_khong_phai_anh_xem_duoc() -> None:
    assert la_anh_xem_duoc("ANH", "image/jpeg") is True
    # Dòng cũ lỡ lưu DICOM là ANH vẫn không vào trang ảnh bản in.
    assert la_anh_xem_duoc("ANH", "application/dicom") is False
    assert la_anh_xem_duoc("TAI_LIEU", "application/dicom") is False
    assert la_anh_xem_duoc("VIDEO", "video/mp4") is False
    assert la_anh_xem_duoc(None, None) is False
    assert la_anh_xem_duoc("ANH", None) is True


def test_phieu_chua_hoan_tat() -> None:
    assert phieu_chua_hoan_tat("COMPLETED", ["DRAFT"]) is True
    assert phieu_chua_hoan_tat("COMPLETED", ["DRAFT", "READY"]) is False
    # Dịch vụ không dùng phiếu (chỉ ảnh) — không phải "quên Hoàn tất".
    assert phieu_chua_hoan_tat("COMPLETED", []) is False
    assert phieu_chua_hoan_tat("IN_PROGRESS", ["DRAFT"]) is False
    assert phieu_chua_hoan_tat(None, ["DRAFT"]) is False
    assert phieu_chua_hoan_tat("rác", [None]) is False


# ── B11: bản in + mở lại ở phòng ──────────────────────────────────────────────


async def _hoan_tat(
    svc: FormEngineService, order: str, form: str, ai: StaffIdentity
) -> str:
    p = await svc.mo_phieu(service_order_id=order, form_id=form, identity=ai)
    await svc.hoan_tat(
        phieu_id=p["id"],
        expected_revision=p["revision"],
        identity=ai,
        thuc_hien_boi=ai.staff_id,
    )
    return str(p["id"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_doi_mau_roi_hoan_tat_in_mot_phieu_khong_ban_nhap(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    svc = FormEngineService(pool)

    # Mở khách: phiếu nháp của mẫu chọn sẵn. Chỉ có nháp → vẫn in, BẢN NHÁP.
    await svc.mo_phieu(service_order_id=order, form_id="KQ_CHUNG", identity=bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert [p["form_id"] for p in ban["phieu"]] == ["KQ_CHUNG"]
    assert ban["phieu"][0]["ban_nhap"] is True

    # Đổi mẫu siêu âm rồi Hoàn tất → in đúng một phiếu, không BẢN NHÁP.
    sa = await _hoan_tat(svc, order, "KQ_SA_VU", bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert [p["form_id"] for p in ban["phieu"]] == ["KQ_SA_VU"]
    assert ban["phieu"][0]["ban_nhap"] is False
    # Nháp KHÔNG bị xoá — chỉ không in.
    so_nhap = await pool.fetchval(
        "SELECT count(*) FROM form_instance WHERE service_order_id = $1::uuid"
        " AND trang_thai = 'DRAFT'",
        order,
    )
    assert so_nhap == 1

    # READY đang sửa lại → vẫn in bản chính thức, không BẢN NHÁP.
    await svc.mo_sua(phieu_id=sa, identity=bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert [p["form_id"] for p in ban["phieu"]] == ["KQ_SA_VU"]
    assert ban["phieu"][0]["ban_nhap"] is False

    # Hai mẫu cùng READY → in cả hai, mới hoàn tất trước.
    await _hoan_tat(svc, order, "KQ_CHUNG", bs)
    ban = await svc.in_ket_qua(service_order_id=order, identity=bs)
    assert [p["form_id"] for p in ban["phieu"]] == ["KQ_CHUNG", "KQ_SA_VU"]
    assert all(p["ban_nhap"] is False for p in ban["phieu"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_mo_lai_khach_o_phong_mo_phieu_ready(kb: KB) -> None:  # noqa: F811
    svc = FormEngineService(kb.pool)
    await svc.mo_phieu(service_order_id=kb.order_id, form_id="KQ_CHUNG", identity=kb.bs)
    await _hoan_tat(svc, kb.order_id, "KQ_SA_VU", kb.bs)
    nhin = await kb.svc.xem(order_id=kb.order_id, identity=kb.bs)
    # Màn phòng lấy `phieu[0]` làm mẫu chọn sẵn → phải là phiếu READY.
    assert nhin["phieu"][0]["form_id"] == "KQ_SA_VU"
    assert nhin["phieu"][0]["trang_thai"] == "READY"
    assert nhin["phieu_chua_hoan_tat"] is False


# ── B7: quyền đọc tệp theo lego, tệp chưa gắn chỉ định ────────────────────────


async def _nguoi_tran(conn: asyncpg.Connection, role: str) -> StaffIdentity:
    """Nhân sự KHÔNG có dòng quyền nào (không chép preset)."""
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        f"Test trần {uuid.uuid4().hex[:6]}",
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
    # Có trigger tự chép preset khi tạo nhân sự — gỡ hết để người này TRẦN.
    await conn.execute(
        "DELETE FROM capability_grant WHERE clinic_id = $1::uuid"
        " AND staff_id = $2::uuid",
        CLINIC,
        sid,
    )
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


async def _cap(conn: asyncpg.Connection, ai: StaffIdentity, quyen: str) -> None:
    await conn.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
        " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability WHERE ma = $3"
        " ON CONFLICT DO NOTHING",
        CLINIC,
        ai.staff_id,
        quyen,
    )


async def _tep(
    conn: asyncpg.Connection,
    ai: StaffIdentity,
    *,
    patient: str,
    order: str | None,
    appointment: str | None,
    loai: str = "ANH",
    mime: str = "image/jpeg",
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, appointment_id,"
            " service_order_id, khoa, ten_hien_thi, loai_tep, mime, so_byte, sha256,"
            " tai_len_boi_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, 'anh.jpg', $6, $7,"
            " 10, repeat('0', 64), $8::uuid) RETURNING id::text",
            CLINIC,
            patient,
            appointment,
            order,
            f"{CLINIC}/ket-qua/{patient}/{uuid.uuid4().hex}.jpg",
            loai,
            mime,
            ai.staff_id,
        )
    )


async def _luot_co_lich(
    conn: asyncpg.Connection, bs: StaffIdentity
) -> tuple[str, str, str, str]:
    """(order, visit, patient, appointment) — lượt mở từ một lịch hẹn."""
    order = await _don_tron(conn, bs)
    dong = await conn.fetchrow(
        "SELECT v.visit_id::text AS vid, v.clinic_patient_id::text AS pid"
        "  FROM service_order o JOIN visit v ON v.visit_id = o.visit_id"
        " WHERE o.id = $1::uuid",
        order,
    )
    stid = await conn.fetchval(
        "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid LIMIT 1", CLINIC
    )
    aid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO appointment (id, clinic_id, clinic_patient_id, service_type_id,"
        " slot_start, slot_end, status, location_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, now(),"
        " now() + interval '30 minutes', 'CHECKED_IN', $5::uuid)",
        aid,
        CLINIC,
        dong["pid"],
        stid,
        bs.location_id,
    )
    await conn.execute(
        "UPDATE visit SET appointment_id = $2::uuid WHERE visit_id = $1::uuid",
        dong["vid"],
        aid,
    )
    # Chỉ định trần là 'draft' — đưa lên đã chốt để tải tệp gắn được.
    await conn.execute(
        "UPDATE service_order SET exec_status = 'authorized',"
        " authorized_by = $2::uuid, authorized_at = now() WHERE id = $1::uuid",
        order,
        bs.staff_id,
    )
    return order, dong["vid"], dong["pid"], aid


@pytest.mark.db
@pytest.mark.asyncio
async def test_lego_kham_khong_vai_bac_si_doc_duoc_tep(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order, _vid, pid, aid = await _luot_co_lich(conn, bs)
        tep = await _tep(conn, bs, patient=pid, order=order, appointment=aid)
        # Tài khoản vai Dược (ngoài NORMAL_READ_ROLES), CHỈ có khối khám.
        lego = await _nguoi_tran(conn, "PHARMACIST")
        await _cap(conn, lego, "clinical.consult.perform")
        tran = await _nguoi_tran(conn, "PHARMACIST")
    svc = TepKetQuaService(pool)

    ds = await svc.danh_sach(identity=lego, clinic_patient_id=pid)
    assert tep in {d["id"] for d in ds}
    # Qua cửa quyền → tới bước tìm tệp trên đĩa (test không có tệp thật).
    with pytest.raises(NotFoundError):
        await svc.duong_dan_de_doc(identity=lego, tep_id=tep)
    chi_dinh = await svc.chi_dinh_cua_lich(identity=lego, appointment_id=aid)
    assert [c["service_order_id"] for c in chi_dinh] == [order]

    # Không lego y khoa, không vai đọc → chặn cả ba đường.
    with pytest.raises(SafetyGateError):
        await svc.danh_sach(identity=tran, clinic_patient_id=pid)
    with pytest.raises(SafetyGateError):
        await svc.duong_dan_de_doc(identity=tran, tep_id=tep)
    with pytest.raises(SafetyGateError):
        await svc.chi_dinh_cua_lich(identity=tran, appointment_id=aid)

    # Khác phòng khám: cùng người, phòng khám khác → không mở được tệp.
    khac = StaffIdentity(
        staff_id=lego.staff_id,
        auth_user_id=lego.auth_user_id,
        full_name="Test",
        department="PHARMACIST",
        role=ClinicRole.PHARMACIST,
        clinic_id=str(uuid.uuid4()),
        location_id=lego.location_id,
        location_name="Cơ sở khác",
    )
    with pytest.raises((NotFoundError, SafetyGateError)):
        await svc.duong_dan_de_doc(identity=khac, tep_id=tep)
    with pytest.raises(SafetyGateError):
        await svc.danh_sach(identity=khac, clinic_patient_id=pid)


@pytest.mark.db
@pytest.mark.asyncio
async def test_tep_chua_gan_hien_rieng_khong_ghep_theo_ten(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order, vid, pid, aid = await _luot_co_lich(conn, bs)
        gan = await _tep(conn, bs, patient=pid, order=order, appointment=aid)
        chua = await _tep(conn, bs, patient=pid, order=None, appointment=aid)
        # Tệp của khách nhưng KHÔNG thuộc lịch này → không hiện.
        _khac = await _tep(conn, bs, patient=pid, order=None, appointment=None)
        ds = await doc_tep_chua_gan(conn, clinic_id=CLINIC, visit_id=vid)
    assert [d["tep_id"] for d in ds] == [chua]
    assert gan not in {d["tep_id"] for d in ds}
    assert ds[0]["mime"] == "image/jpeg"


@pytest.mark.db
@pytest.mark.asyncio
async def test_tai_len_chi_dinh_phai_thuoc_luot_dang_chon(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order, _vid, pid, _aid = await _luot_co_lich(conn, bs)
        # Lịch khác của CÙNG khách.
        stid = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid LIMIT 1",
            CLINIC,
        )
        lich_khac = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO appointment (id, clinic_id, clinic_patient_id,"
            " service_type_id, slot_start, slot_end, status, location_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, now(),"
            " now() + interval '30 minutes', 'CHECKED_IN', $5::uuid)",
            lich_khac,
            CLINIC,
            pid,
            stid,
            bs.location_id,
        )
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    with pytest.raises((ValidationError, ApiValidationError)):
        await TepKetQuaService(pool).tai_len(
            identity=bs,
            clinic_patient_id=pid,
            data=jpg,
            ten_hien_thi="anh.jpg",
            appointment_id=lich_khac,
            service_order_id=order,
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_ban_in_bo_dicom_khoi_trang_anh(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order, _vid, pid, aid = await _luot_co_lich(conn, bs)
        anh = await _tep(conn, bs, patient=pid, order=order, appointment=aid)
        # Dòng cũ lỡ mang ANH + dòng mới TAI_LIEU: cả hai là DICOM.
        await _tep(
            conn,
            bs,
            patient=pid,
            order=order,
            appointment=aid,
            mime="application/dicom",
        )
        await _tep(
            conn,
            bs,
            patient=pid,
            order=order,
            appointment=aid,
            loai="TAI_LIEU",
            mime="application/dicom",
        )
    ban = await FormEngineService(pool).in_ket_qua(service_order_id=order, identity=bs)
    assert [a["id"] for a in ban["anh"]] == [anh]
    assert ban["so_tep_khac"] == 2
