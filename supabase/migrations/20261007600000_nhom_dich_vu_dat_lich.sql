-- NHÓM DỊCH VỤ ĐẶT LỊCH (Tuyền chốt 07/10/2026 — docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md
-- T0–T3). Bộ chọn dịch vụ lúc đặt lịch có 4 nhóm: Khám · Điều trị · Thuốc (ẩn
-- hẳn, T4) · Khác. Nhóm là DỮ LIỆU của loại khám, máy chủ gom (services/
-- dich_vu_dat_lich.py) — giao diện không tự xếp nhóm theo tên.
--
--   * `nhom`  — KHAM (7 loại khám đang có) · DIEU_TRI · THUOC · KHAC.
--   * `thu_tu` — thứ tự trong nhóm (đúng thứ tự Tuyền liệt kê).
--   * `service_price_id` — loại Điều trị TRỎ đúng dòng bảng giá của dịch vụ: giá
--     = giá dòng ấy, không giá riêng ở loại khám, không thu phí khám (T2).
--     Khoá ngoại theo (clinic_id, id) để không trỏ nhầm sang phòng khám khác.
--
-- Sáu loại Điều trị khớp dòng giá theo mã KiotViet trước, tên chuẩn hoá sau
-- (migration 20261002100000: prod có CLS_BIOFEEDBACK/SP000146, CLS_GHE_DTT/
-- SP000158, CLS_LASER_TRE_HOA/SP000215, CLS_LASER_ST_SSD/SP000168, KV_SP000167,
-- KV_SP000165). Phòng khám không có dòng giá nào khớp thì KHÔNG thêm loại ấy —
-- không bịa giá.
--
-- "Khác" (T3): không bắt chọn dịch vụ, ghi chú khuyến khích (appointment.notes),
-- không phiếu khám riêng.
--
-- Chạy lại được: 20260807000007 / 20260917000006 (chạy lại sau seed ở dev-up và
-- ở lượt hai của CI) tắt mọi mã ngoài năm mã lõi → ở đây UPDATE đưa về đúng trạng
-- thái, không chỉ INSERT DO NOTHING (bẫy memory nam-dich-vu-kham-va-tang).

ALTER TABLE public.service_type
    ADD COLUMN IF NOT EXISTS nhom text NOT NULL DEFAULT 'KHAM',
    ADD COLUMN IF NOT EXISTS thu_tu integer NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS service_price_id uuid;

