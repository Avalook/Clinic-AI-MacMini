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

LUẬT 6 CẢN (bảng `tep_ket_qua` thuộc module result_file — đường chuẩn là
`TepKetQuaService.xac_nhan_tep` / `danh_dau_da_gui`), vì sao ghi thẳng: gọi hai hàm đó
cho ~671 tờ cũ sẽ phát `result_file.confirmed` / `sent_to_patient` ⇒ ~671 chuông CSKH,
chạy lại vòng đọc của các lượt đã đóng, ~671 dòng dòng-thời-gian "đã gửi" giả; và
`danh_dau_da_gui` từ chối kênh ngoài `KENH_GUI_HOP_LE` (đúng ý: màn không được chọn
kênh này). Lệnh một lần ⇒ ghi thẳng, giữ đủ ràng buộc DB (trigger chuyển trạng thái,
cấm gửi tờ chưa Hợp lệ), sự kiện riêng `lab.old_result_*` để soát / hoàn tác.

    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi "TÊN TK"   # xem trước
    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi "TÊN TK" --chay
    python -m clinicai.services.xet_nghiem.gmail_bu_cu --boi "TÊN TK" \\
        --hoan-tac LO --ly-do "vì sao"
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
from clinicai.services.tep_ket_qua_service import kiem_tra_quyen_xac_nhan
from clinicai.services.xet_nghiem import gmail
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

KENH: Final = "NGOAI_HE_THONG"
MOC_MAC_DINH: Final = date(2026, 11, 11)
LY_DO: Final = "Bù 12/11: kết quả cũ, đã trả khách ngoài hệ thống (Tuyền duyệt)"
VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")

# Tờ còn hiệu lực đọc qua view chuẩn (không thu hồi, không xoá) — chỉ còn lọc trạng
# thái xác nhận + chưa gửi. Chỉ tờ của thư GMAIL (join drive_tep nguon GMAIL).
_CHON_SQL = """
SELECT k.id::text AS tep_id, k.xac_nhan_trang_thai AS truoc, d.ten AS lab,
       k.service_order_id IS NULL AS theo_luot
  FROM v_tep_ket_qua_hieu_luc k
  JOIN drive_tep t ON t.tep_ket_qua_id = k.id AND t.clinic_id = k.clinic_id
                  AND t.nguon = 'GMAIL'
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
 WHERE k.clinic_id = $1::uuid AND k.gui_luc IS NULL
   AND k.xac_nhan_trang_thai IN ('CHO_XAC_NHAN', 'HOP_LE')
   AND (t.email_nhan_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date < $2::date
 ORDER BY t.email_nhan_luc, k.id
"""
# Tờ của lô `$2` mà lần đánh GẦN NHẤT của nó đúng là lô này (đánh lại ở lô sau ⇒ không
# gỡ nhầm mốc của lô sau).
_LO_SQL = """
SELECT DISTINCT ON (e.payload->>'tep_id')
       e.payload->>'tep_id' AS tep_id, e.payload->>'truoc' AS truoc,
       e.payload->>'lo' AS lo
  FROM domain_event e
 WHERE e.clinic_id = $1::uuid AND e.event_type = 'lab.old_result_marked_delivered'
   AND e.payload->>'tep_id' IN (
       SELECT x.payload->>'tep_id' FROM domain_event x
        WHERE x.clinic_id = $1::uuid
          AND x.event_type = 'lab.old_result_marked_delivered'
          AND x.payload->>'lo' = $2)
 ORDER BY e.payload->>'tep_id', e.seq DESC
"""


def trong_gio_kham(luc: datetime) -> bool:
    """HÀM THUẦN: giờ phòng khám dùng (Tuyền 11/11) — ngày thường 15:30–23:00, cuối tuần
    06:30–23:00 (cùng ngưỡng các script deploy prod 11–12/11). Trong giờ ⇒ không ghi."""
    vn = luc.astimezone(VN)
    hm = vn.hour * 100 + vn.minute
    mo = 630 if vn.isoweekday() >= 6 else 1530
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
        await kiem_tra_quyen_xac_nhan(conn, identity=ai)
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
            await _su_kien(conn, ai, r, lo, "", hoan=False)
            da[r["truoc"]] += 1
    return {"lo": lo, **da}


async def so_to_cua_lo(conn: asyncpg.Connection, cid: str, lo: str) -> int:
    """Số tờ hoàn tác lô `lo` SẼ gỡ (xem trước của hoàn tác)."""
    return sum(1 for r in await conn.fetch(_LO_SQL, cid, lo) if r["lo"] == lo)


