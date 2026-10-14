"""G4d · R3 + T2 (Tuyền chốt E / T2, 14/10/2026) — trả thuốc ↔ tiền.

    scripts/test-nhanh.sh src/tests/services/test_tra_thuoc_hoan_db.py

Trước G4d (đã chạy thật — bài dò 14/10): khách trả 4 viên sau khi về → không
khoản hoàn, sổ "phòng khám nợ khách" = 0; thu 10 viên chưa giao mà khách về →
sổ = 0. Nay:

* trả thuốc BẮT chọn HOAN / DOI (tạo đúng khoản hoàn, mặc định hình thức hiệu
  lực của lần thu gốc) hoặc GIU_LAI (ghi lý do — vẫn là nợ khách);
* sổ PHAI_TRA có khoản THUỐC = đã thu − đã hoàn − đã giao + khách trả lại.

Bất biến tiền thật (bài ngẫu nhiên): tiền thuốc đã thu − tiền đã hoàn
= giá trị thuốc khách đang cầm + sổ "phòng khám nợ khách" (thuốc).
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (xem CP2).

from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.events.catalogue import CONG_NO, SO_NO
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.so_no_service import THUOC, so_du_hien_tai
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _giao, _san_sang, _thu, _xac_minh
from tests.services.test_tien_thuoc_cp5_db import (  # noqa: F401
    _bat_kho_thuoc,
    _dong_thuoc,
    _ql,
    _xuat,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

GIA = 5_000  # đơn giá viên của _san_sang (cp3)


async def _ve(q: Quay) -> None:
    await CheckoutService(q.pool).close(
        identity=q.thu_ngan, visit_id=q.visit_id, ly_do_tu_dong="Cho khách về."
    )


async def _tra(q: Quay, xuat: str, so: Any, ket: Any, **kw: Any) -> dict[str, Any]:
    return await PharmacyService(q.pool).khach_tra_thuoc(
        identity=kw.pop("identity", None) or _ql(q),
        dispense_txn_id=xuat,
        so_luong=so,
        ly_do="Khách dị ứng",
        ket_cuc_tien=ket,
        **kw,
    )


async def _phai_tra_thuoc(q: Quay) -> int:
    async with q.pool.acquire() as conn:
        sd, _ = await so_du_hien_tai(conn, CLINIC, q.visit_id, datetime.now(UTC))
    return sum(
        int(d["so_tien"]) for d in sd.chi_tiet.get("PHAI_TRA", []) if d["loai"] == THUOC
    )


async def _hoan_cua(q: Quay) -> list[tuple[str, str, int, str]]:
    return [
        (r["method"], r["status"], int(r["amount"]), r["reason"])
        for r in await q.pool.fetch(
            "SELECT method, status, amount, reason FROM payment_refund"
            " WHERE visit_id = $1::uuid AND kind = 'thuoc' ORDER BY created_at",
            q.visit_id,
        )
    ]


async def _so_tra(q: Quay) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_return WHERE visit_id = $1::uuid", q.visit_id
        )
    )


# ── chọn kết cục tiền ──────────────────────────────────────────────────────


async def test_hoan_tien_mat_mac_dinh_theo_lan_thu(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 10)
    await _ve(q)
    kq = await _tra(q, await _xuat(q, rx), 4, "HOAN")
    assert kq["hoan"]["status"] == "COMPLETED" and kq["hoan"]["amount"] == 4 * GIA
    assert [h[:3] for h in await _hoan_cua(q)] == [("CASH", "COMPLETED", 4 * GIA)]
    r = await q.pool.fetchrow(
        "SELECT ket_cuc_tien, refund_id IS NOT NULL AS co FROM drug_return"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert (r["ket_cuc_tien"], r["co"]) == ("HOAN", True)
    assert await _phai_tra_thuoc(q) == 0


async def test_hoan_chuyen_khoan_la_khoan_cho_va_hien_viec_ton(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    lan = (await _thu(q, "TRANSFER"))["payment_cycle_id"]
    await _xac_minh(q, lan)
    await _giao(q, rx, lo, 10)
    await _ve(q)
    await _tra(q, await _xuat(q, rx), 2, "HOAN")
    assert [h[:3] for h in await _hoan_cua(q)] == [("TRANSFER", "PENDING", 2 * GIA)]
    async with q.pool.acquire() as conn:
        ton = await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, "thuoc")
    assert any(
        t["loai"] == "HOAN_CHUA_XONG" and t.get("visit_id") == q.visit_id for t in ton
    )


async def test_doi_thuoc_hoan_ra_ghi_ly_do_doi(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 10)
    await _tra(q, await _xuat(q, rx), 3, "DOI", hinh_thuc="CASH")
    (h,) = await _hoan_cua(q)
    assert h[:3] == ("CASH", "COMPLETED", 3 * GIA) and h[3].startswith("Đổi thuốc")


async def test_giu_lai_la_no_khach_hien_viec_ton_roi_hoan_sau(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    lan = (await _thu(q))["payment_cycle_id"]
    await _giao(q, rx, lo, 10)
    await _ve(q)
    await _tra(q, await _xuat(q, rx), 4, "GIU_LAI", ly_do_tien="Trừ lần mua sau")
    assert await _hoan_cua(q) == []
    assert await _phai_tra_thuoc(q) == 4 * GIA
    await chay_ben_nhan(q.pool, CONG_NO, SO_NO)
    async with q.pool.acquire() as conn:
        ton = [
            t
            for t in await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, "thuoc")
            if t.get("visit_id") == q.visit_id
        ]
        dv = await DanhSachHoaDonService._viec_ton(conn, CLINIC, None, "dich_vu")
    assert [(t["loai"], t["so_tien"], t["kind"]) for t in ton] == [
        ("CHUA_TRA_LAI", 4 * GIA, "thuoc")
    ]
    assert "Thuốc" in str(ton[0]["mo_ta"])
    assert not [t for t in dv if t.get("visit_id") == q.visit_id]
    # Xử lý sau: hoàn bằng lệnh hoàn thường → hết nợ khách.
    await HoanTienService(q.pool).tao(
        identity=_ql(q),
        payment_cycle_id=lan,
        visit_id=q.visit_id,
        kind="thuoc",
        dong=[{"payment_bill_line_id": await _dong_thuoc(q, lan), "so_luong": 4}],
        method="CASH",
        reason="Khách quay lại lấy tiền",
    )
    assert await _phai_tra_thuoc(q) == 0


async def test_thieu_lua_chon_hoac_ly_do_bi_tu_choi_khong_ghi_gi(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 10)
    x = await _xuat(q, rx)
    for ket, kw in ((None, {}), ("TRA_BUA", {}), ("GIU_LAI", {"ly_do_tien": " "})):
        with pytest.raises(ValidationError):
            await _tra(q, x, 1, ket, **kw)
    with pytest.raises(ValidationError, match="chỉ còn trả được 10"):
        await _tra(q, x, 11, "HOAN")
    for rac in (-1, 0, "abc"):
        with pytest.raises(ClinicAIBaseException):
            await _tra(q, x, rac, "HOAN")
    assert await _so_tra(q) == 0 and await _hoan_cua(q) == []


async def test_khong_co_lego_thu_thuoc_thi_hoan_bi_chan_tra_cung_khong_ghi(
    q: Quay,
) -> None:
    """Hoàn không được → cả lần trả không ghi (cùng giao dịch); câu chỉ đường."""
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 10)
    co_lego = await q.pool.fetchval("SELECT 1")  # chỉ để giữ nhịp kết nối
    assert co_lego == 1
    try:
        await _tra(q, await _xuat(q, rx), 1, "HOAN", identity=q.duoc_si)
    except ConflictError as e:
        assert "Giữ lại" in str(e)
        assert await _so_tra(q) == 0
    else:
        # Dược sĩ đang có lego Thu tiền thuốc → hoàn được, đúng một khoản.
        assert len(await _hoan_cua(q)) == 1


# ── T2: thu rồi chưa giao mà khách về ──────────────────────────────────────


async def test_t2_thu_chua_giao_khach_ve_la_no_khach_giao_sau_het(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    assert await _phai_tra_thuoc(q) == 0  # khách còn ở phòng khám
    await _ve(q)
    assert await _phai_tra_thuoc(q) == 10 * GIA
    await _giao(q, rx, lo, 6)
    assert await _phai_tra_thuoc(q) == 4 * GIA
    await _giao(q, rx, lo, 4)
    assert await _phai_tra_thuoc(q) == 0


# ── bấm lộn xộn: bất biến tiền thật ────────────────────────────────────────


async def _tien(q: Quay) -> tuple[int, int, int]:
    """(đã thu PAID, đã hoàn chờ/xong, giá trị thuốc khách đang cầm) — đọc
    thẳng sổ tiền và sổ kho, KHÔNG qua công thức sổ nợ."""
    thu = int(
        await q.pool.fetchval(
            "SELECT coalesce(sum(amount), 0) FROM payment_cycle"
            " WHERE visit_id = $1::uuid AND kind = 'thuoc' AND status = 'PAID'",
            q.visit_id,
        )
    )
    hoan = int(
        await q.pool.fetchval(
            "SELECT coalesce(sum(r.amount), 0) FROM payment_refund r"
            " JOIN payment_cycle c ON c.payment_cycle_id = r.payment_cycle_id"
            " WHERE r.visit_id = $1::uuid AND r.kind = 'thuoc'"
            " AND r.status IN ('PENDING', 'COMPLETED') AND c.status = 'PAID'",
            q.visit_id,
        )
    )
    cam = Decimal(
        str(
            await q.pool.fetchval(
                "SELECT coalesce(sum(p.dispensed_qty), 0)"
                " - coalesce((SELECT sum(t.returned_qty) FROM drug_return t"
                "             WHERE t.visit_id = $1::uuid), 0)"
                " FROM prescription p WHERE p.visit_id = $1::uuid",
                q.visit_id,
            )
        )
    )
    return thu, hoan, int(cam * GIA)


async def test_bam_lon_xon_tien_thuoc_khop(q: Quay) -> None:
    rx, _, lo = await _san_sang(q, 10, 100)
    rnd = random.Random(1410)
    da_ve = False
    lech: list[str] = []
    buoc: list[str] = []
    for _ in range(40):
        viec = rnd.choice(["thu", "thu_ck", "xac_minh", "giao", "tra", "ve"])
        try:
            if viec == "thu":
                await _thu(q)
            elif viec == "thu_ck":
                await _thu(q, "TRANSFER")
            elif viec == "xac_minh":
                lan = await q.pool.fetchval(
                    "SELECT payment_cycle_id::text FROM payment_cycle WHERE visit_id ="
                    " $1::uuid AND kind = 'thuoc' AND status = 'PENDING_VERIFICATION'",
                    q.visit_id,
                )
                assert lan is not None
                await _xac_minh(q, lan)
            elif viec == "giao":
                await _giao(q, rx, lo, rnd.randint(1, 4))
            elif viec == "tra":
                ket = rnd.choice(["HOAN", "DOI", "GIU_LAI"])
                await _tra(
                    q,
                    await _xuat(q, rx),
                    rnd.randint(1, 3),
                    ket,
                    ly_do_tien="Khách để lại" if ket == "GIU_LAI" else None,
                )
            elif viec == "ve" and not da_ve:
                await _ve(q)
                da_ve = True
        except (ClinicAIBaseException, AssertionError):
            continue
        buoc.append(viec)
        if da_ve:
            thu, hoan, cam = await _tien(q)
            no_khach = await _phai_tra_thuoc(q)
            if thu - hoan != cam + no_khach:
                lech.append(
                    f"{' → '.join(buoc)} ⇒ thu {thu:,} − hoàn {hoan:,}"
                    f" ≠ khách cầm {cam:,} + nợ khách {no_khach:,}"
                )
                break
    assert da_ve and "tra" in buoc, buoc
    assert lech == [], lech


async def test_ck_cho_xac_minh_chua_giao_duoc_nen_chua_tra_duoc(q: Quay) -> None:
    """Ca biên "trả thuốc đã CK chờ xác minh": tiền còn chờ thì chưa giao được
    (luật thu trước giao) → không có lần giao để trả. Lối hoàn vẫn có câu riêng
    cho lần thu còn chờ (`_hoan_phan_tra`) phòng khi luật giao đổi."""
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q, "TRANSFER")
    with pytest.raises(ConflictError, match="thu tiền thuốc trước"):
        await _giao(q, rx, lo, 4)


async def test_lo_het_han_khach_tra_ve_van_nhan_va_hoan(q: Quay) -> None:
    """G3a chặn BÁN / GIAO lô hết hạn — trả về vẫn phải nhận (thuốc vật lý đã
    quay lại) và tiền vẫn hoàn; lô ấy không bán lại được (luật G3a)."""
    rx, _, lo = await _san_sang(q, 10, 100)
    await _thu(q)
    await _giao(q, rx, lo, 5)
    await q.pool.execute(
        "UPDATE drug_batch SET expiry_date = current_date - 1 WHERE id = $1::uuid", lo
    )
    kq = await _tra(q, await _xuat(q, rx), 2, "HOAN")
    assert kq["hoan"]["amount"] == 2 * GIA
    assert await _so_tra(q) == 1
