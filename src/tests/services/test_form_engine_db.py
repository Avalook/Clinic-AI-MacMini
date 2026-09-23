"""Form Template Engine trên Postgres thật — khung rỗng, điền, hoàn tất.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55474/postgres \
        poetry run pytest src/tests/services/test_form_engine_db.py
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


async def test_18_mau_deu_co_khung_dang_dung(pool: asyncpg.Pool) -> None:
    so = await pool.fetchval(
        "SELECT count(*) FROM form_definition WHERE clinic_id = $1::uuid"
        " AND trang_thai = 'PUBLISHED' AND form_id LIKE 'KQ_%'",
        CLINIC,
    )
    assert so == 18


async def test_khung_rong_co_du_ba_muc_chung(pool: asyncpg.Pool) -> None:
    """Ruột phòng khám đưa sau; ba mục này là phần na ná nhau của mọi mẫu."""
    khung = json.loads(
        await pool.fetchval(
            "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
            " AND form_id = 'KQ_SA_VU' AND trang_thai = 'PUBLISHED'",
            CLINIC,
        )
    )
    assert [m["ma"] for m in khung] == ["mo_ta", "ket_luan", "de_nghi"]
    assert all(b.get("cho_trong") for m in khung for b in m["block"])


async def test_mo_phieu_hai_lan_khong_tao_hai_phieu(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    p1 = await svc.mo_phieu(service_order_id=order_id, form_id="KQ_SA_VU", identity=bs)
    p2 = await svc.mo_phieu(service_order_id=order_id, form_id="KQ_SA_VU", identity=bs)
    assert p1["id"] == p2["id"]
    assert p1["trang_thai"] == "DRAFT"
    # Ba ô, chưa điền gì.
    assert len(p1["con_trong"]) == 3


async def test_tu_luu_khong_phat_su_kien(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.luu_nhap(
        phieu_id=phieu["id"],
        du_lieu={"mo_ta_chi_tiet": {"gia_tri": "Nhu mô đều", "nguon": "USER"}},
        expected_revision=phieu["revision"],
        identity=bs,
    )
    so_su_kien = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid", order_id
    )
    assert so_su_kien == 0


async def test_hai_nguoi_cung_go_thi_khong_ghi_de_im_lang(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.luu_nhap(
        phieu_id=phieu["id"],
        du_lieu={"ket_luan": {"gia_tri": "Bình thường", "nguon": "USER"}},
        expected_revision=phieu["revision"],
        identity=dd,
    )
    with pytest.raises(ValidationError, match="tải lại"):
        await svc.luu_nhap(
            phieu_id=phieu["id"],
            du_lieu={"ket_luan": {"gia_tri": "Khác", "nguon": "USER"}},
            expected_revision=phieu["revision"],
            identity=bs,
        )


async def test_hoan_tat_xac_nhan_toan_bo_va_phat_su_kien(pool: asyncpg.Pool) -> None:
    """#177: bấm Hoàn tất là nhận trách nhiệm cả câu mẫu không sửa."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        dd = await _nguoi(conn, "NURSE_ULTRASOUND")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=dd
    )
    luu = await svc.luu_nhap(
        phieu_id=phieu["id"],
        du_lieu={
            "mo_ta_chi_tiet": {"gia_tri": "Nhu mô đều", "nguon": "USER"},
            "ket_luan": {
                "gia_tri": "Không thấy bất thường",
                "nguon": "TEMPLATE_DEFAULT",
            },
        },
        expected_revision=phieu["revision"],
        identity=dd,
    )
    # Bác sĩ là người thực hiện; điều dưỡng là người gõ.
    xong = await svc.hoan_tat(
        phieu_id=phieu["id"],
        expected_revision=luu["revision"],
        identity=bs,
        thuc_hien_boi=bs.staff_id,
    )
    assert xong["da_hoan_tat"] is True
    # Còn ô "Đề nghị" chưa điền — vẫn cho hoàn tất, chỉ nhắc.
    assert xong["con_trong"] == ["Đề nghị / lời dặn"]

    dong = await pool.fetchrow(
        "SELECT trang_thai, du_lieu, nhap_boi::text AS nhap,"
        " hoan_tat_boi::text AS xong, thuc_hien_boi::text AS lam"
        "  FROM form_instance WHERE id = $1::uuid",
        phieu["id"],
    )
    assert dong["trang_thai"] == "READY"
    # Câu mẫu đã thành "người dùng xác nhận".
    assert json.loads(dong["du_lieu"])["ket_luan"]["nguon"] == "USER"
    assert dong["nhap"] == dd.staff_id and dong["lam"] == bs.staff_id

    su_kien = await pool.fetchrow(
        "SELECT event_type, payload FROM domain_event"
        " WHERE aggregate_id = $1::uuid AND event_type = 'result_form.completed'",
        phieu["id"],
    )
    assert su_kien is not None
    payload = json.loads(su_kien["payload"])
    assert payload["so_o_con_trong"] == 1
    assert payload["thuc_hien_boi"] == bs.staff_id
    # Không có chữ lâm sàng nào trong payload.
    assert "Nhu mô đều" not in su_kien["payload"]


