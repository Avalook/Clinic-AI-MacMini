"""G6 — kiểm kê đầu / cuối ca ở QUẦY: bất biến + bấm ngẫu nhiên, rồi các ca biên.

Mỗi bài chạy ở MỘT CƠ SỞ RIÊNG (fixture `co` của G7) để số liệu không lẫn với bài
khác trong DB dùng chung.

Bất biến (bấm ngẫu nhiên 40 hạt × 10 bước, lệnh thật):
  (1) tồn MỖI lô = cộng dồn sổ vật lý của nó, ≥ 0;
  (2) mở / lưu số đếm / chốt kiểm kê KHÔNG đổi tồn (chỉ "điều chỉnh" mới đổi);
  (3) lệch của dòng đã chốt = đếm − tồn máy, và tồn máy = tồn quầy đúng lúc chốt;
  (4) điều chỉnh xong thì tồn quầy của dòng ấy = số đếm; hoàn tác trả đúng tồn cũ;
  (5) XNT theo ca: tồn cuối = đầu + nhập − bán + trả + khác và = tồn hiện tại.
"""

from __future__ import annotations

import asyncio

# ruff: noqa: F811 — fixture q / co được import từ CP1 / G7.
import inspect
import random
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.events.catalogue import CHUONG
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.pharmacy_service import PharmacyService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import Co, _nhap_kho, co  # noqa: F401
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _san_sang, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _hom_nay() -> str:
    return hom_nay_vn().isoformat()


async def _mo(co: Co, loai: str = "CUOI", ca: str = "TOI") -> dict[str, Any]:
    return await kk.mo_phieu(
        co.q.pool, identity=co.ds, ngay=_hom_nay(), ca=ca, loai=loai
    )


async def _dem(co: Co, pid: str, **theo_thuoc: Any) -> dict[str, Any]:
    """`theo_thuoc`: drug_id → số đếm (đơn vị 'viên')."""
    return await kk.luu_dem(
        co.q.pool,
        identity=co.ds,
        phieu_id=pid,
        dong=[
            {"drug_catalog_id": d, "don_vi": "viên", "dem": v}
            for d, v in theo_thuoc.items()
        ],
    )


async def _ton(co: Co, drug: str) -> Decimal:
    return D(
        str(
            await co.q.pool.fetchval(
                "SELECT coalesce(sum(quantity_on_hand), 0) FROM drug_batch WHERE"
                " drug_catalog_id = $1::uuid AND location_id = $2::uuid"
                " AND noi_chua = 'QUAY'",
                drug,
                co.loc,
            )
        )
    )


async def _thuoc_co_ton(co: Co, so: int = 10) -> tuple[str, str]:
    drug = await _thuoc_moi(co.q)
    lo = await _nhap_kho(co, drug, so)
    return drug, lo


# ── Mở phiếu ─────────────────────────────────────────────────────────────


async def test_hai_nguoi_mo_cung_ca_chi_mot_phieu(co: Co) -> None:
    a = await _mo(co, "DAU", "SANG")
    b = await _mo(co, "DAU", "SANG")
    assert a["id"] == b["id"] and a["moi_mo"] is True and b["moi_mo"] is False
    # Ép ở Postgres, không chỉ ở Python: chèn thẳng cùng khoá bị từ chối.
    with pytest.raises(asyncpg.UniqueViolationError):
        await co.q.pool.execute(
            "INSERT INTO kiem_ke_ca (clinic_id, location_id, ngay, ca, loai, tao_boi)"
            " SELECT clinic_id, location_id, ngay, ca, loai, tao_boi FROM kiem_ke_ca"
            " WHERE id = $1::uuid",
            a["id"],
        )


async def test_dot_xuat_mo_nhieu_phieu(co: Co) -> None:
    a = await _mo(co, "DOT_XUAT", "SANG")
    b = await _mo(co, "DOT_XUAT", "SANG")
    assert a["id"] != b["id"]


async def test_mo_phieu_rac_thi_422_khong_ghi(co: Co) -> None:
    hn = _hom_nay()
    rac = [
        ("không phải ngày", "SANG", "DAU"),
        ("", "SANG", "DAU"),
        (None, "SANG", "DAU"),
        ("2001-01-01", "SANG", "DAU"),
        ("2999-01-01", "SANG", "DAU"),
        (hn, "KHUYA", "DAU"),
        (hn, None, "DAU"),
        (hn, "SANG", "NHAM"),
        (hn, "SANG", None),
    ]
    truoc = await co.q.pool.fetchval(
        "SELECT count(*) FROM kiem_ke_ca WHERE location_id = $1::uuid", co.loc
    )
    for ngay, ca, loai in rac:
        with pytest.raises(ValidationError):
            await kk.mo_phieu(co.q.pool, identity=co.ds, ngay=ngay, ca=ca, loai=loai)
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM kiem_ke_ca WHERE location_id = $1::uuid", co.loc
        )
        == truoc
    )


