"""BƯỚC 0 — giả lập tiền TRƯỚC khi code PR D (kế hoạch đơn vị mẹ/con mục 12, T3–T5).

Lượt có 3 dòng thuốc: A, B có giá, C là "thuốc rác" (danh mục không giá — bác sĩ gõ
tay, máy tự thêm). Đi đúng các lệnh THẬT của quầy/kho/lần thu, sau mỗi bước kiểm:

  I1  tổng tiền các lần thu đang sống = tổng thành tiền các dòng đã chụp vào chúng;
  I2  không dòng nào nằm trong hai lần thu đang sống;
  I3  hoàn tác lần thu → không dòng nào còn bị phủ, thu lại được;
  I4  giao thuốc chỉ cho dòng ĐÃ nằm trong lần thu PAID;
  I5  khách về khi còn dòng kê chưa thu (kể cả số mua để trống = mua đủ) → là nợ,
      chặn check-out; dòng khách không lấy thì không.

Kết quả đo trên code trước PR D ghi ở thân PR. Thu NHIỀU lần thuốc cho một lượt
(T4) KHÔNG làm ở đây: chỉ mục `uq_payment_cycle_thuoc_mot_lan_song` cấm có chủ ý
(xem bài `test_i0_thuoc_chi_mot_lan_thu_song`) — dòng lỗi được gỡ bằng T3 (gán
thuốc đúng / điền giá) hoặc "khách không lấy", rồi thu MỘT lần.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.cong_no_service import no_khi_ve
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thuoc_service import QuayThuocService
from clinicai.services.thuoc.go_dong_lech import dien_gia_thuoc
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _hd,
    _thuoc,
    q,  # noqa: F401
)
from tests.services.test_tien_thuoc_cp3_db import _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mặc định prod (Tuyền 20/09): thu không giữ chỗ lô.
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _ba_dong(q: Quay) -> tuple[str, str, str, str]:
    """A 2 × 10.000, B 3 × 20.000, C 5 × thuốc rác không giá. Trả (A, B, C, thuốc C)."""
    svc = PharmacyService(q.pool)
    ids: list[str] = []
    rac = ""
    for ten, gia, so in (("A", 10_000, 2), ("B", 20_000, 3), ("C", None, 5)):
        rx = await _don(q, so, ten=f"{ten} {q.duoi}")
        thuoc = await _thuoc(q, gia=gia, ten=f"Thuốc {ten} {q.duoi}")
        await svc.xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=thuoc
        )
        ids.append(rx)
        rac = thuoc
    return ids[0], ids[1], ids[2], rac


async def _phu(q: Quay) -> dict[str, int]:
    """Dòng đơn → số lần thu ĐANG SỐNG (chờ xác minh / PAID) đang phủ nó."""
    rows = await q.pool.fetch(
        """
        SELECT bl.source_id, count(*) AS n
          FROM payment_bill_line bl
          JOIN payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid AND c.kind = 'thuoc'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
           AND bl.source_type = 'prescription'
         GROUP BY bl.source_id
        """,
        CLINIC,
        q.visit_id,
    )
    return {str(r["source_id"]): int(r["n"]) for r in rows}


async def _bat_bien(q: Quay) -> None:
    """I1 + I2 sau mỗi bước."""
    tien = await q.pool.fetchrow(
        """
        SELECT coalesce(sum(c.original_amount_or), 0) AS thu,
               coalesce(sum(d.dong), 0) AS dong
          FROM (SELECT payment_cycle_id,
                       coalesce(original_amount, amount) AS original_amount_or
                  FROM payment_cycle
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND kind = 'thuoc' AND status IN ('PENDING_VERIFICATION', 'PAID')
               ) c
          LEFT JOIN LATERAL (
                SELECT sum(line_total) AS dong FROM payment_bill_line bl
                 WHERE bl.payment_cycle_id = c.payment_cycle_id
                   AND bl.billing_owner = 'CLINIC') d ON true
        """,
        CLINIC,
        q.visit_id,
    )
    assert tien["thu"] == tien["dong"], f"I1 lệch: {tien['thu']} ≠ {tien['dong']}"
    assert all(n == 1 for n in (await _phu(q)).values()), "I2: dòng bị thu hai lần"


async def _huy(q: Quay, cycle: str) -> None:
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="thuoc",
        reason="Thu nhầm",
        identity=q.thu_ngan,
    )


async def _khong_lay(q: Quay, rx: str, mua: bool = False) -> None:
    await QuayThuocService(q.pool).chon(
        prescription_id=rx, mua=mua, identity=q.thu_ngan
    )


async def _no(q: Quay) -> Any:
    async with q.pool.acquire() as conn:
        return await no_khi_ve(conn, clinic_id=CLINIC, visit_id=q.visit_id)


# ── I0: luật một lần thu thuốc sống — lý do T4 không làm trong PR này ──────


async def test_i0_thuoc_chi_mot_lan_thu_song(q: Quay) -> None:
    a, _b, c, _ = await _ba_dong(q)
    await _khong_lay(q, c)
    kq = await _thu(q)
    dinh_nghia = await q.pool.fetchval(
        "SELECT indexdef FROM pg_indexes"
        " WHERE indexname = 'uq_payment_cycle_thuoc_mot_lan_song'"
    )
    assert "UNIQUE" in dinh_nghia and "'thuoc'" in dinh_nghia
    # Đã thu thì quầy không tích lại dòng C để thu thêm — phải huỷ phiếu trước.
    with pytest.raises(ConflictError):
        await _khong_lay(q, c, mua=True)
    assert set(await _phu(q)) == {a, _b}
    await _bat_bien(q)
    assert kq["status"] == "PAID"


# ── Đường quầy đi sau PR D: gỡ dòng lỗi rồi thu MỘT lần ────────────────────


async def test_dong_rac_khoa_ca_hoa_don_dien_gia_thi_thu_du(q: Quay) -> None:
    a, b, c, rac = await _ba_dong(q)
    with pytest.raises(ValidationError, match="Chưa thu được"):
        await _thu(q)
    assert await _phu(q) == {}
    # T3: người có quyền giá điền giá cho thuốc rác ngay ở quầy.
    await dien_gia_thuoc(q.pool, identity=q.duoc_si, drug_catalog_id=rac, gia=7_000)
    kq = await _thu(q)
    assert kq["status"] == "PAID"
    assert await _phu(q) == {a: 1, b: 1, c: 1}
    tong = await q.pool.fetchval(
        "SELECT amount FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        kq["payment_cycle_id"],
    )
    assert tong == 2 * 10_000 + 3 * 20_000 + 5 * 7_000
    await _bat_bien(q)


async def test_khach_khong_lay_dong_loi_thu_phan_sach_hoan_tac_thu_lai(
    q: Quay,
) -> None:
    a, b, c, rac = await _ba_dong(q)
    await _khong_lay(q, c)
    lan1 = await _thu(q)
    assert await _phu(q) == {a: 1, b: 1}
    await _bat_bien(q)

    # I3: hoàn tác → không còn phủ; tích lại C, điền giá, thu lại đủ ba dòng.
    await _huy(q, lan1["payment_cycle_id"])
    assert await _phu(q) == {}
    await _khong_lay(q, c, mua=True)
    await dien_gia_thuoc(q.pool, identity=q.duoc_si, drug_catalog_id=rac, gia=7_000)
    lan2 = await _thu(q)
    assert lan2["payment_cycle_id"] != lan1["payment_cycle_id"]
    assert await _phu(q) == {a: 1, b: 1, c: 1}
    await _bat_bien(q)


async def test_hai_nguoi_thu_cung_luc_chi_mot_lan_thu(q: Quay) -> None:
    _a, _b, c, _ = await _ba_dong(q)
    await _khong_lay(q, c)
    rev = (await _hd(q, "thuoc")).revision

    async def thu() -> Any:
        return await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="thuoc",
            idempotency_key=f"test-{uuid.uuid4().hex}",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
            bill_revision=rev,
            method="CASH",
        )

    kq = await asyncio.gather(thu(), thu(), return_exceptions=True)
    thanh_cong = [k for k in kq if isinstance(k, dict)]
    # Người sau chờ khoá lượt, thấy lần thu cùng hoá đơn → trả lại đúng lần ấy.
    assert {k["payment_cycle_id"] for k in thanh_cong} and len(
        {k["payment_cycle_id"] for k in thanh_cong}
    ) == 1
    n = await q.pool.fetchval(
        "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid"
        " AND kind = 'thuoc' AND status = 'PAID'",
        q.visit_id,
    )
    assert n == 1
    await _bat_bien(q)


# ── I4: giao chỉ cho dòng đã thu ───────────────────────────────────────────


async def test_i4_khong_giao_dong_ke_them_sau_khi_thu(q: Quay) -> None:
    a, _b, c, _ = await _ba_dong(q)
    await _khong_lay(q, c)
    await _thu(q)
    # Dòng mới vào đơn SAU lần thu (đính chính, nhập lại…): chưa ai trả tiền.
    moi = await _don(q, 4, ten=f"Kê thêm {q.duoi}")
    thuoc = await _thuoc(q, gia=3_000, ten=f"Thuốc kê thêm {q.duoi}")
    await q.pool.execute(
        "UPDATE prescription SET drug_catalog_id = $2::uuid,"
        " drug_mapped_by = $3::uuid, drug_mapped_at = now() WHERE id = $1::uuid",
        moi,
        thuoc,
        q.duoc_si.staff_id,
    )
    with pytest.raises(ConflictError, match="chưa nằm trong lần thu"):
        await PharmacyService(q.pool).cap_phat(
            identity=q.duoc_si, prescription_id=moi, drug_batch_id=None, so_luong=4
        )
    assert (
        await q.pool.fetchval(
            "SELECT coalesce(dispensed_qty, 0) FROM prescription WHERE id = $1::uuid",
            moi,
        )
        == 0
    )
    # Dòng đã thu vẫn giao bình thường (tự giao khi thu đã giao đủ A thì vượt số).
    assert a in await _phu(q)


# ── I5: khách về còn dòng kê chưa thu ──────────────────────────────────────


async def _quay_ghi_mua(q: Quay, *rxs: str) -> None:
    """Quầy ghi số khách mua = số kê (khách lấy thật)."""
    for rx in rxs:
        await q.pool.execute(
            "UPDATE prescription SET purchased_qty = quantity_num WHERE id = $1::uuid",
            rx,
        )


async def test_i5_dong_ke_quay_chua_ghi_mua_khong_la_no_khong_chan(q: Quay) -> None:
    # Tuyền 26/11: bác sĩ kê ≠ khách mua — dòng quầy chưa ghi khách lấy không là
    # nợ, khách về được (luật T5 "số mua trống = nợ" đã bỏ: prod 1.200 dòng nợ ảo).
    await _ba_dong(q)
    no = await _no(q)
    assert no.dong == []
    assert not no.chan


async def test_i5_quay_ghi_khach_lay_chua_thu_la_no_chan_check_out(q: Quay) -> None:
    a, _b, c, _ = await _ba_dong(q)
    await _quay_ghi_mua(q, a, c)
    no = await _no(q)
    # Dòng rác chưa có giá mà khách đã lấy vẫn là nợ, số tiền chưa rõ.
    assert {d.source_id for d in no.dong} == {a, c}
    assert [d.so_tien for d in no.dong if d.source_id == c] == [None]
    assert no.chan
    with pytest.raises((ConflictError, ValidationError)):
        await CheckoutService(q.pool).close(
            identity=q.thu_ngan, visit_id=q.visit_id, ly_do_tu_dong="Cho khách về."
        )


async def test_i5_khach_khong_lay_va_da_thu_thi_khong_no(q: Quay) -> None:
    a, b, c, _ = await _ba_dong(q)
    await _quay_ghi_mua(q, a, b)
    await _khong_lay(q, c)
    assert {d.source_id for d in (await _no(q)).dong} == {a, b}
    await _thu(q)
    assert (await _no(q)).dong == []


async def test_i5_dong_chua_so_luong_khong_gia_khong_la_no(q: Quay) -> None:
    rx = await _don(q, 1, ten=f"Trống số {q.duoi}")
    await q.pool.execute(
        "UPDATE prescription SET quantity = NULL, quantity_num = NULL"
        " WHERE id = $1::uuid",
        rx,
    )
    no = await _no(q)
    assert no.dong == []
    assert not no.chan


async def test_i5_nha_thuoc_ghi_khach_khong_lay_khong_la_no(q: Quay) -> None:
    rx = await _don(q, 2)
    await PharmacyService(q.pool).tu_choi(
        identity=q.duoc_si, prescription_id=rx, ly_do="Khách đã có thuốc ở nhà"
    )
    assert (await _no(q)).dong == []
