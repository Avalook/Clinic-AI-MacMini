"""Khu 3 — ĐỐI CHIẾU ĐỘC LẬP tiền: sổ gốc ↔ danh sách hoá đơn ↔ báo cáo cuối ngày ↔
file xuất hoá đơn (thu − hoàn theo dòng).

Chạy đúng các lệnh thật của `test_mo_phong_dong_tien_db` (thu tiền mặt / chuyển khoản,
xác minh, huỷ phiếu, bỏ chỉ định, hoàn tiền thừa, ghi nợ…), rồi tính LẠI từ bốn bảng
gốc — `payment_cycle`, `payment_refund`, `payment_bill_line`, `payment_refund_line` —
bằng Python, không dùng hàm nào của ba nơi cần kiểm:

  T1  Tổng kỳ: thu · huỷ · hoàn · thực thu (= thu − huỷ − hoàn) của sổ gốc phải bằng
      `tong` của Danh sách hoá đơn VÀ `tong` của Báo cáo cuối ngày.
  T2  Mỗi phiếu: tổng dòng hàng = số tiền phiếu (chưa giảm giá).
  T3  Mỗi hoá đơn xuất: tổng = Σ (dòng − hoàn ĐÚNG dòng đó), và phần chênh với
      "tiền phiếu − hoàn xong" đúng bằng hoàn KHÔNG THEO DÒNG (không trừ được, chỉ
      ghi chú) — đây là "lỗ hoàn không theo dòng" đã biết, đo cho thấy mức.

Tổng toàn phòng khám đọc trên DB DÙNG CHUNG: test khác ghi tiền cùng lúc thì ba lần
đọc không cùng một thời điểm. Nên đọc sổ gốc TRƯỚC và SAU hai lần đọc kia, chỉ so khi
hai bản sổ giống hệt nhau (không ai ghi trong lúc đó); không đạt sau vài lần thì bỏ
qua (skip), không so bậy.
"""

from __future__ import annotations

# ruff: noqa: F811 — fixture `pool` và autouse `_lam_truoc_thu_sau` được import.
import random
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService
from tests.services.test_check_in_lai_sau_hoan_tac_db import pool  # noqa: F401
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    VIEC,
    _lam_truoc_thu_sau,
    _luot,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]
TEN_TIEN = ("thu", "huy", "hoan", "thuc_thu")


# ── Sổ gốc ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class So:
    thu: int
    huy: int
    hoan: int
    # phiếu → (tiền phiếu, trạng thái, tổng dòng, hoàn có dòng, hoàn không dòng,
    #           thu trong kỳ)
    phieu: dict[str, tuple[int, str, int, int, int, bool]]
    # phiếu → tổng dòng sau khi trừ hoàn đúng dòng (bỏ dòng ≤ 0) — đáp án cho file xuất
    xuat: dict[str, int]

    @property
    def thuc_thu(self) -> int:
        return self.thu - self.huy - self.hoan


