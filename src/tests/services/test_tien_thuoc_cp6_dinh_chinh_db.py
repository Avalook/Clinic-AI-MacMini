"""Đính chính đơn thuốc — nền DB (contract tiền–thuốc CP6 bước 4a, 20/09/2026).

Kiểm các lưới ở Postgres, CHƯA có service đính chính (bước 4b/4c): test tự ghi
đúng các bước service sẽ làm — một dòng `prescription_correction`, dòng thay
thế, rồi gỡ dòng cũ — và kiểm DB nhận / từ chối ra sao.

Luật đã duyệt:
  * dòng hiện hành = removed_at IS NULL; dòng cũ giữ id, tiền/kho cũ bám theo;
  * mức A sửa tại chỗ; B đổi liều tại chỗ được, đổi thuốc/số lượng phải thay;
    C mọi thay đổi chuyên môn phải thay (Q2);
  * dòng lịch sử bất biến, không nhận phân lô / SALE / DISPENSE mới; đối soát
    CP5 (hoàn tiền, huỷ phần chưa giao, khách trả) vẫn chạy (Q3);
  * hồ sơ đã ký: chỉ qua đính chính hồ sơ cùng giao dịch — lưới toàn vẹn,
    không phải ranh giới bảo mật.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _giao,
    _san_sang,
    _thu,
    _xac_minh,
)
from tests.services.test_tien_thuoc_cp5_db import _hoan, _huy_cg, _tra, _xuat

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

LY_DO = "Bác sĩ đính chính đơn"


# ── Các bước service sẽ làm ────────────────────────────────────────────────


async def _lan(
    conn: asyncpg.Connection,
    q: Quay,
    *,
    amendment: str | None = None,
    visit_id: str | None = None,
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO prescription_correction"
            " (clinic_id, visit_id, corrected_by, reason, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid) RETURNING id::text",
            CLINIC,
            visit_id or q.visit_id,
            q.bac_si.staff_id,
            LY_DO,
            amendment,
        )
    )


async def _dong_moi(
    conn: asyncpg.Connection, q: Quay, lan: str | None, ten: str = "Thuốc thay"
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit,"
            " created_in_correction_id)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, $3, '5 viên', 5,"
            " 'viên', $4::uuid FROM visit v WHERE v.visit_id = $5::uuid"
            " RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            ten,
            lan,
            q.visit_id,
        )
    )


async def _go(
    conn: asyncpg.Connection, q: Quay, rx: str, lan: str, thay: str | None
) -> None:
    await conn.execute(
        "UPDATE prescription SET removed_at = now(), removed_by = $2::uuid,"
        " removal_reason = $3, removed_in_correction_id = $4::uuid,"
        " superseded_by_id = $5::uuid WHERE id = $1::uuid",
        rx,
        q.bac_si.staff_id,
        LY_DO,
        lan,
        thay,
    )


async def _thay(q: Quay, rx: str, ten: str = "Thuốc thay") -> str:
    """Một lần đính chính: rx → dòng thay thế mới. Trả id dòng mới."""
    async with q.pool.acquire() as conn, conn.transaction():
        lan = await _lan(conn, q)
        moi = await _dong_moi(conn, q, lan, ten)
        await _go(conn, q, rx, lan, moi)
    return moi


async def _bo(q: Quay, rx: str) -> None:
    async with q.pool.acquire() as conn, conn.transaction():
        await _go(conn, q, rx, await _lan(conn, q), None)


async def _hien_hanh(q: Quay) -> set[str]:
    return {
        r["id"]
        for r in await q.pool.fetch(
            "SELECT id::text FROM prescription WHERE visit_id = $1::uuid"
            " AND removed_at IS NULL",
            q.visit_id,
        )
    }


async def _sua(q: Quay, rx: str, cot: str, gia_tri: Any) -> None:
    await q.pool.execute(
        f"UPDATE prescription SET {cot} = $2 WHERE id = $1::uuid",  # noqa: S608
        rx,
        gia_tri,
    )


async def _ky(q: Quay) -> None:
    await q.pool.execute(
        "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
        " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        q.bac_si.staff_id,
    )


async def _amendment(conn: asyncpg.Connection, q: Quay) -> str:
    """Đúng đường đính chính hồ sơ: AMENDED + visit_amendment, cùng giao dịch."""
    await conn.execute(
        "UPDATE visit SET status = 'AMENDED' WHERE visit_id = $1::uuid", q.visit_id
    )
    return str(
        await conn.fetchval(
            "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, reason,"
            " corrected_fields, original_values, corrected_values)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, ARRAY['don_thuoc'],"
            " '{}'::jsonb, '{}'::jsonb) RETURNING amendment_id::text",
            CLINIC,
            q.visit_id,
            q.bac_si.staff_id,
            LY_DO,
        )
    )


# ══ Supersession: chuỗi, bỏ thuốc, bất biến ══════════════════════════════


async def test_chuoi_a_b_c_truy_nguoc_duoc_va_chi_c_hien_hanh(q: Quay) -> None:
    a = await _don(q, 10, ten="Thuốc A")
    b = await _thay(q, a, "Thuốc B")
    c = await _thay(q, b, "Thuốc C")
    assert await _hien_hanh(q) == {c}
    rows = {
        r["id"]: r
        for r in await q.pool.fetch(
            "SELECT id::text, superseded_by_id::text, removed_in_correction_id::text,"
            " created_in_correction_id::text, drug_name_raw FROM prescription"
            " WHERE visit_id = $1::uuid",
            q.visit_id,
        )
    }
    assert rows[a]["superseded_by_id"] == b and rows[b]["superseded_by_id"] == c
    # Dòng mới sinh trong đúng lần đính chính đã gỡ dòng cũ.
    assert rows[b]["created_in_correction_id"] == rows[a]["removed_in_correction_id"]
    assert rows[c]["created_in_correction_id"] == rows[b]["removed_in_correction_id"]
    assert rows[a]["drug_name_raw"] == "Thuốc A"  # nội dung cũ còn nguyên


async def test_bo_thuoc_khong_thay_the_van_giu_lan_dinh_chinh_va_ly_do(
    q: Quay,
) -> None:
    a = await _don(q, 10)
    await _bo(q, a)
    r = await q.pool.fetchrow(
        "SELECT r.superseded_by_id, c.reason FROM prescription r"
        " JOIN prescription_correction c ON c.id = r.removed_in_correction_id"
        " WHERE r.id = $1::uuid",
        a,
    )
    assert r["superseded_by_id"] is None and r["reason"] == LY_DO
    assert await _hien_hanh(q) == set()


@pytest.mark.parametrize(
    ("cot", "gia_tri"),
    [
        ("dosage_instructions", "Tối 1"),
        ("caution", "Sau ăn"),
        ("purchased_qty", 3),
        ("closed_at", None),  # đổi thành now() dưới đây
        ("removed_at", None),  # "khôi phục" dòng đã gỡ
    ],
)
async def test_dong_lich_su_bat_bien(q: Quay, cot: str, gia_tri: Any) -> None:
    a = await _don(q, 10)
    await _thay(q, a)
    if cot == "closed_at":
        with pytest.raises(asyncpg.CheckViolationError, match="lịch sử"):
            await q.pool.execute(
                "UPDATE prescription SET closed_at = now() WHERE id = $1::uuid", a
            )
        return
    with pytest.raises(asyncpg.PostgresError, match="lịch sử|prescription_go_du"):
        await _sua(q, a, cot, gia_tri)


async def test_go_phai_bang_lan_dinh_chinh_cua_chinh_giao_dich(q: Quay) -> None:
    a = await _don(q, 10)
    async with q.pool.acquire() as conn:
        lan_cu = await _lan(conn, q)  # giao dịch riêng, đã commit
        with pytest.raises(asyncpg.CheckViolationError, match="đang ghi"):
            async with conn.transaction():
                await _go(conn, q, a, lan_cu, None)
        with pytest.raises(asyncpg.CheckViolationError, match="đính chính đang ghi"):
            async with conn.transaction():
                await _dong_moi(conn, q, lan_cu)


async def test_go_khong_kem_sua_noi_dung(q: Quay) -> None:
    a = await _don(q, 10)
    with pytest.raises(asyncpg.CheckViolationError, match="không được kèm sửa"):
        async with q.pool.acquire() as conn, conn.transaction():
            lan = await _lan(conn, q)
            await conn.execute(
                "UPDATE prescription SET removed_at = now(), removed_by = $2::uuid,"
                " removal_reason = $3, removed_in_correction_id = $4::uuid,"
                " dosage_instructions = 'viết lại' WHERE id = $1::uuid",
                a,
                q.bac_si.staff_id,
                LY_DO,
                lan,
            )


async def test_dong_thay_the_khong_ke_thua_viec_nha_thuoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    with pytest.raises(asyncpg.CheckViolationError, match="bắt đầu trống"):
        async with q.pool.acquire() as conn, conn.transaction():
            lan = await _lan(conn, q)
            moi = await _dong_moi(conn, q, lan)
            await conn.execute(
                "UPDATE prescription SET drug_catalog_id = $2::uuid,"
                " drug_mapped_by = $3::uuid, drug_mapped_at = now()"
                " WHERE id = $1::uuid",
                moi,
                drug,
                q.duoc_si.staff_id,
            )
            # Chèn thẳng dòng thay thế mang sẵn thuốc kho → từ chối.
            await conn.execute(
                "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
                " drug_name_raw, quantity, created_in_correction_id, drug_catalog_id,"
                " drug_mapped_by, drug_mapped_at)"
                " VALUES ($1::uuid, $2, $3::uuid, 'x', '1 viên', $4::uuid, $5::uuid,"
                " $6::uuid, now())",
                CLINIC,
                f"test-rx-{uuid.uuid4().hex}",
                q.visit_id,
                lan,
                drug,
                q.duoc_si.staff_id,
            )
    assert rx in await _hien_hanh(q)


async def test_dong_thay_phai_hien_hanh_va_sinh_cung_lan(q: Quay) -> None:
    a = await _don(q, 10, ten="A")
    khac = await _don(q, 3, ten="Dòng có sẵn")
    with pytest.raises(asyncpg.CheckViolationError, match="cùng lần đính chính"):
        async with q.pool.acquire() as conn, conn.transaction():
            await _go(conn, q, a, await _lan(conn, q), khac)


async def test_khong_tao_vong_thay_the(q: Quay) -> None:
    a = await _don(q, 10, ten="A")
    b = await _thay(q, a, "B")
    # B thay ngược bằng A (đã gỡ) → từ chối: dòng thay phải đang hiện hành.
    with pytest.raises(asyncpg.CheckViolationError, match="hiện hành"):
        async with q.pool.acquire() as conn, conn.transaction():
            await _go(conn, q, b, await _lan(conn, q), a)


async def test_mot_dong_moi_chi_thay_mot_dong_cu(q: Quay) -> None:
    a1 = await _don(q, 10, ten="A1")
    a2 = await _don(q, 10, ten="A2")
    with pytest.raises(asyncpg.UniqueViolationError):
        async with q.pool.acquire() as conn, conn.transaction():
            lan = await _lan(conn, q)
            moi = await _dong_moi(conn, q, lan)
            await _go(conn, q, a1, lan, moi)
            await _go(conn, q, a2, lan, moi)


async def test_khong_dinh_chinh_cheo_luot(q: Quay) -> None:
    a = await _don(q, 10)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with q.pool.acquire() as conn, conn.transaction():
            luot2 = await conn.fetchval(
                "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
                " checked_in_at)"
                " SELECT clinic_id, clinic_patient_id, 'IN_PROGRESS', now()"
                " FROM visit WHERE visit_id = $1::uuid RETURNING visit_id::text",
                q.visit_id,
            )
            lan2 = await _lan(conn, q, visit_id=luot2)
            await _go(conn, q, a, lan2, None)


async def test_lan_dinh_chinh_chi_ghi_them(q: Quay) -> None:
    async with q.pool.acquire() as conn:
        lan = await _lan(conn, q)
        for cau in (
            "UPDATE prescription_correction SET reason = 'sửa lại lý do'"
            " WHERE id = $1::uuid",
            "DELETE FROM prescription_correction WHERE id = $1::uuid",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(cau, lan)


# ══ Mức dấu vết A / B / C ════════════════════════════════════════════════


async def test_a_dong_sach_sua_tai_cho_va_xoa_cung_duoc(q: Quay) -> None:
    a = await _don(q, 10)
    await _sua(q, a, "drug_name_raw", "Đổi thuốc")
    await _sua(q, a, "dosage_instructions", "Sáng 1")
    await q.pool.execute("DELETE FROM prescription WHERE id = $1::uuid", a)
    assert await _hien_hanh(q) == set()


async def test_b_phan_lo_chua_thu_doi_lieu_tai_cho_giu_phan_lo(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _sua(q, rx, "dosage_instructions", "Sáng 1 viên")
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM prescription_allocation"
            " WHERE prescription_id = $1::uuid AND released_at IS NULL",
            rx,
        )
        == 1
    )


async def test_b_doi_thuoc_so_luong_tai_cho_bi_chan(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    for cot, v in (("drug_name_raw", "Thuốc khác"), ("quantity", "5 viên")):
        with pytest.raises(asyncpg.CheckViolationError, match="dòng thay thế"):
            await _sua(q, rx, cot, v)


async def test_b_phan_lo_da_nha_van_la_dau_vet_khong_xoa_duoc(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await PharmacyService(q.pool).bo_phan_lo(
        identity=q.duoc_si,
        allocation_id=await q.pool.fetchval(
            "SELECT id::text FROM prescription_allocation"
            " WHERE prescription_id = $1::uuid",
            rx,
        ),
        ly_do="Dược sĩ chọn lại lô",
    )
    with pytest.raises(asyncpg.CheckViolationError, match="dấu vết"):
        await q.pool.execute("DELETE FROM prescription WHERE id = $1::uuid", rx)


async def test_b_go_khi_con_phan_lo_chua_thu_phai_nha_truoc(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    with pytest.raises(asyncpg.CheckViolationError, match="nhả trước"):
        await _thay(q, rx)
    # Nhả với lý do "Bác sĩ đính chính đơn" rồi gỡ: lịch sử phân lô còn.
    async with q.pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "UPDATE prescription_allocation SET released_at = now(),"
            " released_by = $2::uuid, release_reason = $3"
            " WHERE prescription_id = $1::uuid AND released_at IS NULL",
            rx,
            q.bac_si.staff_id,
            LY_DO,
        )
        lan = await _lan(conn, q)
        moi = await _dong_moi(conn, q, lan)
        await _go(conn, q, rx, lan, moi)
    assert await _hien_hanh(q) == {moi}
    assert (
        await q.pool.fetchval(
            "SELECT release_reason FROM prescription_allocation"
            " WHERE prescription_id = $1::uuid",
            rx,
        )
        == LY_DO
    )


async def test_c_da_thu_doi_lieu_hay_luu_y_tai_cho_bi_chan(q: Quay) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    await _thu(q)
    for cot in ("dosage_instructions", "caution"):
        with pytest.raises(asyncpg.CheckViolationError, match="dòng thay thế"):
            await _sua(q, rx, cot, "viết lại")


async def test_c_da_thu_van_ghi_dinh_chinh_duoc_tien_kho_cu_giu_nguyen(
    q: Quay,
) -> None:
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    moi = await _thay(q, rx)
    assert await _hien_hanh(q) == {moi}
    # Không cần huỷ phiếu / hoàn tiền trước; phiếu, SALE, phân lô cũ nguyên vẹn.
    kq = await q.pool.fetchrow(
        "SELECT (SELECT status FROM payment_cycle"
        "         WHERE payment_cycle_id = $2::uuid) AS tt,"
        " (SELECT count(*) FROM inventory_txn t JOIN prescription_allocation a"
        "   ON a.id = t.allocation_id WHERE a.prescription_id = $1::uuid"
        "   AND t.txn_type = 'SALE') AS ban,"
        " (SELECT count(*) FROM payment_bill_line WHERE source_id = $1::text) AS anh",
        rx,
        lan,
    )
    assert (kq["tt"], kq["ban"], kq["anh"]) == ("PAID", 1, 1)


# ══ Q3: dòng lịch sử không nhận tác động thương mại mới ═════════════════


async def test_dong_lich_su_khong_nhan_phan_lo_moi(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    await _thay(q, rx)
    with pytest.raises(Exception, match="đính chính"):
        await _chon(q, rx, lo, 10)


async def test_dong_lich_su_da_thu_khong_giao_them(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _thay(q, rx)
    with pytest.raises(Exception, match="đính chính"):
        await _giao(q, rx, lo, 1)


async def test_dong_lich_su_khong_ghi_sale_moi(q: Quay) -> None:
    """Lần thu đang chờ, bác sĩ đính chính: SALE lên dòng lịch sử bị DB chặn.

    Hôm nay (4a) đường xác minh của service vẫn cố ghi SALE nên bị chặn cả giao
    dịch — lần thu đứng yên ở PENDING, không bán lén. Bước 4b đổi service thành:
    xác minh tiền thật → PAID + CHUA_GHI_BAN, KHÔNG ghi SALE (Q3)."""
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q, "TRANSFER"))["payment_cycle_id"]
    await _thay(q, rx)
    with pytest.raises(asyncpg.CheckViolationError, match="không ghi bán"):
        await _xac_minh(q, lan)
    assert (
        await q.pool.fetchval(
            "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid", lan
        )
        == "PENDING_VERIFICATION"
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE txn_type = 'SALE'"
            " AND payment_cycle_id = $1::uuid",
            lan,
        )
        == 0
    )


async def test_doi_soat_cp5_van_chay_tren_dong_lich_su(q: Quay) -> None:
    """Giao 3/10 → đính chính → hoàn 7 → huỷ phần chưa giao → khách trả 1."""
    rx, _, _ = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    lo = await q.pool.fetchval(
        "SELECT drug_batch_id::text FROM prescription_allocation"
        " WHERE prescription_id = $1::uuid",
        rx,
    )
    await _giao(q, rx, lo, 3)
    await _thay(q, rx)
    await _hoan(q, lan, 7)
    await _huy_cg(q, rx)
    await _tra(q, await _xuat(q, rx), 1)
    so = await q.pool.fetchrow(
        "SELECT"
        " (SELECT count(*) FROM inventory_txn t JOIN prescription_allocation a"
        "   ON a.id = t.allocation_id WHERE a.prescription_id = $1::uuid"
        "   AND t.txn_type = 'SALE_REVERSAL') AS dao,"
        " (SELECT count(*) FROM drug_return WHERE prescription_id = $1::uuid) AS tra",
        rx,
    )
    assert (so["dao"], so["tra"]) == (1, 1)


# ══ D: hồ sơ đã ký ═══════════════════════════════════════════════════════


async def test_da_ky_moi_thay_doi_chuyen_mon_ngoai_dinh_chinh_bi_chan(q: Quay) -> None:
    a = await _don(q, 10)
    await _ky(q)
    with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
        await _sua(q, a, "dosage_instructions", "Tối 1")
    with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
        await q.pool.execute("DELETE FROM prescription WHERE id = $1::uuid", a)
    with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
        await _don(q, 3, ten="Thêm sau ký")
    with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
        await _thay(q, a)


async def test_da_ky_nha_thuoc_van_van_hanh_duoc(q: Quay) -> None:
    rx = await _don(q, 10)
    await _ky(q)
    drug = await q.pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
        " VALUES ($1::uuid, $2, $2, 5000) RETURNING id::text",
        CLINIC,
        f"Thuốc sau ký {q.duoi}",
    )
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )


async def test_da_ky_dinh_chinh_qua_amendment_cung_giao_dich(q: Quay) -> None:
    a = await _don(q, 10, ten="A")
    await _ky(q)
    async with q.pool.acquire() as conn, conn.transaction():
        am = await _amendment(conn, q)
        await conn.execute("SELECT set_config('clinicai.amendment_id', $1, true)", am)
        lan = await _lan(conn, q, amendment=am)
        moi = await _dong_moi(conn, q, lan, "B")
        await _go(conn, q, a, lan, moi)
    assert await _hien_hanh(q) == {moi}
    assert (
        await q.pool.fetchval(
            "SELECT c.amendment_id::text FROM prescription r"
            " JOIN prescription_correction c ON c.id = r.removed_in_correction_id"
            " WHERE r.id = $1::uuid",
            a,
        )
        == am
    )


@pytest.mark.parametrize("sai", ["khong_dat", "rac", "amendment_cu"])
async def test_da_ky_dau_hieu_amendment_sai_bi_chan(q: Quay, sai: str) -> None:
    a = await _don(q, 10)
    await _ky(q)
    cu = None
    if sai == "amendment_cu":
        async with q.pool.acquire() as conn, conn.transaction():
            cu = await _amendment(conn, q)  # đã commit ở giao dịch trước
    with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
        async with q.pool.acquire() as conn, conn.transaction():
            am = await _amendment(conn, q)
            if sai == "rac":
                await conn.execute(
                    "SELECT set_config('clinicai.amendment_id', 'xyz', true)"
                )
            elif sai == "amendment_cu":
                await conn.execute(
                    "SELECT set_config('clinicai.amendment_id', $1, true)", cu
                )
            lan = await _lan(conn, q, amendment=am)
            await _go(conn, q, a, lan, None)


async def test_da_ky_khong_tai_dung_amendment_cua_giao_dich_truoc(q: Quay) -> None:
    """Dùng lại TRỌN một đính chính hồ sơ đã commit (biến phiên + lần đính chính
    cùng trỏ về nó) → chặn: đính chính đơn phải thuộc đính chính hồ sơ ghi trong
    CHÍNH giao dịch này."""
    a = await _don(q, 10)
    await _ky(q)
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            cu = await _amendment(conn, q)
        with pytest.raises(asyncpg.CheckViolationError, match="đính chính hồ sơ"):
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('clinicai.amendment_id', $1, true)", cu
                )
                lan = await _lan(conn, q, amendment=cu)
                await _go(conn, q, a, lan, None)


async def test_chua_ky_khong_gan_amendment(q: Quay) -> None:
    await _don(q, 10)
    async with q.pool.acquire() as conn:
        am = await conn.fetchval(
            "INSERT INTO visit_amendment (clinic_id, visit_id, amended_by, reason,"
            " corrected_fields, original_values, corrected_values)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'x', ARRAY['don_thuoc'],"
            " '{}', '{}') RETURNING amendment_id::text",
            CLINIC,
            q.visit_id,
            q.bac_si.staff_id,
        )
        with pytest.raises(asyncpg.CheckViolationError, match="chưa ký"):
            await _lan(conn, q, amendment=am)


# ══ Tranh chấp: bác sĩ gỡ dòng ↔ dược sĩ chọn lô ═══════════════════════


async def _chen_phan_lo(
    conn: asyncpg.Connection, q: Quay, rx: str, drug: str, lo: str
) -> None:
    await conn.execute(
        "INSERT INTO prescription_allocation (clinic_id, visit_id, prescription_id,"
        " drug_catalog_id, drug_batch_id, quantity, created_by)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, 10, $6::uuid)",
        CLINIC,
        q.visit_id,
        rx,
        drug,
        lo,
        q.duoc_si.staff_id,
    )


async def test_tranh_chap_bac_si_go_truoc_duoc_si_cho_roi_bi_tu_choi(q: Quay) -> None:
    """Lưới cuối ở DB — kể cả đường ghi thẳng không khoá lượt trước."""
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    bs = await q.pool.acquire()
    ds = await q.pool.acquire()
    try:
        tr = bs.transaction()
        await tr.start()
        lan = await _lan(bs, q)
        moi = await _dong_moi(bs, q, lan)
        await _go(bs, q, rx, lan, moi)  # chưa commit

        async def duoc_si() -> None:
            async with ds.transaction():
                await _chen_phan_lo(ds, q, rx, drug, lo)

        viec = asyncio.create_task(duoc_si())
        await asyncio.sleep(0.3)
        assert not viec.done()  # đang chờ khoá FOR SHARE
        await tr.commit()
        with pytest.raises(asyncpg.CheckViolationError, match="đính chính"):
            await viec
    finally:
        await q.pool.release(bs)
        await q.pool.release(ds)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM prescription_allocation"
            " WHERE prescription_id = $1::uuid",
            rx,
        )
        == 0
    )


async def test_tranh_chap_duoc_si_chon_lo_truoc_bac_si_phai_nha(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    bs = await q.pool.acquire()
    ds = await q.pool.acquire()
    try:
        tr = ds.transaction()
        await tr.start()
        await _chen_phan_lo(ds, q, rx, drug, lo)  # chưa commit

        async def bac_si() -> None:
            async with bs.transaction():
                lan = await _lan(bs, q)
                moi = await _dong_moi(bs, q, lan)
                await _go(bs, q, rx, lan, moi)

        viec = asyncio.create_task(bac_si())
        await asyncio.sleep(0.3)
        assert not viec.done()
        await tr.commit()
        with pytest.raises(asyncpg.CheckViolationError, match="nhả trước"):
            await viec
    finally:
        await q.pool.release(bs)
        await q.pool.release(ds)
    assert rx in await _hien_hanh(q)  # không mất gì: dòng + phân lô còn nguyên