async def test_khong_co_quyen_thi_khong_dien_duoc(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        le_tan = await _nguoi(conn, "RECEPTION")
    with pytest.raises(SafetyGateError):
        await FormEngineService(pool).mo_phieu(
            service_order_id=str(uuid.uuid4()), form_id="KQ_SA_VU", identity=le_tan
        )


async def test_xuat_ban_ban_moi_khong_doi_phieu_cu(pool: asyncpg.Pool) -> None:
    """Sửa mẫu v1 → v2 không đổi một chữ nào trong phiếu đã điền."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        ql = await _nguoi(conn, "MANAGEMENT")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    # Không so với số 1 tuyệt đối: database thử có thể đã xuất bản vài lần rồi.
    ban_dau = await pool.fetchval(
        "SELECT version FROM form_definition WHERE clinic_id = $1::uuid"
        " AND form_id = 'KQ_SA_GIAP' AND trang_thai = 'PUBLISHED'",
        CLINIC,
    )
    cu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_GIAP", identity=bs
    )
    assert cu["version"] == ban_dau

    await svc.xuat_ban(
        form_id="KQ_SA_GIAP",
        khung=[
            {
                "ma": "mo_ta",
                "ten": "Mô tả",
                "block": [
                    {
                        "ma": "thuy_phai",
                        "ten": "Thuỳ phải",
                        "kieu": "text",
                        "mac_dinh": "",
                    }
                ],
            }
        ],
        identity=ql,
    )

    # Phiếu cũ vẫn ở v1, khung cũ.
    lai = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_GIAP", identity=bs
    )
    assert lai["version"] == ban_dau
    assert [m["ma"] for m in lai["khung"]] == [m["ma"] for m in cu["khung"]]

    # Phiếu mới lấy v2.
    moi = await svc.mo_phieu(
        service_order_id=str(uuid.uuid4()), form_id="KQ_SA_GIAP", identity=bs
    )
    assert moi["version"] == ban_dau + 1
    assert moi["khung"][0]["block"][0]["ma"] == "thuy_phai"


async def test_bac_si_khong_xuat_ban_duoc_mau(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    with pytest.raises(SafetyGateError):
        await FormEngineService(pool).xuat_ban(
            form_id="KQ_SA_VU",
            khung=[{"ma": "x", "ten": "X", "block": []}],
            identity=bs,
        )


async def test_nguon_la_bi_chan_ngay_luc_luu(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    order_id = str(uuid.uuid4())
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    with pytest.raises(ValidationError, match="nguồn lạ"):
        await svc.luu_nhap(
            phieu_id=phieu["id"],
            du_lieu={"ket_luan": {"gia_tri": "x", "nguon": "TU_DAU_RA"}},
            expected_revision=phieu["revision"],
            identity=bs,
        )


# ── Kết quả sẵn sàng, và sửa lại sau khi đã hoàn tất (23/09/2026) ───────────
# Đây là chỗ dễ sai nhất của cả lát: "dịch vụ đã làm xong" và "đã có kết quả để
# đọc" là HAI sự thật, phát ra từ MỘT nút bấm.


async def _don_co_mau(
    conn: asyncpg.Connection, bs: StaffIdentity, *, mode: str
) -> tuple[str, str]:
    """Một chỉ định có gắn mẫu kết quả, và mẫu ấy khai `result_mode`."""
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test kết quả', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        CLINIC,
        f"KQ-{uuid.uuid4().hex[:10]}",
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
    order_id = await conn.fetchval(
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
        # `gan_boi` BẮT BUỘC ở đây, dù test không quan tâm ai gắn: có một bài
        # kiểm khác canh "migration không được tự gắn mẫu cho dịch vụ nào"
        # bằng cách đếm dòng `gan_boi IS NULL`. Dòng test để trống cột ấy trông
        # y hệt một dòng do migration đẻ ra — và bài kiểm kia đỏ oan.
        "INSERT INTO dich_vu_mau_ket_qua"
        " (clinic_id, service_code, mau, result_mode, gan_boi)"
        " VALUES ($1::uuid, $2, 'SA_VU', $3, $4::uuid)",
        CLINIC,
        ma_dv,
        mode,
        bs.staff_id,
    )
    return order_id, vid


async def _su_kien(pool: asyncpg.Pool, phieu_id: str) -> list[str]:
    rows = await pool.fetch(
        "SELECT event_type FROM domain_event WHERE aggregate_id = $1::uuid"
        " ORDER BY seq",
        phieu_id,
    )
    return [r["event_type"] for r in rows]


async def test_hoan_tat_phat_ca_hai_su_that_khi_ket_qua_co_ngay(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order_id, _ = await _don_co_mau(conn, bs, mode="INLINE")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert await _su_kien(pool, phieu["id"]) == [
        "result_form.completed",
        "result.ready",
    ]


async def test_lay_mau_gui_di_thi_khong_bao_da_co_ket_qua(pool: asyncpg.Pool) -> None:
    """Dịch vụ xong hôm nay, kết quả hai ngày sau — không được báo sớm."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order_id, _ = await _don_co_mau(conn, bs, mode="LATER")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert await _su_kien(pool, phieu["id"]) == ["result_form.completed"]


async def test_chua_gan_mau_thi_im_lang_la_khong_co_ket_qua(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=str(uuid.uuid4()), form_id="KQ_SA_VU", identity=bs
    )
    await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    assert "result.ready" not in await _su_kien(pool, phieu["id"])


async def test_sua_duoc_sau_khi_hoan_tat_va_ghi_lai_lan_sua(
    pool: asyncpg.Pool,
) -> None:
    """Tuyền 23/09: "vẫn cho sửa được vì audit log được mà"."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order_id, _ = await _don_co_mau(conn, bs, mode="INLINE")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    xong = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )

    # Chưa bấm [Sửa lại] thì không gõ đè được — chặn tới khi người dùng nói rõ.
    with pytest.raises(ValidationError, match="Sửa lại"):
        await svc.luu_nhap(
            phieu_id=phieu["id"],
            du_lieu={"ket_luan": {"gia_tri": "Đổi ý", "nguon": "USER"}},
            expected_revision=xong["revision"],
            identity=bs,
        )

    mo = await svc.mo_sua(phieu_id=phieu["id"], identity=bs)
    assert mo["dang_sua"] is True
    luu = await svc.luu_nhap(
        phieu_id=phieu["id"],
        du_lieu={"ket_luan": {"gia_tri": "Kết luận đã sửa", "nguon": "USER"}},
        expected_revision=mo["revision"],
        identity=bs,
    )
    lan_sua = await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=luu["revision"], identity=bs
    )
    assert lan_sua["la_lan_sua"] is True

    # Lần sửa KHÔNG sinh thêm một "đã hoàn tất phiếu" thứ hai — nó là bản mới
    # của cùng một kết quả.
    assert await _su_kien(pool, phieu["id"]) == [
        "result_form.completed",
        "result.ready",
        "result.corrected",
    ]
    con = await pool.fetchrow(
        "SELECT trang_thai, dang_sua FROM form_instance WHERE id = $1::uuid",
        phieu["id"],
    )
    assert con is not None
    assert con["trang_thai"] == "READY"
    assert con["dang_sua"] is False


async def test_trong_luc_sua_ban_cu_van_la_ket_qua_chinh_thuc(
    pool: asyncpg.Pool,
) -> None:
    """Không có khoảnh khắc nào bác sĩ mở ra mà thấy trống."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        order_id, _ = await _don_co_mau(conn, bs, mode="INLINE")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=order_id, form_id="KQ_SA_VU", identity=bs
    )
    await svc.hoan_tat(
        phieu_id=phieu["id"], expected_revision=phieu["revision"], identity=bs
    )
    await svc.mo_sua(phieu_id=phieu["id"], identity=bs)
    dong = await pool.fetchrow(
        "SELECT trang_thai, dang_sua FROM form_instance WHERE id = $1::uuid",
        phieu["id"],
    )
    assert dong is not None
    assert dong["trang_thai"] == "READY"
    assert dong["dang_sua"] is True


async def test_phieu_chua_hoan_tat_thi_khong_can_mo_sua(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
    svc = FormEngineService(pool)
    phieu = await svc.mo_phieu(
        service_order_id=str(uuid.uuid4()), form_id="KQ_SA_VU", identity=bs
    )
    with pytest.raises(ValidationError, match="chưa hoàn tất"):
        await svc.mo_sua(phieu_id=phieu["id"], identity=bs)