DO $$
BEGIN
    ALTER TABLE public.service_type
        ADD CONSTRAINT service_type_nhom_hop_le
        CHECK (nhom IN ('KHAM', 'DIEU_TRI', 'THUOC', 'KHAC'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Điều trị bắt buộc có dòng giá; nhóm khác không mang dòng giá (tiền khám đi
-- theo `loai_kham_phi`, không theo cột này).
DO $$
BEGIN
    ALTER TABLE public.service_type
        ADD CONSTRAINT service_type_dieu_tri_co_gia
        CHECK ((nhom = 'DIEU_TRI') = (service_price_id IS NOT NULL));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_service_price_clinic_id_id
    ON public.service_price (clinic_id, id);

DO $$
BEGIN
    ALTER TABLE public.service_type
        ADD CONSTRAINT service_type_gia_cung_phong_kham
        FOREIGN KEY (clinic_id, service_price_id)
        REFERENCES public.service_price (clinic_id, id) ON DELETE RESTRICT;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON COLUMN public.service_type.nhom IS
    'Nhóm ở bộ chọn đặt lịch: KHAM | DIEU_TRI | THUOC (ẩn) | KHAC — 07/10/2026.';
COMMENT ON COLUMN public.service_type.service_price_id IS
    'Loại Điều trị: dòng bảng giá của chính dịch vụ (giá = dòng này, không phí khám).';

-- ── Khám: thứ tự như ô chọn cũ (5 lĩnh vực rồi Thủ thuật, Sàn chậu) ─────────
UPDATE public.service_type st
   SET thu_tu = v.thu_tu
  FROM (VALUES ('PHU_KHOA', 1), ('SAN_1', 2), ('NOI_TIET_TINH_DUC', 3),
               ('HIEM_MUON', 4), ('NAM_KHOA', 5), ('THU_THUAT', 6),
               ('SAN_CHAU', 7)) AS v(ma, thu_tu)
 WHERE st.code = v.ma AND st.nhom = 'KHAM' AND st.thu_tu IS DISTINCT FROM v.thu_tu;

-- ── Điều trị: 6 loại, mỗi loại trỏ một dòng giá ────────────────────────────
WITH muc(ma, ten, thu_tu, ma_kiotviet, ten_gia) AS (
    VALUES
    ('DT_BIO', 'Tập máy Bio điều trị (chưa gồm đầu dò)', 11, 'SP000146',
     'Tập máy Bio điều trị (chưa bao gồm đầu dò)'),
    ('DT_GHE_DTT', 'Ghế điện từ trường', 12, 'SP000158', 'Ghế điện từ trường'),
    ('DT_LASER_TIEN_DINH', 'Laser trẻ hoá tiền đình', 13, 'SP000165',
     'Laser trẻ hoá tiền đình'),
    ('DT_LASER_TIEN_DINH_AM_DAO', 'Laser trẻ hoá tiền đình và âm đạo', 14,
     'SP000215', 'Laser trẻ hoá tiền đình và âm đạo'),
    ('DT_LASER_1_THANH', 'Laser điều trị bệnh lý 1 thành', 15, 'SP000167',
     'Laser điều trị bệnh lý (SSD, són tiểu..) (1 thành)'),
    ('DT_LASER_2_THANH', 'Laser điều trị bệnh lý 2 thành', 16, 'SP000168',
     'Laser điều trị bệnh lý (SSD, són tiểu…) 2 thành')
), gia AS (
    SELECT DISTINCT ON (c.id, m.ma)
           c.id AS clinic_id, m.ma, m.ten, m.thu_tu, sp.id AS sp_id
      FROM public.clinic c
     CROSS JOIN muc m
      JOIN public.service_price sp
        ON sp.clinic_id = c.id AND sp."group" = 'dich_vu' AND sp.active
       AND (sp.ma_kiotviet = m.ma_kiotviet
            OR public.khoa_ten_dich_vu(sp.name) = public.khoa_ten_dich_vu(m.ten_gia))
     ORDER BY c.id, m.ma,
              (sp.ma_kiotviet IS NOT DISTINCT FROM m.ma_kiotviet) DESC,
              sp.service_code
)
INSERT INTO public.service_type
    (clinic_id, code, name, default_duration_minutes, is_active, form_code,
     form_code_nam, qua_tu_van, di_thang_phong, nhom, thu_tu, service_price_id)
SELECT g.clinic_id, g.ma, g.ten, 30, true, NULL, NULL, false, false, 'DIEU_TRI',
       g.thu_tu, g.sp_id
  FROM gia g
ON CONFLICT (clinic_id, code) DO UPDATE
   SET name = EXCLUDED.name, is_active = true, form_code = NULL,
       form_code_nam = NULL, qua_tu_van = false, di_thang_phong = false,
       nhom = 'DIEU_TRI', thu_tu = EXCLUDED.thu_tu,
       service_price_id = EXCLUDED.service_price_id
 WHERE (service_type.name, service_type.is_active, service_type.form_code,
        service_type.form_code_nam, service_type.qua_tu_van,
        service_type.di_thang_phong, service_type.nhom, service_type.thu_tu,
        service_type.service_price_id)
       IS DISTINCT FROM
       (EXCLUDED.name, true, NULL::text, NULL::text, false, false, 'DIEU_TRI',
        EXCLUDED.thu_tu, EXCLUDED.service_price_id);

-- ── Khác: mọi phòng khám một dòng ──────────────────────────────────────────
INSERT INTO public.service_type
    (clinic_id, code, name, default_duration_minutes, is_active, form_code,
     qua_tu_van, di_thang_phong, nhom, thu_tu)
SELECT c.id, 'KHAC', 'Khác', 30, true, NULL, false, false, 'KHAC', 99
  FROM public.clinic c
ON CONFLICT (clinic_id, code) DO UPDATE
   SET name = 'Khác', is_active = true, form_code = NULL, form_code_nam = NULL,
       qua_tu_van = false, di_thang_phong = false, nhom = 'KHAC', thu_tu = 99,
       service_price_id = NULL
 WHERE (service_type.name, service_type.is_active, service_type.form_code,
        service_type.form_code_nam, service_type.qua_tu_van,
        service_type.di_thang_phong, service_type.nhom, service_type.thu_tu,
        service_type.service_price_id)
       IS DISTINCT FROM
       ('Khác', true, NULL::text, NULL::text, false, false, 'KHAC', 99, NULL::uuid);
