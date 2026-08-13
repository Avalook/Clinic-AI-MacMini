-- Cuộc gọi CSKH phải ghi được KẾT QUẢ, không chỉ ghi "đã gọi".
--
-- Màn /cskh-tasks có ba nút kết quả — "Đã liên hệ", "Chưa nghe máy", "Cần bác
-- sĩ hỗ trợ" — và gửi lên một trường `result`. Không ai nhận trường ấy:
-- `app/api/cskh-followup/route.ts` khai một interface chỉ có
-- `clinic_patient_id` và `note`, nên `result` rơi ngay ở cửa. Cả ba nút ghi ra
-- ĐÚNG MỘT dòng giống hệt nhau, với `cskh_status = 'Đã gọi nhắc tái khám'`.
--
-- Đây không phải thiếu dữ liệu, là DỮ LIỆU SAI. Hôm sau người khác mở lên thấy
-- "đã gọi hôm qua" rồi bỏ qua, trong khi thực tế chuông đổ mà không ai bắt máy.
--
-- Không nhét kết quả vào `cskh_status` (text tự do) vì chỗ đó đang giữ nghĩa
-- khác và không có gì canh giá trị. Một cột riêng, có CHECK, thì bốn giá trị
-- này là bốn giá trị — không phải bốn cách gõ.

ALTER TABLE public.cskh_log
    ADD COLUMN IF NOT EXISTS ket_qua text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.cskh_log'::regclass
           AND conname = 'cskh_log_ket_qua_check'
    ) THEN
        ALTER TABLE public.cskh_log
            ADD CONSTRAINT cskh_log_ket_qua_check
            CHECK (ket_qua IS NULL OR ket_qua = ANY (ARRAY[
                'DA_LIEN_HE',      -- bắt máy, đã nói chuyện được
                'CHUA_NGHE_MAY',   -- gọi mà không ai bắt
                'CAN_BAC_SI',      -- cần bác sĩ hỗ trợ mới trả lời được
                'TU_CHOI'          -- bắt máy nhưng từ chối quay lại
            ]));
    END IF;
END $$;

COMMENT ON COLUMN public.cskh_log.ket_qua IS
    'Kết quả cuộc gọi CSKH. NULL = dòng cũ, ghi trước 20260807000002 khi hệ '
    'chưa có chỗ lưu kết quả — KHÔNG suy ra là đã liên hệ được.';

-- LƯỢT GỌI THỨ MẤY. Luật phòng khám: mỗi hẹn tái khám gọi HAI lần — lần một
-- trước hẹn 5–7 ngày, lần hai vào sáng ngày hẹn. Không có cột này thì mười
-- cuộc gọi ra mười dòng giống hệt nhau, và câu "ai đã gọi lần một, ai còn
-- thiếu lần hai" không trả lời được.
ALTER TABLE public.cskh_log
    ADD COLUMN IF NOT EXISTS luot_goi smallint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.cskh_log'::regclass
           AND conname = 'cskh_log_luot_goi_check'
    ) THEN
        ALTER TABLE public.cskh_log
            ADD CONSTRAINT cskh_log_luot_goi_check
            CHECK (luot_goi IS NULL OR luot_goi BETWEEN 1 AND 9);
    END IF;
END $$;

COMMENT ON COLUMN public.cskh_log.luot_goi IS
    'Cuộc gọi thứ mấy của cùng một hẹn tái khám: 1 = trước hẹn 5–7 ngày, '
    '2 = sáng ngày hẹn. NULL = cuộc gọi ngoài luật hai lần.';

-- Tra "hôm nay ai đã được gọi lượt mấy" là câu hỏi của mọi buổi sáng.
CREATE INDEX IF NOT EXISTS idx_cskh_log_ngay_luot
    ON public.cskh_log (clinic_id, work_date, luot_goi);
