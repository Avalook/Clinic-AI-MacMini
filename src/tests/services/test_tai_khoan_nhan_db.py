"""Tài khoản nhận chuyển khoản (31/10/2026), database thật.

Kịch bản: Quản lý thêm hai tài khoản cho cơ sở của lượt (một mặc định) → thu
chuyển khoản không chọn = gắn tài khoản mặc định; chọn tài khoản kia = gắn tài
khoản ấy; tài khoản đã tắt / của cơ sở khác bị từ chối. Sửa tài khoản của phiếu
đã thu có vết; mọi cột khác của lần thu vẫn bất biến. Hoàn chuyển khoản đi từ
tài khoản đã nhận. Tắt tài khoản mặc định = bỏ mặc định; Postgres giữ một mặc
định mỗi cơ sở và không cho xoá. Báo cáo cuối ngày: cộng các tài khoản = dòng
Chuyển khoản.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.doi_hinh_thuc_service import DoiHinhThucService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.tai_khoan_nhan_service import (
    CHUA_PHAN_LOAI,
    TaiKhoanNhanService,
)
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay
from tests.services.test_tien_thuoc_cp2_db import _rev, _thu_pt, _xm

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ql(q: Quay) -> StaffIdentity:
    """Quản lý có lego Cài đặt phòng khám; danh mục sạch cho bài này."""
    ql = await _nguoi_vai(q, "MANAGEMENT")
    async with q.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " SELECT $1::uuid, $2::uuid, ma, work_pack FROM capability"
            " WHERE ma = 'config.clinic.manage' ON CONFLICT DO NOTHING",
            CLINIC,
            ql.staff_id,
        )
        # Bài khác cùng DB để lại tài khoản: tắt hết để "mặc định / duy nhất"
        # của bài này không bị lẫn.
        await conn.execute(
            "UPDATE tai_khoan_nhan SET mac_dinh = false, dang_dung = false"
            " WHERE clinic_id = $1::uuid",
            CLINIC,
        )
    return ql


async def _co_so(q: Quay) -> str:
    v = await q.pool.fetchval(
        "SELECT a.location_id::text FROM visit v JOIN appointment a"
        " ON a.id = v.appointment_id WHERE v.visit_id = $1::uuid",
        q.visit_id,
    )
    return str(v)


def _so() -> str:
    return str(uuid.uuid4().int)[:12]


async def _them(
    q: Quay, ql: StaffIdentity, ten: str, *, loc: str | None, md: bool = False
) -> str:
    kq = await TaiKhoanNhanService(q.pool).luu(
        identity=ql,
        data={
            "ten_goi": ten,
            "ngan_hang": "Vietcombank",
            "so_tai_khoan": _so(),
            "chu_tai_khoan": "CONG TY DR4WOMEN",
            "location_id": loc,
            "mac_dinh": md,
        },
    )
    return str(kq["id"])


async def _thu_ck(q: Quay, tk: str | None = None, *, chia: bool = False) -> str:
    so = 50_000 if chia else 150_000
    ck: dict[str, Any] = {"hinh_thuc": "TRANSFER", "so_tien": so}
    if tk is not None:
        ck["tai_khoan_id"] = tk
    phan = ([{"hinh_thuc": "CASH", "so_tien": 100_000}] if chia else []) + [ck]
    kq = await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=await _rev(q),
        method="TRANSFER",
        phan=phan,
    )
    return str(kq["payment_cycle_id"])


async def _tk_cua(q: Quay, cid: str) -> str | None:
    v = await q.pool.fetchval(
        "SELECT tai_khoan_nhan_id::text FROM payment_cycle"
        " WHERE payment_cycle_id = $1::uuid",
        cid,
    )
    return str(v) if v else None


async def test_thu_ck_gan_mac_dinh_hoac_tai_khoan_chon(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc = await _co_so(q)
    a = await _them(q, ql, "VCB cơ sở", loc=loc, md=True)
    b = await _them(q, ql, "TCB chung", loc=None)

    # Khối thu: hai tài khoản dùng được, mặc định là của cơ sở.
    ds = await TaiKhoanNhanService(pool).danh_sach(
        identity=q.thu_ngan, visit_id=q.visit_id
    )
    assert set(ds["dung_duoc"]) == {a, b} and ds["mac_dinh"] == a
    assert ds["quan_ly"] is False

    cid = await _thu_ck(q)
    assert await _tk_cua(q, cid) == a
    await _xm(q, cid, "")

    q2 = await tao_quay(pool)
    cid2 = await _thu_ck(q2, b, chia=True)
    assert await _tk_cua(q2, cid2) == b

    # Tiền mặt → không gắn tài khoản.
    q3 = await tao_quay(pool)
    tm = await _thu_pt(q3, "CASH")
    assert await _tk_cua(q3, str(tm["payment_cycle_id"])) is None


async def test_tai_khoan_tat_hoac_co_so_khac_bi_tu_choi(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc_khac = await pool.fetchval(
        # Cơ sở NGỪNG (is_active false) để không lẫn vào bài đếm cơ sở khác.
        "INSERT INTO clinic_location (clinic_id, code, name, address, is_active)"
        " VALUES ($1::uuid, $2, $2, 'x', false) RETURNING id::text",
        CLINIC,
        f"TK-{uuid.uuid4().hex[:6]}",
    )
    khac = await _them(q, ql, "Của cơ sở khác", loc=str(loc_khac))
    with pytest.raises(ValidationError, match="cơ sở khác"):
        await _thu_ck(q, khac)
    tat = await _them(q, ql, "Sắp tắt", loc=None)
    await TaiKhoanNhanService(pool).luu(
        identity=ql,
        tai_khoan_id=tat,
        data={
            "ten_goi": "Sắp tắt",
            "ngan_hang": "Vietcombank",
            "so_tai_khoan": (
                await pool.fetchval(
                    "SELECT so_tai_khoan FROM tai_khoan_nhan WHERE id = $1::uuid", tat
                )
            ),
            "chu_tai_khoan": "CONG TY DR4WOMEN",
            "dang_dung": False,
        },
    )
    with pytest.raises(ValidationError, match="đã tắt"):
        await _thu_ck(q, tat)
    # Thu ngân không sửa được danh mục.
    with pytest.raises(SafetyGateError):
        await TaiKhoanNhanService(pool).luu(
            identity=q.thu_ngan,
            data={
                "ten_goi": "x",
                "ngan_hang": "y",
                "so_tai_khoan": _so(),
                "chu_tai_khoan": "z",
            },
        )


async def test_khong_cai_tai_khoan_thi_chua_phan_loai(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await _ql(q)
    cid = await _thu_ck(q)
    assert await _tk_cua(q, cid) is None


async def test_sua_tai_khoan_phieu_da_thu_co_vet(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc = await _co_so(q)
    a = await _them(q, ql, "A", loc=loc, md=True)
    b = await _them(q, ql, "B", loc=loc)
    cid = await _thu_ck(q)
    await _xm(q, cid, "")
    svc = TaiKhoanNhanService(pool)
    kq = await svc.doi_cho_lan_thu(
        identity=q.thu_ngan,
        payment_cycle_id=cid,
        tai_khoan_id=b,
        tai_khoan_cu=a,
        ly_do="Bấm nhầm tài khoản",
    )
    assert (kq["tai_khoan_cu"], kq["tai_khoan_moi"]) == (a, b)
    assert await _tk_cua(q, cid) == b
    vet = await pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1"
        " AND event_type = 'payment.receiving_account_changed'",
        cid,
    )
    p = json.loads(vet)
    assert (p["tai_khoan_cu"], p["tai_khoan_moi"], p["ly_do"]) == (
        a,
        b,
        "Bấm nhầm tài khoản",
    )
    # Hoàn tác chính lần sửa: đổi lại A. Màn cũ (còn thấy A) thì 409.
    with pytest.raises(ConflictError, match="vừa được người khác"):
        await svc.doi_cho_lan_thu(
            identity=q.thu_ngan, payment_cycle_id=cid, tai_khoan_id=a, tai_khoan_cu=a
        )
    await svc.doi_cho_lan_thu(identity=q.thu_ngan, payment_cycle_id=cid, tai_khoan_id=a)
    assert await _tk_cua(q, cid) == a
    # Guard: mọi cột khác vẫn bất biến.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE payment_cycle SET amount = amount + 1, tai_khoan_nhan_id = $2::uuid"
            " WHERE payment_cycle_id = $1::uuid",
            cid,
            b,
        )
    # Phiếu tiền mặt không có gì để sửa.
    q2 = await tao_quay(pool)
    tm = await _thu_pt(q2, "CASH")
    with pytest.raises(ConflictError, match="không có phần chuyển khoản"):
        await svc.doi_cho_lan_thu(
            identity=q2.thu_ngan,
            payment_cycle_id=str(tm["payment_cycle_id"]),
            tai_khoan_id=a,
        )
    # Đổi hình thức TM → CK: gắn mặc định của cơ sở.
    await DoiHinhThucService(pool).doi(
        identity=q2.thu_ngan,
        payment_cycle_id=str(tm["payment_cycle_id"]),
        hinh_thuc="TRANSFER",
    )
    assert await _tk_cua(q2, str(tm["payment_cycle_id"])) == a


async def test_hoan_ck_tu_tai_khoan_da_nhan(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc = await _co_so(q)
    await _them(q, ql, "A", loc=loc, md=True)
    b = await _them(q, ql, "B", loc=loc)
    cid = await _thu_ck(q, b)
    await _xm(q, cid, "")
    dong = await pool.fetchval(
        "SELECT id::text FROM payment_bill_line WHERE payment_cycle_id = $1::uuid"
        " LIMIT 1",
        cid,
    )
    kq = await HoanTienService(pool).tao(
        identity=ql,
        payment_cycle_id=cid,
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": dong, "so_luong": 1}],
        method="TRANSFER",
        reason="Khách đổi ý không khám",
    )
    tk = await pool.fetchval(
        "SELECT tai_khoan_nhan_id::text FROM payment_refund WHERE refund_id = $1::uuid",
        kq["refund_id"],
    )
    assert tk == b


async def test_tat_mac_dinh_va_bat_bien_postgres(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc = await _co_so(q)
    a = await _them(q, ql, "A", loc=loc, md=True)
    b = await _them(q, ql, "B", loc=loc, md=True)  # đặt B mặc định → A thôi
    md = await pool.fetch(
        "SELECT id::text FROM tai_khoan_nhan WHERE clinic_id = $1::uuid"
        " AND mac_dinh AND location_id = $2::uuid",
        CLINIC,
        loc,
    )
    assert [r["id"] for r in md] == [b]
    so_b = await pool.fetchval(
        "SELECT so_tai_khoan FROM tai_khoan_nhan WHERE id = $1::uuid", b
    )
    # Tắt B đang mặc định → bỏ mặc định; còn A dùng được → tự chọn A.
    kq = await TaiKhoanNhanService(pool).luu(
        identity=ql,
        tai_khoan_id=b,
        data={
            "ten_goi": "B",
            "ngan_hang": "Vietcombank",
            "so_tai_khoan": so_b,
            "chu_tai_khoan": "CONG TY DR4WOMEN",
            "location_id": loc,
            "mac_dinh": True,
            "dang_dung": False,
        },
    )
    assert (kq["tai_khoan"]["mac_dinh"], kq["tai_khoan"]["dang_dung"]) == (False, False)
    cid = await _thu_ck(q)
    assert await _tk_cua(q, cid) == a
    # Postgres: hai mặc định cùng cơ sở / mặc định mà tắt / xoá → chặn.
    with pytest.raises(asyncpg.UniqueViolationError):
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "UPDATE tai_khoan_nhan SET mac_dinh = true, dang_dung = true"
                " WHERE id = ANY($1::uuid[])",
                [a, b],
            )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE tai_khoan_nhan SET mac_dinh = true, dang_dung = false"
            " WHERE id = $1::uuid",
            a,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM tai_khoan_nhan WHERE id = $1::uuid", a)
    # Trùng số tài khoản → 409 câu dễ hiểu.
    with pytest.raises(ConflictError, match="đã có trong danh mục"):
        await TaiKhoanNhanService(pool).luu(
            identity=ql,
            data={
                "ten_goi": "Trùng",
                "ngan_hang": " vietcombank ",
                "so_tai_khoan": so_b,
                "chu_tai_khoan": "X",
            },
        )


async def test_bao_cao_tong_theo_tai_khoan_bang_chuyen_khoan(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    ql = await _ql(q)
    loc = await _co_so(q)
    a = await _them(q, ql, "A báo cáo", loc=loc, md=True)
    b = await _them(q, ql, "B báo cáo", loc=loc)
    ds = [(q, await _thu_ck(q))]
    q2 = await tao_quay(pool)
    ds.append((q2, await _thu_ck(q2, b, chia=True)))
    q3 = await tao_quay(pool)
    await _ql(q3)  # tắt hết → lần thu sau "Chưa phân loại"
    ds.append((q3, await _thu_ck(q3)))
    for qq, cid in ds:
        await _xm(qq, cid, "")

    bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ql, co_so=loc)
    ck = next(r for r in bc["theo_hinh_thuc"] if r["ma"] == "TRANSFER")
    for k in ("thu", "huy", "hoan", "thuc_thu"):
        assert sum(r[k] for r in bc["theo_tai_khoan"]) == ck[k], k
    ten = {r["id"]: r for r in bc["theo_tai_khoan"]}
    assert ten[a]["thu"] >= 150_000 and ten[b]["thu"] >= 50_000
    assert ten[None]["ten"] == CHUA_PHAN_LOAI and ten[None]["thu"] >= 150_000

    hd = await DanhSachHoaDonService(pool).xem(identity=ql, co_so=loc)
    phieu = {p["id"]: p for k in hd["khach"] for p in k["phieu"]}
    assert phieu[ds[1][1]]["tai_khoan_id"] == b
    assert phieu[ds[1][1]]["chuyen_khoan"] == 50_000
    tk_hd = {r["id"]: r for r in hd["theo_tai_khoan"]}
    assert tk_hd[b]["thu"] >= 50_000
