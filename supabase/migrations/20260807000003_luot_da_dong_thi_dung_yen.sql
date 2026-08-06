-- Lượt khám đã đóng thì ĐỨNG YÊN — và mốc đóng phải nằm trên chính lượt khám.
--
-- CHUYỆN ĐÃ XẢY RA TRÊN PRODUCTION, đo được ngày 07/08/2026:
--
--   Lượt ba63841e check-out lúc 16:50:10 (LUOTKHAM-15 = COMPLETED).
--   Lúc 18:21:57 — 91 phút sau, bệnh nhân đã về từ lâu — một bước khác của
--   cùng lượt đổi trạng thái. Trigger `update_visit_current_node` chạy, đi tìm
--   "bước IN_PROGRESS có started_at mới nhất", thấy LUOTKHAM-03 (Sinh hiệu)
--   vẫn còn IN_PROGRESS, và ghi đè `visit.current_node_code` về LUOTKHAM-03.
--
--   Kết quả: một người đã ra về xuất hiện lại trên bảng Trưởng ca ở bước "Sinh
--   hiệu", và ở đó vĩnh viễn. `visit.status` vẫn IN_PROGRESS, không ai gọi
--   tên, không màn nào đóng được nữa vì bước đóng đã COMPLETED rồi.
--
-- HAI NGUYÊN NHÂN, PHẢI SỬA CẢ HAI:
--
--   (a) Check-out BÌNH THƯỜNG không huỷ các bước còn treo. Câu UPDATE làm việc
--       đó nằm trong nhánh `if incomplete:` của checkout_service.close(), nên
--       chỉ chạy khi khách về giữa chừng. Prod hôm nay: LUOTKHAM-13 và
--       LUOTKHAM-14 mỗi mã 23 PENDING, 0 COMPLETED trong suốt đời hệ thống.
--       Sửa ở Python, cùng lần thay đổi này.
--
--   (b) Trigger không biết lượt đã đóng. Nó chỉ nhìn work_item.
--
-- VÌ SAO KHÔNG CHỐNG BẰNG "KHÔNG ĐI LÙI THEO THỜI GIAN":
-- luật ấy nghe gọn nhưng sai. Giao dịch check-in mở LUOTKHAM-01 và LUOTKHAM-03
-- cùng một lúc, nên hai bước IN_PROGRESS song song là chuyện bình thường; một
-- luật so sánh started_at sẽ ghim bệnh nhân lại ở bước đã xong. Cái trigger
-- thiếu không phải thứ tự thời gian, mà là câu trả lời cho "lượt này còn đang
-- diễn ra không". Nên khai thẳng nó ra thành một cột.

-- ---------------------------------------------------------------------------
-- 1. Mốc đóng lượt, khai thẳng trên bảng visit
-- ---------------------------------------------------------------------------
ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS closed_at        timestamptz,
    ADD COLUMN IF NOT EXISTS closed_by_staff_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.visit'::regclass
           AND conname = 'visit_closed_by_fkey'
    ) THEN
        ALTER TABLE public.visit
            ADD CONSTRAINT visit_closed_by_fkey
            FOREIGN KEY (closed_by_staff_id) REFERENCES public.staff (id);
    END IF;
END $$;

COMMENT ON COLUMN public.visit.closed_at IS
    'Lúc Lễ tân đóng lượt (bệnh nhân rời phòng khám). Khác finalized_at — cái '
    'kia là lúc bác sĩ KÝ bệnh án. Trigger update_visit_current_node đứng yên '
    'khi cột này có giá trị (20260807000003).';

-- Vá dữ liệu cũ: lượt nào đã hoàn tất bước đóng thì lấy đúng mốc ấy.
UPDATE public.visit v
   SET closed_at = w.finished_at
  FROM public.work_item w
 WHERE w.visit_id = v.visit_id
   AND w.clinic_id = v.clinic_id
   AND w.node_code = 'LUOTKHAM-15'
   AND w.status = 'COMPLETED'
   AND v.closed_at IS NULL;

