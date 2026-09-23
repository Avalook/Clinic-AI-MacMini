-- Form Template Engine — một cỗ máy, nhiều biểu mẫu (23/09/2026).
--
-- VÌ SAO. Phòng khám có 18 mẫu kết quả cận lâm sàng, 7 biểu mẫu khám, và các
-- phiếu thủ thuật. Chúng **na ná nhau**: cùng là "vài mục, mỗi mục vài ô, có câu
-- mẫu điền sẵn, sửa thoải mái, xong thì xác nhận". Viết 19 cái form bằng 19 đoạn
-- code là 19 chỗ phải sửa mỗi lần bác sĩ đổi một câu chữ.
--
-- Nên: MỘT engine, và mỗi biểu mẫu là DỮ LIỆU (`form_definition.khung`). Đổi chữ
-- trong mẫu = sửa dữ liệu, không đụng code.
--
-- BỐN LUẬT ĐÃ CHỐT TRONG CHAT (#174–#178)
--   1. "Hoàn tất" = **xác nhận toàn bộ nội dung hiện tại**, kể cả câu mẫu không
--      sửa (#177). Câu điền sẵn chỉ là gợi ý nháp cho tới lúc ấy.
--   2. Sửa mẫu v4 → v5 **không đổi hồ sơ cũ**: mỗi hồ sơ ghim đúng phiên bản nó
--      đã dùng. Bản đã xuất bản không sửa tại chỗ.
--   3. `entered_by ≠ performed_by`: người gõ (điều dưỡng nhập thay) không mặc
--      định là người thực hiện. Người gõ là chuyện nhật ký; người thực hiện là
--      dữ liệu nghiệp vụ.
--   4. Mỗi giá trị nhớ **nó từ đâu ra** (câu mẫu, người gõ, tự điền theo ngữ
--      cảnh, tính ra, hay AI gợi ý). Thiếu cái này thì sau không phân biệt được
--      "bác sĩ viết thế" với "máy điền sẵn mà không ai đọc".
--
-- CHƯA ĐIỀN RUỘT. Nội dung từng mẫu (mục nào, ô nào) phòng khám sẽ đưa sau. Ở
-- đây seed **khung rỗng** cho cả 18 mẫu, đủ ba mục mà mẫu nào cũng có. Điền ruột
-- sau là sửa DỮ LIỆU, không phải sửa code — đó là toàn bộ ý nghĩa của việc này.
--
-- Chạy lại được: IF NOT EXISTS / ON CONFLICT.

-- ── Bản thiết kế của một biểu mẫu, theo phiên bản ──────────────────────────
CREATE TABLE IF NOT EXISTS public.form_definition (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    form_id      text NOT NULL,
    version      integer NOT NULL,
    ten          text NOT NULL,
    nhom         text NOT NULL DEFAULT '',
    -- Khung: [{ma, ten, block: [{ma, ten, kieu, mac_dinh, goi_y}]}]
    -- `kieu`: text · so · ngay · chon · nhieu_chon · doan_van · cap_do (đo
    -- trái/phải) · tinh_ra · anh. Một engine hiểu tất, không thêm engine mới.
    khung        jsonb NOT NULL DEFAULT '[]'::jsonb,
    trang_thai   text NOT NULL DEFAULT 'DRAFT',
    tao_boi      uuid REFERENCES public.staff(id),
    tao_luc      timestamptz NOT NULL DEFAULT now(),
    xuat_ban_boi uuid REFERENCES public.staff(id),
    xuat_ban_luc timestamptz,
    PRIMARY KEY (clinic_id, form_id, version),
    CONSTRAINT form_definition_trang_thai
        CHECK (trang_thai IN ('DRAFT', 'PUBLISHED', 'RETIRED')),
    CONSTRAINT form_definition_version_duong CHECK (version > 0),
    -- Đã xuất bản thì phải biết LÚC NÀO. Ai xuất bản có thể trống, vì khung
    -- rỗng ban đầu do hệ thống dựng — ghi tên một người vào đó là mạo danh
    -- rằng đã có người duyệt nội dung.
    CONSTRAINT form_definition_xuat_ban_du
        CHECK (trang_thai <> 'PUBLISHED' OR xuat_ban_luc IS NOT NULL)
);

-- Mỗi biểu mẫu chỉ có MỘT bản đang dùng. Ép ở Postgres: "nhớ tắt bản cũ trước
-- khi bật bản mới" là loại luật người ta quên đúng vào hôm bận nhất.
CREATE UNIQUE INDEX IF NOT EXISTS uq_form_definition_dang_dung
    ON public.form_definition (clinic_id, form_id)
    WHERE trang_thai = 'PUBLISHED';

-- ── Một lần điền biểu mẫu ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.form_instance (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL,
    -- Điền cho chỉ định nào. Mỗi chỉ định một phiếu.
    service_order_id uuid NOT NULL,
    form_id          text NOT NULL,
    version          integer NOT NULL,

    trang_thai       text NOT NULL DEFAULT 'DRAFT',
    -- {ma_o: {gia_tri: ..., nguon: 'TEMPLATE_DEFAULT'|'USER'|...}}
    du_lieu          jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Tăng mỗi lần lưu: màn đang mở mà người khác vừa lưu thì biết mà không đè.
    revision         integer NOT NULL DEFAULT 0,

    -- Người GÕ. Điều dưỡng nhập thay bác sĩ là chuyện bình thường ở phòng khám.
    nhap_boi         uuid REFERENCES public.staff(id),
    -- Người THỰC HIỆN dịch vụ. Đây là dữ liệu nghiệp vụ, không phải nhật ký.
    thuc_hien_boi    uuid REFERENCES public.staff(id),
    hoan_tat_boi     uuid REFERENCES public.staff(id),
    hoan_tat_luc     timestamptz,
    tao_luc          timestamptz NOT NULL DEFAULT now(),
    sua_luc          timestamptz NOT NULL DEFAULT now(),

    FOREIGN KEY (clinic_id, form_id, version)
        REFERENCES public.form_definition(clinic_id, form_id, version),
    CONSTRAINT form_instance_trang_thai
        CHECK (trang_thai IN ('DRAFT', 'READY')),
    CONSTRAINT form_instance_hoan_tat_du
        CHECK ((trang_thai <> 'READY')
               OR (hoan_tat_boi IS NOT NULL AND hoan_tat_luc IS NOT NULL))
);

-- Một chỉ định một phiếu: bấm hai lần không tạo hai phiếu kết quả.
CREATE UNIQUE INDEX IF NOT EXISTS uq_form_instance_chi_dinh
    ON public.form_instance (clinic_id, service_order_id, form_id);
CREATE INDEX IF NOT EXISTS ix_form_instance_chua_xong
    ON public.form_instance (clinic_id, sua_luc)
    WHERE trang_thai = 'DRAFT';

ALTER TABLE public.form_definition ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_instance ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS form_definition_select_own_clinic ON public.form_definition;
CREATE POLICY form_definition_select_own_clinic ON public.form_definition
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
-- Phiếu đã điền có chữ lâm sàng: chỉ đọc qua backend (service_role), không mở
-- cho `authenticated` đọc thẳng như danh mục.
DROP POLICY IF EXISTS form_instance_select_own_clinic ON public.form_instance;
CREATE POLICY form_instance_select_own_clinic ON public.form_instance
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT ON public.form_definition TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.form_definition TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.form_instance TO service_role;

-- ── Khung rỗng cho 18 mẫu kết quả ──────────────────────────────────────────
-- Ba mục mà mẫu nào cũng có. Ruột từng mẫu phòng khám đưa sau; lúc ấy chỉ thêm
-- block vào `khung`, không sửa dòng code nào.
INSERT INTO public.form_definition
    (clinic_id, form_id, version, ten, nhom, khung, trang_thai,
     xuat_ban_boi, xuat_ban_luc)
SELECT m.clinic_id,
       'KQ_' || m.ma,
       1,
       m.ten,
       m.nhom,
       jsonb_build_array(
           jsonb_build_object(
               'ma', 'mo_ta', 'ten', 'Mô tả',
               'block', jsonb_build_array(jsonb_build_object(
                   'ma', 'mo_ta_chi_tiet', 'ten', 'Mô tả chi tiết',
                   'kieu', 'doan_van', 'mac_dinh', '',
                   'cho_trong', true))),
           jsonb_build_object(
               'ma', 'ket_luan', 'ten', 'Kết luận',
               'block', jsonb_build_array(jsonb_build_object(
                   'ma', 'ket_luan', 'ten', 'Kết luận',
                   'kieu', 'doan_van', 'mac_dinh', '',
                   'cho_trong', true))),
           jsonb_build_object(
               'ma', 'de_nghi', 'ten', 'Đề nghị',
               'block', jsonb_build_array(jsonb_build_object(
                   'ma', 'de_nghi', 'ten', 'Đề nghị / lời dặn',
                   'kieu', 'doan_van', 'mac_dinh', '',
                   'cho_trong', true)))
       ),
       'PUBLISHED',
       NULL,
       now()
  FROM public.ket_qua_mau m
 WHERE m.active
ON CONFLICT (clinic_id, form_id, version) DO NOTHING;

-- ── Quyền sửa và xuất bản biểu mẫu ────────────────────────────────────────
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('ket_qua', 'Kết quả cận lâm sàng', 'result',
     'Điền và hoàn tất biểu mẫu kết quả cho dịch vụ đã làm')
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, module = EXCLUDED.module, mo_ta = EXCLUDED.mo_ta;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES
    ('catalogue.form_template.edit', 'Sửa nội dung biểu mẫu',
     'danh_muc', 'catalogue', 'clinical', false),
    ('catalogue.form_template.publish', 'Xuất bản phiên bản biểu mẫu',
     'danh_muc', 'catalogue', 'clinical', false),
    ('result.form.fill', 'Điền và hoàn tất biểu mẫu kết quả',
     'ket_qua', 'result', 'clinical', false)
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, work_pack = EXCLUDED.work_pack,
        module = EXCLUDED.module, rui_ro = EXCLUDED.rui_ro;

-- Ai đang làm dịch vụ thì điền kết quả: bác sĩ, bác sĩ siêu âm, điều dưỡng SA.
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, 'result.form.fill', 'ket_qua', m.role,
       'Chép từ preset khi thêm khối Kết quả (23/09/2026)'
  FROM public.clinic_membership m
 WHERE m.is_active
   AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'TKYK',
                  'MANAGEMENT')
ON CONFLICT DO NOTHING;

INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, c.ma, 'danh_muc', m.role,
       'Chép từ preset khi thêm quyền biểu mẫu (23/09/2026)'
  FROM public.clinic_membership m
  JOIN public.capability c ON c.ma IN ('catalogue.form_template.edit',
                                       'catalogue.form_template.publish')
 WHERE m.is_active AND m.role = 'MANAGEMENT'
ON CONFLICT DO NOTHING;

COMMENT ON TABLE public.form_definition IS
    'Bản thiết kế biểu mẫu theo phiên bản. Sửa v4→v5 không đổi hồ sơ cũ; bản PUBLISHED không sửa tại chỗ.';
COMMENT ON TABLE public.form_instance IS
    'Một lần điền biểu mẫu cho một chỉ định. Hoàn tất = xác nhận toàn bộ nội dung hiện tại, kể cả câu mẫu.';
COMMENT ON COLUMN public.form_instance.nhap_boi IS
    'Người GÕ — khác người thực hiện dịch vụ (điều dưỡng nhập thay bác sĩ).';
COMMENT ON COLUMN public.form_instance.thuc_hien_boi IS
    'Người THỰC HIỆN dịch vụ — dữ liệu nghiệp vụ, không phải nhật ký.';
