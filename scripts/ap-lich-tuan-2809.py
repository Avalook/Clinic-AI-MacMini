#!/usr/bin/env python3
"""Áp lịch làm việc tuần 28/09 → 04/10/2026 (bảng Tuyền gửi) lên prod.

Tuyền 28/09: "cái lịch này là của tuần này luôn, bạn áp lên prod cho tôi" +
"thêm quyền khám nội tiết cho phòng sàn chậu … mình open lego vào".

Làm ba việc, theo thứ tự:
  1. Phòng Sàn chậu thêm node KHAM-NOITIET → bác sĩ / thư ký / điều dưỡng xếp
     ở đó hôm nay có Bàn khám cho khách Nội tiết (quyền theo lịch,
     `quyen_theo_lich_bang`: tiền tố KHAM- → lego Bàn khám).
  2. Ca của tuần KHÔNG có trong bảng → gỡ (RosterService.remove — lịch hẹn mất
     bác sĩ chuyển "Lịch chờ xếp bác sĩ", không huỷ). Ca đã đúng → giữ nguyên.
  3. Ca trong bảng chưa có → xếp (RosterService.add_shift — cùng kiểm vai/vị
     trí, cùng sổ như màn Lịch làm việc), rồi CHỐT tuần (apply_week).

Tên viết tắt → hồ sơ trên prod: `TEN` dưới đây (Tuyền đối chiếu 28/09). Tên
còn None = chưa có hồ sơ / chưa chốt là ai → ô ấy BỎ QUA, in ra để xếp sau.

    docker cp scripts/ap-lich-tuan-2809.py <api>:/tmp/lich.py
    docker exec <api> python /tmp/lich.py          # THỬ KHÔ
    docker exec <api> python /tmp/lich.py --that   # làm thật

Chạy lại được: ca đúng rồi thì không đụng; node đã có thì bỏ qua.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

import asyncpg

PHONG_SAN_CHAU = "Phòng Sàn chậu"
NODE_THEM = "KHAM-NOITIET"
TU, DEN = date(2026, 9, 28), date(2026, 10, 4)

# Tên trong bảng → full_name trên prod. None = chưa có / chưa chốt.
TEN: dict[str, str | None] = {
    "Hà Vũ": "Vũ Thu Hà",
    "Quỳnh Anh": "Lê Quỳnh Anh",
    "Minh Thư": "Phùng Thị Minh Thư",
    "Dương Trang": "Dương Thị Thuỳ Trang",
    "Giầu": "Nguyễn Thị Ngọc Giàu",
    "Trà My": "Trà My",
    "Thủy Tiên": "Nguyễn Thuỷ Tiên",
    "Phương Anh": "Đỗ Thuý Phương Anh",
    "Hải Yến": "Lê Hải Yến",
    "Thanh Huyền": "Nguyễn Thanh Huyền",
    "Đức": "Nguyễn Hữu Đức",
    "N. Vân Anh": "Nguyễn Vân Anh",
    "Huế": "Vũ Thị Huế",
    "Thanh Phương": "Trần Phùng Thanh Phương",
    "Bình": "Đoàn Lộc Bình",
    "Phương Liên": "Nguyễn Phương Liên",
    "Trang Lê": "Lê Huyền Trang",
    "Minh Hằng": "Phan Thị Minh Hằng",
    "Hương Linh": "Trần Thị Hương Linh",
    "Phạm Hà": "Phạm Thị Hà",
    "Hồng Ngọc": "Phan Thị Hồng Ngọc",
    "BS Hằng": "BS Hằng",
    "BS Hùng": "BS Hùng",
    "BS Nam": "BS Nam",
    "BS Quyết": "BS Quyết",
    "BS Thiệp": "BS Thiệp",
    # Chưa có hồ sơ trên prod / chưa chốt (28/09):
    "BS T Linh": None,  # BS Nguyễn Thuỳ Linh — chưa có hồ sơ
    "BS X Thanh": None,  # BS Xuân Thanh — chưa có hồ sơ
    "BS Q Dũng": None,  # BS Hoàng Quốc Dũng — "BS Dũng" trên prod là ai?
    "BS Linh nam khoa": None,  # BS SA Bá Linh hay hồ sơ "BS Linh Nam khoa" (tắt)?
}

T2, T3, T4, T5, T6, T7, CN = (
    date(2026, 9, 28 + i) if i < 3 else date(2026, 10, i - 2) for i in range(7)
)
# Buổi: (ngày, ca).
TOI = [(d, "TOI") for d in (T2, T3, T4, T5, T6)]
T7S, T7C, CNS, CNC = (T7, "SANG"), (T7, "CHIEU"), (CN, "SANG"), (CN, "CHIEU")
BUOI = [*TOI, T7S, T7C, CNS, CNC]


def _hang(tram: tuple[str, ...], ten: list[str | None]) -> list[tuple]:
    """Một hàng của bảng: mỗi buổi một tên (None = ô trống / đen)."""
    assert len(ten) == len(BUOI)
    return [(d, ca, t, n) for (d, ca), n in zip(BUOI, ten) for t in tram if n]


def _hai(
    tram_a: str, tram_b: str, ten: list[str | tuple[str, str] | None]
) -> list[tuple]:
    """Ô gộp hai vị trí: một tên = cả hai; (a, b) = mỗi vị trí một người."""
    out: list[tuple] = []
    for (d, ca), n in zip(BUOI, ten):
        if not n:
            continue
        a, b = (n, n) if isinstance(n, str) else n
        out += [(d, ca, tram_a, a), (d, ca, tram_b, b)]
    return out


#              T2      T3        T4      T5      T6      T7S     T7C     CNS     CNC
LICH = [
    *_hang(
        ("T1_LETAN", "T1_THUNGAN"),
        [
            "Hà Vũ",
            "Quỳnh Anh",
            "Hà Vũ",
            "Quỳnh Anh",
            "Minh Thư",
            "Dương Trang",
            "Dương Trang",
            "Giầu",
            "Giầu",
        ],
    ),
    *_hang(
        ("T1_DOCHISO",),
        [
            "Trà My",
            "Thủy Tiên",
            "Thủy Tiên",
            "Phương Anh",
            "Phương Anh",
            "Hải Yến",
            "Hải Yến",
            "Thanh Huyền",
            "Thanh Huyền",
        ],
    ),
    *_hai(
        "T2_XEPTHUOC",
        "T2_TAODON",
        [
            ("Hà Vũ", "Trà My"),
            ("Quỳnh Anh", "Thủy Tiên"),
            "Đức",
            ("Quỳnh Anh", "Phương Anh"),
            ("Minh Thư", "Phương Anh"),
            ("Dương Trang", "Hải Yến"),
            ("Dương Trang", "Hải Yến"),
            ("Giầu", "Thanh Huyền"),
            "Đức",
        ],
    ),
    *_hang(
        ("T4_SANCHAU_BS",),
        [
            "BS T Linh",
            "BS T Linh",
            "BS Hằng",
            "BS Q Dũng",
            "BS Q Dũng",
            "BS X Thanh",
            "BS Q Dũng",
            "BS X Thanh",
            "BS Hằng",
        ],
    ),
    *_hai(
        "T4_SANCHAU_DD",
        "T4_BIO_DD",
        [
            "N. Vân Anh",
            "Hải Yến",
            ("Huế", "Thanh Phương"),
            "Bình",
            "N. Vân Anh",
            "Phương Liên",
            "Phương Liên",
            "Thanh Phương",
            ("Trang Lê", "Minh Thư"),
        ],
    ),
    # Phòng siêu âm 2 máy: hàng "BS 2 / Điều dưỡng 2" (prod có MỘT cặp vị trí).
    *_hang(
        ("T4_SA_BS1",),
        [
            None,
            None,
            "BS Linh nam khoa",
            None,
            None,
            None,
            None,
            "BS Linh nam khoa",
            None,
        ],
    ),
    *_hang(
        ("T4_SA_DD1",),
        [None, None, "Phạm Hà", None, None, None, None, "Hồng Ngọc", None],
    ),
    *_hang(
        ("T4_SAN_BS",),
        [
            "BS Hùng",
            "BS Nam",
            None,
            "BS Quyết",
            "BS Quyết",
            "BS Nam",
            "BS Hùng",
            "BS Thiệp",
            None,
        ],
    ),
    *_hang(
        ("T4_SAN_DD",),
        [
            "Minh Hằng",
            "Minh Hằng",
            None,
            "Huế",
            "Phạm Hà",
            "Hương Linh",
            "Hương Linh",
            "Trang Lê",
            None,
        ],
    ),
]


async def main() -> int:
    from clinicai.api.exceptions import ValidationError
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.config_service import RosterService

    that = "--that" in sys.argv
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn)
    try:
        phong = await pool.fetchrow(
            "SELECT id::text AS id, clinic_id::text AS cid FROM clinic_room"
            " WHERE name = $1 AND is_active",
            PHONG_SAN_CHAU,
        )
        if phong is None:
            raise SystemExit(f"✗ Không thấy {PHONG_SAN_CHAU} đang bật.")
        cid = phong["cid"]
        ql = await pool.fetchrow(
            """
            SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name,
                   s.primary_location_id::text AS lid
              FROM staff s JOIN clinic_membership m ON m.staff_id = s.id
               AND m.is_active AND m.clinic_id = $1::uuid
             WHERE m.role = 'MANAGEMENT' AND s.is_active
             ORDER BY (s.full_name = 'Quản lý hệ thống') DESC LIMIT 1
            """,
            cid,
        )
        ident = StaffIdentity(
            staff_id=ql["id"],
            auth_user_id=ql["au"] or "",
            full_name=ql["full_name"],
            department="MANAGEMENT",
            role=ClinicRole.MANAGEMENT,
            clinic_id=cid,
            location_id=ql["lid"],
            location_name=None,
        )
        nv = {
            r["full_name"]: r
            for r in await pool.fetch(
                "SELECT s.id::text AS id, s.full_name, s.primary_department AS vai"
                " FROM staff s JOIN clinic_membership m ON m.staff_id = s.id"
                " AND m.is_active AND m.clinic_id = $1::uuid WHERE s.is_active",
                cid,
            )
        }
        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · dưới tên {ql['full_name']}")

        # ── 1. Node Khám Nội tiết cho Phòng Sàn chậu ──
        co_node = await pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_room_node"
            " WHERE room_id = $1::uuid AND node_code = $2)",
            phong["id"],
            NODE_THEM,
        )
        print(f"\n1. {PHONG_SAN_CHAU} + {NODE_THEM}: {'đã có' if co_node else 'THÊM'}")

        # ── Kế hoạch ──
        can: dict[tuple, str] = {}  # (ngày, ca, trạm, staff_id) → tên
        bo_qua: list[str] = []
        loi: list[str] = []
        svc = RosterService(pool)
        async with pool.acquire() as conn:
            for d, ca, tram, ten in LICH:
                full = TEN.get(ten, "?")
                if full == "?":
                    loi.append(f"{d:%d/%m} {ca} {tram}: tên lạ “{ten}”")
                    continue
                if full is None:
                    bo_qua.append(f"{d:%d/%m} {ca} {tram}: {ten}")
                    continue
                r = nv.get(full)
                if r is None:
                    loi.append(f"{d:%d/%m} {ca} {tram}: không có hồ sơ “{full}”")
                    continue
                try:
                    await svc._kiem_pham_vi_tram(
                        conn, clinic_id=cid, station=tram, vai=r["vai"], ten=full
                    )
                except ValidationError as e:
                    loi.append(f"{d:%d/%m} {ca} {tram}: {e}")
                    continue
                can[(d, ca, tram, r["id"])] = full
        dang = await pool.fetch(
            "SELECT id::text AS id, work_date, shift, station, staff_id::text AS sid,"
            " staff_name, status FROM work_roster WHERE clinic_id = $1::uuid"
            " AND work_date BETWEEN $2 AND $3",
            cid,
            TU,
            DEN,
        )
        giu = {
            (r["work_date"], r["shift"], r["station"], r["sid"])
            for r in dang
            if (r["work_date"], r["shift"], r["station"], r["sid"]) in can
            and r["status"] == "APPROVED"
        }
        go = [
            r
            for r in dang
            if (r["work_date"], r["shift"], r["station"], r["sid"]) not in giu
        ]
        them = [k for k in can if k not in giu]

        mat_bs = 0
        for r in go:
            kq = await svc.remove(roster_id=r["id"], identity=ident, dry_run=True)
            mat_bs += int(kq.get("so_lich_cho_xep") or 0)
        print(
            f"\n2. Ca đang có trong tuần: {len(dang)} · giữ {len(giu)} · GỠ {len(go)}"
            f" (lịch hẹn sẽ chuyển 'chờ xếp bác sĩ': {mat_bs})"
        )
        for r in sorted(go, key=lambda r: (r["work_date"], r["shift"], r["station"])):
            print(
                f"   - {r['work_date']:%d/%m} {r['shift']:5} {r['station']:18}"
                f" {r['staff_name']}"
            )
        print(f"\n3. XẾP MỚI: {len(them)} ca")
        for d, ca, tram, _sid in sorted(them):
            print(f"   + {d:%d/%m} {ca:5} {tram:18} {can[(d, ca, tram, _sid)]}")
        if bo_qua:
            print(f"\n⚠ BỎ QUA {len(bo_qua)} ô — chưa có hồ sơ / chưa chốt là ai:")
            for x in bo_qua:
                print(f"   ? {x}")
        if loi:
            print(f"\n✗ {len(loi)} ô KHÔNG xếp được:")
            for x in loi:
                print(f"   ✗ {x}")
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
            return 0

        if not co_node:
            await pool.execute(
                "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
                " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
                cid,
                phong["id"],
                NODE_THEM,
            )
        for r in go:
            await svc.remove(roster_id=r["id"], identity=ident)
        for i, (d, ca, tram, sid) in enumerate(sorted(them)):
            await svc.add_shift(
                work_date=d,
                station=tram,
                shift=ca,
                identity=ident,
                staff_id=sid,
                sort=i,
            )
        await svc.apply_week(week_start=TU, identity=ident)
        print(f"\n✓ Xong: gỡ {len(go)}, xếp {len(them)}, chốt tuần {TU:%d/%m}.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
