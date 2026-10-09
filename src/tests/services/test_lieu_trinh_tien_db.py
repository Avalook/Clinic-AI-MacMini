"""Liệu trình — TIỀN (B2): trả trước k buổi, phủ buổi, cổng làm, nợ khi về,
huỷ phiếu / hoàn tiền, bất biến, tranh chấp.

Số # trong tên bài là dòng bảng tình huống ``docs/KE-HOACH-LIEU-TRINH.md`` Phần
B. Lượt dùng loại khám Điều trị của chính ca (không tự thu phí khám) — hoá đơn
chỉ có buổi điều trị + dòng trả trước, đếm tiền rõ ràng.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.bill_service import ghep_dich_vu, hoa_don_con_no
from clinicai.services.cong_no_service import loc_no_dich_vu, no_khi_ve
from clinicai.services.finance_gate import PAID, states_for_orders
from clinicai.services.ho_so_dich_vu import sinh_chi_dinh_dieu_tri
from clinicai.services.hoan_tac_service import tien_thua_cua_luot
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lieu_trinh_tien import (
    LieuTrinhTienService,
    doc_so_buoi_tra,
    toi_da_tra_truoc,
)
from clinicai.services.payment_service import PaymentService
from clinicai.services.quay_thu_service import dung_hoa_don_quay
from clinicai.services.service_execution_service import cua_tien_ban_kham
from tests.services.test_lieu_trinh_db import (
    GIA,
    LT,
    _khoa,
    buoi_song,
    chi_dinh,
    dang_ky,
    dat_trang_thai,
    doc,
    dung_ca,
    lam_xong,
    luot,
    tao,
)
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


def tien(ca: LT) -> LieuTrinhTienService:
    return LieuTrinhTienService(ca.pool)


async def hoa_don(ca: LT, visit: str) -> Any:
    async with ca.pool.acquire() as conn:
        return await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)


async def thu(ca: LT, visit: str) -> str:
    """Thu tiền mặt đúng hoá đơn còn nợ; trả mã lần thu."""
    hd = await hoa_don(ca, visit)
    kq = await PaymentService(ca.pool).record_payment(
        visit_id=visit,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ca.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=_khoa(),
        quay="dich_vu",
    )
    return str(kq["payment_cycle_id"])


async def tra_truoc(
    ca: LT, visit: str, lt_id: str, so_buoi: int | str, mong: int | None = None
) -> dict[str, Any]:
    return await tien(ca).dat_tra_truoc(
        identity=ca.thu_ngan,
        visit_id=visit,
        lieu_trinh_id=lt_id,
        so_buoi=so_buoi,
        expected_so_buoi=mong,
        idempotency_key=_khoa(),
    )


async def khoi(ca: LT, visit: str, lt_id: str) -> dict[str, Any]:
    q = await tien(ca).quay(identity=ca.thu_ngan, visit_id=visit)
    (x,) = [d for d in q["lieu_trinh"] if d["id"] == lt_id]
    return dict(x)


async def lt_da_tra_truoc(ca: LT, so_buoi: int, tra: int) -> tuple[dict[str, Any], str]:
    """LT ``so_buoi`` buổi đề xuất ở lượt 1 (không làm hôm nay), CSKH đăng ký,
    lượt 2 khách trả trước ``tra`` buổi. Trả (liệu trình, lần thu)."""
    v1 = await luot(ca, dieu_tri=True, ngay_truoc=3)
    lt = await tao(ca, v1, so_buoi)
    await dang_ky(ca, lt["id"])
    v2 = await luot(ca, dieu_tri=True)
    await tra_truoc(ca, v2, lt["id"], tra)
    cyc = await thu(ca, v2)
    return await doc(ca, lt["id"]), cyc


# ── Luật thuần ──────────────────────────────────────────────────────────────


def test_toi_da_va_doc_so_buoi_tra() -> None:
    assert (
        toi_da_tra_truoc(so_buoi=10, da_tra=0, tra_le=0, cho_noi_khac=0, buoi_hom_nay=1)
        == 9
    )
    assert (
        toi_da_tra_truoc(so_buoi=3, da_tra=2, tra_le=1, cho_noi_khac=1, buoi_hom_nay=0)
        == 0
    )
    assert doc_so_buoi_tra("het", 9) == 9 and doc_so_buoi_tra(" HET ", 0) is None
    for rac in (None, "", "abc", 0, -1, 10, True, "1.5"):
        assert doc_so_buoi_tra(rac, 9) is None


def test_hoa_don_thuan_dong_tra_truoc_va_khong_phai_no() -> None:
    hd = ghep_dich_vu(
        str(uuid.uuid4()),
        None,
        [],
        lieu_trinh=[
            {
                "id": "t1",
                "lieu_trinh_id": "lt1",
                "so_buoi": 5,
                "don_gia": 400000,
                "service_name": "Ghế điện từ trường",
            }
        ],
    )
    (d,) = hd.dong
    assert (
        d.source_type == "lieu_trinh"
        and d.ten == "Ghế điện từ trường — trả trước 5 buổi"
    )
    assert hd.tong == 2_000_000 and d.ma == "lt1"
    # Trả trước chưa thu không phải NỢ khi về (khách chưa nhận dịch vụ nào).
    assert loc_no_dich_vu(hd, []) == []
    qt = dung_hoa_don_quay(hd.cho_api(), None)
    (dong,) = qt["phong_kham"]
    assert dong["loai"] == "lieu_trinh" and dong["so_buoi"] == 5
    assert dong["gia"] == 2_000_000 and dong["sua_duoc"] is False


# ── DB ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_1_10_buoi_1_tra_le_gia_chot(pool: asyncpg.Pool) -> None:
    """#1/#10: buổi 1 thu lẻ 1 × đơn giá CHỐT (bảng giá đổi sau không ảnh hưởng);
    thu xong + làm xong → DANG_LAM, còn 9."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    await pool.execute(
        "UPDATE service_price SET unit_price = 999000 WHERE id = $1::uuid", ca.sp
    )
    hd = await hoa_don(ca, v)
    assert [(d.source_id, int(d.thanh_tien or 0)) for d in hd.dong] == [(o, GIA)]
    await thu(ca, v)
    await lam_xong(ca, o)
    d = await doc(ca, lt["id"])
    assert (d["trang_thai"], d["da_lam"], d["con_lai"], d["tra_le"]) == (
        "DANG_LAM",
        1,
        9,
        1,
    )
    assert d["tien_con_lai"] == 9 * GIA


