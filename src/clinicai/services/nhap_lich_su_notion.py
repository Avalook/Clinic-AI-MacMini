"""NẠP gói lịch sử Notion vào schema ``lich_su_notion`` (05/10/2026).

Gói dựng trên máy dev từ ảnh chụp Notion (``nguoi.jsonl``, ``luot_kham.jsonl``,
``dich_vu.jsonl``, ``ket_qua.jsonl``, ``xet_nghiem.jsonl``, ``ke_thuoc.jsonl``,
``lich_hen.jsonl``, ``bat_thuong.jsonl``, ``manifest.json``, thư mục ``tep/``).
Bản ghi trỏ người bằng ``nguoi_key``; KHỚP HỒ SƠ THẬT LÀM Ở ĐÂY, trên DB đích, vì
khách mới được tạo mỗi ngày (khách A tạo hôm nay → 5 lượt Notion gắn vào đúng hồ
sơ ấy, lượt hôm nay thành lần 6).

Luật ghép: 9 số cuối SĐT (chính hoặc phụ) + họ tên bỏ dấu — CẢ HAI phải khớp. Chỉ
ghép vào hồ sơ tạo trên hệ thống (``nguon_nhap IS NULL``); người đã nạp ở lần
trước giữ nguyên hồ sơ cũ (chạy lại an toàn, lần sau chỉ thêm phần mới + cập nhật
nội dung). Không ghép được → tạo hồ sơ mới ``nguon_nhap='notion'``, mã = mã Notion.
Trùng SĐT với khách trên hệ thống mà KHÁC tên → không gộp, ghi sổ bất thường.

MỘT giao dịch: lỗi giữa chừng thì không còn gì. Mặc định THỬ KHÔ (chạy hết rồi
quay lui, in số). ``--that`` mới ghi. Tệp kết quả chép vào kho SAU khi ghi xong.

    python -m clinicai.services.nhap_lich_su_notion /tmp/goi            # thử khô
    python -m clinicai.services.nhap_lich_su_notion /tmp/goi --that     # ghi thật
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import asyncpg

BANG_GOI = (
    "nguoi",
    "luot_kham",
    "dich_vu",
    "ket_qua",
    "xet_nghiem",
    "ke_thuoc",
    "lich_hen",
    "bat_thuong",
)

KHOA_TEN = (
    "regexp_replace(lower(public.f_unaccent(btrim(coalesce({}, '')))),"
    " '\\s+', ' ', 'g')"
)
SO9 = "right(regexp_replace(coalesce({}, ''), '\\D', '', 'g'), 9)"


def _k(x: str) -> str:
    return KHOA_TEN.format(x)


def _s(x: str) -> str:
    return SO9.format(x)


class _ThuKho(Exception):  # noqa: N818 — tín hiệu quay lui, không phải lỗi
    pass


async def _nap_tam(conn: asyncpg.Connection, thu_muc: Path) -> dict[str, int]:
    # Ô mảng trong gói có thể là JSON null (không phải SQL NULL) — coalesce không
    # bắt được; hàm tạm này biến mọi thứ không phải mảng thành mảng rỗng.
    await conn.execute(
        "CREATE OR REPLACE FUNCTION pg_temp._mang(j jsonb) RETURNS jsonb"
        " LANGUAGE sql IMMUTABLE"
        " AS $$ SELECT CASE WHEN jsonb_typeof(j) = 'array' THEN j"
        " ELSE '[]'::jsonb END $$"
    )
    so: dict[str, int] = {}
    for ten in BANG_GOI:
        await conn.execute(f"CREATE TEMP TABLE _g_{ten} (d jsonb) ON COMMIT DROP")
        tep = thu_muc / f"{ten}.jsonl"
        dong = (
            [(ln,) for ln in tep.read_text().splitlines() if ln.strip()]
            if tep.exists()
            else []
        )
        if dong:
            await conn.copy_records_to_table(f"_g_{ten}", records=dong, columns=["d"])
        so[ten] = len(dong)
    return so


async def _nap(
    conn: asyncpg.Connection, thu_muc: Path, *, nguoi_chay: str, clinic_id: str | None
) -> dict[str, Any]:
    manifest = json.loads((thu_muc / "manifest.json").read_text())
    if clinic_id is None:
        ds = await conn.fetch("SELECT id::text FROM public.clinic")
        if len(ds) != 1:
            raise SystemExit(f"Có {len(ds)} phòng khám — truyền --clinic <id>.")
        clinic_id = ds[0]["id"]
    co_so = await conn.fetchval(
        "SELECT id FROM public.clinic_location WHERE clinic_id = $1::uuid"
        " ORDER BY name LIMIT 1",
        clinic_id,
    )
    if co_so is None:
        raise SystemExit("Phòng khám chưa có cơ sở nào.")
    lan = await conn.fetchval(
        """INSERT INTO lich_su_notion.lan_nhap (clinic_id, goi, nguoi_chay)
           VALUES ($1::uuid, $2, $3) RETURNING id""",
        clinic_id,
        str(manifest.get("goi")),
        nguoi_chay,
    )
    so_goi = await _nap_tam(conn, thu_muc)

    # ── 1. Ghép người ────────────────────────────────────────────────────────
    await conn.execute(
        f"""
        CREATE TEMP TABLE _ghep ON COMMIT DROP AS
        SELECT g.d->>'nguoi_key' AS k, g.d,
               coalesce(cu.clinic_patient_id, khop.clinic_patient_id) AS bn,
               CASE WHEN cu.nguoi_key IS NOT NULL THEN cu.cach_ghep
                    WHEN khop.clinic_patient_id IS NOT NULL
                    THEN 'ghep_sdt_ten' END AS cach
          FROM _g_nguoi g
          LEFT JOIN lich_su_notion.nguoi cu ON cu.nguoi_key = g.d->>'nguoi_key'
          LEFT JOIN LATERAL (
              SELECT p.clinic_patient_id FROM public.patient p
               WHERE cu.nguoi_key IS NULL AND p.clinic_id = $1::uuid
                 AND p.nguon_nhap IS NULL
                 AND length({_s("g.d->>'sdt'")}) = 9
                 AND {_s("g.d->>'sdt'")} IN ({_s("p.phone_primary")},
                        {_s("p.phone_secondary")})
                 AND {_k("p.full_name")} = {_k("g.d->>'ten'")}
               ORDER BY p.created_at LIMIT 1) khop ON true
        """,
        clinic_id,
    )
    # Nạp lại sau khi HOÀN TÁC: hồ sơ Notion cũ còn đó (bị ẩn) — nhận lại đúng
    # hồ sơ ấy theo mã và bật lại, không tạo hồ sơ thứ hai.
    await conn.execute(
        """
        UPDATE _ghep x SET bn = p.clinic_patient_id, cach = 'tao_moi'
          FROM public.patient p
         WHERE x.bn IS NULL AND p.clinic_id = $1::uuid AND p.nguon_nhap = 'notion'
           AND p.patient_code IN (x.d->>'ma', (x.d->>'ma') || '-' || left(md5(x.k), 4))
        """,
        clinic_id,
    )
    await conn.execute(
        """
        UPDATE public.patient p SET is_active = true, updated_at = now()
          FROM _ghep x
         WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = x.bn
           AND p.nguon_nhap = 'notion' AND NOT p.is_active
        """,
        clinic_id,
    )
    # Mã hồ sơ: mã Notion; đã có người dùng mã ấy thì thêm đuôi ổn định.
    tao = await conn.fetch(
        """
        INSERT INTO public.patient (clinic_id, location_id, patient_code, full_name,
               date_of_birth, birth_year, phone_primary, gender, address,
               created_at, updated_at, nguon_nhap)
        SELECT $1::uuid, $2::uuid,
               CASE WHEN EXISTS (SELECT 1 FROM public.patient q
                                  WHERE q.clinic_id = $1::uuid
                                    AND q.patient_code = x.d->>'ma')
                    THEN (x.d->>'ma') || '-' || left(md5(x.k), 4) ELSE x.d->>'ma' END,
               coalesce(nullif(btrim(x.d->>'ten'), ''),
                      '(chưa rõ tên) ' || (x.d->>'ma')),
               (x.d->>'ngay_sinh')::date,
                      extract(year FROM (x.d->>'ngay_sinh')::date)::smallint,
               nullif(x.d->>'sdt', ''), x.d->>'gioi', x.d->>'dia_chi',
               coalesce((x.d->>'tao_luc')::timestamptz, now()), now(), 'notion'
          FROM _ghep x WHERE x.bn IS NULL
        RETURNING clinic_patient_id::text, patient_code
        """,
        clinic_id,
        co_so,
    )
    await conn.execute(
        """
        UPDATE _ghep x SET bn = p.clinic_patient_id, cach = 'tao_moi'
          FROM public.patient p
         WHERE x.bn IS NULL AND p.clinic_id = $1::uuid AND p.nguon_nhap = 'notion'
           AND p.patient_code IN (x.d->>'ma', (x.d->>'ma') || '-' || left(md5(x.k), 4))
        """,
        clinic_id,
    )
    con_thieu = await conn.fetchval("SELECT count(*) FROM _ghep WHERE bn IS NULL")
    if con_thieu:
        raise RuntimeError(f"{con_thieu} người không gắn được hồ sơ — dừng.")
    await conn.execute(
        """
        INSERT INTO lich_su_notion.nguoi (nguoi_key, clinic_id, clinic_patient_id,
               lan_nhap_id,
               cach_ghep, ten, sdt, ho_so_notion, nguon_ten, ghi_chu_lan_dau,
                      link_drive, notion_url)
        SELECT x.k, $1::uuid, x.bn, $2, x.cach, x.d->>'ten', x.d->>'sdt',
               ARRAY(SELECT jsonb_array_elements_text(
                   pg_temp._mang(x.d->'ho_so_notion'))),
               x.d->>'nguon_ten', x.d->>'ghi_chu_lan_dau', x.d->>'link_drive',
                      x.d->>'notion_url'
          FROM _ghep x
        ON CONFLICT (nguoi_key) DO UPDATE SET
               ten = EXCLUDED.ten, sdt = EXCLUDED.sdt,
                      ho_so_notion = EXCLUDED.ho_so_notion,
               nguon_ten = EXCLUDED.nguon_ten,
                      ghi_chu_lan_dau = EXCLUDED.ghi_chu_lan_dau,
               link_drive = EXCLUDED.link_drive, notion_url = EXCLUDED.notion_url
        """,
        clinic_id,
        lan,
    )

    # ── 2. Lịch sử: chèn mới hoặc cập nhật nội dung (gói sau có thêm kết quả) ─
    nguoi_cua = "JOIN _ghep x ON x.k = g.d->>'nguoi_key'"
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.luot_kham (notion_id, clinic_id,
               clinic_patient_id, lan_nhap_id,
               ma, ngay_kham, nguon_ngay, lan_thu, thu_tu_khong_chac, loai_kham_goc,
               service_type_id, bac_si_goc, staff_id, co_so_goc, kham_tu_van, chan_doan,
               ghi_chu_vinh_vien, tinh_trang_goc, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2, g.d->>'ma',
               (g.d->>'ngay_kham')::date, g.d->>'nguon_ngay', (g.d->>'lan_thu')::int,
               coalesce((g.d->>'thu_tu_khong_chac')::boolean, false),
                      g.d->>'loai_kham_goc',
               (SELECT st.id FROM public.service_type st
                 WHERE st.code = g.d->>'service_type_code'),
               g.d->>'bac_si_goc',
               (SELECT s.id FROM public.staff s
                  JOIN public.clinic_membership m ON m.staff_id = s.id
                 WHERE m.clinic_id = $1::uuid AND s.full_name = g.d->>'staff_ten'
                 LIMIT 1),
               g.d->>'co_so_goc', g.d->>'kham_tu_van', g.d->>'chan_doan',
               g.d->>'ghi_chu_vinh_vien', g.d->>'tinh_trang_goc', g.d->>'notion_url'
          FROM _g_luot_kham g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               ngay_kham = EXCLUDED.ngay_kham, nguon_ngay = EXCLUDED.nguon_ngay,
               lan_thu = EXCLUDED.lan_thu,
                      thu_tu_khong_chac = EXCLUDED.thu_tu_khong_chac,
               loai_kham_goc = EXCLUDED.loai_kham_goc,
                      service_type_id = EXCLUDED.service_type_id,
               bac_si_goc = EXCLUDED.bac_si_goc, staff_id = EXCLUDED.staff_id,
               kham_tu_van = EXCLUDED.kham_tu_van, chan_doan = EXCLUDED.chan_doan,
               ghi_chu_vinh_vien = EXCLUDED.ghi_chu_vinh_vien,
                      tinh_trang_goc = EXCLUDED.tinh_trang_goc
        """,
        clinic_id,
        lan,
    )
    co_luot = (
        "(SELECT l.notion_id FROM lich_su_notion.luot_kham l"
        " WHERE l.notion_id = (g.d->>'luot_kham_id')::uuid)"
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.dich_vu (notion_id, clinic_id, clinic_patient_id,
               lan_nhap_id,
               luot_kham_id, ma, ten_goc, service_code, nguoi_lam, ngay,
                      tinh_trang_goc, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2, {co_luot}, g.d->>'ma',
               ARRAY(SELECT jsonb_array_elements_text(pg_temp._mang(g.d->'ten_goc'))),
               g.d->>'service_code',
               ARRAY(SELECT jsonb_array_elements_text(pg_temp._mang(g.d->'nguoi_lam'))),
               (g.d->>'ngay')::date, g.d->>'tinh_trang_goc', g.d->>'notion_url'
          FROM _g_dich_vu g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               luot_kham_id = EXCLUDED.luot_kham_id, ten_goc = EXCLUDED.ten_goc,
               service_code = EXCLUDED.service_code, nguoi_lam = EXCLUDED.nguoi_lam,
               ngay = EXCLUDED.ngay, tinh_trang_goc = EXCLUDED.tinh_trang_goc
        """,
        clinic_id,
        lan,
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.ket_qua (notion_id, clinic_id, clinic_patient_id,
               lan_nhap_id,
               dich_vu_id, luot_kham_id, ma, tieu_de, mo_ta, ket_luan, bac_si_ky,
                      ghi_chu,
               ghi_de_chan_doan, da_co_noi_dung, link_drive_cu, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2,
               (SELECT d.notion_id FROM lich_su_notion.dich_vu d
                 WHERE d.notion_id = (g.d->>'dich_vu_id')::uuid),
               {co_luot}, g.d->>'ma', g.d->>'tieu_de', g.d->>'mo_ta', g.d->>'ket_luan',
               ARRAY(SELECT jsonb_array_elements_text(pg_temp._mang(g.d->'bac_si_ky'))),
               g.d->>'ghi_chu', g.d->>'ghi_de_chan_doan',
               coalesce((g.d->>'da_co_noi_dung')::boolean, false),
                      g.d->>'link_drive_cu',
               g.d->>'notion_url'
          FROM _g_ket_qua g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               dich_vu_id = EXCLUDED.dich_vu_id, luot_kham_id = EXCLUDED.luot_kham_id,
               tieu_de = EXCLUDED.tieu_de,
               mo_ta = coalesce(EXCLUDED.mo_ta, lich_su_notion.ket_qua.mo_ta),
               ket_luan = coalesce(EXCLUDED.ket_luan, lich_su_notion.ket_qua.ket_luan),
               bac_si_ky = CASE WHEN EXCLUDED.da_co_noi_dung THEN EXCLUDED.bac_si_ky
                                ELSE lich_su_notion.ket_qua.bac_si_ky END,
               ghi_chu = EXCLUDED.ghi_chu, ghi_de_chan_doan = EXCLUDED.ghi_de_chan_doan,
               da_co_noi_dung = EXCLUDED.da_co_noi_dung
                                OR lich_su_notion.ket_qua.da_co_noi_dung,
               link_drive_cu = EXCLUDED.link_drive_cu
        """,
        clinic_id,
        lan,
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.xet_nghiem (notion_id, clinic_id,
               clinic_patient_id, lan_nhap_id,
               luot_kham_id, ma, noi_lam, phan_loai, ket_qua, ket_qua_ai,
                      tro_ly_ghi_chu,
               ghi_chu_vinh_vien, tep, tinh_trang_goc, ngay, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2, {co_luot}, g.d->>'ma',
               ARRAY(SELECT jsonb_array_elements_text(pg_temp._mang(g.d->'noi_lam'))),
               g.d->>'phan_loai', g.d->>'ket_qua', g.d->>'ket_qua_ai',
                      g.d->>'tro_ly_ghi_chu',
               g.d->>'ghi_chu_vinh_vien', g.d->'tep', g.d->>'tinh_trang_goc',
               (g.d->>'ngay')::date, g.d->>'notion_url'
          FROM _g_xet_nghiem g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               luot_kham_id = EXCLUDED.luot_kham_id, noi_lam = EXCLUDED.noi_lam,
               phan_loai = EXCLUDED.phan_loai, ket_qua = EXCLUDED.ket_qua,
               ket_qua_ai = EXCLUDED.ket_qua_ai,
                      tro_ly_ghi_chu = EXCLUDED.tro_ly_ghi_chu,
               ghi_chu_vinh_vien = EXCLUDED.ghi_chu_vinh_vien, tep = EXCLUDED.tep,
               tinh_trang_goc = EXCLUDED.tinh_trang_goc
        """,
        clinic_id,
        lan,
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.ke_thuoc (notion_id, clinic_id, clinic_patient_id,
               lan_nhap_id,
               luot_kham_id, ma, ten_thuoc, huong_dan, so_luong, ghi_chu_so_luong,
                      luu_y, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2, {co_luot}, g.d->>'ma',
               ARRAY(SELECT jsonb_array_elements_text(pg_temp._mang(g.d->'ten_thuoc'))),
               g.d->>'huong_dan', g.d->>'so_luong', g.d->>'ghi_chu_so_luong',
                      g.d->>'luu_y',
               g.d->>'notion_url'
          FROM _g_ke_thuoc g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               luot_kham_id = EXCLUDED.luot_kham_id, ten_thuoc = EXCLUDED.ten_thuoc,
               huong_dan = EXCLUDED.huong_dan, so_luong = EXCLUDED.so_luong,
               ghi_chu_so_luong = EXCLUDED.ghi_chu_so_luong, luu_y = EXCLUDED.luu_y
        """,
        clinic_id,
        lan,
    )
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.lich_hen (notion_id, clinic_id, clinic_patient_id,
               lan_nhap_id,
               ma, ngay_hen, gio_hen, loai_kham_goc, bac_si_goc, tinh_trang_den,
               tinh_trang_cskh, trang_thai, luot_kham_ids, notion_url)
        SELECT (g.d->>'notion_id')::uuid, $1::uuid, x.bn, $2, g.d->>'ma',
               (g.d->>'ngay_hen')::date, (g.d->>'gio_hen')::time, g.d->>'loai_kham_goc',
               g.d->>'bac_si_goc', g.d->>'tinh_trang_den', g.d->>'tinh_trang_cskh',
               g.d->>'trang_thai',
               ARRAY(SELECT jsonb_array_elements_text(
                   pg_temp._mang(g.d->'luot_kham_ids')))::uuid[],
               g.d->>'notion_url'
          FROM _g_lich_hen g {nguoi_cua}
        ON CONFLICT (notion_id) DO UPDATE SET
               ngay_hen = EXCLUDED.ngay_hen, gio_hen = EXCLUDED.gio_hen,
               loai_kham_goc = EXCLUDED.loai_kham_goc, bac_si_goc = EXCLUDED.bac_si_goc,
               tinh_trang_den = EXCLUDED.tinh_trang_den,
               tinh_trang_cskh = EXCLUDED.tinh_trang_cskh,
                      trang_thai = EXCLUDED.trang_thai,
               luot_kham_ids = EXCLUDED.luot_kham_ids
        """,
        clinic_id,
        lan,
    )

    # ── 3. Sổ bất thường: làm mới phần "chờ xem", giữ phần đã xử lý ───────────
    await conn.execute(
        "DELETE FROM lich_su_notion.bat_thuong"
        " WHERE clinic_id = $1::uuid AND trang_thai = 'chờ xem'",
        clinic_id,
    )
    await conn.execute(
        """
        INSERT INTO lich_su_notion.bat_thuong (clinic_id, lan_nhap_id, loai, muc,
               bang, notion_id,
               clinic_patient_id, luot_kham_id, chi_tiet, notion_url)
        SELECT $1::uuid, $2, g.d->>'loai', g.d->>'muc', g.d->>'bang', g.d->>'notion_id',
               x.bn, (g.d->>'luot_kham_id')::uuid, g.d->>'chi_tiet', g.d->>'notion_url'
          FROM _g_bat_thuong g LEFT JOIN _ghep x ON x.k = g.d->>'nguoi_key'
        """,
        clinic_id,
        lan,
    )
    # Khách tạo mới từ Notion mà TRÙNG SĐT với một khách đang có trên hệ thống
    # (khác tên): có thể lễ tân gõ sai tên — người xem quyết có gộp không.
    await conn.execute(
        f"""
        INSERT INTO lich_su_notion.bat_thuong (clinic_id, lan_nhap_id, loai, muc,
               bang, notion_id,
               clinic_patient_id, chi_tiet, notion_url)
        SELECT DISTINCT ON (x.k) $1::uuid, $2, 'CO_THE_TRUNG_HO_SO_HE_THONG', 'cao',
               'nguoi',
               x.k, x.bn,
               'Cùng SĐT với khách ' || p.patient_code || ' (' || p.full_name ||
               ') trên hệ thống nhưng khác tên — chưa gộp, cần người xem',
               x.d->>'notion_url'
          FROM _ghep x JOIN public.patient p
            ON p.clinic_id = $1::uuid AND p.nguon_nhap IS NULL
           AND length({_s("x.d->>'sdt'")}) = 9
           AND {_s("x.d->>'sdt'")} IN ({_s("p.phone_primary")},
                  {_s("p.phone_secondary")})
         WHERE x.cach = 'tao_moi'
         ORDER BY x.k, p.created_at
        """,
        clinic_id,
        lan,
    )

    so_lieu: dict[str, Any] = {
        "goi": so_goi,
        "tao_ho_so_moi": len(tao),
        "ghep_ho_so_co_san": await conn.fetchval(
            "SELECT count(*) FROM _ghep WHERE cach = 'ghep_sdt_ten'"
        ),
    }
    for b in BANG_GOI:
        so_lieu[f"tong_{b}"] = await conn.fetchval(
            f"SELECT count(*) FROM lich_su_notion.{b} WHERE clinic_id = $1::uuid",
            clinic_id,
        )
    await conn.execute(
        "UPDATE lich_su_notion.lan_nhap SET xong_luc = now(), so_lieu = $2::jsonb"
        " WHERE id = $1",
        lan,
        json.dumps(so_lieu),
    )
    so_lieu["lan_nhap_id"] = lan
    so_lieu["clinic_id"] = clinic_id
    return so_lieu


async def nap(
    pool: asyncpg.Pool,
    thu_muc: Path,
    *,
    that: bool,
    nguoi_chay: str = "may",
    clinic_id: str | None = None,
) -> dict[str, Any]:
    """Nạp gói. ``that=False`` = thử khô: chạy hết trong giao dịch rồi quay lui."""
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


def chep_tep(thu_muc: Path, goc_kho: Path, clinic_id: str) -> dict[str, int]:
    """Chép ``tep/`` của gói vào kho: ``<gốc>/<clinic_id>/lich-su-notion/…``.
    Tệp đã có cùng cỡ thì bỏ qua (chạy lại được)."""
    nguon = thu_muc / "tep"
    dich_goc = goc_kho / clinic_id / "lich-su-notion"
    so = {"chep": 0, "bo_qua": 0}
    if not nguon.exists():
        return so
    for f in nguon.rglob("*"):
        if not f.is_file():
            continue
        dich = dich_goc / f.relative_to(nguon)
        if dich.exists() and dich.stat().st_size == f.stat().st_size:
            so["bo_qua"] += 1
            continue
        dich.parent.mkdir(parents=True, exist_ok=True)
        tam = dich.with_name(dich.name + ".tam")
        shutil.copyfile(f, tam)
        os.replace(tam, dich)
        so["chep"] += 1
    return so


def _sha_goi(thu_muc: Path) -> str:
    h = hashlib.sha256()
    for ten in BANG_GOI:
        p = thu_muc / f"{ten}.jsonl"
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


async def _main(argv: list[str]) -> None:
    from clinicai.services.media_service import goc_cfs

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
            nguoi_chay="nhap-lich-su-notion",
            clinic_id=clinic_id,
        )
    finally:
        await pool.close()
    kq["sha_goi"] = _sha_goi(thu_muc)
    if that and "--khong-chep-tep" not in argv:
        kq["tep"] = chep_tep(thu_muc, goc_cfs(), kq["clinic_id"])
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    print("THỬ KHÔ — chưa ghi gì. Thêm --that để ghi thật." if not that else "ĐÃ GHI.")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
