-- INVENTORY WRITE GUARDS — bốn bất biến mà đường ghi kho phải đứng lên trên.
--
-- `20260802000001` dựng bảng và trigger cộng dồn tồn kho, nhưng chưa ai ghi vào
-- nó bao giờ: màn /pharmacy còn read-only, drug_batch và inventory_txn đều 0
-- dòng trên prod. Đó chính là lý do phải làm BÂY GIỜ — căng lưới trên một cái
-- kho rỗng thì không tốn gì; căng lưới sau khi đã có hàng chục nghìn dòng thì
-- phải NOT VALID rồi VALIDATE riêng, và phải đi sửa dữ liệu đã sai.
--
-- Bốn điều dưới đây phải do DATABASE giữ, không phải do service nhớ giữ. Service
-- vẫn kiểm và trả lỗi tử tế; đây là cái lưới bên dưới, cho cả những đường ghi
-- chưa được viết.
--
-- 1. Tồn kho không âm.
--    `inventory_txn_apply()` cộng thẳng `quantity + quantity_on_hand` không hỏi
--    gì. Xuất 50 viên khỏi lô còn 30 cho ra -20: một con số vô nghĩa mà mọi màn
--    hình vẫn hiển thị bình thường, và không ai biết 20 viên kia đi đâu. Sai
--    lặng lẽ trong sổ kho là loại sai tệ nhất — nó chỉ lộ ra lúc kiểm kê, hàng
--    tháng sau, khi không còn cách nào truy lại.
--
-- 2. Sổ kho không sửa được.
--    `inventory_txn` là sổ cái; `quantity_on_hand` chỉ là tổng của nó. Sửa một
--    dòng txn cũ thì trigger không chạy lại: tồn kho và sổ lệch nhau vĩnh viễn
--    mà không dòng nào nói đã có người sửa. Nhập nhầm thì ghi một dòng ADJUST
--    kèm lý do — đúng cách một cuốn sổ kho được sửa ngoài đời.
--
-- 3. Thao tác tay phải nói ai làm — VÀ người đó không được biến mất.
--    Hai vế, không tách được. Xem mục 3 để biết vì sao.
--
-- 4. Trừ kho không được vượt biên phòng khám.  ← LỖ ĐANG MỞ, không có trong
--    bản gốc của nhánh. Xem mục 4.
--
-- ═══════════════════════════════════════════════════════════════════════════
-- HAI CHỖ BẢN GỐC (nhánh b3, 02/08) KHÔNG CHẠY ĐƯỢC NỮA, ghi lại để người sau
-- không đi lại đúng vết:
--
--   · Bản gốc trỏ trigger vào `public.event_log_append_only_guard()`. Hàm đó
--     CÓ trong `20260714000001_baseline_schema.sql` nhưng KHÔNG CÓ trên prod —
--     baseline chưa bao giờ chạy thật, nó chỉ được `repair` vào bảng lịch sử.
--     Hậu quả là loại tệ nhất: CI (Postgres trắng, chạy baseline thật) XANH,
--     còn `supabase db push` lên prod ĐỎ tại `CREATE TRIGGER`. Nên file này tự
--     khai hàm của mình và cắt hẳn phụ thuộc đó.
--   · Không dùng `enforce_append_only()` (hàm CÓ THẬT trên prod) được: thân hàm
--     tham chiếu `OLD.event_id`, chạy trên inventory_txn sẽ ném "record OLD has
--     no field event_id" thay vì một thông báo có nghĩa.
-- ═══════════════════════════════════════════════════════════════════════════

-- ---------------------------------------------------------------------------
-- 1. Tồn kho không âm
-- ---------------------------------------------------------------------------

-- Xử lý dữ liệu TRƯỚC khi thêm ràng buộc. Trên prod hôm nay khối này đi qua
-- (0 lô âm), nhưng migration phải chạy được trên MỌI DB — staging, máy lập
-- trình viên, một bản restore. Cố ý dừng lại thay vì tự nắn số: nắn xong thì
-- không ai còn biết đã từng âm, mà đó đúng là thứ cần biết.
DO $negative_stock$
DECLARE
    negative_batches int;
BEGIN
    SELECT count(*) INTO negative_batches
      FROM public.drug_batch WHERE quantity_on_hand < 0;

    IF negative_batches > 0 THEN
        RAISE EXCEPTION
            'Có % lô thuốc đang âm tồn. Sửa bằng một dòng ADJUST có lý do rồi '
            'chạy lại migration này — không tự nắn số trong migration, vì nắn '
            'xong thì không ai biết đã từng âm.', negative_batches;
    END IF;
END
$negative_stock$;

ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS drug_batch_qty_non_negative;
ALTER TABLE public.drug_batch ADD CONSTRAINT drug_batch_qty_non_negative
    CHECK (quantity_on_hand >= 0);