@pytest.mark.db
@pytest.mark.asyncio
async def test_2_tra_het_hom_nay_khong_thu_trung_buoi_1(pool: asyncpg.Pool) -> None:
    """#2: đề xuất 10, khách trả hết hôm nay → buổi 1 thu lẻ + trả trước 9 (tối
    đa 9, không phải 10) — tổng 10 × đơn giá, không thu trùng buổi 1."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    k = await khoi(ca, v, lt["id"])
    assert k["tra_truoc_toi_da"] == 9 and k["buoi_hom_nay_trong_hoa_don"] == 1
    kq = await tra_truoc(ca, v, lt["id"], "het")
    assert kq["so_buoi"] == 9
    hd = await hoa_don(ca, v)
    assert sorted((d.source_type, int(d.so_luong)) for d in hd.dong) == [
        ("lieu_trinh", 9),
        ("service_order", 1),
    ]
    assert hd.tong == 10 * GIA
    await thu(ca, v)
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["tra_le"], d["chua_tra"], d["con_tra_truoc"]) == (9, 1, 0, 9)
    assert not (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]
    # Hết chỗ trả trước.
    with pytest.raises(LuotKhamConflictError) as e:
        await tra_truoc(ca, v, lt["id"], 1)
    assert e.value.error_code == "TRA_VUOT"


@pytest.mark.db
@pytest.mark.asyncio
async def test_3_tra_5_toi_buoi_6_vao_hoa_don_gia_chot_goi_y_tra_them(
    pool: asyncpg.Pool,
) -> None:
    """#3: trả trước 5/10 → buổi 1..5 phủ; buổi 6 vào hoá đơn đơn giá chốt;
    quầy gợi ý trả thêm."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 10, 5)
    assert lt["da_tra"] == 5 and lt["trang_thai"] == "DANG_LAM"
    for i in range(5):
        v = await luot(ca, dieu_tri=True)
        o = await chi_dinh(ca, v)
        b = await buoi_song(ca, o)
        assert b is not None and b["tra_truoc"] and b["buoi_so"] == i + 1
        assert (await hoa_don(ca, v)).dong == []
        await lam_xong(ca, o)
    await pool.execute(
        "UPDATE service_price SET unit_price = 123000 WHERE id = $1::uuid", ca.sp
    )
    v6 = await luot(ca, dieu_tri=True)
    o6 = await chi_dinh(ca, v6)
    assert not (await buoi_song(ca, o6))["tra_truoc"]  # type: ignore[index]
    hd = await hoa_don(ca, v6)
    assert [(d.source_id, int(d.thanh_tien or 0)) for d in hd.dong] == [(o6, GIA)]
    k = await khoi(ca, v6, lt["id"])
    assert k["goi_y_tra_them"] is True and k["con_tra_truoc"] == 0
    assert k["tra_truoc_toi_da"] == 4  # 10 − 5 đã trả − buổi 6 trong hoá đơn


