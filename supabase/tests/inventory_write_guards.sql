-- Bài kiểm cho 20260805000003_inventory_write_guards.sql.
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/inventory_write_guards.sql
--
-- Kiểm HÀNH VI, không kiểm sự tồn tại. Một ràng buộc có tên đúng mà không chặn
-- gì thì tệ hơn không có, vì người ta tin là có — đúng như chuyện
-- `array_length(mảng_rỗng,1) >= 1` đã dạy (xem 20260804000021).
--
-- Năm tính chất, và cái thứ năm là thứ prod từng hở thật: một dòng sổ khai
-- phòng khám B nhưng trỏ vào lô của phòng khám A đã trừ thẳng vào kho của A,
-- không một lỗi nào — 100 viên còn 60. Backend chạy service_role nên RLS không
-- đỡ được chỗ đó.

BEGIN;

-- Dữ liệu dựng tại chỗ, không dựa vào seed: CI chạy trên một Postgres trắng.
INSERT INTO public.clinic (id, code, name, timezone)
VALUES ('aa000000-0000-4000-8000-0000000000a1', 'TESTA', 'Phòng khám A',
        'Asia/Ho_Chi_Minh'),
       ('bb000000-0000-4000-8000-0000000000b1', 'TESTB', 'Phòng khám B',
        'Asia/Ho_Chi_Minh')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('cc000000-0000-4000-8000-0000000000c1',
        'aa000000-0000-4000-8000-0000000000a1', 'CS1', 'Cơ sở 1')
ON CONFLICT (id) DO NOTHING;

-- `primary_location_id` là NOT NULL không default. Khai tường minh thay vì dựa
-- vào trigger điền hộ — một bài kiểm dựa vào trigger sẽ đổ khi trigger đổi.
INSERT INTO public.staff
    (id, primary_location_id, full_name, primary_department, employment_type)
VALUES ('dd000000-0000-4000-8000-0000000000d1',
        'cc000000-0000-4000-8000-0000000000c1', 'Dược sĩ thử',
        'PHARMACIST', 'FULL_TIME')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.drug_catalog (id, clinic_id, name_base, name_raw)
VALUES ('ee000000-0000-4000-8000-0000000000e1',
        'aa000000-0000-4000-8000-0000000000a1', 'Thuốc thử', 'Thuốc thử')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.drug_batch
    (id, clinic_id, drug_catalog_id, batch_code, expiry_date,
     quantity_on_hand, unit)
VALUES ('ff000000-0000-4000-8000-0000000000f1',
        'aa000000-0000-4000-8000-0000000000a1',
        'ee000000-0000-4000-8000-0000000000e1', 'LO-1',
        DATE '2030-01-01', 30, 'viên')
ON CONFLICT (id) DO NOTHING;


DO $guards$
DECLARE
    v_lot boolean;
    v_ton numeric;