# ── Số đếm ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rac", ["abc", "-1", -5, "nan", "1e30", "inf", True])
async def test_dem_rac_thi_422_va_khong_ghi_dong_nao(co: Co, rac: Any) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    with pytest.raises(ValidationError):
        await kk.luu_dem(
            co.q.pool,
            identity=co.ds,
            phieu_id=p["id"],
            dong=[
                {"drug_catalog_id": drug, "don_vi": "viên", "dem": 5},  # hợp lệ
                {"drug_catalog_id": drug, "don_vi": "hộp", "dem": rac},  # rác
            ],
        )
    # Cả lệnh bị từ chối: dòng hợp lệ đi cùng cũng KHÔNG được ghi.
    assert (await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=p["id"]))[
        "dong"
    ] == []


async def test_dem_ma_phieu_va_thuoc_rac(co: Co) -> None:
    with pytest.raises(ValidationError):
        await kk.luu_dem(co.q.pool, identity=co.ds, phieu_id="x", dong=[])
    p = await _mo(co)
    with pytest.raises(ValidationError):
        await _dem(co, p["id"], **{"không-phải-uuid": 1})
    with pytest.raises(NotFoundError):
        await _dem(co, p["id"], **{str(uuid.uuid4()): 1})
    with pytest.raises(NotFoundError):
        await kk.luu_dem(
            co.q.pool,
            identity=co.ds,
            phieu_id=str(uuid.uuid4()),
            dong=[{"drug_catalog_id": str(uuid.uuid4()), "don_vi": "viên", "dem": 1}],
        )


async def test_dem_ghi_de_va_bo_dong(co: Co) -> None:
    d1, _ = await _thuoc_co_ton(co)
    d2, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{d1: 4, d2: 6})
    ph = await _dem(co, p["id"], **{d1: "7", d2: None})  # ghi đè d1, bỏ d2
    assert {x["drug_catalog_id"]: x["dem"] for x in ph["dong"]} == {d1: D(7)}


# ── Chốt ─────────────────────────────────────────────────────────────────


async def test_chot_ghi_ton_may_va_lech_nhung_khong_doi_ton(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co, 10)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 8})
    truoc = await _ton(co, drug)
    kq = await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    d = kq["dong"][0]
    assert d["ton_may"] == D(10) and d["dem"] == D(8) and d["lech"] == D(-2)
    assert kq["trang_thai"] == "CHOT" and kq["mot_phan"] is False
    assert await _ton(co, drug) == truoc == D(10)  # (2) chưa tự sửa tồn
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn t JOIN drug_batch b ON b.id ="
            " t.drug_batch_id WHERE b.drug_catalog_id = $1::uuid AND t.txn_type ="
            " 'ADJUST'",
            drug,
        )
        == 0
    )


async def test_chot_lech_phat_su_kien_chuong_va_khong_lech_thi_khong(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co, 5)
    ok = await _mo(co, "DAU", "SANG")
    await _dem(co, ok["id"], **{drug: 5})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=ok["id"])
    sai = await _mo(co, "CUOI", "SANG")
    await _dem(co, sai["id"], **{drug: 4})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=sai["id"])
    ev = {
        str(r["aggregate_id"])
        for r in await co.q.pool.fetch(
            "SELECT aggregate_id FROM domain_event WHERE event_type ="
            " 'pharmacy.stocktake_mismatch' AND aggregate_id = ANY($1::uuid[])",
            [ok["id"], sai["id"]],
        )
    }
    assert ev == {sai["id"]}


async def test_lech_rung_chuong_cho_vai_da_chon_khong_lech_thi_im(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co, 5)
    ok = await _mo(co, "DAU", "CHIEU")
    await _dem(co, ok["id"], **{drug: 5})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=ok["id"])
    sai = await _mo(co, "CUOI", "CHIEU")
    await _dem(co, sai["id"], **{drug: 3})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=sai["id"])
    await chay_ben_nhan(co.q.pool, CHUONG)
    chuong = await co.q.pool.fetch(
        "SELECT vai_nhan, nguoi_goi_staff_id::text AS nguoi, duong_dan, noi_dung,"
        " nguon_id FROM thong_bao WHERE nguon = 'kiem_ke_ca' AND nguon_id = ANY($1)",
        [ok["id"], sai["id"]],
    )
    assert {c["nguon_id"] for c in chuong} == {sai["id"]}
    assert {c["vai_nhan"] for c in chuong} >= {"MANAGEMENT"}
    assert all(c["nguoi"] == str(co.ds.staff_id) for c in chuong)
    assert all(c["duong_dan"] == "/pharmacy/inventory" for c in chuong)
    assert "1 thuốc lệch" in chuong[0]["noi_dung"]


