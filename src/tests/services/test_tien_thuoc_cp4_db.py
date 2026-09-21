"""Contract tiền–thuốc CP4 (19/09/2026): màn Nhà thuốc — máy chủ quyết giai
đoạn và thao tác, giao diện chỉ vẽ."""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole
from clinicai.services import ban_thuoc_service as bt
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _giao,
    _san_sang,
    _thu,
    _xac_minh,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


def _lt(status: str, legacy: bool = False) -> bt.LanThu:
    return bt.LanThu("c", status, "CASH", legacy, False)


@pytest.mark.parametrize(
    ("kham_xong", "lan", "chua_ban", "ket_qua"),
    [
        (False, None, False, bt.CHUA_SAN_SANG),
        (True, None, False, bt.SAN_SANG),
        (True, _lt("PENDING_VERIFICATION"), False, bt.CHO_XAC_MINH),
        (True, _lt("PAID"), False, bt.DA_THU),
        (True, _lt("PAID"), True, bt.CAN_DOI_SOAT),
        (True, _lt("PAID", legacy=True), False, bt.DA_THU_CU),
    ],
)
def test_giai_doan(
    kham_xong: bool, lan: bt.LanThu | None, chua_ban: bool, ket_qua: str
) -> None:
    assert (
        bt.giai_doan(kham_xong=kham_xong, lan_thu=lan, co_phan_lo_chua_ban=chua_ban)
        == ket_qua
    )


def _tt(gd: str, **kw: Any) -> dict[str, bool]:
    mac_dinh: dict[str, Any] = {
        "dong_da_chot": False,
        "da_giao": Decimal(0),
        "co_thuoc_kho": True,
        "co_don_vi": True,
        "co_so_ke": True,
        "can_lo": Decimal(10),
        "da_chon": Decimal(0),
        "co_phan_lo": False,
        "so_ban": Decimal(10),
    }
    return bt.thao_tac_dong(gd=gd, **{**mac_dinh, **kw})


def test_chua_kham_xong_chi_xem_khong_chon_lo() -> None:
    tt = _tt(bt.CHUA_SAN_SANG)
    # Chỉ xem: cả từ chối / chốt cũng khoá dòng khỏi nút Lưu bệnh án.
    assert not any(tt.values())


def test_sau_khi_thu_khong_sua_thuoc_so_mua_lo() -> None:
    for gd in (bt.CHO_XAC_MINH, bt.DA_THU, bt.CAN_DOI_SOAT):
        tt = _tt(gd)
        assert not (tt["xac_dinh_thuoc"] or tt["khai_so_mua"] or tt["chon_lo"])
        assert not tt["tu_choi"]


def test_tu_phan_lo_khong_phat_nut_chon_lo() -> None:
    assert not _tt(bt.SAN_SANG)["chon_lo"]
    assert not _tt(bt.SAN_SANG, da_chon=Decimal(10))["chon_lo"]
    assert not _tt(bt.SAN_SANG, co_don_vi=False)["chon_lo"]


def test_nut_cua_phan_lo_theo_giai_doan() -> None:
    def pl(gd: str, gan: bool, ban: bool = False, con: int = 10) -> dict[str, bool]:
        return bt.thao_tac_phan_lo(
            gd=gd,
            dong_da_chot=False,
            gan_lan_thu=gan,
            da_ban=ban,
            con_giao=Decimal(con),
        )

    assert pl(bt.SAN_SANG, False) == {"bo": False, "doi": False, "giao": False}
    assert pl(bt.CHO_XAC_MINH, True) == {
        "bo": False,
        "doi": False,
        "giao": False,
    }
    assert pl(bt.DA_THU, True, ban=True) == {"bo": False, "doi": False, "giao": True}
    assert not pl(bt.DA_THU, True, ban=True, con=0)["giao"]
    assert not pl(bt.CAN_DOI_SOAT, True)["giao"]


# ── Máy chủ chặn chọn lô trước Khám xong ─────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_chua_kham_xong_khong_chon_lo_duoc(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    lo = await _nhap_lo(q, drug, 100)
    await q.pool.execute(
        "UPDATE appointment SET status = 'CHECKED_IN' WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        q.visit_id,
    )
    with pytest.raises(ConflictError, match="Khám xong"):
        await _chon(q, rx, lo, 10)


