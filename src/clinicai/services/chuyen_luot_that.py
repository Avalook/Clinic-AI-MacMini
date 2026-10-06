"""CHUYỂN lịch sử khám cũ (schema ``lich_su_notion``) thành LƯỢT THẬT (06/10/2026).

Mỗi nhóm (khách, ngày khám) cũ thành MỘT lượt đã khám xong, đi đúng đường dữ liệu
của một lượt bình thường để mọi màn tự hiện:

    appointment COMPLETED (slot 00:00 giờ VN → màn chỉ in NGÀY)
    → visit FINALIZED → consultation PRIMARY → phieu_kham_luot (chẩn đoán, mục A)
    → service_order performed (siêu âm/thủ thuật/xét nghiệm) → form_instance KQ_CHUNG
      (mô tả + kết luận tờ kết quả) → tep_ket_qua (PDF xét nghiệm) → prescription.

Giá trị từng cột chọn để KHÔNG rò thành việc ma (hàng đợi, quầy thu, CSKH, nhắc
tái khám): xem ``claude/RA-SOAT-LUOT-THAT-0510.md`` + PR. Không chèn lab_result,
queue_entry, payment.

* Ngày đó khách đã có lượt thật trên hệ thống (nhập song song từ 18/09) → KHÔNG
  tạo lượt thứ hai; bản cũ vẫn xem ở khối "Hồ sơ khám trước 10/2026".
* Chạy lại an toàn: lượt đã có trong ``lich_su_notion.luot_that`` thì bỏ qua.
* MỘT giao dịch, mặc định THỬ KHÔ. ``--that`` mới ghi. Gỡ: scripts/hoan-tac-luot-that.sql.

    python -m clinicai.services.chuyen_luot_that [--tep-meta tep_meta.jsonl] [--that]
"""

# ruff: noqa: E501 — tệp này phần lớn là câu SQL dài, ngắt dòng làm khó đọc hơn.
from __future__ import annotations

import asyncio
import json
import os
import sys
import unicodedata
from pathlib import Path
from typing import Any

import asyncpg

TEN_NGUOI_NHAP = "Hồ sơ cũ"
MA_LOAI_KHONG_GHI = "HO_SO_CU"
TEN_LOAI_KHONG_GHI = "Không ghi loại khám"

# form → (khoá ô chẩn đoán, khoá ô mục A). HMVS chọn ô chẩn đoán theo giới.
_O_FORM = """
    (VALUES ('PK','pk_dx','pk_a_note'), ('NT','nt_dx','nt_a_note'),
            ('NK','nk_dx','nk_a_note'), ('SK','sk_conclusion','sk_a_note'),
            ('HMVS','hmvs_dx_w','hmvs_a_note'),
            ('SAN_CHAU','sc_dx','san_chau_a_note'),
            ('THU_THUAT','tt_conclusion','thu_thuat_a_note'))
"""

_TEN = "regexp_replace(lower(public.f_unaccent(btrim(coalesce({}, '')))), '\\s+', ' ', 'g')"


def _o(gia_tri: str) -> str:
    """Một ô phiếu dạng {"gia_tri":…, "nguon":"USER"}; rỗng → NULL (bị strip)."""
    return (
        f"CASE WHEN nullif(btrim({gia_tri}), '') IS NOT NULL THEN "
        f"jsonb_build_object('gia_tri', btrim({gia_tri}), 'nguon', 'USER') END"
    )


_O_MUC_A = _o("concat_ws(E'\\n\\n', 'Dịch vụ: ' || kh.ten, n.kham_tv, n.ghi_chu)")


class _ThuKho(Exception):  # noqa: N818 — tín hiệu quay lui, không phải lỗi
    pass


