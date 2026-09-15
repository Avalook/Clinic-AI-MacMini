-- Check-in LƯU BẰNG CHỨNG XÁC MINH NGƯỜI BỆNH.
--
-- LUẬT (CONTEXT v1.0 + Tuyền chốt danh mục 15/09/2026): lễ tân kiểm tra đúng
-- khách rồi mới check-in; phải lưu được AI xác minh, LÚC NÀO, BẰNG CÁCH NÀO, và
-- dịch vụ/bác sĩ hôm nay lúc xác minh. Ba cách:
--   THONG_TIN_CA_NHAN   — đối chiếu thông tin cá nhân (tên, năm sinh, SĐT)
--   GIAY_TO_CO_ANH      — kiểm giấy tờ có ảnh
--   NGUOI_NHA_XAC_NHAN  — người nhà xác nhận
--
-- TRƯỚC BẢN NÀY check-in chỉ lưu `checked_in_by` + `checked_in_at`; bước
-- "Xác minh người bệnh & dịch vụ hôm nay" (LUOTKHAM-02) là một work item bấm
-- bắt đầu/xong không mang dữ liệu gì — không trả lời được "đã kiểm cái gì".
--
-- LỚP BẢO VỆ: service (booking_service) BẮT BUỘC chọn cách khi check-in. DB ép
-- bộ bằng chứng ĐỦ hoặc KHÔNG CÓ (không có nửa bộ), và cách phải thuộc danh mục.
-- DB KHÔNG ép "check-in thì phải có bằng chứng": lượt cũ trước bản này và lượt
-- do điều dưỡng/siêu âm mở trước quầy không có — ép sẽ làm hỏng chúng.

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS xac_minh_cach       text,
    ADD COLUMN IF NOT EXISTS xac_minh_boi        uuid REFERENCES public.staff(id),
    ADD COLUMN IF NOT EXISTS xac_minh_luc        timestamptz,
    ADD COLUMN IF NOT EXISTS xac_minh_dich_vu_id uuid REFERENCES public.service_type(id),
    ADD COLUMN IF NOT EXISTS xac_minh_bac_si_id  uuid REFERENCES public.staff(id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.visit'::regclass
                      AND conname = 'visit_xac_minh_cach_hop_le') THEN
        ALTER TABLE public.visit
            ADD CONSTRAINT visit_xac_minh_cach_hop_le
            CHECK (xac_minh_cach IS NULL OR xac_minh_cach IN
                   ('THONG_TIN_CA_NHAN', 'GIAY_TO_CO_ANH', 'NGUOI_NHA_XAC_NHAN'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.visit'::regclass
                      AND conname = 'visit_xac_minh_du_bo') THEN
        ALTER TABLE public.visit
            ADD CONSTRAINT visit_xac_minh_du_bo
            CHECK ((xac_minh_cach IS NULL) = (xac_minh_boi IS NULL)
               AND (xac_minh_cach IS NULL) = (xac_minh_luc IS NULL));
    END IF;
END $$;

COMMENT ON COLUMN public.visit.xac_minh_cach IS
    'Cách lễ tân xác minh đúng người bệnh lúc check-in gần nhất: '
    'THONG_TIN_CA_NHAN / GIAY_TO_CO_ANH / NGUOI_NHA_XAC_NHAN. Mỗi lần check-in '
    'còn ghi vào event_log appointment.checked_in (20260915000009).';
