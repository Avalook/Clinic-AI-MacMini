"""Tách hẳn thu tiền thuốc và thu tiền dịch vụ (Tuyền 01/10/2026) — DB thật.

"Không cho node thuốc thu hộ tiền dịch vụ": quầy thuốc chỉ thu / xem / hoàn tác
tiền thuốc, quầy dịch vụ chỉ tiền dịch vụ. Máy chủ gác bằng ``quay`` (mọi lệnh
thu / xác minh / huỷ / hoàn tác), sổ giao dịch + bảng thu + báo cáo + phiếu thu
tách theo loại, Postgres ép dòng hoá đơn khớp loại lần thu.

DB dùng chung với bài khác → so HIỆU (sau − trước), không đếm tuyệt đối.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.payment_service import (
    PaymentService,
    QuayKhongThuLoaiNayError,
    kiem_quay,
)
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_quay_thu_mot_hoa_don_db import _dong, _kich_ban
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt
from tests.services.test_tien_thuoc_cp3_db import _san_sang
from tests.services.test_tien_thuoc_cp3_db import _thu as _thu_thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

pytestmark = pytest.mark.db


# ── Luật thuần ─────────────────────────────────────────────────────────────


def test_kiem_quay_thuan() -> None:
    kiem_quay(None, "thuoc")  # lệnh không đi qua quầy: chỉ còn cửa quyền
    kiem_quay("thuoc", "thuoc")
    kiem_quay("dich_vu", "dich_vu")
    with pytest.raises(QuayKhongThuLoaiNayError) as e:
        kiem_quay("thuoc", "dich_vu")
    assert e.value.status_code == 409
    assert "Thu tiền thuốc" in str(e.value) and "Thu tiền dịch vụ" in str(e.value)
    with pytest.raises(QuayKhongThuLoaiNayError):
        kiem_quay("dich_vu", "thuoc")
    with pytest.raises(ValidationError):
        kiem_quay("quay-la", "thuoc")


# ── Máy chủ chặn thu chéo ở MỌI lệnh ───────────────────────────────────────


@pytest.mark.asyncio
async def test_moi_lenh_thu_cheo_bi_chan_khong_ghi_gi(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q)
    svc = PaymentService(pool)

    # Thu: quầy thuốc đòi thu dịch vụ / quầy dịch vụ đòi thu thuốc.
    for kind, quay in (("dich_vu", "thuoc"), ("thuoc", "dich_vu")):
        with pytest.raises(QuayKhongThuLoaiNayError):
            await svc.record_payment(
                visit_id=q.visit_id,
                kind=kind,
                amount=None,
                clinic_patient_id=None,
                method="CASH",
                identity=q.thu_ngan,
                idempotency_key=f"tach-{uuid.uuid4().hex}",
                quay=quay,
            )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        == 0
    )

    # Chuyển khoản dịch vụ chờ xác minh: xác minh / huỷ chờ từ quầy thuốc → 409.
    ck = await _thu_pt(q, "TRANSFER")
    assert ck["status"] == "PENDING_VERIFICATION"
    with pytest.raises(QuayKhongThuLoaiNayError):
        await svc.xac_minh_dien_tu(
            payment_cycle_id=ck["payment_cycle_id"],
            visit_id=q.visit_id,
            kind="dich_vu",
            reference="FT1",
            identity=q.thu_ngan,
            quay="thuoc",
        )
    with pytest.raises(QuayKhongThuLoaiNayError):
        await svc.huy_cho_xac_minh(
            payment_cycle_id=ck["payment_cycle_id"],
            visit_id=q.visit_id,
            kind="dich_vu",
            reason="Khách không chuyển",
            identity=q.thu_ngan,
            quay="thuoc",
        )
    with pytest.raises(QuayKhongThuLoaiNayError):
        await svc.hoan_tac(
            payment_cycle_id=ck["payment_cycle_id"],
            ly_do=None,
            identity=q.thu_ngan,
            quay="thuoc",
        )
    # Đúng quầy: xác minh được, rồi void từ quầy sai bị chặn, đúng quầy được.
    xm = await svc.xac_minh_dien_tu(
        payment_cycle_id=ck["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        reference="FT1",
        identity=q.thu_ngan,
        quay="dich_vu",
    )
    assert xm["status"] == "PAID"
    with pytest.raises(QuayKhongThuLoaiNayError):
        await svc.void_payment(
            payment_cycle_id=ck["payment_cycle_id"],
            visit_id=q.visit_id,
            kind="dich_vu",
            reason="Bấm nhầm khách",
            identity=q.thu_ngan,
            quay="thuoc",
        )


@pytest.mark.asyncio
async def test_hoan_tac_van_chay_o_moi_quay(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hoàn tác lần thu vẫn làm được ở từng quầy — chỉ lần thu của quầy ấy."""
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    dv = await _thu_pt(q, "CASH")
    await _san_sang(q)
    th = await _thu_thuoc(q)
    svc = PaymentService(pool)
    with pytest.raises(QuayKhongThuLoaiNayError):
        await svc.hoan_tac(
            payment_cycle_id=th["payment_cycle_id"],
            ly_do=None,
            identity=q.thu_ngan,
            quay="dich_vu",
        )
    r = await svc.hoan_tac(
        payment_cycle_id=th["payment_cycle_id"],
        ly_do="thu nhầm",
        identity=q.thu_ngan,
        quay="thuoc",
    )
    assert (r["status"], r["kind"]) == ("VOIDED", "thuoc")
    r = await svc.hoan_tac(
        payment_cycle_id=dv["payment_cycle_id"],
        ly_do="thu nhầm",
        identity=q.thu_ngan,
        quay="dich_vu",
    )
    assert (r["status"], r["kind"]) == ("VOIDED", "dich_vu")