async def doc_so(pool: asyncpg.Pool, clinic: str, tu: datetime, den: datetime) -> So:
    bills = await pool.fetch(
        "SELECT payment_cycle_id::text id, amount, status, paid_at, closed_at"
        " FROM payment_cycle WHERE clinic_id = $1::uuid",
        clinic,
    )
    refunds = await pool.fetch(
        "SELECT refund_id::text id, payment_cycle_id::text cycle_id, amount, status,"
        " completed_at FROM payment_refund WHERE clinic_id = $1::uuid",
        clinic,
    )
    lines = await pool.fetch(
        "SELECT id::text, payment_cycle_id::text cycle_id, line_total"
        " FROM payment_bill_line WHERE clinic_id = $1::uuid"
        " AND billing_owner = 'CLINIC'",  # chỉ dòng phòng khám thu mới lên hoá đơn
        clinic,
    )
    rlines = await pool.fetch(
        "SELECT refund_id::text, payment_bill_line_id::text line_id, amount"
        " FROM payment_refund_line WHERE clinic_id = $1::uuid",
        clinic,
    )

    def trong(t: Any) -> bool:
        return isinstance(t, datetime) and tu <= t < den

    thu = sum(int(b["amount"]) for b in bills if trong(b["paid_at"]))
    huy = sum(
        int(b["amount"])
        for b in bills
        if b["status"] == "VOIDED" and trong(b["closed_at"])
    )
    hoan_xong = [r for r in refunds if r["status"] == "COMPLETED"]
    hoan = sum(int(r["amount"]) for r in hoan_xong if trong(r["completed_at"]))

    co_dong = {x["refund_id"] for x in rlines}
    hoan_dong: dict[str, int] = {}  # dòng hàng → tiền đã hoàn xong
    for x in rlines:
        if any(r["id"] == x["refund_id"] for r in hoan_xong):
            hoan_dong[x["line_id"]] = hoan_dong.get(x["line_id"], 0) + int(x["amount"])
    phieu: dict[str, tuple[int, str, int, int, int, bool]] = {}
    xuat: dict[str, int] = {}
    for b in bills:
        mine = [x for x in lines if x["cycle_id"] == b["id"]]
        r_co = sum(
            int(r["amount"])
            for r in hoan_xong
            if r["cycle_id"] == b["id"] and r["id"] in co_dong
        )
        r_khong = sum(
            int(r["amount"])
            for r in hoan_xong
            if r["cycle_id"] == b["id"] and r["id"] not in co_dong
        )
        tong_dong = sum(int(x["line_total"]) for x in mine)
        phieu[b["id"]] = (
            int(b["amount"]),
            b["status"],
            tong_dong,
            r_co,
            r_khong,
            trong(b["paid_at"]),
        )
        xuat[b["id"]] = sum(
            t
            for t in (int(x["line_total"]) - hoan_dong.get(x["id"], 0) for x in mine)
            if t > 0
        )
    return So(thu, huy, hoan, phieu, xuat)


def _khung() -> tuple[datetime, datetime, str]:
    h = now_vn().date()
    tu = datetime.combine(h, time.min, tzinfo=CLINIC_TZ)
    return tu, tu + timedelta(days=1), h.isoformat()


async def chay_ngau_nhien(pool: asyncpg.Pool, ca: Ca, so_hat: int) -> Counter[str]:
    """Bấm ngẫu nhiên có hạt cố định bằng lệnh thật; trả đếm bước chạy được."""
    chay: Counter[str] = Counter()
    for hat in range(so_hat):
        rnd = random.Random(hat)
        v, o = await _luot(pool, ca)
        for _ in range(8):
            ten = rnd.choice(sorted(VIEC))
            try:
                await VIEC[ten](pool, ca, v, o)
            except (ClinicAIBaseException, AssertionError, asyncpg.PostgresError):
                continue  # bị chặn đúng luật — người thật cũng vậy
            chay[ten] += 1
    return chay


async def doc_on_dinh(pool: asyncpg.Pool, ca: Ca, doc: Any) -> tuple[So, Any] | None:
    """Gọi `doc()` giữa hai lần đọc sổ gốc; chỉ trả khi sổ không đổi."""
    tu, den, _ = _khung()
    for _ in range(6):
        truoc = await doc_so(pool, ca.thu_ngan.clinic_id, tu, den)
        kq = await doc()
        sau = await doc_so(pool, ca.thu_ngan.clinic_id, tu, den)
        if truoc == sau:
            return truoc, kq
    return None


# ── T1: tổng kỳ ──────────────────────────────────────────────────────────


async def test_t1_tong_bang_bao_cao_va_so_goc_khop_nhau(pool: asyncpg.Pool) -> None:
    ca = await _dung(pool)
    quan_ly = replace(ca.thu_ngan, role=ClinicRole.MANAGEMENT)
    chay = await chay_ngau_nhien(pool, ca, 25)
    _, _, ngay = _khung()

    async def doc() -> tuple[dict[str, Any], dict[str, Any]]:
        ds = await DanhSachHoaDonService(pool).xem(identity=quan_ly, tu=ngay, den=ngay)
        bc = await BaoCaoCuoiNgayService(pool).bao_cao(
            identity=quan_ly, tu=ngay, den=ngay
        )
        return ds, bc

    got = await doc_on_dinh(pool, ca, doc)
    if got is None:
        pytest.skip("DB đang có test khác ghi tiền liên tục — không đọc ổn định được")
    so, (ds, bc) = got
    t = ds["tong"]
    bang = {
        "sổ gốc": (so.thu, so.huy, so.hoan, so.thuc_thu),
        "danh sách hoá đơn": (
            t["da_thu"],
            t["gia_tri_huy"],
            t["da_hoan"],
            t["thu_rong"],
        ),
        "báo cáo cuối ngày": tuple(bc["tong"][k] for k in TEN_TIEN),
    }
    print(f"\nBƯỚC CHẠY ĐƯỢC: {dict(chay)}")
    for nguon, v in bang.items():
        print(
            f"  {nguon:<20} thu={v[0]:>10} huỷ={v[1]:>9} hoàn={v[2]:>9}"
            f" thực thu={v[3]:>10}"
        )
    assert bang["danh sách hoá đơn"] == bang["sổ gốc"], bang
    assert bang["báo cáo cuối ngày"] == bang["sổ gốc"], bang
    assert so.thuc_thu == so.thu - so.huy - so.hoan


