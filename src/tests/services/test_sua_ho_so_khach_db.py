"""Test sửa hồ sơ khách đủ trường hành chính + CCCD + email trên Postgres thật.

Yêu cầu G1 (tệp viec-cho-codex-1410.md):
- Sửa từng trường (address, gender, ethnicity, nationality, occupation,
  patient_objection, guardian_name, email, national_id_number 9 số & 12 số,
  full_name, date_of_birth) -> đọc lại từ DB đúng.
- Khách Notion có SĐT lạ: chỉ sửa địa chỉ -> lưu thành công, SĐT không đổi.
- Email rác -> 422 tiếng Việt; email rỗng/null -> cập nhật email IS NULL.
- CCCD rác (không phải 9 hoặc 12 số) -> 422; 9 hoặc 12 số -> lưu thành công.
- Thử ngược: bỏ trường khỏi DTO -> đỏ.
- Hai người cùng sửa: sua_luc cũ -> 409 ConflictError.
- Xuất hoá đơn kế toán (XuatHoaDonService.xem): có email khi khách có patient.email.
"""

from __future__ import annotations

import datetime
import uuid

import asyncpg
import pytest
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.schemas.patient import PatientUpdateDTO
from clinicai.services.patient_service import _UPDATE_COLUMNS, PatientService
from clinicai.services.quay_thu_service import ma_phieu
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _tao_khach_test(
    conn: asyncpg.Connection,
    loc_id: str,
    phone_primary: str = "0901234567",
    email: str | None = None,
) -> tuple[uuid.UUID, StaffIdentity]:
    pid = await conn.fetchval(
        """
        INSERT INTO patient (
            clinic_id, patient_code, full_name, location_id,
            phone_primary, email, date_of_birth
        )
        VALUES ($1::uuid, $2, 'Bệnh Nhân Ban Đầu', $3::uuid, $4, $5, '1990-01-01')
        RETURNING clinic_patient_id;
        """,
        CLINIC,
        f"BN-{uuid.uuid4().hex[:8]}",
        loc_id,
        phone_primary,
        email,
    )
    staff = StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Nhân viên CSKH",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id=loc_id,
        location_name="Cơ sở test",
    )
    return pid, staff


async def test_sua_tung_truong_hanh_chinh(pool: asyncpg.Pool) -> None:
    """Sửa từng trường hành chính, CCCD 9 và 12 số, email -> đọc lại DB đúng."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
        pid, staff = await _tao_khach_test(conn, loc)

    svc = PatientService(pool)

    # 1. Cập nhật đồng loạt các trường hành chính
    dto = PatientUpdateDTO(
        full_name="Nguyễn Thị Mai Lan",
        date_of_birth=datetime.date(1995, 8, 20),
        gender="Nữ",
        ethnicity="Kinh",
        nationality="Việt Nam",
        occupation="Kỹ sư phần mềm",
        patient_objection="Dị ứng kháng sinh nhóm Beta-lactam",
        address="Số 10 Phố Huế, Hàng Bài, Hoàn Kiếm, Hà Nội",
        guardian_name="Trần Văn Ba",
        email="mai.lan@example.com",
        national_id_number="001195000123",  # 12 số
    )
    res = await svc.update_patient(pid, dto, identity=staff)
    assert res.full_name == "Nguyễn Thị Mai Lan"
    assert res.gender == "Nữ"
    assert res.email == "mai.lan@example.com"
    # national_id_number trả về qua DTO bị che
    assert res.national_id_number == "001*******23"

    # Đọc trực tiếp Postgres kiểm tra
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT full_name, date_of_birth, gender, ethnicity, nationality,
                   occupation, patient_objection, address, guardian_name, email,
                   national_id_number
            FROM patient
            WHERE clinic_patient_id = $1;
            """,
            pid,
        )
        assert row is not None
        assert row["full_name"] == "Nguyễn Thị Mai Lan"
        assert row["date_of_birth"] == datetime.date(1995, 8, 20)
        assert row["gender"] == "Nữ"
        assert row["ethnicity"] == "Kinh"
        assert row["nationality"] == "Việt Nam"
        assert row["occupation"] == "Kỹ sư phần mềm"
        assert row["patient_objection"] == "Dị ứng kháng sinh nhóm Beta-lactam"
        assert row["address"] == "Số 10 Phố Huế, Hàng Bài, Hoàn Kiếm, Hà Nội"
        assert row["guardian_name"] == "Trần Văn Ba"
        assert row["email"] == "mai.lan@example.com"
        assert row["national_id_number"] == "001195000123"

    # 2. Sửa riêng CCCD 9 số (CMND cũ)
    dto_cmnd = PatientUpdateDTO(national_id_number="123456789")
    await svc.update_patient(pid, dto_cmnd, identity=staff)
    async with pool.acquire() as conn:
        cccd_db = await conn.fetchval(
            "SELECT national_id_number FROM patient WHERE clinic_patient_id = $1;",
            pid,
        )
        assert cccd_db == "123456789"


