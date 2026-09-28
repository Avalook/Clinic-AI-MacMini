-- PHÍ KHÁM = DỊCH VỤ KHÁM NGƯỜI KHÁM CHỌN, THEO MÃ KIOTVIET (Tuyền 28/09/2026).
--
-- "Trước giờ ta đang giả định giá của phụ khoa, nam khoa, sản khoa… nhưng thực
-- tế tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … thêm khu vực tick
-- dưới dòng Bác sĩ tư vấn ghi để chọn loại dịch vụ chính xác của dịch vụ khám,
-- lúc đó tiền mới tính, mình không còn bịa giá nữa."
-- Nguồn sự thật: DanhSachSanPham_KV21092026-171729-2929.xlsx — nhóm "Phí khám"
-- (6 loại khám) và nhóm "Thủ thuật" (loại Thủ thuật).
--
-- 1. `loai_kham_phi`: loại khám → các dịch vụ khám chọn được (tra theo mã KV).
--    Lượt ĐI THẲNG PHÒNG (Sàn chậu, Thủ thuật) dùng danh sách này ở QUẦY để thêm
--    dịch vụ; các loại khác tick ở Bàn khám / quầy thu → tính tiền khám.
-- 2. `luot_phi_kham`: dịch vụ khám đã chọn của một lượt (bỏ = đóng dấu, không xoá).
-- 3. Bảng giá: thêm SP000119, SP000112 (KV để 0đ = CHƯA CÓ GIÁ → để trống, không
--    bịa); đổi tên dòng phí khám sang tên KiotViet; TẮT 4 dòng không có trong
--    KiotViet (giá bịa): Khám phụ khoa 400k, Nội tiết 500k, Thủ thuật 300k,
--    Sàn chậu 300k (không mã).
--
-- Chạy lại được.

-- ── 3. Bảng giá ──────────────────────────────────────────────────────────────
INSERT INTO service_price
    (clinic_id, service_code, name, "group", unit_price, ma_kiotviet,
     billing_owner, category)
SELECT p.clinic_id, v.ma_noi_bo, v.ten, 'dich_vu', v.gia, v.ma_kv, 'CLINIC',
       'Phí khám · KiotViet'
  FROM public.service_price p
 CROSS JOIN (VALUES
       ('KV_SP000119', 'Khám quản lý thai (TS)', 250000::numeric, 'SP000119'),
       ('KV_SP000112', 'Khám sau sinh BN cũ', NULL::numeric, 'SP000112')
     ) AS v(ma_noi_bo, ten, gia, ma_kv)
 WHERE p.service_code = 'KHAM_SAN_1'
   AND NOT EXISTS (
       SELECT 1 FROM public.service_price q
        WHERE q.clinic_id = p.clinic_id AND q.ma_kiotviet = v.ma_kv);

UPDATE public.service_price s
   SET name = v.ten, updated_at = now()
  FROM (VALUES
       ('SP000003', 'Khám mong con lần đầu'),
       ('SP000004', 'Tái khám mong con'),
       ('SP000005', 'Khám tư vấn viêm nhiễm phụ khoa'),
       ('SP000007', 'Khám nam khoa'),
       ('SP000079', 'Khám quản lý thai')
     ) AS v(ma_kv, ten)
 WHERE s.ma_kiotviet = v.ma_kv AND s.name IS DISTINCT FROM v.ten;

UPDATE public.service_price
   SET active = false, updated_at = now()
 WHERE active
   AND ma_kiotviet IS NULL
   AND service_code IN ('CLS_KHAM_PHU_KHOA', 'KHAM_NOI_TIET_TINH_DUC',
                        'KHAM_THU_THUAT', 'KHAM_SAN_CHAU');

-- ── 1. Loại khám → dịch vụ khám chọn được ────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.loai_kham_phi (
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_type_id  uuid NOT NULL REFERENCES public.service_type(id)
                         ON DELETE CASCADE,
    service_price_id uuid NOT NULL REFERENCES public.service_price(id)
                         ON DELETE CASCADE,
    thu_tu           integer NOT NULL DEFAULT 0,
    PRIMARY KEY (clinic_id, service_type_id, service_price_id)
);