# ── Đọc màn: đi qua các giai đoạn ────────────────────────────────────────


async def _luot(q: Quay) -> dict[str, Any]:
    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    return next(g for g in man["luot"] if g["visit_id"] == q.visit_id)


@pytest.mark.db
@pytest.mark.asyncio
async def test_man_nha_thuoc_qua_tung_giai_doan(q: Quay) -> None:
    rx, drug, lo = await _san_sang(q, 10, 100)
    g = await _luot(q)
    assert g["giai_doan"] == bt.SAN_SANG
    d = g["dong"][0]
    assert (d["can_lo"], d["da_chon"]) == (Decimal(10), Decimal(10))
    assert not d["phan_lo"][0]["thao_tac"]["bo"]
    assert not d["thao_tac"]["chon_lo"]
    assert [
        (b["ton_vat_ly"], b["co_the_phan_lo"])
        for b in d["lo_goi_y"]
        if b["drug_batch_id"] == lo
    ] == [(Decimal(100), Decimal(100))]

    cho = await _thu(q, "QR")
    g = await _luot(q)
    assert g["giai_doan"] == bt.CHO_XAC_MINH
    pl = g["dong"][0]["phan_lo"][0]
    assert pl["dang_giu"] and not any(pl["thao_tac"].values())
    assert g["dong"][0]["lo_goi_y"][0]["co_the_phan_lo"] == Decimal(90)

    await _xac_minh(q, cho["payment_cycle_id"])
    g = await _luot(q)
    assert g["giai_doan"] == bt.DA_THU
    assert g["dong"][0]["phan_lo"][0]["thao_tac"]["giao"]
    await _giao(q, rx, lo, 4)
    pl = (await _luot(q))["dong"][0]["phan_lo"][0]
    assert (pl["handed_over_qty"], pl["con_giao"]) == (Decimal(4), Decimal(6))


@pytest.mark.db
@pytest.mark.asyncio
async def test_man_nha_thuoc_can_doi_soat_khong_cho_giao(q: Quay) -> None:
    _, _, lo = await _san_sang(q)
    cho = await _thu(q, "TRANSFER")
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date = current_date - 1 WHERE id = $1::uuid", lo
    )
    await _xac_minh(q, cho["payment_cycle_id"])
    g = await _luot(q)
    assert g["giai_doan"] == bt.CAN_DOI_SOAT
    assert g["lan_thu"]["can_doi_soat"] is True
    assert not g["dong"][0]["phan_lo"][0]["thao_tac"]["giao"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_man_nha_thuoc_huy_phieu_khong_moi_chon_lo_tay(q: Quay) -> None:
    _, _, _ = await _san_sang(q)
    lan = await _thu(q)
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=lan["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Thu nhầm khách",
        identity=q.thu_ngan,
    )
    g = await _luot(q)
    assert g["giai_doan"] == bt.SAN_SANG and g["lan_thu"] is None
    # Kế hoạch lô vẫn còn để lần thu sau tái sử dụng, nhưng không mời sửa tay.
    assert not any(g["dong"][0]["phan_lo"][0]["thao_tac"].values())


@pytest.mark.db
@pytest.mark.asyncio
async def test_man_nha_thuoc_luot_khac_phong_kham_khong_lot(q: Quay) -> None:
    await _san_sang(q)
    khac = dataclasses.replace(
        q.duoc_si, clinic_id="00000000-0000-0000-0000-00000000dead"
    )
    man = await bt.man_nha_thuoc(q.pool, identity=khac)
    assert all(g["visit_id"] != q.visit_id for g in man["luot"])


# ── Review CP4 P1 #1: chưa Khám xong thì MỌI lệnh đổi dòng thuốc bị chặn ──


@pytest.mark.db
@pytest.mark.asyncio
async def test_chua_kham_xong_ca_nam_lenh_ghi_deu_bi_chan(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)  # xác định khi đã Khám xong
    lo = await _nhap_lo(q, drug, 100)
    await q.pool.execute(
        "UPDATE appointment SET status = 'CHECKED_IN' WHERE id ="
        " (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)",
        q.visit_id,
    )
    ph = PharmacyService(q.pool)
    lenh = {
        "xac_dinh_thuoc": ph.xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
        ),
        "khai_so_luong_mua": ph.khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=5
        ),
        "phan_lo": ph.phan_lo(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=10
        ),
        "tu_choi": ph.tu_choi(
            identity=q.duoc_si, prescription_id=rx, ly_do="khách đã có thuốc"
        ),
        "chot": ph.chot(identity=q.duoc_si, prescription_id=rx),
    }
    for ten, coro in lenh.items():
        with pytest.raises(ConflictError, match="Khám xong"):
            await coro
        assert ten
    r = await q.pool.fetchrow(
        "SELECT closed_at, purchased_qty FROM prescription WHERE id = $1::uuid", rx
    )
    assert r["closed_at"] is None and r["purchased_qty"] is None