# ── T2 + T3: từng phiếu, từng dòng ──────────────────────────────────────


async def test_t2_t3_thu_tru_hoan_theo_dong_tung_phieu(pool: asyncpg.Pool) -> None:
    ca = await _dung(pool)
    quan_ly = replace(ca.thu_ngan, role=ClinicRole.MANAGEMENT)
    await chay_ngau_nhien(pool, ca, 25)
    _, _, ngay = _khung()

    async def doc() -> dict[str, Any]:
        return await XuatHoaDonService(pool).xem(
            identity=quan_ly, tu=ngay, den=ngay, che_do="mot"
        )

    got = await doc_on_dinh(pool, ca, doc)
    if got is None:
        pytest.skip("DB đang có test khác ghi tiền liên tục — không đọc ổn định được")
    so, kq = got
    xuat = {h["payment_cycle_id"]: h for h in kq["hoa_don"]}

    # T2 — mọi phiếu có dòng: Σ dòng = tiền phiếu (hệ thống hiện chưa có giảm giá).
    lech_dong = {
        pid: (tien, tong_dong)
        for pid, (tien, st, tong_dong, _c, _k, _t) in so.phieu.items()
        if tong_dong and tien != tong_dong and st in ("PAID", "VOIDED")
    }
    # T3 — file xuất = Σ (dòng − hoàn đúng dòng), từng phiếu.
    sai_xuat = {
        pid: (h["tong"], so.xuat[pid])
        for pid, h in xuat.items()
        if h["tong"] != so.xuat[pid]
    }
    # Hoàn không theo dòng: tiền phiếu − hoàn xong − tổng xuất.
    khong_dong = {pid: so.phieu[pid][4] for pid in xuat if so.phieu[pid][4] > 0}
    ghi_chu_thieu = [
        pid
        for pid in khong_dong
        if not any("không theo dòng" in g for g in xuat[pid].get("ghi_chu", []))
    ]
    print(
        f"\nPHIẾU XUẤT: {len(xuat)} · lệch dòng↔tiền phiếu: {len(lech_dong)} · "
        f"xuất ≠ đáp án: {len(sai_xuat)} · hoàn không theo dòng: {len(khong_dong)} "
        f"(tổng {sum(khong_dong.values())}đ)"
    )
    assert not lech_dong, f"tổng dòng ≠ tiền phiếu: {lech_dong}"
    assert not sai_xuat, f"file xuất ≠ đáp án (thu − hoàn đúng dòng): {sai_xuat}"
    assert not ghi_chu_thieu, f"hoàn không theo dòng mà KHÔNG ghi chú: {ghi_chu_thieu}"


# ── Case vàng: số tính tay, dựng bằng sổ gốc (như test_xuat_hoa_don_db) ───


@dataclass(frozen=True)
class DongGoc:
    ten: str
    so_luong: int
    tien: int  # line_total (đã là số SAU giảm)
    giam: int = 0  # discount_allocated