@pytest.mark.db
@pytest.mark.asyncio
async def test_6_19_20_luot_dieu_tri_buoi_phu_quay_0d_lam_ngay(
    pool: asyncpg.Pool,
) -> None:
    """#6/#19/#20: đã trả trước → lượt đặt lịch Điều trị → chỉ định tự sinh gắn
    buổi PHỦ → hoá đơn 0đ, cổng làm mở (dây thu trước BẬT, không tick) cả ở
    phòng lẫn bàn khám, kể cả khi quầy chưa chốt lựa chọn."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 6, 6)
    v = await luot(ca, dieu_tri=True)
    async with day_thu_truoc(pool, True):
        async with pool.acquire() as conn, conn.transaction():
            o = await sinh_chi_dinh_dieu_tri(
                conn, clinic_id=CLINIC, visit_id=v, nguoi_bam=None
            )
        assert o is not None
        b = await buoi_song(ca, o)
        assert b is not None and b["lt"] == lt["id"] and b["tra_truoc"]
        hd = await hoa_don(ca, v)
        assert hd.dong == [] and hd.tong == 0
        async with pool.acquire() as conn:
            q = (await states_for_orders(conn, CLINIC, [o]))[o]
        assert q.finance_state == PAID and q.duoc_lam
        assert cua_tien_ban_kham(
            q, selection_status="PENDING", duoc_chua_thu=False
        ) == (
            True,
            None,
            False,
        )
    chip = await ca.svc.chip(identity=ca.le_tan, visit_ids=v)
    assert chip["chi_dinh"][o]["tra_truoc"] is True


@pytest.mark.db
@pytest.mark.asyncio
async def test_buoi_phu_da_chot_khong_ket_cho_thu(pool: asyncpg.Pool) -> None:
    """Bấm thử staging 09/10: buổi đã trả trước (0đ) — quầy [Chốt dịch vụ] xong
    thì lượt RỜI chờ thu và tính là xong tiền. Trước: dòng tick 0đ bị coi là
    còn khoản, "chốt 0đ" không ghi được (hoá đơn không dòng) → kẹt mãi."""
    from clinicai.services.cashier_board_service import CashierBoardService

    ca = await dung_ca(pool)
    await lt_da_tra_truoc(ca, 6, 6)
    v = await luot(ca, dieu_tri=True)
    async with pool.acquire() as conn, conn.transaction():
        o = await sinh_chi_dinh_dieu_tri(
            conn, clinic_id=CLINIC, visit_id=v, nguoi_bam=None
        )
    assert o is not None
    bang = CashierBoardService(pool)

    async def mot() -> dict[str, Any]:
        b = await bang.board(identity=ca.thu_ngan, modes=["dich_vu"])
        (i,) = [i for i in b["items"] if i["visit_id"] == v]
        da_thu = (v, "dich_vu") in {(p["visit_id"], p["kind"]) for p in b["paid"]}
        return {**i, "da_thu": da_thu}

    # Còn chờ khách chốt (PENDING) → vẫn ở chờ thu, 0đ.
    i = await mot()
    assert i["cho_thu"] is True and i["quay_thu"]["tong"] == 0
    # Quầy chốt → SELECTED, buổi vẫn phủ → xong.
    await dat_trang_thai(ca, o, selection_status="SELECTED")
    i = await mot()
    assert (i["cho_thu"], i["da_thu"]) == (False, True)


@pytest.mark.db
@pytest.mark.asyncio
async def test_7_17_buoi_phu_huy_tra_ve_hoan_tac_gan_lai(pool: asyncpg.Pool) -> None:
    """#7: buổi phủ, khách về không làm → huỷ chỉ định → buổi trả về, số đã trả
    giữ, không thành tiền thừa. #17: hoàn tác bỏ → gắn lại + phủ lại (còn buổi
    đã trả); hết buổi đã trả thì vào hoá đơn."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 3, 1)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    assert (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]
    await dat_trang_thai(ca, o, exec_status="cancelled", execution_status="CANCELLED")
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["con_tra_truoc"], d["so_gan"]) == (1, 1, 0)
    async with pool.acquire() as conn:
        thua = await tien_thua_cua_luot(conn, CLINIC, [v])
    assert int((thua.get(v) or {}).get("tong") or 0) == 0
    # Hoàn tác bỏ → gắn lại, phủ lại.
    await dat_trang_thai(ca, o, exec_status="authorized", execution_status="PENDING")
    b = await buoi_song(ca, o)
    assert b is not None and b["tra_truoc"]
    # Một buổi khác dùng mất buổi đã trả trong lúc chỉ định này đang bỏ → hoàn
    # tác bỏ vẫn gắn lại nhưng vào hoá đơn (không âm).
    await dat_trang_thai(ca, o, exec_status="cancelled", execution_status="CANCELLED")
    v2 = await luot(ca, dieu_tri=True)
    o2 = await chi_dinh(ca, v2)
    assert (await buoi_song(ca, o2))["tra_truoc"]  # type: ignore[index]
    await dat_trang_thai(ca, o, exec_status="authorized", execution_status="PENDING")
    b = await buoi_song(ca, o)
    assert b is not None and not b["tra_truoc"]
    assert [d.source_id for d in (await hoa_don(ca, v)).dong] == [o]


