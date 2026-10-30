"""Kho ↔ quầy thật · kiểm ca số thật · đồng bộ hoàn tác (Tuyền 31/10/2026).

Mỗi nhóm bài ứng với một tình huống đã nêu trong đợt 31/10: lệch tính tại lúc đếm,
ô trống khác số 0, lệch không áp được phải nói ra, hoàn tác lần thu / hoàn tác giao
ở mọi trạng thái dòng đơn, khách trả rồi hoàn tác, chuyển kho hai chiều, ngày đầu
bật tách. Cuối tệp là bấm ngẫu nhiên giữ ba bất biến: tồn lô = tổng sổ, số đã giao =
sổ ròng, tiền không hoàn hai lần.
"""

from __future__ import annotations

import asyncio

# ruff: noqa: F811 — fixture q / co được import từ CP1 / G7.
import dataclasses
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import _resolve_identity
from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.phieu_kham.hanh_trinh import dung_moc
from clinicai.services import ban_thuoc_service, lo_thuoc_service
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services import lech_kiem_ke_service as lech
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.so_no_service import so_du_hien_tai
from tests.services.test_http_quy_doi_va_thuoc_tra_db import (
    _chi_xem_kho,
    _khong_quyen,
)
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import (
    Co,
    _bat,
    _chuyen,
    _hang,
    _nhap_kho,
    _ton_noi,
    co,  # noqa: F401
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import (
    _chon,
    _dong_da_xac_dinh,
    _kd,
    _nhap_lo,
    _san_sang,
    _thu,
    _ton,
)
from tests.services.test_tien_thuoc_cp6_dinh_chinh_db import _thay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


@pytest.fixture
def _thu_gan_lo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


# ── Dựng ──────────────────────────────────────────────────────────────────


def _hom_nay() -> str:
    return hom_nay_vn().isoformat()


async def _mo(co: Co, loai: str = "DOT_XUAT", ca: str = "TOI", ngay: Any = None) -> str:
    p = await kk.mo_phieu(
        co.q.pool, identity=co.ds, ngay=ngay or _hom_nay(), ca=ca, loai=loai
    )
    return str(p["id"])


async def _dem(co: Co, pid: str, drug: str, so: Any, gio: Any = None) -> None:
    await kk.luu_dem(
        co.q.pool,
        identity=co.ds,
        phieu_id=pid,
        dong=[
            {"drug_catalog_id": drug, "don_vi": "viên", "dem": so, "dem_luc": gio},
        ],
    )


async def _chot(co: Co, pid: str) -> dict[str, Any]:
    xem = await kk.xem_lech(co.q.pool, identity=co.ds, phieu_id=pid)
    return await kk.chot(
        co.q.pool,
        identity=co.ds,
        phieu_id=pid,
        ly_do_dong=[{**d, "ly_do": "Đếm lệch thật"} for d in xem["dong"]],
    )


async def _so(co: Co, drug: str) -> dict[str, Decimal]:
    return await _ton_noi(co, drug)


async def _rx(q: Quay, rx: str) -> asyncpg.Record:
    r = await q.pool.fetchrow(
        "SELECT dispensed_qty, dispensed_at, dispensed_by_staff_id, closed_at,"
        " dispense_status FROM prescription WHERE id = $1::uuid",
        rx,
    )
    assert r is not None
    return r


async def _xuat(q: Quay, rx: str) -> list[str]:
    return [
        r["id"]
        for r in await q.pool.fetch(
            "SELECT id::text FROM inventory_txn WHERE txn_type = 'DISPENSE'"
            " AND ref_id = $1::uuid ORDER BY performed_at, id",
            rx,
        )
    ]


async def _so_dao(q: Quay, rx: str) -> Decimal:
    return D(
        str(
            await q.pool.fetchval(
                "SELECT coalesce(sum(quantity), 0) FROM inventory_txn"
                " WHERE txn_type = 'DISPENSE_REVERSAL' AND ref_id = $1::uuid",
                rx,
            )
        )
    )


async def _giao_tu_chon(q: Quay, identity: Any, rx: str, so: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).cap_phat(
        identity=identity, prescription_id=rx, drug_batch_id=None, so_luong=so
    )


async def _tra(q: Quay, xuat: str, so: Any, ket_cuc: str = "HOAN") -> dict[str, Any]:
    kw: dict[str, Any] = {"ly_do_tien": "Khách để lại"} if ket_cuc == "GIU_LAI" else {}
    return await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=xuat,
        so_luong=so,
        ly_do="Khách dị ứng",
        ket_cuc_tien=ket_cuc,
        **kw,
    )


async def _hoan_tac(q: Quay, cycle: str) -> dict[str, Any]:
    return await PaymentService(q.pool).hoan_tac(
        payment_cycle_id=cycle, ly_do="Thu nhầm hình thức", identity=q.thu_ngan
    )


async def _bat_bien_so(q: Quay, lo_ids: list[str]) -> None:
    """Tồn mỗi hàng lô = cộng dồn sổ vật lý của nó, ≥ 0."""
    for r in await q.pool.fetch(
        "SELECT b.id::text, b.quantity_on_hand,"
        " coalesce(sum(t.quantity) FILTER (WHERE t.txn_type NOT IN"
        " ('SALE', 'SALE_REVERSAL')), 0) so FROM drug_batch b"
        " LEFT JOIN inventory_txn t ON t.drug_batch_id = b.id"
        " WHERE b.id = ANY($1::uuid[]) GROUP BY b.id",
        lo_ids,
    ):
        assert r["quantity_on_hand"] == r["so"] >= 0, dict(r)


async def _bat_bien_giao(q: Quay, rx: str) -> None:
    """Số đã giao = sổ ròng + phần chờ gán lô (lần thu còn hiệu lực)."""
    r = await q.pool.fetchrow(
        """
        SELECT p.dispensed_qty,
               coalesce((SELECT -sum(t.quantity) FROM inventory_txn t
                          WHERE t.ref_id = p.id AND t.ref_type = 'prescription'
                            AND t.txn_type IN ('DISPENSE', 'DISPENSE_REVERSAL')), 0)
               + coalesce((SELECT sum(g.so_luong) FROM thuoc_giao_chua_gan_lo g
                            WHERE g.prescription_id = p.id
                              AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL), 0)
                   AS so
          FROM prescription p WHERE p.id = $1::uuid
        """,
        rx,
    )
    assert r is not None and r["dispensed_qty"] == r["so"], dict(r or {})


# ── 1. Lệch tính tại lúc đếm ──────────────────────────────────────────────