async def dung_phieu(
    pool: asyncpg.Pool,
    quan_ly: Any,
    visit: str,
    dong: list[DongGoc],
    *,
    giam: int = 0,
) -> tuple[str, list[str]]:
    """Phiếu PAID hôm nay + các dòng. Trả (id phiếu, id từng dòng)."""
    tien = sum(d.tien for d in dong)
    cid = str(uuid4())
    # Ràng buộc payment_cycle_giam_gia_khop: không giảm → mọi cột giảm giá rỗng;
    # có giảm → đủ loại, giá trị, lý do, người giảm, số gốc.
    await pool.execute(
        "INSERT INTO payment_cycle(payment_cycle_id,clinic_id,visit_id,kind,amount,"
        "status,legacy,paid_at,created_at,created_by,confirmed_by,method,"
        "original_amount,discount_amount,discount_type,discount_value,"
        "discount_reason,discount_by) VALUES($1::uuid,$2::uuid,$3::uuid,"
        "'dich_vu',$5,'PAID',true,now(),now(),$4::uuid,$4::uuid,'CASH',$6,$7,$8,"
        "$9,$10,$11::uuid)",
        cid,
        quan_ly.clinic_id,
        visit,
        quan_ly.staff_id,
        tien,
        tien + giam if giam else None,
        giam,
        "AMOUNT" if giam else None,
        giam if giam else None,
        "Đối chiếu độc lập" if giam else None,
        quan_ly.staff_id if giam else None,
    )
    ids: list[str] = []
    for d in dong:
        ids.append(
            str(
                await pool.fetchval(
                    "INSERT INTO payment_bill_line(clinic_id,payment_cycle_id,visit_id,"
                    "kind,source_type,source_id,name_snapshot,quantity,unit_price,"
                    "line_total,discount_allocated,billing_owner) VALUES($1::uuid,"
                    "$2::uuid,$3::uuid,'dich_vu','exam',$9,$4,$5,$6,$7,$8,'CLINIC')"
                    " RETURNING id",
                    quan_ly.clinic_id,
                    cid,
                    visit,
                    d.ten,
                    d.so_luong,
                    (d.tien + d.giam) // d.so_luong,  # giá TRƯỚC giảm (ràng buộc DB)
                    d.tien,
                    d.giam,
                    uuid4().hex,  # mỗi dòng một nguồn: DB cấm thu hai lần
                )
            )
        )
    return cid, ids


async def hoan(
    pool: asyncpg.Pool,
    quan_ly: Any,
    visit: str,
    cid: str,
    so_tien: int,
    *,
    trang_thai: str = "COMPLETED",
    dong: list[tuple[str, int, int]] | None = None,
) -> None:
    """Một khoản hoàn; `dong` = [(id dòng, số lượng, tiền)].

    `dong=None` dựng khoản hoàn CŨ KHÔNG DÒNG. Từ migration 20260919000004 DB ép tiền
    đầu khoản = tổng dòng lúc COMMIT nên khoản mới không thể không dòng; chỉ dữ liệu
    TRƯỚC 19/09 mới có. Dựng bằng `session_replication_role = replica` (tắt trigger),
    giới hạn trong giao dịch này nên không ảnh hưởng worker khác."""
    async with pool.acquire() as conn, conn.transaction():
        if dong is None:
            await conn.execute("SET LOCAL session_replication_role = replica")
        rid = await conn.fetchval(
            "INSERT INTO payment_refund(clinic_id,visit_id,kind,payment_cycle_id,"
            "amount,status,method,reason,created_by,created_at,completed_at,"
            "completed_by) VALUES($1::uuid,$2::uuid,'dich_vu',$3::uuid,$4,$5,'CASH',"
            "'Đối chiếu',$6::uuid,now(),CASE WHEN $5='COMPLETED' THEN now() END,"
            "CASE WHEN $5='COMPLETED' THEN $6::uuid END) RETURNING refund_id",
            quan_ly.clinic_id,
            visit,
            cid,
            so_tien,
            trang_thai,
            quan_ly.staff_id,
        )
        for line_id, sl, tien in dong or []:
            await conn.execute(
                "INSERT INTO payment_refund_line(clinic_id,refund_id,"
                "payment_bill_line_id,payment_cycle_id,quantity,amount) VALUES("
                "$1::uuid,$2,$3::uuid,$4::uuid,$5,$6)",
                quan_ly.clinic_id,
                rid,
                line_id,
                cid,
                sl,
                tien,
            )


async def xuat_phieu(pool: asyncpg.Pool, quan_ly: Any, cid: str) -> dict[str, Any]:
    ngay = _khung()[2]
    kq = await XuatHoaDonService(pool).xem(
        identity=quan_ly, tu=ngay, den=ngay, che_do="mot"
    )
    return next(h for h in kq["hoa_don"] if h["payment_cycle_id"] == cid)


