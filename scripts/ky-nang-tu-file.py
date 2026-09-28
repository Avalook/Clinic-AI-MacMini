#!/usr/bin/env python3
"""Đổ KỸ NĂNG từ file nhân sự phòng khám vào bảng ky_nang / nhan_su_ky_nang.

Tuyền chốt 28/09/2026 (phân quyền bản "D"): màn Phân quyền tick theo kỹ năng.
Hôm 27/09 quyền (lego) đã được áp THEO ĐÚNG file này bằng kim-nguu-3-tang-2709.py
— nên script này KHÔNG đụng quyền: chỉ ghi định nghĩa 12 kỹ năng (cùng bảng đổi
kỹ năng → lego + phòng) và ai có kỹ năng nào. Quyền từng người giữ nguyên.

    docker cp scripts/ky-nang-tu-file.py <api>:/tmp/kn2.py
    docker cp ky-nang.json <api>:/tmp/ky-nang.json
    docker exec <api> python /tmp/kn2.py --ky-nang /tmp/ky-nang.json          # THỬ KHÔ
    docker exec <api> python /tmp/kn2.py --ky-nang /tmp/ky-nang.json --that   # làm thật
    # Người MỚI tạo tài khoản: thêm --cap-quyen = tick qua KyNangService (bật lego).

Local: PYTHONPATH=src DATABASE_URL=... .venv/bin/python scripts/ky-nang-tu-file.py …

Chạy lại được (upsert định nghĩa, thêm thành viên còn thiếu, không xoá ai).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import asyncpg

# Cùng bảng đổi với kim-nguu-3-tang-2709.py (KY_NANG) — (mã, tên, nhóm, lego, mã phòng).
_LE_TAN = (
    "tiep_don",
    "ds_benh_nhan",
    "them_benh_nhan",
    "thu_tien_dv",
    "thu_tien_thuoc",
)
_SA, _TTP = ("KN-SA-T1", "KN-SA1"), ("KN-THUTHUAT", "KN-TTNG")
KY_NANG: list[tuple[str, str, str, tuple[str, ...], tuple[str, ...]]] = [
    ("le_tan", "Lễ tân", "Tiếp đón & thu", _LE_TAN, ()),
    ("cskh", "CSKH", "Tiếp đón & thu", ("cham_soc_khach",), ()),
    ("do_chi_so", "Đo chỉ số sk", "Khám", ("do_sinh_hieu",), ()),
    ("hoi_benh", "Hỏi bệnh", "Khám", ("tu_van",), ()),
    ("tkyk", "TKYK", "Khám", ("ban_kham",), ()),
    ("phu_bs_san", "Phụ BS Sản", "Khám", ("ban_kham",), ()),
    ("phu_sa", "Phụ SA", "Phòng dịch vụ", ("phong",), _SA),
    ("thu_thuat", "Thủ thuật", "Phòng dịch vụ", ("phong",), _TTP),
    ("lay_mau", "Lấy mẫu xét nghiệm", "Phòng dịch vụ", ("phong",), ("KN-LAYMAU",)),
    ("phu_san_chau", "Phụ sàn chậu", "Phòng dịch vụ", ("phong",), ("KN-SANCHAU",)),
    ("bio", "Bio", "Phòng dịch vụ", ("phong",), ("KN-SAN-BIO",)),
    ("thuoc", "Thuốc", "Nhà thuốc", ("kho_thuoc",), ()),
]
# Tên trong file → tài khoản (cùng BI_DANH của kim-nguu-3-tang-2709.py).
# 28/09: hồ sơ đã đổi tên theo file (tai-khoan-theo-danh-sach.py); hồ sơ "ĐD …"
# trùng người đã khoá (không còn khớp vì chỉ đọc hồ sơ đang làm việc).
BI_DANH: dict[str, tuple[str, ...]] = {
    "Nguyễn Thị Ngọc Giầu": ("Nguyễn Thị Ngọc Giàu", "ĐD Giầu"),
    "Vũ Thị Huế": ("Vũ Thị Huế", "ĐD Huế"),
    "Phùng Thị Minh Thư": ("Phùng Thị Minh Thư", "ĐD Thư"),
    "Phan Thị Minh Hằng": ("Phan Thị Minh Hằng", "ĐD Hằng"),
    "Nguyễn Vân Anh": ("Nguyễn Vân Anh", "TL Vân Anh"),
    "Hồng Ngọc": ("Phan Thị Hồng Ngọc",),
}


async def _cap_quyen(cid: str, gan: list[tuple[str, str, str]]) -> int:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.ky_nang_service import KyNangService

    pool = await asyncpg.create_pool(_dsn())
    try:
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
        co = {
            (r["staff_id"], r["ky_nang_ma"])
            for r in await pool.fetch(
                "SELECT staff_id::text AS staff_id, ky_nang_ma FROM nhan_su_ky_nang"
                " WHERE clinic_id = $1::uuid",
                cid,
            )
        }
        svc = KyNangService(pool)
        so = 0
        for sid, tk, ma in gan:
            if (sid, ma) in co:
                continue
            await svc.doi(staff_id=sid, ma=ma, bat=True, identity=ident)
            print(f"    + {tk}: {ma}")
            so += 1
        print(f"  ✓ cấp quyền {so} lượt gán mới (thao tác dưới tên {ql['full_name']})")
        return 0
    finally:
        await pool.close()


def _dsn() -> str:
    u = os.environ.get("DATABASE_URL", "")
    if not u:
        raise SystemExit("✗ Thiếu DATABASE_URL.")
    return u.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    if "--ky-nang" not in sys.argv:
        raise SystemExit("✗ Thiếu --ky-nang <tệp JSON {họ tên: [kỹ năng]}>.")
    with open(sys.argv[sys.argv.index("--ky-nang") + 1], encoding="utf-8") as f:
        file: dict[str, list[str]] = json.load(f)
    that = "--that" in sys.argv
    ten_ma = {ten: ma for ma, ten, *_ in KY_NANG}
    la = sorted({k for ks in file.values() for k in ks} - set(ten_ma))
    if la:
        raise SystemExit(f"✗ Kỹ năng lạ trong file: {la} — DỪNG, bổ sung KY_NANG.")

    conn = await asyncpg.connect(_dsn())
    try:
        cid = await conn.fetchval(
            "SELECT clinic_id::text FROM clinic_room WHERE code = 'KN-TIEPDON' LIMIT 1"
        )
        if not cid:
            raise SystemExit("✗ Không thấy phòng KN-TIEPDON — chưa có cơ sở Kim Ngưu.")
        phong = {
            r["code"]: r["id"]
            for r in await conn.fetch(
                "SELECT code, id::text AS id FROM clinic_room"
                " WHERE clinic_id = $1::uuid",
                cid,
            )
        }
        thieu = sorted({c for *_, ps in KY_NANG for c in ps} - set(phong))
        if thieu:
            raise SystemExit(f"✗ Thiếu phòng {thieu} — DỪNG.")
        nguoi = await conn.fetch(
            "SELECT s.id::text AS id, s.full_name FROM staff s"
            "  JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active"
            "   AND m.clinic_id = $1::uuid WHERE s.is_active",
            cid,
        )
        theo_ten: dict[str, list[str]] = {}
        for n in nguoi:
            theo_ten.setdefault(n["full_name"], []).append(n["id"])

        gan: list[tuple[str, str, str]] = []  # (staff_id, tên tài khoản, mã kỹ năng)
        chua_co: list[str] = []
        for ten, ks in file.items():
            tks = [t for t in BI_DANH.get(ten, (ten,)) if t in theo_ten]
            if not tks:
                chua_co.append(ten)
                continue
            for tk in tks:
                for sid in theo_ten[tk]:
                    gan.extend((sid, tk, ten_ma[k]) for k in ks)

        print(f"{'LÀM THẬT' if that else 'THỬ KHÔ'} · phòng khám {cid}")
        print(
            f"  {len(KY_NANG)} kỹ năng · {len(gan)} lượt gán cho "
            f"{len({g[0] for g in gan})} tài khoản"
        )
        print(
            f"  người trong file CHƯA có tài khoản ({len(chua_co)}): "
            f"{', '.join(chua_co) or '—'}"
        )
        if not that:
            return 0
        async with conn.transaction():
            for i, (ma, ten, nhom, lego, ps) in enumerate(KY_NANG):
                await conn.execute(
                    """
                    INSERT INTO ky_nang
                        (clinic_id, ma, ten, nhom, thu_tu, lego, phong_ids)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6::text[], $7::uuid[])
                    ON CONFLICT (clinic_id, ma) DO UPDATE
                       SET ten = EXCLUDED.ten, nhom = EXCLUDED.nhom,
                           thu_tu = EXCLUDED.thu_tu, lego = EXCLUDED.lego,
                           phong_ids = EXCLUDED.phong_ids, updated_at = now()
                    """,
                    cid,
                    ma,
                    ten,
                    nhom,
                    (i + 1) * 10,
                    list(lego),
                    [phong[c] for c in ps],
                )
            them = 0
            if "--cap-quyen" in sys.argv:
                # Người MỚI (chưa có lượt gán): tick qua KyNangService — ghi
                # thành viên + bật đúng lego của kỹ năng, cùng đường màn Phân quyền.
                print("  (cấp quyền theo kỹ năng cho lượt gán mới — sau giao dịch)")
                return await _cap_quyen(cid, gan)
            for sid, _tk, ma in gan:
                kq = await conn.execute(
                    "INSERT INTO nhan_su_ky_nang (clinic_id, staff_id, ky_nang_ma)"
                    " VALUES ($1::uuid, $2::uuid, $3) ON CONFLICT DO NOTHING",
                    cid,
                    sid,
                    ma,
                )
                them += int(kq.split()[-1])
        print(f"  ✓ đã ghi {len(KY_NANG)} kỹ năng, thêm {them} lượt gán mới")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
