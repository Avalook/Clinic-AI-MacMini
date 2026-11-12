"""BÙ KẾT QUẢ EMAIL CŨ — "đã trả khách ngoài hệ thống" (Tuyền duyệt 12/11/2026).

Tờ kết quả email về TRƯỚC 11/11 (ngày bật tự nhận Gmail trên prod) nhân viên đã trả
khách bằng Gmail / Zalo như trước khi có hệ thống. Không bắt người kiểm lại từng tờ,
không để CSKH ngập việc "Kết quả chưa gửi": lệnh chạy MỘT lần, mỗi tờ còn hiệu lực
chưa gửi:
  * Chờ xác nhận ⇒ Hợp lệ (người đứng tên = tài khoản Tuyền chọn, lý do `LY_DO`);
  * đã gửi, kênh `NGOAI_HE_THONG` (migration 20261112090000) ⇒ việc CSKH tự tắt,
    bàn Việc của đối tác thấy "Đã gửi khách".
Không đụng chỉ định, lượt khám, tiền. Mỗi tờ một sự kiện
`lab.old_result_marked_delivered` (lô, trạng thái trước) ⇒ soát được, HOÀN TÁC theo
lô (gỡ mốc gửi ngoài hệ thống; Hợp lệ giữ nguyên — database không cho lùi về Chờ xác
nhận, và đó đúng là việc người kiểm sẽ làm).

    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi EMAIL        # xem trước
    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi EMAIL --chay
    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi EMAIL --hoan-tac LO
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from collections import Counter
from datetime import date, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.api.identity import StaffIdentity, danh_tinh_nhan_vien
from clinicai.events.catalogue import XetNghiemBuKetQuaCu
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.xet_nghiem import gmail

KENH: Final = "NGOAI_HE_THONG"
MOC_MAC_DINH: Final = date(2026, 11, 11)
LY_DO: Final = "Bù 12/11: kết quả cũ, đã trả khách ngoài hệ thống (Tuyền duyệt)"
VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")

_CHON_SQL = """
SELECT k.id::text AS tep_id, k.xac_nhan_trang_thai AS truoc, d.ten AS lab,
       k.service_order_id IS NULL AS theo_luot
  FROM tep_ket_qua k
  JOIN drive_tep t ON t.tep_ket_qua_id = k.id AND t.clinic_id = k.clinic_id
                  AND t.nguon = 'GMAIL'
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
 WHERE k.clinic_id = $1::uuid AND k.da_xoa_luc IS NULL AND k.gui_luc IS NULL
   AND k.xac_nhan_trang_thai IN ('CHO_XAC_NHAN', 'HOP_LE')
   AND (t.email_nhan_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date < $2::date
 ORDER BY t.email_nhan_luc, k.id
"""


def trong_gio_kham(luc: datetime) -> bool:
    """HÀM THUẦN: giờ phòng khám dùng (Tuyền 11/11) — ngày thường 15:30–23:00, cuối tuần
    06:30–23:00 (cùng ngưỡng script deploy). Trong giờ ⇒ lệnh ghi không chạy."""
    hm = luc.astimezone(VN).hour * 100 + luc.astimezone(VN).minute
    mo = 630 if luc.astimezone(VN).isoweekday() >= 6 else 1530
    return mo <= hm < 2300


async def xem_truoc(conn: asyncpg.Connection, cid: str, moc: date) -> Counter[str]:
    """Số tờ sẽ được đánh, theo lab · trạng thái · gắn vào đâu. Không ghi gì."""
    dem: Counter[str] = Counter()
    for r in await conn.fetch(_CHON_SQL, cid, moc):
        noi = "theo lượt" if r["theo_luot"] else "chỉ định"
        dem[f"{r['lab']} · {r['truoc']} · {noi}"] += 1
    return dem


async def chay(pool: asyncpg.Pool, ai: StaffIdentity, moc: date) -> dict[str, Any]:
    """Đánh mọi tờ trong phạm vi — MỘT giao dịch: hỏng giữa chừng ⇒ không đổi gì."""
    lo = str(uuid.uuid4())
    da = Counter[str]()
    async with pool.acquire() as conn, conn.transaction():
        if not await can(conn, ai, "result.file.confirm"):
            raise PermissionError("Người đứng tên chưa có quyền Xác nhận kết quả.")
        for r in await conn.fetch(_CHON_SQL, ai.clinic_id, moc):
            if r["truoc"] == "CHO_XAC_NHAN":
                await conn.execute(
                    "UPDATE tep_ket_qua SET xac_nhan_trang_thai = 'HOP_LE',"
                    "       xac_nhan_luc = now(), xac_nhan_boi_staff_id = $3::uuid,"
                    "       xac_nhan_ly_do = $4"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    "   AND xac_nhan_trang_thai = 'CHO_XAC_NHAN'",
                    ai.clinic_id,
                    r["tep_id"],
                    ai.staff_id,
                    LY_DO,
                )
            n = await conn.execute(
                "UPDATE tep_ket_qua SET gui_luc = now(), gui_boi_staff_id = $3::uuid,"
                "       gui_kenh = $4"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid AND gui_luc IS NULL"
                "   AND da_xoa_luc IS NULL AND xac_nhan_trang_thai = 'HOP_LE'",
                ai.clinic_id,
                r["tep_id"],
                ai.staff_id,
                KENH,
            )
            if n != "UPDATE 1":
                da["bo_qua"] += 1
                continue
            await _su_kien(conn, ai, r, lo, hoan=False)
            da[r["truoc"]] += 1
    return {"lo": lo, **da}


async def hoan_tac(pool: asyncpg.Pool, ai: StaffIdentity, lo: str) -> int:
    """Gỡ mốc "đã gửi ngoài hệ thống" của đúng lô `lo` (tờ đã gửi lại thật thì giữ)."""
    async with pool.acquire() as conn, conn.transaction():
        if not await can(conn, ai, "result.file.confirm"):
            raise PermissionError("Người hoàn tác chưa có quyền Xác nhận kết quả.")
        rows = await conn.fetch(
            "SELECT payload->>'tep_id' AS tep_id, payload->>'truoc' AS truoc"
            "  FROM domain_event WHERE clinic_id = $1::uuid"
            "   AND event_type = 'lab.old_result_marked_delivered'"
            "   AND payload->>'lo' = $2",
            ai.clinic_id,
            lo,
        )
        so = 0
        for r in rows:
            n = await conn.execute(
                "UPDATE tep_ket_qua SET gui_luc = NULL, gui_boi_staff_id = NULL,"
                "       gui_kenh = NULL"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid AND gui_kenh = $3",
                ai.clinic_id,
                r["tep_id"],
                KENH,
            )
            if n == "UPDATE 1":
                await _su_kien(conn, ai, r, lo, hoan=True)
                so += 1
    return so


async def _su_kien(
    conn: asyncpg.Connection, ai: StaffIdentity, r: Any, lo: str, *, hoan: bool
) -> None:
    # Tên viết thẳng (không qua biến): test "mọi sự kiện có nơi phát" đọc chữ ở đây.
    await emit_event(
        conn,
        ten="lab.old_result_mark_undone" if hoan else "lab.old_result_marked_delivered",
        clinic_id=ai.clinic_id,
        aggregate_id=r["tep_id"],
        payload=XetNghiemBuKetQuaCu(tep_id=r["tep_id"], truoc=r["truoc"], lo=lo),
        boi=nguoi(ai),
    )


async def _nguoi(conn: asyncpg.Connection, cid: str, email: str) -> StaffIdentity:
    sid = await conn.fetchval(
        "SELECT s.id::text FROM staff s JOIN clinic_membership m"
        "    ON m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active"
        " WHERE lower(s.email) = lower($2) AND s.is_active IS NOT FALSE",
        cid,
        email.strip(),
    )
    ai = await danh_tinh_nhan_vien(conn, clinic_id=cid, staff_id=sid) if sid else None
    if ai is None:
        raise SystemExit(f"Không thấy nhân viên đang làm có email {email!r}.")
    return ai


async def _main(a: argparse.Namespace) -> None:
    from clinicai.core.database import close_pool, create_pool

    cid = gmail.phong_kham_cua_khoa() or os.environ.get("GMAIL_CLINIC_ID")
    if not cid:
        raise SystemExit("Thiếu GMAIL_CLINIC_ID — không biết phòng khám nào.")
    cho_phep = os.environ.get("CHO_PHEP_GIO_KHAM") == "1"
    if (a.chay or a.hoan_tac) and trong_gio_kham(datetime.now(VN)) and not cho_phep:
        raise SystemExit("Đang giờ phòng khám dùng — chạy ngoài giờ.")
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            ai = await _nguoi(conn, cid, a.boi)
            dem = await xem_truoc(conn, cid, a.moc)
        print(f"Người đứng tên: {ai.full_name} · mốc: thư về trước {a.moc:%d/%m/%Y}")
        for k, v in sorted(dem.items()):
            print(f"  {v:>4} | {k}")
        print(f"  Tổng {sum(dem.values())} tờ.")
        if a.hoan_tac:
            so = await hoan_tac(pool, ai, a.hoan_tac)
            print(f"Hoàn tác lô {a.hoan_tac}: gỡ {so} tờ.")
        elif a.chay:
            kq = await chay(pool, ai, a.moc)
            print(f"ĐÃ CHẠY — lô {kq.pop('lo')}: {dict(kq)}")
        else:
            print("Mới XEM TRƯỚC, chưa ghi gì. Thêm --chay để chạy thật.")
    finally:
        await close_pool(pool)


def _tham_so() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--boi", required=True, help="email tài khoản đứng tên")
    p.add_argument("--moc", type=date.fromisoformat, default=MOC_MAC_DINH)
    p.add_argument("--chay", action="store_true")
    p.add_argument("--hoan-tac", dest="hoan_tac", default=None)
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(_main(_tham_so()))