@pytest.mark.db
@pytest.mark.asyncio
async def test_8_hoan_tac_xong_tien_khong_doi(pool: asyncpg.Pool) -> None:
    """#8 (phần tiền): hoàn tác Xong buổi phủ → đếm đã làm giảm, buổi vẫn phủ."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 2, 2)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)
    await dat_trang_thai(ca, o, execution_status="IN_PROGRESS")
    d = await doc(ca, lt["id"])
    assert (d["da_lam"], d["da_tra"], d["dung_tra_truoc"]) == (0, 2, 1)
    assert (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]


@pytest.mark.db
@pytest.mark.asyncio
async def test_9_hai_phong_tranh_buoi_tra_truoc_cuoi(pool: asyncpg.Pool) -> None:
    """#9: còn ĐÚNG 1 buổi đã trả, hai chỉ định cùng liệu trình sinh đồng thời
    (hai giao dịch) → đúng một buổi phủ, buổi kia vào hoá đơn — không âm."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 5, 1)
    v1 = await luot(ca, dieu_tri=True)
    v2 = await luot(ca, dieu_tri=True)
    o1, o2 = await asyncio.gather(chi_dinh(ca, v1), chi_dinh(ca, v2))
    phu = [
        bool((await buoi_song(ca, o))["tra_truoc"])  # type: ignore[index]
        for o in (o1, o2)
    ]
    assert sorted(phu) == [False, True]
    trong_hd = [len((await hoa_don(ca, v)).dong) for v in (v1, v2)]
    assert sorted(trong_hd) == [0, 1]
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["dung_tra_truoc"]) == (1, 1)
    loi = await pool.fetch(
        "SELECT lieu_trinh_id::text AS lt FROM bat_bien_lieu_trinh($1::uuid)", CLINIC
    )
    assert lt["id"] not in [r["lt"] for r in loi]