async def test_g1_hoan_theo_dong_tru_dung_dong_va_dung_so_luong(
    pool: asyncpg.Pool,
) -> None:
    """Tay: khám 300.000 + que thử 3 cái 90.000 = 390.000. Hoàn trọn dòng khám
    (300.000) và 1 que (30.000) → còn que thử 2 cái 60.000, đơn giá 30.000."""
    q = await tao_quay(pool)
    quan_ly = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    cid, (kham, que) = await dung_phieu(
        pool,
        quan_ly,
        q.visit_id,
        [DongGoc("Khám", 1, 300000), DongGoc("Que", 3, 90000)],
    )
    await hoan(
        pool,
        quan_ly,
        q.visit_id,
        cid,
        330000,
        dong=[(kham, 1, 300000), (que, 1, 30000)],
    )
    hd = await xuat_phieu(pool, quan_ly, cid)
    assert [
        (d["ten"], d["so_luong"], d["don_gia"], d["thanh_tien"]) for d in hd["dong"]
    ] == [("Que", 2, 30000, 60000)]
    assert hd["tong"] == 60000 == 390000 - 330000


async def test_g2_hoan_cho_xu_ly_chua_tru_nhung_co_ghi_chu(pool: asyncpg.Pool) -> None:
    """Hoàn đang CHỜ chưa là tiền ra khỏi két → chưa trừ; có ghi chú cho kế toán.
    Tay: que thử 3 cái 300.000 (100.000/cái); chờ hoàn 1 cái 100.000 → vẫn 300.000."""
    q = await tao_quay(pool)
    quan_ly = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    cid, (que,) = await dung_phieu(
        pool, quan_ly, q.visit_id, [DongGoc("Que", 3, 300000)]
    )
    await hoan(
        pool,
        quan_ly,
        q.visit_id,
        cid,
        100000,
        trang_thai="PENDING",
        dong=[(que, 1, 100000)],
    )
    hd = await xuat_phieu(pool, quan_ly, cid)
    assert hd["tong"] == 300000
    assert any("Đang chờ hoàn 100.000đ" in g for g in hd["ghi_chu"])


async def test_g3_giam_gia_chia_theo_ti_le_khi_hoan_mot_phan(
    pool: asyncpg.Pool,
) -> None:
    """Tay: 1 dòng 300.000, giảm 20.000 → khách trả 280.000 (line_total = 280.000,
    giảm 20.000). Hoàn 140.000 (một nửa) → còn 140.000, giảm còn lại 10.000, trước
    giảm 150.000."""
    q = await tao_quay(pool)
    quan_ly = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    cid, (d1,) = await dung_phieu(
        pool, quan_ly, q.visit_id, [DongGoc("Khám", 1, 280000, giam=20000)], giam=20000
    )
    await hoan(pool, quan_ly, q.visit_id, cid, 140000, dong=[(d1, 1, 140000)])
    hd = await xuat_phieu(pool, quan_ly, cid)
    (d,) = hd["dong"]
    assert (d["thanh_tien"], d["giam_gia"], d["truoc_giam"]) == (140000, 10000, 150000)
    assert hd["tong"] == sum(x["truoc_giam"] - x["giam_gia"] for x in hd["dong"])


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CHỜ QUYẾT 15–16/10 (memory xuat-hoa-don-doi-chieu-1510-1610): hoàn CŨ (trước "
        "19/09, DB nay cấm tạo mới) ĐÃ XONG nhưng không gắn dòng nào thì hoá đơn xuất "
        "KHÔNG trừ (chỉ ghi chú), nên tổng "
        "xuất > tiền phiếu − hoàn. Tuyền 'check sau', chưa chỉ dòng sai. Quyết định: "
        "trừ tỉ lệ vào các dòng, hay chặn tạo khoản hoàn không dòng."
    ),
)
async def test_g4_hoan_khong_theo_dong_phai_duoc_tru_khoi_hoa_don(
    pool: asyncpg.Pool,
) -> None:
    """Bất biến KHÔNG phụ thuộc cách quyết: hoá đơn xuất = tiền phiếu − hoàn xong."""
    q = await tao_quay(pool)
    quan_ly = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    cid, _ = await dung_phieu(pool, quan_ly, q.visit_id, [DongGoc("Khám", 1, 300000)])
    await hoan(pool, quan_ly, q.visit_id, cid, 100000, dong=None)
    hd = await xuat_phieu(pool, quan_ly, cid)
    assert any("không theo dòng" in g for g in hd["ghi_chu"]), "ít nhất phải ghi chú"
    assert hd["tong"] == 300000 - 100000, "đang xuất 300.000 dù đã hoàn 100.000"