async def _chuyen(
    conn: asyncpg.Connection, tep_meta: list[dict[str, Any]]
) -> dict[str, Any]:
    clinic = await conn.fetchval(
        "SELECT clinic_id FROM lich_su_notion.lan_nhap WHERE hoan_tac_luc IS NULL "
        "ORDER BY id DESC LIMIT 1"
    )
    if clinic is None:
        raise SystemExit("Chưa có lần nạp lịch sử nào.")
    co_so = await conn.fetchval(
        "SELECT id FROM clinic_location WHERE clinic_id = $1 ORDER BY created_at LIMIT 1",
        clinic,
    )
    lan = await conn.fetchval(
        "INSERT INTO lich_su_notion.lan_chuyen (clinic_id) VALUES ($1) RETURNING id",
        clinic,
    )

    # Người đứng tên các cột bắt buộc khi lượt cũ không ghi ai: nhân sự HỆ THỐNG,
    # không hoạt động, không thành viên phòng khám → không bao giờ thành người ký.
    may = await conn.fetchval(
        "SELECT id FROM staff WHERE employment_type = 'SYSTEM' AND full_name = $1 LIMIT 1",
        TEN_NGUOI_NHAP,
    )
    if may is None:
        may = await conn.fetchval(
            "INSERT INTO staff (full_name, short_name, primary_location_id, primary_department,"
            " employment_type, is_active) VALUES ($1, $1, $2, 'MANAGEMENT', 'SYSTEM', false)"
            " RETURNING id",
            TEN_NGUOI_NHAP,
            co_so,
        )
    # Loại khám cho lượt cũ không ghi loại (appointment.service_type_id NOT NULL).
    loai_khong_ghi = await conn.fetchval(
        "SELECT id FROM service_type WHERE clinic_id = $1 AND code = $2",
        clinic,
        MA_LOAI_KHONG_GHI,
    )
    if loai_khong_ghi is None:
        loai_khong_ghi = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active) VALUES ($1, $2, $3, false)"
            " RETURNING id",
            clinic,
            MA_LOAI_KHONG_GHI,
            TEN_LOAI_KHONG_GHI,
        )

    await conn.execute(
        "CREATE TEMP TABLE _ts ON COMMIT DROP AS SELECT $1::uuid AS clinic, $2::uuid AS co_so,"
        " $3::uuid AS may, $4::uuid AS loai_khong_ghi, $5::bigint AS lan",
        clinic,
        co_so,
        may,
        loai_khong_ghi,
        lan,
    )
    await conn.execute(
        "CREATE TEMP TABLE _tep_meta (khoa text PRIMARY KEY, so_byte bigint, sha256 text)"
        " ON COMMIT DROP"
    )
    if tep_meta:
        await conn.copy_records_to_table(
            "_tep_meta",
            records=[
                (unicodedata.normalize("NFC", m["khoa"]), m["so_byte"], m["sha256"])
                for m in tep_meta
            ],
        )

    so: dict[str, Any] = {"lan_chuyen_id": lan, "clinic_id": str(clinic)}
    for buoc, sql in _CAC_BUOC:
        kq = await conn.execute(sql)
        so[buoc] = int(kq.split()[-1]) if kq and kq.split()[-1].isdigit() else kq
    so["con_lai_chua_chuyen"] = await conn.fetchval(
        "SELECT count(*) FROM lich_su_notion.luot_kham l WHERE NOT EXISTS"
        " (SELECT 1 FROM lich_su_notion.luot_that t WHERE t.notion_id = l.notion_id)"
    )
    await conn.execute(
        "UPDATE lich_su_notion.lan_chuyen SET so_lieu = $2 WHERE id = $1",
        lan,
        json.dumps(so, default=str),
    )
    return so


_NHOM = """
CREATE TEMP TABLE _nhom ON COMMIT DROP AS
WITH moi AS (
    SELECT l.* FROM lich_su_notion.luot_kham l, _ts
     WHERE l.clinic_id = _ts.clinic
       AND NOT EXISTS (SELECT 1 FROM lich_su_notion.luot_that t WHERE t.notion_id = l.notion_id)
), g AS (
    SELECT clinic_patient_id, ngay_kham,
           array_agg(notion_id ORDER BY lan_thu NULLS LAST, notion_id) AS cac_luot,
           (array_agg(service_type_id ORDER BY lan_thu NULLS LAST, notion_id)
                FILTER (WHERE service_type_id IS NOT NULL))[1] AS loai,
           (array_agg(staff_id ORDER BY lan_thu NULLS LAST, notion_id)
                FILTER (WHERE staff_id IS NOT NULL))[1] AS bs,
           string_agg(DISTINCT nullif(btrim(chan_doan), ''), E'\\n') AS chan_doan,
           string_agg(nullif(btrim(kham_tu_van), ''), E'\\n\\n'
                      ORDER BY lan_thu NULLS LAST, notion_id) AS kham_tv,
           string_agg(DISTINCT nullif(btrim(ghi_chu_vinh_vien), ''), E'\\n') AS ghi_chu
      FROM moi GROUP BY 1, 2
)
SELECT g.*,
       (g.ngay_kham::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') AS luc,
       gen_random_uuid() AS appt, gen_random_uuid() AS visit, gen_random_uuid() AS phien,
       coalesce(g.loai, _ts.loai_khong_ghi) AS loai_that,
       coalesce(st.form_code, 'PK') AS form_id,
       (EXISTS (SELECT 1 FROM visit v
                 WHERE v.clinic_id = _ts.clinic AND v.clinic_patient_id = g.clinic_patient_id
                   AND (v.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = g.ngay_kham)
        OR EXISTS (SELECT 1 FROM appointment a
                 WHERE a.clinic_id = _ts.clinic AND a.clinic_patient_id = g.clinic_patient_id
                   AND a.slot_start = (g.ngay_kham::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh')))
           AS trung
  FROM g CROSS JOIN _ts
  LEFT JOIN service_type st ON st.id = g.loai
"""