@pytest.mark.db
@pytest.mark.asyncio
async def test_11_12_giam_duoi_da_tra_dung_hoan_buoi_du(pool: asyncpg.Pool) -> None:
    """#11: giảm số buổi dưới số đã trả → 409 "hoàn tiền trước". #12 (Q5): dừng
    còn buổi đã trả → quầy chỉ dòng hoàn; hoàn quá số buổi CHƯA dùng → 409;
    hoàn đúng → giảm được số buổi; mở lại được."""
    ca = await dung_ca(pool)
    lt, cyc = await lt_da_tra_truoc(ca, 5, 5)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)  # dùng 1 buổi đã trả
    hien = await doc(ca, lt["id"])
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.dieu_chinh(
            identity=ca.bac_si,
            lieu_trinh_id=lt["id"],
            expected_revision=hien["revision"],
            so_buoi=2,
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "SO_BUOI_DUOI_DA_TRA"
    kq = await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=hien["revision"],
        ly_do="Khách chuyển viện",
        idempotency_key=_khoa(),
    )
    assert kq["lieu_trinh"]["con_tra_truoc"] == 4
    k = await khoi(ca, v, lt["id"])
    assert k["hoan_duoc_toi_da"] == 4
    (dong,) = k["dong_hoan_duoc"]
    assert dong["payment_cycle_id"] == cyc and dong["con_hoan_duoc"] == 5
    hoan = HoanTienService(pool)
    with pytest.raises(LuotKhamConflictError) as e:
        await hoan.tao(
            identity=ca.thu_ngan,
            payment_cycle_id=cyc,
            visit_id=dong["visit_id"],
            kind="dich_vu",
            dong=[
                {"payment_bill_line_id": dong["payment_bill_line_id"], "so_luong": 5}
            ],
            method="CASH",
            reason="Khách dừng liệu trình",
        )
    assert e.value.error_code == "PHU_VUOT_DA_TRA"
    await hoan.tao(
        identity=ca.thu_ngan,
        payment_cycle_id=cyc,
        visit_id=dong["visit_id"],
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong["payment_bill_line_id"], "so_luong": 4}],
        method="CASH",
        reason="Khách dừng liệu trình",
    )
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["con_tra_truoc"], d["trang_thai"]) == (1, 0, "DUNG")
    kq = await ca.svc.mo_lai(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=d["revision"],
        idempotency_key=_khoa(),
    )
    kq = await ca.svc.dieu_chinh(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=kq["lieu_trinh"]["revision"],
        so_buoi=1,
        idempotency_key=_khoa(),
    )
    assert kq["lieu_trinh"]["trang_thai"] == "XONG"


@pytest.mark.db
@pytest.mark.asyncio
async def test_16_hoan_tac_lan_thu_tra_truoc(pool: asyncpg.Pool) -> None:
    """#16: huỷ phiếu trả trước khi buổi CHƯA làm → buổi bỏ phủ, vào hoá đơn,
    dòng trả trước quay lại chờ thu. Đã làm buổi bằng tiền ấy → 409 (không hoàn
    tác quá số buổi chưa dùng; thu nhầm số buổi thì hoàn phần chưa dùng)."""
    ca = await dung_ca(pool)
    lt, cyc = await lt_da_tra_truoc(ca, 4, 2)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    assert (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]
    pay = PaymentService(pool)
    await pay.hoan_tac(
        payment_cycle_id=cyc, ly_do="Thu nhầm khách", identity=ca.thu_ngan
    )
    assert not (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]
    assert [d.source_id for d in (await hoa_don(ca, v)).dong] == [o]
    assert (await doc(ca, lt["id"]))["da_tra"] == 0
    # Thu lại: dòng trả trước quay lại chờ thu ở lượt đã trả.
    assert (await khoi(ca, v, lt["id"]))["da_tra"] == 0
    cyc_luot_cu = await pool.fetchval(
        "SELECT visit_id::text FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        cyc,
    )
    cyc2 = await thu(ca, cyc_luot_cu)
    assert (await buoi_song(ca, o))["tra_truoc"]  # type: ignore[index]
    await lam_xong(ca, o)
    with pytest.raises(ConflictError):
        await pay.hoan_tac(
            payment_cycle_id=cyc2, ly_do="Thu nhầm khách", identity=ca.thu_ngan
        )
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["dung_tra_truoc"]) == (2, 1)


