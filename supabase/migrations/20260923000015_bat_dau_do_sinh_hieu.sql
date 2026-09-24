-- Bắt đầu đo sinh hiệu — một bước thật, không phải một cái nút gọi (23/09/2026).
--
-- Tuyền chốt: `Gọi vào → Bắt đầu` là hai bước cho một việc; bỏ [Gọi vào đo],
-- chỉ còn `Chờ đo → [Bắt đầu] → Đang đo → [Lưu sinh hiệu] → Đã đo`.
--
-- Trước migration này KHÔNG CÓ trạng thái "đang đo". Màn hình tự suy ra nó từ
-- `goi_do_luc` — tức "đã gọi" bị đọc thành "đã bắt đầu đo", hai chuyện khác
-- nhau. Giờ nó là một trạng thái có thật, có người, có giờ.
--
--     vitals_status:  pending → in_progress → recorded
--
-- MỌI CHỖ ĐỌC ĐỀU SO `= 'recorded'` (kiểm 23/09: định tuyến, cổng xếp phòng,
-- tiến độ lượt, màn khách hàng). Nên `in_progress` được đối xử đúng như "chưa
-- đo" ở mọi cổng, không chỗ nào phải sửa theo.
--
-- `pending → recorded` VẪN ĐƯỢC PHÉP: lưu sinh hiệu mà chưa ai bấm [Bắt đầu]
-- không bị chặn. Hệ thống mở, và [Bắt đầu] là mốc để đo thời gian chờ, không
-- phải cửa khoá. Khi ấy `vitals_started_*` để trống — không ai bấm thì không
-- bịa ra một người đã bấm.
--
-- `goi_do_luc` / `goi_do_boi` GIỮ NGUYÊN CỘT VÀ DỮ LIỆU CŨ, chỉ thôi dùng làm
-- trạng thái. KHÔNG chép sang `vitals_started_*`: "đã gọi" không chứng minh
-- "đã bắt đầu đo".
--
-- KHÔNG có `vitals.corrected`. Mỗi lần lưu sinh hiệu vẫn THÊM một dòng
-- `vital_measurement` như trước, dòng cũ giữ nguyên — đo lại sau năm phút là
-- chuyện bình thường, không phải một lần sửa sai. Phân biệt "đo lại" với "gõ
-- nhầm" là câu hỏi chuyên môn còn MỞ, không tự trả lời ở đây.

ALTER TABLE public.encounter_flow
    ADD COLUMN IF NOT EXISTS vitals_started_at timestamptz,
    ADD COLUMN IF NOT EXISTS vitals_started_by uuid REFERENCES public.staff(id);

-- Thêm-nếu-chưa-có chứ không "DROP rồi ADD" cho mọi ràng buộc: migration từ
-- 20260730 phải chạy lại được hai lần.
DO $$
BEGIN
    -- Nới CHECK cũ để nhận trạng thái mới. Đây là chỗ DUY NHẤT phải DROP: tên
    -- ràng buộc giữ nguyên, chỉ tập giá trị rộng ra.
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_vitals_status'
           AND conrelid = 'public.encounter_flow'::regclass
           AND pg_get_constraintdef(oid) NOT LIKE '%in_progress%'
    ) THEN
        ALTER TABLE public.encounter_flow
            DROP CONSTRAINT encounter_flow_vitals_status;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_vitals_status'
           AND conrelid = 'public.encounter_flow'::regclass
    ) THEN
        ALTER TABLE public.encounter_flow
            ADD CONSTRAINT encounter_flow_vitals_status
            CHECK (vitals_status IN ('pending', 'in_progress', 'recorded'));
    END IF;

    -- Có người thì có giờ, và ngược lại.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_vitals_started_cap'
           AND conrelid = 'public.encounter_flow'::regclass
    ) THEN
        ALTER TABLE public.encounter_flow
            ADD CONSTRAINT encounter_flow_vitals_started_cap
            CHECK ((vitals_started_at IS NULL) = (vitals_started_by IS NULL));
    END IF;

    -- "Đang đo" thì phải biết ai bắt đầu, lúc nào. Không có trạng thái đang đo
    -- mà không có người đo.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'encounter_flow_dang_do_co_nguoi'
           AND conrelid = 'public.encounter_flow'::regclass
    ) THEN
        ALTER TABLE public.encounter_flow
            ADD CONSTRAINT encounter_flow_dang_do_co_nguoi
            CHECK (vitals_status <> 'in_progress' OR vitals_started_at IS NOT NULL);
    END IF;
END $$;

COMMENT ON COLUMN public.encounter_flow.vitals_started_at IS
    'Lúc bấm [Bắt đầu] đo sinh hiệu. Trống nếu lưu thẳng mà không ai bấm Bắt đầu.';
COMMENT ON COLUMN public.encounter_flow.vitals_started_by IS
    'Người bấm [Bắt đầu]. Không suy ra từ goi_do_boi — "đã gọi" không phải "đã đo".';
COMMENT ON COLUMN public.encounter_flow.goi_do_luc IS
    'DỮ LIỆU CŨ (trước 23/09/2026). Giữ để đọc lịch sử; không còn dùng làm trạng thái.';
