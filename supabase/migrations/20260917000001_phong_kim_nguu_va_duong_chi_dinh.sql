-- Phòng Kim Ngưu + một đường chỉ định duy nhất (Tuyền chốt 16/09/2026 khuya).
--
-- ĐO TRÊN FINAL CLOUD TRƯỚC KHI VIẾT:
--   * `clinic_room` vẫn là bộ phòng mẫu (Khám 1–4, SA1–3, Sinh hiệu…) — không
--     phòng nào trùng với lịch Excel Kim Ngưu, nên hàng chờ theo phòng không có
--     chỗ để đứng.
--   * `vi_tri_lam_viec` (27 vị trí) KHÔNG trỏ tới phòng nào: biết hôm nay cô A
--     đứng "Điều dưỡng siêu âm 1" nhưng không biết đó là hàng chờ của phòng nào.
--   * `DICHVU-THUTHUAT` khai điều dưỡng làm được. Tuyền: *"tất cả là các bác sĩ
--     làm đó, điều dưỡng rồi thư ký trợ lý chỉ hỗ trợ thôi"*.
--
-- MỘT ĐƯỜNG CHỈ ĐỊNH: `service_order` + `queue_entry`. Migration này chỉ thêm
-- chỗ cần cho đường ấy — gắn tệp vào đúng chỉ định, bác sĩ duyệt theo chỉ định,
-- ai lấy mẫu theo từng xét nghiệm. Không đụng các bảng đường cũ.
--
-- CHẠY LẠI ĐƯỢC: mọi câu đều IF NOT EXISTS / ON CONFLICT / chỉ ghi chỗ khác.

BEGIN;

-- ── 1. Phòng Kim Ngưu ──────────────────────────────────────────────────────
-- Tên phòng lấy đúng chữ trong lịch Excel, để lịch, thanh bên và TV cùng một tên.
WITH phong(code, name, floor, sort, show_on_tv, nodes) AS (
    VALUES
    ('KN-TIEPDON',   'Quầy tiếp đón',            'Tầng 1', 10, false,
        ARRAY['LUOTKHAM-01', 'LUOTKHAM-14']),
    ('KN-DOCHISO',   'Đo chỉ số sức khoẻ',       'Tầng 1', 20, true,
        ARRAY['LUOTKHAM-03']),
    ('KN-LAYMAU',    'Lấy mẫu',                  'Tầng 1', 30, true,
        ARRAY['DICHVU-LAYMAU-MAU', 'DICHVU-LAYMAU-NUOCTIEU']),
    ('KN-NOITIET',   'Phòng Nội tiết',           'Tầng 1', 40, true,
        ARRAY['KHAM-NOITIET', 'KHAM-PHUKHOA', 'KHAM-SANKHOA',
              'KHAM-HIEMMUON-VOSINH', 'KHAM-NAMKHOA']),
    ('KN-THUTHUAT',  'Phòng thủ thuật',          'Tầng 1', 50, true,
        ARRAY['DICHVU-THUTHUAT', 'DICHVU-LAYMAU-AMDAO', 'DICHVU-SANGLOC-COTUCUNG']),
    ('KN-SA-T1',     'Phòng siêu âm tầng 1',     'Tầng 1', 60, true,
        ARRAY['DICHVU-SIEUAM']),
    ('KN-TTNG',      'Thủ thuật ngoài giờ',      'Tầng 1', 70, true,
        ARRAY['DICHVU-THUTHUAT']),
    ('KN-QUAYTHUOC', 'Quầy thuốc',               'Tầng 2', 80, false,
        ARRAY['THUOC-04', 'DICHVU-THUOC']),
    ('KN-SANCHAU',   'Phòng Sàn chậu',           'Tầng 4', 90, true,
        ARRAY['KHAM-PHUKHOA', 'DICHVU-THUTHUAT']),
    ('KN-SAN-BIO',   'Phòng Sản - Biofeedback',  'Tầng 4', 100, true,
        ARRAY['KHAM-SANKHOA', 'DICHVU-THUTHUAT']),
    ('KN-SA1',       'Phòng siêu âm 1 (tầng 4)', 'Tầng 4', 110, true,
        ARRAY['DICHVU-SIEUAM']),
    ('KN-SA2',       'Phòng siêu âm 2 (tầng 4)', 'Tầng 4', 120, true,
        ARRAY['DICHVU-SIEUAM'])
),
dung AS (
    INSERT INTO
        public.clinic_room
        (clinic_id, location_id, code, name, node_code, floor, sort, show_on_tv)
    SELECT c.id,
           (SELECT l.id FROM public.clinic_location l
             WHERE l.clinic_id = c.id AND l.is_active
             ORDER BY l.created_at, l.id LIMIT 1),
           p.code, p.name, p.nodes[1], p.floor, p.sort, p.show_on_tv
      FROM phong p
      CROSS JOIN public.clinic c
     WHERE c.id = 'a0000000-0000-4000-8000-000000000001'
       AND EXISTS (SELECT 1 FROM public.clinic_location l
                    WHERE l.clinic_id = c.id AND l.is_active)
    ON CONFLICT (clinic_id, code) DO UPDATE
        SET name = EXCLUDED.name, floor = EXCLUDED.floor, sort = EXCLUDED.sort,
            show_on_tv = EXCLUDED.show_on_tv, is_active = true, accepting = true,
            updated_at = now()
    RETURNING id, clinic_id, code
)
INSERT INTO
    public.clinic_room_node (clinic_id, room_id, node_code)
