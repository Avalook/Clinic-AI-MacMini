"""Nhiều đơn vị bán + giá theo đơn vị cho thuốc (Tuyền 31/10/2026).

Bất biến (giả lập trước khi code — luật làm việc của repo):
  B1  số trên dòng đơn / hoá đơn theo ĐƠN VỊ ĐÃ BÁN, số ở lô theo ĐƠN VỊ LÔ;
  B2  bán 1 hộp (30 gói): lô trừ đúng 30 gói theo FEFO, tiền đúng giá hộp;
  B3  đã thu thì hệ số và giá theo ẢNH CHỤP — sửa danh mục sau đó không đổi gì;
  B4  tổng hoàn không vượt, không hụt số đã thu dù trả lẻ từng gói;
  B5  đơn vị không rõ thì không đoán: vẫn giao, vào chờ gán lô, nói rõ cần làm gì.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services import ban_theo_don_service as btd
from clinicai.services import ban_thuoc_service as bt
from clinicai.services import bao_cao_cuoi_ngay_service as bc
from clinicai.services import bao_cao_thuoc_service as bct
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.don_vi_thuoc import (
    BangDonVi,
    DonViBan,
    QuyDoiDong,
    doc_don_vi_gui_len,
)
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _huy_phieu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


def _han(ngay: int) -> date:
    return date.today() + timedelta(days=ngay)


async def _luu(q: Quay, ten: str, **kw: Any) -> str:
    kq = await PharmacyService(q.pool).luu_thuoc(
        identity=q.duoc_si, drug_catalog_id=None, ten=ten, **kw
    )
    return str(kq["id"])


async def _thuoc_goi(q: Quay, *, hop: bool = True) -> str:
    """Androgel của Tuyền: gói 85.000đ, hộp 30 gói 2.400.000đ."""
    return await _luu(
        q,
        f"Androgel {uuid.uuid4().hex[:8]}",
        gia=85_000,
        don_vi_ban="gói",
        cac_don_vi=[{"don_vi": "hộp", "he_so": 30, "gia": 2_400_000}] if hop else None,
    )


async def _lo(
    q: Quay, drug: str, so: Any, don_vi: str = "gói", han: date | None = None
) -> str:
    """Lô thẳng theo `don_vi` (đi qua `nhap_lo`, thuốc phải đúng đơn vị đó)."""
    kq = await PharmacyService(q.pool).nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=so,
        batch_code=f"LO-{uuid.uuid4().hex[:10]}",
        expiry_date=han or _han(400),
        unit=don_vi,
    )
    return str(kq["drug_batch_id"])


async def _ton(q: Quay, lo: str) -> Decimal:
    return Decimal(
        str(
            await q.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
            )
        )
    )


async def _ban(q: Quay, drug: str, so: str) -> str:
    """Quầy "lấy thêm": thêm dòng `so` ("1 hộp") vào đơn bán."""
    kq = await QuayThuocService(q.pool).luu_dong_them(
        visit_id=q.visit_id,
        dong=[{"drug_catalog_id": drug, "quantity": so}],
        identity=q.thu_ngan,
    )
    return str(kq["them"][0])


async def _ke(q: Quay, drug: str | None, chu: str) -> str:
    """Bác sĩ gõ tự do: `chu` đi qua đúng hai hàm đọc của Postgres, rồi nhà thuốc
    xác định thuốc kho."""
    rx = str(
        await q.pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, 'thuoc go tay',"
            " $3, public.so_luong_tu_van_ban($3), public.don_vi_tu_van_ban($3)"
            " FROM visit v WHERE v.visit_id = $4::uuid RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            chu,
            q.visit_id,
        )
    )
    if drug:
        await PharmacyService(q.pool).xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
        )
    return rx


async def _hd(q: Quay) -> Any:
    async with q.pool.acquire() as conn:
        return await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )


async def _thu(q: Quay, **kw: Any) -> dict[str, Any]:
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="thuoc",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=kw.pop("bill_revision", None) or (await _hd(q)).revision,
        **kw,
    )


async def _giao(q: Quay, rx: str, so: Any, **kw: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=None, so_luong=so, **kw
    )


async def _xuat(q: Quay, rx: str) -> list[Any]:
    return list(
        await q.pool.fetch(
            "SELECT t.id::text AS id, -t.quantity AS so, b.batch_code"
            "  FROM inventory_txn t JOIN drug_batch b ON b.id = t.drug_batch_id"
            " WHERE t.ref_id = $1::uuid AND t.txn_type = 'DISPENSE'"
            " ORDER BY t.performed_at, t.id",
            rx,
        )
    )


async def _tra(q: Quay, txn: str, so: Any, ket_cuc: str = "HOAN") -> dict[str, Any]:
    return await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=txn,
        so_luong=so,
        ly_do="Khách trả",
        ket_cuc_tien=ket_cuc,
        ly_do_tien="Để lại trừ lần sau" if ket_cuc == "GIU_LAI" else None,
        hinh_thuc="CASH",
    )


async def _dong_rx(q: Quay, rx: str) -> Any:
    return await q.pool.fetchrow("SELECT * FROM prescription WHERE id = $1::uuid", rx)


async def _cho(q: Quay, rx: str) -> list[dict[str, Any]]:
    kq = await PharmacyService(q.pool).cho_gan_lo(identity=q.duoc_si)
    return [d for d in kq["dong"] if d["prescription_id"] == rx]


async def _sua_don_vi(q: Quay, drug: str, ds: list[dict[str, Any]], **kw: Any) -> None:
    r = await q.pool.fetchrow(
        "SELECT name_raw, unit_price, don_vi_ban FROM drug_catalog WHERE id = $1::uuid",
        drug,
    )
    await PharmacyService(q.pool).luu_thuoc(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        ten=r["name_raw"],
        gia=kw.get("gia", r["unit_price"]),
        don_vi_ban=kw.get("don_vi_ban", r["don_vi_ban"]),
        cac_don_vi=ds,
    )


async def _dong_danh_muc(q: Quay, drug: str) -> dict[str, Any]:
    ds = await PharmacyService(q.pool).danh_muc(identity=q.duoc_si)
    return next(d for d in ds if d["id"] == drug)


async def _phien(q: Quay, drug: str, don_vi: str) -> str:
    d = await _dong_danh_muc(q, drug)
    return str(next(x for x in d["cac_don_vi"] if x["don_vi"] == don_vi)["phien"])


# ── Bán và giao: B1, B2 ───────────────────────────────────────────────────


async def test_ban_1_hop_tien_dung_gia_hop_tru_30_goi_fefo_tach_hai_lo(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    xa = await _lo(q, drug, 40, han=_han(400))
    gan = await _lo(q, drug, 20, han=_han(30))
    rx = await _ban(q, drug, "1 hộp")

    hd = await _hd(q)
    d = hd.dong[0]
    assert (d.don_vi, d.so_luong, d.don_gia) == ("hộp", 1, 2_400_000)
    assert d.thanh_tien == 2_400_000 and d.he_so == 30 and hd.thu_duoc

    await _thu(q)
    kq = await _giao(q, rx, 1)

    assert await _ton(q, gan) == 0, "lô hết hạn sớm nhất trừ trước"
    assert await _ton(q, xa) == 30, "tách hai lô: 20 + 10 gói"
    assert [x["so_luong"] for x in kq["lo_da_tru"]] == [20, 10]
    assert kq["chua_tru_kho"] == 0
    assert "trừ 20 gói" in kq["tom_tat"] and "hộp" not in kq["tom_tat"]
    dong = await _dong_rx(q, rx)
    assert dong["dispensed_qty"] == 1 and dong["dispense_status"] == "CAP_DU"


async def test_anh_chup_giu_don_vi_gia_he_so_cua_lan_thu(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _ban(q, drug, "2 hộp")
    await _thu(q)
    r = await q.pool.fetchrow(
        "SELECT unit, quantity, unit_price, line_total, he_so FROM payment_bill_line"
        " WHERE visit_id = $1::uuid AND drug_catalog_id = $2::uuid",
        q.visit_id,
        drug,
    )
    assert (r["unit"], r["quantity"], r["unit_price"]) == ("hộp", 2, 2_400_000)
    assert (r["line_total"], r["he_so"]) == (4_800_000, 30)


async def test_quay_doi_don_vi_doi_tien_ngay_va_giu_so(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "2 gói")
    assert (await _hd(q)).tong == 170_000

    kq = await QuayThuocService(q.pool).doi_don_vi(
        prescription_id=rx, don_vi="HỘP", identity=q.thu_ngan
    )

    assert kq["don_vi"] == "hộp", "nhận diện không phân biệt hoa thường"
    assert (await _hd(q)).tong == 4_800_000
    doc = await QuayThuocService(q.pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    dong = next(d for d in doc["dong"] if d["id"] == rx)
    assert dong["gia"] == 2_400_000 and dong["so_mua"] is None
    assert [x["don_vi"] for x in dong["don_vi_chon"]] == ["gói", "hộp"]


async def test_dong_bac_si_doi_don_vi_o_quay_giu_chu_ke_goc(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ke(q, drug, "1 gói")
    await QuayThuocService(q.pool).doi_don_vi(
        prescription_id=rx, don_vi="hộp", identity=q.thu_ngan
    )
    dong = await _dong_rx(q, rx)
    assert (dong["quantity"], dong["unit"]) == ("1 hộp", "hộp")
    assert dong["so_luong_ke_goc"] == "1 gói", "giữ chữ bác sĩ kê gốc"


# ── Mục 2: hệ số và giá theo ảnh chụp ─────────────────────────────────────


async def test_doi_he_so_sau_khi_thu_giao_va_tra_van_theo_30(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 60)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _sua_don_vi(
        q,
        drug,
        [
            {
                "don_vi": "hộp",
                "he_so": 28,
                "gia": 2_000_000,
                "phien": await _phien(q, drug, "hộp"),
            }
        ],
    )

    await _giao(q, rx, 1)

    assert await _ton(q, lo) == 30, "giao theo hệ số lúc bán, không theo 28"
    kq = await _tra(q, (await _xuat(q, rx))[0]["id"], 15)
    assert kq["hoan"]["amount"] == 1_200_000, "hoàn theo giá và hệ số đã chụp"


async def test_doi_gia_truoc_khi_thu_thi_hoa_don_doi_dau(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _ban(q, drug, "1 hộp")
    cu = (await _hd(q)).revision
    await _sua_don_vi(
        q,
        drug,
        [
            {
                "don_vi": "hộp",
                "he_so": 30,
                "gia": 2_300_000,
                "phien": await _phien(q, drug, "hộp"),
            }
        ],
    )
    assert (await _hd(q)).revision != cu
    with pytest.raises(ConflictError):
        await _thu(q, bill_revision=cu)


async def test_dong_cu_don_vi_goc_khong_chup_he_so_la_1(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 10)
    rx = await _ban(q, drug, "3 gói")
    await _thu(q)
    he_so = await q.pool.fetchval(
        "SELECT he_so FROM payment_bill_line WHERE source_id = $1", rx
    )
    assert he_so is None
    await _giao(q, rx, 3)
    assert await _ton(q, lo) == 7


async def test_huy_phieu_sau_khi_giao_khach_tra_van_theo_he_so_luc_ban(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 60)
    rx = await _ban(q, drug, "1 hộp")
    kq = await _thu(q)
    await _giao(q, rx, 1)
    await _sua_don_vi(
        q,
        drug,
        [
            {
                "don_vi": "hộp",
                "he_so": 28,
                "gia": 2_400_000,
                "phien": await _phien(q, drug, "hộp"),
            }
        ],
    )
    await _huy_phieu(q, str(kq["payment_cycle_id"]))

    tra = await _tra(q, (await _xuat(q, rx))[0]["id"], 15, ket_cuc="GIU_LAI")

    so_ban = await q.pool.fetchval(
        "SELECT so_luong_ban FROM drug_return WHERE id = $1::uuid",
        tra["drug_return_id"],
    )
    assert so_ban == Decimal("0.5"), "15 gói theo hệ số 30 đã chụp, không theo 28"


# ── Mục 3: đơn vị gốc, tắt đơn vị ─────────────────────────────────────────


async def test_doi_don_vi_goc_khi_con_ton_bi_chan_khong_doi_nghia_so_ton(
    q: Quay,
) -> None:
    drug = await _thuoc_goi(q, hop=False)
    await _lo(q, drug, 10)
    with pytest.raises(ConflictError, match="đổi nghĩa toàn bộ số tồn"):
        await _sua_don_vi(q, drug, [], don_vi_ban="hộp")
    ban = await q.pool.fetchval(
        "SELECT don_vi_ban FROM drug_catalog WHERE id = $1::uuid", drug
    )
    assert ban == "gói"


async def test_doi_don_vi_goc_khi_da_co_he_so_bi_chan(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    with pytest.raises(ConflictError, match="hệ số"):
        await _sua_don_vi(q, drug, [], don_vi_ban="viên")


async def test_doi_don_vi_goc_khi_chua_co_gi_thi_duoc(q: Quay) -> None:
    drug = await _thuoc_goi(q, hop=False)
    await _sua_don_vi(q, drug, [], don_vi_ban="viên")
    ban = await q.pool.fetchval(
        "SELECT don_vi_ban FROM drug_catalog WHERE id = $1::uuid", drug
    )
    assert ban == "viên"


async def test_tat_don_vi_khong_lam_hong_dong_cho_thu_va_cho_gan(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 hộp")
    await _sua_don_vi(
        q,
        drug,
        [
            {
                "don_vi": "hộp",
                "he_so": 30,
                "gia": 2_400_000,
                "dang_ban": False,
                "phien": await _phien(q, drug, "hộp"),
            }
        ],
    )
    # Dòng đang chờ thu giữ giá đã lưu, vẫn thu được.
    hd = await _hd(q)
    assert hd.thu_duoc and hd.tong == 2_400_000
    # Dòng mới thì không chọn được đơn vị đã tắt.
    khac = await _ban(q, drug, "1 gói")
    with pytest.raises(ValidationError, match="đã tắt bán"):
        await QuayThuocService(q.pool).doi_don_vi(
            prescription_id=khac, don_vi="hộp", identity=q.thu_ngan
        )
    await _thu(q)
    # Chưa có lô: vào chờ gán; nhập lô rồi gán vẫn được dù đơn vị đang tắt.
    await _giao(q, rx, 1)
    lo = await _lo(q, drug, 40)
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"][0]["so_tru"] == 30
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=d["id"], drug_batch_id=lo
    )
    assert await _ton(q, lo) == 10


# ── Mục 4: khách trả, hoàn tiền ───────────────────────────────────────────


async def test_tra_5_goi_cua_hop_hoan_dung_tien_khong_lam_tron_mat(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 30)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    txn = (await _xuat(q, rx))[0]["id"]

    kq = await _tra(q, txn, 5)

    assert kq["hoan"]["amount"] == 400_000
    assert kq["tom_tat"] == ("Khách trả 5 gói (≈ 0,167 hộp đã bán) — hoàn 400.000đ.")
    assert await _ton(q, lo) == 5, "thuốc trả về đúng lô, theo đơn vị lô"
    r = await q.pool.fetchrow(
        "SELECT returned_qty, so_luong_ban FROM drug_return WHERE id = $1::uuid",
        kq["drug_return_id"],
    )
    assert r["returned_qty"] == 5
    assert abs(r["so_luong_ban"] - Decimal(5) / 30) < Decimal("0.000001")


async def test_tra_le_nhieu_lan_tong_hoan_dung_bang_so_da_thu(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 30)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    txn = (await _xuat(q, rx))[0]["id"]

    tien = [(await _tra(q, txn, so))["hoan"]["amount"] for so in (7, 7, 7, 9)]

    assert sum(tien) == 2_400_000, "không dư, không vượt"
    with pytest.raises(ValidationError, match="chỉ còn trả được 0"):
        await _tra(q, txn, 1)


async def test_tra_le_co_giam_gia_khong_vuot_so_da_thu(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 30)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(
        q,
        discount_type="AMOUNT",
        discount_value=400_000,
        discount_reason="khách quen",
    )
    thu = await q.pool.fetchval(
        "SELECT line_total FROM payment_bill_line WHERE source_id = $1", rx
    )
    assert thu == 2_000_000
    await _giao(q, rx, 1)
    txn = (await _xuat(q, rx))[0]["id"]

    tien = [(await _tra(q, txn, so))["hoan"]["amount"] for so in (10, 20)]

    assert tien[0] == 666_667 and sum(tien) == 2_000_000


async def test_giu_lai_tien_so_no_tinh_theo_don_vi_da_ban(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 30)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    await _tra(q, (await _xuat(q, rx))[0]["id"], 15, ket_cuc="GIU_LAI")
    from clinicai.core.clock import now_vn
    from clinicai.services.so_no_service import _THUOC_PHAI_TRA_SQL

    r = await q.pool.fetchrow(_THUOC_PHAI_TRA_SQL, CLINIC, q.visit_id, now_vn())
    assert r["con"] == Decimal("0.5"), "nợ khách nửa hộp, không phải 15 hộp"


# ── Mục 5: giao một phần ──────────────────────────────────────────────────


async def test_giao_mot_phan_theo_goi_chan_qua_so_va_ba_lan_10_goi_du_hop(
    q: Quay,
) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 100)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)

    await _giao(q, rx, 10, don_vi_giao="gói")
    assert (await _dong_rx(q, rx))["dispensed_qty"] == Decimal("0.333333")
    with pytest.raises(ValidationError, match="không giao quá số đã bán"):
        await _giao(q, rx, 21, don_vi_giao="gói")
    await _giao(q, rx, 10, don_vi_giao="gói")
    await _giao(q, rx, 10, don_vi_giao="gói")

    dong = await _dong_rx(q, rx)
    assert dong["dispensed_qty"] == 1 and dong["dispense_status"] == "CAP_DU"
    assert await _ton(q, lo) == 70, "ba lần 10 gói trừ đúng 30"


async def test_man_nha_thuoc_hien_khach_mua_1_hop_da_giao_15_goi(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 100)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 15, don_vi_giao="gói")

    man = await bt.man_nha_thuoc(q.pool, identity=q.duoc_si)
    luot = next(g for g in man["luot"] if g["visit_id"] == q.visit_id)
    d = next(x for x in luot["dong"] if x["id"] == rx)

    assert d["quy_doi"] == "1 hộp = 30 gói"
    assert d["da_giao_goc"] == "15 gói"
    assert d["don_vi_giao"] == ["hộp", "gói"]
    assert d["xuat"][0]["don_vi"] == "gói"


async def test_giao_bang_don_vi_khong_doi_duoc_noi_ro(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    with pytest.raises(ValidationError, match="thêm đơn vị ở Danh mục kho"):
        await _giao(q, rx, 5, don_vi_giao="vỉ")


# ── Mục 1 + 6 (lô cũ): Metronidazol bán viên, lô DEMO tính hộp ────────────


async def _metronidazol(q: Quay, so_hop: Any = 10) -> tuple[str, str]:
    """Thuốc bán viên, lô cũ tính hộp: nhập khi chưa khai đơn vị rồi mới khai —
    đúng cách dữ liệu DEMO bị lệch."""
    drug = await _luu(q, f"Metronidazol {uuid.uuid4().hex[:8]}", gia=2_000)
    lo = await _lo(q, drug, so_hop, don_vi="hộp")
    await q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = 'viên' WHERE id = $1::uuid", drug
    )
    return drug, lo


async def test_metronidazol_cho_gan_cu_tru_duoc_sau_khi_khai_he_so(q: Quay) -> None:
    drug, lo = await _metronidazol(q)
    rx = await _ban(q, drug, "20 viên")
    await _thu(q)

    kq = await _giao(q, rx, 20)

    assert kq["chua_tru_kho"] == 20 and await _ton(q, lo) == 10
    assert "“hộp” chưa có hệ số về “viên”" in kq["tom_tat"]
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"] == [] and d["lo_khac_don_vi"][0]["batch_code"]
    assert "chưa có hệ số" in d["can_lam"]

    # Tuyền thêm "1 hộp = 30 viên" → dòng chờ cũ trừ được, tồn hiện đúng.
    await _sua_don_vi(
        q, drug, [{"don_vi": "hộp", "he_so": 30, "gia": 55_000, "dang_ban": True}]
    )
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"][0]["so_tru"] == Decimal("0.667")
    assert d["can_lam"] is None
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=d["id"], drug_batch_id=lo
    )
    assert await _ton(q, lo) == Decimal("9.333")
    dm = await _dong_danh_muc(q, drug)
    assert dm["ton_quy_doi"] == "= 280 viên · 9 hộp 10 viên"
    assert dm["lo_chua_quy_doi"] == []


async def test_metronidazol_giao_moi_sau_khi_khai_he_so_tru_ngay(q: Quay) -> None:
    drug, lo = await _metronidazol(q)
    await _sua_don_vi(
        q, drug, [{"don_vi": "hộp", "he_so": 30, "gia": 55_000, "dang_ban": True}]
    )
    rx = await _ban(q, drug, "30 viên")
    await _thu(q)

    kq = await _giao(q, rx, 30)

    assert kq["chua_tru_kho"] == 0
    assert await _ton(q, lo) == 9, "30 viên = đúng 1 hộp"


async def test_lo_khac_goc_he_so_lon_doi_khong_chan_thi_giu_an_toan(q: Quay) -> None:
    drug = await _luu(q, f"Dung dịch {uuid.uuid4().hex[:8]}", gia=100)
    lo = await _lo(q, drug, 5, don_vi="thùng")
    await q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = 'ml' WHERE id = $1::uuid", drug
    )
    await _sua_don_vi(
        q, drug, [{"don_vi": "thùng", "he_so": 3000, "gia": 250_000, "dang_ban": True}]
    )
    rx = await _ban(q, drug, "1 ml")
    await _thu(q)

    kq = await _giao(q, rx, 1)

    assert kq["chua_tru_kho"] == 1 and await _ton(q, lo) == 5, "không trộn số"


async def test_lo_khong_du_phan_con_lai_cho_gan_doi_lai_dung_so_goi(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 25)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)

    kq = await _giao(q, rx, 1)

    assert await _ton(q, lo) == 0
    assert abs(kq["chua_tru_kho"] - Decimal(5) / 30) < Decimal("0.000001")
    assert (await _dong_rx(q, rx))["dispensed_qty"] == 1
    moi = await _lo(q, drug, 10)
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"][0]["so_tru"] == 5
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=d["id"], drug_batch_id=moi
    )
    assert await _ton(q, moi) == 5


async def test_quet_lo_khac_don_vi_dong_quy_doi_dung(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    lo = await _lo(q, drug, 40)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)

    await PharmacyService(q.pool).cap_phat(
        identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
    )

    assert await _ton(q, lo) == 10


async def test_cho_gan_cong_don_giua_cac_don_vi_khong_giao_lo_hai_lan(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx1 = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx1, 1)  # chưa có lô: 30 gói vào chờ gán

    lo = await _lo(q, drug, 35)
    khac = await _dong_danh_muc(q, drug)
    assert khac["ton_theo_don_vi"]

    # Lượt khác bán 10 gói: trên kệ thật chỉ còn 5 gói không có chủ.
    rows = await PharmacyService(q.pool).ton_kho(identity=q.duoc_si)
    dong = next(r for r in rows if r["id"] == lo)
    assert dong["ton_kha_dung_thuoc"] == 5


# ── Mục 7: bác sĩ gõ tự do ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("chu", "don_vi", "co_so", "gia"),
    [
        ("2 Hộp", "Hộp", 2, 2_400_000),
        ("1 hộp 30 gói", "hộp 30 gói", 1, 2_400_000),
        ("1 hop", "hop", 1, 2_400_000),
        ("10g", "g", 10, 85_000),
        ("1/2 hộp", None, None, None),
        ("hop", None, None, None),
        ("", None, None, None),
    ],
)
async def test_chu_bac_si_nhan_ra_thi_khop_khong_thi_khong_doan_so(
    q: Quay, chu: str, don_vi: str | None, co_so: int | None, gia: int | None
) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ke(q, drug, chu)
    dong = await _dong_rx(q, rx)
    assert dong["quantity"] == chu, "giữ nguyên chữ bác sĩ"
    assert dong["unit"] == don_vi
    assert dong["quantity_num"] == co_so, "không đoán số"
    d = (await _hd(q)).dong[0]
    if gia is None:
        assert d.van_de and d.thanh_tien is None
    else:
        assert d.don_gia == gia and d.van_de is None


async def test_don_vi_tat_hai_nghia_thi_khong_doan() -> None:
    b = BangDonVi(
        goc="viên",
        gia_goc=Decimal(1000),
        dong={"vỉ": DonViBan("vỉ", Decimal(10), Decimal(9000), True)},
    )
    assert b.he_so("v") is None, "viên hay vỉ: không chọn"
    assert b.he_so("vien") == 1
    assert b.he_so("VỈ") == 10
    assert b.nhan_ra("VI") == "vỉ"


# ── Mục 8: dữ liệu rác, trùng, giá 0, sửa cùng lúc ────────────────────────


@pytest.mark.parametrize(
    ("dong", "cau"),
    [
        ({"don_vi": "hộp", "he_so": 0}, "lớn hơn 0"),
        ({"don_vi": "hộp", "he_so": -3}, "lớn hơn 0"),
        ({"don_vi": "hộp", "he_so": "abc"}, "một con số"),
        ({"don_vi": "hộp", "he_so": None}, "một con số"),
        ({"don_vi": "hộp", "he_so": "NaN"}, "lớn hơn 0"),
        ({"don_vi": "hộp", "he_so": 99_999}, "quá lớn"),
        ({"don_vi": "hộp", "he_so": "0.0001"}, "quá nhỏ"),
        ({"don_vi": "", "he_so": 30}, "Nhập tên đơn vị"),
        ({"don_vi": "x" * 51, "he_so": 2}, "quá dài"),
        ({"don_vi": "gói", "he_so": 1}, "đơn vị gốc"),
        ({"don_vi": " GÓI ", "he_so": 1}, "đơn vị gốc"),
        ({"don_vi": "hộp", "he_so": 30, "gia": "abc"}, "một con số"),
        ({"don_vi": "hộp", "he_so": 30, "gia": -1}, "không âm"),
    ],
)
def test_don_vi_rac_tra_cau_tieng_viet(dong: dict[str, Any], cau: str) -> None:
    with pytest.raises(ValidationError, match=cau):
        doc_don_vi_gui_len([dong], goc="gói", gia_goc=Decimal(85_000))


@pytest.mark.parametrize("rac", ["abc", 5, {"a": 1}, [1], ["x"]])
def test_danh_sach_rac_khong_500(rac: Any) -> None:
    with pytest.raises(ValidationError):
        doc_don_vi_gui_len(rac, goc="gói", gia_goc=Decimal(1))


def test_don_vi_trung_khac_hoa_thuong_va_khoang_trang() -> None:
    with pytest.raises(ValidationError, match="bị trùng"):
        doc_don_vi_gui_len(
            [{"don_vi": "Hộp", "he_so": 30}, {"don_vi": "hộp ", "he_so": 28}],
            goc="gói",
            gia_goc=Decimal(1000),
        )


def test_chua_khai_don_vi_goc_khong_them_duoc_don_vi() -> None:
    with pytest.raises(ValidationError, match="Đơn vị gốc"):
        doc_don_vi_gui_len([{"don_vi": "hộp", "he_so": 3}], goc="", gia_goc=None)


async def test_gia_trong_luu_ro_goi_y_he_so_nhan_gia_goc(q: Quay) -> None:
    drug = await _luu(
        q,
        f"Androgel {uuid.uuid4().hex[:8]}",
        gia=85_000,
        don_vi_ban="gói",
        cac_don_vi=[{"don_vi": "hộp", "he_so": 30}],
    )
    gia = await q.pool.fetchval(
        "SELECT gia FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
    )
    assert gia == 2_550_000


async def test_gia_trong_ma_chua_co_gia_goc_thi_hoi(q: Quay) -> None:
    with pytest.raises(ValidationError, match="chưa có giá gốc"):
        await _luu(
            q,
            f"Androgel {uuid.uuid4().hex[:8]}",
            don_vi_ban="gói",
            cac_don_vi=[{"don_vi": "hộp", "he_so": 30}],
        )


async def test_gia_0_la_gia_hop_le(q: Quay) -> None:
    drug = await _luu(
        q,
        f"Tặng kèm {uuid.uuid4().hex[:8]}",
        gia=85_000,
        don_vi_ban="gói",
        cac_don_vi=[{"don_vi": "hộp", "he_so": 30, "gia": 0}],
    )
    await _ban(q, drug, "1 hộp")
    hd = await _hd(q)
    assert hd.dong[0].don_gia == 0 and hd.dong[0].van_de is None


async def test_gia_viet_dau_cham_nghin_doc_dung() -> None:
    d = doc_don_vi_gui_len(
        [{"don_vi": "hộp", "he_so": "30", "gia": "2.400.000"}],
        goc="gói",
        gia_goc=None,
    )
    assert d[0].gia == 2_400_000


async def test_hai_nguoi_sua_cung_luc_nguoi_sau_bi_bao(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    phien = await _phien(q, drug, "hộp")
    dong = {"don_vi": "hộp", "he_so": 30, "gia": 2_300_000, "phien": phien}
    await _sua_don_vi(q, drug, [dong])
    with pytest.raises(ConflictError, match="người khác sửa"):
        await _sua_don_vi(q, drug, [{**dong, "gia": 2_200_000}])
    gia = await q.pool.fetchval(
        "SELECT gia FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
    )
    assert gia == 2_300_000


async def test_don_vi_khong_gui_len_thi_giu_nguyen(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _sua_don_vi(q, drug, [{"don_vi": "vỉ", "he_so": 5, "gia": 400_000}])
    n = await q.pool.fetchval(
        "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", drug
    )
    assert n == 2


async def test_doi_don_vi_rac_tra_cau_tieng_viet(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 gói")
    with pytest.raises(ValidationError, match="Chọn đơn vị"):
        await QuayThuocService(q.pool).doi_don_vi(
            prescription_id=rx, don_vi="   ", identity=q.thu_ngan
        )


# ── Mục 9: revision, khoá sau khi thu ─────────────────────────────────────


async def test_doi_don_vi_doi_revision_khong_thu_nham_so_cu(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 gói")
    cu = (await _hd(q)).revision
    await QuayThuocService(q.pool).doi_don_vi(
        prescription_id=rx, don_vi="hộp", identity=q.thu_ngan
    )
    assert (await _hd(q)).revision != cu
    with pytest.raises(ConflictError):
        await _thu(q, bill_revision=cu)
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_bill_line WHERE source_id = $1", rx
        )
        == 0
    )


async def test_da_thu_thi_khoa_doi_don_vi(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ban(q, drug, "1 gói")
    await _thu(q)
    with pytest.raises(ConflictError, match="đã thu"):
        await QuayThuocService(q.pool).doi_don_vi(
            prescription_id=rx, don_vi="hộp", identity=q.thu_ngan
        )


# ── Mục 5 đề bài: đơn vị lạ ───────────────────────────────────────────────


async def test_don_vi_la_tinh_gia_goc_co_canh_bao_giao_cho_gan_noi_can_them(
    q: Quay,
) -> None:
    drug = await _thuoc_goi(q, hop=False)
    lo = await _lo(q, drug, 40)
    rx = await _ban(q, drug, "1 tuýp")

    hd = await _hd(q)
    assert hd.dong[0].don_gia == 85_000 and hd.thu_duoc
    assert any("“tuýp” chưa khai" in c for c in hd.canh_bao)
    await _thu(q)

    kq = await _giao(q, rx, 1)

    assert kq["chua_tru_kho"] == 1 and await _ton(q, lo) == 40
    assert "Cần thêm đơn vị “tuýp”" in kq["tom_tat"]
    assert "1 tuýp = ? gói" in kq["tom_tat"]

    await _sua_don_vi(
        q, drug, [{"don_vi": "tuýp", "he_so": 10, "gia": 800_000, "dang_ban": True}]
    )
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"][0]["so_tru"] == 10
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=d["id"], drug_batch_id=lo
    )
    assert await _ton(q, lo) == 30


# ── Mục 10: thuốc có tồn chưa khai đơn vị ─────────────────────────────────


async def test_chua_khai_don_vi_giao_duoc_chi_cho_khai_roi_gan_duoc(q: Quay) -> None:
    drug = await _luu(q, f"Cetrotide {uuid.uuid4().hex[:8]}", gia=500_000)
    lo = await _lo(q, drug, 10, don_vi="lọ")
    rx = await _ban(q, drug, "1")  # quầy không có đơn vị để ghi
    assert (await _dong_rx(q, rx))["unit"] is None
    doc = await QuayThuocService(q.pool).doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert next(d for d in doc["dong"] if d["id"] == rx)["chua_khai_don_vi"] is True
    dm = await _dong_danh_muc(q, drug)
    assert dm["chua_khai_don_vi"] is True
    await _thu(q)

    kq = await _giao(q, rx, 1)

    assert kq["chua_tru_kho"] == 1 and await _ton(q, lo) == 10, "không đoán đơn vị"
    assert "chưa khai đơn vị" in kq["tom_tat"]

    await _sua_don_vi(q, drug, [], don_vi_ban="lọ")
    d = (await _cho(q, rx))[0]
    assert d["lo_gan_duoc"][0]["so_tru"] == 1
    await PharmacyService(q.pool).gan_lo_da_giao(
        identity=q.duoc_si, dong_id=d["id"], drug_batch_id=lo
    )
    assert await _ton(q, lo) == 9


# ── Mục 6: báo cáo ────────────────────────────────────────────────────────


async def test_bao_cao_hang_hoa_1_hop_va_3_goi_khong_cong_thanh_4(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _ban(q, drug, "1 hộp")
    await _ban(q, drug, "3 gói")
    await _thu(q)
    cycle = await q.pool.fetchval(
        "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    rows = await q.pool.fetch(bc._DONG_SQL, CLINIC, [cycle])

    dong = bc.gom_hang_hoa([dict(r) for r in rows], [])["thuoc"]["dong"]

    theo = {d["don_vi"]: d for d in dong}
    assert theo["hộp"]["sl_ban"] == 1 and theo["hộp"]["doanh_thu"] == 2_400_000
    assert theo["gói"]["sl_ban"] == 3 and theo["gói"]["doanh_thu"] == 255_000
    assert theo["gói"]["khoa"] == drug, "khối tồn kho gắn vào dòng đơn vị gốc"


async def test_bao_cao_thuoc_theo_khach_tieu_hao_theo_tung_don_vi(q: Quay) -> None:
    kq = bct.gom_thuoc_theo_khach(
        khach=[{"visit_id": "v"}],
        don=[
            {"id": "a", "visit_id": "v", "nguon": "QUAY", "ten_kho": "A"},
            {"id": "b", "visit_id": "v", "nguon": "QUAY", "ten_kho": "A"},
        ],
        bill=[
            {"id": "1", "source_id": "a", "quantity": 1, "unit": "hộp"},
            {"id": "2", "source_id": "b", "quantity": 3, "unit": "gói"},
        ],
        hoan=[],
    )
    assert {(t["don_vi"], t["thuc_ban"]) for t in kq["tieu_hao"]} == {
        ("hộp", 1.0),
        ("gói", 3.0),
    }


def test_bao_cao_thuoc_ke_30_vien_mua_1_hop_khong_lech() -> None:
    kq = bct.gom_thuoc_theo_khach(
        khach=[{"visit_id": "v"}],
        don=[
            {
                "id": "a",
                "visit_id": "v",
                "nguon": "BAC_SI",
                "ten_kho": "A",
                "drug_name_raw": "A",
                "quay_sua": True,
                "ke_goc_num": 30,
                "he_so_ke": 1,
                "he_so_dong": 30,
                "unit": "hộp",
            }
        ],
        bill=[
            {
                "id": "1",
                "source_id": "a",
                "quantity": 1,
                "unit": "hộp",
                "he_so": 30,
                "line_total": 9,
            }
        ],
        hoan=[],
    )
    d = kq["khach"][0]["dong"][0]
    assert (d["so_ke"], d["thuc_ban"], d["chenh"]) == (1.0, 1.0, 0.0)
    assert d["don_vi"] == "hộp" and d["lech"] is False


async def test_ban_theo_don_ke_30_goi_mua_1_hop_la_du_khong_bao_vuot(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ke(q, drug, "30 gói")
    await QuayThuocService(q.pool).doi_don_vi(
        prescription_id=rx, don_vi="hộp", identity=q.thu_ngan
    )
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=rx, so_luong=1, identity=q.thu_ngan
    )
    await _thu(q)

    async with q.pool.acquire() as conn:
        don = await btd._doc_goc(conn, CLINIC, goc=q.visit_id, dang_ban={})

    d = don["dong"][0]
    assert (d["so_ke"], d["da_mua"], d["con_lai"]) == (30, 30, 0)
    assert d["vuot"] is False and d["don_vi"] == "gói"


async def test_ban_theo_don_ke_2_hop_mua_30_goi_con_30_goi(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    rx = await _ke(q, drug, "2 hộp")
    await QuayThuocService(q.pool).chon(
        prescription_id=rx, mua=False, identity=q.thu_ngan
    )
    await _ban(q, drug, "30 gói")
    await _thu(q)
    async with q.pool.acquire() as conn:
        don = await btd._doc_goc(conn, CLINIC, goc=q.visit_id, dang_ban={})
    d = don["dong"][0]
    assert (d["so_ke"], d["da_mua"], d["con_lai"]) == (60, 30, 30)


async def test_kiem_ca_cho_gan_quy_ve_don_vi_goc(q: Quay) -> None:
    from clinicai.services.kiem_ke_ca_service import giao_chua_gan_lo_theo_thuoc

    drug = await _thuoc_goi(q)
    rx1 = await _ban(q, drug, "1 hộp")
    rx2 = await _ban(q, drug, "3 gói")
    await _thu(q)
    await _giao(q, rx1, Decimal("0.5"))
    await _giao(q, rx2, 3)
    async with q.pool.acquire() as conn:
        kq = await giao_chua_gan_lo_theo_thuoc(conn, clinic_id=CLINIC, location_id=None)
    assert kq[drug] == 18


# ── Hàm thuần ─────────────────────────────────────────────────────────────


def test_quy_doi_dong_lo_thung_doi_khong_chan_tra_none() -> None:
    b = BangDonVi(
        goc="ml",
        dong={"thùng": DonViBan("thùng", Decimal(3000), None, False)},
    )
    q = QuyDoiDong(don_vi="ml", he_so_dong=Decimal(1), bang=b)
    assert q.so_lo(Decimal(3000), "thùng") == 1
    assert q.so_lo(Decimal(1), "thùng") is None


def test_chu_ton_quy_doi() -> None:
    b = BangDonVi(
        goc="gói",
        dong={"hộp": DonViBan("hộp", Decimal(30), Decimal(1), True)},
    )
    assert b.chu_ton([{"don_vi": "gói", "ton": 125}]) == "4 hộp 5 gói"
    assert b.chu_ton([{"don_vi": "gói", "ton": 120}]) == "4 hộp"
    assert b.chu_ton([{"don_vi": "gói", "ton": 5}]) is None
    assert b.chu_ton([{"don_vi": "hộp", "ton": 2}, {"don_vi": "gói", "ton": 5}]) == (
        "= 65 gói · 2 hộp 5 gói"
    )
    assert b.chu_ton([{"don_vi": "lạ", "ton": 5}]) is None
