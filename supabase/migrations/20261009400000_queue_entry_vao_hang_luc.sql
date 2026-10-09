-- GIỜ VÀO HÀNG LẦN ĐẦU của một chỗ chờ (Tuyền 09/10/2026, việc 7b).
--
-- `queue_entry.eligible_at` là KHOÁ XẾP HÀNG: khách rời phòng dịch vụ thì
-- `hang_cho.mo_cho_bi_chan` đặt lại `eligible_at = now()` — luật cố ý "quay
-- lại thì xếp sau người đang chờ" (giữ nguyên). Hệ quả: giờ khách THẬT SỰ bắt
-- đầu chờ bị ghi đè, Hành trình khách thấy `eligible_at` muộn hơn giờ bắt đầu
-- khám, coi là "quay lại" và bỏ trống "vào/chờ" (ví dụ thật: vào hàng 18:13,
-- khám 18:37 — màn không hiện 24′ chờ).
--
-- Cột mới `vao_hang_luc` = lần ĐẦU chỗ chờ này có giờ vào hàng (bắt đầu chờ
-- thật). Không đổi thứ tự hàng: mọi câu xếp vẫn đọc `eligible_at`.
--
-- Bất biến ép ở Postgres (SO-LUAT Phần 6), không rải ở mọi chỗ INSERT/UPDATE
-- (Python + hàm SQL): trigger BEFORE INSERT / UPDATE OF eligible_at,
-- vao_hang_luc —
--   * tạo ở 'waiting' (có eligible_at) → vao_hang_luc = eligible_at;
--   * tạo ở 'blocked' (eligible_at rỗng) → để rỗng; lần đầu được mở
--     (`mo_cho_bi_chan` đặt eligible_at) → vao_hang_luc = giờ ấy, tức
--     COALESCE(vao_hang_luc, now());
--   * đã có giá trị thì KHÔNG BAO GIỜ bị ghi đè (kể cả lệnh ghi thẳng cột).
--
-- BẪY ĐÃ TRÁNH: không `ADD COLUMN … DEFAULT now()` — mọi dòng cũ sẽ nhận giờ
-- chạy migration. Thứ tự: thêm cột NULL → điền dòng cũ = eligible_at (dòng đã
-- bị ghi đè trước hôm nay thì đành chịu) → trigger cho dòng mới.
--
-- Chạy lại nhiều lần được.

-- ── 1. Cột, rỗng ───────────────────────────────────────────────────────────
ALTER TABLE public.queue_entry ADD COLUMN IF NOT EXISTS vao_hang_luc timestamptz;

COMMENT ON COLUMN public.queue_entry.vao_hang_luc IS
    'Lần ĐẦU chỗ chờ có giờ vào hàng (bắt đầu chờ thật) — không bao giờ ghi đè. '
    'eligible_at vẫn là khoá xếp hàng (bị đặt lại khi khách quay lại).';

-- ── 2. Dòng cũ = eligible_at hiện có ───────────────────────────────────────
-- Tin `notify_row_change` của mỗi dòng giống hệt nhau ({t, c}) — Postgres gộp
-- trong một giao dịch, không dội tin xuống màn.
UPDATE public.queue_entry
   SET vao_hang_luc = eligible_at
 WHERE vao_hang_luc IS NULL
   AND eligible_at IS NOT NULL;

-- ── 3. Dòng mới: trigger ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.queue_entry_giu_vao_hang_luc()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.vao_hang_luc IS NOT NULL THEN
        NEW.vao_hang_luc := OLD.vao_hang_luc;
    ELSE
        NEW.vao_hang_luc := coalesce(NEW.vao_hang_luc, NEW.eligible_at);
    END IF;
    RETURN NEW;
END
$function$;

COMMENT ON FUNCTION public.queue_entry_giu_vao_hang_luc() IS
    'vao_hang_luc = eligible_at đầu tiên của chỗ chờ; đã có thì giữ nguyên.';

DROP TRIGGER IF EXISTS trg_queue_entry_vao_hang_luc ON public.queue_entry;
CREATE TRIGGER trg_queue_entry_vao_hang_luc
    BEFORE INSERT OR UPDATE OF eligible_at, vao_hang_luc ON public.queue_entry
    FOR EACH ROW EXECUTE FUNCTION public.queue_entry_giu_vao_hang_luc();

DO $verify$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                    WHERE tgname = 'trg_queue_entry_vao_hang_luc'
                      AND NOT tgisinternal) THEN
        RAISE EXCEPTION 'thiếu trigger trg_queue_entry_vao_hang_luc';
    END IF;
    IF EXISTS (SELECT 1 FROM public.queue_entry
                WHERE vao_hang_luc IS NULL AND eligible_at IS NOT NULL) THEN
        RAISE EXCEPTION 'còn chỗ chờ có eligible_at mà chưa có vao_hang_luc';
    END IF;
END
$verify$;

NOTIFY pgrst, 'reload schema';
