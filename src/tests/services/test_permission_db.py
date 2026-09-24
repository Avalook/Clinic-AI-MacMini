"""Quyền theo capability trên Postgres thật — mô hình 5 lớp.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55473/postgres \\
        poetry run pytest src/tests/services/test_permission_db.py

Bảy điều phải đúng:
  1. Người chưa được cấp thì không làm được, dù vai "nghe có vẻ đúng".
  2. Quản lý bật một KHỐI là người ấy làm được ngay (không cần sửa code).
  3. Quản lý cấp được khối NẰM NGOÀI preset của vai — preset chỉ là gợi ý.
  4. Thu khối thì mất quyền, nhưng dòng cũ không bị xoá (còn tra được).
  5. Không ai cấp quyền được nếu không có `permission.manage`.
  6. Không cấp cho người ngoài phòng khám của mình.
  7. Mọi lần cấp/thu đều để lại sự kiện có tên người làm.
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
from clinicai.permissions.can import can, quyen_hieu_luc
from clinicai.services.permission_service import (
    PermissionService,
    cap_preset_mac_dinh,
)

CLINIC = "a0000000-0000-4000-8000-000000000001"
# Một phòng khám thứ hai, tự dựng: dữ liệu seed chỉ có một phòng khám.
CLINIC_KHAC_CODE = "PK-TEST-KHAC"

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


async def _nguoi(
    conn: asyncpg.Connection, role: str, *, clinic_id: str = CLINIC
) -> StaffIdentity:
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        clinic_id,
        sid,
        role,
    )

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=clinic_id,
        location_id=loc,
        location_name="Cơ sở test",
    )


@pytest_asyncio.fixture
async def quan_ly(pool: asyncpg.Pool) -> StaffIdentity:
    """Một quản lý thật: có khối Phân quyền nên chỉnh được cho người khác."""
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability"
            " WHERE work_pack = 'quan_tri_quyen' ON CONFLICT DO NOTHING",
            CLINIC,
            ql.staff_id,
        )
    return ql


async def test_chua_cap_thi_khong_lam_duoc(pool: asyncpg.Pool) -> None:
    """Vai nghe "có vẻ đúng" không đủ: quyền phải được cấp thật.

    23/09/2026 đổi ví dụ từ ĐIỀU DƯỠNG sang THU NGÂN. Không nới luật — luật vẫn
    y nguyên — mà vì ví dụ cũ đã sai nghiệp vụ: Tuyền chốt bác sĩ = thư ký y
    khoa = điều dưỡng cùng đặt chỉ định được. Bài kiểm ấy không chỉ CHO PHÉP
    cái sai, nó CANH cho cái sai không đổi.

    Thu ngân là ví dụ đúng: nhóm mẫu của họ không có khối Chỉ định, nên chưa ai
    cấp thì không đặt chỉ định được, dù màn hình có hiện nút hay không.
    """
    async with pool.acquire() as conn:
        thu_ngan = await _nguoi(conn, "CASHIER")
        assert await can(conn, thu_ngan, "clinical.order.place") is False


async def test_dieu_duong_dat_duoc_chi_dinh_ngay_tu_dau(pool: asyncpg.Pool) -> None:
    """Không phải chờ quản lý tick thêm (Tuyền chốt 23/09/2026).

    KHÔNG SUY RỘNG: đây là quyền đặt chỉ định. Ký bệnh án và duyệt/phát hành kết
    quả là quyền khác, và bài kiểm này không nói gì về chúng.

    `_nguoi` ở tệp này CỐ Ý không cấp preset — cả tệp xoay quanh "chưa cấp thì
    chưa có". Nên bài này gọi `cap_preset_mac_dinh` đúng như `staff_service` làm
    lúc thêm nhân sự thật: thứ cần chứng minh là NHÓM MẪU đã có khối Chỉ định,
    không phải ai đó tick tay.
    """
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
        await cap_preset_mac_dinh(
            conn, clinic_id=CLINIC, staff_id=dd.staff_id, vai="NURSE_ULTRASOUND"
        )
        assert await can(conn, dd, "clinical.order.place") is True


async def test_quan_ly_bat_mot_khoi_la_lam_duoc_ngay(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        # Thu ngân, vì nhóm mẫu của họ không có khối Chỉ định — đúng thứ bài
        # này cần: một người CHƯA có quyền, rồi quản lý bật cho.
        ai_do = await _nguoi(conn, "CASHIER")

    svc = PermissionService(pool)
    kq = await svc.cap_khoi(staff_id=ai_do.staff_id, khoi="chi_dinh", identity=quan_ly)
    assert kq["da_cap"] == ["clinical.order.place"]

    async with pool.acquire() as conn:
        # Không sửa dòng code nào: thu ngân chỉ định được.
        assert await can(conn, ai_do, "clinical.order.place") is True
        assert "clinical.order.place" in await quyen_hieu_luc(conn, ai_do)


async def test_cap_duoc_khoi_ngoai_preset_cua_vai(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Preset chỉ là gợi ý — không phải trần quyền (#132)."""
    async with pool.acquire() as conn:
        thu_ngan = await _nguoi(conn, "CASHIER")

    await PermissionService(pool).cap_khoi(
        staff_id=thu_ngan.staff_id, khoi="sinh_hieu", identity=quan_ly
    )
    async with pool.acquire() as conn:
        assert await can(conn, thu_ngan, "vitals.measure") is True