async def test_khach_notion_sdt_la_sua_dia_chi_thanh_cong(pool: asyncpg.Pool) -> None:
    """Khách Notion có SĐT lạ: sửa địa chỉ vẫn lưu được vì SĐT không gửi lại."""
    notion_phones = ["02438888888", "+14155552671", "0912-345-678"]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
        for phone in notion_phones:
            pid, staff = await _tao_khach_test(conn, loc, phone_primary=phone)
            svc = PatientService(pool)

            # Chỉ sửa địa chỉ, không gửi phone_primary
            dto = PatientUpdateDTO(address="Địa chỉ mới từ CSKH")
            updated = await svc.update_patient(pid, dto, identity=staff)
            assert updated.address == "Địa chỉ mới từ CSKH"

            # DB vẫn giữ nguyên SĐT cũ của Notion
            phone_db = await conn.fetchval(
                "SELECT phone_primary FROM patient WHERE clinic_patient_id = $1;",
                pid,
            )
            assert phone_db == phone


async def test_email_rac_va_email_null(pool: asyncpg.Pool) -> None:
    """Email rác ném lỗi tiếng Việt; email rỗng/null xoá về NULL trong DB."""
    # 1. Email rác
    for bad in ["khong-phai-email", "abc@", "@domain.com", "a" * 250 + "@b.com"]:
        with pytest.raises(PydanticValidationError) as exc_info:
            PatientUpdateDTO(email=bad)
        assert "Email không đúng định dạng" in str(exc_info.value)

    # 2. Email rỗng / khoảng trắng -> chuyển thành None
    dto_blank = PatientUpdateDTO(email="   ")
    assert dto_blank.email is None

    # 3. Cập nhật email thành NULL trong DB
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
        pid, staff = await _tao_khach_test(conn, loc, email="cu@example.com")

    svc = PatientService(pool)
    # Gửi email=None tường minh để xoá
    await svc.update_patient(pid, PatientUpdateDTO(email=None), identity=staff)

    async with pool.acquire() as conn:
        email_db = await conn.fetchval(
            "SELECT email FROM patient WHERE clinic_patient_id = $1;",
            pid,
        )
        assert email_db is None


async def test_cccd_rac_va_hop_le(pool: asyncpg.Pool) -> None:
    """CCCD rác (không phải 9 hoặc 12 số) ném lỗi; 9 hoặc 12 số hợp lệ."""
    # CCCD rác
    rac_list = [
        "123",
        "12345678",
        "1234567890",
        "12345678901",
        "1234567890123",
        "abc123456",
    ]
    for bad_cccd in rac_list:
        with pytest.raises(PydanticValidationError) as exc_info:
            PatientUpdateDTO(national_id_number=bad_cccd)
        assert "Số CCCD phải gồm 9 hoặc 12 chữ số" in str(exc_info.value)

    # CCCD hợp lệ
    dto_9 = PatientUpdateDTO(national_id_number="123456789")
    assert dto_9.national_id_number == "123456789"
    dto_12 = PatientUpdateDTO(national_id_number="001190000001")
    assert dto_12.national_id_number == "001190000001"


async def test_thu_nguoc_bo_truong_khoi_dto() -> None:
    """Thử ngược: kiểm tra các trường hành chính bắt buộc trong DTO và cột update."""
    bat_buoc = {
        "full_name",
        "date_of_birth",
        "gender",
        "ethnicity",
        "nationality",
        "occupation",
        "patient_objection",
        "address",
        "guardian_name",
        "email",
        "national_id_number",
    }
    fields = set(PatientUpdateDTO.model_fields.keys())
    for f in bat_buoc:
        assert f in fields, f"Trường {f} bị thiếu trong PatientUpdateDTO!"
        assert f in _UPDATE_COLUMNS, f"Trường {f} bị thiếu trong _UPDATE_COLUMNS!"