-- ---------------------------------------------------------------------------
-- 2. Trigger đứng yên khi lượt đã đóng
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.update_visit_current_node()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_visit_id     uuid;
    v_clinic_id    uuid;
    v_active_node  text;
    v_closed       boolean;
BEGIN
    -- Only care about status changes on items that belong to a visit.
    v_visit_id  := coalesce(NEW.visit_id, OLD.visit_id);
    v_clinic_id := coalesce(NEW.clinic_id, OLD.clinic_id);

    IF v_visit_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- LƯỢT ĐÃ ĐÓNG THÌ ĐỨNG YÊN. Bệnh nhân đã rời phòng khám; không có bước
    -- nào "đang diễn ra" nữa, kể cả khi còn sót một work_item chưa ai đóng.
    -- Xem đầu file: đây là chỗ một người đã về nhà bị kéo ngược lên bảng.
    SELECT (v.closed_at IS NOT NULL
            OR v.status IN ('FINALIZED', 'AMENDED', 'INCOMPLETE'))
      INTO v_closed
      FROM public.visit v
     WHERE v.visit_id = v_visit_id
       AND v.clinic_id = v_clinic_id;

    IF coalesce(v_closed, FALSE) THEN
        RETURN NEW;
    END IF;

    -- Find the most recently started IN_PROGRESS work item for this visit.
    -- That is where the patient is right now.
    SELECT w.node_code
      INTO v_active_node
      FROM public.work_item w
     WHERE w.visit_id = v_visit_id
       AND w.clinic_id = v_clinic_id
       AND w.status = 'IN_PROGRESS'
     ORDER BY w.started_at DESC NULLS LAST
     LIMIT 1;

    -- Update visit — only if the node actually changed (avoid noisy updates).
    UPDATE public.visit
       SET previous_node_code = current_node_code,
           current_node_code  = v_active_node,
           current_node_since = CASE
               WHEN v_active_node IS DISTINCT FROM current_node_code
               THEN now()
               ELSE current_node_since
           END,
           updated_at = now()
     WHERE visit_id = v_visit_id
       AND clinic_id = v_clinic_id
       AND current_node_code IS DISTINCT FROM v_active_node;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.update_visit_current_node() IS
    'Giữ visit.current_node_code khớp với bước đang diễn ra. ĐỨNG YÊN khi lượt '
    'đã đóng (visit.closed_at) hoặc hồ sơ đã chốt — nếu không, một work_item '
    'còn sót sẽ kéo bệnh nhân đã ra về trở lại bảng điều phối (20260807000003).';

-- ---------------------------------------------------------------------------
-- 3. Dọn hậu quả đã có
-- ---------------------------------------------------------------------------
-- Các lượt đã đóng mà con trỏ đang chỉ sai chỗ: đưa về đúng bước đóng, và huỷ
-- những bước còn treo của chúng. Không xoá dòng nào — huỷ bằng đổi trạng thái.
-- `finished_at` KHÔNG PHẢI TUỲ CHỌN: ràng buộc
-- `work_item_finished_when_terminal` của workflow kernel buộc
-- status ∈ (COMPLETED, SKIPPED, CANCELLED) ⟺ finished_at IS NOT NULL.
-- Bản đầu của migration này quên nó và bị production từ chối — bài kiểm không
-- bắt được vì trên lược đồ trần không có lượt đã đóng nào để dọn, nên câu
-- UPDATE khớp 0 dòng và chạy qua trong im lặng.
UPDATE public.work_item w
   SET status = 'CANCELLED',
       finished_at = coalesce(w.finished_at, v.closed_at, now()),
       updated_at = now()
  FROM public.visit v
 WHERE v.visit_id = w.visit_id
   AND v.clinic_id = w.clinic_id
   AND v.closed_at IS NOT NULL
   AND w.status IN ('PENDING', 'IN_PROGRESS');

UPDATE public.visit v
   SET current_node_code = 'LUOTKHAM-15',
       current_room_id   = NULL,
       updated_at        = now()
 WHERE v.closed_at IS NOT NULL
   AND v.current_node_code IS DISTINCT FROM 'LUOTKHAM-15';
