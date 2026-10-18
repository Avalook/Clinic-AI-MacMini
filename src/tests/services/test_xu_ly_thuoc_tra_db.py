"""Thuốc khách trả: lệnh QUYẾT ĐỊNH xử lý (17/10/2026, việc B của KE-HOACH-QUY-DOI).

    scripts/test-nhanh.sh src/tests/services/test_xu_ly_thuoc_tra_db.py

Trước đây (CP5, HOLD J1/J2) thuốc khách trả nằm "chờ kiểm" vĩnh viễn: tồn vật lý +,
lượng bán được − và không lệnh nào quyết. Nay đúng MỘT quyết định, một lần:

    trả 3 viên          : tồn vật lý +3   · bán được  0  (giữ chờ kiểm)
    BAN_LAI (bán lại)   : tồn vật lý  0   · bán được +3
    HUY (huỷ)           : tồn vật lý −3   · bán được  0, và một dòng DISCARD

Số mong đợi tính tay theo sơ đồ trên (so với trạng thái TRƯỚC khi trả), không tính
lại bằng chính hàm đang thử.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _kd, _ton
from tests.services.test_tien_thuoc_cp5_db import _da_thu_giao, _tra, _xuat

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def _lan_tra(q: Quay, so: int = 3) -> tuple[str, str, str, tuple[int, int]]:
    """Giao rồi cho khách trả `so` viên. Trả (id lần trả, id lô, rx, (tồn, bán được)
    TRƯỚC khi trả)."""
    rx, lo, _ = await _da_thu_giao(q, 5)
    truoc = (await _ton(q, lo), await _kd(q, lo))
    await _tra(q, await _xuat(q, rx), so)
    tra = await q.pool.fetchval(
        "SELECT id::text FROM drug_return WHERE prescription_id = $1::uuid", rx
    )
    return str(tra), lo, rx, truoc


async def _xu_ly(
    q: Quay, tra: str, quyet: Any, ly: str | None = None
) -> dict[str, Any]:
    return await PharmacyService(q.pool).xu_ly_thuoc_tra(
        identity=q.duoc_si, drug_return_id=tra, quyet_dinh=quyet, ly_do=ly
    )


async def test_tra_xong_chua_quyet_thi_giu_cho_kiem(q: Quay) -> None:
    tra, lo, _rx, (ton0, kd0) = await _lan_tra(q, 3)
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton0 + 3, kd0)
    cho = await PharmacyService(q.pool).thuoc_tra_cho_kiem(identity=q.duoc_si)
    d = next(x for x in cho if x["id"] == tra)
    assert (d["so_luong"], d["batch_code"], d["ly_do_tra"]) == (
        Decimal(3),
        await q.pool.fetchval(
            "SELECT batch_code FROM drug_batch WHERE id=$1::uuid", lo
        ),
        "Khách dị ứng",
    )
    assert d["thuoc"] and d["nguoi_tra"]


async def test_ban_lai_chi_dat_quyet_dinh_va_ban_duoc_tang_lai(q: Quay) -> None:
    tra, lo, _rx, (ton0, kd0) = await _lan_tra(q, 3)
    kq = await _xu_ly(q, tra, "BAN_LAI")
    assert kq["discard_txn_id"] is None
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton0 + 3, kd0 + 3)
    r = await q.pool.fetchrow(
        "SELECT disposition, disposition_by::text AS boi, disposition_at,"
        " disposition_reason, disposition_txn_id FROM drug_return WHERE id=$1::uuid",
        tra,
    )
    assert r["disposition"] == "BAN_LAI" and r["boi"] == q.duoc_si.staff_id
    assert r["disposition_at"] is not None and r["disposition_txn_id"] is None
    # Không có dòng DISCARD nào cho lần trả này.
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE ref_type = 'drug_return'"
            " AND txn_type = 'DISCARD' AND ref_id = $1::uuid",
            tra,
        )
        == 0
    )
    cho = await PharmacyService(q.pool).thuoc_tra_cho_kiem(identity=q.duoc_si)
    assert tra not in [x["id"] for x in cho]


async def test_huy_ghi_discard_cung_giao_dich_va_ton_vat_ly_giam(q: Quay) -> None:
    tra, lo, _rx, (ton0, kd0) = await _lan_tra(q, 3)
    kq = await _xu_ly(q, tra, "HUY", "Hộp đã mở, hỏng")
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton0, kd0)  # về đúng trước khi trả
    txn = await q.pool.fetchrow(
        "SELECT txn_type, quantity, reason, ref_type, ref_id::text AS ref_id,"
        " drug_batch_id::text AS lo FROM inventory_txn WHERE id = $1::uuid",
        kq["discard_txn_id"],
    )
    assert (txn["txn_type"], txn["quantity"], txn["ref_type"], txn["ref_id"]) == (
        "DISCARD",
        Decimal(-3),
        "drug_return",
        tra,
    )
    assert txn["lo"] == lo and "Hộp đã mở, hỏng" in txn["reason"]
    r = await q.pool.fetchrow(
        "SELECT disposition, disposition_reason, disposition_txn_id::text AS txn"
        " FROM drug_return WHERE id = $1::uuid",
        tra,
    )
    assert (r["disposition"], r["disposition_reason"], r["txn"]) == (
        "HUY",
        "Hộp đã mở, hỏng",
        kq["discard_txn_id"],
    )


@pytest.mark.parametrize("ly", [None, "", "  ", "ab"])
async def test_huy_phai_co_ly_do(q: Quay, ly: str | None) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 2)
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    with pytest.raises(ValidationError, match="ghi lý do"):
        await _xu_ly(q, tra, "HUY", ly)
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)
    assert (
        await q.pool.fetchval(
            "SELECT disposition FROM drug_return WHERE id=$1::uuid", tra
        )
        is None
    )


@pytest.mark.parametrize("quyet", [None, "", "RESTOCK", "huy", [], {}, 3])
async def test_quyet_dinh_rac_thanh_cau_tieng_viet(q: Quay, quyet: Any) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 2)
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    with pytest.raises(ValidationError, match="nhập lại bán được"):
        await _xu_ly(q, tra, quyet, "lý do")
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)


@pytest.mark.parametrize(
    ("dau", "sau"),
    [("BAN_LAI", "HUY"), ("HUY", "BAN_LAI"), ("HUY", "HUY"), ("BAN_LAI", "BAN_LAI")],
)
async def test_chi_quyet_mot_lan_lan_hai_khong_doi_gi(
    q: Quay, dau: str, sau: str
) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 3)
    await _xu_ly(q, tra, dau, "Hỏng nắp")
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    with pytest.raises(ConflictError, match="đã được xử lý"):
        await _xu_ly(q, tra, sau, "Đổi ý nhé")
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)
    assert await q.pool.fetchval(
        "SELECT count(*) FROM inventory_txn WHERE ref_type='drug_return'"
        " AND txn_type='DISCARD' AND ref_id=$1::uuid",
        tra,
    ) == (1 if dau == "HUY" else 0)


async def test_hai_nguoi_cung_bam_chi_mot_nguoi_thang(q: Quay) -> None:
    tra, lo, _rx, (ton0, _) = await _lan_tra(q, 3)
    kq = await asyncio.gather(
        _xu_ly(q, tra, "HUY", "Hỏng nắp"),
        _xu_ly(q, tra, "HUY", "Hỏng nắp"),
        return_exceptions=True,
    )
    loi = [x for x in kq if isinstance(x, BaseException)]
    assert len(loi) == 1 and isinstance(loi[0], ConflictError), kq
    assert await _ton(q, lo) == ton0  # chỉ MỘT dòng DISCARD
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE ref_type='drug_return'"
            " AND txn_type='DISCARD' AND ref_id=$1::uuid",
            tra,
        )
        == 1
    )


async def test_postgres_chan_sua_lan_hai_xoa_va_sua_cot_khac(q: Quay) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 3)
    # Cột khác ngoài quyết định: không sửa được kể cả lần đầu.
    with pytest.raises(asyncpg.PostgresError, match="không sửa cột khác"):
        await q.pool.execute(
            "UPDATE drug_return SET returned_qty = 1, disposition = 'BAN_LAI',"
            " disposition_by = returned_by, disposition_at = now() WHERE id=$1::uuid",
            tra,
        )
    # Giá trị lạ.
    with pytest.raises(asyncpg.CheckViolationError, match="BAN_LAI hoặc HUY"):
        await q.pool.execute(
            "UPDATE drug_return SET disposition = 'RESTOCK',"
            " disposition_by = returned_by, disposition_at = now()"
            " WHERE id=$1::uuid",
            tra,
        )
    # HUY mà không có dòng DISCARD → CHECK chặn (huỷ mà tồn không giảm là sai sổ).
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE drug_return SET disposition = 'HUY', disposition_by = returned_by,"
            " disposition_at = now(), disposition_reason = 'không có dòng sổ'"
            " WHERE id=$1::uuid",
            tra,
        )
    receive = await q.pool.fetchval(
        "SELECT id::text FROM inventory_txn WHERE clinic_id=$1::uuid"
        " AND drug_batch_id=$2::uuid AND txn_type='RECEIVE' LIMIT 1",
        q.duoc_si.clinic_id,
        lo,
    )
    assert receive is not None
    # Cùng clinic/lô là chưa đủ: dòng RECEIVE không thể chứng minh đã huỷ tồn.
    with pytest.raises(asyncpg.CheckViolationError, match="đúng DISCARD"):
        await q.pool.execute(
            "UPDATE drug_return SET disposition='HUY', disposition_by=returned_by,"
            " disposition_at=now(), disposition_reason='Huỷ lô trả',"
            " disposition_txn_id=$2::uuid WHERE id=$1::uuid",
            tra,
            receive,
        )
    manual = await PharmacyService(q.pool).huy(
        identity=q.duoc_si, drug_batch_id=lo, so_luong=1, ly_do="Huỷ kiểm thử"
    )
    discard_sai = await q.pool.fetchval(
        "SELECT id::text FROM inventory_txn WHERE clinic_id=$1::uuid"
        " AND drug_batch_id=$2::uuid AND txn_type='DISCARD' AND ref_type='manual'"
        " ORDER BY performed_at DESC LIMIT 1",
        q.duoc_si.clinic_id,
        lo,
    )
    assert manual["ok"] and discard_sai is not None
    # Cùng loại nhưng sai lượng và sai ref_type/ref_id cũng phải bị chặn.
    with pytest.raises(asyncpg.CheckViolationError, match="đúng DISCARD"):
        await q.pool.execute(
            "UPDATE drug_return SET disposition='HUY', disposition_by=returned_by,"
            " disposition_at=now(), disposition_reason='Huỷ lô trả',"
            " disposition_txn_id=$2::uuid WHERE id=$1::uuid",
            tra,
            discard_sai,
        )
    await _xu_ly(q, tra, "BAN_LAI")
    with pytest.raises(asyncpg.PostgresError, match="đã xử lý"):
        await q.pool.execute(
            "UPDATE drug_return SET disposition_reason = 'sửa lại' WHERE id=$1::uuid",
            tra,
        )
    with pytest.raises(asyncpg.PostgresError, match="không xoá"):
        await q.pool.execute("DELETE FROM drug_return WHERE id=$1::uuid", tra)


async def test_lo_cua_co_so_khac_thi_khong_thay(q: Quay) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 2)
    khac = dataclasses.replace(q.duoc_si, location_id=str(uuid.uuid4()))
    with pytest.raises(NotFoundError):
        await PharmacyService(q.pool).xu_ly_thuoc_tra(
            identity=khac, drug_return_id=tra, quyet_dinh="BAN_LAI"
        )
    cho = await PharmacyService(q.pool).thuoc_tra_cho_kiem(identity=khac)
    assert tra not in [x["id"] for x in cho]
    assert (
        await q.pool.fetchval(
            "SELECT disposition FROM drug_return WHERE id=$1::uuid", tra
        )
        is None
    )
    assert await _ton(q, lo) is not None


async def test_huy_khi_so_ke_it_hon_so_tra_thi_bao_kiem_kho(q: Quay) -> None:
    tra, lo, _rx, _ = await _lan_tra(q, 3)
    ton = await _ton(q, lo)
    async with q.pool.acquire() as conn:
        await PharmacyService._ghi_so_trong(
            conn,
            identity=q.duoc_si,
            drug_batch_id=lo,
            txn_type="ADJUST",
            quantity=Decimal(-(ton - 1)),
            reason="kiểm kho",
            ref_type="manual",
            ref_id=None,
        )
    with pytest.raises(ConflictError, match="kiểm kho trước khi huỷ"):
        await _xu_ly(q, tra, "HUY", "Hỏng nắp")
    assert (
        await q.pool.fetchval(
            "SELECT disposition FROM drug_return WHERE id=$1::uuid", tra
        )
        is None
    )
