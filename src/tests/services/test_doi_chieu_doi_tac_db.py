"""Khu 4 — ĐỐI CHIẾU ĐỘC LẬP tiền đối tác (billing_owner = EXTERNAL_PARTNER).

`test_doi_tac_khong_vao_tien_phong_kham_db` đã chứng minh tiền đối tác KHÔNG vào phiếu
thu / hoá đơn / thực thu (mọi tập con chỉ định × hai hình thức thu). Ở đây kiểm nửa
còn lại — chính SỔ ĐỐI TÁC (`doi_tac_thanh_toan`, "đã thu tiền khách") và chỗ nó giao
với tiền phòng khám:

  K1  Bấm ngẫu nhiên ghi nhận / huỷ / ghi lại "đã thu": mô hình TAY (luật ghi ở
      docstring `ghi_nhan_da_thu`) dự đoán từng bước nên lỗi hay không; rồi sổ gốc
      phải bằng màn /doi-tac, bằng `bill_service.doi_tac_da_thu`, và bằng sổ sự kiện
      (recorded − voided = số ghi nhận còn hiệu lực).
  K2  Báo cáo cuối ngày: khối `doi_tac.tong` = Σ ghi nhận còn hiệu lực trong ngày.
  K3  Đổi chủ thu SAU khi phòng khám đã thu: lịch sử phiếu KHÔNG đổi (đã chụp).
  K4  (xfail strict, CHỜ QUYẾT) cùng đợt ấy, đối tác vẫn ghi nhận "đã thu" được cho đúng
      chỉ định phòng khám đã thu → một dịch vụ nằm ở hai sổ.

Tổng toàn phòng khám trên DB DÙNG CHUNG: đọc sổ gốc trước và sau lần đọc báo cáo, chỉ
so khi không đổi (không ổn định sau vài lần thì skip).
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, time, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.bill_service import doi_tac_da_thu
from clinicai.services.config_service import PriceListService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.payment_service import PaymentService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai, _viec_da_nhan
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_quay_thu_mot_hoa_don_db import _dong, _kich_ban
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_LOI_LUAT = (ValidationError, LuotKhamConflictError, ConflictError, SafetyGateError)

#: (đầu vào, số tiền đúng hoặc None nếu rác) — viết tay theo luật, KHÔNG gọi
#: `doc_so_tien`.
_TIEN: list[tuple[Any, int | None]] = [
    (0, 0),
    (150_000, 150_000),
    (900_000, 900_000),
    ("900.000", 900_000),
    ("1.200.000đ", 1_200_000),
    (100_000_000, 100_000_000),
    (100_000_001, None),
    (-5, None),
    ("rác", None),
    (1.5, None),
    (True, None),
]
_HINH: list[tuple[Any, str | None]] = [
    ("CASH", "CASH"),
    ("transfer", "TRANSFER"),
    (" Cash ", "CASH"),
    ("QR", None),
    ("", None),
]
_LY_DO: list[tuple[str, bool]] = [
    ("ghi nhầm số tiền", True),
    ("  ", False),
    ("ab", False),
]


# ── Sổ gốc ───────────────────────────────────────────────────────────────


async def dang_hieu_luc(
    pool: asyncpg.Pool, oids: list[str]
) -> dict[str, tuple[int, str]]:
    rows = await pool.fetch(
        "SELECT service_order_id::text oid, so_tien, hinh_thuc FROM doi_tac_thanh_toan"
        " WHERE clinic_id = $1::uuid AND huy_luc IS NULL"
        " AND service_order_id = ANY($2::uuid[])",
        CLINIC,
        oids,
    )
    return {r["oid"]: (int(r["so_tien"]), r["hinh_thuc"]) for r in rows}


async def tong_hom_nay(pool: asyncpg.Pool) -> int:
    """Σ ghi nhận còn hiệu lực ghi trong ngày VN hôm nay (cả phòng khám)."""
    h = now_vn().date()
    tu = datetime.combine(h, time.min, tzinfo=CLINIC_TZ)
    v = await pool.fetchval(
        "SELECT coalesce(sum(so_tien), 0) FROM doi_tac_thanh_toan"
        " WHERE clinic_id = $1::uuid AND huy_luc IS NULL"
        " AND ghi_luc >= $2 AND ghi_luc < $3",
        CLINIC,
        tu,
        tu + timedelta(days=1),
    )
    return int(v)


async def sk_rong(pool: asyncpg.Pool, oid: str) -> int:
    """recorded − voided của một việc, đếm từ sổ sự kiện."""
    rows = await pool.fetch(
        "SELECT event_type FROM domain_event WHERE aggregate_id = $1::uuid"
        " AND event_type LIKE 'partner.payment_%'",
        oid,
    )
    ten = [r["event_type"] for r in rows]
    return ten.count("partner.payment_recorded") - ten.count("partner.payment_voided")


async def man_doi_tac(dt: Any, pool: asyncpg.Pool, oids: list[str]) -> dict[str, Any]:
    """Màn /doi-tac: chỉ định → `da_thu` ({so_tien, hinh_thuc}) hoặc None."""
    kq = await DoiTacService(pool).viec_doi_tac(identity=dt)
    return {
        v["chi_dinh_id"]: v["da_thu"]
        for k in kq["khach"]
        for v in k["viec"]
        if v["chi_dinh_id"] in oids
    }


# ── K1 + K2: bấm ngẫu nhiên có mô hình tay ───────────────────────────────


@pytest.mark.parametrize("seed", range(12))
async def test_k1_k2_ghi_huy_ghi_lai_khop_mo_hinh_man_hinh_va_bao_cao(
    pool: asyncpg.Pool, seed: int
) -> None:
    rng = random.Random(seed)
    qs: list[Quay] = [await tao_quay(pool) for _ in range(3)]
    oids = [await _viec_da_nhan(q) for q in qs]
    dt = await _nguoi_vai(qs[0], "PARTNER")
    ql = await _nguoi_vai(qs[0], "MANAGEMENT")
    svc = DoiTacService(pool)
    mo_hinh: dict[str, tuple[int, str] | None] = {o: None for o in oids}
    trace: tuple[str, ...] = ()

    for buoc in range(10):
        oid = rng.choice(oids)
        if rng.random() < 0.65:
            vao_t, tien = rng.choice(_TIEN)
            vao_h, ht = rng.choice(_HINH)
            trace = (*trace, f"s{seed}b{buoc} ghi {oid[:4]} {vao_t!r} {vao_h!r}")
            cu = mo_hinh[oid]
            loi_du_kien = (
                tien is None or ht is None or (cu is not None and cu != (tien, ht))
            )
            try:
                kq = await svc.ghi_nhan_da_thu(
                    order_id=oid, identity=dt, so_tien=vao_t, hinh_thuc=vao_h
                )
            except _LOI_LUAT:
                assert loi_du_kien, f"mô hình nói hợp lệ mà bị từ chối: {trace}"
            else:
                assert not loi_du_kien, (
                    f"mô hình nói phải từ chối mà được nhận: {trace}"
                )
                assert kq["already"] is (cu is not None)
                assert tien is not None and ht is not None
                mo_hinh[oid] = (tien, ht)
        else:
            ly, ly_ok = rng.choice(_LY_DO)
            trace = (*trace, f"s{seed}b{buoc} huy {oid[:4]} {ly!r}")
            try:
                kq = await svc.huy_da_thu(order_id=oid, identity=dt, ly_do=ly)
            except _LOI_LUAT:
                assert not ly_ok, f"lý do hợp lệ mà bị từ chối: {trace}"
            else:
                assert ly_ok, f"lý do rác mà được nhận: {trace}"
                assert kq["already"] is (mo_hinh[oid] is None)
                mo_hinh[oid] = None

        # Sau MỖI bước: sổ gốc = mô hình = màn /doi-tac = bill_service = sổ sự kiện.
        goc = await dang_hieu_luc(pool, oids)
        mong = {o: v for o, v in mo_hinh.items() if v is not None}
        assert goc == mong, f"sổ gốc ≠ mô hình: {goc} ≠ {mong} | {trace}"
        man = await man_doi_tac(dt, pool, oids)
        for o in oids:
            ra = man.get(o)
            assert (ra is None) == (mo_hinh[o] is None), f"màn /doi-tac: {trace}"
            if ra is not None:
                assert (int(ra["so_tien"]), ra["hinh_thuc"]) == mo_hinh[o], trace
            assert await sk_rong(pool, o) == (1 if mo_hinh[o] else 0), (
                f"sự kiện: {trace}"
            )
        async with pool.acquire() as conn:
            bill = await doi_tac_da_thu(conn, CLINIC, oids)
        assert {o: int(v["so_tien"]) for o, v in bill.items()} == {
            o: v[0] for o, v in mong.items()
        }, f"bill_service: {trace}"

    # K2 — khối `doi_tac` của báo cáo cuối ngày = Σ ghi nhận còn hiệu lực hôm nay.
    for _ in range(6):
        truoc = await tong_hom_nay(pool)
        bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ql)
        if truoc == await tong_hom_nay(pool):
            assert int(bc["doi_tac"]["tong"]) == truoc, "báo cáo ≠ sổ đối tác"
            return
    pytest.skip("DB đang có test khác ghi tiền đối tác liên tục")


# ── K3 + K4: đổi chủ thu sau khi phòng khám đã thu ───────────────────────


async def _da_thu_roi_doi_chu(pool: asyncpg.Pool) -> tuple[Quay, str, str, Any]:
    """Quầy thu 700.000 (khám 150 + SÂ 250 + Soi 300); quản lý đổi SÂ sang đối tác."""
    q, sa, soi, _hpv = await _kich_ban(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    qt = (await _dong(q))["quay_thu"]
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=700_000,
        bill_revision=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=f"dtdc-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
    )
    pid = await pool.fetchval(
        "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
        " AND service_code = $2",
        CLINIC,
        f"SA-{q.duoi}",
    )
    await PriceListService(pool).update(
        price_id=str(pid), identity=ql, billing_owner="EXTERNAL_PARTNER"
    )
    return q, sa, str(kq["payment_cycle_id"]), ql


async def test_k3_doi_chu_thu_sau_khi_da_thu_khong_viet_lai_lich_su_phieu(
    pool: asyncpg.Pool,
) -> None:
    """Phiếu đã chụp `billing_owner` lúc thu: đổi bảng giá sau đó, phiếu vẫn 700.000,
    dòng SÂ vẫn của phòng khám, không phát sinh tiền thừa."""
    _q, _sa, cid, ql = await _da_thu_roi_doi_chu(pool)
    dong = await pool.fetch(
        "SELECT name_snapshot, billing_owner, line_total FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid",
        cid,
    )
    assert sum(int(r["line_total"]) for r in dong) == 700_000
    assert all(r["billing_owner"] == "CLINIC" for r in dong)
    ngay = now_vn().date().isoformat()
    khach = (await DanhSachHoaDonService(pool).xem(identity=ql, tu=ngay, den=ngay))[
        "khach"
    ]
    phieu = next(p for k in khach for p in k["phieu"] if p["id"] == cid)
    assert phieu["so_tien"] == 700_000
    assert sum(int(d["thanh_tien"]) for d in phieu["dong"]) == 700_000


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CHỜ QUYẾT 17/10 (khu 4): `PriceListService.update` đổi billing_owner mà "
        "không kiểm chỉ định/phiếu thu đang có, và `ghi_nhan_da_thu` chỉ xét chủ thu "
        "HIỆN TẠI của bảng giá — nên đối tác ghi 'đã thu' được cho chỉ định phòng "
        "khám đã thu: một dịch vụ nằm ở hai sổ. Hướng: chặn đổi chủ thu khi đã có "
        "phiếu, hoặc chặn ghi nhận khi chỉ định đã nằm trong phiếu thu."
    ),
)
async def test_k4_chi_dinh_phong_kham_da_thu_khong_duoc_ghi_la_doi_tac_da_thu(
    pool: asyncpg.Pool,
) -> None:
    """Bất biến KHÔNG phụ thuộc cách quyết: một chỉ định không ở hai sổ thu."""
    q, sa, _cid, _ql = await _da_thu_roi_doi_chu(pool)
    dt = await _nguoi_vai(q, "PARTNER")
    await pool.execute(
        "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
        " VALUES ($1::uuid, $2::uuid, 'KHACH_DA_CHON')",
        CLINIC,
        sa,
    )
    with pytest.raises(_LOI_LUAT):
        await DoiTacService(pool).ghi_nhan_da_thu(
            order_id=sa, identity=dt, so_tien=250_000, hinh_thuc="CASH"
        )


async def test_k5_cung_so_tien_khac_hinh_thuc_phai_huy_roi_ghi_lai(
    pool: asyncpg.Pool,
) -> None:
    """Nhánh ngẫu nhiên ít trúng: 900.000 tiền mặt rồi 900.000 chuyển khoản là KHÁC
    ghi nhận (hình thức quyết định đối soát két) — không được coi là bấm lại."""
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    dt = await _nguoi_vai(q, "PARTNER")
    svc = DoiTacService(pool)
    await svc.ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="CASH"
    )
    with pytest.raises(_LOI_LUAT):
        await svc.ghi_nhan_da_thu(
            order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="TRANSFER"
        )
    assert await dang_hieu_luc(pool, [oid]) == {oid: (900_000, "CASH")}
    await svc.huy_da_thu(order_id=oid, identity=dt, ly_do="đổi hình thức thu")
    await svc.ghi_nhan_da_thu(
        order_id=oid, identity=dt, so_tien=900_000, hinh_thuc="TRANSFER"
    )
    assert await dang_hieu_luc(pool, [oid]) == {oid: (900_000, "TRANSFER")}
