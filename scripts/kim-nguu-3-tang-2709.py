#!/usr/bin/env python3
"""Dựng lại cấu trúc phòng khám: chỉ còn Kim Ngưu, 3 tầng; gán lego theo vai.

ĐÃ CŨ từ 01/10/2026: tên / tầng phòng theo bảng lịch Tuyền gửi nằm ở migration
20261001200000_phong_theo_bang_lich.sql (Quầy thuốc Tầng 2, gộp hai phòng siêu
âm…). Chạy lại script này sẽ ĐƯA TÊN PHÒNG VỀ BẢN 27/09 — chỉ để tra lịch sử.

    docker cp scripts/kim-nguu-3-tang-2709.py <api>:/tmp/kn.py
    docker cp ky-nang.json <api>:/tmp/ky-nang.json   # KHÔNG trong git (tên người thật)
    docker exec <api> python /tmp/kn.py --ky-nang /tmp/ky-nang.json          # THỬ KHÔ
    docker exec <api> python /tmp/kn.py --ky-nang /tmp/ky-nang.json --that   # làm thật

Tuyền chốt 27/09/2026 tối (chat):
  * Xoá cơ sở "Phòng khám Dr4Women" và "Hào Nam" — lịch hẹn / lượt khám / khách
    của Dr4Women CHUYỂN sang Kim Ngưu trước (giữ lịch sử), rồi xoá phòng + cơ sở.
  * Kim Ngưu: T1 Quầy lễ tân · Đo sinh hiệu · Kho thuốc · Bác sĩ tư vấn · Phòng
    bác sĩ chính; T2 Phòng siêu âm 1, 2; T3 Phòng thủ thuật 1, 2 · Phòng đối
    tác. Lấy mẫu làm ở thủ thuật + siêu âm. Mỗi phòng một TV.
    DÙNG LẠI phòng cũ (đổi tên / tầng) để lịch sử lượt khám không mồ côi; phòng
    thừa TẮT, không xoá.
  * Lego (node thanh bên): người có trong file nhân sự của phòng khám ("Sáng Ý -
    Thông tin nhân sự.xlsx" → `ky-nang.json` {họ tên: [kỹ năng]}) = HỢP các kỹ
    năng (`KY_NANG`) — trần quyền; lịch làm việc quyết hôm nay đứng đâu. Người
    không có trong file: THEO VAI (`LEGO_THEO_VAI`). Quản lý thêm Điều phối.
  * Giữ phòng Sàn chậu + Sản-Biofeedback (Tầng 3) — 17 / 13 người có kỹ năng ấy.

Hai pha: (1) cấu trúc — MỘT giao dịch SQL; (2) lego — qua
`PermissionService.doi_lego` (cùng cửa màn Phân quyền, có nhật ký), chạy sau khi
pha 1 đã ghi. Thử khô: pha 1 ROLLBACK, pha 2 chỉ in kế hoạch.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import asyncpg

KN = "Kim Ngưu"
XOA = ("Phòng khám Dr4Women", "Hào Nam")

_TT = [
    "DICHVU-THUTHUAT",
    "DICHVU-LAYMAU-AMDAO",
    "DICHVU-SANGLOC-COTUCUNG",
    "DICHVU-LAYMAU-MAU",
    "DICHVU-LAYMAU-NUOCTIEU",
    "DICHVU-TINHDICHDO",
]
_SA = ["DICHVU-SIEUAM", "DICHVU-LAYMAU-MAU", "DICHVU-LAYMAU-NUOCTIEU", "DICHVU-LAYMAU-AMDAO"]
_KHAM = ["KHAM-NOITIET", "KHAM-PHUKHOA", "KHAM-SANKHOA", "KHAM-NAMKHOA", "KHAM-HIEMMUON-VOSINH"]
_THUOC = ["THUOC-04", "DICHVU-THUOC", "THUOC-01", "THUOC-02", "THUOC-03"]
_DT = [
    "DICHVU-LAYMAU-MAU",
    "DICHVU-DXA",
    "DICHVU-HINHANH-NGOAI",
    "DICHVU-LAYMAU-AMDAO",
    "DICHVU-LAYMAU-NUOCTIEU",
    "DICHVU-SANGLOC-COTUCUNG",
]

# code phòng → (tên mới, tầng, sort, việc phục vụ; việc đầu = việc chính)
PHONG: dict[str, tuple[str, str, int, list[str] | None]] = {
    "KN-TIEPDON": ("Quầy lễ tân", "Tầng 1", 10, ["LUOTKHAM-01", "LUOTKHAM-14"]),
    "KN-DOCHISO": ("Đo sinh hiệu", "Tầng 1", 20, ["LUOTKHAM-03", "DICHVU-DXA"]),
    "KN-QUAYTHUOC": ("Kho thuốc", "Tầng 1", 30, _THUOC),
    "KN-TUVAN": ("Bác sĩ tư vấn", "Tầng 1", 40, ["LUOTKHAM-02"]),
    "KN-NOITIET": ("Phòng bác sĩ chính", "Tầng 1", 50, _KHAM),
    "KN-SA-T1": ("Phòng siêu âm 1", "Tầng 2", 60, _SA),
    "KN-SA1": ("Phòng siêu âm 2", "Tầng 2", 70, _SA),
    "KN-THUTHUAT": ("Phòng thủ thuật 1", "Tầng 3", 80, _TT),
    "KN-TTNG": ("Phòng thủ thuật 2", "Tầng 3", 90, _TT),
    # Giữ nguyên việc (None) — chỉ chuyển tầng / thứ tự / bật TV.
    "KN-SANCHAU": ("Phòng Sàn chậu", "Tầng 3", 92, None),
    "KN-SAN-BIO": ("Phòng Sản - Biofeedback", "Tầng 3", 94, None),
    "KN-DOITAC": ("Phòng đối tác", "Tầng 3", 100, _DT),
}
TAT = ("KN-LAYMAU", "KN-SA2")
# Vị trí "Hỏi bệnh ban đầu" sang phòng tư vấn mới.
VI_TRI_SANG = {"T1_HOIBENH": "KN-TUVAN"}
CHUA_XONG = ("done", "completed", "cancelled", "not_performed")


def phong_thay(node: str | None) -> str:
    """Phòng Kim Ngưu nhận lịch sử của một phòng bị xoá / tắt, theo việc chính."""
    n = node or ""
    if n == "LUOTKHAM-03":
        return "KN-DOCHISO"
    if n.startswith("THUOC") or n == "DICHVU-THUOC":
        return "KN-QUAYTHUOC"
    if n.startswith("KHAM-"):
        return "KN-NOITIET"
    if n == "DICHVU-SIEUAM":
        return "KN-SA-T1"
    if n in ("DICHVU-DXA", "DICHVU-HINHANH-NGOAI"):
        return "KN-DOITAC"
    if n.startswith("DICHVU-"):
        return "KN-THUTHUAT"
    return "KN-TIEPDON"


LEGO_THEO_VAI: dict[str, set[str]] = {
    "RECEPTION": {"tiep_don", "ds_benh_nhan", "them_benh_nhan", "thu_tien_dv", "thu_tien_thuoc"},
    "RECEPTION_DD": {"do_sinh_hieu"},  # tài khoản vai lễ tân tên "ĐD …"
    "DOCTOR": {"tu_van", "ban_kham"},
    "TKYK": {"ban_kham"},
    "NURSE_ULTRASOUND": {"phong"},
    "PARTNER": {"doi_tac"},
}
PHONG_DD_SA = ("KN-SA-T1", "KN-SA1", "KN-THUTHUAT", "KN-TTNG")

# Kỹ năng trong file nhân sự → (lego, phòng của lego "phong").
_LE_TAN = {
    "tiep_don", "ds_benh_nhan", "them_benh_nhan", "thu_tien_dv", "thu_tien_thuoc", "dat_lich"
}
_SA, _TTP = ("KN-SA-T1", "KN-SA1"), ("KN-THUTHUAT", "KN-TTNG")
KY_NANG: dict[str, tuple[set[str], tuple[str, ...]]] = {
    "Lễ tân": (_LE_TAN, ()),
    "Đo chỉ số sk": ({"do_sinh_hieu"}, ()),
    "Hỏi bệnh": ({"tu_van"}, ()),
    "TKYK": ({"ban_kham"}, ()),
    "Phụ BS Sản": ({"ban_kham"}, ()),
    "Phụ SA": ({"phong"}, _SA),
    "Thủ thuật": ({"phong"}, _TTP),
    "Lấy mẫu xét nghiệm": ({"phong", "doi_tac"}, ("KN-LAYMAU",)),
    "Phụ sàn chậu": ({"phong"}, ("KN-SANCHAU",)),
    "Bio": ({"phong"}, ("KN-SAN-BIO",)),
    "Thuốc": ({"kho_thuoc"}, ()),
    "CSKH": ({"cham_soc_khach", "dat_lich", "them_benh_nhan"}, ()),
}
# Tên trong file → (các) tài khoản trên hệ thống khi tên không khớp nguyên văn.
# Nghi một người hai tài khoản: Tuyền 27/09 — áp kỹ năng cho CẢ HAI.
BI_DANH: dict[str, tuple[str, ...]] = {
    "Nguyễn Thị Ngọc Giầu": ("Nguyễn Thị Ngọc Giàu", "ĐD Giầu"),
    "Vũ Thị Huế": ("ĐD Huế",),
    "Phùng Thị Minh Thư": ("Phùng Thị Minh Thư", "ĐD Thư"),
    "Phan Thị Minh Hằng": ("Phan Thị Minh Hằng", "ĐD Hằng"),
    "Nguyễn Vân Anh": ("TL Vân Anh",),
}


def quyen_tu_ky_nang(ky_nang: list[str]) -> tuple[set[str], list[str]]:
    """Hợp lego + phòng của các kỹ năng. Kỹ năng lạ → báo, không đoán."""
    lego: set[str] = set()
    phong: set[str] = set()
    for k in ky_nang:
        if k not in KY_NANG:
            raise SystemExit(f"✗ Kỹ năng lạ trong file: {k!r} — DỪNG, bổ sung KY_NANG.")
        lg, ph = KY_NANG[k]
        lego |= lg
        phong |= set(ph)
    return lego, sorted(phong)


def so(kq: str) -> int:
    return int(kq.split()[-1])


async def pha_cau_truc(conn: asyncpg.Connection, cid: str) -> dict[str, str]:
    kn = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid AND name=$2", cid, KN
    )
    if not kn:
        raise SystemExit("✗ Không thấy cơ sở Kim Ngưu — DỪNG.")
    await conn.execute("UPDATE clinic_location SET is_active=TRUE WHERE id=$1::uuid", kn)

    if not await conn.fetchval(
        "SELECT 1 FROM clinic_room WHERE clinic_id=$1::uuid AND code='KN-TUVAN'", cid
    ):
        await conn.execute(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code, floor, sort)"
            " VALUES ($1::uuid, $2::uuid, 'KN-TUVAN', 'Bác sĩ tư vấn', 'LUOTKHAM-02', 'Tầng 1', 40)",
            cid,
            kn,
        )
        print("  + tạo phòng Bác sĩ tư vấn (KN-TUVAN)")
    ma_id = {
        r["code"]: r["id"]
        for r in await conn.fetch(
            "SELECT code, id::text AS id FROM clinic_room"
            " WHERE clinic_id=$1::uuid AND location_id=$2::uuid",
            cid,
            kn,
        )
    }
    thieu = [c for c in list(PHONG) + list(TAT) if c not in ma_id]
    if thieu:
        raise SystemExit(f"✗ Kim Ngưu thiếu phòng {thieu} — DỪNG.")

    # 1. Chuyển dữ liệu của cơ sở bị xoá sang Kim Ngưu, rồi xoá.
    for ten in XOA:
        lid = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid AND name=$2", cid, ten
        )
        if not lid:
            print(f"  · {ten}: không có — bỏ qua")
            continue
        for p in await conn.fetch(
            "SELECT id::text AS id, code, node_code FROM clinic_room WHERE location_id=$1::uuid", lid
        ):
            moi = ma_id[phong_thay(p["node_code"])]
            n = 0
            for bang, cot in (
                ("visit", "current_room_id"),
                ("work_item", "room_id"),
                ("service_order", "room_id"),
                ("service_order", "phong_du_kien_id"),
                ("queue_entry", "room_id"),
                ("service_execution_attempt", "room_id_snapshot"),
            ):
                n += so(
                    await conn.execute(
                        f"UPDATE {bang} SET {cot}=$1::uuid WHERE {cot}=$2::uuid", moi, p["id"]
                    )
                )
            await conn.execute(
                "UPDATE vi_tri_lam_viec SET room_id=NULL, is_active=FALSE WHERE room_id=$1::uuid",
                p["id"],
            )
            print(f"  · {ten} / {p['code']} → {phong_thay(p['node_code'])}: {n} dòng lịch sử")
        for bang, cot in (
            ("appointment", "location_id"),
            ("patient", "location_id"),
            ("visit", "location_id"),
            ("pregnancy", "location_id"),
            ("work_session", "location_id"),
            ("staff_task", "location_id"),
            ("staff", "primary_location_id"),
        ):
            n = so(await conn.execute(f"UPDATE {bang} SET {cot}=$1::uuid WHERE {cot}=$2::uuid", kn, lid))
            if n:
                print(f"  · {ten}: {bang}.{cot} → Kim Ngưu: {n}")
        for bang in ("block_budget", "visit_gate_rule", "staff_node"):
            n = so(await conn.execute(f"DELETE FROM {bang} WHERE location_id=$1::uuid", lid))
            if n:
                print(f"  · {ten}: xoá cấu hình {bang}: {n}")
        n = so(await conn.execute("DELETE FROM clinic_room WHERE location_id=$1::uuid", lid))
        await conn.execute("DELETE FROM clinic_location WHERE id=$1::uuid", lid)
        print(f"  ✓ xoá cơ sở {ten} ({n} phòng)")

    # 2. Kim Ngưu: đổi tên / tầng / việc; bật TV mọi phòng.
    for code, (ten, tang, sort, viec) in PHONG.items():
        rid = ma_id[code]
        if viec is None:
            await conn.execute(
                "UPDATE clinic_room SET name=$2, floor=$3, sort=$4, is_active=TRUE,"
                " show_on_tv=TRUE, updated_at=now() WHERE id=$1::uuid",
                rid,
                ten,
                tang,
                sort,
            )
            print(f"  ✓ {tang} · {ten} ({code}): giữ việc cũ")
            continue
        await conn.execute(
            "UPDATE clinic_room SET name=$2, floor=$3, sort=$4, node_code=$5, is_active=TRUE,"
            " show_on_tv=TRUE, updated_at=now() WHERE id=$1::uuid",
            rid,
            ten,
            tang,
            sort,
            viec[0],
        )
        await conn.execute("DELETE FROM clinic_room_node WHERE room_id=$1::uuid", rid)
        for v in viec:
            await conn.execute(
                "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
                " VALUES ($1::uuid, $2::uuid, $3)",
                cid,
                rid,
                v,
            )
        print(f"  ✓ {tang} · {ten} ({code}): {', '.join(viec)}")

    # 3. Phòng thừa: chuyển chỉ định chưa xong sang phòng thay, rồi TẮT (không xoá).
    for code in TAT:
        rid = ma_id[code]
        node = await conn.fetchval("SELECT node_code FROM clinic_room WHERE id=$1::uuid", rid)
        n = so(
            await conn.execute(
                "UPDATE service_order SET room_id=$1::uuid WHERE room_id=$2::uuid"
                " AND exec_status <> ALL($3::text[])",
                ma_id[phong_thay(node)],
                rid,
                list(CHUA_XONG),
            )
        )
        await conn.execute(
            "UPDATE clinic_room SET is_active=FALSE, show_on_tv=FALSE, updated_at=now()"
            " WHERE id=$1::uuid",
            rid,
        )
        m = so(
            await conn.execute(
                "UPDATE vi_tri_lam_viec SET is_active=FALSE WHERE room_id=$1::uuid", rid
            )
        )
        print(f"  ✓ tắt {code} ({m} vị trí tắt, {n} chỉ định chưa xong → {phong_thay(node)})")
    for vt, code in VI_TRI_SANG.items():
        await conn.execute(
            "UPDATE vi_tri_lam_viec SET room_id=$1::uuid, is_active=TRUE"
            " WHERE clinic_id=$2::uuid AND code=$3",
            ma_id[code],
            cid,
            vt,
        )

    # 4. In lại: vị trí của từng phòng; việc không còn phòng đang bật phục vụ.
    for r in await conn.fetch(
        """
        SELECT r.floor, r.name,
               coalesce(string_agg(v.ten, ', ' ORDER BY v.sort), '— chưa có vị trí —') AS vt
          FROM clinic_room r
          LEFT JOIN vi_tri_lam_viec v ON v.room_id = r.id AND v.is_active
         WHERE r.clinic_id=$1::uuid AND r.is_active GROUP BY r.id ORDER BY r.floor, r.sort
        """,
        cid,
    ):
        print(f"    {r['floor']} · {r['name']}: {r['vt']}")
    mo_coi = await conn.fetch(
        """
        SELECT DISTINCT rn.node_code FROM clinic_room_node rn
          JOIN clinic_room r ON r.id = rn.room_id AND r.clinic_id = $1::uuid
         WHERE NOT EXISTS (SELECT 1 FROM clinic_room_node x JOIN clinic_room y ON y.id = x.room_id
                            WHERE x.node_code = rn.node_code AND y.is_active)
        """,
        cid,
    )
    print(f"    việc mất phòng phục vụ: {[r['node_code'] for r in mo_coi] or 'không có'}")
    return ma_id


async def pha_lego(
    pool: asyncpg.Pool, cid: str, ma_id: dict[str, str], that: bool, ky_nang: dict[str, list[str]]
) -> None:
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.permission_service import PermissionService

    ql = await pool.fetchrow(
        """
        SELECT s.id::text AS id, s.auth_user_id::text AS au, s.full_name, l.id::text AS lid
          FROM staff s JOIN clinic_membership m ON m.staff_id=s.id AND m.is_active
          JOIN clinic_location l ON l.clinic_id=m.clinic_id AND l.name=$2
         WHERE m.clinic_id=$1::uuid AND m.role='MANAGEMENT' AND s.is_active
         ORDER BY (s.full_name='Quản lý hệ thống') DESC LIMIT 1
        """,
        cid,
        KN,
    )
    ident = StaffIdentity(
        staff_id=ql["id"],
        auth_user_id=ql["au"] or "",
        full_name=ql["full_name"],
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=cid,
        location_id=ql["lid"],
        location_name=KN,
    )
    print(f"  (thao tác dưới tên {ql['full_name']})")
    svc = PermissionService(pool)
    nguoi = await pool.fetch(
        """
        SELECT s.id::text AS id, s.full_name, m.role FROM staff s
          JOIN clinic_membership m ON m.staff_id=s.id AND m.is_active AND m.clinic_id=$1::uuid
         WHERE s.is_active ORDER BY m.role, s.full_name
        """,
        cid,
    )
    phong_dd = sorted(ma_id[c] for c in PHONG_DD_SA)
    # Tài khoản → kỹ năng (theo họ tên nguyên văn, hoặc bí danh).
    theo_tk: dict[str, list[str]] = {}
    for ten, ks in ky_nang.items():
        for tk in BI_DANH.get(ten, (ten,)):
            theo_tk.setdefault(tk, []).extend(ks)
    co_tk = {n["full_name"] for n in nguoi}
    chua_co = [t for t in ky_nang if not any(tk in co_tk for tk in BI_DANH.get(t, (t,)))]
    print(f"  người trong file CHƯA có tài khoản ({len(chua_co)}): {', '.join(chua_co) or '—'}")
    for n in nguoi:
        vai = n["role"]
        if vai == "RECEPTION" and n["full_name"].startswith("ĐD "):
            vai = "RECEPTION_DD"
        hien = await svc.lego_cua_nguoi(staff_id=n["id"], identity=ident)
        co = {m["ma"] for m in hien["lego"] if m["bat"] or m["mot_phan"]}
        if vai == "MANAGEMENT":
            if "dieu_phoi" not in co:
                print(f"  {n['full_name']} (QL): + dieu_phoi")
                if that:
                    await svc.doi_lego(staff_id=n["id"], ma="dieu_phoi", bat=True, identity=ident)
            continue
        phong_ids: list[str] | None = phong_dd
        nguon = vai
        if n["full_name"] in theo_tk:
            muon, ma_phong = quyen_tu_ky_nang(theo_tk[n["full_name"]])
            phong_ids = [ma_id[c] for c in ma_phong]
            nguon = "file"
        else:
            muon = LEGO_THEO_VAI.get(vai)
            if muon is None:
                continue
        if vai != "PARTNER":
            # Mọi nhân viên nội bộ tự đăng ký ca (Tuyền 27/09 tối: "bật lại node
            # lịch làm việc cho nhân viên") — chạy lại script không được tắt nó.
            muon = muon | {"lich_lam_viec"}
        tat = sorted(co - muon)
        ghi_phong = ""
        if "phong" in muon:
            ghi_phong = " @ " + ",".join(c for c, i in ma_id.items() if i in (phong_ids or []))
        print(f"  {n['full_name']} ({nguon}): tắt {tat or '—'} · bật {sorted(muon)}{ghi_phong}")
        if not that:
            continue
        for ma in tat:
            await svc.doi_lego(staff_id=n["id"], ma=ma, bat=False, identity=ident)
        for ma in sorted(muon):
            await svc.doi_lego(
                staff_id=n["id"],
                ma=ma,
                bat=True,
                identity=ident,
                phong_ids=phong_ids if ma == "phong" else None,
            )


async def main() -> int:
    that = "--that" in sys.argv
    if "--ky-nang" not in sys.argv:
        raise SystemExit("✗ Thiếu --ky-nang <tệp JSON {họ tên: [kỹ năng]}>.")
    with open(sys.argv[sys.argv.index("--ky-nang") + 1], encoding="utf-8") as f:
        ky_nang: dict[str, list[str]] = json.load(f)
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        cid = await pool.fetchval("SELECT clinic_id::text FROM clinic_location WHERE name=$1 LIMIT 1", KN)
        print(f"== Pha 1: cấu trúc ({'LÀM THẬT' if that else 'THỬ KHÔ — sẽ ROLLBACK'})")
        async with pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            try:
                ma_id = await pha_cau_truc(conn, cid)
            except BaseException:
                await tx.rollback()
                raise
            if that:
                await tx.commit()
            else:
                await tx.rollback()
        print(f"== Pha 2: lego theo vai ({'LÀM THẬT' if that else 'KẾ HOẠCH'})")
        await pha_lego(pool, cid, ma_id, that, ky_nang)
        if not that:
            print("\nĐây là THỬ KHÔ. Thêm --that để làm thật.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
