-- Slice 1 (18/09/2026): rail mới là nguồn duy nhất cho
-- chỉ định → thực hiện → kết quả → vòng đọc → theo dõi → đóng lượt.
--
-- Ba thứ còn thiếu để làm được điều đó trên đúng các bảng đã có:
--
-- 1. `round_requirement.status = 'follow_up'`. Bác sĩ chuyển một yêu cầu đang
--    chờ (kết quả về muộn, dịch vụ không làm được) sang theo dõi: lượt khám
--    không phải chờ nữa, nhưng việc không biến mất — nó thành một
--    `follow_up_case` có người phụ trách và hạn. `waived_by`/`waived_reason`
--    là NGƯỜI QUYẾT và LÝ DO cho cả hai lối (miễn hoặc chuyển theo dõi).
--
-- 2. `follow_up_case` gắn được vào LƯỢT và CHỈ ĐỊNH. Bảng này có từ kernel
--    (20260730000005) nhưng chỉ nối qua `origin_work_item_id` — tức là rail cũ.
--    Nay checkout, CSKH và bác sĩ hỏi "lượt này/chỉ định này còn theo dõi gì"
--    thẳng trên rail mới.
--
-- 3. Mỗi chỉ định chỉ một việc theo dõi ĐANG MỞ, để bấm lại không sinh hai
--    việc cho CSKH gọi hai lần.
--
-- Không đụng dữ liệu cũ. Chạy lại nhiều lần được.

ALTER TABLE public.round_requirement
    ADD COLUMN IF NOT EXISTS follow_up_case_id uuid
        REFERENCES public.follow_up_case(id) ON DELETE RESTRICT;

ALTER TABLE public.round_requirement DROP CONSTRAINT IF EXISTS round_requirement_status;
ALTER TABLE public.round_requirement ADD CONSTRAINT round_requirement_status
    CHECK (status IN ('open', 'satisfied', 'waived', 'follow_up'));

ALTER TABLE public.round_requirement DROP CONSTRAINT IF EXISTS round_requirement_follow_up;
ALTER TABLE public.round_requirement ADD CONSTRAINT round_requirement_follow_up
    CHECK (status <> 'follow_up'
           OR (waived_by IS NOT NULL
               AND nullif(btrim(coalesce(waived_reason, '')), '') IS NOT NULL
               AND followup_owner IS NOT NULL
               AND followup_due IS NOT NULL
               AND follow_up_case_id IS NOT NULL));

COMMENT ON COLUMN public.round_requirement.waived_by IS
    'Bác sĩ QUYẾT yêu cầu này: miễn (status=waived) hoặc chuyển theo dõi '
    '(status=follow_up). Slice 1, 20260918000001.';
COMMENT ON COLUMN public.round_requirement.waived_reason IS
    'Lý do bác sĩ miễn hoặc chuyển theo dõi — bắt buộc cho cả hai.';

ALTER TABLE public.follow_up_case
    ADD COLUMN IF NOT EXISTS visit_id uuid,
    ADD COLUMN IF NOT EXISTS service_order_id uuid
        REFERENCES public.service_order(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS created_by uuid
        REFERENCES public.staff(id) ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'follow_up_case_visit_fk'
           AND conrelid = 'public.follow_up_case'::regclass
    ) THEN
        ALTER TABLE public.follow_up_case
            ADD CONSTRAINT follow_up_case_visit_fk FOREIGN KEY (clinic_id, visit_id)
                REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_follow_up_case_visit
    ON public.follow_up_case (clinic_id, visit_id) WHERE visit_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_follow_up_case_order_open
    ON public.follow_up_case (service_order_id)
    WHERE service_order_id IS NOT NULL AND status = 'OPEN';

COMMENT ON COLUMN public.follow_up_case.service_order_id IS
    'Chỉ định mà việc theo dõi này chờ (thường: kết quả về muộn). Đóng DONE '
    'khi bác sĩ duyệt kết quả của chỉ định. Slice 1, 20260918000001.';
COMMENT ON COLUMN public.follow_up_case.visit_id IS
    'Lượt khám sinh ra việc theo dõi — checkout đọc để biết lượt đã bàn giao '
    'gì, thay vì nối qua work_item của rail cũ.';