COMMENT ON CONSTRAINT drug_batch_qty_non_negative ON public.drug_batch IS
    'Tồn kho không âm. Trigger inventory_txn_apply() cộng thẳng, không tự kiểm.';

-- ---------------------------------------------------------------------------
-- 2. inventory_txn append-only
-- ---------------------------------------------------------------------------

-- ERRCODE `insufficient_privilege` (42501), không phải raise_exception mặc định
-- (P0001). Hai lý do: nó khớp với `enforce_append_only()` đang chạy trên prod
-- cho event_log, và PostgREST dịch 42501 thành HTTP 403 — đúng nghĩa "không
-- được phép", thay vì 400 "dữ liệu sai".
-- ⚠ supabase/tests/inventory_write_guards.sql phải bắt WHEN insufficient_privilege.
CREATE OR REPLACE FUNCTION public.inventory_txn_append_only_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Sổ kho % chỉ ghi thêm: % không được phép. Nhập nhầm thì ghi một dòng '
        'ADJUST kèm lý do.', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

COMMENT ON FUNCTION public.inventory_txn_append_only_guard() IS
    'Chặn UPDATE/DELETE trên sổ kho. Khai riêng thay vì dùng lại '
    'event_log_append_only_guard() vì hàm đó chỉ có trong baseline, không có '
    'trên prod (baseline mới được repair chứ chưa từng chạy).';

DROP TRIGGER IF EXISTS inventory_txn_append_only ON public.inventory_txn;
CREATE TRIGGER inventory_txn_append_only
    BEFORE UPDATE OR DELETE ON public.inventory_txn
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_append_only_guard();

-- ---------------------------------------------------------------------------
-- 3. Thao tác tay phải nói ai làm — và người ấy phải ở lại trong sổ
-- ---------------------------------------------------------------------------

-- `performed_by_staff_id` đang nullable. Cấp thuốc mà không biết ai cấp thì
-- không trả lời được câu hỏi duy nhất đáng hỏi khi có sự cố. Không đặt NOT NULL
-- (đường máy — đơn thuốc, đồng bộ POS — có thể không có người), nhưng ràng
-- buộc: đã là thao tác tay (`ref_type` NULL hoặc 'manual') thì phải có người.
--
-- ĐỔI FK SANG RESTRICT, và đây KHÔNG phải chuyện phụ. FK hiện tại là
-- `ON DELETE SET NULL`. Ghép nó với CHECK bên dưới là hai luật khoá chết nhau:
-- xoá một nhân viên đã từng ghi sổ tay, FK cố SET NULL, CHECK cấm NULL, và
-- Postgres ném ra
--     ERROR: new row for relation "inventory_txn" violates check constraint
--            "inventory_txn_manual_needs_actor"
-- — một thông báo về bảng KHO khi người vận hành đang xoá NHÂN SỰ. Đã tái hiện
-- được trên prod. Hôm nay chưa nổ vì kho rỗng; nó sẽ nổ đúng ngày B.3 lên.
--
-- RESTRICT là câu trả lời đúng chứ không chỉ là cách tránh va chạm: file này
-- vừa tuyên bố sổ kho không sửa được thì cũng không thể cho phép xoá người đã
-- ký sổ. Nhất quán với `inventory_txn_batch_fkey` vốn đã RESTRICT. Nghỉ việc
-- xử lý bằng `is_active = false`, không xoá cứng.
ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_staff_fkey;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_staff_fkey
    FOREIGN KEY (performed_by_staff_id)
    REFERENCES public.staff (id) ON DELETE RESTRICT;

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_manual_needs_actor;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_manual_needs_actor
    CHECK (
        (ref_type IS NOT NULL AND ref_type <> 'manual')
        OR performed_by_staff_id IS NOT NULL
    );

COMMENT ON CONSTRAINT inventory_txn_manual_needs_actor ON public.inventory_txn IS
    'Thao tác kho bằng tay phải gắn với một nhân viên. Đi kèm FK RESTRICT: '
    'người đã ký sổ thì không xoá được nữa (dùng is_active thay vì xoá).';

-- ---------------------------------------------------------------------------
-- 4. Trừ kho không vượt biên phòng khám
-- ---------------------------------------------------------------------------

-- LỖ ĐANG MỞ TRÊN PROD, không có trong bản gốc. `inventory_txn_apply()` viết
--     WHERE id = NEW.drug_batch_id
-- và không hề nhắc tới clinic_id. Backend chạy service_role nên BỎ QUA RLS: một
-- txn khai `clinic_id` = phòng khám B nhưng `drug_batch_id` trỏ vào lô của
-- phòng khám A sẽ trừ thẳng vào kho của A, không một lỗi nào. Đã dựng lại được
-- trên prod: lô 100 viên của A còn 60 sau một txn mang tên B.
--
-- Vá ở HAI TẦNG vì chúng trả lời hai câu khác nhau:
--   · FK phức hợp — DB tự chặn, không phụ thuộc vào việc thân hàm có nhớ hay
--     không. Đây là hàng rào thật.
--   · WHERE trong hàm — để khi có gì đó lọt qua (ai đó DROP FK, hay một đường
--     ghi tương lai) thì lỗi là một câu tiếng người, không phải một lần trừ
--     kho im lặng.
-- Sửa hàm mà không có FK là để lại một luật chỉ tồn tại trong trí nhớ của một
-- hàm; thêm FK mà không sửa hàm là để lại một thông báo lỗi không ai đọc hiểu.

