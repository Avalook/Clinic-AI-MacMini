"""Mô phỏng ngẫu nhiên hai việc mới của đợt 17/10: QUY ĐỔI ĐƠN VỊ LÚC NHẬP và
QUYẾT ĐỊNH THUỐC KHÁCH TRẢ — bấm lẫn với giao, trả, huỷ, điều chỉnh, kiểm kho.

    scripts/test-nhanh.sh src/tests/services/test_mo_phong_quy_doi_tra_db.py

Mỗi bước chọn một lệnh ngẫu nhiên (theo hạt), tự tính ĐÁP ÁN từ luật viết trên giấy
(hàm `dap_an_nhap`, không gọi code đang thử), gọi service thật, rồi:

  * luật từ chối → sổ kho KHÔNG đổi dòng nào;
  * luật nhận → lô mới đúng đơn vị bán, đúng số đã đổi, đúng giá vốn làm tròn;
  * BAN_LAI: tồn giữ, bán được +số trả;
    HUY: tồn −số trả, bán được giữ, đúng MỘT dòng DISCARD;
  * quyết lần hai: bị từ chối, không đổi gì;
  * sau MỖI bước: R1–R5 của bộ mô phỏng #495 (`kiem_tat_ca`: tồn = cộng sổ,
    xuất–nhập–tồn, tồn theo ca, thẻ kho, giao chưa gắn lô) và R7–R9 bên dưới.

  R7  mọi lô của thuốc có đơn vị bán đều tính đúng đơn vị bán (không còn "hộp" lẻ loi);
  R8  lần trả đã HUY có đúng một DISCARD khớp số · BAN_LAI không có DISCARD;
  R9  dòng phiếu nhập có số gốc: số đã đổi = số gốc × hệ số (làm tròn 3 số lẻ).
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture q / co được import.
import random
import uuid
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_kho_quay_db import (  # noqa: F401
    Co,
    _bat,
    _chuyen,
    _don,
    _nhap_kho,
    co,
)
from tests.services.test_mo_phong_kho_day_du_db import kiem_tat_ca, quay_con_han
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]
D = Decimal
BA_LE = D("0.001")


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


# ── Đáp án viết tay (luật quy đổi trên giấy) ────────────────────────────────

LOI = "loi"


def dap_an_nhap(
    drug: str,
    unit: str,
    so: int,
    gia: int | None,
    he: Any,
    xac_nhan: bool,
    nho: dict[tuple[str, str], D],
) -> tuple[str, D | None, int | None, D | None]:
    """→ (LOI | "ok", số vào kho, giá vốn, hệ số mới cần nhớ)."""
    khoa = unit.strip().lower()
    if khoa == "viên":  # đúng đơn vị bán: nguyên trạng, hệ số gõ vào bị bỏ qua
        return "ok", D(so), gia, None
    da_nho = nho.get((drug, khoa))
    if he is None:
        if da_nho is None:
            return LOI, None, None, None
        hs, moi = da_nho, None
    else:
        try:
            hs = D(str(he))
        except Exception:  # noqa: BLE001
            return LOI, None, None, None
        if not hs.is_finite() or hs <= 0 or hs > 10_000:
            return LOI, None, None, None
        hs = hs.quantize(BA_LE, rounding=ROUND_HALF_UP)
        if hs <= 0:
            return LOI, None, None, None
        if da_nho is not None and max(hs / da_nho, da_nho / hs) > 10 and not xac_nhan:
            return LOI, None, None, None
        moi = hs
    qty = (D(so) * hs).quantize(BA_LE, rounding=ROUND_HALF_UP)
    von = None if gia is None else int((D(gia) / hs).quantize(D(1), ROUND_HALF_UP))
    return "ok", qty, von, moi


# ── Đọc trạng thái ───────────────────────────────────────────────────────────


async def _so_dong_so(co: Co) -> int:
    return int(
        await co.q.pool.fetchval(
            "SELECT count(*) FROM inventory_txn t JOIN drug_batch b ON"
            " b.id = t.drug_batch_id WHERE b.location_id = $1::uuid",
            co.loc,
        )
    )


async def _ton_kd(co: Co, lo: str) -> tuple[D, D]:
    r = await co.q.pool.fetchrow(
        "SELECT quantity_on_hand, drug_batch_kha_dung($2::uuid, id) AS kd"
        " FROM drug_batch WHERE id = $1::uuid",
        lo,
        co.ds.clinic_id,
    )
    return D(str(r["quantity_on_hand"])), D(str(r["kd"]))


async def kiem_moi(co: Co, thuoc: list[str], trace: tuple[str, ...]) -> None:
    pool = co.q.pool
    dau = " | ".join(trace)
    # R7
    sai = await pool.fetch(
        "SELECT batch_code, unit FROM drug_batch"
        " WHERE drug_catalog_id = ANY($1::uuid[]) AND lower(btrim(unit)) <> 'viên'",
        thuoc,
    )
    assert not sai, f"R7: lô lệch đơn vị bán {[dict(r) for r in sai]}\n{dau}"
    # R8
    for r in await pool.fetch(
        "SELECT id::text, returned_qty, disposition, disposition_txn_id::text AS txn"
        " FROM drug_return WHERE drug_batch_id IN (SELECT id FROM drug_batch"
        " WHERE drug_catalog_id = ANY($1::uuid[]))",
        thuoc,
    ):
        dc = await pool.fetch(
            "SELECT id::text, quantity FROM inventory_txn WHERE txn_type = 'DISCARD'"
            " AND ref_type = 'drug_return' AND ref_id = $1::uuid",
            r["id"],
        )
        if r["disposition"] == "HUY":
            assert len(dc) == 1, f"R8: lần trả HUY có {len(dc)} dòng DISCARD\n{dau}"
            assert D(str(dc[0]["quantity"])) == -D(str(r["returned_qty"]))
            assert dc[0]["id"] == r["txn"]
        else:
            assert not dc, f"R8: lần trả {r['disposition']} có DISCARD\n{dau}"
    # R9
    for r in await pool.fetch(
        "SELECT so_luong, so_luong_goc, he_so FROM phieu_kho_dong"
        " WHERE so_luong_goc IS NOT NULL"
    ):
        assert D(str(r["so_luong"])) == (
            D(str(r["so_luong_goc"])) * D(str(r["he_so"]))
        ).quantize(BA_LE, ROUND_HALF_UP), f"R9: {dict(r)}\n{dau}"


async def kiem_tat_ca_moi(co: Co, thuoc: list[str], trace: tuple[str, ...]) -> None:
    await kiem_tat_ca(co, thuoc, trace)
    await kiem_moi(co, thuoc, trace)


# ── Bấm ngẫu nhiên ───────────────────────────────────────────────────────────

_LENH = (
    "nhap_le",
    "nhap_le",
    "nhap_phieu",
    "giao",
    "giao",
    "tra",
    "tra",
    "tra",
    "xu_ly",
    "xu_ly",
    "xu_ly",
    "xu_ly_lai",
    "huy",
    "dieu_chinh",
    "kiem",
)
_DON_VI = ("viên", "Viên", "hộp", "Hộp ", "vỉ", "hộp")
_HE_SO = (
    None,
    None,
    "10",
    "10",
    "12",
    5,
    "abc",
    "0",
    "-2",
    "1e12",
    "99999",
    "500",
    "0.0004",
    "7",  # phần lẻ ≥ 0,5 khi chia giá vốn: bắt lỗi làm tròn xuống
    "6",
    "3.5",
)
_GIA = (None, 1_000, 2_500, 45_000, 99_999, 100_000, 450_000)


@pytest.mark.parametrize("seed", range(120))
async def test_nhap_quy_doi_va_xu_ly_thuoc_tra_bam_ngau_nhien(
    co: Co, seed: int
) -> None:
    rng = random.Random(seed)
    pool = co.q.pool
    svc = PharmacyService(pool)
    await _bat(co)
    rx, drug0 = await _don(co, 14)
    thuoc = [drug0, await _thuoc_moi(co.q)]
    for d in thuoc:  # đơn vị bán rõ ràng cho cả hai thuốc
        await pool.execute(
            "UPDATE drug_catalog SET don_vi_ban = 'viên' WHERE id = $1::uuid", d
        )
    await _thu(co.q)
    kho_dau = [await _nhap_kho(co, d, 30) for d in thuoc]
    await _chuyen(co, kho_dau[0], 14)
    nho: dict[tuple[str, str], D] = {}
    ghi: Counter[str] = Counter()
    tu_choi: Counter[str] = Counter()
    quyet: Counter[str] = Counter()
    trace: tuple[str, ...] = (f"seed={seed} mở đầu",)
    await kiem_tat_ca_moi(co, thuoc, trace)

    async def lo_co_ton() -> list[str]:
        return [
            r["id"]
            for r in await pool.fetch(
                "SELECT id::text FROM drug_batch"
                " WHERE drug_catalog_id = ANY($1::uuid[])"
                " AND location_id = $2::uuid AND quantity_on_hand > 0 ORDER BY id",
                thuoc,
                co.loc,
            )
        ]

    for buoc in range(14):
        lenh = rng.choice(_LENH)
        trace = (*trace, f"seed={seed} buoc={buoc} {lenh}")
        truoc = await _so_dong_so(co)
        try:
            if lenh == "nhap_le":
                drug = rng.choice(thuoc)
                unit, so = rng.choice(_DON_VI), rng.randint(1, 5)
                gia, he = rng.choice(_GIA), rng.choice(_HE_SO)
                xn = rng.random() < 0.3
                kq_dk, qty, von, moi = dap_an_nhap(drug, unit, so, gia, he, xn, nho)
                ma = f"MP-{uuid.uuid4().hex[:8]}"
                try:
                    kq = await svc.nhap_lo(
                        identity=co.ds,
                        drug_catalog_id=drug,
                        so_luong=so,
                        batch_code=ma,
                        expiry_date=hom_nay_vn(),
                        unit=unit,
                        cost_price=gia,
                        he_so=he,
                        xac_nhan_he_so=xn,
                    )
                except ValidationError:
                    assert kq_dk == LOI, f"luật từ chối mà đáp án nhận: {trace}"
                    assert await _so_dong_so(co) == truoc, f"từ chối mà sổ đổi: {trace}"
                    tu_choi[lenh] += 1
                else:
                    assert kq_dk == "ok", f"luật nhận mà đáp án từ chối: {trace}"
                    lo_moi = await pool.fetchrow(
                        "SELECT unit, quantity_on_hand, cost_price FROM drug_batch"
                        " WHERE id = $1::uuid",
                        kq["drug_batch_id"],
                    )
                    assert lo_moi["unit"] == "viên", trace
                    assert D(str(lo_moi["quantity_on_hand"])) == qty, (
                        lo_moi,
                        qty,
                        trace,
                    )
                    assert (
                        None
                        if lo_moi["cost_price"] is None
                        else int(lo_moi["cost_price"])
                    ) == von, (
                        lo_moi,
                        von,
                        trace,
                    )
                    if moi is not None:
                        nho[(drug, unit.strip().lower())] = moi
            elif lenh == "nhap_phieu":
                dong_nhap: list[dict[str, Any]] = []
                dap_an_nhap_list: list[
                    tuple[str, str, int, int | None, str | int | None, bool]
                ] = []
                for d in thuoc:  # hai dòng, HAI THUỐC khác nhau (hệ số nhớ độc lập)
                    unit, so = rng.choice(_DON_VI), rng.randint(1, 5)
                    gia_phieu, he_phieu = rng.choice(_GIA), rng.choice(_HE_SO)
                    xn = rng.random() < 0.3
                    dap_an_nhap_list.append((d, unit, so, gia_phieu, he_phieu, xn))
                    dong_nhap.append(
                        {
                            "drug_catalog_id": d,
                            "batch_code": f"MP-{uuid.uuid4().hex[:8]}",
                            "expiry_date": hom_nay_vn().isoformat(),
                            "so_luong": so,
                            "unit": unit,
                            "gia_nhap": gia_phieu,
                            "he_so": he_phieu,
                            "xac_nhan_he_so": xn,
                        }
                    )
                kq_phieu = [dap_an_nhap(*x, nho) for x in dap_an_nhap_list]
                try:
                    await kho.tao_phieu_nhap(
                        pool, identity=co.ds, khoa_gui=uuid.uuid4().hex, dong=dong_nhap
                    )
                except ValidationError:
                    assert any(k[0] == LOI for k in kq_phieu), (
                        f"phiếu từ chối oan: {trace}"
                    )
                    assert await _so_dong_so(co) == truoc, (
                        f"phiếu hỏng mà sổ đổi: {trace}"
                    )
                    tu_choi[lenh] += 1
                else:
                    assert all(k[0] == "ok" for k in kq_phieu), (
                        f"phiếu nhận oan: {trace}"
                    )
                    for (d, unit, *_), k in zip(
                        dap_an_nhap_list, kq_phieu, strict=True
                    ):
                        if k[3] is not None:
                            nho[(d, unit.strip().lower())] = k[3]
            elif lenh == "giao":
                cho = await quay_con_han(co, drug0)
                if cho:
                    await svc.cap_phat(
                        identity=co.ds,
                        prescription_id=rx,
                        drug_batch_id=rng.choice(cho),
                        so_luong=rng.randint(1, 3),
                    )
            elif lenh == "tra":
                # Trả 1..số còn trả được của một lần giao (không chỉ 1 viên).
                dong_tra = await pool.fetch(
                    "SELECT t.id::text AS id, -t.quantity - coalesce((SELECT"
                    " sum(returned_qty) FROM drug_return r WHERE"
                    " r.original_dispense_txn_id = t.id), 0) AS con"
                    " FROM inventory_txn t WHERE t.ref_id = $1::uuid"
                    " AND t.txn_type = 'DISPENSE'",
                    rx,
                )
                dong_tra = [d for d in dong_tra if d["con"] > 0]
                if dong_tra:
                    dong_duoc_tra = rng.choice(dong_tra)
                    await svc.khach_tra_thuoc(
                        identity=co.ds,
                        dispense_txn_id=dong_duoc_tra["id"],
                        so_luong=rng.randint(1, int(dong_duoc_tra["con"])),
                        ly_do="Khách trả mô phỏng",
                        ket_cuc_tien="HOAN",
                    )
            elif lenh == "xu_ly":
                cac_tra = await pool.fetch(
                    "SELECT id::text, drug_batch_id::text AS lo, returned_qty"
                    " FROM drug_return WHERE disposition IS NULL AND drug_batch_id IN"
                    " (SELECT id FROM drug_batch WHERE location_id = $1::uuid)",
                    co.loc,
                )
                if cac_tra:
                    r_tra = rng.choice(cac_tra)
                    qd = rng.choice(("BAN_LAI", "HUY", "HUY"))
                    ly = rng.choice(("Hỏng nắp", "Hết hạn", "ab", "", None))
                    qty = D(str(r_tra["returned_qty"]))
                    ton0, kd0 = await _ton_kd(co, r_tra["lo"])
                    thieu_ly = qd == "HUY" and len((ly or "").strip()) < 3
                    try:
                        kq = await svc.xu_ly_thuoc_tra(
                            identity=co.ds,
                            drug_return_id=r_tra["id"],
                            quyet_dinh=qd,
                            ly_do=ly,
                        )
                    except ValidationError:
                        assert thieu_ly, f"từ chối oan: {trace}"
                        assert (await _ton_kd(co, r_tra["lo"])) == (ton0, kd0), trace
                        assert await _so_dong_so(co) == truoc
                        tu_choi[lenh] += 1
                    except ConflictError:
                        assert qd == "HUY" and ton0 < qty, f"Conflict oan: {trace}"
                        assert (await _ton_kd(co, r_tra["lo"])) == (ton0, kd0), trace
                        tu_choi[lenh] += 1
                    else:
                        assert not thieu_ly, f"nhận mà thiếu lý do: {trace}"
                        ton1, kd1 = await _ton_kd(co, r_tra["lo"])
                        quyet[qd] += 1
                        if qd == "BAN_LAI":
                            assert (ton1, kd1) == (ton0, kd0 + qty), (trace, kq)
                        else:
                            assert (ton1, kd1) == (ton0 - qty, kd0), (trace, kq)
            elif lenh == "xu_ly_lai":
                da_xu_ly = await pool.fetch(
                    "SELECT id::text, drug_batch_id::text AS lo FROM drug_return"
                    " WHERE disposition IS NOT NULL AND drug_batch_id IN"
                    " (SELECT id FROM drug_batch WHERE location_id = $1::uuid)",
                    co.loc,
                )
                if da_xu_ly:
                    da_tra = rng.choice(da_xu_ly)
                    ton0, kd0 = await _ton_kd(co, da_tra["lo"])
                    with pytest.raises(ConflictError):
                        await svc.xu_ly_thuoc_tra(
                            identity=co.ds,
                            drug_return_id=da_tra["id"],
                            quyet_dinh=rng.choice(("BAN_LAI", "HUY")),
                            ly_do="Quyết lần hai",
                        )
                    assert (await _ton_kd(co, da_tra["lo"])) == (ton0, kd0), trace
                    assert await _so_dong_so(co) == truoc
            elif lenh == "huy":
                ds = await lo_co_ton()
                if ds:
                    await svc.huy(
                        identity=co.ds,
                        drug_batch_id=rng.choice(ds),
                        so_luong=1,
                        ly_do="Mô phỏng",
                    )
            elif lenh == "dieu_chinh":
                ds = await lo_co_ton()
                if ds:
                    await svc.dieu_chinh(
                        identity=co.ds,
                        drug_batch_id=rng.choice(ds),
                        so_luong=rng.choice((-1, 1, 2)),
                        ly_do="Điều chỉnh mô phỏng",
                    )
            elif lenh == "kiem":
                ds = await lo_co_ton()
                if ds:
                    lo = rng.choice(ds)
                    ton = (await _ton_kd(co, lo))[0]
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
        except (ConflictError, ValidationError, NotFoundError):
            tu_choi[lenh] += 1
        if await _so_dong_so(co) > truoc:
            ghi[lenh] += 1
        await kiem_tat_ca_moi(co, thuoc, trace)
    print(
        f"MOPHONG2 seed={seed} ghi={dict(ghi)} tu_choi={dict(tu_choi)} "
        f"quyet={dict(quyet)}"
    )
