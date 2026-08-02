-- Ai đã làm việc này.
--
-- event_log trả lời được "cái gì xảy ra, lúc nào, ở phòng khám nào" nhưng chưa
-- bao giờ trả lời được "ai": không có cột actor. Màn Lịch sử thao tác
-- (app/(dashboard)/audit-log) mở đầu bằng đúng câu "xem ai đã thay đổi gì", rồi
-- hiển thị `source` — "api", "dashboard" — vì đó là thứ gần nhất nó có.
--
-- Dữ liệu thật ra đã ở đó một nửa: 8/9 chỗ ghi event nhét
-- metadata->>'clinic_staff_id' vào JSONB. Nhưng JSONB không có khoá ngoại (xoá
-- một nhân sự là còn lại chuỗi UUID trỏ vào hư không), không có index — câu hỏi
-- "ai đã đọc hồ sơ bệnh nhân này" phải quét toàn bảng — và im lặng khi một
-- service quên ghi. Một nửa dữ liệu không kiểm chứng được thì không phải là
-- audit trail, chỉ là log.
--
-- Thêm cột lúc bảng còn nhỏ là một dòng ALTER; thêm sau một năm là một cuộc
-- backfill từ JSONB mà không ai dám chạy. TT 13/2025 (bệnh án điện tử, hạn
-- 31/12/2026) sẽ hỏi đúng câu này, và câu trả lời phải có sẵn từ trước.
--
-- NULL nghĩa là **hệ thống**, không phải "không rõ ai": relay, worker và các
-- kênh ngoài (Zalo, walk-in) sinh event không có người đứng sau. Vì vậy cột
-- không NOT NULL — ép NOT NULL sẽ buộc mọi event máy sinh phải trỏ vào một nhân
-- sự giả, tức là nói dối trong chính cái bảng dùng để đối chiếu sự thật.

ALTER TABLE public.event_log
    ADD COLUMN IF NOT EXISTS actor_staff_id uuid;

-- ON DELETE RESTRICT, không phải SET NULL: nếu có ai đó xoá cứng một nhân sự,
-- thà chặn thao tác xoá còn hơn để lịch sử tự quên mất người đã hành động.
-- staff vốn được vô hiệu hoá bằng is_active, không bị xoá — nên ràng buộc này
-- trong đời thường không chặn ai cả.
DO $fk$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'event_log_actor_staff_id_fkey'
           AND conrelid = 'public.event_log'::regclass
    ) THEN
        ALTER TABLE public.event_log
            ADD CONSTRAINT event_log_actor_staff_id_fkey
            FOREIGN KEY (actor_staff_id) REFERENCES public.staff (id)
            ON DELETE RESTRICT;
    END IF;
END
$fk$;

-- Backfill từ chính JSONB đã ghi. Nối sang staff thay vì ép kiểu thẳng: chuỗi
-- rác hoặc UUID của một nhân sự không còn tồn tại sẽ bị bỏ qua chứ không làm
-- migration đổ, và cũng không tạo ra một khoá ngoại trỏ vào chỗ trống.
UPDATE public.event_log e
   SET actor_staff_id = s.id
  FROM public.staff s
 WHERE e.actor_staff_id IS NULL
   AND e.metadata ? 'clinic_staff_id'
   AND e.metadata ->> 'clinic_staff_id' ~
       '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
   AND s.id = (e.metadata ->> 'clinic_staff_id')::uuid;

-- Câu hỏi cần đỡ là "nhân sự này đã làm gì, gần nhất trước", luôn trong phạm vi
-- một phòng khám. Dẫn đầu bằng clinic_id để cùng lúc thoả bất biến tenant
-- (supabase/tests/tenant_invariants.sql).
CREATE INDEX IF NOT EXISTS idx_event_log_actor
    ON public.event_log (clinic_id, actor_staff_id, occurred_at DESC);

COMMENT ON COLUMN public.event_log.actor_staff_id IS
    'Nhân sự đã gây ra event. NULL = hệ thống (relay, worker, kênh ngoài), '
    'không phải "không rõ". Nguồn sự thật thay cho metadata->>''clinic_staff_id'', '
    'khoá này không còn được ghi mới từ 20260802000003.';