# ── Lịch sử / bảng thu / báo cáo tách riêng ────────────────────────────────


@pytest.mark.asyncio
async def test_so_giao_dich_bang_thu_va_bao_cao_tach_rieng(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    bao_cao = BaoCaoCuoiNgayService(pool)
    truoc = {
        k: await bao_cao.bao_cao(identity=ql, loai=k) for k in ("dich_vu", "thuoc")
    }
    truoc_ca = await bao_cao.bao_cao(identity=ql)

    dv = await _thu_pt(q, "CASH")
    await _san_sang(q)
    th = await _thu_thuoc(q)
    tien_dv = 150_000
    tien_thuoc = int(
        await pool.fetchval(
            "SELECT amount FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
            th["payment_cycle_id"],
        )
    )
    assert tien_thuoc > 0

    # Sổ giao dịch: mỗi quầy chỉ thấy lần thu của loại mình.
    board = CashierBoardService(pool)
    gd = {
        k: await board.giao_dich(identity=q.thu_ngan, tu=None, den=None, kind=k)
        for k in ("thuoc", "dich_vu", None)
    }
    assert {g["loai"] for g in gd["thuoc"]["giao_dich"]} == {"thuoc"}
    assert {g["loai"] for g in gd["dich_vu"]["giao_dich"]} == {"dich_vu"}
    ids = {k: {g["id"] for g in v["giao_dich"]} for k, v in gd.items()}
    assert th["payment_cycle_id"] in ids["thuoc"]
    assert dv["payment_cycle_id"] not in ids["thuoc"]
    assert dv["payment_cycle_id"] in ids["dich_vu"]
    assert th["payment_cycle_id"] not in ids["dich_vu"]
    # Không truyền loại (script cũ) / loại rác: cả hai, như trước.
    assert {th["payment_cycle_id"], dv["payment_cycle_id"]} <= ids[None]
    rac = await board.giao_dich(identity=q.thu_ngan, tu=None, den=None, kind="rác")
    assert {th["payment_cycle_id"], dv["payment_cycle_id"]} <= {
        g["id"] for g in rac["giao_dich"]
    }

    # Lịch sử gom theo khách: quầy thuốc không kèm dịch vụ đối tác / phòng.
    ls_thuoc = await QuayThuService(pool).lich_su(
        identity=q.thu_ngan, kind="thuoc", chi_tiet=True
    )
    [khach_thuoc] = [k for k in ls_thuoc["khach"] if k["visit_id"] == q.visit_id]
    assert [p["id"] for p in khach_thuoc["phieu"]] == [th["payment_cycle_id"]]
    assert khach_thuoc["doi_tac"] == []

    # Bảng thu: quầy thuốc không trả "đã thu" của dịch vụ; quầy dịch vụ ngược lại.
    b_thuoc = await board.board(identity=q.thu_ngan, modes=["thuoc"])
    b_dv = await board.board(identity=q.thu_ngan, modes=["dich_vu"])
    assert {p["kind"] for p in b_thuoc["paid"]} <= {"thuoc"}
    assert {p["kind"] for p in b_dv["paid"]} <= {"dich_vu"}
    assert all(i["drugs"] for i in b_thuoc["items"])
    assert all(c["kind"] == "thuoc" for c in b_thuoc["cho_xac_minh"])
    assert all(c["kind"] == "dich_vu" for c in b_dv["cho_xac_minh"])

    # Báo cáo cuối ngày: tách theo loại (chỉ một loại khi chọn loại).
    sau = {k: await bao_cao.bao_cao(identity=ql, loai=k) for k in ("dich_vu", "thuoc")}
    sau_ca = await bao_cao.bao_cao(identity=ql)

    def hieu(s: dict[str, Any], t: dict[str, Any]) -> int:
        return int(s["tong"]["thuc_thu"]) - int(t["tong"]["thuc_thu"])

    assert hieu(sau["dich_vu"], truoc["dich_vu"]) == tien_dv
    assert hieu(sau["thuoc"], truoc["thuoc"]) == tien_thuoc
    assert hieu(sau_ca, truoc_ca) == tien_dv + tien_thuoc
    assert (sau["dich_vu"]["loai"], sau["thuoc"]["loai"], sau_ca["loai"]) == (
        "dich_vu",
        "thuoc",
        None,
    )
    # Chọn loại thì ô "theo loại" của loại kia đứng im ở 0 (không cộng lẫn).
    for k, kia in (("dich_vu", "thuoc"), ("thuoc", "dich_vu")):
        o_kia = next(o for o in sau[k]["theo_loai"] if o["ma"] == kia)
        assert o_kia["thu"] == 0
    # Loại rác = cả hai.
    rac_bc = await bao_cao.bao_cao(identity=ql, loai="rác")
    assert rac_bc["loai"] is None


# ── Phiếu thu không lẫn ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_phieu_thuoc_khong_in_dich_vu_khach_tra_doi_tac(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q, sa, soi, hpv = await _kich_ban(pool)
    qt = (await _dong(q))["quay_thu"]
    dv = await PaymentService(pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        amount=qt["tong"],
        bill_revision=qt["revision"],
        clinic_patient_id=None,
        identity=q.thu_ngan,
        method="CASH",
        idempotency_key=f"tach-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [sa, soi, hpv],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
        quay="dich_vu",
    )
    await _san_sang(q)
    th = await _thu_thuoc(q)
    phieu = QuayThuService(pool)
    p_dv = await phieu.phieu(identity=q.thu_ngan, id_=dv["payment_cycle_id"])
    p_th = await phieu.phieu(identity=q.thu_ngan, id_=th["payment_cycle_id"])
    # Phiếu dịch vụ ghi dịch vụ khách trả đối tác (không cộng); phiếu thuốc thì
    # không — chỉ dòng thuốc.
    assert [d["ten"] for d in p_dv["doi_tac"]] == [f"HPV-{q.duoi}"]
    assert (p_th["kind"], p_th["doi_tac"]) == ("thuoc", [])
    assert p_th["dong"] and not any(
        d["ten"].startswith(("SA-", "SOI-", "HPV-")) for d in p_th["dong"]
    )
    assert not any(d["ten"].startswith("Thuốc") for d in p_dv["dong"])


# ── Postgres ép dòng hoá đơn khớp loại lần thu ─────────────────────────────


@pytest.mark.asyncio
async def test_dong_hoa_don_phai_khop_loai_lan_thu(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    dv = await _thu_pt(q, "CASH")
    await _san_sang(q)
    th = await _thu_thuoc(q)
    lan = {
        k: await pool.fetchrow(
            "SELECT clinic_id::text AS c, payment_id::text AS p FROM payment_cycle"
            " WHERE payment_cycle_id = $1::uuid",
            v["payment_cycle_id"],
        )
        for k, v in (("dich_vu", dv), ("thuoc", th))
    }
    sql = (
        "INSERT INTO payment_bill_line (clinic_id, payment_id, payment_cycle_id,"
        " visit_id, kind, source_type, source_id, name_snapshot, quantity,"
        " unit_price, line_total, billing_owner)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, 'x', 1,"
        " 1000, 1000, 'CLINIC')"
    )
    # Dòng thuốc vào lần thu dịch vụ, dòng chỉ định vào lần thu thuốc → CHẶN.
    for kind_lan, kind_dong, nguon in (
        ("dich_vu", "thuoc", "prescription"),  # khác loại lần thu → trigger
        ("thuoc", "dich_vu", "service_order"),  # khác loại lần thu → trigger
        ("thuoc", "dich_vu", "exam"),  # khác loại lần thu → trigger
        ("thuoc", "thuoc", "service_order"),  # loại ↔ nguồn lệch → CHECK
        ("dich_vu", "dich_vu", "prescription"),  # loại ↔ nguồn lệch → CHECK
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            await pool.execute(
                sql,
                lan[kind_lan]["c"],
                lan[kind_lan]["p"],
                (dv if kind_lan == "dich_vu" else th)["payment_cycle_id"],
                q.visit_id,
                kind_dong,
                nguon,
                uuid.uuid4().hex,
            )
    # Cặp khớp thì ghi được (không bị ràng buộc chặn nhầm).
    # Ghi trong giao dịch rồi cuộn lại: không để dòng thử trong sổ chỉ-thêm.
    with pytest.raises(_CuonLai):
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    sql,
                    lan["thuoc"]["c"],
                    lan["thuoc"]["p"],
                    th["payment_cycle_id"],
                    q.visit_id,
                    "thuoc",
                    "prescription",
                    uuid.uuid4().hex,
                )
                raise _CuonLai


class _CuonLai(Exception):  # noqa: N818
    pass