# Dịch vụ khám ([KH]…) không phải chỉ định cận lâm sàng: ghi tên vào mục A.
_KH = """
CREATE TEMP TABLE _kh ON COMMIT DROP AS
SELECT n.visit, string_agg(DISTINCT array_to_string(d.ten_goc, ', '), E'\\n') AS ten
  FROM _nhom n JOIN lich_su_notion.dich_vu d ON d.luot_kham_id = ANY (n.cac_luot)
 WHERE NOT n.trung AND array_to_string(d.ten_goc, ' ') ~ '^\\s*\\[KH\\]'
 GROUP BY 1
"""

_CAC_BUOC: list[tuple[str, str]] = [
    ("nhom", _NHOM),
    ("so_luot_trung_ngay", "SELECT 1 FROM _nhom WHERE trung"),
    (
        "ghep_luot",
        """
    INSERT INTO lich_su_notion.luot_that (notion_id, clinic_id, lan_chuyen_id, appointment_id,
                                      visit_id, trung_luot_co_san)
SELECT u.id, _ts.clinic, _ts.lan,
       CASE WHEN n.trung THEN NULL ELSE n.appt END,
       CASE WHEN n.trung THEN NULL ELSE n.visit END, n.trung
  FROM _nhom n CROSS JOIN _ts CROSS JOIN LATERAL unnest(n.cac_luot) AS u(id)
""",
    ),
    ("kh", _KH),
    (
        "appointment",
        """
    INSERT INTO appointment (id, clinic_id, clinic_patient_id, doctor_id, location_id,
                         service_type_id, booking_channel, is_walkin, slot_start, slot_end,
                         status, created_at, updated_at)
SELECT n.appt, _ts.clinic, n.clinic_patient_id, NULL, _ts.co_so, n.loai_that, NULL, false,
       n.luc, n.luc + interval '15 minutes', 'COMPLETED', n.luc, n.luc
  FROM _nhom n CROSS JOIN _ts WHERE NOT n.trung
""",
    ),
    # Bác sĩ gắn SAU: nhánh UPDATE giữ nguyên COMPLETED không kiểm sức chứa ca.
    (
        "appointment_bac_si",
        """
    UPDATE appointment a SET doctor_id = n.bs
  FROM _nhom n, _ts
     WHERE a.clinic_id = _ts.clinic AND a.id = n.appt AND NOT n.trung AND n.bs IS NOT NULL
""",
    ),
    (
        "visit",
        """
    INSERT INTO visit (visit_id, clinic_id, clinic_patient_id, appointment_id, attending_doctor_id,
                   location_id, service_type_id, status, checked_in_at, created_at, updated_at)
SELECT n.visit, _ts.clinic, n.clinic_patient_id, n.appt, n.bs, _ts.co_so, n.loai_that,
       'IN_PROGRESS', n.luc, n.luc, n.luc
  FROM _nhom n CROSS JOIN _ts WHERE NOT n.trung
""",
    ),
    (
        "consultation",
        """
    INSERT INTO consultation (id, clinic_id, visit_id, round_no, kind, status, doctor_staff_id,
                          started_by, started_at, completed_by, completed_at, outcome,
                          created_at, updated_at)
SELECT n.phien, _ts.clinic, n.visit, 1, 'PRIMARY', 'completed', n.bs,
       coalesce(n.bs, _ts.may), n.luc, coalesce(n.bs, _ts.may), n.luc, 'SERVICES', n.luc, n.luc
  FROM _nhom n CROSS JOIN _ts WHERE NOT n.trung
""",
    ),
    (
        "phieu_kham",
        f"""
WITH p AS (
    INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu, revision,
                                 tao_boi, sua_boi, tao_luc, sua_luc)
    SELECT _ts.clinic, n.visit, n.form_id,
           (SELECT max(f.version) FROM form_definition f
             WHERE f.clinic_id = _ts.clinic AND f.form_id = n.form_id
               AND f.trang_thai = 'PUBLISHED'),
           jsonb_strip_nulls(jsonb_build_object(
               CASE WHEN o.dx = 'hmvs_dx_w' AND pt.gender = 'Nam' THEN 'hmvs_dx_m' ELSE o.dx END,
               {_o("n.chan_doan")},
               o.a_note,
               {_O_MUC_A})),
           1, coalesce(n.bs, _ts.may), coalesce(n.bs, _ts.may), n.luc, n.luc
      FROM _nhom n CROSS JOIN _ts
      JOIN {_O_FORM} AS o(form_id, dx, a_note) ON o.form_id = n.form_id
      LEFT JOIN patient pt ON pt.clinic_patient_id = n.clinic_patient_id
      LEFT JOIN _kh kh ON kh.visit = n.visit
     WHERE NOT n.trung
    RETURNING id
)
SELECT count(*) FROM p
""",
    ),
    # Trigger ghi "lịch sử sửa phiếu" mang ngày hôm nay — lượt cũ không có lần sửa
    # nào. Phải là câu RIÊNG: dòng trigger sinh ra không thấy được trong cùng câu.
    (
        "bo_lich_su_sua_phieu",
        """
    DELETE FROM phieu_kham_lich_su h
 USING phieu_kham_luot p, _nhom n
 WHERE h.phieu_id = p.id AND p.visit_id = n.visit AND NOT n.trung
""",
    ),
    # ── Chỉ định cận lâm sàng: dịch vụ (trừ [KH]), tờ kết quả, xét nghiệm ──
    (
        "chi_dinh_tam",
        """
CREATE TEMP TABLE _cd ON COMMIT DROP AS
WITH dv AS (
    SELECT d.notion_id, n.visit, n.phien, n.luc, n.bs,
           array_to_string(d.ten_goc, ', ') AS ten, d.service_code, d.nguoi_lam
      FROM lich_su_notion.dich_vu d JOIN _nhom n ON d.luot_kham_id = ANY (n.cac_luot)
     WHERE NOT n.trung AND array_to_string(d.ten_goc, ' ') !~ '^\\s*\\[KH\\]'
), kq AS (
    SELECT k.*, row_number() OVER (PARTITION BY k.dich_vu_id ORDER BY k.notion_id) AS thu
      FROM lich_su_notion.ket_qua k
)
-- 1) mỗi dịch vụ một chỉ định; tờ kết quả ĐẦU TIÊN của dịch vụ gắn vào chính nó
SELECT gen_random_uuid() AS so, dv.notion_id AS nguon, 'dich_vu' AS loai, dv.visit, dv.phien,
       dv.luc, dv.bs, coalesce(dv.ten, 'Dịch vụ') AS ten, dv.service_code, dv.nguoi_lam,
       kq.notion_id AS kq_id, kq.mo_ta, kq.ket_luan, kq.bac_si_ky, NULL::text AS kq_chu
  FROM dv LEFT JOIN kq ON kq.dich_vu_id = dv.notion_id AND kq.thu = 1
UNION ALL
-- 2) tờ kết quả còn lại (thứ 2 trở đi, hoặc không gắn dịch vụ): chỉ định riêng
SELECT gen_random_uuid(), kq.notion_id, 'ket_qua', n.visit, n.phien, n.luc, n.bs,
       coalesce(nullif(btrim(kq.tieu_de), ''), 'Kết quả siêu âm'), NULL, NULL,
       kq.notion_id, kq.mo_ta, kq.ket_luan, kq.bac_si_ky, NULL
  FROM kq
  LEFT JOIN lich_su_notion.dich_vu d ON d.notion_id = kq.dich_vu_id
  JOIN _nhom n ON coalesce(kq.luot_kham_id, d.luot_kham_id) = ANY (n.cac_luot)
 WHERE NOT n.trung
   AND (kq.thu > 1 OR kq.dich_vu_id IS NULL
        OR array_to_string(d.ten_goc, ' ') ~ '^\\s*\\[KH\\]'
        OR d.luot_kham_id IS NULL)
UNION ALL
-- 3) xét nghiệm: chỉ định riêng, kết quả chữ + tệp PDF
SELECT gen_random_uuid(), x.notion_id, 'xet_nghiem', n.visit, n.phien, n.luc, n.bs,
       'Xét nghiệm' || coalesce(' · ' || nullif(array_to_string(x.noi_lam, ', '), ''), ''),
       NULL, NULL, NULL, NULL, NULL, NULL,
       nullif(concat_ws(E'\\n', nullif(btrim(x.ket_qua), ''),
                        nullif(btrim(x.ket_qua_ai), '')), '')
  FROM lich_su_notion.xet_nghiem x JOIN _nhom n ON x.luot_kham_id = ANY (n.cac_luot)
 WHERE NOT n.trung
""",
    ),
    (
        "service_order",
        f"""
WITH cd AS (
    SELECT c.*,
           CASE WHEN c.loai = 'xet_nghiem' THEN 'DICHVU-LAYMAU-MAU'
                WHEN c.ten ~* '^\\s*\\[TT\\]|thủ thuật' THEN 'DICHVU-THUTHUAT'
                ELSE 'DICHVU-SIEUAM' END AS node,
           (SELECT s.id FROM staff s
             WHERE {_TEN.format("s.full_name")} = {_TEN.format("c.nguoi_lam[1]")}
             LIMIT 1) AS nguoi_lam_id,
           (SELECT s.id FROM staff s
             WHERE {_TEN.format("s.full_name")} = {_TEN.format("c.bac_si_ky[1]")}
             LIMIT 1) AS bs_ky
      FROM _cd c
)
    INSERT INTO service_order (id, clinic_id, visit_id, consultation_id, service_code, service_name,
       node_code, source, exec_status, execution_status, selection_status, recorded_by,
       authorized_by, authorized_at, room_id, performed_by, bac_si_lam_id, started_at,
       finished_at, result_note, ket_qua_luc, duyet_luc, duyet_boi, lan_chi_dinh,
       created_at, updated_at)
SELECT cd.so, _ts.clinic, cd.visit, cd.phien, coalesce(cd.service_code, 'HO_SO_CU'), cd.ten,
       cd.node, 'VISIT_ORDER', 'performed', 'COMPLETED', NULL, coalesce(cd.bs, _ts.may),
       coalesce(cd.bs, _ts.may), cd.luc,
       (SELECT r.id FROM clinic_room r JOIN clinic_room_node rn ON rn.room_id = r.id
         WHERE r.clinic_id = _ts.clinic AND rn.node_code = cd.node
         ORDER BY r.la_doi_tac, r.sort, r.code LIMIT 1),
       coalesce(cd.bs_ky, cd.nguoi_lam_id), coalesce(cd.bs_ky, cd.nguoi_lam_id), cd.luc, cd.luc,
       coalesce(nullif(btrim(cd.ket_luan), ''), cd.kq_chu), cd.luc, cd.luc,
       coalesce(cd.bs_ky, cd.bs, _ts.may), 1, cd.luc, cd.luc
  FROM cd CROSS JOIN _ts
""",
    ),
    (
        "form_ket_qua",
        """
    INSERT INTO form_instance (clinic_id, service_order_id, form_id, version, trang_thai, du_lieu,
                           revision, nhap_boi, thuc_hien_boi, hoan_tat_boi, hoan_tat_luc,
                           tao_luc, sua_luc)
SELECT _ts.clinic, c.so, 'KQ_CHUNG', 1, 'READY',
       jsonb_strip_nulls(jsonb_build_object(
           'noi_dung', nullif(btrim(coalesce(c.mo_ta, c.kq_chu)), ''),
           'ket_luan', nullif(btrim(c.ket_luan), ''))),
       1, so.performed_by, so.performed_by, coalesce(so.performed_by, _ts.may), c.luc,
       c.luc, c.luc
  FROM _cd c CROSS JOIN _ts JOIN service_order so ON so.id = c.so
 WHERE nullif(btrim(coalesce(c.mo_ta, '') || coalesce(c.ket_luan, '') || coalesce(c.kq_chu, '')), '')
       IS NOT NULL
""",
    ),
    (
        "tep_ket_qua",
        """
    INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, appointment_id, service_order_id, khoa,
       ten_hien_thi, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id, tai_len_luc,
       vi_tri, gui_luc, gui_boi_staff_id, gui_kenh, cho_phep_gui_luc, cho_phep_gui_boi_staff_id)
SELECT _ts.clinic, n.clinic_patient_id, n.appt, c.so,
       _ts.clinic::text || '/lich-su-notion/' || m.khoa, t.ten, 'PDF', 'application/pdf',
       m.so_byte, m.sha256, _ts.may, c.luc, 'cfs', c.luc, _ts.may, 'TRUC_TIEP', c.luc, _ts.may
  FROM _cd c CROSS JOIN _ts
  JOIN _nhom n ON n.visit = c.visit
  JOIN lich_su_notion.xet_nghiem x ON x.notion_id = c.nguon
  CROSS JOIN LATERAL jsonb_to_recordset(
      CASE WHEN jsonb_typeof(x.tep) = 'array' THEN x.tep ELSE '[]'::jsonb END)
      AS t(ten text, khoa text)
  JOIN _tep_meta m ON m.khoa = normalize(t.khoa, NFC)
 WHERE c.loai = 'xet_nghiem' AND m.so_byte > 0
ON CONFLICT DO NOTHING
""",
    ),
    (
        "don_thuoc",
        """
    INSERT INTO prescription (id, clinic_id, source_ref, clinic_patient_id, visit_id, drug_name_raw,
       dosage_instructions, quantity, nguon, created_by, closed_at, created_at, updated_at)
SELECT gen_random_uuid(), _ts.clinic, 'ho-so-cu-' || k.notion_id, n.clinic_patient_id, n.visit,
       coalesce(nullif(array_to_string(k.ten_thuoc, ', '), ''), 'Thuốc'),
       nullif(concat_ws(' · ', nullif(btrim(k.huong_dan), ''), nullif(btrim(k.luu_y), '')), ''),
       nullif(concat_ws(' ', nullif(btrim(k.so_luong), ''), nullif(btrim(k.ghi_chu_so_luong), '')), ''),
       'BAC_SI', coalesce(n.bs, _ts.may), n.luc, n.luc, n.luc
  FROM lich_su_notion.ke_thuoc k JOIN _nhom n ON k.luot_kham_id = ANY (n.cac_luot)
  CROSS JOIN _ts
 WHERE NOT n.trung
""",
    ),
    (
        "ky_luot",
        """
    UPDATE visit v SET status = 'FINALIZED', finalized_at = n.luc, finalized_by = n.bs,
       exam_completed_at = n.luc, closed_at = n.luc
  FROM _nhom n, _ts
     WHERE v.clinic_id = _ts.clinic AND v.visit_id = n.visit AND NOT n.trung
""",
    ),
    (
        "so_ghep_ban_ghi",
        """
    INSERT INTO lich_su_notion.ban_ghi_that (notion_id, bang, ban_ghi_id, lan_chuyen_id)
SELECT c.nguon, 'service_order', c.so, _ts.lan FROM _cd c CROSS JOIN _ts
UNION ALL
SELECT c.kq_id, 'service_order', c.so, _ts.lan FROM _cd c CROSS JOIN _ts
 WHERE c.kq_id IS NOT NULL AND c.kq_id <> c.nguon
UNION ALL
SELECT replace(p.source_ref, 'ho-so-cu-', '')::uuid, 'prescription', p.id, _ts.lan
  FROM prescription p CROSS JOIN _ts JOIN _nhom n ON n.visit = p.visit_id
 WHERE p.clinic_id = _ts.clinic AND p.source_ref LIKE 'ho-so-cu-%'
ON CONFLICT DO NOTHING
""",
    ),
]


async def chuyen(
    pool: asyncpg.Pool, *, that: bool, tep_meta: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """``that=False`` = thử khô: chạy hết trong giao dịch rồi quay lui."""
    ket_qua: dict[str, Any] = {}
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                ket_qua = await _chuyen(conn, tep_meta or [])
                if not that:
                    raise _ThuKho
        except _ThuKho:
            ket_qua["thu_kho"] = True
    return ket_qua


async def _main(argv: list[str]) -> None:
    that = "--that" in argv
    meta: list[dict[str, Any]] = []
    if "--tep-meta" in argv:
        p = Path(argv[argv.index("--tep-meta") + 1])
        meta = [json.loads(d) for d in p.read_text().splitlines() if d.strip()]
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=1)
    try:
        kq = await chuyen(pool, that=that, tep_meta=meta)
    finally:
        await pool.close()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    print("THỬ KHÔ — chưa ghi gì. Thêm --that để ghi thật." if not that else "ĐÃ GHI.")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
