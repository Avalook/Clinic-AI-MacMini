"""Quầy thu MỘT hoá đơn (Tuyền chốt 27/09/2026, đợt 3) — với database thật.

* Bấm Thu = máy chủ CHỐT lựa chọn + GHI SỔ trong MỘT giao dịch: bỏ tick →
  NOT_SELECTED; dịch vụ khách trả đối tác không cộng; gửi lại cùng khoá không
  thu hai lần; hỏng bước thu thì lựa chọn cũng không được ghi.
* Hoá đơn DỰ KIẾN của bảng (chỉ định chờ quyết tính như khách làm) có đúng
  ``revision`` của hoá đơn thật sau khi chốt.
* Ô phòng: số chờ + vắng nhất do máy chủ trả.
* So với bác sĩ chỉ định; sổ gom theo khách (có hoàn); CSV; phiếu in; khác
  phòng khám không thấy; ngày rác không ném.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import BillChangedError, NotFoundError
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.payment_service import KHONG_CON_KHOAN, PaymentService
from clinicai.services.quay_thu_service import QuayThuService, csv_lich_su
from tests.services.test_doi_tac_tu_thu_db import HPV_NODE, _gia, _nguoi_vai
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


async def _cd(q: Quay, ma: str, node: str = "DICHVU-SIEUAM") -> str:
    """Chỉ định chính thức CHỜ KHÁCH QUYẾT (PENDING) — như bác sĩ vừa bấm."""
    return str(
        await q.pool.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status, lan_chi_dinh)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $4, $5, 'authorized',"
            " $6::uuid, $6::uuid, now(), 'PENDING', 1) RETURNING id::text",
            CLINIC,
            q.visit_id,
            q.consultation_id,
            ma,
            node,
            q.bac_si.staff_id,
        )
    )


async def _kich_ban(pool: asyncpg.Pool) -> tuple[Quay, str, str, str]:
    """Khám 150k + SÂ 250k + Soi 300k (phòng khám thu) + HPV 900k (đối tác)."""
    q = await tao_quay(pool)
    await _gia(q, f"SA-{q.duoi}", 250_000, "DICHVU-SIEUAM", ben="CLINIC")
    await _gia(q, f"SOI-{q.duoi}", 300_000, "DICHVU-SIEUAM", ben="CLINIC")
    await _gia(q, f"HPV-{q.duoi}", 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    sa = await _cd(q, f"SA-{q.duoi}")
    soi = await _cd(q, f"SOI-{q.duoi}")
    hpv = await _cd(q, f"HPV-{q.duoi}", HPV_NODE)
    return q, sa, soi, hpv


async def _dong(q: Quay) -> dict[str, Any]:
    b = await CashierBoardService(q.pool).board(identity=q.thu_ngan, modes=["dich_vu"])
    dong: dict[str, Any] = next(i for i in b["items"] if i["visit_id"] == q.visit_id)
    return dong | {"_bang": b}


def _khoa() -> str:
    return f"thu-gop-{uuid.uuid4().hex}"


async def _trang_thai(q: Quay, *ids: str) -> list[str]:
    rows = await q.pool.fetch(
        "SELECT id::text, selection_status FROM service_order"
        " WHERE id = ANY($1::uuid[])",
        list(ids),
    )
    st = {r["id"]: r["selection_status"] for r in rows}
    return [st[i] for i in ids]


@pytest.mark.db
@pytest.mark.asyncio
async def test_bang_tra_mot_hoa_don_du_kien(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    d = await _dong(q)
    qt = d["quay_thu"]
    # Chỉ định còn chờ quyết tính NHƯ khách làm: 150 + 250 + 300 (HPV không cộng).
    assert qt["tong"] == 700_000
    assert [r["id"] for r in qt["phong_kham"]][1:] == [sa, soi]
    assert [r["id"] for r in qt["doi_tac"]] == [hpv]
    assert qt["lua_chon"]["order_ids_seen"] == [sa, soi, hpv]
    # Hoá đơn thật (cũ) vẫn không cộng chỉ định chưa chốt — không đổi hợp đồng cũ.
    assert d["hoa_don"]["dich_vu"]["tong"] == 150_000
    ss = qt["so_sanh"]
    assert (ss["so_chi_dinh"], ss["so_lam"], ss["so_bo"]) == (3, 3, 0)
    assert ss["bac_si"] == q.bac_si.full_name and ss["lan"] == 1
    # Ô phòng: vắng nhất lên đầu, có số chờ.
    phong = qt["phong_kham"][1]["phong_chon_duoc"]
    if phong:
        assert phong[0]["vang_nhat"] is True
        assert all("dang_cho" in p for p in phong)
        assert [p["dang_cho"] for p in phong] == sorted(p["dang_cho"] for p in phong)
    # Máy chủ quyết ai chờ thu + đếm cho tab.
    b = d["_bang"]
    assert q.visit_id in b["ds_cho_thu"]
    assert b["dem"]["cho_thu"] == len(b["ds_cho_thu"])
    assert d["cho_thu"] is True and d["cho_phut"] is not None


@pytest.mark.db
@pytest.mark.asyncio
async def test_thu_gop_chot_va_thu_mot_giao_dich(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    d = await _dong(q)
    seen = d["quay_thu"]["lua_chon"]["order_ids_seen"]
    khoa = _khoa()
    chon = {
        "order_ids_seen": seen,
        "selected_order_ids": [sa, hpv],  # bỏ tick Soi
        "expected_selection_revision": d["quay_thu"]["lua_chon"]["revision"],
    }
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=400_000,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=khoa,
        chon=chon,
    )
    assert kq["status"] == "PAID" and kq["chon"]["changed"] is True
    assert await _trang_thai(q, sa, soi, hpv) == [
        "SELECTED",
        "NOT_SELECTED",
        "SELECTED",
    ]
    tien = await pool.fetchval(
        "SELECT amount FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        kq["payment_cycle_id"],
    )
    assert tien == 400_000  # khám 150 + SÂ 250; HPV khách trả đối tác
    # Gửi lại CÙNG khoá (mất phản hồi, bấm lại) → đúng kết quả cũ, không thu hai lần.
    lai = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=400_000,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=khoa,
        chon=chon,
    )
    assert lai["payment_cycle_id"] == kq["payment_cycle_id"]
    so = await pool.fetchval(
        "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
    )
    assert so == 1
    # Bảng: khách rời Chờ thu, sang Đã thu hôm nay.
    b = (await _dong(q))["_bang"]
    assert q.visit_id not in b["ds_cho_thu"]
    assert b["dem"]["da_thu_hom_nay"] >= 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_hoa_don_du_kien_khop_revision_sau_khi_chot(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    qt = (await _dong(q))["quay_thu"]
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=_khoa(),
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi, hpv],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
    )
    assert kq["status"] == "PAID"
    assert await _trang_thai(q, sa, soi, hpv) == ["SELECTED"] * 3


@pytest.mark.db
@pytest.mark.asyncio
async def test_thu_hong_thi_lua_chon_cung_khong_ghi(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    qt = (await _dong(q))["quay_thu"]
    with pytest.raises(BillChangedError):
        await PaymentService(pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            amount=1_000,  # số màn thấy lệch máy chủ
            clinic_patient_id=None,
            identity=q.thu_ngan,
            method="CASH",
            idempotency_key=_khoa(),
            chon={
                "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
                "selected_order_ids": [sa],
                "expected_selection_revision": qt["lua_chon"]["revision"],
            },
        )
    # MỘT giao dịch: lựa chọn không được lưu nửa vời.
    assert await _trang_thai(q, sa, soi, hpv) == ["PENDING"] * 3
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    )
    # Tập chỉ định đã đổi (bác sĩ vừa thêm) → 409 có mã, không thu.
    with pytest.raises(LuotKhamConflictError) as e:
        await PaymentService(pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
            method="CASH",
            idempotency_key=_khoa(),
            chon={
                "order_ids_seen": [sa, soi],
                "selected_order_ids": [sa],
                "expected_selection_revision": qt["lua_chon"]["revision"],
            },
        )
    assert e.value.error_code == "SELECTION_ORDER_SET_CHANGED"


@pytest.mark.db
@pytest.mark.asyncio
async def test_chi_doi_tac_thi_chot_khong_thu(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await pool.execute(
        "UPDATE service_type SET di_thang_phong = true WHERE clinic_id = $1::uuid"
        " AND code = $2",
        CLINIC,
        f"KT-{q.duoi}",
    )
    await _gia(q, f"HPV-{q.duoi}", 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    hpv = await _cd(q, f"HPV-{q.duoi}", HPV_NODE)
    d = await _dong(q)
    assert d["quay_thu"]["tong"] == 0 and d["cho_thu"] is True
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=_khoa(),
        chon={
            "order_ids_seen": [hpv],
            "selected_order_ids": [hpv],
            "expected_selection_revision": 0,
        },
    )
    assert kq["status"] == KHONG_CON_KHOAN and kq["payment_cycle_id"] is None
    assert await _trang_thai(q, hpv) == ["SELECTED"]
    assert q.visit_id not in (await _dong(q))["_bang"]["ds_cho_thu"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_so_gom_theo_khach_co_hoan_csv_phieu(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    qt = (await _dong(q))["quay_thu"]
    kq = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=_khoa(),
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi, hpv],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
    )
    cycle = kq["payment_cycle_id"]
    ql = await _nguoi_vai(q, "MANAGEMENT")
    dong_soi = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_id = $2",
        cycle,
        soi,
    )
    hoan = await HoanTienService(pool).tao(
        identity=ql,
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong_soi, "so_luong": 1}],
        method="CASH",
        reason="khách không làm soi",
    )

    svc = QuayThuService(pool)
    ls = await svc.lich_su(identity=q.thu_ngan, tim=f"TT-{q.duoi}", chi_tiet=True)
    [g] = ls["khach"]
    assert (g["tong_goc"], g["tong_hoan"], g["con_lai"]) == (700_000, 300_000, 400_000)
    assert g["co_hoan"] and [s["loai"] for s in g["su_kien"]] == ["thu", "hoan"]
    assert g["doi_tac"][0]["id"] == hpv and g["doi_tac"][0]["gia"] == 900_000
    assert g["phieu"][0]["hoan"] is not None
    assert ls["co_quyen_huy"] is True
    # Tìm theo mã phiếu; bộ lọc hình thức; ngày rác → hôm nay, không ném.
    ma = g["ma_phieu_dau"]
    assert (await svc.lich_su(identity=q.thu_ngan, tim=ma))["khach"][0]["visit_id"] == (
        q.visit_id
    )
    assert all(
        q.visit_id != k["visit_id"]
        for k in (
            await svc.lich_su(identity=q.thu_ngan, tim=f"TT-{q.duoi}", hinh_thuc="QR")
        )["khach"]
    )
    rac = await svc.lich_su(identity=q.thu_ngan, tu="rác", den="2026-13-45", tim="x")
    assert rac["tu"] == rac["den"]
    # CSV: có BOM, đủ dòng thu + hoàn.
    out = csv_lich_su(ls["khach"])
    assert out.startswith("﻿") and "Hoàn" in out and ma in out

    # Phiếu in: thu (kèm đối tác tham khảo) + hoàn.
    p = await svc.phieu(identity=q.thu_ngan, id_=cycle)
    assert p["tong"] == 700_000 and p["loai"] == "thu"
    assert [x["ten"] for x in p["doi_tac"]] == [f"HPV-{q.duoi}"]
    assert p["phong_kham"]
    ph = await svc.phieu(identity=q.thu_ngan, id_=hoan["refund_id"], loai="hoan")
    assert ph["loai"] == "hoan" and ph["tong"] == 300_000 and ph["ly_do"]

    # Khác phòng khám: không thấy sổ, không in được phiếu.
    khac = str(
        await pool.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"Q{q.duoi}",
        )
    )
    ngoai = dataclasses.replace(q.thu_ngan, clinic_id=khac)
    assert (await svc.lich_su(identity=ngoai, tim=f"TT-{q.duoi}"))["khach"] == []
    with pytest.raises(NotFoundError):
        await svc.phieu(identity=ngoai, id_=cycle)


def test_cua_so_thu_va_xuat_theo_quyen_thu() -> None:
    """Sổ, tệp xuất và phiếu in đứng sau CÙNG cửa quyền thu tiền của quầy."""
    from clinicai.api.v1.routers import cashier

    can = {"/cashier/lich-su", "/cashier/lich-su.csv", "/cashier/phieu/{phieu_id}"}
    for r in cashier.router.routes:
        if getattr(r, "path", None) in can:
            deps = [d.call for d in r.dependant.dependencies]  # type: ignore[attr-defined]
            assert cashier._GUARD in deps, getattr(r, "path", "")  # noqa: SLF001