@pytest.mark.db
@pytest.mark.asyncio
async def test_18_check_out_buoi_phu_da_lam_khong_no(pool: asyncpg.Pool) -> None:
    """#18: check-out lượt có buổi phủ đã làm → không nợ, không chặn."""
    ca = await dung_ca(pool)
    await lt_da_tra_truoc(ca, 3, 3)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)
    async with pool.acquire() as conn:
        no = await no_khi_ve(conn, clinic_id=CLINIC, visit_id=v)
    assert no.dong == [] and not no.chan


@pytest.mark.db
@pytest.mark.asyncio
async def test_21_bao_cao_ngay_tinh_tien_tra_truoc_ngay_thu(pool: asyncpg.Pool) -> None:
    """#21: tiền trả trước tính vào doanh thu NGÀY THU; dòng hoá đơn "‹dịch vụ›
    — trả trước 5 buổi" (so tổng trước/sau — bài khác cùng ngày không làm lệch)."""
    ca = await dung_ca(pool)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
    svc = BaoCaoCuoiNgayService(pool)

    def thu_dv(bc: dict[str, Any]) -> int:
        (d,) = [x for x in bc["theo_loai"] if x["ma"] == "dich_vu"]
        return int(d["thu"])

    truoc = thu_dv(await svc.bao_cao(identity=ql, loai="dich_vu"))
    _, cyc = await lt_da_tra_truoc(ca, 8, 5)
    sau = thu_dv(await svc.bao_cao(identity=ql, loai="dich_vu"))
    assert sau - truoc == 5 * GIA
    dong = await pool.fetchrow(
        "SELECT name_snapshot, quantity FROM payment_bill_line"
        " WHERE payment_cycle_id = $1::uuid",
        cyc,
    )
    assert dong["name_snapshot"] == f"{ca.ten} — trả trước 5 buổi"
    assert int(dong["quantity"]) == 5


