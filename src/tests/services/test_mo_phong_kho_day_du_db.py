"""Mô phỏng ĐẦY ĐỦ kho thuốc: bấm ngẫu nhiên MỌI thao tác, sau MỖI bước so
các màn báo cáo với đáp án tính LẠI từ sổ gốc `inventory_txn`.

`test_kho_quay_db` đã bấm ngẫu nhiên (chuyển kho, giao, trả, huỷ, kiểm, điều
chỉnh) nhưng chỉ kiểm TỒN. `test_doi_chieu_kho_thuoc_db` so báo cáo với sổ nhưng
chưa có chuyển kho / giao không lô / kiểm kê ca. File này nối hai bên: một chuỗi
thao tác đủ loại, rồi sau mỗi bước:

  R1  tồn mỗi lô = cộng dồn sổ vật lý, ≥ 0 (bất biến của `test_kho_quay_db`);
  R2  Xuất–nhập–tồn (cả kho + quầy) = đáp án độc lập, từng thuốc × đơn vị;
  R3  Tồn theo ca (chỉ quầy) = đáp án độc lập (có tính CHUYỂN vào/ra);
  R4  Thẻ kho: tồn sau của dòng mới nhất = tồn hiện tại; tồn theo đơn vị khớp;
  R5  "Giao chưa gắn lô" của báo cáo = cộng các lần giao chưa gắn lô;
  R6  Giao không chỉ định lô: máy tự chọn lô, chỉ được ghi DISPENSE âm của đơn đó;
  R7  Số đã giao của đơn = số trừ ở lô + số chờ gán lô (không mất, không đếm hai lần).

Cuối mỗi hạt: kiểm kê ca đủ vòng (mở → đếm → chốt → điều chỉnh → hoàn tác):
lệch = đếm − tồn máy, điều chỉnh đưa tồn QUẦY về số đếm, hoàn tác trả đúng tồn cũ.

Mọi thay đổi gọi service thật; SQL chỉ đọc sổ.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import asyncio
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_doi_chieu_kho_thuoc_db import khop
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import (
    Co,
    _bat,
    _bat_bien,
    _chuyen,
    _don,
    _hang,
    _nhap_kho,
    co,  # noqa: F401
)
from tests.services.test_kiem_ke_ca_db import _tra_thuoc
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal

_VL = kho.LOAI_VAT_LY


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _hom_nay_iso() -> str:
    return hom_nay_vn().isoformat()


def _cua_so_ca() -> tuple[datetime, datetime]:
    h = hom_nay_vn()
    tu = datetime(h.year, h.month, h.day, tzinfo=CLINIC_TZ)
    return tu, tu + timedelta(days=2)


# ── Đáp án độc lập ───────────────────────────────────────────────────────

_COT_XNT = ("ton_dau", "nhap", "xuat", "dieu_chinh", "huy", "tra_lai", "ton_cuoi")


async def dap_an_xnt(co: Co, drug: str) -> dict[str, dict[str, Decimal]]:
    """(đơn vị → 7 cột) của cả KHO + QUẦY ở cơ sở, từ sổ gốc. Cửa sổ = hôm nay."""
    h = hom_nay_vn()
    moc_dau = datetime(h.year, h.month, h.day, tzinfo=CLINIC_TZ)
    moc_cuoi = moc_dau + timedelta(days=1)
    rows = await co.q.pool.fetch(
        "SELECT lower(btrim(b.unit)) AS dv, t.txn_type, t.quantity, t.performed_at"
        " FROM inventory_txn t JOIN drug_batch b ON b.id = t.drug_batch_id"
        " WHERE b.drug_catalog_id = $1::uuid AND b.location_id = $2::uuid",
        drug,
        co.loc,
    )
    ra: dict[str, dict[str, Decimal]] = {}
    for r in rows:
        if r["txn_type"] not in _VL:
            continue
        o = ra.setdefault(r["dv"], {c: D(0) for c in _COT_XNT})
        so = D(str(r["quantity"]))
        t = r["performed_at"]
        if t < moc_dau:
            o["ton_dau"] += so
        if t < moc_cuoi:
            o["ton_cuoi"] += so
        if not moc_dau <= t < moc_cuoi:
            continue
        loai = r["txn_type"]
        if loai == "RECEIVE":
            o["nhap"] += so
        elif loai == "DISPENSE":
            o["xuat"] -= so
        elif loai == "ADJUST":
            o["dieu_chinh"] += so
        elif loai == "DISCARD":
            o["huy"] -= so
        elif loai == "RETURN_RECEIVED":
            o["tra_lai"] += so
        # CHUYEN_RA / CHUYEN_VAO: chỉ đổi tồn từng hàng, không có cột riêng.
    return {dv: o for dv, o in ra.items() if any(o.values())}


async def kiem_xnt(co: Co, thuoc: list[str], dau: str) -> None:
    """R2: màn Xuất–nhập–tồn = sổ gốc; và đẳng thức cột (chuyển kho tự triệt tiêu)."""
    kq = await kho.xuat_nhap_ton(
        co.q.pool, identity=co.ds, tu=_hom_nay_iso(), den=_hom_nay_iso()
    )
    for d in thuoc:
        thuc = {
            str(r["don_vi"]).lower().strip(): {c: D(str(r[c])) for c in _COT_XNT}
            for r in kq["dong"]
            if r["drug_catalog_id"] == d and any(D(str(r[c])) for c in _COT_XNT)
        }
        an = await dap_an_xnt(co, d)
        assert thuc == an, f"{dau}\n  XNT màn={thuc}\n  sổ gốc={an}"
        for dv, o in an.items():
            assert (
                o["ton_dau"]
                + o["nhap"]
                - o["xuat"]
                + o["dieu_chinh"]
                - o["huy"]
                + o["tra_lai"]
                == o["ton_cuoi"]
            ), f"{dau}: cột {dv} không cộng ra tồn cuối {o}"


async def kiem_the_kho(co: Co, thuoc: list[str], dau: str) -> None:
    """R4: thẻ kho khớp tồn hiện tại, riêng từng đơn vị; lịch sử cộng ra đúng tồn."""
    for d in thuoc:
        the = await kho.the_kho(co.q.pool, identity=co.ds, drug_catalog_id=d)
        ton = {
            r["dv"]: D(str(r["t"]))
            for r in await co.q.pool.fetch(
                "SELECT lower(btrim(unit)) dv, sum(quantity_on_hand) t FROM drug_batch"
                " WHERE drug_catalog_id = $1::uuid AND location_id = $2::uuid"
                " GROUP BY 1",
                d,
                co.loc,
            )
            if D(str(r["t"])) != 0
        }
        theo_dv: dict[str, list[dict[str, Any]]] = {}
        for r in the["dong"]:  # mới nhất trước
            theo_dv.setdefault(str(r["don_vi"]).lower().strip(), []).append(r)
        for dv, ds in theo_dv.items():
            assert D(str(ds[0]["ton_sau"])) == ton.get(dv, D(0)), (
                f"{dau}: thẻ kho {dv} tồn sau {ds[0]['ton_sau']} ≠ {ton.get(dv)}"
            )
            assert D(str(ds[-1]["ton_truoc"])) == 0, (
                f"{dau}: lịch sử không bắt đầu từ 0"
            )
            for moi, cu in zip(ds, ds[1:], strict=False):
                assert D(str(cu["ton_sau"])) == D(str(moi["ton_truoc"])), (
                    f"{dau}: thẻ kho đứt mạch giữa hai dòng {dv}"
                )
        on_man = {
            str(x["don_vi"]).lower().strip(): D(str(x["ton"]))
            for x in the["thuoc"]["ton_theo_don_vi"]
        }
        assert on_man == ton, f"{dau}: tồn theo đơn vị màn={on_man} ≠ {ton}"


async def kiem_giao_chua_gan_lo(co: Co, thuoc: list[str], dau: str) -> None:
    """R5: báo cáo "giao chưa gắn lô" = cộng các lần giao còn trống lô."""
    async with co.q.pool.acquire() as conn:
        bc = await kk.giao_chua_gan_lo_theo_thuoc(
            conn, clinic_id=co.ds.clinic_id, location_id=co.loc
        )
    for d in thuoc:
        so = await co.q.pool.fetchval(
            "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo"
            " WHERE drug_catalog_id = $1::uuid AND drug_batch_id IS NULL"
            " AND clinic_id = $2::uuid",
            d,
            co.ds.clinic_id,
        )
        assert D(str(bc.get(d, 0))) == D(str(so)), f"{dau}: giao chưa gắn lô {d}"


async def kiem_tat_ca(co: Co, thuoc: list[str], trace: tuple[str, ...]) -> None:
    dau = " | ".join(trace)
    await _bat_bien(co, thuoc, trace)  # R1
    await kiem_xnt(co, thuoc, dau)  # R2
    tu, den = _cua_so_ca()
    for d in thuoc:
        await khop(co, d, tu, den, dau=dau)  # R3
    await kiem_the_kho(co, thuoc, dau)  # R4
    await kiem_giao_chua_gan_lo(co, thuoc, dau)  # R5


# ── Vòng kiểm kê ca ──────────────────────────────────────────────────────


async def _ton_quay(co: Co, drug: str) -> Decimal:
    return D(
        str(
            await co.q.pool.fetchval(
                "SELECT coalesce(sum(quantity_on_hand), 0) FROM drug_batch"
                " WHERE drug_catalog_id = $1::uuid AND location_id = $2::uuid"
                " AND noi_chua = 'QUAY' AND lower(btrim(unit)) = 'viên'",
                drug,
                co.loc,
            )
        )
    )


async def vong_kiem_ke(co: Co, thuoc: list[str], rng: random.Random, dau: str) -> None:
    """Mở → đếm → chốt (lệch = đếm − tồn máy) → điều chỉnh → hoàn tác."""
    pool = co.q.pool
    p = await kk.mo_phieu(
        pool, identity=co.ds, ngay=_hom_nay_iso(), ca="TOI", loai="CUOI"
    )
    dem = {d: max(D(0), await _ton_quay(co, d) + rng.randint(-2, 2)) for d in thuoc}
    await kk.luu_dem(
        pool,
        identity=co.ds,
        phieu_id=p["id"],
        dong=[
            {"drug_catalog_id": d, "don_vi": "viên", "dem": v} for d, v in dem.items()
        ],
    )
    truoc = {d: await _ton_quay(co, d) for d in thuoc}
    kq = await kk.chot(pool, identity=co.ds, phieu_id=p["id"])
    for r in kq["dong"]:
        d = r["drug_catalog_id"]
        assert D(str(r["ton_may"])) == truoc[d], f"{dau}: tồn máy chốt sai"
        assert D(str(r["lech"])) == dem[d] - truoc[d], f"{dau}: lệch sai"
    assert {d: await _ton_quay(co, d) for d in thuoc} == truoc, (
        "chốt không được sửa tồn"
    )
    if not any(dem[d] != truoc[d] for d in thuoc):
        return
    try:
        dc = await kk.dieu_chinh_theo_kiem_ke(
            pool, identity=co.ds, phieu_id=p["id"], ly_do="Mô phỏng"
        )
    except ConflictError:
        return  # không còn lệch áp được: luật từ chối đúng
    bo_qua = {
        str(x.get("drug_catalog_id") or x.get("thuoc")) for x in dc.get("bo_qua", [])
    }
    sau = {d: await _ton_quay(co, d) for d in thuoc}
    for d in thuoc:
        if d in bo_qua:
            continue
        assert sau[d] == dem[d], (
            f"{dau}: sau điều chỉnh tồn quầy {sau[d]} ≠ đếm {dem[d]}"
        )
    try:
        await kk.hoan_tac_dieu_chinh(pool, identity=co.ds, phieu_id=p["id"])
    except ConflictError:
        return  # phần cộng đã bán mất: hệ thống nói rõ, không lặng lẽ
    assert {d: await _ton_quay(co, d) for d in thuoc} == truoc, (
        f"{dau}: hoàn tác điều chỉnh không trả đúng tồn cũ"
    )


# ── Bấm ngẫu nhiên đủ thao tác ───────────────────────────────────────────


async def quay_con_han(co: Co, drug: str) -> list[str]:
    """Lô ở QUẦY của `drug` còn tồn và chưa hết hạn — chỗ giao / gắn lô được."""
    return [
        r["id"]
        for r in await co.q.pool.fetch(
            "SELECT id::text FROM drug_batch WHERE noi_chua = 'QUAY'"
            " AND drug_catalog_id = $1::uuid AND location_id = $2::uuid"
            " AND quantity_on_hand > 0 AND expiry_date >= $3 ORDER BY id",
            drug,
            co.loc,
            hom_nay_vn(),
        )
    ]


async def ids_so(co: Co) -> set[str]:
    return {
        r["id"]
        for r in await co.q.pool.fetch(
            "SELECT t.id::text AS id FROM inventory_txn t JOIN drug_batch b ON"
            " b.id = t.drug_batch_id WHERE b.location_id = $1::uuid",
            co.loc,
        )
    }


async def kiem_giao_cua_don(co: Co, rx: str, trace: tuple[str, ...]) -> None:
    """R7: số đã giao của đơn = số đã trừ ở lô (DISPENSE) + số còn chờ gán lô.
    Không mất, không đếm hai lần — dù máy tự chọn lô, giao tay hay gán lô sau."""
    pool = co.q.pool
    da_giao = D(
        str(
            await pool.fetchval(
                "SELECT dispensed_qty FROM prescription WHERE id = $1::uuid", rx
            )
        )
    )
    da_tru = D(
        str(
            await pool.fetchval(
                "SELECT coalesce(-sum(quantity), 0) FROM inventory_txn"
                " WHERE ref_id = $1::uuid AND txn_type = 'DISPENSE'",
                rx,
            )
        )
    )
    cho = D(
        str(
            await pool.fetchval(
                "SELECT coalesce(sum(so_luong), 0) FROM thuoc_giao_chua_gan_lo"
                " WHERE prescription_id = $1::uuid AND drug_batch_id IS NULL",
                rx,
            )
        )
    )
    assert da_giao == da_tru + cho, f"R7 đã giao {da_giao} ≠ {da_tru} + {cho}: {trace}"


_LENH = (
    "nhap",
    "nhap_het_han",
    "chuyen_ra",
    "chuyen_ra",
    "quay_tra_kho",
    "giao",
    "giao_khong_lo",
    "gan_lo",
    "tra",
    "huy",
    "kiem",
    "dieu_chinh",
    "hoan_tac",
)


@pytest.mark.parametrize("seed", range(60))
async def test_bam_ngau_nhien_du_thao_tac_moi_man_bang_so_goc(
    co: Co, seed: int
) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    await _bat(co)
    rx, drug0 = await _don(co, 14)
    thuoc = [drug0, await _thuoc_moi(co.q)]
    await _thu(co.q)
    kho_dau = [await _nhap_kho(co, d, 30) for d in thuoc]
    chuyen_cuoi: list[str] = [(await _chuyen(co, kho_dau[0], 12))["id"]]
    da_ghi_so: Counter[str] = Counter()
    bi_tu_choi: Counter[str] = Counter()
    trace: tuple[str, ...] = (f"seed={seed} mở đầu: nhập 30×2, chuyển 12 ra quầy",)
    await kiem_tat_ca(co, thuoc, trace)

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

    for buoc in range(12):
        lenh = rng.choice(_LENH)
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        id_so_truoc = await ids_so(co)
        sổ_trước = len(id_so_truoc)
        try:
            if lenh == "nhap":
                await _nhap_kho(co, rng.choice(thuoc), rng.randint(1, 5))
            elif lenh == "nhap_het_han":
                await _nhap_kho(
                    co,
                    rng.choice(thuoc),
                    rng.randint(1, 4),
                    han=hom_nay_vn() - timedelta(days=rng.randint(1, 30)),
                )
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
                cho = await quay_con_han(co, drug0)
                if cho:
                    await svc.cap_phat(
                        identity=co.ds,
                        prescription_id=rx,
                        drug_batch_id=rng.choice(cho),
                        so_luong=1,
                    )
            elif lenh == "giao_khong_lo":
                await svc.cap_phat(
                    identity=co.ds,
                    prescription_id=rx,
                    drug_batch_id=None,
                    so_luong=1,
                )
            elif lenh == "gan_lo":
                dong = await pool.fetchval(
                    "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE"
                    " prescription_id = $1::uuid AND drug_batch_id IS NULL LIMIT 1",
                    rx,
                )
                cho = await quay_con_han(co, drug0)
                if dong and cho:
                    await svc.gan_lo_da_giao(
                        identity=co.ds, dong_id=dong, drug_batch_id=rng.choice(cho)
                    )
            elif lenh == "tra":
                txn = await pool.fetchval(
                    "SELECT t.id::text FROM inventory_txn t WHERE t.ref_id=$1::uuid"
                    " AND t.txn_type='DISPENSE' AND NOT EXISTS (SELECT 1 FROM"
                    " drug_return r WHERE r.original_dispense_txn_id = t.id) LIMIT 1",
                    rx,
                )
                if txn:
                    await _tra_thuoc(svc, co, txn)
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
                    ton = D(str((await _hang(co, lo))["quantity_on_hand"]))
                    await kho.kiem_kho(
                        pool,
                        identity=co.ds,
                        khoa_gui=uuid.uuid4().hex,
                        dong=[
                            {
                                "drug_batch_id": lo,
                                "thuc_te": max(D(0), ton + rng.randint(-1, 2)),
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
        except (ConflictError, ValidationError, NotFoundError):
            bi_tu_choi[lenh] += 1  # luật từ chối: sổ không được đổi, kiểm ngay dưới
        id_so_sau = await ids_so(co)
        sổ_sau = len(id_so_sau)
        if lenh == "giao_khong_lo":  # R6
            # Máy TỰ CHỌN lô (27/10/2026): chỉ được ghi DISPENSE âm của đơn này.
            moi = await pool.fetch(
                "SELECT txn_type, quantity, ref_id::text AS ref_id FROM inventory_txn"
                " WHERE id = ANY($1::uuid[])",
                list(id_so_sau - id_so_truoc),
            )
            assert all(
                r["txn_type"] == "DISPENSE" and r["quantity"] < 0 and r["ref_id"] == rx
                for r in moi
            ), f"giao không lô ghi dòng sổ lạ: {trace}"
        await kiem_giao_cua_don(co, rx, trace)  # R7
        if sổ_sau > sổ_trước:
            da_ghi_so[lenh] += 1
        await kiem_tat_ca(co, thuoc, trace)
    await vong_kiem_ke(co, thuoc, rng, " | ".join(trace))
    await kiem_tat_ca(co, thuoc, (*trace, "sau vòng kiểm kê ca"))
    # Bài không rỗng: in ra mỗi loại thao tác đã GHI được bao nhiêu dòng sổ.
    print(f"MOPHONG seed={seed} ghi={dict(da_ghi_so)} tu_choi={dict(bi_tu_choi)}")


# ── Hết hạn và tranh chấp ────────────────────────────────────────────────


async def test_lo_het_han_khong_giao_duoc_va_so_khong_doi(co: Co) -> None:
    rx, drug = await _don(co, 3)
    await _thu(co.q)
    lo = await _nhap_kho(co, drug, 5, han=hom_nay_vn() - timedelta(days=1))
    svc = PharmacyService(co.q.pool)
    truoc = await co.q.pool.fetchval(
        "SELECT count(*) FROM inventory_txn WHERE drug_batch_id = $1::uuid", lo
    )
    with pytest.raises((ConflictError, ValidationError)):
        await svc.cap_phat(
            identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=1
        )
    assert (
        await co.q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn WHERE drug_batch_id = $1::uuid", lo
        )
        == truoc
    )
    await kiem_tat_ca(co, [drug], ("lô hết hạn",))


async def test_hai_nguoi_cung_giao_lo_con_mot_cai_chi_mot_nguoi_duoc(co: Co) -> None:
    rx, drug = await _don(co, 2)
    await _thu(co.q)
    lo = await _nhap_kho(co, drug, 1)
    svc = PharmacyService(co.q.pool)

    async def giao() -> str:
        try:
            await svc.cap_phat(
                identity=co.ds, prescription_id=rx, drug_batch_id=lo, so_luong=1
            )
            return "ok"
        except (ConflictError, ValidationError):
            return "tu_choi"

    kq = await asyncio.gather(giao(), giao())
    assert sorted(kq) == ["ok", "tu_choi"], kq
    assert D(str((await _hang(co, lo))["quantity_on_hand"])) == 0
    await kiem_tat_ca(co, [drug], ("hai người cùng giao",))


async def test_hai_phieu_chuyen_cung_luc_khong_chuyen_qua_ton_kho(co: Co) -> None:
    drug = await _thuoc_moi(co.q)
    await _bat(co)
    lo = await _nhap_kho(co, drug, 5)

    async def chuyen(so: int) -> str:
        try:
            await _chuyen(co, lo, so)
            return "ok"
        except (ConflictError, ValidationError):
            return "tu_choi"

    kq = await asyncio.gather(chuyen(4), chuyen(4))
    assert kq.count("ok") == 1, kq  # 4 + 4 > 5: chỉ một phiếu qua
    kho_con = D(str((await _hang(co, lo))["quantity_on_hand"]))
    assert kho_con == 1
    await kiem_tat_ca(co, [drug], ("hai phiếu chuyển cùng lúc",))