async def test_chot_roi_khong_sua_duoc_va_chot_lan_hai_tra_lai(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    with pytest.raises(ValidationError):  # chưa đếm gì
        await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    await _dem(co, p["id"], **{drug: 10})
    a = await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    b = await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    assert a["gui_lai"] is False and b["gui_lai"] is True
    assert a["chot_luc"] == b["chot_luc"]
    with pytest.raises(ConflictError):
        await _dem(co, p["id"], **{drug: 1})
    # Ép ở Postgres: sửa thẳng dòng / phiếu đã chốt bị từ chối.
    with pytest.raises(asyncpg.PostgresError, match="đã chốt"):
        await co.q.pool.execute(
            "UPDATE kiem_ke_ca_dong SET dem = 99 WHERE kiem_ke_ca_id = $1::uuid",
            p["id"],
        )
    with pytest.raises(asyncpg.PostgresError, match="đã chốt"):
        await co.q.pool.execute(
            "UPDATE kiem_ke_ca SET ca = 'SANG' WHERE id = $1::uuid", p["id"]
        )


async def test_chot_o_co_so_khac_khong_thay_phieu(co: Co) -> None:
    import dataclasses

    p = await _mo(co)
    nguoi_khac = dataclasses.replace(co.ds, location_id=str(uuid.uuid4()))
    with pytest.raises(NotFoundError):
        await kk.doc_phieu(co.q.pool, identity=nguoi_khac, phieu_id=p["id"])


async def test_ban_giua_luc_dem_ton_may_la_tai_gio_chot(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})  # đếm lúc còn 10
    lo = await co.q.pool.fetchval(
        "SELECT id::text FROM drug_batch WHERE drug_catalog_id = $1::uuid"
        " AND location_id = $2::uuid AND noi_chua = 'QUAY'",
        drug,
        co.loc,
    )
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=3
    )  # bán 3 giữa lúc đếm và chốt
    kq = await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    assert kq["dong"][0]["ton_may"] == D(7)  # tồn máy ĐÚNG GIỜ CHỐT
    assert kq["dong"][0]["lech"] == D(2)


async def test_kiem_mot_phan_va_day_du(co: Co) -> None:
    a, _ = await _thuoc_co_ton(co)
    b, _ = await _thuoc_co_ton(co)
    p1 = await _mo(co, "DOT_XUAT")
    await _dem(co, p1["id"], **{a: 10})
    assert (await kk.chot(co.q.pool, identity=co.ds, phieu_id=p1["id"]))["mot_phan"]
    p2 = await _mo(co, "DOT_XUAT")
    await _dem(co, p2["id"], **{a: 10, b: 10})
    assert not (await kk.chot(co.q.pool, identity=co.ds, phieu_id=p2["id"]))["mot_phan"]


async def test_giao_chua_gan_lo_hien_rieng_khong_tinh_lech(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=4
    )  # giao không lô: sổ chưa trừ
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 6})  # kệ thật còn 6
    d = (await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"]))["dong"][0]
    ton_truoc = await co.q.pool.fetchval(
        "SELECT sum(quantity_on_hand) FROM drug_batch WHERE drug_catalog_id=$1::uuid",
        drug,
    )
    with pytest.raises(ConflictError, match="tránh trừ kho hai lần"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm thử"
        )
    assert (
        await co.q.pool.fetchval(
            "SELECT sum(quantity_on_hand) FROM drug_batch "
            "WHERE drug_catalog_id=$1::uuid",
            drug,
        )
        == ton_truoc
    )
    assert d["giao_chua_gan_lo"] == D(4)
    assert d["ton_may"] == D(10) and d["lech"] == D(
        -4
    )  # lệch số học; cột riêng giải thích


# ── Dùng số cuối ca trước làm đầu ca ─────────────────────────────────────


async def test_dung_so_cuoi_ca_truoc(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co, 10)
    cuoi = await _mo(co, "CUOI", "SANG")
    await _dem(co, cuoi["id"], **{drug: 10})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=cuoi["id"])
    dau = await _mo(co, "DAU", "CHIEU")
    kq = await kk.dung_so_cuoi_ca_truoc(co.q.pool, identity=co.ds, phieu_id=dau["id"])
    assert kq["dung_so_ca_truoc"] is True
    assert [x["dem"] for x in kq["dong"]] == [D(10)]
    with pytest.raises(ConflictError):  # không phải phiếu đầu ca
        await kk.dung_so_cuoi_ca_truoc(co.q.pool, identity=co.ds, phieu_id=cuoi["id"])
    sang = await _mo(co, "DAU", "SANG")  # trước phiếu cuối ca SÁNG nên không có gì
    with pytest.raises(ConflictError):
        await kk.dung_so_cuoi_ca_truoc(co.q.pool, identity=co.ds, phieu_id=sang["id"])


