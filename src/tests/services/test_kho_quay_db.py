"""G7 — tách KHO / QUẦY: bước 0 bất biến + bấm ngẫu nhiên, rồi các ca biên.

Mọi bài chạy ở MỘT CƠ SỞ RIÊNG (is_active = false) — công tắc tách kho/quầy là
theo cơ sở, DB test dùng chung giữa các bài, bật ở cơ sở của `q` sẽ đổi hành vi
của mọi bài khác.

Bất biến (bấm ngẫu nhiên 40 hạt × 10 bước, lệnh thật):
  (1) tồn MỖI HÀNG (lô × nơi chứa) = cộng dồn sổ vật lý của hàng ấy, ≥ 0;
  (2) chỉ CHUYỂN thì tổng KHO + QUẦY của thuốc không đổi;
  (3) tổng mọi hàng của thuốc = tồn "cơ sở cũ" = cộng dồn sổ KHÔNG tính chuyển;
  (4) giao / nhận trả chỉ trên hàng QUẦY — không dòng DISPENSE nào ở KHO;
  (5) hai hàng cùng số lô là CÙNG lô: cùng thuốc, hạn, đơn vị, mã tem.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q được import từ CP1.
import dataclasses
import random
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.services import ban_thuoc_service, lo_thuoc_service
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import ma_vach_service as mv
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


@dataclasses.dataclass
class Co:
    """Quầy thử đặt ở một cơ sở riêng: `q` + người dùng ở cơ sở ấy."""

    q: Quay
    loc: str
    ds: StaffIdentity  # dược sĩ ở cơ sở riêng


@pytest_asyncio.fixture
async def co(q: Quay) -> Co:
    ma = f"TK{q.duoi}"
    loc = str(
        await q.pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Tách kho thử', false) RETURNING id::text",
            CLINIC,
            ma,
        )
    )
    # Lượt thử chuyển sang cơ sở riêng để giao thuốc ở đúng kho cơ sở ấy.
    await q.pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        loc,
    )
    ds = dataclasses.replace(q.duoc_si, location_id=loc, location_name="Tách kho thử")
    return Co(q, loc, ds)


async def _bat(co: Co) -> None:
    await kho.dat_tach_kho_quay(co.q.pool, identity=co.ds, bat=True)


async def _nhap_kho(co: Co, drug: str, so: int, **kw: Any) -> str:
    kq = await PharmacyService(co.q.pool).nhap_lo(
        identity=co.ds,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=kw.get("ma", f"LO-{uuid.uuid4().hex[:10]}"),
        expiry_date=kw.get("han", hom_nay_vn() + timedelta(days=900)),
        unit="viên",
    )
    return str(kq["drug_batch_id"])


async def _chuyen(
    co: Co, hang: str, so: Any, huong: str = "KHO_QUAY", **kw: Any
) -> dict[str, Any]:
    return await kho.chuyen_kho(
        co.q.pool,
        identity=co.ds,
        khoa_gui=kw.get("khoa", uuid.uuid4().hex),
        huong=huong,
        ly_do=kw.get("ly_do", "Quầy hết hàng"),
        dong=[{"drug_batch_id": hang, "so_luong": so}],
    )


async def _hang(co: Co, lo: str) -> Any:
    return await co.q.pool.fetchrow(
        "SELECT id::text, noi_chua, quantity_on_hand, ma_tem, batch_code, expiry_date"
        " FROM drug_batch WHERE id = $1::uuid",
        lo,
    )


async def _ton_noi(co: Co, drug: str) -> dict[str, Decimal]:
    rows = await co.q.pool.fetch(
        "SELECT noi_chua, coalesce(sum(quantity_on_hand), 0) t FROM drug_batch"
        " WHERE drug_catalog_id = $1::uuid AND location_id = $2::uuid GROUP BY 1",
        drug,
        co.loc,
    )
    return {"KHO": Decimal(0), "QUAY": Decimal(0)} | {
        r["noi_chua"]: Decimal(str(r["t"])) for r in rows
    }


def _id_dich(kq: dict[str, Any]) -> str:
    return str(kq["dong"][0]["drug_batch_dich_id"])


# ── Công tắc ─────────────────────────────────────────────────────────────


async def test_mac_dinh_tat_nhap_vao_quay_va_khong_chuyen_duoc(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    lo = await _nhap_kho(co, drug, 10)
    assert (await _hang(co, lo))["noi_chua"] == "QUAY"  # hành vi cũ: một kho
    with pytest.raises(ConflictError, match="chưa bật"):
        await _chuyen(co, lo, 1)


async def test_bat_nhap_vao_kho_quay_giu_nguyen_tat_khi_con_kho_409(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    cu = await _nhap_kho(co, drug, 10)  # trước khi bật: hàng QUẦY, bán được
    await _bat(co)
    moi = await _nhap_kho(co, drug, 7)
    assert (await _hang(co, cu))["noi_chua"] == "QUAY"
    assert (await _hang(co, moi))["noi_chua"] == "KHO"
    assert await _ton_noi(co, drug) == {"KHO": Decimal(7), "QUAY": Decimal(10)}
    with pytest.raises(ConflictError, match="còn"):
        await kho.dat_tach_kho_quay(co.q.pool, identity=co.ds, bat=False)
    await _chuyen(co, moi, 7)
    await kho.dat_tach_kho_quay(co.q.pool, identity=co.ds, bat=False)
    assert (await kho.tach_kho_quay_dang_bat(co.q.pool, co.ds)) is False


# ── Chuyển kho ───────────────────────────────────────────────────────────


async def test_chuyen_kho_quay_giu_tong_va_chia_se_ma_tem(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 20)
    kq = await _chuyen(co, kho_lo, 8)
    quay = _id_dich(kq)
    a, b = await _hang(co, kho_lo), await _hang(co, quay)
    assert (a["noi_chua"], a["quantity_on_hand"]) == ("KHO", 12)
    assert (b["noi_chua"], b["quantity_on_hand"]) == ("QUAY", 8)
    assert (a["batch_code"], a["expiry_date"], a["ma_tem"]) == (
        b["batch_code"],
        b["expiry_date"],
        b["ma_tem"],
    )
    # Chuyển tiếp lần hai vào CHÍNH hàng quầy ấy, không đẻ hàng thứ ba.
    kq2 = await _chuyen(co, kho_lo, 2)
    assert _id_dich(kq2) == quay
    assert await _ton_noi(co, drug) == {"KHO": Decimal(10), "QUAY": Decimal(10)}
    # Mỗi hàng sổ = tồn; sổ chuyển đối ứng.
    sổ = await co.q.pool.fetch(
        "SELECT txn_type, quantity, drug_batch_id::text FROM inventory_txn"
        " WHERE ref_type = 'phieu_kho' AND ref_id = $1::uuid ORDER BY txn_type",
        kq["id"],
    )
    assert [(r["txn_type"], r["quantity"]) for r in sổ] == [
        ("CHUYEN_RA", -8),
        ("CHUYEN_VAO", 8),
    ]


async def test_chuyen_khong_hop_le(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 5)
    with pytest.raises(ConflictError, match="chỉ còn"):
        await _chuyen(co, lo, 6)  # quá tồn kho
    for rac in (0, -1, "abc", "", None, float("nan"), "inf"):
        with pytest.raises(ValidationError):
            await _chuyen(co, lo, rac)
    het_han = await _nhap_kho(co, drug, 5, han=hom_nay_vn() - timedelta(days=1))
    with pytest.raises(ConflictError, match="hết hạn"):
        await _chuyen(co, het_han, 1)
    with pytest.raises(NotFoundError):
        await _chuyen(co, str(uuid.uuid4()), 1)
    with pytest.raises(ValidationError):
        await kho.chuyen_kho(
            co.q.pool,
            identity=co.ds,
            khoa_gui=uuid.uuid4().hex,
            huong="KHO_QUAY",
            ly_do="x",
            dong=[],
        )
    # Hàng QUẦY không chuyển theo chiều KHO → QUẦY.
    quay = _id_dich(await _chuyen(co, lo, 2))
    with pytest.raises(ValidationError, match="KHO"):
        await _chuyen(co, quay, 1, huong="KHO_QUAY")
    # Lần bị từ chối không để lại gì: kho 3 + 5 (lô hết hạn), quầy 2.
    assert await _ton_noi(co, drug) == {"KHO": Decimal(8), "QUAY": Decimal(2)}


async def test_chuyen_gui_lai_cung_khoa_mot_phieu(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 5)
    khoa = uuid.uuid4().hex
    a = await _chuyen(co, lo, 2, khoa=khoa)
    b = await _chuyen(co, lo, 2, khoa=khoa)
    assert b["gui_lai"] is True and b["id"] == a["id"]
    assert await _ton_noi(co, drug) == {"KHO": Decimal(3), "QUAY": Decimal(2)}


async def test_hai_co_so_khong_lan(co: Co) -> None:
    q = co.q
    drug = await _thuoc_moi(q)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 5)
    loc2 = str(
        await q.pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Tách kho thử 2', false) RETURNING id::text",
            CLINIC,
            f"TL{q.duoi}",
        )
    )
    ds2 = dataclasses.replace(q.duoc_si, location_id=loc2, location_name="Thử 2")
    await kho.dat_tach_kho_quay(q.pool, identity=ds2, bat=True)
    with pytest.raises(NotFoundError):
        await kho.chuyen_kho(
            q.pool,
            identity=ds2,
            khoa_gui=uuid.uuid4().hex,
            huong="KHO_QUAY",
            ly_do="x",
            dong=[{"drug_batch_id": lo, "so_luong": 1}],
        )
    assert await _ton_noi(co, drug) == {"KHO": Decimal(5), "QUAY": Decimal(0)}


async def test_hoan_tac_chuyen_mot_lan_va_khi_quay_da_ban_409(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 10)
    kq = await _chuyen(co, lo, 6)
    await kho.hoan_tac_chuyen(
        co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=kq["id"]
    )
    assert await _ton_noi(co, drug) == {"KHO": Decimal(10), "QUAY": Decimal(0)}
    with pytest.raises(ConflictError, match="đã hoàn tác"):
        await kho.hoan_tac_chuyen(
            co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=kq["id"]
        )
    # Quầy đã giao bớt → không rút lại phần không còn.
    kq2 = await _chuyen(co, lo, 4)
    await _thu(co.q)
    await PharmacyService(co.q.pool).cap_phat(
        identity=co.ds,
        prescription_id=rx,
        drug_batch_id=_id_dich(kq2),
        so_luong=3,
    )
    with pytest.raises(ConflictError, match="quầy"):
        await kho.hoan_tac_chuyen(
            co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=kq2["id"]
        )


async def _don(co: Co, so: int) -> tuple[str, str]:
    """Dòng đơn `so` viên của lượt (đã chuyển sang cơ sở riêng), thuốc có giá."""
    return await _dong_da_xac_dinh(co.q, so)


async def test_danh_sach_phieu_va_the_kho_hien_chuyen_kho(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 10)
    kq = await _chuyen(co, lo, 4, ly_do="Quầy sắp hết")
    ds = await kho.danh_sach_phieu(co.q.pool, identity=co.ds, loai="CHUYEN")
    p = next(x for x in ds if x["id"] == kq["id"])
    assert p["ma_phieu"].startswith("CK-") and p["huong"] == "KHO_QUAY"
    assert p["ly_do"] == "Quầy sắp hết" and p["da_hoan_tac"] is False
    assert [d["noi_chua"] for d in p["dong"]] == ["QUAY"]
    await kho.hoan_tac_chuyen(
        co.q.pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, phieu_id=kq["id"]
    )
    ds = await kho.danh_sach_phieu(co.q.pool, identity=co.ds, loai="CHUYEN")
    assert next(x for x in ds if x["id"] == kq["id"])["da_hoan_tac"] is True
    the = await kho.the_kho(co.q.pool, identity=co.ds, drug_catalog_id=drug)
    nhan = {d["loai_nhan"] for d in the["dong"]}
    assert {"Chuyển kho (ra)", "Chuyển kho (vào)"} <= nhan


# ── Bán / giao chỉ ở QUẦY ────────────────────────────────────────────────


async def test_giao_tu_kho_bi_chan_o_dich_vu_va_o_db(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 10)
    await _thu(co.q)
    svc = PharmacyService(co.q.pool)
    with pytest.raises(ConflictError, match="KHO"):
        await svc.cap_phat(
            identity=co.ds, prescription_id=rx, drug_batch_id=kho_lo, so_luong=1
        )
    # Chốt cuối ở DB: ghi thẳng sổ DISPENSE vào hàng KHO bị trigger từ chối.
    with pytest.raises(asyncpg.PostgresError, match="đang ở KHO"):
        await co.q.pool.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " ref_type, ref_id, performed_by_staff_id)"
            " VALUES ($1::uuid, $2::uuid, 'DISPENSE', -1, 'prescription', $3::uuid,"
            " $4::uuid)",
            CLINIC,
            kho_lo,
            rx,
            co.ds.staff_id,
        )
    assert (await _hang(co, kho_lo))["quantity_on_hand"] == 10
    # Chuyển sang quầy rồi giao được.
    quay = _id_dich(await _chuyen(co, kho_lo, 4))
    await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=quay, so_luong=3
    )
    assert await _ton_noi(co, drug) == {"KHO": Decimal(6), "QUAY": Decimal(1)}


async def test_quay_het_ma_kho_con_hien_goi_y_chuyen(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 9)

    async def dong() -> Any:
        man = await ban_thuoc_service.man_nha_thuoc(co.q.pool, identity=co.ds)
        return next(d for lt in man["luot"] for d in lt["dong"] if d["id"] == rx)

    d = await dong()
    assert d["lo_goi_y"] == []  # quầy hết → không bán được
    assert [k["drug_batch_id"] for k in d["kho_con"]] == [kho_lo]
    assert d["kho_con"][0]["ton"] == 9
    quay = _id_dich(await _chuyen(co, kho_lo, 5))
    d = await dong()
    assert [x["drug_batch_id"] for x in d["lo_goi_y"]] == [quay]
    assert [k["ton"] for k in d["kho_con"]] == [4]


async def test_khach_tra_thuoc_ve_quay_khong_ve_kho(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 10)
    quay = _id_dich(await _chuyen(co, kho_lo, 5))
    await _thu(co.q)
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=quay, so_luong=3
    )
    txn = await co.q.pool.fetchval(
        "SELECT id::text FROM inventory_txn WHERE ref_id = $1::uuid"
        " AND txn_type = 'DISPENSE'",
        rx,
    )
    await svc.khach_tra_thuoc(
        identity=co.ds,
        dispense_txn_id=txn,
        so_luong=2,
        ly_do="Khách trả",
        ket_cuc_tien="GIU_LAI",
        ly_do_tien="Kho/quầy — tiền giữ lại",
    )
    assert await _ton_noi(co, drug) == {"KHO": Decimal(5), "QUAY": Decimal(4)}


async def test_giao_khong_lo_van_chay_va_gan_lo_chi_ve_quay(co: Co) -> None:
    rx, drug = await _don(co, 2)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 10)
    quay = _id_dich(await _chuyen(co, kho_lo, 5))
    await _thu(co.q)
    svc = PharmacyService(co.q.pool)
    await svc.cap_phat(
        identity=co.ds, prescription_id=rx, drug_batch_id=None, so_luong=2
    )
    dong = await co.q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id=$1::uuid",
        rx,
    )
    with pytest.raises(ConflictError, match="KHO"):
        await svc.gan_lo_da_giao(identity=co.ds, dong_id=dong, drug_batch_id=kho_lo)
    cho = await svc.cho_gan_lo(identity=co.ds)
    goi_y = next(d for d in cho["dong"] if d["id"] == dong)["lo_gan_duoc"]
    assert [x["drug_batch_id"] for x in goi_y] == [quay]  # chỉ hàng quầy
    await svc.gan_lo_da_giao(identity=co.ds, dong_id=dong, drug_batch_id=quay)
    assert await _ton_noi(co, drug) == {"KHO": Decimal(5), "QUAY": Decimal(3)}


# ── Một lô, hai hàng ─────────────────────────────────────────────────────


async def test_sua_lo_cap_nhat_ca_hai_hang_va_huy_theo_tung_hang(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    han = hom_nay_vn() - timedelta(days=2)
    kho_lo = await _nhap_kho(co, drug, 10, han=hom_nay_vn() + timedelta(days=5))
    quay = _id_dich(await _chuyen(co, kho_lo, 4))
    await lo_thuoc_service.sua_lo(
        co.q.pool,
        identity=co.ds,
        drug_batch_id=quay,
        batch_code="LO-DOI-" + uuid.uuid4().hex[:6],
        expiry_date=han,
    )
    a, b = await _hang(co, kho_lo), await _hang(co, quay)
    assert (a["batch_code"], a["expiry_date"]) == (b["batch_code"], b["expiry_date"])
    # Hết hạn: huỷ từng hàng, mỗi hàng ghi một dòng DISCARD riêng.
    for lo in (kho_lo, quay):
        await lo_thuoc_service.huy_lo(
            co.q.pool,
            identity=co.ds,
            drug_batch_id=lo,
            ly_do="Hết hạn",
            khoa_gui=str(uuid.uuid4()),
        )
    assert await _ton_noi(co, drug) == {"KHO": Decimal(0), "QUAY": Decimal(0)}


async def test_tem_tra_ve_hang_quay_kem_so_con_o_kho(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 10)
    tem = (await _hang(co, kho_lo))["ma_tem"]
    # Chưa có hàng quầy: tem ra hàng KHO, báo "chưa ở quầy".
    kq = await mv.tra_ma(co.q.pool, identity=co.ds, ma=tem)
    assert kq["lo"]["noi_chua"] == "KHO"
    quay = _id_dich(await _chuyen(co, kho_lo, 3))
    kq = await mv.tra_ma(co.q.pool, identity=co.ds, ma=tem)
    assert kq["lo"]["id"] == quay and kq["lo"]["noi_chua"] == "QUAY"
    assert kq["lo"]["kho_con"] == 7
    # Gợi ý FEFO để bán chỉ có hàng quầy.
    async with co.q.pool.acquire() as conn:
        goi_y = await mv.goi_y_lo(conn, co.ds, drug)
    assert [x["id"] for x in goi_y] == [quay]


async def test_hai_hang_khac_hang_nhau_thi_db_tu_choi(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 10)
    await _chuyen(co, kho_lo, 3)
    with pytest.raises(asyncpg.PostgresError, match="khác thuốc, hạn"):
        await co.q.pool.execute(
            "UPDATE drug_batch SET expiry_date = expiry_date + 1 WHERE id = $1::uuid",
            kho_lo,
        )


async def test_nhap_cung_so_lo_khac_hang_bi_chan_nhu_cu(co: Co) -> None:
    drug, khac = await _thuoc_moi(co.q), await _thuoc_moi(co.q)
    await _bat(co)
    kho_lo = await _nhap_kho(co, drug, 5, ma="LO-CHUNG")
    await _chuyen(co, kho_lo, 2)
    with pytest.raises(ConflictError, match="thuốc khác"):
        await _nhap_kho(co, khac, 5, ma="LO-CHUNG")
    # Nhập thêm đúng lô đó (cùng hạn): cộng vào hàng KHO sẵn có.
    han = (await _hang(co, kho_lo))["expiry_date"]
    cung = await _nhap_kho(co, drug, 4, ma="LO-CHUNG", han=han)
    assert cung == kho_lo
    assert await _ton_noi(co, drug) == {"KHO": Decimal(7), "QUAY": Decimal(2)}


# ── Bấm ngẫu nhiên ───────────────────────────────────────────────────────


async def _bat_bien(co: Co, thuoc: list[str], trace: tuple[str, ...]) -> None:
    pool = co.q.pool
    for r in await pool.fetch(
        "SELECT b.id::text, b.quantity_on_hand,"
        " coalesce(sum(t.quantity) FILTER (WHERE t.txn_type = ANY($2::text[])), 0) so"
        " FROM drug_batch b LEFT JOIN inventory_txn t ON t.drug_batch_id = b.id"
        " WHERE b.drug_catalog_id = ANY($1::uuid[]) GROUP BY b.id",
        thuoc,
        list(kho.LOAI_VAT_LY),
    ):
        assert r["quantity_on_hand"] == r["so"] >= 0, (dict(r), trace)  # (1)
    for d in thuoc:  # (3)
        tong = await pool.fetchval(
            "SELECT coalesce(sum(quantity_on_hand), 0) FROM drug_batch"
            " WHERE drug_catalog_id = $1::uuid",
            d,
        )
        so_cu = await pool.fetchval(
            "SELECT coalesce(sum(t.quantity), 0) FROM inventory_txn t JOIN drug_batch b"
            " ON b.id = t.drug_batch_id WHERE b.drug_catalog_id = $1::uuid"
            " AND t.txn_type = ANY($2::text[])",
            d,
            [x for x in kho.LOAI_VAT_LY if not x.startswith("CHUYEN")],
        )
        assert tong == so_cu, (d, tong, so_cu, trace)
    sai = await pool.fetchval(  # (4)
        "SELECT count(*) FROM inventory_txn t JOIN drug_batch b"
        " ON b.id = t.drug_batch_id"
        " WHERE b.drug_catalog_id = ANY($1::uuid[]) AND b.noi_chua = 'KHO'"
        " AND t.txn_type IN ('DISPENSE', 'RETURN_RECEIVED', 'SALE')",
        thuoc,
    )
    assert sai == 0, trace
    lech = await pool.fetchval(  # (5)
        "SELECT count(*) FROM drug_batch a JOIN drug_batch b ON a.clinic_id=b.clinic_id"
        " AND a.location_id=b.location_id AND a.batch_code=b.batch_code AND a.id<>b.id"
        " WHERE a.drug_catalog_id = ANY($1::uuid[]) AND (a.ma_tem<>b.ma_tem"
        " OR a.expiry_date IS DISTINCT FROM b.expiry_date OR a.unit<>b.unit)",
        thuoc,
    )
    assert lech == 0, trace


@pytest.mark.parametrize("seed", range(40))
async def test_bam_ngau_nhien_kho_quay_40_luot_10_buoc(co: Co, seed: int) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    await _bat(co)
    rx, drug0 = await _don(co, 10)
    thuoc = [drug0, await _thuoc_moi(co.q)]
    await _thu(co.q)
    kho_dau = [await _nhap_kho(co, d, 30) for d in thuoc]
    await _nhap_kho(co, thuoc[0], 5, han=hom_nay_vn() - timedelta(days=1))
    # Mở đầu bắt buộc: quầy có sẵn 12 viên thuốc kê để các bước giao / trả có việc.
    chuyen_cuoi: list[str] = [(await _chuyen(co, kho_dau[0], 12))["id"]]
    trace: tuple[str, ...] = ()

    async def hang_co_ton(noi: str) -> list[str]:
        return [
            r["id"]
            for r in await pool.fetch(
                "SELECT id::text FROM drug_batch WHERE noi_chua = $1 AND"
                " drug_catalog_id = ANY($2::uuid[]) AND location_id = $3::uuid"
                " AND quantity_on_hand > 0 ORDER BY id",
                noi,
                thuoc,
                co.loc,
            )
        ]

    for buoc in range(10):
        lenh = rng.choice(
            (
                "nhap",
                "chuyen_ra",
                "chuyen_ra",
                "quay_tra_kho",
                "giao",
                "tra",
                "huy",
                "kiem",
                "dieu_chinh",
                "hoan_tac",
            )
        )
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        truoc = [await _ton_noi(co, d) for d in thuoc]
        chi_chuyen = lenh in ("chuyen_ra", "quay_tra_kho", "hoan_tac")
        try:
            try:
                if lenh == "nhap":
                    await _nhap_kho(co, rng.choice(thuoc), rng.randint(1, 5))
                elif lenh == "chuyen_ra":
                    ds = await hang_co_ton("KHO")
                    if ds:
                        kq = await _chuyen(co, rng.choice(ds), rng.randint(1, 4))
                        chuyen_cuoi.append(kq["id"])
                elif lenh == "quay_tra_kho":
                    ds = await hang_co_ton("QUAY")
                    if ds:
                        kq = await _chuyen(
                            co, rng.choice(ds), rng.randint(1, 3), huong="QUAY_KHO"
                        )
                        chuyen_cuoi.append(kq["id"])
                elif lenh == "giao":
                    cho = []
                    for x in await hang_co_ton("QUAY"):
                        h = await pool.fetchrow(
                            "SELECT drug_catalog_id::text AS d, expiry_date"
                            " FROM drug_batch WHERE id = $1::uuid",
                            x,
                        )
                        if h["d"] == drug0 and (
                            h["expiry_date"] is None or h["expiry_date"] >= hom_nay_vn()
                        ):
                            cho.append(x)
                    if cho:
                        await svc.cap_phat(
                            identity=co.ds,
                            prescription_id=rx,
                            drug_batch_id=rng.choice(cho),
                            so_luong=1,
                        )
                elif lenh == "tra":
                    txn = await pool.fetchval(
                        "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id=$1::uuid"
                        " AND t.txn_type='DISPENSE' AND NOT EXISTS (SELECT 1 FROM"
                        " drug_return r WHERE r.original_dispense_txn_id = t.id)"
                        " LIMIT 1",
                        rx,
                    )
                    if txn:
                        await svc.khach_tra_thuoc(
                            identity=co.ds,
                            dispense_txn_id=txn,
                            so_luong=1,
                            ly_do="Khách trả mô phỏng",
                        )
                elif lenh == "huy":
                    ds = await hang_co_ton("KHO") + await hang_co_ton("QUAY")
                    if ds:
                        await svc.huy(
                            identity=co.ds,
                            drug_batch_id=rng.choice(ds),
                            so_luong=1,
                            ly_do="Mô phỏng",
                        )
                elif lenh == "kiem":
                    ds = await hang_co_ton("KHO") + await hang_co_ton("QUAY")
                    if ds:
                        lo = rng.choice(ds)
                        ton = Decimal(str((await _hang(co, lo))["quantity_on_hand"]))
                        await kho.kiem_kho(
                            pool,
                            identity=co.ds,
                            khoa_gui=uuid.uuid4().hex,
                            dong=[
                                {
                                    "drug_batch_id": lo,
                                    "thuc_te": ton + rng.randint(-1, 2),
                                }
                            ],
                        )
                elif lenh == "dieu_chinh":
                    ds = await hang_co_ton("KHO") + await hang_co_ton("QUAY")
                    if ds:
                        await svc.dieu_chinh(
                            identity=co.ds,
                            drug_batch_id=rng.choice(ds),
                            so_luong=rng.choice((-1, 1, 2)),
                            ly_do="Điều chỉnh mô phỏng",
                        )
                elif lenh == "hoan_tac" and chuyen_cuoi:
                    await kho.hoan_tac_chuyen(
                        pool,
                        identity=co.ds,
                        khoa_gui=uuid.uuid4().hex,
                        phieu_id=chuyen_cuoi.pop(rng.randrange(len(chuyen_cuoi))),
                    )
            except (ConflictError, ValidationError):
                pass  # luật từ chối bằng tiếng Việt là kết quả đúng, không phải lỗi
            sau = [await _ton_noi(co, d) for d in thuoc]
            if chi_chuyen:  # (2)
                assert [sum(x.values()) for x in truoc] == [
                    sum(x.values()) for x in sau
                ], trace
            await _bat_bien(co, thuoc, trace)
        except Exception as exc:
            pytest.fail(f"Chuỗi gây lỗi: {trace!r}\n{type(exc).__name__}: {exc}")
    # Bài không rỗng: sổ có dòng chuyển và (thường) có giao từ quầy.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM inventory_txn t JOIN drug_batch b"
            " ON b.id = t.drug_batch_id WHERE b.location_id = $1::uuid"
            " AND t.txn_type = 'CHUYEN_VAO'",
            co.loc,
        )
        >= 1
    )
