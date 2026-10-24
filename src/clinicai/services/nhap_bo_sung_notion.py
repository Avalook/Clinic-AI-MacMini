"""NẠP GÓI PHỤ lịch sử Notion (06/10/2026) — chạy SAU gói chính (`nhap_lich_su_notion`).

Gói phụ dựng trên máy dev (``dong_goi_phu.py``): ``cham_soc.jsonl``,
``nguon_khach.jsonl``, ``nguoi_nha.jsonl``, ``du_kien_sinh.jsonl``, ``manifest.json``.
Bản ghi trỏ người bằng ``nguoi_key``; người → hồ sơ lấy từ ``lich_su_notion.nguoi``
(gói chính đã ghép). Người chưa có trong đó thì BỎ và đếm — bộ này không tạo hồ sơ.

* **Lịch sử chăm sóc** → ``lich_su_notion.cham_soc``, chỉ đọc. KHÔNG ghi vào
  ``tuong_tac_cskh`` / ``nhac_tai_kham`` / ``hen_goi_lai`` hay bảng nào
  ``v_viec_cskh`` đọc: không sinh việc CSKH nào.
* **Nguồn khách** → ``lich_su_notion.nguoi.kenh``. Màn chỉ hiện nó khi khách chưa có
  kênh nào trên hệ thống (``COT_KENH_DOI_HUY``) — không ghi đè.
* **Người nhà** → ``patient_link`` (FAMILY), CHỈ khi cả hai người đều đã có hồ sơ;
  cặp đã liên kết thì để nguyên.
* **Dự kiến sinh** → ``pregnancy`` (nguồn "Khác", người ghi = nhân sự hệ thống "Hồ
  sơ cũ"), chỉ cho khách CHƯA có thai kỳ nào trên hệ thống. Dự kiến sinh từ hôm nay
  trở đi → đang theo dõi; đã qua → kết cục "không rõ".

Hai bảng hệ thống ghi sổ ở ``lich_su_notion.ban_ghi_bo_sung`` → chạy lại không
trùng, gỡ đúng dòng (``scripts/hoan-tac-bo-sung-notion.sql``).

MỘT giao dịch. Mặc định THỬ KHÔ (chạy hết rồi quay lui, in số). ``--that`` mới ghi.

    python -m clinicai.services.nhap_bo_sung_notion /tmp/goi-phu            # thử khô
    python -m clinicai.services.nhap_bo_sung_notion /tmp/goi-phu --that     # ghi thật
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg

from clinicai.services.nhap_lich_su_notion import _ThuKho

BANG_GOI_PHU = ("cham_soc", "nguon_khach", "nguoi_nha", "du_kien_sinh")

#: Nhân sự HỆ THỐNG đứng tên cột bắt buộc (patient_link.created_by) — cùng người
#: với ``chuyen_luot_that.TEN_NGUOI_NHAP``: không hoạt động, không thành viên.
TEN_NGUOI_NHAP = "Hồ sơ cũ"
GHI_CHU_NGUOI_NHA = "Người nhà ghi trong hồ sơ trước 10/2026"


async def _nap_tam(conn: asyncpg.Connection, thu_muc: Path) -> dict[str, int]:
    so: dict[str, int] = {}
    for ten in BANG_GOI_PHU:
        await conn.execute(f"CREATE TEMP TABLE _p_{ten} (d jsonb) ON COMMIT DROP")
        tep = thu_muc / f"{ten}.jsonl"
        dong = (
            [[ln] for ln in tep.read_text().splitlines() if ln.strip()]
            if tep.exists()
            else []
        )
        if dong:
            await conn.copy_records_to_table(f"_p_{ten}", records=dong, columns=["d"])
        so[ten] = len(dong)
    return so


async def _nguoi_he_thong(conn: asyncpg.Connection, co_so: Any) -> Any:
    may = await conn.fetchval(
        "SELECT id FROM public.staff WHERE employment_type = 'SYSTEM'"
        " AND full_name = $1 LIMIT 1",
        TEN_NGUOI_NHAP,
    )
    if may is None:
        may = await conn.fetchval(
            "INSERT INTO public.staff (full_name, short_name, primary_location_id,"
            " primary_department, employment_type, is_active)"
            " VALUES ($1, $1, $2, 'MANAGEMENT', 'SYSTEM', false) RETURNING id",
            TEN_NGUOI_NHAP,
            co_so,
        )
    return may


async def _nap(
    conn: asyncpg.Connection, thu_muc: Path, *, nguoi_chay: str, clinic_id: str | None
) -> dict[str, Any]:
    manifest = json.loads((thu_muc / "manifest.json").read_text())
    if clinic_id is None:
        ds = await conn.fetch("SELECT id::text FROM public.clinic")
        if len(ds) != 1:
            raise SystemExit(f"Có {len(ds)} phòng khám — truyền --clinic <id>.")
        clinic_id = ds[0]["id"]
    if not await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM lich_su_notion.nguoi WHERE clinic_id = $1::uuid)",
        clinic_id,
    ):
        raise SystemExit("Chưa nạp gói chính (lich_su_notion.nguoi rỗng) — dừng.")
    co_so = await conn.fetchval(
        "SELECT id FROM public.clinic_location WHERE clinic_id = $1::uuid"
        " ORDER BY created_at LIMIT 1",
        clinic_id,
    )
    lan = await conn.fetchval(
        """INSERT INTO lich_su_notion.lan_nhap (clinic_id, goi, nguoi_chay)
           VALUES ($1::uuid, $2, $3) RETURNING id""",
        clinic_id,
        str(manifest.get("goi")),
        nguoi_chay,
    )
    so_goi = await _nap_tam(conn, thu_muc)
    # nguoi_key → hồ sơ (gói chính đã ghép; hồ sơ ẩn sau khi gỡ thì không tính).
    await conn.execute(
        """
        CREATE TEMP TABLE _bn ON COMMIT DROP AS
        SELECT n.nguoi_key AS k, n.clinic_patient_id AS bn
          FROM lich_su_notion.nguoi n
          JOIN public.patient p ON p.clinic_patient_id = n.clinic_patient_id
         WHERE n.clinic_id = $1::uuid AND p.is_active
        """,
        clinic_id,
    )
    await conn.execute("CREATE UNIQUE INDEX ON _bn (k)")
    so: dict[str, Any] = {"goi": so_goi}

    # ── C1. Lịch sử chăm sóc ────────────────────────────────────────────────
    so["cham_soc_khong_co_ho_so"] = await conn.fetchval(
        "SELECT count(*) FROM _p_cham_soc g"
        " WHERE NOT EXISTS (SELECT 1 FROM _bn b WHERE b.k = g.d->>'nguoi_key')"
    )
    trong_lsn = (
        "(SELECT x.notion_id FROM lich_su_notion.{bang} x"
        " WHERE x.notion_id = (g.d->>'{cot}')::uuid)"
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.cham_soc (notion_id, clinic_id, clinic_patient_id,
               lan_nhap_id, ma, luc, buoc, phan_loai, kich_ban, tinh_trang, noi_dung,
               doi_tuong, nguoi_lam, cha_id, lich_hen_id, luot_kham_id, xet_nghiem_id,
               notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, b.bn, $2, g.d->>'ma',
               (g.d->>'luc')::timestamptz, g.d->>'buoc', g.d->>'phan_loai',
               g.d->>'kich_ban', g.d->>'tinh_trang', g.d->>'noi_dung',
               g.d->>'doi_tuong', g.d->>'nguoi_lam', (g.d->>'cha_id')::uuid,
               {trong_lsn.format(bang="lich_hen", cot="lich_hen_id")},
               {trong_lsn.format(bang="luot_kham", cot="luot_kham_id")},
               {trong_lsn.format(bang="xet_nghiem", cot="xet_nghiem_id")},
               g.d->>'notion_url'
          FROM _p_cham_soc g JOIN _bn b ON b.k = g.d->>'nguoi_key'
        ON CONFLICT (notion_id) DO UPDATE SET
               clinic_patient_id = EXCLUDED.clinic_patient_id,
               luc = EXCLUDED.luc, buoc = EXCLUDED.buoc,
               phan_loai = EXCLUDED.phan_loai, kich_ban = EXCLUDED.kich_ban,
               tinh_trang = EXCLUDED.tinh_trang, noi_dung = EXCLUDED.noi_dung,
               doi_tuong = EXCLUDED.doi_tuong, nguoi_lam = EXCLUDED.nguoi_lam,
               cha_id = EXCLUDED.cha_id, lich_hen_id = EXCLUDED.lich_hen_id,
               luot_kham_id = EXCLUDED.luot_kham_id,
               xet_nghiem_id = EXCLUDED.xet_nghiem_id
        """,
        clinic_id,
        lan,
    )

    # ── C2a. Nguồn khách ────────────────────────────────────────────────────
    so["nguon_khach_khong_co_ho_so"] = await conn.fetchval(
        "SELECT count(*) FROM _p_nguon_khach g"
        " WHERE NOT EXISTS (SELECT 1 FROM _bn b WHERE b.k = g.d->>'nguoi_key')"
    )
    await conn.execute(
        """
        UPDATE lich_su_notion.nguoi n SET kenh = nullif(btrim(g.d->>'kenh'), '')
          FROM _p_nguon_khach g
         WHERE n.clinic_id = $1::uuid AND n.nguoi_key = g.d->>'nguoi_key'
           AND n.kenh IS DISTINCT FROM nullif(btrim(g.d->>'kenh'), '')
        """,
        clinic_id,
    )
    # Bao nhiêu hồ sơ sẽ HIỆN nguồn cũ (chưa có kênh nào trên hệ thống).
    so["nguon_khach_se_hien"] = await conn.fetchval(
        """
        SELECT count(DISTINCT n.clinic_patient_id) FROM lich_su_notion.nguoi n
         WHERE n.clinic_id = $1::uuid AND n.kenh IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM public.appointment a
                            WHERE a.clinic_id = n.clinic_id
                              AND a.clinic_patient_id = n.clinic_patient_id
                              AND a.booking_channel IS NOT NULL)
        """,
        clinic_id,
    )

    # ── C2b. Người nhà → patient_link ───────────────────────────────────────
    may = await _nguoi_he_thong(conn, co_so)
    await conn.execute(
        """
        CREATE TEMP TABLE _cap ON COMMIT DROP AS
        SELECT DISTINCT least(a.bn, b.bn) AS p1, greatest(a.bn, b.bn) AS p2,
               (g.d->>'nguoi_key_a') || ' + ' || (g.d->>'nguoi_key_b') AS nguon
          FROM _p_nguoi_nha g
          JOIN _bn a ON a.k = g.d->>'nguoi_key_a'
          JOIN _bn b ON b.k = g.d->>'nguoi_key_b'
         WHERE a.bn <> b.bn
        """
    )
    so["nguoi_nha_thieu_ho_so"] = await conn.fetchval(
        "SELECT count(*) FROM _p_nguoi_nha g"
        " WHERE NOT EXISTS (SELECT 1 FROM _bn b WHERE b.k = g.d->>'nguoi_key_a')"
        "    OR NOT EXISTS (SELECT 1 FROM _bn b WHERE b.k = g.d->>'nguoi_key_b')"
    )
    so["nguoi_nha_da_lien_ket_san"] = await conn.fetchval(
        """
        SELECT count(*) FROM (SELECT DISTINCT p1, p2 FROM _cap) c
         WHERE EXISTS (SELECT 1 FROM public.patient_link l
                        WHERE l.clinic_id = $1::uuid
                          AND least(l.patient_a, l.patient_b) = c.p1
                          AND greatest(l.patient_a, l.patient_b) = c.p2)
        """,
        clinic_id,
    )
    moi_lk = await conn.fetch(
        """
        WITH them AS (
            INSERT INTO public.patient_link (clinic_id, patient_a, patient_b, relation,
                   created_by, note)
            SELECT $1::uuid, c.p1, c.p2, 'FAMILY', $2::uuid, $4
              FROM (SELECT DISTINCT ON (p1, p2) p1, p2 FROM _cap ORDER BY p1, p2) c
            ON CONFLICT (clinic_id, least(patient_a, patient_b),
                         greatest(patient_a, patient_b)) DO NOTHING
            RETURNING id, patient_a, patient_b
        )
        INSERT INTO lich_su_notion.ban_ghi_bo_sung (bang, ban_ghi_id, nguon, lan_nhap_id)
        SELECT 'patient_link', t.id,
               (SELECT min(c.nguon) FROM _cap c
                 WHERE c.p1 = t.patient_a AND c.p2 = t.patient_b), $3
          FROM them t
        RETURNING ban_ghi_id
        """,
        clinic_id,
        may,
        lan,
        GHI_CHU_NGUOI_NHA,
    )
    so["nguoi_nha_lien_ket_moi"] = len(moi_lk)

    # ── C2c. Dự kiến sinh → pregnancy ───────────────────────────────────────
    await conn.execute(
        """
        CREATE TEMP TABLE _dks ON COMMIT DROP AS
        SELECT DISTINCT ON (b.bn) b.bn, (g.d->>'du_kien_sinh')::date AS edd,
               coalesce(g.d->>'notion_id', g.d->>'nguoi_key') AS nguon
          FROM _p_du_kien_sinh g JOIN _bn b ON b.k = g.d->>'nguoi_key'
         WHERE g.d->>'du_kien_sinh' ~ '^\\d{4}-\\d{2}-\\d{2}$'
         ORDER BY b.bn, (g.d->>'du_kien_sinh')::date DESC
        """
    )
    so["du_kien_sinh_khong_co_ho_so"] = await conn.fetchval(
        "SELECT count(*) FROM _p_du_kien_sinh g"
        " WHERE NOT EXISTS (SELECT 1 FROM _bn b WHERE b.k = g.d->>'nguoi_key')"
    )
    so["du_kien_sinh_da_co_thai_ky"] = await conn.fetchval(
        "SELECT count(*) FROM _dks d WHERE EXISTS (SELECT 1 FROM public.pregnancy p"
        " WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = d.bn)",
        clinic_id,
    )
    moi_tk = await conn.fetch(
        """
        WITH them AS (
            INSERT INTO public.pregnancy (clinic_id, clinic_patient_id, location_id,
                   edd_date, edd_nguon, outcome, created_by)
            SELECT $1::uuid, d.bn, $2::uuid, d.edd, 'KHAC',
                   CASE WHEN d.edd >= (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                        THEN 'ONGOING' ELSE 'UNKNOWN' END,
                   $3::uuid
              FROM _dks d
             WHERE NOT EXISTS (SELECT 1 FROM public.pregnancy p
                                WHERE p.clinic_id = $1::uuid
                                  AND p.clinic_patient_id = d.bn)
            RETURNING id, clinic_patient_id, outcome
        ), so AS (
            INSERT INTO lich_su_notion.ban_ghi_bo_sung (bang, ban_ghi_id, nguon,
                   lan_nhap_id)
            SELECT 'pregnancy', t.id,
                   (SELECT d.nguon FROM _dks d WHERE d.bn = t.clinic_patient_id), $4
              FROM them t
        )
        SELECT outcome FROM them
        """,
        clinic_id,
        co_so,
        may,
        lan,
    )
    so["du_kien_sinh_dang_theo_doi"] = sum(1 for r in moi_tk if r[0] == "ONGOING")
    so["du_kien_sinh_da_qua"] = sum(1 for r in moi_tk if r[0] == "UNKNOWN")

    so["tong_cham_soc"] = await conn.fetchval(
        "SELECT count(*) FROM lich_su_notion.cham_soc WHERE clinic_id = $1::uuid",
        clinic_id,
    )
    so["tong_nguon_khach"] = await conn.fetchval(
        "SELECT count(*) FROM lich_su_notion.nguoi"
        " WHERE clinic_id = $1::uuid AND kenh IS NOT NULL",
        clinic_id,
    )
    for bang in ("patient_link", "pregnancy"):
        so[f"tong_{bang}_bo_sung"] = await conn.fetchval(
            "SELECT count(*) FROM lich_su_notion.ban_ghi_bo_sung WHERE bang = $1",
            bang,
        )
    await conn.execute(
        "UPDATE lich_su_notion.lan_nhap SET xong_luc = now(), so_lieu = $2::jsonb"
        " WHERE id = $1",
        lan,
        json.dumps(so),
    )
    so["lan_nhap_id"] = lan
    so["clinic_id"] = clinic_id
    return so


async def nap(
    pool: asyncpg.Pool,
    thu_muc: Path,
    *,
    that: bool,
    nguoi_chay: str = "may",
    clinic_id: str | None = None,
) -> dict[str, Any]:
    """Nạp gói phụ. ``that=False`` = thử khô: chạy hết trong giao dịch rồi quay lui."""
    ket_qua: dict[str, Any] = {}
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                ket_qua = await _nap(
                    conn, thu_muc, nguoi_chay=nguoi_chay, clinic_id=clinic_id
                )
                if not that:
                    raise _ThuKho
        except _ThuKho:
            ket_qua["thu_kho"] = True
    return ket_qua


async def _main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    thu_muc = Path(argv[0])
    that = "--that" in argv
    clinic_id = argv[argv.index("--clinic") + 1] if "--clinic" in argv else None
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    try:
        kq = await nap(
            pool,
            thu_muc,
            that=that,
            nguoi_chay="nhap-bo-sung-notion",
            clinic_id=clinic_id,
        )
    finally:
        await pool.close()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    print("THỬ KHÔ — chưa ghi gì. Thêm --that để ghi thật." if not that else "ĐÃ GHI.")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