# ── Điều chỉnh theo kiểm kê (bước riêng, hoàn tác được) ───────────────────


async def test_dieu_chinh_dua_ton_ve_so_dem_va_hoan_tac(co: Co) -> None:
    thieu, _ = await _thuoc_co_ton(co, 10)
    thua, _ = await _thuoc_co_ton(co, 10)
    p = await _mo(co)
    await _dem(co, p["id"], **{thieu: 7, thua: 12})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    with pytest.raises(ValidationError):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="  "
        )
    kq = await kk.dieu_chinh_theo_kiem_ke(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm lại cuối ca"
    )
    assert kq["bo_qua"] == []
    assert await _ton(co, thieu) == D(7) and await _ton(co, thua) == D(12)
    with pytest.raises(ConflictError):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Lần hai"
        )
    ph = await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=p["id"])
    assert ph["dieu_chinh_ly_do"] == "Đếm lại cuối ca" and ph["nguoi_dieu_chinh"]
    await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=p["id"])
    assert await _ton(co, thieu) == D(10) and await _ton(co, thua) == D(10)
    with pytest.raises(ConflictError):
        await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=p["id"])
    # Sổ chỉ thêm: điều chỉnh + hoàn tác = hai dòng ADJUST mỗi thuốc, tổng 0.
    so = await co.q.pool.fetchval(
        "SELECT coalesce(sum(t.quantity), 0) FROM inventory_txn t JOIN drug_batch b"
        " ON b.id = t.drug_batch_id WHERE b.drug_catalog_id = ANY($1::uuid[])"
        " AND t.txn_type = 'ADJUST'",
        [thieu, thua],
    )
    assert so == 0


async def test_dieu_chinh_truoc_chot_va_khong_lech_bi_tu_choi(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 10})
    with pytest.raises(ConflictError, match="chốt"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="x"
        )
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    with pytest.raises(ConflictError, match="lệch"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="x"
        )


async def test_dieu_chinh_tru_het_ton_thi_bao_phan_bo_qua(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    lo = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 4})  # lệch −6 theo tồn 10
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=8
    )  # bán 8 → quầy còn 2, ít hơn phần cần trừ 6
    kq = await kk.dieu_chinh_theo_kiem_ke(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Thiếu thật"
    )
    assert await _ton(co, drug) == D(0)
    assert (
        kq["bo_qua"] and kq["bo_qua"][0]["con_thieu"] == 4.0
    )  # nói rõ, không cắt lặng


async def test_hoan_tac_khong_duoc_khi_phan_da_cong_them_bi_xuat_het(co: Co) -> None:
    drug, lo = await _thuoc_co_ton(co, 10)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 13})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    await kk.dieu_chinh_theo_kiem_ke(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Thừa thật"
    )  # quầy 13
    await PharmacyService(co.q.pool).huy(
        identity=co.ds, drug_batch_id=lo, so_luong=12, ly_do="Vỡ"
    )  # còn 1 < 3 đã cộng
    with pytest.raises(ConflictError, match="Không hoàn tác"):
        await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=p["id"])
    assert await _ton(co, drug) == D(1)  # không trừ dở


# ── Nhắc, danh sách ──────────────────────────────────────────────────────


async def test_nhac_thieu_kiem_khong_chan_ban(co: Co) -> None:
    n = await kk.nhac_thieu_kiem(co.q.pool, identity=co.ds, ngay=_hom_nay(), ca="CHIEU")
    assert n["thieu_dau_ca"] is True and n["thieu_cuoi_ca_truoc"] is True
    rac = await kk.nhac_thieu_kiem(co.q.pool, identity=co.ds, ngay="rác", ca="rác")
    assert rac["ca"] in ("SANG", "CHIEU", "TOI")  # không ném
    drug, _ = await _thuoc_co_ton(co)
    for loai, ca in (("DAU", "CHIEU"), ("CUOI", "SANG")):
        p = await _mo(co, loai, ca)
        await _dem(co, p["id"], **{drug: 10})
        await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    n = await kk.nhac_thieu_kiem(co.q.pool, identity=co.ds, ngay=_hom_nay(), ca="CHIEU")
    assert n["thieu_dau_ca"] is False and n["thieu_cuoi_ca_truoc"] is False


