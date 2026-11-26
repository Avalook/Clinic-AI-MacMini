-- PR B (26/11/2026, kế hoạch đơn vị mẹ/con mục 7, 12, 13): kê đơn không còn tự
-- thêm thuốc lạ vào danh mục (bỏ đoạn INSERT trong `dinh_chinh_don._ma_kho`).
-- Bác sĩ gõ tên không có trong danh mục → bấm "Nhờ kho thêm thuốc": ghi MỘT yêu
-- cầu ở đây, chuông cho người nhận việc kho; người kho thêm thuốc ở Danh mục rồi
-- bấm "Xong" (bấm lại "Mở lại" được — hoàn tác).
--
-- Bảng KHÔNG có khoá ngoại tới `drug_catalog`: yêu cầu là chữ người gõ, không
-- phải "thuốc đã được dùng" (nút Xoá thuốc của danh mục đếm mọi khoá ngoại).
-- Chạy lại nhiều lần được: IF NOT EXISTS / DROP … IF EXISTS / ON CONFLICT.

CREATE TABLE IF NOT EXISTS public.thuoc_nho_kho (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id  uuid REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    ten_go       text NOT NULL,
    ghi_chu      text,
    -- Lượt đang kê lúc nhờ (nếu có) — chỉ để người kho biết khách nào đang chờ.
    visit_id     uuid,
    tao_boi      uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc      timestamptz NOT NULL DEFAULT now(),
    xong_boi     uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    xong_luc     timestamptz,
    CONSTRAINT thuoc_nho_kho_ten_go CHECK (length(btrim(ten_go)) BETWEEN 1 AND 200),
    CONSTRAINT thuoc_nho_kho_ghi_chu CHECK (ghi_chu IS NULL OR length(ghi_chu) <= 500),
    CONSTRAINT thuoc_nho_kho_xong_day_du CHECK ((xong_luc IS NULL) = (xong_boi IS NULL))
);

-- Hai người nhờ cùng một tên lúc yêu cầu cũ còn mở = MỘT yêu cầu (ép ở DB).
CREATE UNIQUE INDEX IF NOT EXISTS uq_thuoc_nho_kho_dang_mo
    ON public.thuoc_nho_kho (clinic_id, lower(btrim(ten_go)))
    WHERE xong_luc IS NULL;

CREATE INDEX IF NOT EXISTS thuoc_nho_kho_theo_luc
    ON public.thuoc_nho_kho (clinic_id, tao_luc DESC);

ALTER TABLE public.thuoc_nho_kho ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS thuoc_nho_kho_select_own_clinic ON public.thuoc_nho_kho;
CREATE POLICY thuoc_nho_kho_select_own_clinic
    ON public.thuoc_nho_kho FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT, INSERT, UPDATE ON public.thuoc_nho_kho TO service_role;
GRANT SELECT ON public.thuoc_nho_kho TO authenticated;

-- Người nhận chuông mặc định: như chuông hạn lô — quản lý chỉnh ở màn Dây nối chuông.
INSERT INTO public.day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh, bat)
SELECT id, 'pharmacy.drug_requested', ARRAY['PHARMACIST','MANAGEMENT'], false, true
  FROM public.clinic
ON CONFLICT (clinic_id, su_kien) DO NOTHING;

-- Màn Kho thuốc làm mới tức thời (kênh LISTEN/NOTIFY của mình).
DROP TRIGGER IF EXISTS trg_notify_thuoc_nho_kho ON public.thuoc_nho_kho;
CREATE TRIGGER trg_notify_thuoc_nho_kho
    AFTER INSERT OR UPDATE OR DELETE ON public.thuoc_nho_kho
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