-- FK phức hợp cần một UNIQUE để tham chiếu. `id` đã là PK nên (id, clinic_id)
-- là dư về mặt định danh — nó tồn tại chỉ để làm cái neo cho FK bên dưới.
DO $batch_tenant_anchor$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.drug_batch'::regclass
           AND conname = 'uq_drug_batch_id_clinic'
    ) THEN
        ALTER TABLE public.drug_batch
            ADD CONSTRAINT uq_drug_batch_id_clinic UNIQUE (id, clinic_id);
    END IF;
END
$batch_tenant_anchor$;

ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_batch_same_clinic_fkey;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_batch_same_clinic_fkey
    FOREIGN KEY (drug_batch_id, clinic_id)
    REFERENCES public.drug_batch (id, clinic_id) ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION public.inventory_txn_apply()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE public.drug_batch
       SET quantity_on_hand = quantity_on_hand + NEW.quantity,
           updated_at = now()
     WHERE id = NEW.drug_batch_id
       AND clinic_id = NEW.clinic_id;

    -- Không tìm thấy thì DỪNG. Bỏ qua lặng lẽ còn tệ hơn cả trừ nhầm: dòng vẫn
    -- vào sổ, tồn kho không đổi, và sổ với số dư lệch nhau ngay từ dòng đầu.
    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Lô thuốc % không thuộc phòng khám % (hoặc không tồn tại) — '
            'không trừ kho chéo phòng khám.', NEW.drug_batch_id, NEW.clinic_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    RETURN NEW;
END
$$;

COMMENT ON CONSTRAINT inventory_txn_batch_same_clinic_fkey ON public.inventory_txn IS
    'Dòng sổ và lô thuốc phải cùng một phòng khám. Backend chạy service_role '
    'nên RLS không đỡ được chỗ này — ràng buộc phải nằm trong DB.';

-- ---------------------------------------------------------------------------
-- 5. Tự kiểm
-- ---------------------------------------------------------------------------

DO $verify$
DECLARE
    apply_body text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'drug_batch_qty_non_negative'
                      AND conrelid = 'public.drug_batch'::regclass) THEN
        RAISE EXCEPTION 'thiếu drug_batch_qty_non_negative';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'inventory_txn_manual_needs_actor'
                      AND conrelid = 'public.inventory_txn'::regclass) THEN
        RAISE EXCEPTION 'thiếu inventory_txn_manual_needs_actor';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'inventory_txn_batch_same_clinic_fkey'
                      AND conrelid = 'public.inventory_txn'::regclass) THEN
        RAISE EXCEPTION 'thiếu inventory_txn_batch_same_clinic_fkey';
    END IF;

    -- Trigger phải tồn tại VÀ đang bật ('O' = origin). Một trigger bị DISABLE
    -- trông y hệt một trigger đang chạy trong mọi bản `\d`.
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                    WHERE tgrelid = 'public.inventory_txn'::regclass
                      AND tgname = 'inventory_txn_append_only'
                      AND tgenabled = 'O') THEN
        RAISE EXCEPTION 'inventory_txn_append_only thiếu hoặc đang bị tắt';
    END IF;

    -- Cặp CHECK + FK phải khớp nhau. Nếu ai đó đưa FK về SET NULL thì việc xoá
    -- một nhân viên đã ghi sổ tay sẽ ném lỗi về bảng KHO — kiểm ngay tại đây
    -- còn hơn để người vận hành gặp nó lúc 8h sáng.
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.inventory_txn'::regclass
           AND contype = 'f'
           AND confrelid = 'public.staff'::regclass
           AND confdeltype <> 'r'   -- 'r' = RESTRICT
    ) THEN
        RAISE EXCEPTION
            'FK inventory_txn -> staff phải là ON DELETE RESTRICT: SET NULL sẽ '
            'đánh nhau với inventory_txn_manual_needs_actor';
    END IF;

    -- Hàm cộng dồn phải thật sự mang clinic_id, không chỉ "đã có người sửa".
    SELECT prosrc INTO apply_body
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname = 'inventory_txn_apply';

    IF apply_body IS NULL OR apply_body NOT LIKE '%clinic_id = NEW.clinic_id%' THEN
        RAISE EXCEPTION
            'inventory_txn_apply() không lọc theo clinic_id — trừ kho chéo '
            'phòng khám sẽ chạy im lặng';
    END IF;
END
$verify$;