async def test_khoa_lac_quan_409(pool: asyncpg.Pool) -> None:
    """Hai người cùng sửa: người gửi sua_luc cũ bị báo 409 ConflictError."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
        pid, staff1 = await _tao_khach_test(conn, loc)
        staff2 = StaffIdentity(
            staff_id=str(uuid.uuid4()),
            auth_user_id=str(uuid.uuid4()),
            full_name="Nhân viên 2",
            department="CSKH",
            role=ClinicRole.CSKH,
            clinic_id=CLINIC,
            location_id=loc,
            location_name="Cơ sở test",
        )

    svc = PatientService(pool)
    p_ban_dau = await svc.get_by_id(pid, clinic_id=CLINIC)
    assert p_ban_dau is not None
    moc_cu = p_ban_dau.updated_at

    # Người 1 cập nhật thành công kèm thẻ khoá lạc quan moc_cu
    await svc.update_patient(
        pid,
        PatientUpdateDTO(address="Địa chỉ người 1 sửa", sua_luc=moc_cu),
        identity=staff1,
    )

    # Người 2 gửi sửa kèm moc_cu (nay đã cũ vì người 1 vừa sửa) -> 409 ConflictError
    with pytest.raises(ConflictError) as exc_info:
        await svc.update_patient(
            pid,
            PatientUpdateDTO(address="Địa chỉ người 2 sửa", sua_luc=moc_cu),
            identity=staff2,
        )
    assert "Hồ sơ này vừa được người khác sửa" in str(exc_info.value)


async def test_xuat_hoa_don_doc_patient_email(pool: asyncpg.Pool) -> None:
    """XuatHoaDonService đọc email trực tiếp từ cột patient.email."""
    q = await tao_quay(pool)
    manager = StaffIdentity(
        staff_id=q.thu_ngan.staff_id,
        auth_user_id=q.thu_ngan.auth_user_id,
        full_name=q.thu_ngan.full_name,
        department="Ban Giám Đốc",
        role=ClinicRole.MANAGEMENT,
        clinic_id=q.thu_ngan.clinic_id,
        location_id=q.thu_ngan.location_id,
        location_name="Cơ sở test",
    )
    cycle = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO payment_cycle(
            payment_cycle_id, clinic_id, visit_id, kind, amount,
            status, legacy, paid_at, closed_at, created_at, created_by,
            confirmed_by, method
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, 'dich_vu', 200000,
            'PAID', true, now(), NULL, now(), $4::uuid, $4::uuid, 'TRANSFER'
        );
        """,
        cycle,
        manager.clinic_id,
        q.visit_id,
        manager.staff_id,
    )
    await pool.execute(
        """
        INSERT INTO payment_bill_line(
            clinic_id, payment_cycle_id, visit_id, kind, source_type,
            source_id, name_snapshot, quantity, unit, unit_price,
            line_total, billing_owner
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, 'dich_vu', 'exam',
            'x', 'Khám tổng quát', 1, 'Lần', 200000, 200000, 'CLINIC'
        );
        """,
        manager.clinic_id,
        cycle,
        q.visit_id,
    )

    # Đặt email trực tiếp trên bảng patient
    await pool.execute(
        """
        UPDATE patient p
        SET email = 'email_chinh_thuc@example.com'
        FROM visit v
        WHERE v.visit_id = $1::uuid AND p.clinic_patient_id = v.clinic_patient_id;
        """,
        q.visit_id,
    )

    day = now_vn().date().isoformat()
    data = await XuatHoaDonService(pool).xem(identity=manager, tu=day, den=day)
    ma = {h["ma_phieu"]: h for h in data["hoa_don"]}
    assert ma_phieu(cycle) in ma
    hd = ma[ma_phieu(cycle)]
    assert hd["email"] == "email_chinh_thuc@example.com"


async def test_dau_vao_rac_khong_bi_500() -> None:
    """Đầu vào rác (full_name/location_id gửi null/rỗng) bị chặn 422, không 500."""
    with pytest.raises(PydanticValidationError) as exc:
        PatientUpdateDTO(full_name=None)
    assert "Họ và tên không được để trống" in str(exc.value)

    with pytest.raises(PydanticValidationError) as exc:
        PatientUpdateDTO(full_name="   ")
    assert "Họ và tên không được để trống" in str(exc.value)

    with pytest.raises(PydanticValidationError) as exc:
        PatientUpdateDTO(location_id=None)
    assert "Cơ sở không được để trống" in str(exc.value)

    with pytest.raises(PydanticValidationError) as exc:
        PatientUpdateDTO(is_active=None)
    assert "Trạng thái hoạt động không được để trống" in str(exc.value)


async def test_so_dien_thoai_co_dinh_02_tao_va_sua_duoc(pool: asyncpg.Pool) -> None:
    """SĐT cố định 02 tạo/sửa được; normalize_vn_phone giữ nguyên không nhận."""
    from clinicai.core.phone import normalize_vn_phone
    from clinicai.schemas.patient import PatientCreateDTO

    # normalize_vn_phone giữ nguyên KHÔNG nhận số bàn (tránh gộp nhầm MPI)
    assert normalize_vn_phone("0281234567") is None
    assert normalize_vn_phone("0241234567") is None

    # Tạo và sửa hồ sơ với số bàn 02 hợp lệ
    dto_create = PatientCreateDTO(
        full_name="Khách Dùng Số Bàn",
        location_id=uuid.uuid4(),
        phone_primary="0281234567",
    )
    assert dto_create.phone_primary == "0281234567"

    dto_update = PatientUpdateDTO(phone_primary="0247654321")
    assert dto_update.phone_primary == "0247654321"

    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1;",
            CLINIC,
        )
        pid, staff = await _tao_khach_test(conn, loc, phone_primary="0281234567")

    svc = PatientService(pool)
    updated = await svc.update_patient(pid, dto_update, identity=staff)
    assert updated.phone_primary == "0247654321"

    async with pool.acquire() as conn:
        phone_db = await conn.fetchval(
            "SELECT phone_primary FROM patient WHERE clinic_patient_id = $1;",
            pid,
        )
        assert phone_db == "0247654321"
