"""Khách không mua cả đơn + mở lại (16/11/2026) — `services/khach_khong_lay.py`.

Đóng dòng đi đúng `PharmacyService.tu_choi`; mở lại là lệnh bù có sự kiện.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services import ban_thuoc_service as bt
from clinicai.services import khach_khong_lay as kkl
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    q,  # noqa: F401
)
from tests.services.test_tien_thuoc_cp3_db import _san_sang, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def _dong(q: Quay, rx: str) -> dict[str, object]:
    r = await q.pool.fetchrow(
        "SELECT closed_at, refusal_reason, dispense_status FROM prescription"
        " WHERE id = $1::uuid AND removed_at IS NULL",
        rx,
    )
    assert r is not None
    return dict(r)


async def _su_kien(q: Quay, rx: str, loai: str) -> list[dict[str, object]]:
    rows = await q.pool.fetch(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = $2 ORDER BY recorded_at",
        rx,
        loai,
    )
    return [json.loads(r["payload"]) for r in rows]


async def test_ca_don_dong_moi_dong_chua_giao(q: Quay) -> None:
    a, b = await _don(q, 10, "thuoc A"), await _don(q, 5, "thuoc B")
    kq = await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, "  Hết tiền ")
    assert kq == {"ok": True, "so_dong": 2}
    for rx in (a, b):
        d = await _dong(q, rx)
        assert d["closed_at"] is not None
        assert d["refusal_reason"] == "Hết tiền"
        assert d["dispense_status"] == "TU_CHOI"
        assert len(await _su_kien(q, rx, "pharmacy.refused")) == 1
    # Bấm lại: không còn dòng nào để đóng — không lỗi, không ghi thêm.
    lai = await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, "Hết tiền")
    assert lai["so_dong"] == 0
    assert len(await _su_kien(q, a, "pharmacy.refused")) == 1


async def test_luot_da_thu_tu_choi_ca_luot_khong_dong_dong_nao(q: Quay) -> None:
    rx, _drug, _lo = await _san_sang(q, 2)
    await _thu(q)
    # Câu CẢ LƯỢT (kiểm trước khi đóng dòng nào), không phải câu của từng dòng.
    with pytest.raises(ConflictError, match="hoặc đang chờ xác minh"):
        await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, "Đổi ý")
    assert (await _dong(q, rx))["closed_at"] is None
    assert await _su_kien(q, rx, "pharmacy.refused") == []


async def test_mo_lai_dong_ve_dang_xu_ly_co_su_kien(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).tu_choi(
        identity=q.duoc_si, prescription_id=rx, ly_do="Đã có thuốc ở nhà"
    )
    kq = await kkl.mo_lai_dong(q.pool, q.duoc_si, rx)
    assert kq == {"ok": True, "so_dong": 1}
    d = await _dong(q, rx)
    assert d["closed_at"] is None
    assert d["refusal_reason"] is None
    assert d["dispense_status"] == "CHUA_CAP"
    ev = await _su_kien(q, rx, "pharmacy.refuse_undone")
    assert len(ev) == 1
    assert ev[0]["refusal_reason_cu"] == "Đã có thuốc ở nhà"
    # Bấm lại: dòng đã mở — không ghi thêm sự kiện.
    assert (await kkl.mo_lai_dong(q.pool, q.duoc_si, rx))["so_dong"] == 0
    assert len(await _su_kien(q, rx, "pharmacy.refuse_undone")) == 1
    # Mở xong thì ghi "khách không lấy" lại được như thường.
    await PharmacyService(q.pool).tu_choi(
        identity=q.duoc_si, prescription_id=rx, ly_do="Lại đổi ý"
    )
    assert (await _dong(q, rx))["refusal_reason"] == "Lại đổi ý"


async def test_mo_lai_ca_don(q: Quay) -> None:
    a, b = await _don(q, 10, "thuoc A"), await _don(q, 5, "thuoc B")
    await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, "Hết tiền")
    kq = await kkl.mo_lai_ca_don(q.pool, q.duoc_si, q.visit_id)
    assert kq == {"ok": True, "so_dong": 2}
    for rx in (a, b):
        assert (await _dong(q, rx))["closed_at"] is None
        assert len(await _su_kien(q, rx, "pharmacy.refuse_undone")) == 1


async def test_khong_mo_dong_chot_khong_giao_them(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    with pytest.raises(ConflictError, match="Chốt"):
        await kkl.mo_lai_dong(q.pool, q.duoc_si, rx)
    assert (await kkl.mo_lai_ca_don(q.pool, q.duoc_si, q.visit_id))["so_dong"] == 0
    assert (await _dong(q, rx))["closed_at"] is not None


async def test_ly_do_rong_la_loi_nhap(q: Quay) -> None:
    rx = await _don(q, 10)
    for ly in ("", "   ", None):
        with pytest.raises(ValidationError):
            await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, ly)
    assert (await _dong(q, rx))["closed_at"] is None


async def test_id_rac_khong_500(q: Quay) -> None:
    for rac in ("abc", "", None, 123, "1' OR 1=1 --"):
        with pytest.raises(ValidationError):
            await kkl.khong_lay_ca_don(q.pool, q.duoc_si, rac, "Hết tiền")
        with pytest.raises(ValidationError):
            await kkl.mo_lai_dong(q.pool, q.duoc_si, rac)
        with pytest.raises(ValidationError):
            await kkl.mo_lai_ca_don(q.pool, q.duoc_si, rac)


async def test_co_tren_man_theo_dung_luat(q: Quay) -> None:
    rx = await _don(q, 10)

    async def luot() -> dict[str, Any]:
        man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
        return next(x for x in man["luot"] if x["visit_id"] == q.visit_id)

    truoc = await luot()
    assert truoc["khong_lay_ca_don"] is True
    assert truoc["mo_lai_ca_don"] is False
    await kkl.khong_lay_ca_don(q.pool, q.duoc_si, q.visit_id, "Hết tiền")
    sau = await luot()
    assert sau["khong_lay_ca_don"] is False
    assert sau["mo_lai_ca_don"] is True
    dong = next(d for d in sau["dong"] if d["id"] == rx)
    assert dong["thao_tac"]["mo_lai"] is True


async def test_luat_mo_lai_ham_thuan() -> None:
    chung: dict[str, Any] = {
        "da_dong": True,
        "khach_khong_lay": True,
        "da_giao": Decimal(0),
        "lich_su": False,
        "da_thu_tien": False,
    }
    assert kkl.ly_do_khong_mo_lai(**chung) is None
    sai: dict[str, Any]
    for sai in (
        {"da_dong": False},
        {"khach_khong_lay": False},
        {"da_giao": Decimal(1)},
        {"lich_su": True},
        {"da_thu_tien": True},
    ):
        assert kkl.ly_do_khong_mo_lai(**{**chung, **sai})
    # Cờ trên màn dùng cùng luật: đã thu (giai đoạn khác SAN_SANG) → không mở.
    tt: dict[str, Any] = {
        "dong_da_chot": True,
        "da_giao": Decimal(0),
        "co_thuoc_kho": False,
        "co_don_vi": True,
        "co_so_ke": True,
        "can_lo": Decimal(0),
        "da_chon": Decimal(0),
        "co_phan_lo": False,
        "so_ban": Decimal(10),
        "khach_khong_lay": True,
    }
    assert bt.thao_tac_dong(gd=bt.SAN_SANG, **tt)["mo_lai"]
    assert not bt.thao_tac_dong(gd=bt.DA_THU, **tt)["mo_lai"]
    assert not bt.thao_tac_dong(gd=bt.SAN_SANG, **{**tt, "khach_khong_lay": False})[
        "mo_lai"
    ]
    assert not bt.thao_tac_dong(gd=bt.SAN_SANG, **tt, co_quyen_ghi=False)["mo_lai"]