async def test_danh_sach_dem_dong_va_lech(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    ds = await kk.danh_sach(co.q.pool, identity=co.ds, ngay=_hom_nay())
    assert ds[0]["so_dong"] == 1 and ds[0]["so_lech"] == 1
    assert await kk.danh_sach(co.q.pool, identity=co.ds, ngay="rác")  # rác = không lọc


# ── XNT theo ca và báo cáo hàng hoá ──────────────────────────────────────


def _cua_so(co: Co) -> tuple[Any, Any]:
    from datetime import datetime

    from clinicai.core.clock import CLINIC_TZ

    h = hom_nay_vn()
    tu = datetime(h.year, h.month, h.day, tzinfo=CLINIC_TZ)
    return tu, tu + timedelta(days=2)


async def _xnt(co: Co, drug: str) -> list[dict[str, Any]]:
    tu, den = _cua_so(co)
    async with co.q.pool.acquire() as conn:
        rows = await kk.xnt_theo_ca(
            conn,
            clinic_id=co.ds.clinic_id,
            location_id=co.loc,
            tu=tu,
            den=den,
        )
    return [r for r in rows if r["drug_catalog_id"] == drug]


async def test_xnt_theo_ca_dong_nhat_thuc(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    lo = await _nhap_kho(co, drug, 20)
    await _thu(co.q)
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=6)
    await svc.dieu_chinh(identity=co.ds, drug_batch_id=lo, so_luong=-1, ly_do="Vỡ")
    (r,) = await _xnt(co, drug)
    assert (r["ton_dau"], r["nhap"], r["ban"], r["tra"], r["khac"]) == (
        D(0),
        D(20),
        D(6),
        D(0),
        D(-1),
    )
    assert r["ton_cuoi"] == r["ton_dau"] + r["nhap"] - r["ban"] + r["tra"] + r["khac"]
    assert r["ton_cuoi"] == await _ton(co, drug) == D(13)


async def test_bao_cao_hang_hoa_them_khoi_kho_khong_doi_so_tien(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")  # thu = SALE
    # Luồng thật: quầy giữ lô cho đơn → thu tiền (SALE) → giao một phần (DISPENSE).
    # Dùng quầy mặc định `q` vì thu tiền gắn với cơ sở của thu ngân; chỉ đọc thuốc MỚI.
    rx, drug, lo = await _san_sang(q, so=10, ton=20)
    await _thu(q)
    ds = q.duoc_si
    await PharmacyService(q.pool).cap_phat(
        identity=ds, prescription_id=rx, drug_batch_id=lo, so_luong=4
    )
    p = await kk.mo_phieu(q.pool, identity=ds, ngay=_hom_nay(), ca="TOI", loai="CUOI")
    await kk.luu_dem(
        q.pool,
        identity=ds,
        phieu_id=p["id"],
        dong=[{"drug_catalog_id": drug, "don_vi": "viên", "dem": 15}],
    )
    await kk.chot(q.pool, identity=ds, phieu_id=p["id"])
    bc = await BaoCaoCuoiNgayService(q.pool).bao_cao(
        identity=ds, tu=_hom_nay(), den=_hom_nay(), loai="thuoc"
    )
    thuoc = bc["hang_hoa"]["thuoc"]
    d = next(x for x in thuoc["dong"] if x["khoa"] == drug)
    assert d["sl_ban"] == 10.0 and d["doanh_thu"] > 0  # số THU cũ nguyên vẹn
    k = d["kho"]["theo_don_vi"][0]
    assert (k["nhap"], k["sl_ban"], k["ton_cuoi"]) == (20.0, 4.0, 16.0)
    assert k["kiem_ke"] == 15.0 and k["lech"] == -1.0
    assert k["da_thu_chua_giao"] == 6.0  # đã thu 10, giao 4 → còn 6 chưa giao
    assert thuoc["co_ton"] is True


async def test_bao_cao_dich_vu_khong_co_khoi_kho(co: Co) -> None:
    bc = await BaoCaoCuoiNgayService(co.q.pool).bao_cao(
        identity=co.ds, tu=_hom_nay(), den=_hom_nay(), loai="dich_vu", co_so=co.loc
    )
    assert all("kho" not in d for d in bc["hang_hoa"]["dich_vu"]["dong"])
    assert "co_ton" not in bc["hang_hoa"]["thuoc"]


# ── Bấm ngẫu nhiên ───────────────────────────────────────────────────────


async def _tra_thuoc(svc: PharmacyService, co: Co, txn: str) -> None:
    kw: dict[str, Any] = {}
    if "ket_cuc_tien" in inspect.signature(svc.khach_tra_thuoc).parameters:
        kw["ket_cuc_tien"] = "HOAN"  # luật R3 #430: bắt buộc chọn kết cục tiền
    await svc.khach_tra_thuoc(
        identity=co.ds,
        dispense_txn_id=txn,
        so_luong=1,
        ly_do="Khách trả mô phỏng",
        **kw,
    )


async def _bat_bien(co: Co, thuoc: list[str], trace: tuple[str, ...]) -> None:
    pool = co.q.pool
    for r in await pool.fetch(
        "SELECT b.id::text, b.quantity_on_hand,"
        " coalesce(sum(t.quantity) FILTER (WHERE t.txn_type = ANY($2::text[])), 0) so"
        " FROM drug_batch b LEFT JOIN inventory_txn t ON t.drug_batch_id = b.id"
        " WHERE b.drug_catalog_id = ANY($1::uuid[]) GROUP BY b.id",
        thuoc,
        [
            "RECEIVE",
            "DISPENSE",
            "ADJUST",
            "DISCARD",
            "RETURN_RECEIVED",
            "CHUYEN_RA",
            "CHUYEN_VAO",
        ],
    ):
        assert r["quantity_on_hand"] == r["so"] >= 0, (dict(r), trace)  # (1)
    for d in thuoc:  # (5)
        for x in await _xnt(co, d):
            assert x["ton_cuoi"] == (
                x["ton_dau"] + x["nhap"] - x["ban"] + x["tra"] + x["khac"]
            ), (x, trace)
            assert x["ton_cuoi"] == await _ton(co, d), (x, trace)


@pytest.mark.parametrize("seed", range(40))
async def test_bam_ngau_nhien_kiem_ke_ca_40_luot_10_buoc(co: Co, seed: int) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    rx, drug0 = await _dong_da_xac_dinh(co.q, 10)
    thuoc = [drug0, await _thuoc_moi(co.q)]
    await _thu(co.q)
    for d in thuoc:
        await _nhap_kho(co, d, 30)
    da_chot: list[str] = []  # phiếu đã chốt, chưa điều chỉnh
    da_dieu_chinh: list[tuple[str, dict[str, Decimal]]] = []
    phieu_nhap: str | None = None
    trace: tuple[str, ...] = ()

    async def ton_ca() -> dict[str, Decimal]:
        return {d: await _ton(co, d) for d in thuoc}

    for buoc in range(10):
        lenh = rng.choice(
            (
                "nhap",
                "giao",
                "tra",
                "huy",
                "dieu_chinh_thuong",
                "mo_dem",
                "chot",
                "dieu_chinh_kk",
                "hoan_tac_kk",
                "mo_dem",
            )
        )
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        truoc = await ton_ca()
        chi_kiem = lenh in ("mo_dem", "chot")
        try:
            try:
                if lenh == "nhap":
                    await _nhap_kho(co, rng.choice(thuoc), rng.randint(1, 5))
                elif lenh == "giao":
                    lo = await pool.fetchval(
                        "SELECT id::text FROM drug_batch WHERE drug_catalog_id ="
                        " $1::uuid AND location_id = $2::uuid AND quantity_on_hand > 0"
                        " AND (expiry_date IS NULL OR expiry_date >= current_date)"
                        " ORDER BY id LIMIT 1",
                        drug0,
                        co.loc,
                    )
                    if lo:
                        await svc.cap_phat(
                            identity=co.ds,
                            prescription_id=rx,
                            drug_batch_id=lo,
                            so_luong=1,
                        )
                elif lenh == "tra":
                    txn = await pool.fetchval(
                        "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id ="
                        " $1::uuid AND t.txn_type = 'DISPENSE' AND NOT EXISTS"
                        " (SELECT 1 FROM drug_return r WHERE"
                        " r.original_dispense_txn_id = t.id) LIMIT 1",
                        rx,
                    )
                    if txn:
                        await _tra_thuoc(svc, co, txn)
                elif lenh in ("huy", "dieu_chinh_thuong"):
                    lo = await pool.fetchval(
                        "SELECT id::text FROM drug_batch WHERE drug_catalog_id ="
                        " ANY($1::uuid[]) AND location_id = $2::uuid AND"
                        " quantity_on_hand > 0 ORDER BY id LIMIT 1",
                        thuoc,
                        co.loc,
                    )
                    if lo and lenh == "huy":
                        await svc.huy(
                            identity=co.ds, drug_batch_id=lo, so_luong=1, ly_do="Vỡ"
                        )
                    elif lo:
                        await svc.dieu_chinh(
                            identity=co.ds,
                            drug_batch_id=lo,
                            so_luong=rng.choice((-1, 1, 2)),
                            ly_do="Mô phỏng",
                        )
                elif lenh == "mo_dem":
                    p = await kk.mo_phieu(
                        pool,
                        identity=co.ds,
                        ngay=_hom_nay(),
                        ca=rng.choice(("SANG", "CHIEU", "TOI")),
                        loai=rng.choice(("DAU", "CUOI", "DOT_XUAT")),
                    )
                    phieu_nhap = p["id"]
                    if p["trang_thai"] == "NHAP":
                        chon = rng.sample(thuoc, rng.randint(1, len(thuoc)))
                        await kk.luu_dem(
                            pool,
                            identity=co.ds,
                            phieu_id=p["id"],
                            dong=[
                                {
                                    "drug_catalog_id": d,
                                    "don_vi": "viên",
                                    "dem": (await _ton(co, d)) + rng.randint(-2, 2)
                                    if rng.random() < 0.8
                                    else rng.randint(0, 40),
                                }
                                for d in chon
                            ],
                        )
                elif lenh == "chot" and phieu_nhap:
                    ton_luc_chot = await ton_ca()
                    kq = await kk.chot(pool, identity=co.ds, phieu_id=phieu_nhap)
                    for x in kq["dong"]:  # (3)
                        assert x["ton_may"] == ton_luc_chot[x["drug_catalog_id"]], trace
                        assert x["lech"] == x["dem"] - x["ton_may"], trace
                    if not kq["gui_lai"] and kq["dieu_chinh_luc"] is None:
                        da_chot.append(phieu_nhap)
                    phieu_nhap = None
                elif lenh == "dieu_chinh_kk" and da_chot:
                    pid = da_chot.pop(rng.randrange(len(da_chot)))
                    ph = await kk.doc_phieu(pool, identity=co.ds, phieu_id=pid)
                    cu = await ton_ca()
                    kq = await kk.dieu_chinh_theo_kiem_ke(
                        pool, identity=co.ds, phieu_id=pid, ly_do="Mô phỏng"
                    )
                    sau = await ton_ca()
                    bo = {(b["drug_catalog_id"]) for b in kq["bo_qua"]}
                    for x in ph["dong"]:  # (4)
                        if x["lech"] and x["drug_catalog_id"] not in bo:
                            assert (
                                sau[x["drug_catalog_id"]]
                                == cu[x["drug_catalog_id"]] + x["lech"]
                            ), (x, cu, sau, trace)
                    da_dieu_chinh.append((pid, cu))
                elif lenh == "hoan_tac_kk" and da_dieu_chinh:
                    pid, cu = da_dieu_chinh.pop()
                    await kk.hoan_tac_dieu_chinh(pool, identity=co.ds, phieu_id=pid)
            except (ConflictError, ValidationError):
                pass  # luật từ chối bằng tiếng Việt là kết quả đúng, không phải lỗi
            sau = await ton_ca()
            if chi_kiem:  # (2)
                assert truoc == sau, trace
            await _bat_bien(co, thuoc, trace)
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM kiem_ke_ca WHERE location_id = $1::uuid", co.loc
        )
        >= 0
    )


