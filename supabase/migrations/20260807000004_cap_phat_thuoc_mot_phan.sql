-- "Mua / không mua / mua một phần" — ba tình huống thật, một mô hình.
--
-- Luật Quang mô tả: bệnh nhân có thể mua thuốc, không mua, hoặc mua một phần.
-- Hôm nay không ghi lại được tình huống nào trong ba: bảng `prescription` chỉ
-- có `quantity` kiểu TEXT (bác sĩ gõ tay, vd "30 viên") và KHÔNG có cột nào
-- lưu ĐÃ CẤP BAO NHIÊU. Bệnh nhân lấy 5 trong 10 viên thì hệ thống không biết,
-- không trừ kho được, không đối soát tiền được, không tra lại được ngày sau.
--
-- BA CỘT, KHÔNG PHẢI MỘT CỜ:
--   quantity_num   — số lượng KÊ, dạng số. Suy từ `quantity` khi đọc được.
--   dispensed_qty  — số lượng ĐÃ CẤP. Cộng dồn qua từng lần cấp.
--   refusal_reason / closed_at — khách nói thôi. "Lấy 5 rồi thôi" khác "chưa
--   cấp nốt", và hai thứ đó phải phân biệt được, nếu không dược sĩ sẽ đi hỏi
--   lại một người đã về.
--
-- TRẠNG THÁI LÀ CỘT SINH RA, KHÔNG PHẢI CỘT GHI TAY. Một cột `status` ghi tay
-- là một cột sẽ lệch với các con số bên cạnh nó — kiểu lỗi đã gặp hai lần
-- trong repo này. Ở đây trạng thái được TÍNH từ chính hai con số ấy, nên không
-- có trạng thái nào tồn tại mà không đúng với số liệu.

-- ---------------------------------------------------------------------------
-- 1. Đọc số lượng từ câu bác sĩ gõ
-- ---------------------------------------------------------------------------
-- Bác sĩ gõ tự do: "30 viên", "2 vỉ", "1 hộp". Hai hàm này lấy phần số và phần
-- đơn vị, và TRẢ NULL KHI KHÔNG CHẮC — "1/2 viên", "uống đến hết" thì không
-- đoán. NULL nghĩa là "chưa biết, hỏi dược sĩ", và mọi ràng buộc bên dưới đều
-- bỏ qua khi số lượng kê chưa biết. Đoán bừa ở đây sẽ thành trừ kho sai.

-- NHÓM BẮT PHẢI BAO CẢ CON SỐ.
--
-- Bản đầu viết `regexp_match(x, '^[0-9]+([.,][0-9]+)?')` rồi lấy `[1]`.
-- `regexp_match` trả về CÁC NHÓM BẮT, không phải cả khớp — nên `[1]` là nhóm
-- phần thập phân. Kết quả đo được: "30 viên" ra NULL, và "2,5 ml" ra 0.5. Một
-- hàm đọc số lượng thuốc trả 0.5 thay vì 2.5 là một lần trừ kho sai.
-- Nay nhóm ngoài bao cả con số, nhóm trong đổi thành không-bắt (?:...).
CREATE OR REPLACE FUNCTION public.so_luong_tu_van_ban(p_text text)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $function$
    SELECT CASE
        WHEN btrim(coalesce(p_text, '')) ~ '^[0-9]+(?:[.,][0-9]+)?\s*(?:$|[^0-9/.,].*$)'
        -- `nullif(..., 0)`: "0 viên" không phải một số lượng, nó là một câu
        -- gõ nhầm. Trả 0 sẽ đụng ngay ràng buộc `quantity_num > 0` và làm
        -- ĐỔ CẢ MIGRATION lúc điền dữ liệu cũ — một dòng gõ nhầm từ nhiều
        -- tháng trước không được phép chặn một lần nâng cấp lược đồ.
        THEN nullif(
                 replace(
                     (regexp_match(btrim(p_text),
                                   '^([0-9]+(?:[.,][0-9]+)?)'))[1],
                     ',', '.')::numeric,
                 0)
        ELSE NULL
    END
$function$;

COMMENT ON FUNCTION public.so_luong_tu_van_ban(text) IS
    'Số lượng kê từ câu bác sĩ gõ ("30 viên" → 30). NULL khi không chắc — '
    '"1/2 viên" hay "uống đến hết" thì để dược sĩ nhập, không đoán.';

