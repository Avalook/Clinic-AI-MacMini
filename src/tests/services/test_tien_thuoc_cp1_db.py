"""Contract tiền–thuốc CP1: hoá đơn do máy chủ tính, định danh thuốc kho, số
lượng mua, bên thu tiền, ảnh chụp hoá đơn (19/09/2026).

Mỗi test dựng một lượt riêng với MÃ DỊCH VỤ, LOẠI KHÁM và THUỐC mang đuôi ngẫu
nhiên — không đụng bảng giá / danh mục mà các test khác dùng.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import (
    BillChangedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
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
    return await tao_quay(pool)


async def tao_quay(pool: asyncpg.Pool) -> Quay:
    """Một lượt đã khám xong, kèm thu ngân / dược sĩ / bác sĩ riêng."""
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
            "INSERT INTO service_type (clinic_id, code, name, gia_mac_dinh)"
            " VALUES ($1::uuid, $2, $3, 150000) RETURNING id::text",
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
    # Lifecycle v1 Slice 3: chỉ chỉ định khách đã CHỌN mới vào hoá đơn — các
    # test tiền ở đây kiểm cách tính tiền của dịch vụ khách đã chọn làm.
    return str(
        await q.pool.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'DICHVU-SIEUAM',"
            " 'authorized', $6::uuid, $6::uuid, now(), 'SELECTED')"
            " RETURNING id::text",
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


async def _nhap_lo(q: Quay, drug: str, so: int = 100, **kw) -> str:  # type: ignore[no-untyped-def]
    kq = await PharmacyService(q.pool).nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=f"LO-{uuid.uuid4().hex[:10]}",
        expiry_date=kw.get("han", date(2099, 12, 31)),
        unit=kw.get("don_vi", "viên"),
    )
    return str(kq["drug_batch_id"])


async def _du_lo(q: Quay) -> None:
    """CP3: thu tiền thuốc đòi đủ lô. Chọn lô MỚI (100 viên) cho mọi dòng đã
    xác định thuốc mà còn thiếu lô — để test CP1/CP2 vẫn chỉ đo đúng điều của
    chúng."""
    for r in await q.pool.fetch(
        "SELECT r.id::text, r.drug_catalog_id::text,"
        " coalesce(r.purchased_qty, r.quantity_num) - r.dispensed_qty"
        " - coalesce((SELECT sum(a.quantity) FROM prescription_allocation a"
        "   WHERE a.prescription_id = r.id AND a.released_at IS NULL), 0) AS thieu"
        " FROM prescription r WHERE r.visit_id = $1::uuid"
        " AND r.drug_catalog_id IS NOT NULL AND r.closed_at IS NULL",
        q.visit_id,
    ):
        if r["thieu"] is not None and r["thieu"] > 0:
            await PharmacyService(q.pool).phan_lo(
                identity=q.duoc_si,
                prescription_id=r["id"],
                drug_batch_id=await _nhap_lo(q, r["drug_catalog_id"]),
                so_luong=r["thieu"],
            )


async def _thu(q: Quay, kind: str, **kw) -> None:  # type: ignore[no-untyped-def]
    if kind == "thuoc" and kw.get("du_lo", True):
        await _du_lo(q)
    await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind=kind,
        idempotency_key=kw.get("key") or f"test-{uuid.uuid4().hex}",
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
    # Đổi vì Lifecycle v1 Slice 3 (Outstanding Bill): dòng đối tác tự thu không
    # phải khoản phòng khám thu → không vào hoá đơn, không vào ảnh chụp (trước:
    # hiện ra nhưng không cộng). 27/09/2026: dòng ấy tách sang `dong_doi_tac`
    # (quầy hiện "khách trả trực tiếp đối tác — không cộng").
    assert {d.ben_thu for d in hd.dong} == {"CLINIC"}
    assert [d.ben_thu for d in hd.dong_doi_tac] == ["EXTERNAL_PARTNER"]
    await _thu(q, "dich_vu")
    p = await _phieu(q, "dich_vu")
    assert p is not None and p["amount"] == 350_000
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE payment_cycle_id = $1"
            " AND billing_owner = 'EXTERNAL_PARTNER'",
            p["payment_cycle_id"],
        )
        == 0
    )


# ── C1: chưa xác định thuốc kho thì chưa thu ──────────────────────────────


async def test_chua_xac_dinh_thuoc_kho_chua_thu_duoc(q: Quay) -> None:
    await _don(q, 10)
    await _thuoc(q)  # có thuốc trong danh mục nhưng dòng đơn CHƯA gắn — không đoán
    hd = await _hd(q, "thuoc")
    assert not hd.thu_duoc
    assert any("thuốc chưa có trong danh mục giá" in v for v in hd.van_de)
    with pytest.raises(ValidationError, match="thuốc chưa có trong danh mục giá"):
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
    rev = (await _hd(q, "thuoc")).revision
    await _thu(q, "thuoc", bill_revision=rev)
    await _thu(q, "thuoc", bill_revision=rev)
    # Gửi lại KHÔNG kèm dấu hoá đơn thì không chứng minh được là cùng hoá đơn.
    with pytest.raises(ConflictError, match="hoá đơn khác"):
        await _thu(q, "thuoc")
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        == 1
    )


# ── Review CP1 #1: chưa biết số kê thì không có số mua ────────────────────


async def test_chua_biet_so_ke_thi_khong_khai_so_mua(q: Quay) -> None:
    rx = await _don(q, 10)
    await q.pool.execute(
        "UPDATE prescription SET quantity_num = NULL WHERE id = $1::uuid", rx
    )
    with pytest.raises(ValidationError, match="Chưa xác định số lượng bác sĩ kê"):
        await PharmacyService(q.pool).khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=100
        )
    # DB cũng chặn — không ai lách được bằng một đường ghi khác.
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE prescription SET purchased_qty = 100 WHERE id = $1::uuid", rx
        )


# ── Review CP1 #2: revision gắn định danh thuốc kho ────────────────────────


async def test_doi_thuoc_a_sang_b_cung_gia_thi_revision_doi(q: Quay) -> None:
    rx = await _don(q, 10)
    a = await _thuoc(q, gia=5_000, ten=f"Thuốc A {q.duoi}")
    b = await _thuoc(q, gia=5_000, ten=f"Thuốc B {q.duoi}")
    ph = PharmacyService(q.pool)
    await ph.xac_dinh_thuoc(identity=q.duoc_si, prescription_id=rx, drug_catalog_id=a)
    rev_a = (await _hd(q, "thuoc")).revision
    await ph.xac_dinh_thuoc(identity=q.duoc_si, prescription_id=rx, drug_catalog_id=b)
    hd_b = await _hd(q, "thuoc")
    assert hd_b.tong == 50_000 and hd_b.revision != rev_a
    with pytest.raises(BillChangedError):
        await _thu(q, "thuoc", bill_revision=rev_a)


# ── Review CP1 #4: đã thu — thu lại vs hoá đơn khác cùng tổng ──────────────


async def _thu_kham(q: Quay) -> str:
    rev: str = (await _hd(q, "dich_vu")).revision
    await _thu(q, "dich_vu", bill_revision=rev)
    return rev


async def test_da_thu_a_gia_doi_roi_gui_lai_a_van_thanh_cong(q: Quay) -> None:
    # Đổi vì Lifecycle v1 Slice 3: "gửi lại vì mất phản hồi" nay nhận ra bằng
    # CÙNG Idempotency-Key (biên nhận trong giao dịch), không bằng so hình chiếu
    # `payment`. Cùng khoá + cùng nội dung → trả đúng lần thu cũ.
    khoa = f"test-{uuid.uuid4().hex}"
    rev_a = (await _hd(q, "dich_vu")).revision
    await _thu(q, "dich_vu", bill_revision=rev_a, key=khoa)
    p0 = await _phieu(q, "dich_vu")
    await q.pool.execute(
        "UPDATE service_price SET unit_price = 180000 WHERE service_code = $1",
        f"KHAM-{q.duoi}",
    )
    assert (await _hd(q, "dich_vu")).revision != rev_a  # hoá đơn hiện tại đã khác
    await _thu(q, "dich_vu", bill_revision=rev_a, key=khoa)  # mạng rớt, gửi lại
    p1 = await _phieu(q, "dich_vu")
    assert p0 is not None and p1 is not None
    assert (p1["payment_cycle_id"], p1["amount"]) == (p0["payment_cycle_id"], 150_000)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        == 1
    )


async def test_da_thu_a_hoa_don_b_cung_tong_khong_duoc_coi_la_da_tra(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        await _gia_dv(conn, f"X-{q.duoi}", f"Dịch vụ X {q.duoi}", 100_000)
        await _gia_dv(conn, f"Y-{q.duoi}", f"Dịch vụ Y {q.duoi}", 100_000)
    o = await _chi_dinh(q, f"X-{q.duoi}", f"Dịch vụ X {q.duoi}")
    await _thu_kham(q)
    # Nội dung đổi (X → Y), tổng vẫn 250.000.
    await q.pool.execute(
        "UPDATE service_order SET service_code = $2, service_name = $3"
        " WHERE id = $1::uuid",
        o,
        f"Y-{q.duoi}",
        f"Dịch vụ Y {q.duoi}",
    )
    # Đổi vì Lifecycle v1 Slice 3: chỉ định (cùng id) đã được lần thu A phủ —
    # hoá đơn còn nợ không có nó nữa, nên không có "hoá đơn B" nào để thu và
    # không thể coi B là đã trả bằng tiền của A: lần thu mới bị từ chối.
    hd_b = await _hd(q, "dich_vu")
    assert hd_b.dong == []
    with pytest.raises(ValidationError, match="không còn khoản"):
        await _thu(q, "dich_vu", bill_revision=hd_b.revision, amount=250_000)


# ── Review CP1 #3: đổi dòng thuốc và lần thu không commit hai sự thật ──────


async def _giu_khoa_luot_roi_thu(q: Quay, lenh) -> None:  # type: ignore[no-untyped-def]
    """Một giao dịch THU đang giữ khoá lượt (đúng như PaymentService) thì lệnh
    đổi dòng thuốc phải CHỜ; thu xong commit thì lệnh ấy thấy 'đã thu' và dừng."""
    import asyncio

    async with q.pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        await conn.execute(
            "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE", q.visit_id
        )
        viec = asyncio.ensure_future(lenh())
        await asyncio.sleep(0.4)
        assert not viec.done(), "lệnh đổi dòng thuốc không chờ khoá lượt"
        await conn.execute(
            "INSERT INTO payment (clinic_id, visit_id, clinic_patient_id, kind,"
            " status, amount, paid_by_staff_id, paid_at)"
            " SELECT clinic_id, visit_id, clinic_patient_id, 'thuoc', 'PAID', 50000,"
            " $2::uuid, now() FROM visit WHERE visit_id = $1::uuid",
            q.visit_id,
            q.thu_ngan.staff_id,
        )
        await tr.commit()
    with pytest.raises(ConflictError, match="đã thu"):
        await viec


async def test_doi_thuoc_cho_lan_thu_dang_chay(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    b = await _thuoc(q, ten=f"Thuốc B {q.duoi}")
    await _giu_khoa_luot_roi_thu(
        q,
        lambda: PharmacyService(q.pool).xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=b
        ),
    )


async def test_doi_so_mua_cho_lan_thu_dang_chay(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _giu_khoa_luot_roi_thu(
        q,
        lambda: PharmacyService(q.pool).khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=4
        ),
    )


async def test_tu_choi_cho_lan_thu_dang_chay(q: Quay) -> None:
    rx = await _don(q, 10)
    await _giu_khoa_luot_roi_thu(
        q,
        lambda: PharmacyService(q.pool).tu_choi(
            identity=q.duoc_si, prescription_id=rx, ly_do="Khách đổi ý"
        ),
    )


async def test_thu_va_doi_thuoc_dong_thoi_khong_ra_hai_su_that(q: Quay) -> None:
    """Bắn thật đồng thời nhiều lần: nếu lần thu thành công thì ảnh chụp và
    dòng đơn PHẢI cùng một thuốc."""
    import asyncio

    for i in range(8):
        rx = await _don(q, 2, ten=f"rx{i}")
        a = await _thuoc(q, ten=f"A{i} {q.duoi}")
        b = await _thuoc(q, ten=f"B{i} {q.duoi}")
        ph = PharmacyService(q.pool)
        await ph.xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=a
        )
        # CP3: lô chọn TRƯỚC khi thu (không phải trong lúc đua) — thu tiền thuốc
        # đòi đủ lô. Đổi thuốc khi đã có lô thì bị từ chối; bất biến cần đo
        # vẫn là ảnh chụp và dòng đơn cùng một thuốc.
        await _du_lo(q)
        await asyncio.gather(
            _thu(q, "thuoc", du_lo=False),
            ph.xac_dinh_thuoc(
                identity=q.duoc_si, prescription_id=rx, drug_catalog_id=b
            ),
            return_exceptions=True,
        )
        p = await _phieu(q, "thuoc")
        if p is not None:
            chup = await q.pool.fetch(
                "SELECT source_id, drug_catalog_id::text FROM payment_bill_line"
                " WHERE payment_cycle_id = $1",
                p["payment_cycle_id"],
            )
            hien = {
                r["id"]: r["drug_catalog_id"]
                for r in await q.pool.fetch(
                    "SELECT id::text, drug_catalog_id::text FROM prescription"
                    " WHERE visit_id = $1::uuid",
                    q.visit_id,
                )
            }
            for r in chup:
                assert hien[r["source_id"]] == r["drug_catalog_id"]
            return
    pytest.fail("không lần thu nào thành công — kịch bản không đo được gì")


# ── Review CP1 #5: chưa biết giá là NULL, không phải 0đ ────────────────────


async def test_dich_vu_doi_tac_chua_biet_gia_chup_la_null(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        await _gia_dv(
            conn, f"DN-{q.duoi}", f"Đối tác chưa giá {q.duoi}", None, "EXTERNAL_PARTNER"
        )
    await _chi_dinh(q, f"DN-{q.duoi}", f"Đối tác chưa giá {q.duoi}")
    await _thu_kham(q)
    r = await q.pool.fetchrow(
        "SELECT unit_price, line_total FROM payment_bill_line WHERE visit_id = $1::uuid"
        " AND billing_owner = 'EXTERNAL_PARTNER'",
        q.visit_id,
    )
    # Đổi vì Lifecycle v1 Slice 3: dòng đối tác không vào ảnh chụp lần thu của
    # phòng khám (trước: chụp với giá NULL).
    assert r is None
    # Dòng phòng khám thu thì DB không nhận thiếu giá.
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_id, payment_cycle_id,"
            " visit_id, kind, source_type, source_id, name_snapshot, quantity,"
            " billing_owner) SELECT clinic_id, payment_id, payment_cycle_id,"
            " visit_id, kind, 'exam', 'x-' || gen_random_uuid()::text, 'x', 1,"
            " 'CLINIC' FROM payment_bill_line"
            " WHERE visit_id = $1::uuid LIMIT 1",
            q.visit_id,
        )


# ── Review CP1 #6: quyền thật, không chỉ đếm policy ───────────────────────


async def test_quyen_that_tren_payment_bill_line(q: Quay) -> None:
    await _thu_kham(q)
    uid = str(uuid.uuid4())
    await q.pool.execute("INSERT INTO auth.users (id) VALUES ($1::uuid)", uid)
    await q.pool.execute(
        "UPDATE staff SET auth_user_id = $2::uuid WHERE id = $1::uuid",
        q.thu_ngan.staff_id,
        uid,
    )
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            await conn.execute(
                "SELECT set_config('request.jwt.claim.sub', $1, true)", uid
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM payment_bill_line WHERE visit_id = $1::uuid",
                    q.visit_id,
                )
                >= 1
            )
            # Người không thuộc phòng khám nào: RLS lọc sạch.
            await conn.execute(
                "SELECT set_config('request.jwt.claim.sub', $1, true)",
                str(uuid.uuid4()),
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM payment_bill_line WHERE visit_id = $1::uuid",
                    q.visit_id,
                )
                == 0
            )
    async with q.pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE authenticated")
                await conn.execute(
                    "INSERT INTO payment_bill_line (clinic_id, payment_id,"
                    " payment_cycle_id, visit_id, kind, source_type, source_id,"
                    " name_snapshot, quantity, unit_price, line_total,"
                    " billing_owner) SELECT clinic_id, payment_id, payment_cycle_id,"
                    " visit_id, kind, 'exam', 'x-' || gen_random_uuid()::text,"
                    " 'x', 1, 0, 0, 'CLINIC'"
                    " FROM payment_bill_line LIMIT 1"
                )
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE service_role")
            await conn.execute(
                "INSERT INTO payment_bill_line (clinic_id, payment_id,"
                " payment_cycle_id, visit_id, kind, source_type, source_id,"
                " name_snapshot, quantity, unit_price, line_total, billing_owner)"
                " SELECT clinic_id, payment_id, payment_cycle_id, visit_id, kind,"
                " 'exam', 'x-' || gen_random_uuid()::text, 'x', 1, 0, 0, 'CLINIC'"
                " FROM payment_bill_line"
                " WHERE visit_id = $1::uuid LIMIT 1",
                q.visit_id,
            )
            await conn.execute("SELECT 1 FROM payment_bill_line LIMIT 1")


# ── Review CP1 lần 2: thuốc kho phải CÙNG phòng khám — ép ở DB ─────────────


async def test_dong_don_phong_kham_a_khong_tro_thuoc_phong_kham_b(q: Quay) -> None:
    rx = await _don(q, 10)
    clinic_b = await q.pool.fetchval(
        "INSERT INTO clinic (code, name) VALUES ($1, 'Phòng khám B thử')"
        " RETURNING id::text",
        f"PK-B-{q.duoi}",
    )
    thuoc_b = await q.pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
        " VALUES ($1::uuid, 'Thuốc của B', 'Thuốc của B', 5000) RETURNING id::text",
        clinic_b,
    )
    # Ghi thẳng SQL — đúng loại đường ghi không đi qua service (service_role
    # bỏ qua RLS). Khoá ngoại ghép (drug_catalog_id, clinic_id) phải chặn.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await q.pool.execute(
            "UPDATE prescription SET drug_catalog_id = $2::uuid,"
            " drug_mapped_by = $3::uuid, drug_mapped_at = now()"
            " WHERE id = $1::uuid",
            rx,
            thuoc_b,
            q.duoc_si.staff_id,
        )
    # Đường service cũng từ chối (không thấy thuốc trong danh mục của mình).
    with pytest.raises(NotFoundError):
        await PharmacyService(q.pool).xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=thuoc_b
        )