async def test_sua_so_dem_giu_snapshot_va_bao_cao_chi_ban_da_chot(co: Co) -> None:
    drug, _lo = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})
    goc = await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    with pytest.raises(ValidationError, match="lý do"):
        await kk.sua_so_dem(co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do=" ")
    ban_sua = await kk.sua_so_dem(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm nhầm"
    )
    assert ban_sua["phieu_truoc_id"] == p["id"] and ban_sua["phien_ban"] == 2
    assert (
        await kk.sua_so_dem(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Gọi lại"
        )
    )["id"] == ban_sua["id"]
    assert (await _mo(co))["id"] == ban_sua["id"]
    async with co.q.pool.acquire() as conn:
        k = await kk.kiem_trong_khoang(
            conn,
            clinic_id=co.ds.clinic_id,
            location_id=co.loc,
            tu_ngay=hom_nay_vn(),
            den_ngay=hom_nay_vn(),
        )
    assert k[(drug, "viên", "CUOI")]["dem"] == D(9)
    # Hàng về sau chốt không đổi nền tồn của lần đếm đã đính chính.
    await _nhap_kho(co, drug, 3)
    await _dem(co, ban_sua["id"], **{drug: 8})
    moi = await kk.chot(co.q.pool, identity=co.ds, phieu_id=ban_sua["id"])
    assert moi["dong"][0]["ton_may"] == D(10)
    assert moi["dong"][0]["lech"] == D(-2)
    assert await _ton(co, drug) == D(13)
    assert (await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=p["id"]))[
        "dong"
    ] == goc["dong"]
    async with co.q.pool.acquire() as conn:
        k = await kk.kiem_trong_khoang(
            conn,
            clinic_id=co.ds.clinic_id,
            location_id=co.loc,
            tu_ngay=hom_nay_vn(),
            den_ngay=hom_nay_vn(),
        )
    assert k[(drug, "viên", "CUOI")]["dem"] == D(8)
    with pytest.raises(ConflictError, match="bản sửa"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Không dùng bản cũ"
        )