-- Chỉ trả đơn vị KHI ĐÃ ĐỌC ĐƯỢC SỐ. Bản đầu trả "/2 viên" cho "1/2 viên" —
-- một đơn vị vô nghĩa đi kèm một số lượng NULL, tức là nói dối một nửa.
CREATE OR REPLACE FUNCTION public.don_vi_tu_van_ban(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $function$
    SELECT CASE
        WHEN public.so_luong_tu_van_ban(p_text) IS NULL THEN NULL
        ELSE nullif(
            btrim(regexp_replace(btrim(coalesce(p_text, '')),
                                 '^[0-9]+(?:[.,][0-9]+)?', '')),
            '')
    END
$function$;

COMMENT ON FUNCTION public.don_vi_tu_van_ban(text) IS
    'Đơn vị từ câu bác sĩ gõ ("30 viên" → "viên"). NULL khi không có phần chữ.';

-- ---------------------------------------------------------------------------
-- 2. Cột cấp phát trên đơn thuốc
-- ---------------------------------------------------------------------------
ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS quantity_num          numeric,
    ADD COLUMN IF NOT EXISTS unit                  text,
    ADD COLUMN IF NOT EXISTS dispensed_qty         numeric NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dispensed_at          timestamptz,
    ADD COLUMN IF NOT EXISTS dispensed_by_staff_id uuid,
    ADD COLUMN IF NOT EXISTS refusal_reason        text,
    ADD COLUMN IF NOT EXISTS closed_at             timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.prescription'::regclass
           AND conname = 'prescription_dispensed_by_fkey'
    ) THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_dispensed_by_fkey
            FOREIGN KEY (dispensed_by_staff_id) REFERENCES public.staff (id);
    END IF;
END $$;

-- Điền cho những dòng đã có. Prod hôm nay 0 dòng, nhưng migration phải chạy
-- đúng trên mọi database — kể cả bản khôi phục từ sao lưu cũ.
UPDATE public.prescription
   SET quantity_num = public.so_luong_tu_van_ban(quantity),
       unit         = public.don_vi_tu_van_ban(quantity)
 WHERE quantity_num IS NULL
   AND quantity IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Ràng buộc — những điều KHÔNG được phép đúng cùng lúc
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'prescription_dispensed_qty_check') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_dispensed_qty_check
            CHECK (dispensed_qty >= 0);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'prescription_quantity_num_check') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_quantity_num_check
            CHECK (quantity_num IS NULL OR quantity_num > 0);
    END IF;

    -- KHÔNG CẤP QUÁ SỐ ĐÃ KÊ. Chỉ canh được khi biết số kê; khi `quantity_num`
    -- còn NULL thì dược sĩ là người canh, và câu từ chối nằm ở service.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'prescription_khong_cap_qua_ke') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_khong_cap_qua_ke
            CHECK (quantity_num IS NULL OR dispensed_qty <= quantity_num);
    END IF;

    -- ĐÃ CẤP THÌ PHẢI BIẾT AI CẤP VÀ LÚC NÀO — và ngược lại. Cùng dạng ràng
    -- buộc "hai chiều" với work_item_finished_when_terminal của workflow
    -- kernel: nó chặn được cả hai kiểu sai, không chỉ một.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.prescription'::regclass
                      AND conname = 'prescription_cap_thi_co_dau_vet') THEN
        ALTER TABLE public.prescription
            ADD CONSTRAINT prescription_cap_thi_co_dau_vet
            CHECK ((dispensed_qty > 0)
                   = (dispensed_at IS NOT NULL
                      AND dispensed_by_staff_id IS NOT NULL));
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. Trạng thái cấp phát — SINH RA từ số liệu, không ghi tay
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'prescription'
           AND column_name = 'dispense_status'
    ) THEN
        ALTER TABLE public.prescription
            ADD COLUMN dispense_status text
            GENERATED ALWAYS AS (
                CASE
                    WHEN dispensed_qty = 0 AND refusal_reason IS NOT NULL
                        THEN 'TU_CHOI'
                    WHEN dispensed_qty = 0
                        THEN 'CHUA_CAP'
                    WHEN quantity_num IS NOT NULL
                         AND dispensed_qty >= quantity_num
                        THEN 'CAP_DU'
                    ELSE 'CAP_MOT_PHAN'
                END
            ) STORED;
    END IF;
END $$;

COMMENT ON COLUMN public.prescription.dispense_status IS
    'CHUA_CAP / CAP_MOT_PHAN / CAP_DU / TU_CHOI — TÍNH từ dispensed_qty, '
    'quantity_num và refusal_reason. Cột sinh ra, không ghi tay: một cột trạng '
    'thái ghi tay là một cột sẽ lệch với con số bên cạnh (20260807000004).';

COMMENT ON COLUMN public.prescription.closed_at IS
    'Dược sĩ chốt "không cấp thêm nữa". Phân biệt "lấy 5 rồi thôi" với "chưa '
    'cấp nốt" — thiếu nó thì dược sĩ đi hỏi lại một người đã ra về.';

-- Hàng đợi của dược sĩ là "đơn chưa chốt", tra theo phòng khám.
CREATE INDEX IF NOT EXISTS idx_prescription_hang_doi
    ON public.prescription (clinic_id, closed_at, created_at DESC);