SELECT d.clinic_id, d.id, n.node
  FROM dung d
  JOIN phong p ON p.code = d.code
 CROSS JOIN LATERAL unnest(p.nodes) AS n(node)
 WHERE EXISTS (SELECT 1 FROM public.node_definition nd
                WHERE nd.clinic_id = d.clinic_id AND nd.code = n.node)
ON CONFLICT (room_id, node_code) DO NOTHING;

-- Bộ phòng mẫu cũ: TẮT, không xoá — lịch sử điều phối vẫn trỏ về chúng.
UPDATE public.clinic_room
   SET is_active = false, accepting = false, updated_at = now()
 WHERE clinic_id = 'a0000000-0000-4000-8000-000000000001'
   AND code NOT LIKE 'KN-%'
   AND is_active;

-- ── 2. Vị trí trong lịch → phòng ──────────────────────────────────────────
ALTER TABLE public.vi_tri_lam_viec
    ADD COLUMN IF NOT EXISTS room_id uuid REFERENCES public.clinic_room(id)
        ON DELETE SET NULL;

COMMENT ON COLUMN public.vi_tri_lam_viec.room_id IS
    'Hàng chờ của phòng nào. Người đứng vị trí này hôm nay thấy hàng chờ ấy. '
    'NULL = vị trí không làm việc với hàng chờ phòng (trưởng ca).';

