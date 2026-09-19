"""Contract tiền–thuốc CP6 bước 2 (20/09/2026): migration nền.

* khoá ngoại GHÉP cùng phòng khám: payment_cycle → payment,
  payment_bill_line → payment_cycle;
* `doi_soat_ly_do`: mã nguyên nhân cần đối soát (HOA_DON_DOI / CHUA_GHI_BAN),
  bất biến `can_doi_soat = có mã`, chỉ hình thành lúc chờ → đã thu;
* dựng lại mã cho dữ liệu CP2–CP5 CHỈ từ sự kiện; không dựng được thì dừng.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import json
import uuid

import asyncpg
import pytest

from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _san_sang, _thu, _xac_minh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lan(q: Quay, cycle: str) -> asyncpg.Record:
    r = await q.pool.fetchrow(
        "SELECT status, can_doi_soat, doi_soat_ly_do FROM payment_cycle"
        " WHERE payment_cycle_id = $1::uuid",
        cycle,
    )
    assert r is not None
    return r


# ── Khoá ngoại ghép cùng phòng khám ──────────────────────────────────────


async def _phong_kham_khac(conn: asyncpg.Connection, duoi: str) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"K{duoi}",
        )
    )


async def test_dong_hoa_don_khac_phong_kham_lan_thu_bi_chan(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = (await _thu(q))["payment_cycle_id"]
    khac = await _phong_kham_khac(q.pool, q.duoi)
    with pytest.raises(asyncpg.ForeignKeyViolationError, match="same_clinic"):
        await q.pool.execute(
            "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
            " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
            " line_total, billing_owner)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'thuoc', 'prescription', 'x',"
            " 'lệch', 1, 1, 1, 'CLINIC')",
            khac,
            lan,
            q.visit_id,
        )


async def test_lan_thu_tro_payment_khac_phong_kham_bi_chan(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    cho = (await _thu(q, "QR"))["payment_cycle_id"]  # chờ → payment_id rỗng
    async with q.pool.acquire() as conn:
        khac = await _phong_kham_khac(conn, q.duoi)
        loc = await conn.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name)"
            " VALUES ($1::uuid, 'K1', 'Cơ sở khác') RETURNING id::text",
            khac,
        )
        bn = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN khác', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            khac,
            f"K-{q.duoi}",
            loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', now()) RETURNING visit_id::text",
            khac,
            bn,
        )
        pm = await conn.fetchval(
            "INSERT INTO payment (clinic_id, visit_id, clinic_patient_id, kind,"
            " status, amount, paid_at) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'thuoc', 'PAID', 1000, now()) RETURNING id::text",
            khac,
            vid,
            bn,
        )
        with pytest.raises(asyncpg.ForeignKeyViolationError, match="same_clinic"):
            await conn.execute(
                "UPDATE payment_cycle SET payment_id = $2::uuid"
                " WHERE payment_cycle_id = $1::uuid",
                cho,
                pm,
            )


# ── Mã nguyên nhân: CHECK + chốt ─────────────────────────────────────────


async def test_ma_la_hoac_co_lech_ma_bi_db_chan(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = (await _thu(q))["payment_cycle_id"]
    for dat, mong in (
        ("can_doi_soat = true, doi_soat_ly_do = '{DOAN_BUA}'", "ma_hop_le"),
        ("can_doi_soat = true, doi_soat_ly_do = '{}'", "khop_co"),
        ("can_doi_soat = false, doi_soat_ly_do = '{HOA_DON_DOI}'", "khop_co"),
        ("can_doi_soat = true, doi_soat_ly_do = ARRAY[NULL]::text[]", "ma_hop_le"),
    ):
        async with q.pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            try:
                # Tắt chốt trong giao dịch thử để đo riêng CHECK của bảng.
                await conn.execute(
                    "ALTER TABLE payment_cycle DISABLE TRIGGER trg_payment_cycle_guard"
                )
                with pytest.raises(asyncpg.CheckViolationError, match=mong):
                    await conn.execute(
                        f"UPDATE payment_cycle SET {dat}"  # noqa: S608
                        " WHERE payment_cycle_id = $1::uuid",
                        lan,
                    )
            finally:
                await tx.rollback()


async def test_ma_bat_bien_sau_khi_da_thu(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = (await _thu(q))["payment_cycle_id"]
    # Đã thu: không sửa gì tại chỗ được (chốt dừng ngay ở bước chuyển trạng thái).
    with pytest.raises(asyncpg.CheckViolationError, match="không chuyển"):
        await q.pool.execute(
            "UPDATE payment_cycle SET can_doi_soat = true,"
            " doi_soat_ly_do = '{HOA_DON_DOI}' WHERE payment_cycle_id = $1::uuid",
            lan,
        )


async def test_ma_chi_hinh_thanh_luc_cho_sang_da_thu(q: Quay) -> None:
    """Chờ → HUỶ CHỜ là một chuyển hợp lệ, nhưng mã nguyên nhân KHÔNG được hình
    thành ở đó — chỉ ở chờ → đã thu."""
    _, _, _ = await _san_sang(q)
    cho = (await _thu(q, "QR"))["payment_cycle_id"]
    with pytest.raises(asyncpg.CheckViolationError, match="cột đã ghi"):
        await q.pool.execute(
            "UPDATE payment_cycle SET status = 'CANCELLED', closed_at = now(),"
            " closed_by = created_by, close_reason = 'thử gắn mã lúc huỷ',"
            # Chỉ đổi MÃ (không đổi cờ): đo đúng nhánh mã của chốt.
            " doi_soat_ly_do = '{HOA_DON_DOI}'"
            " WHERE payment_cycle_id = $1::uuid",
            cho,
        )


# ── Service: mã dựng từ sự thật lúc xác minh ─────────────────────────────


async def _doi_gia(q: Quay) -> None:
    await q.pool.execute(
        "UPDATE drug_catalog SET unit_price = unit_price + 1000 WHERE id ="
        " (SELECT drug_catalog_id FROM prescription WHERE visit_id = $1::uuid"
        "  LIMIT 1)",
        q.visit_id,
    )


async def _het_han(q: Quay, lo: str) -> None:
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date = current_date - 1 WHERE id = $1::uuid", lo
    )


@pytest.mark.parametrize(
    ("doi_gia", "het_han", "mong"),
    [
        (False, False, []),
        (True, False, ["HOA_DON_DOI"]),
        (False, True, ["CHUA_GHI_BAN"]),
        (True, True, ["HOA_DON_DOI", "CHUA_GHI_BAN"]),
    ],
)
async def test_xac_minh_ghi_dung_ma_nguyen_nhan(
    q: Quay, doi_gia: bool, het_han: bool, mong: list[str]
) -> None:
    _, _, lo = await _san_sang(q)
    cho = (await _thu(q, "TRANSFER"))["payment_cycle_id"]
    if doi_gia:
        await _doi_gia(q)
    if het_han:
        await _het_han(q, lo)
    kq = await _xac_minh(q, cho)
    assert (kq["can_doi_soat"], kq["doi_soat_ly_do"]) == (bool(mong), mong)
    r = await _lan(q, cho)
    assert (r["status"], r["can_doi_soat"], list(r["doi_soat_ly_do"])) == (
        "PAID",
        bool(mong),
        mong,
    )
    # Gửi lại cùng mã giao dịch → như cũ, kể cả mã nguyên nhân.
    assert (await _xac_minh(q, cho))["doi_soat_ly_do"] == mong


# ── Dựng lại mã cho dữ liệu CP2–CP5 ──────────────────────────────────────


async def _su_kien(conn: asyncpg.Connection, loai: str, cycle: str) -> None:
    await conn.execute(
        "INSERT INTO event_log (clinic_id, event_type, aggregate_type, aggregate_id,"
        " payload, metadata, source, event_published)"
        " VALUES ($1::uuid, $2, 'payment', $3::uuid, $4::jsonb, '{}'::jsonb,"
        " 'test', false)",
        CLINIC,
        loai,
        str(uuid.uuid4()),
        json.dumps({"payment_cycle_id": cycle}),
    )


async def _truoc_cp6(conn: asyncpg.Connection, cycle: str) -> None:
    """Dựng lại trạng thái "đã chạy CP2–CP5": cờ bật, chưa có mã (chỉ trong
    giao dịch thử — CHECK và chốt được tắt tạm, rồi huỷ giao dịch)."""
    await conn.execute(
        "ALTER TABLE payment_cycle DROP CONSTRAINT payment_cycle_doi_soat_khop_co"
    )
    await conn.execute(
        "ALTER TABLE payment_cycle DISABLE TRIGGER trg_payment_cycle_guard"
    )
    await conn.execute(
        "UPDATE payment_cycle SET can_doi_soat = true, doi_soat_ly_do = '{}'"
        " WHERE payment_cycle_id = $1::uuid",
        cycle,
    )


async def test_dung_lai_ma_tu_su_kien(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = (await _thu(q))["payment_cycle_id"]
    async with q.pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await _truoc_cp6(conn, lan)
            await _su_kien(conn, "payment.sale_not_applied", lan)
            await _su_kien(conn, "payment.reconciliation_needed", lan)
            assert (
                await conn.fetchval("SELECT payment_cycle_dung_lai_ly_do_doi_soat()")
                >= 1
            )
            assert list(
                await conn.fetchval(
                    "SELECT doi_soat_ly_do FROM payment_cycle"
                    " WHERE payment_cycle_id = $1::uuid",
                    lan,
                )
            ) == ["CHUA_GHI_BAN", "HOA_DON_DOI"]
        finally:
            await tx.rollback()


async def test_can_doi_soat_ma_khong_co_su_kien_thi_dung(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = (await _thu(q))["payment_cycle_id"]
    async with q.pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await _truoc_cp6(conn, lan)
            with pytest.raises(asyncpg.CheckViolationError, match="không đoán"):
                await conn.fetchval("SELECT payment_cycle_dung_lai_ly_do_doi_soat()")
        finally:
            await tx.rollback()
