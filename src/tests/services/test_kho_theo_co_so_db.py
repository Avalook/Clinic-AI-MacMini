"""Kho riêng từng cơ sở (Tuyền chốt 08/10/2026, mở Hào Nam).

Lô và phiếu kho thuộc một cơ sở. Thao tác gắn LƯỢT dùng cơ sở của lượt (DB
chặn lô cơ sở khác); màn kho / nhập / kiểm dùng cơ sở đang làm
(`identity.location_id`). Cùng số lô được có ở hai cơ sở.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import dataclasses
import uuid
from datetime import date
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services import ban_thuoc_service as bt
from clinicai.services import kho_thuoc_service as kho
from clinicai.services.pharmacy_service import LO_KHAC_CO_SO, PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _chon, _dong_da_xac_dinh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _co_so_hn(q: Quay) -> tuple[str, str]:
    """Cơ sở thứ hai của CÙNG phòng khám. is_active = false: DB test dùng chung
    trong một lượt chạy — cơ sở đang mở thứ hai sẽ đổi hành vi tự gán cơ sở
    của các bài khác. Kho không xét is_active."""
    ma = f"HN{q.duoi}"
    loc = await q.pool.fetchval(
        "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
        " VALUES ($1::uuid, $2, 'Hào Nam thử', false) RETURNING id::text",
        CLINIC,
        ma,
    )
    return str(loc), ma.upper()


def _o(identity: StaffIdentity, loc: str) -> StaffIdentity:
    return dataclasses.replace(identity, location_id=loc, location_name="Hào Nam")


async def _nhap(
    q: Quay, identity: StaffIdentity, drug: str, ma_lo: str, so: int
) -> str:
    kq = await PharmacyService(q.pool).nhap_lo(
        identity=identity,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=ma_lo,
        expiry_date=date(2099, 12, 31),
        unit="viên",
    )
    return str(kq["drug_batch_id"])


async def test_cung_so_lo_hai_co_so_va_ton_kho_theo_co_so(q: Quay) -> None:
    hn, _ = await _co_so_hn(q)
    duoc_si_hn = _o(q.duoc_si, hn)
    _rx, drug = await _dong_da_xac_dinh(q, 5)
    ma_lo = f"LO-CHUNG-{q.duoi}"
    lo_kn = await _nhap(q, q.duoc_si, drug, ma_lo, 30)
    lo_hn = await _nhap(q, duoc_si_hn, drug, ma_lo, 7)
    assert lo_kn != lo_hn

    # Nhập lại cùng số lô ở HN cộng vào lô HN, không đụng lô KN.
    assert await _nhap(q, duoc_si_hn, drug, ma_lo, 3) == lo_hn
    ton = dict(
        await q.pool.fetch(
            "SELECT id::text, quantity_on_hand FROM drug_batch"
            " WHERE id = ANY($1::uuid[])",
            [lo_kn, lo_hn],
        )
    )
    assert (float(ton[lo_kn]), float(ton[lo_hn])) == (30, 10)

    svc = PharmacyService(q.pool)
    thay_kn = {r["id"] for r in await svc.ton_kho(identity=q.duoc_si)}
    thay_hn = {r["id"] for r in await svc.ton_kho(identity=duoc_si_hn)}
    assert lo_kn in thay_kn and lo_hn not in thay_kn
    assert lo_hn in thay_hn and lo_kn not in thay_hn

    dm_hn = next(r for r in await svc.danh_muc(identity=duoc_si_hn) if r["id"] == drug)
    assert float(dm_hn["ton"]) == 10
    the_hn = await kho.the_kho(q.pool, identity=duoc_si_hn, drug_catalog_id=drug)
    assert sum(float(d["so_luong"]) for d in the_hn["dong"]) == 10


async def test_lo_hn_khong_phan_duoc_cho_luot_kn(q: Quay) -> None:
    hn, _ = await _co_so_hn(q)
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo_hn = await _nhap(q, _o(q.duoc_si, hn), drug, f"LO-HN-{q.duoi}", 50)
    lo_kn = await _nhap_lo(q, drug, 50)

    # Màn Nhà thuốc chỉ gợi ý lô của cơ sở của lượt.
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    g = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
    goi_y = {b["drug_batch_id"] for d in g["dong"] for b in d["lo_goi_y"]}
    assert lo_kn in goi_y and lo_hn not in goi_y

    # Qua service: câu tiếng Việt.
    with pytest.raises(ValidationError) as loi:
        await _chon(q, rx, lo_hn, 10)
    assert loi.value.message == LO_KHAC_CO_SO

    # Lách service, ghi thẳng: DB chặn.
    with pytest.raises(asyncpg.CheckViolationError, match="cơ sở"):
        await q.pool.execute(
            "INSERT INTO prescription_allocation (clinic_id, visit_id,"
            " prescription_id, drug_catalog_id, drug_batch_id, quantity, created_by)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, 10, $6::uuid)",
            CLINIC,
            q.visit_id,
            rx,
            drug,
            lo_hn,
            q.duoc_si.staff_id,
        )
    # Lô đúng cơ sở vẫn đi qua.
    await _chon(q, rx, lo_kn, 10)


async def test_so_kho_giao_theo_don_lo_khac_co_so_bi_db_chan(q: Quay) -> None:
    hn, _ = await _co_so_hn(q)
    rx, drug = await _dong_da_xac_dinh(q, 4)
    lo_hn = await _nhap(q, _o(q.duoc_si, hn), drug, f"LO-HN2-{q.duoi}", 20)
    with pytest.raises(asyncpg.CheckViolationError, match="cơ sở"):
        await q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type,"
            " quantity, ref_type, ref_id, performed_by_staff_id)"
            " VALUES ($1::uuid, $2::uuid, 'DISPENSE', -4, 'prescription',"
            " $3::uuid, $4::uuid)",
            CLINIC,
            lo_hn,
            rx,
            q.duoc_si.staff_id,
        )


async def test_so_phieu_kem_ma_co_so_va_kiem_kho_theo_co_so(q: Quay) -> None:
    hn, ma_hn = await _co_so_hn(q)
    duoc_si_hn = _o(q.duoc_si, hn)
    _rx, drug = await _dong_da_xac_dinh(q, 1)

    def _dong(ma_lo: str) -> list[dict[str, Any]]:
        return [
            {
                "drug_catalog_id": drug,
                "batch_code": ma_lo,
                "expiry_date": "2099-12-31",
                "so_luong": 12,
                "gia_nhap": 1000,
                "unit": "viên",
            }
        ]

    kq_hn = await kho.tao_phieu_nhap(
        q.pool,
        identity=duoc_si_hn,
        khoa_gui=uuid.uuid4().hex,
        dong=_dong(f"LO-P-{q.duoi}"),
    )
    assert kq_hn["ma_phieu"] == f"PN-{ma_hn}-0001"

    ma_kn = await q.pool.fetchval(
        "SELECT upper(btrim(code)) FROM clinic_location WHERE id = $1::uuid",
        q.duoc_si.location_id,
    )
    kq_kn = await kho.tao_phieu_nhap(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=_dong(f"LO-P-{q.duoi}"),  # cùng số lô, cơ sở khác: được
    )
    assert kq_kn["ma_phieu"].startswith(f"PN-{ma_kn}-")

    ds_hn = await kho.danh_sach_phieu(q.pool, identity=duoc_si_hn, loai="NHAP")
    phieu_hn = {p["id"] for p in ds_hn}
    assert kq_hn["id"] in phieu_hn and kq_kn["id"] not in phieu_hn
    assert kho.ma_phieu_kho("KIEM", "KN", 12) == "KK-KN-0012"

    lo_kn = await q.pool.fetchval(
        "SELECT drug_batch_id::text FROM phieu_kho_dong WHERE phieu_kho_id = $1::uuid",
        kq_kn["id"],
    )
    # Kiểm kho ở HN không chạm lô KN.
    with pytest.raises(NotFoundError, match="cơ sở"):
        await kho.kiem_kho(
            q.pool,
            identity=duoc_si_hn,
            khoa_gui=uuid.uuid4().hex,
            dong=[{"drug_batch_id": lo_kn, "thuc_te": 0}],
        )
    kk = await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo_kn, "thuc_te": 12}],
    )
    assert kk["ma_phieu"].startswith(f"KK-{ma_kn}-")
