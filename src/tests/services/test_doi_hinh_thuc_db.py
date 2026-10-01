"""V7 — đổi hình thức thu (TM / CK / QR) sau khi đã thu, với database thật.

Kịch bản: thu TIỀN MẶT 150k → dược sĩ (chỉ có khối thu THUỐC) đổi sang CHUYỂN
KHOẢN kèm mã → mọi chỗ đọc hình thức thấy hình thức mới (lịch sử quầy, 5 ô tổng,
bảng giao dịch, bản in, báo cáo cuối ngày + mục "Đổi hình thức"), sổ gốc
`payment_cycle.method` giữ nguyên. Phiếu đã huỷ / có hoàn không đổi được; sổ
đổi chỉ thêm; hai người đổi cùng lúc thì người sau bị từ chối.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.doi_hinh_thuc_service import (
    KHONG_DOI_CO_HOAN,
    KHONG_DOI_DA_HUY,
    DoiHinhThucService,
)
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _theo(ds: list[dict[str, Any]], ma: str) -> int:
    return next((int(o["thu"]) for o in ds if o["ma"] == ma), 0)


async def test_doi_hinh_thuc_moi_cho_doc_deu_thay(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    bc = BaoCaoCuoiNgayService(pool)
    truoc = await bc.bao_cao(identity=ql)
    tm = await _thu_pt(q, "CASH")
    cid = tm["payment_cycle_id"]
    giua = await bc.bao_cao(identity=ql)

    # Dược sĩ — chỉ giữ khối thu THUỐC — đổi được phiếu DỊCH VỤ ("mở hết").
    kq = await DoiHinhThucService(pool).doi(
        identity=q.duoc_si,
        payment_cycle_id=cid,
        hinh_thuc="TRANSFER",
        hinh_thuc_cu="CASH",
        reference="  FT30090001 ",
        ly_do="Khách chuyển khoản, bấm nhầm tiền mặt",
    )
    assert kq == {
        "payment_cycle_id": cid,
        "hinh_thuc": "TRANSFER",
        "hinh_thuc_cu": "CASH",
        "chia": None,
    }

    # Sổ gốc bất biến; sổ đổi có đúng một dòng.
    assert (
        await pool.fetchval(
            "SELECT method FROM payment_cycle WHERE payment_cycle_id = $1::uuid", cid
        )
        == "CASH"
    )
    dong = await pool.fetch(
        "SELECT method_cu, method_moi, reference, boi::text FROM"
        " payment_cycle_doi_hinh_thuc WHERE cycle_id = $1::uuid",
        cid,
    )
    assert [tuple(r) for r in dong] == [
        ("CASH", "TRANSFER", "FT30090001", q.duoc_si.staff_id)
    ]

    # Sự kiện + nhật ký.
    assert (
        await pool.fetchval(
            "SELECT payload->>'sang' FROM domain_event"
            " WHERE event_type = 'payment.method_changed' AND aggregate_id = $1::uuid",
            cid,
        )
        == "TRANSFER"
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type = 'payment.method_changed'"
            " AND aggregate_id = $1::uuid",
            cid,
        )
        == 1
    )

    # Lịch sử quầy thu: hình thức hiệu lực + cờ + lịch sử đổi; 5 ô tổng dời tiền.
    ls = await QuayThuService(pool).lich_su(identity=q.thu_ngan)
    g = next(k for k in ls["khach"] if k["visit_id"] == q.visit_id)
    thu = next(s for s in g["su_kien"] if s["loai"] == "thu")
    assert thu["hinh_thuc"] == "TRANSFER"
    assert thu["doi_hinh_thuc"]["duoc"] is True
    assert thu["doi_hinh_thuc"]["hinh_thuc_goc"] == "CASH"
    assert [(d["tu"], d["sang"]) for d in thu["doi_hinh_thuc"]["lan_doi"]] == [
        ("CASH", "TRANSFER")
    ]
    assert g["phieu"][0]["hinh_thuc"] == "TRANSFER"
    loc_ck = await QuayThuService(pool).lich_su(
        identity=q.thu_ngan, hinh_thuc="TRANSFER"
    )
    assert any(k["visit_id"] == q.visit_id for k in loc_ck["khach"])

    # Bảng giao dịch (tab Đã thanh toán hôm nay): hình thức + mã hiệu lực.
    gd = await CashierBoardService(pool).giao_dich(
        identity=q.thu_ngan, tu=None, den=None
    )
    dong_gd = next(d for d in gd["giao_dich"] if d["id"] == cid)
    assert (dong_gd["phuong_thuc"], dong_gd["ma_giao_dich"]) == (
        "TRANSFER",
        "FT30090001",
    )
    assert dong_gd["doi_hinh_thuc"]["duoc"] is True

    # Bản in phiếu thu.
    phieu = await QuayThuService(pool).phieu(identity=q.thu_ngan, id_=cid)
    assert phieu["hinh_thuc"] == "TRANSFER"

    # Báo cáo cuối ngày: 150k chuyển từ Tiền mặt sang Chuyển khoản; KHÔNG là huỷ.
    sau = await bc.bao_cao(identity=ql)
    assert (
        _theo(giua["theo_hinh_thuc"], "CASH") - _theo(truoc["theo_hinh_thuc"], "CASH")
        == 150_000
    )
    assert _theo(sau["theo_hinh_thuc"], "CASH") == _theo(
        truoc["theo_hinh_thuc"], "CASH"
    )
    assert (
        _theo(sau["theo_hinh_thuc"], "TRANSFER")
        - _theo(truoc["theo_hinh_thuc"], "TRANSFER")
        == 150_000
    )
    assert sau["tong"]["huy"] == truoc["tong"]["huy"]
    moi = [o for o in sau["doi_hinh_thuc"] if o["cycle_id"] == cid]
    assert [(o["tu"], o["sang"], o["so_tien"], o["nguoi"]) for o in moi] == [
        ("CASH", "TRANSFER", 150_000, q.duoc_si.full_name)
    ]

    # Gửi lại đúng hình thức hiện hành → thành công, không thêm dòng.
    lai = await DoiHinhThucService(pool).doi(
        identity=q.thu_ngan, payment_cycle_id=cid, hinh_thuc="TRANSFER"
    )
    assert lai["da_la_hinh_thuc_nay"] is True
    # Màn còn thấy hình thức cũ (người khác vừa đổi) → 409, không đè.
    with pytest.raises(ConflictError, match="vừa được người khác đổi"):
        await DoiHinhThucService(pool).doi(
            identity=q.thu_ngan,
            payment_cycle_id=cid,
            hinh_thuc="CASH",
            hinh_thuc_cu="CASH",
        )
    # QR bỏ từ 01/10: máy cũ gửi "QR" = Chuyển khoản → đã là hình thức này.
    qr = await DoiHinhThucService(pool).doi(
        identity=q.thu_ngan,
        payment_cycle_id=cid,
        hinh_thuc="QR",
        hinh_thuc_cu="TRANSFER",
    )
    assert qr["da_la_hinh_thuc_nay"] is True
    gd = await CashierBoardService(pool).giao_dich(
        identity=q.thu_ngan, tu=None, den=None
    )
    dong_gd = next(d for d in gd["giao_dich"] if d["id"] == cid)
    assert dong_gd["phuong_thuc"] == "TRANSFER"
    # Đổi về tiền mặt bỏ mã.
    await DoiHinhThucService(pool).doi(
        identity=q.thu_ngan,
        payment_cycle_id=cid,
        hinh_thuc="CASH",
        reference="bỏ qua vì tiền mặt",
    )
    assert (
        await pool.fetchval(
            "SELECT hinh_thuc_hieu_luc(clinic_id, payment_cycle_id, method)"
            " FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
            cid,
        )
        == "CASH"
    )
    assert (
        await pool.fetchval(
            "SELECT reference FROM payment_cycle_doi_hinh_thuc"
            " WHERE cycle_id = $1::uuid ORDER BY id DESC LIMIT 1",
            cid,
        )
        is None
    )

    with pytest.raises(ValidationError):
        await DoiHinhThucService(pool).doi(
            identity=q.thu_ngan, payment_cycle_id=cid, hinh_thuc="CARD"
        )


async def test_khong_doi_khi_da_huy_hoac_co_hoan(pool: asyncpg.Pool) -> None:
    # Phiếu đã huỷ.
    q = await tao_quay(pool)
    tm = await _thu_pt(q, "CASH")
    await PaymentService(pool).void_payment(
        payment_cycle_id=tm["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Bấm nhầm khách",
        identity=q.thu_ngan,
    )
    with pytest.raises(ConflictError, match=KHONG_DOI_DA_HUY):
        await DoiHinhThucService(pool).doi(
            identity=q.thu_ngan, payment_cycle_id=tm["payment_cycle_id"], hinh_thuc="QR"
        )
    ls = await QuayThuService(pool).lich_su(identity=q.thu_ngan)
    g = next(k for k in ls["khach"] if k["visit_id"] == q.visit_id)
    thu = next(s for s in g["su_kien"] if s["loai"] == "thu")
    assert thu["doi_hinh_thuc"]["duoc"] is False

    # Phiếu có khoản hoàn.
    q2 = await tao_quay(pool)
    ql = await _nguoi_vai(q2, "MANAGEMENT")
    tm2 = await _thu_pt(q2, "CASH")
    dong = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " LIMIT 1",
        tm2["payment_cycle_id"],
    )
    await HoanTienService(pool).tao(
        identity=ql,
        payment_cycle_id=tm2["payment_cycle_id"],
        visit_id=q2.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong, "so_luong": 1}],
        method="CASH",
        reason="khách đổi ý không khám",
    )
    with pytest.raises(ConflictError, match=KHONG_DOI_CO_HOAN):
        await DoiHinhThucService(pool).doi(
            identity=q2.thu_ngan,
            payment_cycle_id=tm2["payment_cycle_id"],
            hinh_thuc="TRANSFER",
        )
    gd = await CashierBoardService(pool).giao_dich(
        identity=q2.thu_ngan, tu=None, den=None
    )
    dong_gd = next(d for d in gd["giao_dich"] if d["id"] == tm2["payment_cycle_id"])
    assert dong_gd["doi_hinh_thuc"] == {
        "duoc": False,
        "ly_do_khong": KHONG_DOI_CO_HOAN,
        "hinh_thuc_goc": "CASH",
        "lan_doi": [],
    }


async def test_so_doi_chi_them_va_db_chan_ghi_thang(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    tm = await _thu_pt(q, "CASH")
    cid = tm["payment_cycle_id"]
    await DoiHinhThucService(pool).doi(
        identity=q.thu_ngan, payment_cycle_id=cid, hinh_thuc="QR"
    )
    for lenh in (
        "UPDATE payment_cycle_doi_hinh_thuc SET method_moi = 'CASH'"
        " WHERE cycle_id = $1::uuid",
        "DELETE FROM payment_cycle_doi_hinh_thuc WHERE cycle_id = $1::uuid",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await pool.execute(lenh, cid)
    # Guard cũ của payment_cycle vẫn giữ: không sửa thẳng method.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE payment_cycle SET method = 'QR' WHERE payment_cycle_id = $1::uuid",
            cid,
        )
    # Ghi thẳng với method_cu sai (tranh chấp) → trigger chặn.
    with pytest.raises(asyncpg.CheckViolationError, match="vừa được đổi"):
        await pool.execute(
            "INSERT INTO payment_cycle_doi_hinh_thuc (clinic_id, cycle_id, method_cu,"
            " method_moi, boi)"
            " VALUES ($1::uuid, $2::uuid, 'CASH', 'TRANSFER', $3::uuid)",
            q.thu_ngan.clinic_id,
            cid,
            q.thu_ngan.staff_id,
        )
    # Ghi thẳng lên phiếu đã huỷ → trigger chặn.
    q2 = await tao_quay(pool)
    tm2 = await _thu_pt(q2, "CASH")
    await PaymentService(pool).void_payment(
        payment_cycle_id=tm2["payment_cycle_id"],
        visit_id=q2.visit_id,
        kind="dich_vu",
        reason="Bấm nhầm khách",
        identity=q2.thu_ngan,
    )
    with pytest.raises(asyncpg.CheckViolationError, match="đang đã thu"):
        await pool.execute(
            "INSERT INTO payment_cycle_doi_hinh_thuc (clinic_id, cycle_id, method_cu,"
            " method_moi, boi) VALUES ($1::uuid, $2::uuid, 'CASH', 'QR', $3::uuid)",
            q2.thu_ngan.clinic_id,
            tm2["payment_cycle_id"],
            q2.thu_ngan.staff_id,
        )
    # Phòng khám khác không đổi được phiếu của phòng này (404).
    khac = str(
        await pool.fetchval(
            "INSERT INTO clinic (code, name, timezone) VALUES ($1, 'PK khác',"
            " 'Asia/Ho_Chi_Minh') RETURNING id::text",
            f"V7{uuid.uuid4().hex[:6]}",
        )
    )
    import dataclasses

    from clinicai.api.exceptions import NotFoundError
    from clinicai.core.exceptions import SafetyGateError

    with pytest.raises((NotFoundError, SafetyGateError)):
        await DoiHinhThucService(pool).doi(
            identity=dataclasses.replace(q.thu_ngan, clinic_id=khac),
            payment_cycle_id=cid,
            hinh_thuc="TRANSFER",
        )