UPDATE public.vi_tri_lam_viec v
   SET room_id = r.id
  FROM (VALUES
    ('T1_LETAN', 'KN-TIEPDON'), ('T1_THUNGAN', 'KN-TIEPDON'),
    ('T1_DOCHISO', 'KN-DOCHISO'), ('T1_LAYMAU', 'KN-LAYMAU'),
    ('T1_BS_NOITIET', 'KN-NOITIET'), ('T1_HOIBENH', 'KN-NOITIET'),
    ('T1_TKYK', 'KN-NOITIET'),
    ('T1_TT_BS', 'KN-THUTHUAT'), ('T1_TT_DD', 'KN-THUTHUAT'),
    ('T1_SA_BS', 'KN-SA-T1'), ('T1_SA_DD', 'KN-SA-T1'),
    ('T1_TTNG_BS', 'KN-TTNG'), ('T1_TTNG_DD1', 'KN-TTNG'),
    ('T1_TTNG_DD2', 'KN-TTNG'),
    ('T2_XEPTHUOC', 'KN-QUAYTHUOC'), ('T2_TAODON', 'KN-QUAYTHUOC'),
    ('T4_SANCHAU_BS', 'KN-SANCHAU'), ('T4_SANCHAU_BSTT', 'KN-SANCHAU'),
    ('T4_SANCHAU_DD', 'KN-SANCHAU'),
    ('T4_SAN_BS', 'KN-SAN-BIO'), ('T4_SAN_DD', 'KN-SAN-BIO'),
    ('T4_BIO_DD', 'KN-SAN-BIO'),
    ('T4_SA_BS1', 'KN-SA1'), ('T4_SA_DD1', 'KN-SA1'),
    ('T4_SA_BS2', 'KN-SA2'), ('T4_SA_DD2', 'KN-SA2')
  ) AS m(vi_tri, phong)
  JOIN public.clinic_room r
    ON r.code = m.phong AND r.clinic_id = 'a0000000-0000-4000-8000-000000000001'
 WHERE v.code = m.vi_tri AND v.clinic_id = r.clinic_id
   AND v.room_id IS DISTINCT FROM r.id;

-- ── 3. Thủ thuật do BÁC SĨ làm ────────────────────────────────────────────
UPDATE public.node_definition
   SET actor_roles = ARRAY['DOCTOR']
 WHERE code IN ('DICHVU-THUTHUAT', 'DICHVU-LAYMAU-AMDAO', 'DICHVU-SANGLOC-COTUCUNG')
   AND actor_roles IS DISTINCT FROM ARRAY['DOCTOR'];

-- ── 4. Ai lấy mẫu — theo TỪNG xét nghiệm ──────────────────────────────────
ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS doi_tac_lay_mau boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_price.doi_tac_lay_mau IS
    'Xét nghiệm này đối tác tự lấy mẫu (true) hay điều dưỡng phòng khám lấy '
    '(false). Quản lý tích trong cấu hình. Chỉ có nghĩa với bước lấy mẫu.';

-- ── 5. Kết quả gắn vào ĐÚNG chỉ định ──────────────────────────────────────
ALTER TABLE public.tep_ket_qua
    ADD COLUMN IF NOT EXISTS service_order_id uuid
        REFERENCES public.service_order(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_service_order
    ON public.tep_ket_qua (service_order_id) WHERE service_order_id IS NOT NULL;

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS ket_qua_luc timestamptz,
    ADD COLUMN IF NOT EXISTS bac_si_danh_gia text,
    ADD COLUMN IF NOT EXISTS duyet_luc timestamptz,
    ADD COLUMN IF NOT EXISTS duyet_boi uuid REFERENCES public.staff(id)
        ON DELETE RESTRICT;

COMMENT ON COLUMN public.service_order.ket_qua_luc IS
    'Lần đầu có kết quả (tệp hoặc nội dung) cho chỉ định này — đối tác hay người '
    'thực hiện tải lên. Chờ bác sĩ duyệt khi duyet_luc còn NULL.';
COMMENT ON COLUMN public.service_order.duyet_luc IS
    'Bác sĩ duyệt kết quả + cho phép gửi khách. Từ mốc này CSKH thấy "Đã có kết quả".';

DO $$
DECLARE
    so_phong integer;
    vi_tri_co_phong integer;
BEGIN
    SELECT count(*) INTO so_phong FROM public.clinic_room
     WHERE code LIKE 'KN-%' AND is_active;
    SELECT count(*) INTO vi_tri_co_phong FROM public.vi_tri_lam_viec
     WHERE room_id IS NOT NULL;
    RAISE NOTICE 'Phòng Kim Ngưu: %, vị trí đã nối phòng: %', so_phong, vi_tri_co_phong;
END $$;

COMMIT;