async def test_sua_so_dem_bat_hoan_tac_va_khong_tru_hai_lan(co: Co) -> None:
    drug, _lo = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 8})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    await kk.dieu_chinh_theo_kiem_ke(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Thiếu"
    )
    assert await _ton(co, drug) == D(8)
    with pytest.raises(ConflictError, match="Hoàn tác"):
        await kk.sua_so_dem(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm nhầm"
        )
    await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=p["id"])
    ban_sua = await kk.sua_so_dem(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm lại"
    )
    await _dem(co, ban_sua["id"], **{drug: 9})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=ban_sua["id"])
    await kk.dieu_chinh_theo_kiem_ke(
        co.q.pool, identity=co.ds, phieu_id=ban_sua["id"], ly_do="Đúng 9"
    )
    assert await _ton(co, drug) == D(9)
    await kk.hoan_tac_dieu_chinh(co.q.pool, identity=co.ds, phieu_id=ban_sua["id"])
    assert await _ton(co, drug) == D(10)


async def test_sua_so_dem_chan_thuoc_moi_va_khac_co_so(co: Co) -> None:
    drug, _lo = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    from dataclasses import replace

    with pytest.raises(NotFoundError):
        await kk.sua_so_dem(
            co.q.pool,
            identity=replace(co.ds, location_id=str(uuid.uuid4())),
            phieu_id=p["id"],
            ly_do="Khác cơ sở",
        )
    sua = await kk.sua_so_dem(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Đếm nhầm"
    )
    drug2, _lo2 = await _thuoc_co_ton(co)
    with pytest.raises(ValidationError, match="chỉ sửa thuốc đã đếm"):
        await _dem(co, sua["id"], **{drug2: 3})