async def test_thu_khoi_thi_mat_quyen_nhung_van_tra_duoc_lich_su(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")

    svc = PermissionService(pool)
    await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    await svc.thu_khoi(
        staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly, ly_do="Hết ca"
    )

    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is False
        dong = await conn.fetchrow(
            "SELECT revoked_at, revoked_by::text AS ai, ly_do FROM capability_grant"
            " WHERE staff_id = $1::uuid AND capability = 'clinical.order.place'",
            dd.staff_id,
        )
    # Dòng cũ còn nguyên: vẫn trả lời được ai từng có quyền gì.
    assert dong is not None
    assert dong["revoked_at"] is not None
    assert dong["ai"] == quan_ly.staff_id
    assert dong["ly_do"] == "Hết ca"


async def test_cap_lai_thi_cap_duoc_lan_nua(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    svc = PermissionService(pool)
    await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    await svc.thu_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    lai = await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    assert lai["da_cap"] == ["clinical.order.place"]
    async with pool.acquire() as conn:
        assert await can(conn, dd, "clinical.order.place") is True


async def test_cap_hai_lan_khong_tao_hai_dong(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    svc = PermissionService(pool)
    await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    lan_2 = await svc.cap_khoi(staff_id=dd.staff_id, khoi="chi_dinh", identity=quan_ly)
    # Không có gì xảy ra thì không kể lại — và không nhân đôi dòng.
    assert lan_2["da_cap"] == []
    async with pool.acquire() as conn:
        so = await conn.fetchval(
            "SELECT count(*) FROM capability_grant WHERE staff_id = $1::uuid"
            " AND capability = 'clinical.order.place' AND revoked_at IS NULL",
            dd.staff_id,
        )
    assert so == 1


async def test_khong_co_quyen_phan_quyen_thi_khong_cap_duoc(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        bac_si = await _nguoi(conn, "DOCTOR")
        nan_nhan = await _nguoi(conn, "NURSE_ULTRASOUND")
        # Bác sĩ có khối Chỉ định nhưng KHÔNG có Phân quyền.
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($1::uuid, $2::uuid, 'clinical.order.place', 'chi_dinh')"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            bac_si.staff_id,
        )

    with pytest.raises(SafetyGateError):
        await PermissionService(pool).cap_khoi(
            staff_id=nan_nhan.staff_id, khoi="chi_dinh", identity=bac_si
        )


async def test_khong_cap_cho_nguoi_ngoai_phong_kham(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        clinic_khac = await conn.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, $2,"
            " 'Asia/Ho_Chi_Minh') ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name"
            " RETURNING id::text",
            CLINIC_KHAC_CODE,
            "Phòng khám khác (test)",
        )
        nguoi_la = await _nguoi(conn, "RECEPTION", clinic_id=clinic_khac)

    with pytest.raises(ValidationError):
        await PermissionService(pool).cap_khoi(
            staff_id=nguoi_la.staff_id, khoi="chi_dinh", identity=quan_ly
        )


async def test_moi_lan_cap_deu_de_lai_su_kien(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")

    await PermissionService(pool).cap_khoi(
        staff_id=dd.staff_id, khoi="sinh_hieu", identity=quan_ly
    )
    dong = await pool.fetchrow(
        "SELECT event_type, actor_staff_id::text AS ai, payload, is_public"
        "  FROM domain_event WHERE aggregate_id = $1::uuid"
        "   AND event_type = 'capability.granted'",
        dd.staff_id,
    )
    assert dong is not None
    assert dong["ai"] == quan_ly.staff_id
    # Quyền là chuyện nội bộ: AI và đối tác không có việc gì phải nghe.
    assert dong["is_public"] is False
    assert "vitals.measure" in dong["payload"]


async def test_them_preset_la_chep_mot_loat_khoi(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """ "Thêm nhanh preset Lễ tân" = chép khối, không phải thừa kế sống (#134)."""
    async with pool.acquire() as conn:
        ai_do = await _nguoi(conn, "NURSE_ULTRASOUND")

    await PermissionService(pool).them_preset(
        staff_id=ai_do.staff_id, vai="RECEPTION", identity=quan_ly
    )
    async with pool.acquire() as conn:
        co = await quyen_hieu_luc(conn, ai_do)
    assert "reception.checkin.perform" in co
    assert "payment.service.collect" in co


# ── Nhóm quyền mẫu: quản lý tự thêm, sửa, xoá (Tuyền 23/09/2026) ────────────
# Trước hôm nay, preset là hằng số trong Python. Bộ test này giữ ba lằn ranh:
# nhóm KHÔNG phải quyền · sửa nhóm không đổi quyền người cũ · nhóm dựng sẵn tắt
# chứ không xoá mất dấu.


async def test_nhom_dung_san_khop_voi_hang_so_trong_ma(pool: asyncpg.Pool) -> None:
    """Lệch nghĩa là người mới được cấp khác bộ quản lý nhìn thấy trên màn."""
    from clinicai.permissions.catalogue import PRESET

    rows = await pool.fetch(
        "SELECT ma, khoi FROM quyen_preset WHERE clinic_id = $1::uuid AND he_thong",
        CLINIC,
    )
    trong_db = {r["ma"]: sorted(r["khoi"]) for r in rows}
    for vai, khoi in PRESET.items():
        assert vai in trong_db, f"nhóm dựng sẵn thiếu {vai}"
        assert trong_db[vai] == sorted(khoi), f"nhóm {vai} lệch với hằng số"


async def test_quan_ly_them_nhom_moi_roi_cap_cho_nguoi(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    async with pool.acquire() as conn:
        ai_do = await _nguoi(conn, "CASHIER")
    svc = PermissionService(pool)

    # Mã ngẫu nhiên: database thử dùng lại giữa các lần chạy, và một bài kiểm
    # đỏ chỉ vì lần chạy trước để lại dòng cũ là một bài kiểm nói dối.
    ma = f"ca_toi_{uuid.uuid4().hex[:6]}"
    moi = await svc.luu_nhom(
        ma=ma,
        ten="Điều dưỡng ca tối",
        khoi=["sinh_hieu", "dieu_phoi"],
        mo_ta=None,
        identity=quan_ly,
    )
    assert moi["ma"] == ma.upper() and moi["moi"] is True

    await svc.them_preset(staff_id=ai_do.staff_id, vai=ma, identity=quan_ly)
    async with pool.acquire() as conn:
        assert await can(conn, ai_do, "vitals.measure") is True


async def test_sua_nhom_khong_doi_quyen_cua_nguoi_da_cap(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    """Nếu nó đổi được thì một lần sửa nhóm là âm thầm đổi quyền mười người."""
    async with pool.acquire() as conn:
        ai_do = await _nguoi(conn, "CASHIER")
    svc = PermissionService(pool)
    ma = f"TAM_THOI_{uuid.uuid4().hex[:6].upper()}"
    await svc.luu_nhom(
        ma=ma, ten="Nhóm tạm", khoi=["sinh_hieu"], mo_ta=None, identity=quan_ly
    )
    await svc.them_preset(staff_id=ai_do.staff_id, vai=ma, identity=quan_ly)

    # Bỏ khối khỏi NHÓM — người đã cấp vẫn giữ nguyên quyền.
    await svc.luu_nhom(ma=ma, ten="Nhóm tạm", khoi=[], mo_ta=None, identity=quan_ly)
    async with pool.acquire() as conn:
        assert await can(conn, ai_do, "vitals.measure") is True


async def test_khoi_khong_co_that_thi_tu_choi(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    with pytest.raises(ValidationError, match="không có thật"):
        await PermissionService(pool).luu_nhom(
            ma="BAY",
            ten="Nhóm bịa",
            khoi=["khoi_khong_ton_tai"],
            mo_ta=None,
            identity=quan_ly,
        )


async def test_nhom_dung_san_thi_tat_chu_khong_xoa_mat_dau(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    svc = PermissionService(pool)
    kq = await svc.xoa_nhom(ma="CASHIER_THUOC", identity=quan_ly)
    assert kq.get("da_tat") is True
    con = await pool.fetchval(
        "SELECT active FROM quyen_preset WHERE clinic_id = $1::uuid AND ma = $2",
        CLINIC,
        "CASHIER_THUOC",
    )
    assert con is False


async def test_nhom_tu_dat_thi_xoa_han(
    pool: asyncpg.Pool, quan_ly: StaffIdentity
) -> None:
    svc = PermissionService(pool)
    ma = f"XOA_THU_{uuid.uuid4().hex[:6].upper()}"
    await svc.luu_nhom(ma=ma, ten="Xoá thử", khoi=[], mo_ta=None, identity=quan_ly)
    kq = await svc.xoa_nhom(ma=ma, identity=quan_ly)
    assert kq.get("da_xoa") is True
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM quyen_preset WHERE clinic_id = $1::uuid AND ma = $2",
            CLINIC,
            ma,
        )
        == 0
    )


async def test_khong_co_quyen_phan_quyen_thi_khong_sua_duoc_nhom(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        thu_ngan = await _nguoi(conn, "CASHIER")
    with pytest.raises(SafetyGateError):
        await PermissionService(pool).luu_nhom(
            ma="LEN_LUT",
            ten="Tự cấp",
            khoi=["quan_tri_quyen"],
            mo_ta=None,
            identity=thu_ngan,
        )