async def hoan_tac(
    pool: asyncpg.Pool, ai: StaffIdentity, lo: str, ly_do: object
) -> int:
    """Gỡ mốc "đã gửi ngoài hệ thống" của đúng lô `lo`: chỉ tờ còn kênh NGOAI_HE_THONG
    và lần đánh gần nhất là lô này (tờ đã gửi thật / đánh lại ở lô sau thì giữ).
    Ngoại lệ có duyệt của luật "không xoá mốc gửi": mốc này là ghi bù, không phải lần
    gửi thật. Bắt lý do ≥ 3 ký tự, ghi vào sự kiện."""
    ly = doc_ly_do(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        await kiem_tra_quyen_xac_nhan(conn, identity=ai)
        so = 0
        for r in await conn.fetch(_LO_SQL, ai.clinic_id, lo):
            if r["lo"] != lo:
                continue
            n = await conn.execute(
                "UPDATE tep_ket_qua SET gui_luc = NULL, gui_boi_staff_id = NULL,"
                "       gui_kenh = NULL"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid AND gui_kenh = $3",
                ai.clinic_id,
                r["tep_id"],
                KENH,
            )
            if n == "UPDATE 1":
                await _su_kien(conn, ai, r, lo, ly, hoan=True)
                so += 1
    return so


async def _su_kien(
    conn: asyncpg.Connection,
    ai: StaffIdentity,
    r: Any,
    lo: str,
    ly_do: str,
    *,
    hoan: bool,
) -> None:
    # Tên viết thẳng (không qua biến): test "mọi sự kiện có nơi phát" đọc chữ ở đây.
    await emit_event(
        conn,
        ten="lab.old_result_mark_undone" if hoan else "lab.old_result_marked_delivered",
        clinic_id=ai.clinic_id,
        aggregate_id=r["tep_id"],
        payload=XetNghiemBuKetQuaCu(
            tep_id=r["tep_id"], truoc=r["truoc"], lo=lo, ly_do=ly_do
        ),
        boi=nguoi(ai),
    )


async def _nguoi(conn: asyncpg.Connection, cid: str, ai_la: str) -> StaffIdentity:
    """Người đứng tên theo TÊN đúng của tài khoản hoặc email hồ sơ (prod để trống email
    trong `staff` — email đăng nhập ở kho đăng nhập riêng). Phải đúng MỘT người."""
    ds = await conn.fetch(
        "SELECT DISTINCT s.id::text AS id FROM staff s JOIN clinic_membership m"
        "    ON m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active"
        " WHERE s.is_active IS NOT FALSE"
        "   AND (s.full_name = $2 OR lower(coalesce(s.email, '')) = lower($2))",
        cid,
        ai_la.strip(),
    )
    if len(ds) != 1:
        raise SystemExit(f"{ai_la!r}: thấy {len(ds)} nhân viên đang làm — cần đúng 1.")
    ai = await danh_tinh_nhan_vien(conn, clinic_id=cid, staff_id=ds[0]["id"])
    if ai is None:
        raise SystemExit(f"{ai_la!r}: tài khoản chưa có cơ sở chính — không dùng được.")
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
            if a.hoan_tac:
                n = await so_to_cua_lo(conn, cid, a.hoan_tac)
                print(f"Người làm: {ai.full_name} · lô {a.hoan_tac}: {n} tờ sẽ gỡ.")
            else:
                dem = await xem_truoc(conn, cid, a.moc)
                print(f"Người đứng tên: {ai.full_name} · thư về trước {a.moc:%d/%m/%Y}")
                for k, v in sorted(dem.items()):
                    print(f"  {v:>4} | {k}")
                print(f"  Tổng {sum(dem.values())} tờ.")
        if a.hoan_tac:
            so = await hoan_tac(pool, ai, a.hoan_tac, a.ly_do)
            print(f"ĐÃ HOÀN TÁC lô {a.hoan_tac}: gỡ {so} tờ.")
        elif a.chay:
            kq = await chay(pool, ai, a.moc)
            print(f"ĐÃ CHẠY — lô {kq.pop('lo')}: {dict(kq)}")
        else:
            print("Mới XEM TRƯỚC, chưa ghi gì. Thêm --chay để chạy thật.")
    finally:
        await close_pool(pool)


def _tham_so() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--boi", required=True, help="tên đúng (hoặc email) tài khoản")
    p.add_argument("--moc", type=date.fromisoformat, default=MOC_MAC_DINH)
    p.add_argument("--chay", action="store_true")
    p.add_argument("--hoan-tac", dest="hoan_tac", default=None)
    p.add_argument("--ly-do", dest="ly_do", default="", help="bắt buộc khi hoàn tác")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(_main(_tham_so()))