async def test_pending_moi_sau_chot_chan_dieu_chinh(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=2
    )
    with pytest.raises(ConflictError, match="tránh trừ kho hai lần"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Chưa rõ nguồn"
        )
    assert await _ton(co, drug) == D(10)


async def test_sua_so_dem_dong_thoi_chi_mot_ban(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 9})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    a, b = await asyncio.gather(
        *(
            kk.sua_so_dem(
                co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Nhập nhầm"
            )
            for _ in range(2)
        )
    )
    assert a["id"] == b["id"]


async def test_snapshot_pending_van_chan_sau_gan_lo(co: Co) -> None:
    rx, drug = await _dong_da_xac_dinh(co.q, 10)
    lo = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    svc = PharmacyService(co.q.pool)
    giao = await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=2
    )
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 8})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    dong = await co.q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id=$1::uuid", rx
    )
    await svc.gan_lo_da_giao(identity=co.ds, dong_id=dong, drug_batch_id=lo)
    with pytest.raises(ConflictError, match="tránh trừ kho hai lần"):
        await kk.dieu_chinh_theo_kiem_ke(
            co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Không trừ lại"
        )
    assert giao
    assert await _ton(co, drug) == D(8)


async def test_migration_dinh_chinh_chay_lai_khong_mat_du_lieu(co: Co) -> None:
    drug, _ = await _thuoc_co_ton(co)
    p = await _mo(co)
    await _dem(co, p["id"], **{drug: 10})
    await kk.chot(co.q.pool, identity=co.ds, phieu_id=p["id"])
    sua = await kk.sua_so_dem(
        co.q.pool, identity=co.ds, phieu_id=p["id"], ly_do="Thử migration"
    )
    migration = (
        Path(__file__).resolve().parents[3]
        / "supabase/migrations/20261018120000_kiem_ke_ca_dinh_chinh.sql"
    )
    await co.q.pool.execute(migration.read_text())
    assert (await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=sua["id"]))[
        "phien_ban"
    ] == 2
    assert (await kk.doc_phieu(co.q.pool, identity=co.ds, phieu_id=p["id"]))["dong"][0][
        "dem"
    ] == D(10)
