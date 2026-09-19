"""Contract tiền–thuốc CP1: hoá đơn do máy chủ tính, định danh thuốc kho, số
lượng mua, bên thu tiền, ảnh chụp hoá đơn (19/09/2026).

Mỗi test dựng một lượt riêng với MÃ DỊCH VỤ, LOẠI KHÁM và THUỐC mang đuôi ngẫu
nhiên — không đụng bảng giá / danh mục mà các test khác dùng.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import BillChangedError, ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@dataclass
class Quay:
    pool: asyncpg.Pool
    visit_id: str
    consultation_id: str
    thu_ngan: StaffIdentity
    duoc_si: StaffIdentity
    bac_si: StaffIdentity
    duoi: str


async def _gia_dv(
    conn: asyncpg.Connection, ma: str, ten: str, gia: int | None, ben: str = "CLINIC"
) -> None:
    await conn.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price, billing_owner, node_code)"
        " VALUES ($1::uuid, 'dich_vu', $2, $3, $4, $5, 'DICHVU-SIEUAM')",
        CLINIC,
        ma,
        ten,
        gia,
        ben,
    )


@pytest_asyncio.fixture
async def q(pool: asyncpg.Pool) -> Quay:
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        thu_ngan = await _nguoi(conn, loc, "CASHIER")
        duoc_si = await _nguoi(conn, loc, "PHARMACIST")
        st = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name) VALUES ($1::uuid, $2,"
            " $3) RETURNING id::text",
            CLINIC,
            f"KT-{duoi}",
            f"Khám thử {duoi}",
        )
        await _gia_dv(conn, f"KHAM-{duoi}", f"Khám thử {duoi}", 150_000)
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN thử tiền thuốc', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"TT-{duoi}",
            loc,
        )
        appt = await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, now(),"
            " now() + interval '15 minutes', 'COMPLETED') RETURNING id::text",
            CLINIC,
            pid,
            loc,
            st,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at, appointment_id)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', $3::uuid, now(), $4::uuid)"
            " RETURNING visit_id::text",
            CLINIC,
            pid,
            bac_si.staff_id,
            appt,
        )
        con = await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY') RETURNING id::text",
            CLINIC,
            vid,
        )
    return Quay(pool, vid, con, thu_ngan, duoc_si, bac_si, duoi)


async def _chi_dinh(q: Quay, ma: str, ten: str) -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'DICHVU-SIEUAM',"
            " 'authorized', $6::uuid, $6::uuid, now()) RETURNING id::text",
            CLINIC,
            q.visit_id,
            q.consultation_id,
            ma,
            ten,
            q.bac_si.staff_id,
        )
    )


async def _thuoc(q: Quay, gia: int | None = 5_000, ten: str | None = None) -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
            " VALUES ($1::uuid, $2, $2, $3) RETURNING id::text",
            CLINIC,
            ten or f"Thuốc thử {q.duoi}",
            gia,
        )
    )


async def _don(q: Quay, so: int = 10, ten: str = "thuoc go tay") -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, $3, $4, $5,"
            " 'viên' FROM visit v WHERE v.visit_id = $6::uuid RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            ten,
            f"{so} viên",
            so,
            q.visit_id,
        )
    )


async def _hd(q: Quay, kind: str):  # type: ignore[no-untyped-def]
    async with q.pool.acquire() as conn:
        return await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind=kind
        )


async def _thu(q: Quay, kind: str, **kw) -> None:  # type: ignore[no-untyped-def]
    await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind=kind,
        amount=kw.get("amount"),
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=kw.get("bill_revision"),
    )


async def _phieu(q: Quay, kind: str) -> asyncpg.Record | None:
    return await q.pool.fetchrow(
        "SELECT id, amount, status, payment_cycle_id, bill_revision FROM payment"
        " WHERE visit_id = $1::uuid AND kind = $2",
        q.visit_id,
        kind,
    )


# ── Acceptance 1 + 3: máy chủ tính, trình duyệt không thay được số ─────────


async def test_thuoc_10_x_5000_la_50000_va_anh_chup_hoa_don(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    hd = await _hd(q, "thuoc")
    assert hd.tong == 50_000 and hd.thu_duoc
    await _thu(q, "thuoc")  # không gửi số — máy chủ tự tính
    p = await _phieu(q, "thuoc")
    assert p is not None and p["amount"] == 50_000
    assert p["bill_revision"] == hd.revision
    dong = await q.pool.fetch(
        "SELECT source_id, quantity, unit_price, line_total FROM payment_bill_line"
        " WHERE payment_cycle_id = $1",
        p["payment_cycle_id"],
    )
    assert [
        (r["source_id"], r["quantity"], r["unit_price"], r["line_total"]) for r in dong
    ] == [(rx, Decimal(10), Decimal(5_000), Decimal(50_000))]


async def test_trinh_duyet_sua_amount_thanh_1_bi_tu_choi(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    with pytest.raises(BillChangedError):
        await _thu(q, "thuoc", amount=1)
    # Số cũ của màn cũ (quên nhân số lượng: 5.000) cũng bị từ chối.
    with pytest.raises(BillChangedError):
        await _thu(q, "thuoc", amount=5_000)
    assert await _phieu(q, "thuoc") is None


async def test_hoa_don_doi_sau_khi_mo_man_thi_bill_changed(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    cu = (await _hd(q, "thuoc")).revision
    await PharmacyService(q.pool).khai_so_luong_mua(
        identity=q.duoc_si, prescription_id=rx, so_luong=4
    )
    with pytest.raises(BillChangedError):
        await _thu(q, "thuoc", bill_revision=cu)
    await _thu(q, "thuoc", bill_revision=(await _hd(q, "thuoc")).revision)
    p = await _phieu(q, "thuoc")
    assert p is not None and p["amount"] == 20_000


# ── Acceptance 4: thiếu giá thì không thu được ─────────────────────────────


async def test_thieu_gia_khong_tao_hoa_don_thu_duoc(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        await _gia_dv(conn, f"KG-{q.duoi}", f"Không giá {q.duoi}", None)
    await _chi_dinh(q, f"KG-{q.duoi}", f"Không giá {q.duoi}")
    hd = await _hd(q, "dich_vu")
    assert not hd.thu_duoc and any("chưa có giá" in v for v in hd.van_de)
    with pytest.raises(ValidationError, match="chưa có giá"):
        await _thu(q, "dich_vu")
    assert await _phieu(q, "dich_vu") is None


# ── Acceptance 5: đối tác tự thu không vào tổng ────────────────────────────


async def test_dich_vu_doi_tac_tu_thu_khong_cong_vao_tong(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        await _gia_dv(conn, f"PK-{q.duoi}", f"Phòng khám làm {q.duoi}", 200_000)
        await _gia_dv(
            conn, f"DT-{q.duoi}", f"Đối tác thu {q.duoi}", 900_000, "EXTERNAL_PARTNER"
        )
    await _chi_dinh(q, f"PK-{q.duoi}", f"Phòng khám làm {q.duoi}")
    await _chi_dinh(q, f"DT-{q.duoi}", f"Đối tác thu {q.duoi}")
    hd = await _hd(q, "dich_vu")
    assert hd.tong == 150_000 + 200_000
    assert {d.ben_thu for d in hd.dong} == {"CLINIC", "EXTERNAL_PARTNER"}
    await _thu(q, "dich_vu")
    p = await _phieu(q, "dich_vu")
    assert p is not None and p["amount"] == 350_000
    # Dòng đối tác vẫn có trong ảnh chụp để biết khách đã làm gì.
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE payment_cycle_id = $1"
            " AND billing_owner = 'EXTERNAL_PARTNER'",
            p["payment_cycle_id"],
        )
        == 1
    )


# ── C1: chưa xác định thuốc kho thì chưa thu ──────────────────────────────


async def test_chua_xac_dinh_thuoc_kho_chua_thu_duoc(q: Quay) -> None:
    await _don(q, 10)
    await _thuoc(q)  # có thuốc trong danh mục nhưng dòng đơn CHƯA gắn — không đoán
    hd = await _hd(q, "thuoc")
    assert not hd.thu_duoc
    assert any("chưa xác định thuốc" in v for v in hd.van_de)
    with pytest.raises(ValidationError, match="chưa xác định thuốc"):
        await _thu(q, "thuoc")


# ── Acceptance 10 (phần hoá đơn) + 11 (phần hoá đơn) ───────────────────────


async def test_mua_4_tren_10_hoa_don_4(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await PharmacyService(q.pool).khai_so_luong_mua(
        identity=q.duoc_si, prescription_id=rx, so_luong=4
    )
    hd = await _hd(q, "thuoc")
    assert hd.tong == 20_000
    with pytest.raises(ValidationError, match="số kê"):
        await PharmacyService(q.pool).khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=11
        )


async def test_tu_choi_toan_bo_khong_co_khoan_thuoc(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).tu_choi(
        identity=q.duoc_si, prescription_id=rx, ly_do="Khách đã có thuốc ở nhà"
    )
    hd = await _hd(q, "thuoc")
    assert hd.dong == [] and hd.tong == 0
    with pytest.raises(ValidationError, match="không có khoản nào"):
        await _thu(q, "thuoc")


# ── Giá mâu thuẫn giữa hai bảng giá (HOLD J5 không bị chọn hộ) ─────────────


async def test_hai_bang_gia_mau_thuan_thi_khong_thu(q: Quay) -> None:
    rx = await _don(q, 2)
    thuoc = await _thuoc(q, gia=5_000)
    await q.pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price) VALUES ($1::uuid, 'thuoc', $2, $3, 6000)",
        CLINIC,
        f"T-{q.duoi}",
        f"Thuốc thử {q.duoi}",
    )
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=thuoc
    )
    hd = await _hd(q, "thuoc")
    assert not hd.thu_duoc and any("mâu thuẫn" in v for v in hd.van_de)


# ── C4: sau khi thu, hoá đơn đã chụp — không sửa dòng thuốc, không sửa ảnh ──


async def test_da_thu_thi_khong_sua_dong_thuoc_va_anh_chup_bat_bien(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _thu(q, "thuoc")
    with pytest.raises(ConflictError, match="đã thu"):
        await PharmacyService(q.pool).khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=3
        )
    khac = await _thuoc(q, ten=f"Thuốc khác {q.duoi}")
    with pytest.raises(ConflictError, match="đã thu"):
        await PharmacyService(q.pool).xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=khac
        )
    with pytest.raises(asyncpg.PostgresError, match="ảnh chụp"):
        await q.pool.execute(
            "UPDATE payment_bill_line SET unit_price = 1 WHERE visit_id = $1::uuid",
            q.visit_id,
        )


async def test_thu_lai_giong_het_khong_ghi_lan_hai(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _thu(q, "thuoc")
    await _thu(q, "thuoc")
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        == 1
    )