async def test_dem_50_giao_5_chot_khong_lech_gio_dem_tu_trinh_duyet(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    await _nhap_kho(co, drug, 50)
    await _thu(co.q)
    pid = await _mo(co)
    # Người đếm gõ số TRƯỚC khi giao, chỉ bấm lưu lúc chốt (sau khi giao).
    gio_go = datetime.now(CLINIC_TZ).isoformat()
    await asyncio.sleep(0.01)
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    assert (await _so(co, drug))["QUAY"] == 45
    await _dem(co, pid, drug, 50, gio_go)
    kq = await _chot(co, pid)
    d = kq["dong"][0]
    assert d["ton_may"] == 50 and d["lech"] == 0  # không tự cộng 5
    assert (await _so(co, drug))["QUAY"] == 45


async def test_dem_lai_cap_nhat_gio_cung_so_giu_gio_cu_gio_rac_ve_may_chu(
    co: Co,
) -> None:
    drug = await _thuoc_moi(co.q)
    await _nhap_kho(co, drug, 10)
    pid = await _mo(co)

    async def gio() -> Any:
        return await co.q.pool.fetchval(
            "SELECT dem_luc FROM kiem_ke_ca_dong WHERE kiem_ke_ca_id = $1::uuid", pid
        )

    await _dem(co, pid, drug, 9)
    g1 = await gio()
    assert g1 is not None
    await asyncio.sleep(0.01)
    await _dem(co, pid, drug, 9)  # màn gửi lại mọi dòng mỗi lần lưu
    assert await gio() == g1
    await _dem(co, pid, drug, 8)
    assert await gio() > g1
    await _dem(co, pid, drug, 7, "2099-01-01T00:00:00+07:00")  # tương lai
    assert (await gio()).year < 2099
    await _dem(co, pid, drug, 6, "không phải giờ")  # rác không ném
    assert await gio() is not None


async def test_dung_so_cuoi_ca_truoc_khong_tinh_lai_dieu_chinh_cua_phieu_ay(
    co: Co,
) -> None:
    drug = await _thuoc_moi(co.q)
    await _nhap_kho(co, drug, 10)
    cuoi = await _mo(co, "CUOI", "SANG")
    await _dem(co, cuoi, drug, 8)
    await _chot(co, cuoi)
    assert (await _so(co, drug))["QUAY"] == 8
    dau = await _mo(co, "DAU", "CHIEU")
    await kk.dung_so_cuoi_ca_truoc(co.q.pool, identity=co.ds, phieu_id=dau)
    d = (await _chot(co, dau))["dong"][0]
    assert d["lech"] == 0  # ADJUST của ca trước không bị coi là thuốc đi
    assert (await _so(co, drug))["QUAY"] == 8


# ── 2. Ô trống khác số 0 ──────────────────────────────────────────────────


async def test_o_trong_khong_dung_ton_so_0_that_moi_ve_0(co: Co) -> None:
    dem_0, _ = await _thuoc_ton(co, 10)
    khong_dem, _ = await _thuoc_ton(co, 10)
    bo_trong, _ = await _thuoc_ton(co, 10)
    pid = await _mo(co)
    await _dem(co, pid, dem_0, 0)
    await _dem(co, pid, bo_trong, 3)
    await _dem(co, pid, bo_trong, "")  # xoá ô = bỏ dòng, không phải số 0
    kq = await _chot(co, pid)
    assert [x["drug_catalog_id"] for x in kq["dong"]] == [dem_0]
    assert kq["mot_phan"] is True
    assert (await _so(co, dem_0))["QUAY"] == 0
    assert (await _so(co, khong_dem))["QUAY"] == 10
    assert (await _so(co, bo_trong))["QUAY"] == 10


async def _thuoc_ton(co: Co, so: int) -> tuple[str, str]:
    drug = await _thuoc_moi(co.q)
    return drug, await _nhap_kho(co, drug, so)


# ── 3. Lệch nhiều lô, phần không áp được ─────────────────────────────────


async def test_lech_am_tru_fefo_nhieu_lo_khong_xuong_duoi_0(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    som = await _nhap_kho(co, drug, 3, han=hom_nay_vn() + timedelta(days=30))
    muon = await _nhap_kho(co, drug, 10, han=hom_nay_vn() + timedelta(days=300))
    pid = await _mo(co)
    await _dem(co, pid, drug, 8)  # sổ 13, lệch −5
    await _chot(co, pid)
    assert (await _hang(co, som))["quantity_on_hand"] == 0
    assert (await _hang(co, muon))["quantity_on_hand"] == 8
    await _bat_bien_so(co.q, [som, muon])


async def test_lech_duong_quay_khong_co_lo_noi_ro_cach_xu_ly(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    await _nhap_kho(co, drug, 5)  # chỉ có hàng KHO
    pid = await _mo(co)
    await _dem(co, pid, drug, 2)
    kq = await _chot(co, pid)
    d = kq["dong"][0]
    assert d["lech"] == 2 and d["chua_ap"] == 2
    assert "chuyển lô từ kho" in d["chua_ap_ly_do"]
    assert kq["dieu_chinh_luc"] is None  # không báo đã khớp
    assert await _so(co, drug) == {"KHO": D(5), "QUAY": D(0)}


# ── 4. Số rác, chốt tranh chấp, ca cũ ─────────────────────────────────────


async def test_so_le_so_rac_so_cuc_lon(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    pid = await _mo(co)
    await _dem(co, pid, drug, "7,5")
    await _chot(co, pid)
    assert (await _hang(co, lo))["quantity_on_hand"] == D("7.5")
    p2 = await _mo(co)
    for rac in ("-1", "abc", "1e30", "NaN", "Infinity", True):
        with pytest.raises(ValidationError):
            await _dem(co, p2, drug, rac)
    for rac in ("-1", "abc", "1e30"):
        with pytest.raises(ValidationError):
            await kho.kiem_kho(
                co.q.pool,
                identity=co.ds,
                khoa_gui=uuid.uuid4().hex,
                dong=[{"drug_batch_id": lo, "thuc_te": rac, "ly_do": "x"}],
            )


async def test_hai_nguoi_chot_cung_phieu_chi_ghi_so_mot_lan(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    pid = await _mo(co)
    await _dem(co, pid, drug, 7)
    a, b = await asyncio.gather(_chot(co, pid), _chot(co, pid))
    assert sorted((a["gui_lai"], b["gui_lai"])) == [False, True]
    assert (await _hang(co, lo))["quantity_on_hand"] == 7
    c = await _chot(co, pid)  # gửi lại lệnh sau đó
    assert c["gui_lai"] is True
    assert (await _hang(co, lo))["quantity_on_hand"] == 7
    await _bat_bien_so(co.q, [lo])


async def test_dau_ca_chot_muon_sau_khi_cuoi_ca_da_dem_khong_sua_hai_lan(
    co: Co,
) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    dau = await _mo(co, "DAU", "SANG")
    await _dem(co, dau, drug, 8)
    cuoi = await _mo(co, "CUOI", "SANG")
    await _dem(co, cuoi, drug, 8)  # cùng chỗ thiếu 2
    await _chot(co, dau)
    d = (await _chot(co, cuoi))["dong"][0]
    assert d["lech"] == 0  # ADJUST của phiếu đầu ca đã sửa rồi
    assert (await _hang(co, lo))["quantity_on_hand"] == 8


async def test_chot_ca_ngay_truoc_khong_dung_ton_hom_nay(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 5)  # nhập hôm nay
    hom_qua = hom_nay_vn() - timedelta(days=1)
    await co.q.pool.execute(
        "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
        " reason, ref_type, performed_by_staff_id, performed_at) VALUES ($1::uuid,"
        " $2::uuid, 'RECEIVE', 10, 'Tồn hôm qua', 'manual', $3::uuid,"
        " now() - interval '2 days')",
        CLINIC,
        lo,
        co.ds.staff_id,
    )
    assert (await _hang(co, lo))["quantity_on_hand"] == 15
    pid = await _mo(co, "CUOI", "TOI", hom_qua.isoformat())
    await _dem(co, pid, drug, 9)  # gõ bù hôm nay, số là số tối qua
    d = (await _chot(co, pid))["dong"][0]
    assert d["ton_may"] == 10 and d["lech"] == -1  # sổ cuối ca hôm qua, không phải 15
    assert (await _hang(co, lo))["quantity_on_hand"] == 14


async def test_phieu_cu_co_lan_kiem_sau_thi_khong_ap_nua(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    cu = await _mo(co)
    await _dem(co, cu, drug, 7)  # chưa chốt
    moi = await _mo(co)
    await _dem(co, moi, drug, 9)
    await _chot(co, moi)
    assert (await _hang(co, lo))["quantity_on_hand"] == 9
    d = (await _chot(co, cu))["dong"][0]
    assert d["chua_ap"] == d["lech"] != 0
    assert "lần kiểm sau" in d["chua_ap_ly_do"]
    assert (await _hang(co, lo))["quantity_on_hand"] == 9


# ── 3b. Kiểm kho: N theo đơn vị, không còn kẹt vòng tròn ──────────────────


async def test_kiem_kho_bat_ly_do_tung_dong_hoan_tac_duoc(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)

    async def kiem(so: int, ly: Any) -> dict[str, Any]:
        return await kho.kiem_kho(
            co.q.pool,
            identity=co.ds,
            khoa_gui=uuid.uuid4().hex,
            dong=[{"drug_batch_id": lo, "thuc_te": so, "ly_do": ly}],
        )

    with pytest.raises(ValidationError, match="lý do"):
        await kiem(8, None)
    assert (await _hang(co, lo))["quantity_on_hand"] == 10
    kq = await kiem(8, "Vỡ")
    assert (await _hang(co, lo))["quantity_on_hand"] == 8
    khoa = uuid.uuid4().hex
    hoan = await kho.hoan_tac_kiem_kho(
        co.q.pool, identity=co.ds, khoa_gui=khoa, phieu_id=kq["id"]
    )
    assert (await _hang(co, lo))["quantity_on_hand"] == 10
    gui_lai = await kho.hoan_tac_kiem_kho(
        co.q.pool, identity=co.ds, khoa_gui=khoa, phieu_id=kq["id"]
    )
    assert gui_lai["id"] == hoan["id"]
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await kho.hoan_tac_kiem_kho(
            co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=kq["id"]
        )
    await _bat_bien_so(co.q, [lo])


async def test_kiem_kho_con_khac_don_vi_khong_ket_vong_tron(co: Co) -> None:
    """Giao "gói" chưa gắn lô không chặn đếm lô "viên": hai đơn vị là hai thứ."""
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await co.q.pool.execute(
        "UPDATE prescription SET unit = 'gói' WHERE id = $1::uuid", rx
    )
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)  # không có lô "gói" → chờ gán
    lo = await _nhap_kho(co, drug, 10)
    kq = await kho.kiem_kho(
        co.q.pool,
        identity=co.ds,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": lo, "thuc_te": 9, "ly_do": "Rơi vỡ"}],
    )
    assert kq["dong"][0]["lech"] == -1  # N của "gói" không tính vào "viên"
    pid = await _mo(co)
    await _dem(co, pid, drug, 9)
    assert (await _chot(co, pid))["dong"][0]["lech"] == 0


def test_tach_cho_gan_lo_uu_tien_cho_thieu_thuan() -> None:
    lo = [("a", D(5), D(5)), ("b", D(5), D(2))]
    assert kho.tach_cho_gan_lo(D(3), lo, D(0)) == {"a": D(0), "b": D(3)}
    # Không lô nào thiếu, không còn lô chưa đếm → cộng vào lô đầu để sổ = đếm + N.
    assert kho.tach_cho_gan_lo(D(3), [("a", D(5), D(5))], D(0)) == {"a": D(3)}
    # Lô chưa đếm gánh được thì phiếu không bịa lệch.
    assert kho.tach_cho_gan_lo(D(3), [("a", D(5), D(5))], D(4)) == {"a": D(0)}


async def test_man_kho_hien_so_tren_ke_khi_co_phan_cho_gan(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 4)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 4)
    await _nhap_kho(co, drug, 10)
    ton = await PharmacyService(co.q.pool).ton_kho(identity=co.ds)
    d = next(x for x in ton if x["drug_catalog_id"] == drug)
    assert d["so_tren_ke_quay"] == 6 and d["da_giao_chua_doi_chieu"] == 4


# ── 5. Hoàn tác lần thu thuốc ở mọi trạng thái ────────────────────────────


@pytest.mark.usefixtures("_thu_gan_lo")
async def test_hoan_tac_phan_lo_ve_du_va_kha_dung_dung(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=4
    )
    assert (await _ton(q, lo), await _kd(q, lo)) == (96, 90)
    kq = await _hoan_tac(q, lan)
    assert kq["status"] == "VOIDED"
    assert kq["thuoc_ve_quay"]["so_luong"] == 4
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 100)
    r = await _rx(q, rx)
    assert r["dispensed_qty"] == 0 and r["dispensed_at"] is None
    assert r["dispensed_by_staff_id"] is None
    pl = await q.pool.fetch(
        "SELECT handed_over_qty, released_at, payment_cycle_id FROM"
        " prescription_allocation WHERE prescription_id = $1::uuid ORDER BY created_at",
        rx,
    )
    assert pl[0]["handed_over_qty"] == 0 and pl[0]["released_at"] is not None
    assert pl[-1]["released_at"] is None and pl[-1]["payment_cycle_id"] is None
    await _bat_bien_so(q, [lo])
    # Thu lại rồi giao lại đúng kế hoạch lô.
    lan2 = (await _thu(q))["payment_cycle_id"]
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=10
    )
    assert (await _ton(q, lo), await _kd(q, lo)) == (90, 90)
    # Hoàn tác lần nữa: chỉ đảo lần giao mới, dòng cũ không đảo hai lần.
    await _hoan_tac(q, lan2)
    assert (await _ton(q, lo), await _kd(q, lo)) == (100, 100)
    assert await _so_dao(q, rx) == 14
    await _bat_bien_so(q, [lo])
    await _bat_bien_giao(q, rx)


async def test_hoan_tac_tu_chon_lo_va_cho_gan_lo(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    lo = await _nhap_kho(co, drug, 6)
    lan = (await _thu(co.q))["payment_cycle_id"]
    kq = await _giao_tu_chon(co.q, co.ds, rx, 10)  # 6 trừ lô, 4 chờ gán
    assert kq["chua_tru_kho"] == 4
    assert (await _so(co, drug))["QUAY"] == 0
    await _hoan_tac(co.q, lan)
    assert (await _so(co, drug))["QUAY"] == 6
    assert (await _rx(co.q, rx))["dispensed_qty"] == 0
    cho = await PharmacyService(co.q.pool).cho_gan_lo(identity=co.ds)
    assert not [x for x in cho["dong"] if x["prescription_id"] == rx]
    await _bat_bien_so(co.q, [lo])


async def test_hoan_tac_hai_lan_khong_doi_gi(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await _hoan_tac(co.q, lan)
    await _hoan_tac(co.q, lan)
    a, b = await asyncio.gather(_hoan_tac(co.q, lan), _hoan_tac(co.q, lan))
    assert a["status"] == b["status"] == "VOIDED"
    assert await _so_dao(co.q, rx) == 3
    assert (await _hang(co, lo))["quantity_on_hand"] == 5


async def test_hai_nguoi_hoan_tac_cung_luc_chi_ve_mot_lan(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await asyncio.gather(_hoan_tac(co.q, lan), _hoan_tac(co.q, lan))
    assert await _so_dao(co.q, rx) == 3
    assert (await _hang(co, lo))["quantity_on_hand"] == 5


async def test_hoan_tac_dong_da_chot_mo_lai_giao_lai_duoc(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await PharmacyService(co.q.pool).chot(identity=co.ds, prescription_id=rx)
    assert (await _rx(co.q, rx))["closed_at"] is not None
    await _hoan_tac(co.q, lan)
    assert (await _rx(co.q, rx))["closed_at"] is None
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    assert (await _so(co, drug))["QUAY"] == 2


async def test_hoan_tac_dong_bac_si_dinh_chinh_ve_quay_van_lich_su(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await _thay(co.q, rx)
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 5
    r = await co.q.pool.fetchrow(
        "SELECT dispensed_qty, removed_at FROM prescription WHERE id = $1::uuid", rx
    )
    assert r is not None and r["dispensed_qty"] == 0 and r["removed_at"] is not None
    # Sổ lịch sử vẫn chỉ cho GIẢM số giao, không cột nào khác.
    with pytest.raises(asyncpg.PostgresError, match="đính chính"):
        await co.q.pool.execute(
            "UPDATE prescription SET drug_name_raw = 'Sửa lậu' WHERE id = $1::uuid", rx
        )


async def test_hoan_tac_sau_check_out_va_ban_le_da_dong(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await co.q.pool.execute(
        "UPDATE visit SET closed_at = now(), ban_le = true WHERE visit_id = $1::uuid",
        co.q.visit_id,
    )
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 5
    assert (
        await co.q.pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", co.q.visit_id
        )
        is None
    )  # bán lẻ mở lại để thu lại được


async def test_hoan_tac_lan_thu_khach_da_check_out_luot_thuong(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await co.q.pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", co.q.visit_id
    )
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 5
    assert (await _rx(co.q, rx))["dispensed_qty"] == 0
    assert (
        await co.q.pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", co.q.visit_id
        )
        is not None
    )  # lượt thường không tự mở lại


async def test_hoan_tac_ngay_sau_khong_sua_so_ca_cu(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    pid = await _mo(co)
    await _dem(co, pid, drug, 7)
    goc = await _chot(co, pid)
    moc = datetime.now(CLINIC_TZ)
    dau_ngay = moc - timedelta(days=1)

    async def xnt() -> list[dict[str, Any]]:
        async with co.q.pool.acquire() as conn:
            return await kk.xnt_theo_ca(
                conn, clinic_id=CLINIC, location_id=co.loc, tu=dau_ngay, den=moc
            )

    truoc = await xnt()
    await asyncio.sleep(0.01)
    await _hoan_tac(co.q, lan)
    # Thuốc về quầy HÔM NAY: khoảng đã qua và phiếu đã chốt không đổi.
    sau = await xnt()
    assert [{k: v for k, v in x.items() if k != "ton_cuoi"} for x in truoc] == [
        {k: v for k, v in x.items() if k != "ton_cuoi"} for x in sau
    ]
    assert (await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=pid))["dong"] == goc[
        "dong"
    ]
    assert (await _so(co, drug))["QUAY"] == 10


async def test_lo_het_han_hoac_da_huy_het_van_nhan_thuoc_ve(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 4)
    lo = await _nhap_kho(co, drug, 4, han=hom_nay_vn() + timedelta(days=30))
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 4)
    assert (await _hang(co, lo))["quantity_on_hand"] == 0
    await co.q.pool.execute(
        "UPDATE drug_batch SET expiry_date = $2 WHERE id = $1::uuid",
        lo,
        hom_nay_vn() - timedelta(days=1),
    )
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 4  # đúng sự thật trên kệ
    await _bat_bien_so(co.q, [lo])
    # Thu lại: lô hết hạn không tự trừ, phần giao vào chờ gán lô.
    await _thu(co.q)
    kq = await _giao_tu_chon(co.q, co.ds, rx, 4)
    assert kq["chua_tru_kho"] == 4


async def test_lo_da_huy_het_van_nhan_thuoc_ve_so_van_khop(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 4)
    lo = await _nhap_kho(co, drug, 10, han=hom_nay_vn() + timedelta(days=30))
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 4)
    await PharmacyService(co.q.pool).huy(
        identity=co.ds, drug_batch_id=lo, so_luong=6, ly_do="Vỡ cả hộp"
    )
    assert (await _hang(co, lo))["quantity_on_hand"] == 0
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 4
    await _bat_bien_so(co.q, [lo])


async def test_chuyen_khoan_cho_xac_minh_khong_co_gi_de_ve(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 3)
    await _nhap_lo(q, drug, 5)
    lan = (await _thu(q, "QR"))["payment_cycle_id"]
    with pytest.raises(ConflictError):
        await _giao_tu_chon(q, q.duoc_si, rx, 3)
    xem = await PaymentService(q.pool).xem_truoc_hoan_tac(
        payment_cycle_id=lan, identity=q.thu_ngan
    )
    assert xem["phai_tra"] == 0 and xem["thuoc_ve_quay"] == 0
    assert (await _hoan_tac(q, lan))["status"] == "CANCELLED"
    assert await _so_dao(q, rx) == 0


async def test_hoa_don_cong_ty_bao_truoc_khi_hoan_tac(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    xem = await PaymentService(co.q.pool).xem_truoc_hoan_tac(
        payment_cycle_id=lan, identity=co.q.thu_ngan
    )
    assert xem["co_hoa_don_cong_ty"] is False and xem["thuoc_ve_quay"] == 3
    await co.q.pool.execute(
        "INSERT INTO hoa_don_cong_ty (clinic_id, payment_cycle_id, ten_cong_ty,"
        " ghi_boi) VALUES ($1::uuid, $2::uuid, 'Cty A', $3::uuid)",
        CLINIC,
        lan,
        co.q.thu_ngan.staff_id,
    )
    xem = await PaymentService(co.q.pool).xem_truoc_hoan_tac(
        payment_cycle_id=lan, identity=co.q.thu_ngan
    )
    assert xem["co_hoa_don_cong_ty"] is True


# ── 6. Khách trả rồi hoàn tác; tiền không hoàn hai lần ────────────────────


async def test_khach_tra_mot_phan_roi_hoan_tac_chi_ve_phan_chua_tra(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    lo = await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    [xuat] = await _xuat(co.q, rx)
    await _tra(co.q, xuat, 2, "GIU_LAI")
    assert (await _hang(co, lo))["quantity_on_hand"] == 7  # 5 + 2 trả
    await _hoan_tac(co.q, lan)
    assert await _so_dao(co.q, rx) == 3  # chỉ phần còn ở tay khách
    assert (await _hang(co, lo))["quantity_on_hand"] == 10
    assert (await _rx(co.q, rx))["dispensed_qty"] == 0
    tra = await co.q.pool.fetchrow(
        "SELECT returned_qty, disposition FROM drug_return"
        " WHERE original_dispense_txn_id = $1::uuid",
        xuat,
    )
    assert tra is not None and tra["returned_qty"] == 2 and tra["disposition"] is None
    # Thuốc trả chờ kiểm vẫn bị giữ, không lọt vào số bán được.
    assert await _kd(co.q, lo) == 8
    await _bat_bien_so(co.q, [lo])


@pytest.mark.usefixtures("_thu_gan_lo")
async def test_khach_tra_het_roi_hoan_tac_phan_lo(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 5, 10)
    lan = (await _thu(q))["payment_cycle_id"]
    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=5
    )
    [xuat] = await _xuat(q, rx)
    await _tra(q, xuat, 5, "GIU_LAI")
    kq = await _hoan_tac(q, lan)
    assert kq["thuoc_ve_quay"]["so_luong"] == 0  # phần trả đã về từ trước
    assert await _so_dao(q, rx) == 0
    assert (await _rx(q, rx))["dispensed_qty"] == 0
    assert await _ton(q, lo) == 10
    assert await _kd(q, lo) == 5  # 5 viên trả còn chờ kiểm


async def test_da_hoan_tien_roi_hoan_tac_chi_tra_phan_con_lai(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    [xuat] = await _xuat(co.q, rx)
    await _tra(co.q, xuat, 2, "HOAN")  # hoàn 2 viên tiền mặt
    svc = PaymentService(co.q.pool)
    xem = await svc.xem_truoc_hoan_tac(payment_cycle_id=lan, identity=co.q.thu_ngan)
    assert xem["da_thu"] > 0 and xem["da_hoan"] > 0
    assert xem["phai_tra"] == xem["da_thu"] - xem["da_hoan"]
    assert xem["thuoc_ve_quay"] == 3
    await _hoan_tac(co.q, lan)
    # Hoàn tác xong không còn hoàn thêm được — đã trả khách phần còn lại.
    line = await co.q.pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_type = 'prescription'",
        lan,
    )
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await HoanTienService(co.q.pool).tao(
            identity=dataclasses.replace(co.q.thu_ngan),
            payment_cycle_id=lan,
            visit_id=co.q.visit_id,
            kind="thuoc",
            dong=[{"payment_bill_line_id": line, "so_luong": 1}],
            method="CASH",
            reason="Thử hoàn lần hai",
        )
    # Đang chờ xác nhận hoàn chuyển khoản thì chưa chốt được số phải trả.


async def test_hoan_cho_xac_nhan_chan_hoan_tac(co: Co) -> None:
    _rxid, drug = await _dong_da_xac_dinh(co.q, 5)
    await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    line = await co.q.pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_type = 'prescription'",
        lan,
    )
    await HoanTienService(co.q.pool).tao(
        identity=co.q.thu_ngan,
        payment_cycle_id=lan,
        visit_id=co.q.visit_id,
        kind="thuoc",
        dong=[{"payment_bill_line_id": line, "so_luong": 1}],
        method="TRANSFER",
        reason="Khách đổi ý",
    )
    with pytest.raises(ConflictError, match="đang chờ"):
        await _hoan_tac(co.q, lan)


async def test_thu_lai_sau_hoan_tac_khong_tinh_lan_tra_cu_vao_no_khach(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    [xuat] = await _xuat(co.q, rx)
    await _tra(co.q, xuat, 2, "GIU_LAI")
    await _hoan_tac(co.q, lan)
    await co.q.pool.execute(
        "UPDATE drug_return SET disposition = 'BAN_LAI', disposition_by = $2::uuid,"
        " disposition_at = now() WHERE original_dispense_txn_id = $1::uuid",
        xuat,
        co.ds.staff_id,
    )
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    async with co.q.pool.acquire() as conn:
        du, _ = await so_du_hien_tai(
            conn, CLINIC, co.q.visit_id, datetime.now(CLINIC_TZ) + timedelta(days=2)
        )
    assert du.phai_tra == 0  # giao đủ lần thu mới, không nợ khách


# ── Nút Hoàn tác giao: tiền giữ nguyên ────────────────────────────────────


async def test_hoan_tac_giao_giu_tien_giao_lai_duoc(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    lo = await _nhap_kho(co, drug, 10)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    svc = PharmacyService(co.q.pool)
    [xuat] = await _xuat(co.q, rx)
    kq = await svc.hoan_tac_giao(
        identity=co.ds, dispense_txn_id=xuat, ly_do="Giao nhầm"
    )
    assert kq["dispensed_qty"] == 0
    assert (await _hang(co, lo))["quantity_on_hand"] == 10
    assert (
        await co.q.pool.fetchval(
            "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid", lan
        )
        == "PAID"
    )
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await svc.hoan_tac_giao(identity=co.ds, dispense_txn_id=xuat)
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await _tra(co.q, xuat, 1)
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    assert (await _hang(co, lo))["quantity_on_hand"] == 5
    await _bat_bien_so(co.q, [lo])
    await _bat_bien_giao(co.q, rx)


@pytest.mark.usefixtures("_thu_gan_lo")
async def test_hoan_tac_giao_phan_lo_giao_lai_dung_lo(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 5, 10)
    await _thu(q)
    svc = PharmacyService(q.pool)
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=5
    )
    [xuat] = await _xuat(q, rx)
    await _tra(q, xuat, 2, "GIU_LAI")
    await svc.hoan_tac_giao(identity=q.duoc_si, dispense_txn_id=xuat)
    # Đã bán 5, khách từng trả 2: phần giao lại đúng 3, không thành giao 5 lần nữa.
    assert (await _rx(q, rx))["dispensed_qty"] == 2
    assert await _so_dao(q, rx) == 3
    assert await _ton(q, lo) == 10
    await svc.cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=3
    )
    with pytest.raises(ValidationError):
        await svc.cap_phat(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
        )
    await _bat_bien_so(q, [lo])


async def test_hoan_tac_dong_cho_gan_lo_giao_lai_duoc(co: Co) -> None:
    rx, _drug = await _dong_da_xac_dinh(co.q, 3)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    svc = PharmacyService(co.q.pool)
    dong = await co.q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id = $1::uuid",
        rx,
    )
    await svc.huy_dong_cho_gan_lo(identity=co.ds, dong_id=dong)
    assert (await _rx(co.q, rx))["dispensed_qty"] == 0
    with pytest.raises(ConflictError, match="đã gán lô hoặc đã hoàn tác"):
        await svc.huy_dong_cho_gan_lo(identity=co.ds, dong_id=dong)
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await svc.gan_lo_da_giao(
            identity=co.ds, dong_id=dong, drug_batch_id=str(uuid.uuid4())
        )
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    await _bat_bien_giao(co.q, rx)


async def test_hoan_tac_giao_va_khach_tra_cung_luc_khong_vuot(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    lo = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    [xuat] = await _xuat(co.q, rx)
    kq = await asyncio.gather(
        PharmacyService(co.q.pool).hoan_tac_giao(identity=co.ds, dispense_txn_id=xuat),
        _tra(co.q, xuat, 5, "GIU_LAI"),
        return_exceptions=True,
    )
    assert sum(isinstance(x, ConflictError) for x in kq) >= 1
    assert (await _hang(co, lo))["quantity_on_hand"] == 10  # về đúng một đường
    await _bat_bien_so(co.q, [lo])


async def test_db_chan_dong_dao_sai_va_dao_hai_lan(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 5)
    lo = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 5)
    [xuat] = await _xuat(co.q, rx)

    async def dao(so: int) -> None:
        await co.q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " ref_type, ref_id, performed_by_staff_id, reverses_txn_id)"
            " VALUES ($1::uuid, $2::uuid, 'DISPENSE_REVERSAL', $3, 'prescription',"
            " $4::uuid, $5::uuid, $6::uuid)",
            CLINIC,
            lo,
            so,
            rx,
            co.ds.staff_id,
            xuat,
        )

    with pytest.raises(asyncpg.CheckViolationError, match="không khớp"):
        await dao(4)  # không đảo một phần
    await dao(5)
    with pytest.raises(asyncpg.UniqueViolationError):
        await dao(5)
    assert (await _hang(co, lo))["quantity_on_hand"] == 10


# ── 7. Sự kiện ────────────────────────────────────────────────────────────


async def test_hoan_tac_phat_su_kien_cho_hanh_trinh_va_so_no(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _nhap_kho(co, drug, 5)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    [xuat] = await _xuat(co.q, rx)
    await PharmacyService(co.q.pool).hoan_tac_giao(identity=co.ds, dispense_txn_id=xuat)
    r = await co.q.pool.fetchrow(
        "SELECT payload FROM domain_event WHERE event_type ="
        " 'medicine.dispense_undone' AND aggregate_id = $1::uuid",
        rx,
    )
    assert r is not None


def test_hanh_trinh_khong_bao_da_nhan_thuoc_sau_hoan_tac() -> None:
    t = datetime(2026, 10, 31, 8, 0, tzinfo=CLINIC_TZ)

    def moc(su_kien: list[Any]) -> dict[str, Any]:
        ds = dung_moc(
            dat_lich_luc=None,
            check_in_luc=t,
            ve_luc=None,
            su_kien=[("prescription.saved", t, {}), *su_kien],
            chi_dinh=[],
        )
        return next(x for x in ds if x["ma"] == "THUOC")

    giao = ("medicine.dispensed", t + timedelta(minutes=5), {})
    hoan = ("medicine.dispense_undone", t + timedelta(minutes=6), {"so_da_giao": "0"})
    giao_lai = ("medicine.dispensed", t + timedelta(minutes=7), {})
    assert moc([giao])["ket"] is not None
    assert moc([giao, hoan])["ket"] is None
    assert moc([giao, hoan, giao_lai])["ket"] is not None


# ── 8. Chuyển kho ─────────────────────────────────────────────────────────


async def test_quay_ve_kho_bat_ly_do_kho_ra_quay_khong_bat(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo_kho = await _nhap_kho(co, drug, 10)
    kq = await _chuyen(co, lo_kho, 4, ly_do=None)
    hang_quay = str(kq["dong"][0]["drug_batch_dich_id"])
    with pytest.raises(ValidationError, match="lý do"):
        await _chuyen(co, hang_quay, 1, "QUAY_KHO", ly_do="  ")
    await _chuyen(co, hang_quay, 1, "QUAY_KHO", ly_do="Gần hết hạn")
    assert await _so(co, drug) == {"KHO": D(7), "QUAY": D(3)}
    with pytest.raises(ConflictError, match="không đủ"):
        await _chuyen(co, hang_quay, 99, "QUAY_KHO", ly_do="Quá tồn")


async def test_lo_het_han_o_quay_ve_kho_roi_huy_co_lich_su(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    lo = await _nhap_kho(co, drug, 5)
    await _bat(co)
    await co.q.pool.execute(
        "UPDATE drug_batch SET expiry_date = $2 WHERE id = $1::uuid",
        lo,
        hom_nay_vn() - timedelta(days=3),
    )
    kq = await _chuyen(co, lo, 5, "QUAY_KHO", ly_do="Hết hạn, đưa về huỷ")
    hang_kho = str(kq["dong"][0]["drug_batch_dich_id"])
    with pytest.raises(ConflictError, match="hết hạn"):
        await _chuyen(co, hang_kho, 1)  # không cho ra quầy lại
    await lo_thuoc_service.huy_lo(
        co.q.pool,
        identity=co.ds,
        drug_batch_id=hang_kho,
        ly_do="Hết hạn",
        khoa_gui=uuid.uuid4().hex,
    )
    assert await _so(co, drug) == {"KHO": D(0), "QUAY": D(0)}
    the = await kho.the_kho(co.q.pool, identity=co.ds, drug_catalog_id=drug)
    assert {"Huỷ thuốc"} <= {x["loai_nhan"] for x in the["dong"]}
    assert {x["noi_chua"] for x in the["dong"]} == {"KHO", "QUAY"}


@pytest.mark.usefixtures("_thu_gan_lo")
async def test_quay_ve_kho_khong_rut_phan_da_ban_chua_giao(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 4)
    lo = await _nhap_kho(co, drug, 6)
    await _chon(co.q, rx, lo, 4)
    await _thu(co.q)
    await _bat(co)
    with pytest.raises(ConflictError, match="chưa giao"):
        await _chuyen(co, lo, 3, "QUAY_KHO", ly_do="Rút nhầm")
    await _chuyen(co, lo, 2, "QUAY_KHO", ly_do="Dư")


async def test_quay_ve_kho_khong_rut_thuoc_tra_cho_kiem(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 3)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    [xuat] = await _xuat(co.q, rx)
    await _tra(co.q, xuat, 2, "GIU_LAI")
    await _bat(co)
    with pytest.raises(ConflictError):
        await _chuyen(co, lo, 1, "QUAY_KHO", ly_do="Rút thuốc trả")


async def test_hai_nguoi_chuyen_nguoc_chieu_khong_khoa_cheo(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo_kho = await _nhap_kho(co, drug, 10)
    kq = await _chuyen(co, lo_kho, 5)
    quay = str(kq["dong"][0]["drug_batch_dich_id"])
    await asyncio.gather(
        *(
            _chuyen(co, lo_kho, 1)
            if i % 2
            else _chuyen(co, quay, 1, "QUAY_KHO", ly_do="Trả về")
            for i in range(6)
        )
    )
    assert await _so(co, drug) == {"KHO": D(5), "QUAY": D(5)}
    await _bat_bien_so(co.q, [lo_kho, quay])


async def test_lo_khong_han_chuyen_duoc_hai_noi_cung_so_lo_phan_biet(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    kq_nhap = await PharmacyService(co.q.pool).nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=10,
        batch_code=f"KH-{uuid.uuid4().hex[:8]}",
        expiry_date=None,
        unit="viên",
    )
    lo_kho = str(kq_nhap["drug_batch_id"])
    quay = str((await _chuyen(co, lo_kho, 4))["dong"][0]["drug_batch_dich_id"])
    a, b = await _hang(co, lo_kho), await _hang(co, quay)
    assert a["batch_code"] == b["batch_code"] and a["expiry_date"] is None
    # Kiểm đếm kho: cùng số lô, hai hàng, mỗi hàng lệch riêng.
    kq = await kho.kiem_kho(
        co.q.pool,
        identity=co.ds,
        khoa_gui=uuid.uuid4().hex,
        dong=[
            {"drug_batch_id": lo_kho, "thuc_te": 5, "ly_do": "Rơi"},
            {"drug_batch_id": quay, "thuc_te": 4},
        ],
    )
    assert {str(x["drug_batch_id"]): x["lech"] for x in kq["dong"]} == {
        lo_kho: -1,
        quay: 0,
    }
    ds = await lech.ds_lech(co.q.pool, identity=co.ds, tu=_hom_nay(), den=_hom_nay())
    d = next(x for x in ds["dong"] if x["so_lo"] == a["batch_code"])
    assert d["noi_chua"] == "KHO" and d["so_so"] == 6 and d["so_dem"] == 5


# ── 9. Ngày đầu chuyển sang tách ──────────────────────────────────────────


async def test_ngay_dau_tach_kiem_ca_chi_quay_kiem_kho_dung_noi(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    cu = await _nhap_kho(co, drug, 10)
    await _bat(co)
    moi = await _nhap_kho(co, drug, 20)
    assert (await _hang(co, cu))["noi_chua"] == "QUAY"
    assert (await _hang(co, moi))["noi_chua"] == "KHO"
    pid = await _mo(co)
    await _dem(co, pid, drug, 10)
    d = (await _chot(co, pid))["dong"][0]
    assert d["ton_may"] == 10 and d["lech"] == 0  # KHO không lẫn vào
    kq = await kho.kiem_kho(
        co.q.pool,
        identity=co.ds,
        khoa_gui=uuid.uuid4().hex,
        dong=[{"drug_batch_id": moi, "thuc_te": 19, "ly_do": "Vỡ một viên"}],
    )
    assert kq["dong"][0]["lech"] == -1
    assert await _so(co, drug) == {"KHO": D(19), "QUAY": D(10)}
    with pytest.raises(ConflictError, match="Kho còn"):
        await kho.dat_tach_kho_quay(co.q.pool, identity=co.ds, bat=False)


async def test_kiem_kho_hang_kho_khong_tach_phan_cho_gan(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _bat(co)
    lo_kho = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)  # quầy hết, kho còn → vẫn giao, chờ gán
    assert (await _rx(co.q, rx))["dispensed_qty"] == 3
    cho = await PharmacyService(co.q.pool).cho_gan_lo(identity=co.ds)
    dong = next(x for x in cho["dong"] if x["prescription_id"] == rx)
    assert {b["noi_chua"] for b in dong["lo_gan_duoc"]} == {"KHO"}
    await PharmacyService(co.q.pool).gan_lo_da_giao(
        identity=co.ds, dong_id=dong["id"], drug_batch_id=lo_kho
    )
    assert (await _so(co, drug))["KHO"] == 7


async def test_quay_het_kho_con_van_giao_gan_lo_tu_quay_sau_khi_chuyen(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 4)
    await _bat(co)
    lo_kho = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    kq = await _giao_tu_chon(co.q, co.ds, rx, 4)
    assert kq["chua_tru_kho"] == 4 and "gán lô ở kho hoặc quầy" in kq["tom_tat"]
    quay = str((await _chuyen(co, lo_kho, 6))["dong"][0]["drug_batch_dich_id"])
    dong = await co.q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id = $1::uuid",
        rx,
    )
    await PharmacyService(co.q.pool).gan_lo_da_giao(
        identity=co.ds, dong_id=dong, drug_batch_id=quay
    )
    assert await _so(co, drug) == {"KHO": D(4), "QUAY": D(2)}


# ── 4b. Báo cáo lệch, quản lý sửa số ──────────────────────────────────────


async def test_bao_cao_lech_va_sua_so_sau_cung_giu_lich_su(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    pid = await _mo(co, "CUOI", "SANG")
    await _dem(co, pid, drug, 8)
    await _chot(co, pid)
    ds = await lech.ds_lech(co.q.pool, identity=co.ds, tu=_hom_nay(), den=_hom_nay())
    d = next(x for x in ds["dong"] if x["drug_catalog_id"] == drug)
    assert (d["so_so"], d["so_dem"], d["lech"], d["so_sau_cung"]) == (10, 8, -2, 8)
    assert d["ly_do"] == "Đếm lệch thật" and d["nguoi"] and d["loai"] == "CUOI"

    async def sua(so: Any, ly: Any = "Đếm lại") -> dict[str, Any]:
        return await lech.sua_so_sau_cung(
            co.q.pool,
            identity=co.ds,
            nguon="CA",
            dong_id=d["dong_id"],
            so_moi=so,
            ly_do=ly,
        )

    with pytest.raises(ValidationError, match="lý do"):
        await sua(9, " ")
    with pytest.raises(ValidationError, match="không âm"):
        await sua("rác")
    with pytest.raises(ValidationError, match="trùng"):
        await sua(8)
    assert (await sua(9))["chenh"] == 1
    assert (await _hang(co, lo))["quantity_on_hand"] == 9
    assert (await sua(7))["chenh"] == -2  # so với số sau cùng, không phải số gốc
    assert (await _hang(co, lo))["quantity_on_hand"] == 7
    ds = await lech.ds_lech(co.q.pool, identity=co.ds, tu=_hom_nay(), den=_hom_nay())
    d = next(x for x in ds["dong"] if x["drug_catalog_id"] == drug)
    assert d["so_dem"] == 8 and d["so_sau_cung"] == 7
    assert [x["so_moi"] for x in d["lich_su_sua"]] == [9, 7]
    # Đã sửa thì không hoàn tác phiếu gốc nữa: sửa tiếp bằng dòng mới.
    with pytest.raises(ConflictError, match="sửa số sau cùng"):
        await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=pid)
    with pytest.raises(asyncpg.PostgresError, match="chỉ thêm"):
        await co.q.pool.execute(
            "UPDATE kiem_ke_sua_so SET so_moi = 1 WHERE dong_id = $1::uuid",
            d["dong_id"],
        )
    await _bat_bien_so(co.q, [lo])


async def test_bao_cao_lech_ngay_rac_khong_nem(co: Co) -> None:
    kq = await lech.ds_lech(co.q.pool, identity=co.ds, tu="rác", den="31/13/2026")
    assert kq["dong"] == [] and kq["tu"] == _hom_nay()


# ── 10. Quyền ─────────────────────────────────────────────────────────────


async def test_nguoi_chi_xem_khong_thay_nut_thu_ngan_van_hoan_tac_duoc(
    co: Co, monkeypatch: pytest.MonkeyPatch
) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    lo = await _nhap_kho(co, drug, 5)
    lan = (await _thu(co.q))["payment_cycle_id"]
    await _giao_tu_chon(co.q, co.ds, rx, 3)

    async def khong_quyen(*_a: Any, **_k: Any) -> bool:
        return False

    man = await ban_thuoc_service.man_nha_thuoc(co.q.pool, identity=co.ds)
    dong = next(d for g in man["luot"] for d in g["dong"] if d["id"] == rx)
    assert dong["xuat"][0]["thao_tac"]["hoan_tac_giao"] is True
    monkeypatch.setattr(ban_thuoc_service, "can", khong_quyen)
    man = await ban_thuoc_service.man_nha_thuoc(co.q.pool, identity=co.ds)
    dong = next(d for g in man["luot"] for d in g["dong"] if d["id"] == rx)
    assert dong["xuat"][0]["thao_tac"] == {"tra": False, "hoan_tac_giao": False}
    # Người thu không có khối Nhà thuốc vẫn hoàn tác lần thu: thuốc tự về quầy.
    await _hoan_tac(co.q, lan)
    assert (await _hang(co, lo))["quantity_on_hand"] == 5


async def test_quyen_cua_may_chu_chan_nguoi_khong_co_lego(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 3)
    await _nhap_kho(co, drug, 5)
    await _thu(co.q)
    await _giao_tu_chon(co.q, co.ds, rx, 3)
    [xuat] = await _xuat(co.q, rx)
    ai: dict[str, Any] = {"ai": await _khong_quyen(co.q.pool)}
    app.dependency_overrides[get_db_pool] = lambda: co.q.pool
    app.dependency_overrides[_resolve_identity] = lambda: ai["ai"]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://kho"
        ) as api:
            for url, than in (
                ("/api/v1/pharmacy/hoan-tac-giao", {"dispense_txn_id": xuat}),
                (
                    "/api/v1/pharmacy/sua-so-kiem-ke",
                    {"nguon": "CA", "dong_id": str(uuid.uuid4()), "so_moi": 1},
                ),
            ):
                r = await api.post(url, json=than)
                assert r.status_code == 403, (url, r.text)
            # Người chỉ xem kho: đọc được báo cáo lệch, không có nút và lệnh ghi bị 403.
            ai["ai"] = await _chi_xem_kho(co.q.pool, co.loc)
            r = await api.get(f"/api/v1/pharmacy/lech-kiem-ke?tu={_hom_nay()}")
            assert r.status_code == 200 and r.json()["sua_duoc"] is False
            r = await api.post(
                "/api/v1/pharmacy/hoan-tac-giao", json={"dispense_txn_id": xuat}
            )
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
    assert (await _rx(co.q, rx))["dispensed_qty"] == 3


async def test_migration_chay_lai_khong_doi_du_lieu(co: Co) -> None:
    drug, lo = await _thuoc_ton(co, 10)
    pid = await _mo(co)
    await _dem(co, pid, drug, 9)
    await _chot(co, pid)
    mig = (
        Path(__file__).resolve().parents[3]
        / "supabase/migrations/20261101100000_kho_quay_that.sql"
    )
    await co.q.pool.execute(mig.read_text())
    assert (await _hang(co, lo))["quantity_on_hand"] == 9


# ── Bấm ngẫu nhiên ────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(15))
async def test_bam_ngau_nhien_thu_giao_tra_hoan_tac_giu_bat_bien(
    co: Co, seed: int
) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    rx, drug = await _dong_da_xac_dinh(co.q, 6)
    lo = await _nhap_kho(co, drug, 4)
    trace: list[str] = []

    async def lan_song() -> Any:
        return await pool.fetchval(
            "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id ="
            " $1::uuid AND kind = 'thuoc' AND status = 'PAID'",
            co.q.visit_id,
        )

    for _ in range(14):
        lenh = rng.choice(
            ("thu", "giao", "giao", "tra", "hoan_giao", "hoan_cho", "void")
        )
        trace.append(lenh)
        try:
            if lenh == "thu" and not await lan_song():
                await _thu(co.q)
            elif lenh == "giao":
                await _giao_tu_chon(co.q, co.ds, rx, rng.randint(1, 3))
            elif lenh in ("tra", "hoan_giao"):
                con = await pool.fetch(
                    "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id = $1::uuid"
                    " AND t.txn_type = 'DISPENSE' AND NOT EXISTS (SELECT 1 FROM"
                    " inventory_txn x WHERE x.reverses_txn_id = t.id)",
                    rx,
                )
                if con:
                    xuat = rng.choice(con)["id"]
                    if lenh == "tra":
                        await _tra(co.q, xuat, 1, "GIU_LAI")
                    else:
                        await svc.hoan_tac_giao(identity=co.ds, dispense_txn_id=xuat)
            elif lenh == "hoan_cho":
                dong = await pool.fetchval(
                    "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id"
                    " = $1::uuid AND drug_batch_id IS NULL AND huy_luc IS NULL LIMIT 1",
                    rx,
                )
                if dong:
                    await svc.huy_dong_cho_gan_lo(identity=co.ds, dong_id=dong)
            elif lenh == "void" and (cycle := await lan_song()):
                await _hoan_tac(co.q, cycle)
                assert (await _rx(co.q, rx))["dispensed_qty"] == 0, trace
        except (ConflictError, ValidationError):
            pass
        await _bat_bien_so(co.q, [lo])
        # Không đổi tồn âm và không còn dòng bán treo sau khi không còn lần thu.
        if not await lan_song():
            assert (await _rx(co.q, rx))["dispensed_qty"] == 0, trace
    assert (await _so(co, drug))["QUAY"] <= 4 + 6, trace
