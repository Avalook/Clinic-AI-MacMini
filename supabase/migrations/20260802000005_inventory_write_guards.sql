-- INVENTORY WRITE GUARDS — hai bất biến mà đường ghi kho phải đứng lên trên.
--
-- `20260802000001` dựng bảng và trigger cộng dồn tồn kho, nhưng chưa ai ghi vào
-- nó bao giờ: màn /pharmacy là read-only. Trước khi mở đường ghi (B.3), hai
-- điều dưới đây phải do DATABASE giữ, không phải do service nhớ giữ. Service
-- vẫn kiểm và trả lỗi tử tế; hai ràng buộc này là cái lưới bên dưới, cho cả
-- những đường ghi chưa được viết.
--
-- 1. Tồn kho không âm.
--    `inventory_txn_apply()` cộng thẳng `quantity + quantity_on_hand` không hỏi
--    gì. Xuất 50 viên khỏi lô còn 30 sẽ cho ra -20: một con số vô nghĩa mà mọi
--    màn hình vẫn hiển thị bình thường, và không ai biết 20 viên kia đi đâu.
--    Sai lặng lẽ trong sổ kho là loại sai tệ nhất — nó chỉ lộ ra lúc kiểm kê,
--    hàng tháng sau, khi không còn cách nào truy lại.
--
-- 2. Sổ kho không sửa được.
--    `inventory_txn` là sổ cái: `quantity_on_hand` chỉ là tổng của nó. Sửa một
--    dòng txn cũ thì trigger không chạy lại, tồn kho và sổ lệch nhau vĩnh viễn
--    mà không dòng nào nói đã có người sửa. Nhập nhầm thì ghi một dòng ADJUST
--    kèm lý do — đúng cách một cuốn sổ kho được sửa ngoài đời.

-- ---------------------------------------------------------------------------
-- 1. Tồn kho không âm
-- ---------------------------------------------------------------------------

-- Dọn trước cho chắc: nếu môi trường nào đã kịp ghi âm (chưa có, nhưng migration
-- phải chạy được trên mọi DB), đưa về 0 và ghi lại dấu vết bằng một dòng ADJUST
-- thay vì để ALTER TABLE gãy giữa chừng.
DO $$
DECLARE
    negative_batches int;
BEGIN
    SELECT count(*) INTO negative_batches
      FROM public.drug_batch WHERE quantity_on_hand < 0;

    IF negative_batches > 0 THEN
        RAISE EXCEPTION
            'Có % lô thuốc đang âm tồn. Sửa bằng ADJUST rồi chạy lại migration '
            'này — không tự nắn số trong migration, vì nắn xong thì không ai '
            'biết đã từng âm.', negative_batches;
    END IF;
END
$$;

ALTER TABLE public.drug_batch DROP CONSTRAINT IF EXISTS drug_batch_qty_non_negative;
ALTER TABLE public.drug_batch ADD CONSTRAINT drug_batch_qty_non_negative
    CHECK (quantity_on_hand >= 0);

-- ---------------------------------------------------------------------------
-- 2. inventory_txn append-only
-- ---------------------------------------------------------------------------

-- `event_log_append_only_guard()` (baseline) chỉ RAISE với TG_TABLE_NAME/TG_OP —
-- không dính gì tới event_log ngoài cái tên, nên dùng lại được nguyên vẹn.
DROP TRIGGER IF EXISTS inventory_txn_append_only ON public.inventory_txn;
CREATE TRIGGER inventory_txn_append_only
    BEFORE UPDATE OR DELETE ON public.inventory_txn
    FOR EACH ROW EXECUTE FUNCTION public.event_log_append_only_guard();

-- ---------------------------------------------------------------------------
-- 3. Mọi biến động tồn kho phải nói ai làm
-- ---------------------------------------------------------------------------

-- `performed_by_staff_id` đang nullable. Cấp thuốc mà không biết ai cấp thì
-- không trả lời được câu hỏi duy nhất đáng hỏi khi có sự cố. Không đặt NOT NULL
-- (nhập liệu tự động sau này có thể không có người), nhưng ràng buộc: đã là
-- thao tác tay (ref_type IS NULL hoặc 'manual') thì phải có người.
ALTER TABLE public.inventory_txn DROP CONSTRAINT IF EXISTS inventory_txn_manual_needs_actor;
ALTER TABLE public.inventory_txn ADD CONSTRAINT inventory_txn_manual_needs_actor
    CHECK (
        (ref_type IS NOT NULL AND ref_type <> 'manual')
        OR performed_by_staff_id IS NOT NULL
    );

COMMENT ON CONSTRAINT drug_batch_qty_non_negative ON public.drug_batch IS
    'Tồn kho không âm. Trigger inventory_txn_apply() cộng thẳng, không tự kiểm.';
COMMENT ON CONSTRAINT inventory_txn_manual_needs_actor ON public.inventory_txn IS
    'Thao tác kho bằng tay phải gắn với một nhân viên.';