@pytest.mark.db
@pytest.mark.asyncio
async def test_tra_truoc_revision_bo_va_khoa_khi_da_thu(pool: asyncpg.Pool) -> None:
    """Đặt / đổi / bỏ dòng trả trước: cầm số cũ → 409; dòng đã thu không bỏ
    được (hoàn tác lần thu trước); liệu trình đã dừng → 409; bấm lại cùng khoá
    = một lần."""
    ca = await dung_ca(pool)
    v1 = await luot(ca, dieu_tri=True)
    lt = await tao(ca, v1, 6)
    v = await luot(ca, dieu_tri=True)
    khoa = _khoa()
    a = await tien(ca).dat_tra_truoc(
        identity=ca.thu_ngan,
        visit_id=v,
        lieu_trinh_id=lt["id"],
        so_buoi=2,
        idempotency_key=khoa,
    )
    b = await tien(ca).dat_tra_truoc(
        identity=ca.thu_ngan,
        visit_id=v,
        lieu_trinh_id=lt["id"],
        so_buoi=2,
        idempotency_key=khoa,
    )
    assert a == b
    with pytest.raises(LuotKhamConflictError) as e:
        await tra_truoc(ca, v, lt["id"], 3)  # màn tưởng chưa chọn
    assert e.value.error_code == "STALE_TRA_TRUOC"
    kq = await tra_truoc(ca, v, lt["id"], 3, mong=2)
    assert kq["tra_truoc_id"] == a["tra_truoc_id"] and kq["so_buoi"] == 3
    with pytest.raises(LuotKhamConflictError):
        await tra_truoc(ca, v, lt["id"], "mười", mong=3)
    await tien(ca).bo_tra_truoc(
        identity=ca.thu_ngan, tra_truoc_id=kq["tra_truoc_id"], idempotency_key=_khoa()
    )
    assert (await hoa_don(ca, v)).dong == []
    kq = await tra_truoc(ca, v, lt["id"], 2)
    await thu(ca, v)
    with pytest.raises(LuotKhamConflictError) as e:
        await tien(ca).bo_tra_truoc(
            identity=ca.thu_ngan,
            tra_truoc_id=kq["tra_truoc_id"],
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "DA_NAM_TRONG_LAN_THU"
    # Trả thêm lần nữa trong CÙNG lượt (dòng đã thu không chặn dòng mới).
    kq2 = await tra_truoc(ca, v, lt["id"], 1)
    assert kq2["tra_truoc_id"] != kq["tra_truoc_id"]
    d = await doc(ca, lt["id"])
    await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=d["revision"],
        idempotency_key=_khoa(),
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await tra_truoc(ca, v, lt["id"], 1, mong=1)
    assert e.value.error_code == "LIEU_TRINH_DA_DUNG"


@pytest.mark.db
@pytest.mark.asyncio
async def test_bat_bien_postgres_chan_va_canh_gac_phat_hien(pool: asyncpg.Pool) -> None:
    """Postgres chặn: phủ buổi khi chưa trả; thu lẻ buổi đang phủ. Sổ bị sửa
    vòng qua trigger → ``bat_bien_lieu_trinh`` báo PHU_VUOT (bộ canh gác)."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 3, order=o)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE lieu_trinh_buoi SET tra_truoc = true"
            " WHERE service_order_id = $1::uuid",
            o,
        )
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute("SET LOCAL session_replication_role = replica")
            await conn.execute(
                "UPDATE lieu_trinh_buoi SET tra_truoc = true"
                " WHERE service_order_id = $1::uuid",
                o,
            )
            await conn.execute("SET LOCAL session_replication_role = origin")
            loi = await conn.fetch(
                "SELECT lieu_trinh_id::text, loai FROM bat_bien_lieu_trinh($1::uuid)",
                CLINIC,
            )
            assert (lt["id"], "PHU_VUOT") in [(r[0], r[1]) for r in loi]
            # Buổi đang phủ: dòng thu lẻ bị từ chối (không thu hai lần).
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id,"
                    " visit_id, kind, source_type, source_id, name_snapshot,"
                    " quantity, unit_price, line_total, billing_owner)"
                    " VALUES ($1::uuid, gen_random_uuid(), $2::uuid, 'dich_vu',"
                    " 'service_order', $3, 'x', 1, 1, 1, 'CLINIC')",
                    CLINIC,
                    v,
                    o,
                )
        finally:
            await tr.rollback()


@pytest.mark.db
@pytest.mark.asyncio
async def test_buoi_phu_chua_lam_mang_sang_luot_moi_giu_buoi(
    pool: asyncpg.Pool,
) -> None:
    """Buổi phủ chưa làm ở lượt hôm trước → khách đến lượt mới: chỉ định đi theo
    khách (``mang_sang_luot_moi``, cổng tiền coi như đã trả) và vẫn là đúng buổi
    ấy, vẫn phủ, hoá đơn lượt mới 0đ."""
    from clinicai.services.chi_dinh_service import ChiDinhService

    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 4, 2)
    v_cu = await luot(ca, dieu_tri=True, ngay_truoc=1)
    o = await chi_dinh(ca, v_cu)
    truoc = await buoi_song(ca, o)
    assert truoc is not None and truoc["tra_truoc"]
    v_moi = await luot(ca, dieu_tri=True)
    async with pool.acquire() as conn, conn.transaction():
        await ChiDinhService.mang_sang_luot_moi(conn, clinic_id=CLINIC, visit_id=v_moi)
    assert (
        await pool.fetchval(
            "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", o
        )
        == v_moi
    )
    sau = await buoi_song(ca, o)
    assert sau is not None and (sau["lt"], sau["buoi_so"], sau["tra_truoc"]) == (
        lt["id"],
        truoc["buoi_so"],
        True,
    )
    assert (await hoa_don(ca, v_moi)).dong == []