COMMENT ON TABLE public.loai_kham_phi IS
'Loại khám → dịch vụ khám chọn được (mã KiotViet). Nguồn: file KiotViet 21/09/2026, Tuyền chốt 28/09.';

INSERT INTO public.loai_kham_phi (clinic_id, service_type_id, service_price_id, thu_tu)
SELECT st.clinic_id, st.id, sp.id, v.thu_tu
  FROM (VALUES
       ('PHU_KHOA', 'SP000005', 1), ('PHU_KHOA', 'SP000006', 2),
       ('NOI_TIET_TINH_DUC', 'SP000006', 1),
       ('SAN_1', 'SP000079', 1), ('SAN_1', 'SP000119', 2), ('SAN_1', 'SP000112', 3),
       ('HIEM_MUON', 'SP000003', 1), ('HIEM_MUON', 'SP000004', 2),
       ('NAM_KHOA', 'SP000007', 1),
       ('SAN_CHAU', 'SP000006', 1), ('SAN_CHAU', 'SP000145', 2),
       ('THU_THUAT', 'SP000020', 1), ('THU_THUAT', 'SP000021', 2),
       ('THU_THUAT', 'SP000022', 3), ('THU_THUAT', 'SP000023', 4),
       ('THU_THUAT', 'SP000024', 5), ('THU_THUAT', 'SP000074', 6),
       ('THU_THUAT', 'SP000076', 7), ('THU_THUAT', 'SP000091', 8),
       ('THU_THUAT', 'SP000093', 9), ('THU_THUAT', 'SP000100', 10),
       ('THU_THUAT', 'SP000102', 11), ('THU_THUAT', 'SP000104', 12),
       ('THU_THUAT', 'SP000109', 13), ('THU_THUAT', 'SP000114', 14),
       ('THU_THUAT', 'SP000115', 15), ('THU_THUAT', 'SP000116', 16),
       ('THU_THUAT', 'SP000126', 17), ('THU_THUAT', 'SP000133', 18),
       ('THU_THUAT', 'SP000137', 19), ('THU_THUAT', 'SP000151', 20),
       ('THU_THUAT', 'SP000156', 21), ('THU_THUAT', 'SP000162', 22),
       ('THU_THUAT', 'SP000165', 23), ('THU_THUAT', 'SP000167', 24),
       ('THU_THUAT', 'SP000168', 25), ('THU_THUAT', 'SP000214', 26),
       ('THU_THUAT', 'SP000215', 27)
     ) AS v(loai, ma_kv, thu_tu)
  JOIN public.service_type st ON st.code = v.loai
  JOIN public.service_price sp
    ON sp.clinic_id = st.clinic_id AND sp.ma_kiotviet = v.ma_kv AND sp.active
ON CONFLICT DO NOTHING;

-- ── 2. Dịch vụ khám đã chọn của lượt ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.luot_phi_kham (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    service_price_id uuid NOT NULL REFERENCES public.service_price(id)
                         ON DELETE RESTRICT,
    chon_boi         uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    chon_luc         timestamptz NOT NULL DEFAULT now(),
    bo_boi           uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    bo_luc           timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS luot_phi_kham_mot_dong_song
    ON public.luot_phi_kham (clinic_id, visit_id, service_price_id)
    WHERE bo_luc IS NULL;
CREATE INDEX IF NOT EXISTS luot_phi_kham_theo_luot
    ON public.luot_phi_kham (clinic_id, visit_id);

COMMENT ON TABLE public.luot_phi_kham IS
'Dịch vụ khám đã chọn của một lượt (tick ở Bàn khám / quầy). Tiền khám = tổng các dòng còn sống. Bỏ tick = đóng dấu bo_luc.';

ALTER TABLE public.loai_kham_phi ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.luot_phi_kham ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS loai_kham_phi_select_own_clinic ON public.loai_kham_phi;
CREATE POLICY loai_kham_phi_select_own_clinic ON public.loai_kham_phi
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS luot_phi_kham_select_own_clinic ON public.luot_phi_kham;
CREATE POLICY luot_phi_kham_select_own_clinic ON public.luot_phi_kham
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.loai_kham_phi TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.luot_phi_kham TO service_role;
