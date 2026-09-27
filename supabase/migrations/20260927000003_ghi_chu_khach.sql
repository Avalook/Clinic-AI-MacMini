-- GHI CHÚ VỀ KHÁCH (Tuyền 27/09/2026): "khung làm việc của CSKH chưa dễ cho
-- việc ghi chú … cho bệnh nhân này — thêm vào khung bên phải của mục Quản lý
-- khách hàng. Lễ tân cũng nên có."
--
-- Khác các chỗ "ghi chú" đã có:
--   * `tuong_tac_cskh.noi_dung` — ghi KÈM một lần gọi/một mốc quầy (có loại,
--     kênh, kết quả). Ghi chú ở đây không gắn cuộc gọi nào.
--   * `nhac_viec_ca_nhan` — việc có GIỜ NHẮC, của riêng một người.
--   * ghi chú của phòng / đối tác — gắn một chỉ định.
-- Đây là sổ ghi chú CHUNG về một khách: ai ghi cũng thấy, để ca sau không bỏ
-- sót ("khách dặn chỉ gọi sau 17h", "khách ngại nhắc chuyện cũ"...).
--
-- CHỈ THÊM, không sửa nội dung. Ghi nhầm thì người ghi GỠ (ẩn khỏi danh sách,
-- dòng vẫn còn + ai gỡ, lúc nào) rồi ghi dòng mới — không viết lại quá khứ.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.ghi_chu_khach (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL REFERENCES public.patient (clinic_patient_id)
                           ON DELETE RESTRICT,
    noi_dung          text NOT NULL
                           CHECK (length(btrim(noi_dung)) BETWEEN 1 AND 2000),
    tao_boi_staff_id  uuid NOT NULL REFERENCES public.staff (id),
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    go_luc            timestamptz,
    go_boi_staff_id   uuid REFERENCES public.staff (id),
    -- Gỡ thì phải biết AI gỡ và LÚC NÀO — và ngược lại.
    CONSTRAINT ghi_chu_khach_go_co_dau_vet
        CHECK ((go_luc IS NULL) = (go_boi_staff_id IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_ghi_chu_khach_khach
    ON public.ghi_chu_khach (clinic_id, clinic_patient_id, tao_luc DESC);

COMMENT ON TABLE public.ghi_chu_khach IS
'Sổ ghi chú chung về một khách (CSKH, lễ tân…). Chỉ thêm; ghi nhầm thì người ghi gỡ (go_luc) — không sửa nội dung (27/09/2026).';

ALTER TABLE public.ghi_chu_khach ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ghi_chu_khach_select_own_clinic ON public.ghi_chu_khach;
CREATE POLICY ghi_chu_khach_select_own_clinic ON public.ghi_chu_khach
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.ghi_chu_khach TO service_role;
