-- Hai cột trạng thái của chỉ định khớp nhau ở MỘT chỗ: Postgres.
--
-- `execution_status` (đường làm mới) là nguồn thật; `exec_status` (cột cũ) là
-- bản chiếu cho các màn/view còn đọc cột cũ. Trước bản này có 4 lối ghi lệch:
--   · đối tác tự lấy mẫu (`doi_tac_da_lay_mau`) chỉ ghi cột cũ → hành trình vẫn
--     đếm "chưa làm", báo CSKH sai;
--   · [Không làm được] khi chưa có phòng → cột mới NOT_PERFORMED, cột cũ còn
--     `authorized` → lượt không đóng được, quầy vẫn thấy dòng mở;
--   · đường làm mới không ghi `started_at`/`finished_at` → điều phối, theo dõi
--     thủ thuật, dòng thời gian check-out và hạn CHO_KQ_XN đọc giờ rỗng;
--   · CASE viết tay trong `ServiceExecutionService._doi_trang_thai` — nay chuyển
--     vào trigger này, mọi lối ghi đều đi qua.
--
-- Luật (trigger BEFORE UPDATE, chỉ chỉ định đã qua nháp):
--   xuôi  — `execution_status` đổi → suy `exec_status`, ghi giờ bắt đầu/xong;
--   ngược — chỉ `exec_status` đổi sang in_progress/performed/not_performed (lối
--           cũ) trên chỉ định đời mới (`selection_status` có giá trị) → kéo
--           `execution_status` theo. Chỉ định đời cũ giữ NULL (quy ước "NULL =
--           legacy" của 20260922000001).

-- [Không làm được] có thể xảy ra trước khi có phòng (khách từ chối lúc chờ).
ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_room_when_assigned;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_room_when_assigned
        CHECK (exec_status NOT IN ('assigned', 'in_progress', 'performed')
               OR room_id IS NOT NULL);

CREATE OR REPLACE FUNCTION public.service_order_dong_bo_trang_thai()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.exec_status IN ('draft', 'cancelled') THEN
        RETURN NEW;
    END IF;

    IF NEW.execution_status IS DISTINCT FROM OLD.execution_status THEN
        -- xuôi: đường làm mới → cột cũ
        NEW.exec_status := CASE NEW.execution_status
            WHEN 'IN_PROGRESS' THEN
                CASE WHEN NEW.room_id IS NOT NULL THEN 'in_progress' ELSE NEW.exec_status END
            WHEN 'COMPLETED' THEN
                CASE WHEN NEW.room_id IS NOT NULL THEN 'performed' ELSE NEW.exec_status END
            WHEN 'NOT_PERFORMED' THEN
                CASE WHEN nullif(btrim(coalesce(NEW.not_performed_reason, '')), '') IS NOT NULL
                     THEN 'not_performed' ELSE NEW.exec_status END
            WHEN 'INTERRUPTED' THEN
                CASE WHEN NEW.room_id IS NOT NULL THEN 'assigned' ELSE 'authorized' END
            WHEN 'PENDING' THEN
                CASE WHEN NEW.room_id IS NOT NULL THEN 'assigned' ELSE 'authorized' END
            ELSE NEW.exec_status
        END;
        IF NEW.execution_status = 'IN_PROGRESS' THEN
            NEW.started_at := coalesce(NEW.started_at, now());
            NEW.finished_at := NULL;
        ELSIF NEW.execution_status IN ('COMPLETED', 'NOT_PERFORMED') THEN
            -- Bắt đầu lại luôn xoá giờ xong (nhánh trên), nên coalesce chỉ giữ
            -- giờ thật của dòng cũ khi chữa dữ liệu.
            NEW.finished_at := coalesce(NEW.finished_at, now());
        END IF;
    ELSIF NEW.exec_status IS DISTINCT FROM OLD.exec_status
          AND NEW.selection_status IS NOT NULL THEN
        -- ngược: lối cũ (đối tác lấy mẫu, /start, /complete) → cột mới
        IF NEW.exec_status = 'in_progress'
           AND NEW.execution_status IS DISTINCT FROM 'IN_PROGRESS' THEN
            NEW.execution_status := 'IN_PROGRESS';
            NEW.execution_revision := NEW.execution_revision + 1;
        ELSIF NEW.exec_status = 'performed'
              AND NEW.execution_status IS DISTINCT FROM 'COMPLETED' THEN
            NEW.execution_status := 'COMPLETED';
            NEW.execution_revision := NEW.execution_revision + 1;
        ELSIF NEW.exec_status = 'not_performed'
              AND NEW.execution_status IS DISTINCT FROM 'NOT_PERFORMED' THEN
            NEW.execution_status := 'NOT_PERFORMED';
            NEW.execution_revision := NEW.execution_revision + 1;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS service_order_dong_bo_trang_thai ON public.service_order;
CREATE TRIGGER service_order_dong_bo_trang_thai
    BEFORE UPDATE ON public.service_order
    FOR EACH ROW EXECUTE FUNCTION public.service_order_dong_bo_trang_thai();

-- Chữa dòng đã lệch (chạy lại vô hại).
-- 1. Lối cũ đã làm/không làm mà cột mới chưa theo (đối tác tự lấy mẫu…).
UPDATE public.service_order
   SET execution_status = CASE exec_status
           WHEN 'in_progress' THEN 'IN_PROGRESS'
           WHEN 'performed' THEN 'COMPLETED'
           ELSE 'NOT_PERFORMED' END,
       execution_revision = execution_revision + 1
 WHERE selection_status IS NOT NULL
   AND exec_status IN ('in_progress', 'performed', 'not_performed')
   AND coalesce(execution_status, 'PENDING') IN ('PENDING', 'INTERRUPTED');

-- 2. Không làm được mà cột cũ còn mở.
UPDATE public.service_order
   SET exec_status = 'not_performed'
 WHERE execution_status = 'NOT_PERFORMED'
   AND exec_status IN ('authorized', 'assigned', 'in_progress')
   AND nullif(btrim(coalesce(not_performed_reason, '')), '') IS NOT NULL;

-- 3. Giờ bắt đầu/xong lấy từ lần làm (service_execution_attempt) cho dòng cũ.
UPDATE public.service_order so
   SET started_at = coalesce(so.started_at, a.bat_dau),
       finished_at = coalesce(so.finished_at, a.ket_thuc)
  FROM (
      SELECT clinic_id, service_order_id,
             min(started_at) AS bat_dau, max(completed_at) AS ket_thuc
        FROM public.service_execution_attempt
       GROUP BY clinic_id, service_order_id
  ) a
 WHERE a.clinic_id = so.clinic_id AND a.service_order_id = so.id
   AND so.execution_status IN ('IN_PROGRESS', 'COMPLETED', 'NOT_PERFORMED')
   AND (so.started_at IS NULL OR (so.finished_at IS NULL
        AND so.execution_status <> 'IN_PROGRESS'));
