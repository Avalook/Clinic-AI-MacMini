"""Báo cáo cuối ngày (29/09/2026) — với database thật, qua đúng lệnh thu/huỷ/hoàn.

Kịch bản: lượt 1 thu TIỀN MẶT 700k (khám + SÂ + Soi; HPV khách trả đối tác)
rồi hoàn Soi 300k · lượt 2 CHUYỂN KHOẢN 150k (xác minh) · lượt 3 tiền mặt 150k
rồi HUỶ phiếu · lượt 4 THUỐC tiền mặt · đối tác ghi đã thu HPV 900k.

DB dùng chung với bài khác cùng ngày → so HIỆU (sau − trước), không đếm tuyệt đối.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_quay_thu_mot_hoa_don_db import _dong, _kich_ban
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt, _xm
from tests.services.test_tien_thuoc_cp3_db import _san_sang
from tests.services.test_tien_thuoc_cp3_db import _thu as _thu_thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


def _hieu(sau: dict[str, Any], truoc: dict[str, Any], *khoa: str) -> tuple[int, ...]:
    return tuple(int(sau[k]) - int(truoc[k]) for k in khoa)


def _theo(ds: list[dict[str, Any]], ma: str) -> dict[str, Any]:
    return next(
        (o for o in ds if o["ma"] == ma), {"thu": 0, "huy": 0, "hoan": 0, "thuc_thu": 0}
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_bao_cao_cuoi_ngay_tong_dung_tung_dong(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    svc = BaoCaoCuoiNgayService(pool)
    q1, sa, soi, hpv = await _kich_ban(pool)
    ql = await _nguoi_vai(q1, "MANAGEMENT")
    truoc = await svc.bao_cao(identity=ql)

    # Lượt 1: tiền mặt 700k, rồi hoàn Soi 300k (tiền mặt → hoàn xong ngay).
    qt = (await _dong(q1))["quay_thu"]
    kq = await PaymentService(pool).record_payment(
        visit_id=q1.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q1.thu_ngan,
        method="CASH",
        idempotency_key=f"bccn-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi, hpv],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
    )
    assert kq["status"] == "PAID"
    dong_soi = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " AND source_id = $2",
        kq["payment_cycle_id"],
        soi,
    )
    await HoanTienService(pool).tao(
        identity=ql,
        payment_cycle_id=kq["payment_cycle_id"],
        visit_id=q1.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong_soi, "so_luong": 1}],
        method="CASH",
        reason="khách không làm soi",
    )
    # Đối tác ghi đã thu HPV 900k — tham khảo, không cộng.
    await pool.execute(
        "INSERT INTO doi_tac_thanh_toan (clinic_id, service_order_id, so_tien,"
        " hinh_thuc, ghi_boi) VALUES ($1::uuid, $2::uuid, 900000, 'CASH', $3::uuid)",
        q1.thu_ngan.clinic_id,
        hpv,
        ql.staff_id,
    )

    # Lượt 2: chuyển khoản 150k, xác minh.
    q2 = await tao_quay(pool)
    ck = await _thu_pt(q2, "TRANSFER")
    await _xm(q2, ck["payment_cycle_id"], "FT29090001")

    # Lượt 3: tiền mặt 150k rồi huỷ phiếu.
    q3 = await tao_quay(pool)
    tm = await _thu_pt(q3, "CASH")
    await PaymentService(pool).void_payment(
        payment_cycle_id=tm["payment_cycle_id"],
        visit_id=q3.visit_id,
        kind="dich_vu",
        reason="Bấm nhầm khách",
        identity=q3.thu_ngan,
    )

    # Lượt 4: thuốc tiền mặt.
    q4 = await tao_quay(pool)
    await _san_sang(q4)
    th = await _thu_thuoc(q4)
    tien_thuoc = int(
        await pool.fetchval(
            "SELECT amount FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
            th["payment_cycle_id"],
        )
    )
    assert tien_thuoc > 0

    sau = await svc.bao_cao(identity=ql, tu="rác", den="2026-99-99")
    assert sau["tu"] == sau["den"] == truoc["tu"]

    tong = _hieu(sau["tong"], truoc["tong"], "thu", "huy", "hoan", "thuc_thu")
    assert tong == (
        700_000 + 150_000 + 150_000 + tien_thuoc,
        150_000,
        300_000,
        700_000 + 150_000 - 300_000 + tien_thuoc,
    )
    # Tiền mặt / chuyển khoản.
    tm_s, tm_t = (
        _theo(sau["theo_hinh_thuc"], "CASH"),
        _theo(truoc["theo_hinh_thuc"], "CASH"),
    )
    assert _hieu(tm_s, tm_t, "thu", "huy", "hoan", "thuc_thu") == (
        700_000 + 150_000 + tien_thuoc,
        150_000,
        300_000,
        700_000 - 300_000 + tien_thuoc,
    )
    ck_s, ck_t = (
        _theo(sau["theo_hinh_thuc"], "TRANSFER"),
        _theo(truoc["theo_hinh_thuc"], "TRANSFER"),
    )
    assert _hieu(ck_s, ck_t, "thu", "thuc_thu") == (150_000, 150_000)
    # Dịch vụ vs thuốc.
    assert _hieu(
        _theo(sau["theo_loai"], "dich_vu"),
        _theo(truoc["theo_loai"], "dich_vu"),
        "thuc_thu",
    ) == (550_000,)
    assert _hieu(
        _theo(sau["theo_loai"], "thuoc"), _theo(truoc["theo_loai"], "thuoc"), "thuc_thu"
    ) == (tien_thuoc,)
    # Theo người thu (mỗi lượt một thu ngân riêng).
    nguoi = {o["ten"]: o for o in sau["theo_nguoi_thu"]}
    assert nguoi[q1.thu_ngan.full_name]["thuc_thu"] == 700_000
    assert (
        nguoi[q3.thu_ngan.full_name]["thu"],
        nguoi[q3.thu_ngan.full_name]["thuc_thu"],
    ) == (
        150_000,
        0,
    )
    # Hoàn + huỷ: ai, lúc nào, lý do.
    cu = {o["id"] for o in truoc["hoan_huy"]}
    moi = {
        (o["loai"], o["ly_do"], o["so_tien"])
        for o in sau["hoan_huy"]
        if o["id"] not in cu
    }
    assert moi == {
        ("hoan", "khách không làm soi", 300_000),
        ("huy", "Bấm nhầm khách", 150_000),
    }
    assert all(o["nguoi"] and o["luc"] for o in sau["hoan_huy"])
    # Khách: 3 lượt tạo sau mốc "trước" (lượt 1 dựng trước mốc); 3 lượt đã thu
    # (lượt 3 chỉ có phiếu huỷ → không tính).
    assert _hieu(sau["khach"], truoc["khach"], "so_luot_kham", "so_luot_da_thu") == (
        3,
        3,
    )
    # Đối tác: tham khảo, không vào thực thu.
    assert sau["doi_tac"]["tong"] - truoc["doi_tac"]["tong"] == 900_000
    top = {o["ten"]: o["doanh_thu"] for o in sau["top_dich_vu"]}
    assert top.get(f"SOI-{q1.duoi}") == 300_000

    # Khác phòng khám: không thấy gì của phòng này.
    khac = str(
        await pool.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"B{q1.duoi}",
        )
    )
    ngoai = await svc.bao_cao(identity=dataclasses.replace(ql, clinic_id=khac))
    assert ngoai["tong"]["thu"] == 0 and ngoai["hoan_huy"] == []


def test_cua_bao_cao_cuoi_ngay_la_report_view() -> None:
    from clinicai.api.v1.routers import reports

    for p in ("/reports/cuoi-ngay", "/reports/cuoi-ngay.csv"):
        route = next(r for r in reports.router.routes if getattr(r, "path", "") == p)
        deps = [d.call for d in route.dependant.dependencies]  # type: ignore[attr-defined]
        assert reports._READ_GUARD in deps