# ── Review CP4 P1 #2: chốt không bỏ lại thuốc đã bán chưa giao ───────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_da_thu_giao_mot_phan_thi_khong_chot_duoc(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 3)
    with pytest.raises(ConflictError, match="Còn 7 đã bán mà chưa giao"):
        await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    d = (await _luot(q))["dong"][0]
    assert not d["closed"] and not d["thao_tac"]["chot"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_da_thu_giao_du_thi_chot_duoc(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 10)
    assert (await _luot(q))["dong"][0]["thao_tac"]["chot"]
    kq = await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    assert kq["dispense_status"] == "CAP_DU"


@pytest.mark.db
@pytest.mark.asyncio
async def test_can_doi_soat_hoac_cho_xac_minh_thi_khong_chot(q: Quay) -> None:
    rx, _, lo = await _san_sang(q)
    cho = await _thu(q, "TRANSFER")
    with pytest.raises(ConflictError, match="chờ xác minh"):
        await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date = current_date - 1 WHERE id = $1::uuid", lo
    )
    await _xac_minh(q, cho["payment_cycle_id"])
    with pytest.raises(ConflictError, match="đối soát"):
        await PharmacyService(q.pool).chot(identity=q.duoc_si, prescription_id=rx)
    g = await _luot(q)
    assert g["giai_doan"] == bt.CAN_DOI_SOAT and not g["dong"][0]["thao_tac"]["chot"]


def test_nut_chot_theo_giai_doan_va_so_da_giao() -> None:
    assert _tt(bt.SAN_SANG)["chot"]
    assert _tt(bt.DA_THU_CU)["chot"]
    assert not _tt(bt.CHO_XAC_MINH)["chot"]
    assert not _tt(bt.CAN_DOI_SOAT, da_giao=Decimal(10))["chot"]
    assert not _tt(bt.DA_THU, da_giao=Decimal(3))["chot"]
    assert _tt(bt.DA_THU, da_giao=Decimal(10))["chot"]


# ── Review CP4 P2: người chỉ đọc không thấy nút ghi ──────────────────────


def test_khong_co_quyen_ghi_thi_khong_nut_nao() -> None:
    assert not any(_tt(bt.SAN_SANG, co_quyen_ghi=False).values())
    assert not any(
        bt.thao_tac_phan_lo(
            gd=bt.DA_THU,
            dong_da_chot=False,
            gan_lan_thu=True,
            da_ban=True,
            con_giao=Decimal(5),
            co_quyen_ghi=False,
        ).values()
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_thu_ngan_thuoc_xem_duoc_nhung_khong_co_nut(q: Quay) -> None:
    await _san_sang(q)
    doc = dataclasses.replace(
        q.thu_ngan, role=ClinicRole.CASHIER_THUOC, vai_tai_khoan=None
    )
    man = await bt.man_nha_thuoc(q.pool, identity=doc)
    g = next(x for x in man["luot"] if x["visit_id"] == q.visit_id)
    assert man["co_quyen_ghi"] is False and g["giai_doan"] == bt.SAN_SANG
    d = g["dong"][0]
    assert not any(d["thao_tac"].values())
    assert not any(v for p in d["phan_lo"] for v in p["thao_tac"].values())
    # Flow tự phân lô không phát hành thao tác sửa lô kể cả cho người có quyền ghi.
    assert not any((await _luot(q))["dong"][0]["phan_lo"][0]["thao_tac"].values())
