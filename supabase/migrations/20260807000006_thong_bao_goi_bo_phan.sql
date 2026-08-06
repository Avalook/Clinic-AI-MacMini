-- Trưởng ca GỌI được bộ phận liên quan, và cuộc gọi ấy để lại dấu vết.
--
-- Luật Quang mô tả: khi có chuyện bất thường (chờ quá lâu, phòng quá tải) thì
-- trưởng ca thấy cảnh báo, bấm nút "gọi", và người/bộ phận liên quan nhận được
-- thông báo màu ĐỎ.
--
-- Nửa "NHÌN THẤY" đã dựng thật: ngưỡng cấu hình được (`dispatch_threshold`),
-- cảnh báo tính bằng hàm thuần `build_alerts()`, có màn /truong-ca/canh-bao,
-- có realtime.
--
-- Nửa "GỌI NGƯỜI" KHÔNG TỒN TẠI Ở BẤT KỲ LỚP NÀO. Không nút, không endpoint,
-- không bảng nào lưu thông báo, không đường nào để một bộ phận khác nhận được
-- gì. Trưởng ca nhìn thấy phòng đang tắc rồi phải rời màn hình, cầm điện thoại
-- hoặc đi bộ sang.
--
-- Và thứ duy nhất trông giống thông báo đỏ trong sản phẩm là ba dòng VIẾT CỨNG
-- trong GlobalHeader (đã gỡ hôm nay, 20260807 — commit "Chuông thôi nói dối").
--
-- BẢNG NÀY LƯU CUỘC GỌI, KHÔNG PHẢI LƯU CẢNH BÁO.
--
-- Cảnh báo được TÍNH LẠI mỗi lần đọc từ trạng thái hàng đợi — nó đúng như vậy,
-- và không nên đóng băng vào một bảng. Cái cần lưu là hành động của con người:
-- ai đã gọi ai, lúc nào, vì việc gì, bên kia đã nhận chưa, đã xử lý chưa. Thiếu
-- nó thì không đo được thời gian phản hồi và không đối soát được cuối ca.

CREATE TABLE IF NOT EXISTS public.thong_bao (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           uuid NOT NULL REFERENCES public.clinic (id)
                             ON DELETE RESTRICT,

    -- NGƯỜI NHẬN: theo VAI (cả bộ phận) hoặc theo MỘT NGƯỜI. Ít nhất một.
    -- Gọi theo vai là mặc định — lúc phòng tắc thì cần ai đó ở đó nhận, không
    -- cần đúng một người đang bận tay.
    vai_nhan            text,
    nguoi_nhan_staff_id uuid REFERENCES public.staff (id) ON DELETE SET NULL,

    muc_do              text NOT NULL DEFAULT 'KHAN',
    tieu_de             text NOT NULL,
    noi_dung            text NOT NULL,

    -- Nguồn sinh ra nó, để tra ngược và để chống gọi trùng.
    nguon               text NOT NULL,
    nguon_id            text,
    duong_dan           text,

    nguoi_goi_staff_id  uuid NOT NULL REFERENCES public.staff (id)
                             ON DELETE RESTRICT,
    tao_luc             timestamptz NOT NULL DEFAULT now(),
    da_doc_luc          timestamptz,
    da_xu_ly_luc        timestamptz,
    da_xu_ly_boi        uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    ghi_chu_xu_ly       text,

    CONSTRAINT thong_bao_co_nguoi_nhan
        CHECK (vai_nhan IS NOT NULL OR nguoi_nhan_staff_id IS NOT NULL),
    CONSTRAINT thong_bao_muc_do_check
        CHECK (muc_do IN ('KHAN', 'THUONG')),
    -- ĐÃ XỬ LÝ THÌ PHẢI BIẾT AI XỬ LÝ — và ngược lại. Cùng dạng ràng buộc hai
    -- chiều với các bảng khác trong dự án: nó chặn được cả hai kiểu sai.
    CONSTRAINT thong_bao_xu_ly_co_nguoi
        CHECK ((da_xu_ly_luc IS NOT NULL) = (da_xu_ly_boi IS NOT NULL))
);

-- CHỐNG GỌI TRÙNG. Trưởng ca bấm nút mười lần trong lúc sốt ruột thì bên kia
-- nhận đúng MỘT thông báo, không phải mười. Chỉ chặn khi cái cũ CHƯA ĐƯỢC XỬ
-- LÝ — xử lý xong rồi mà việc tái diễn thì gọi lại được.
CREATE UNIQUE INDEX IF NOT EXISTS uq_thong_bao_dang_mo
    ON public.thong_bao (clinic_id, nguon, nguon_id, vai_nhan)
 WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL AND vai_nhan IS NOT NULL;

-- "Có gì cho tôi chưa" — câu hỏi chạy mỗi 20 giây ở mọi máy trong phòng khám.
CREATE INDEX IF NOT EXISTS idx_thong_bao_cho_toi
    ON public.thong_bao (clinic_id, vai_nhan, da_xu_ly_luc, tao_luc DESC);

COMMENT ON TABLE public.thong_bao IS
    'Cuộc gọi của Trưởng ca tới một bộ phận. Lưu HÀNH ĐỘNG (ai gọi ai, lúc '
    'nào, đã nhận chưa, đã xử lý chưa), không lưu cảnh báo — cảnh báo được '
    'tính lại từ hàng đợi mỗi lần đọc (20260807000006).';

COMMENT ON COLUMN public.thong_bao.muc_do IS
    'KHAN = thông báo ĐỎ, cần xử lý ngay. THUONG = nhắc việc.';

ALTER TABLE public.thong_bao ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'thong_bao'
           AND policyname = 'thong_bao_select_own_clinic'
    ) THEN
        CREATE POLICY thong_bao_select_own_clinic
            ON public.thong_bao FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

GRANT SELECT ON public.thong_bao TO authenticated;
GRANT ALL ON public.thong_bao TO service_role;