BEGIN
    -- ── 1. Ca hợp lệ phải ĐI QUA ───────────────────────────────────────────
    --
    -- Kiểm cái này TRƯỚC. Bốn bài dưới đều khẳng định "phải chặn", và một
    -- ràng buộc chặn TẤT CẢ cũng làm cả bốn xanh — kể cả khi nó khoá luôn
    -- việc cấp thuốc bình thường.
    INSERT INTO public.inventory_txn
        (clinic_id, drug_batch_id, txn_type, quantity, performed_by_staff_id)
    VALUES ('aa000000-0000-4000-8000-0000000000a1',
            'ff000000-0000-4000-8000-0000000000f1', 'DISPENSE', -10,
            'dd000000-0000-4000-8000-0000000000d1');

    SELECT quantity_on_hand INTO v_ton
      FROM public.drug_batch WHERE id = 'ff000000-0000-4000-8000-0000000000f1';
    IF v_ton <> 20 THEN
        RAISE EXCEPTION 'cấp 10 từ lô 30 phải còn 20, đang là %', v_ton;
    END IF;

    -- ── 2. Tồn kho không âm ────────────────────────────────────────────────
    v_lot := true;
    BEGIN
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity,
             performed_by_staff_id)
        VALUES ('aa000000-0000-4000-8000-0000000000a1',
                'ff000000-0000-4000-8000-0000000000f1', 'DISPENSE', -50,
                'dd000000-0000-4000-8000-0000000000d1');
    EXCEPTION WHEN check_violation THEN
        v_lot := false;
    END;
    IF v_lot THEN
        RAISE EXCEPTION
            'xuất 50 khỏi lô còn 20 VẪN LỌT — tồn kho âm được, và mọi màn hình '
            'sẽ hiển thị con số ấy như thật';
    END IF;

    -- ── 3. Sổ kho chỉ ghi thêm ─────────────────────────────────────────────
    v_lot := true;
    BEGIN
        UPDATE public.inventory_txn SET quantity = 999
         WHERE clinic_id = 'aa000000-0000-4000-8000-0000000000a1';
    EXCEPTION WHEN insufficient_privilege THEN
        v_lot := false;
    END;
    IF v_lot THEN
        RAISE EXCEPTION
            'SỬA được dòng sổ kho — trigger không chạy lại, nên tồn kho và sổ '
            'lệch nhau vĩnh viễn mà không dòng nào nói đã có người sửa';
    END IF;

    v_lot := true;
    BEGIN
        DELETE FROM public.inventory_txn
         WHERE clinic_id = 'aa000000-0000-4000-8000-0000000000a1';
    EXCEPTION WHEN insufficient_privilege THEN
        v_lot := false;
    END;
    IF v_lot THEN
        RAISE EXCEPTION 'XOÁ được dòng sổ kho';
    END IF;

    -- ── 4. Thao tác tay phải nói ai làm ────────────────────────────────────
    v_lot := true;
    BEGIN
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity, ref_type)
        VALUES ('aa000000-0000-4000-8000-0000000000a1',
                'ff000000-0000-4000-8000-0000000000f1', 'RECEIVE', 5, 'manual');
    EXCEPTION WHEN check_violation THEN
        v_lot := false;
    END;
    IF v_lot THEN
        RAISE EXCEPTION
            'ghi kho bằng tay mà không gắn nhân viên nào VẪN LỌT — lúc có sự '
            'cố sẽ không trả lời được câu duy nhất đáng hỏi';
    END IF;

    -- ── 5. Không trừ kho vượt biên phòng khám ──────────────────────────────
    --
    -- Đây là lỗ đã mở thật trên prod trước 20260805000003.
    v_lot := true;
    BEGIN
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity,
             performed_by_staff_id)
        VALUES ('bb000000-0000-4000-8000-0000000000b1',   -- phòng khám B
                'ff000000-0000-4000-8000-0000000000f1',   -- lô của A
                'DISPENSE', -5, 'dd000000-0000-4000-8000-0000000000d1');
    EXCEPTION WHEN foreign_key_violation THEN
        v_lot := false;
    END;
    IF v_lot THEN
        RAISE EXCEPTION
            'phòng khám B trừ được kho của phòng khám A — service_role bỏ qua '
            'RLS, nên chốt phải nằm trong DB';
    END IF;

    SELECT quantity_on_hand INTO v_ton
      FROM public.drug_batch WHERE id = 'ff000000-0000-4000-8000-0000000000f1';
    IF v_ton <> 20 THEN
        RAISE EXCEPTION
            'kho của A đổi thành % sau những lần ghi lẽ ra bị chặn', v_ton;
    END IF;

    RAISE NOTICE 'chốt ghi kho: năm tính chất đều đúng';
END
$guards$;


DO $fk_va_check_khong_danh_nhau$
BEGIN
    -- FK `ON DELETE SET NULL` cộng với CHECK cấm NULL là hai luật khoá chết
    -- nhau: xoá một nhân viên đã ghi sổ tay sẽ ném ra một lỗi về bảng KHO trong
    -- lúc người vận hành đang xoá NHÂN SỰ. Kiểm ở đây còn hơn để họ gặp nó lúc
    -- 8h sáng.
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.inventory_txn'::regclass
           AND contype = 'f'
           AND confrelid = 'public.staff'::regclass
           AND confdeltype <> 'r'
    ) THEN
        RAISE EXCEPTION
            'FK inventory_txn -> staff phải là ON DELETE RESTRICT';
    END IF;
END
$fk_va_check_khong_danh_nhau$;

ROLLBACK;
