-- Assertions for 20260802000005_inventory_write_guards.sql (B.3).
--   psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/inventory_write_guards.sql
--
-- Kho thuốc là một cuốn sổ kép: `inventory_txn` là sổ, `drug_batch
-- .quantity_on_hand` là số dư, và trigger giữ hai bên khớp nhau. Ba điều dưới
-- đây phải do DATABASE giữ chứ không phải do service nhớ giữ — vì `PharmacyService`
-- không phải là thứ duy nhất sẽ ghi vào hai bảng này mãi mãi.

BEGIN;

DO $shape$
DECLARE
    non_negative_check text;
    actor_check text;
    append_only_triggers integer;
BEGIN
    SELECT pg_get_constraintdef(c.oid)
      INTO non_negative_check
      FROM pg_constraint c
     WHERE c.conrelid = 'public.drug_batch'::regclass
       AND c.conname = 'drug_batch_qty_non_negative';

    IF non_negative_check IS NULL THEN
        RAISE EXCEPTION 'drug_batch has no non-negative stock constraint';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
      INTO actor_check
      FROM pg_constraint c
     WHERE c.conrelid = 'public.inventory_txn'::regclass
       AND c.conname = 'inventory_txn_manual_needs_actor';

    IF actor_check IS NULL THEN
        RAISE EXCEPTION 'inventory_txn does not require an actor for manual work';
    END IF;

    -- BEFORE UPDATE OR DELETE = hai dòng trong pg_trigger cho cùng một tên.
    SELECT count(*)
      INTO append_only_triggers
      FROM pg_trigger t
     WHERE t.tgrelid = 'public.inventory_txn'::regclass
       AND t.tgname = 'inventory_txn_append_only'
       AND NOT t.tgisinternal;

    IF append_only_triggers = 0 THEN
        RAISE EXCEPTION 'inventory_txn is not append-only';
    END IF;
END
$shape$;

-- Fixtures — cuộn lại cùng transaction.
INSERT INTO auth.users (id) VALUES ('10000000-0000-0000-0000-0000000000b1');

INSERT INTO public.staff (id, full_name, primary_department, auth_user_id)
VALUES (
    '20000000-0000-0000-0000-0000000000b1',
    'Dược sĩ kiểm thử',
    'PHARMACIST',
    '10000000-0000-0000-0000-0000000000b1'
);

INSERT INTO public.drug_catalog (id, clinic_id, name_base, name_raw)
VALUES (
    '50000000-0000-0000-0000-0000000000b1',
    'a0000000-0000-4000-8000-000000000001',
    'Paracetamol',
    'Paracetamol 500mg'
);

INSERT INTO public.drug_batch (
    id, clinic_id, drug_catalog_id, batch_code, expiry_date, unit
)
VALUES (
    '60000000-0000-0000-0000-0000000000b1',
    'a0000000-0000-4000-8000-000000000001',
    '50000000-0000-0000-0000-0000000000b1',
    'LOT-TEST-B1',
    CURRENT_DATE + 180,
    'viên'
);

-- Lô mới sinh ra rỗng: mọi số dư phải truy được về một dòng sổ.
DO $new_batch_starts_empty$
DECLARE
    on_hand numeric;
BEGIN
    SELECT quantity_on_hand INTO on_hand
      FROM public.drug_batch WHERE id = '60000000-0000-0000-0000-0000000000b1';
    IF on_hand <> 0 THEN
        RAISE EXCEPTION 'new batch started at % instead of 0', on_hand;
    END IF;
END
$new_batch_starts_empty$;

INSERT INTO public.inventory_txn (
    clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
    performed_by_staff_id
)
VALUES (
    'a0000000-0000-4000-8000-000000000001',
    '60000000-0000-0000-0000-0000000000b1',
    'RECEIVE', 100, 'Nhập hàng kiểm thử', 'manual',
    '20000000-0000-0000-0000-0000000000b1'
);

DO $trigger_keeps_the_balance$
DECLARE
    on_hand numeric;
BEGIN
    SELECT quantity_on_hand INTO on_hand
      FROM public.drug_batch WHERE id = '60000000-0000-0000-0000-0000000000b1';
    IF on_hand <> 100 THEN
        RAISE EXCEPTION 'stock is % after receiving 100', on_hand;
    END IF;
END
$trigger_keeps_the_balance$;

DO $cannot_dispense_more_than_on_hand$
DECLARE
    failing_constraint text;
BEGIN
    BEGIN
        INSERT INTO public.inventory_txn (
            clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
            performed_by_staff_id
        )
        VALUES (
            'a0000000-0000-4000-8000-000000000001',
            '60000000-0000-0000-0000-0000000000b1',
            'DISPENSE', -101, 'Xuất quá tồn', 'manual',
            '20000000-0000-0000-0000-0000000000b1'
        );
        RAISE EXCEPTION 'stock went negative and nobody noticed';
    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS failing_constraint = CONSTRAINT_NAME;
    END;

    -- Nêu tên ràng buộc, vì `inventory_txn_qty_sign_check` cũng chặn được vài
    -- dòng sai và sẽ làm test này xanh trong khi tồn kho vẫn âm được.
    IF failing_constraint <> 'drug_batch_qty_non_negative' THEN
        RAISE EXCEPTION 'blocked by % instead of the non-negative rule',
            failing_constraint;
    END IF;
END
$cannot_dispense_more_than_on_hand$;

DO $ledger_cannot_be_rewritten$
BEGIN
    BEGIN
        UPDATE public.inventory_txn
           SET quantity = 999
         WHERE drug_batch_id = '60000000-0000-0000-0000-0000000000b1';
        RAISE EXCEPTION 'a past stock movement was edited';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'a past stock movement was edited' THEN
                RAISE;
            END IF;
    END;

    BEGIN
        DELETE FROM public.inventory_txn
         WHERE drug_batch_id = '60000000-0000-0000-0000-0000000000b1';
        RAISE EXCEPTION 'a past stock movement was deleted';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'a past stock movement was deleted' THEN
                RAISE;
            END IF;
    END;
END
$ledger_cannot_be_rewritten$;

DO $manual_work_needs_a_person$
BEGIN
    BEGIN
        INSERT INTO public.inventory_txn (
            clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
            performed_by_staff_id
        )
        VALUES (
            'a0000000-0000-4000-8000-000000000001',
            '60000000-0000-0000-0000-0000000000b1',
            'ADJUST', -5, 'Kiểm kê', 'manual', NULL
        );
        RAISE EXCEPTION 'stock moved by hand with nobody attached';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    -- Cùng dòng đó nhưng không ghi ref_type: vẫn là thao tác tay, vẫn phải có người.
    BEGIN
        INSERT INTO public.inventory_txn (
            clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
            performed_by_staff_id
        )
        VALUES (
            'a0000000-0000-4000-8000-000000000001',
            '60000000-0000-0000-0000-0000000000b1',
            'ADJUST', -5, 'Kiểm kê', NULL, NULL
        );
        RAISE EXCEPTION 'a NULL ref_type dodged the actor rule';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END
$manual_work_needs_a_person$;

-- Đường máy: nhập liệu tự động (POS, đối soát) chưa có người bấm nút. Cấm luôn
-- cả nhóm này nghĩa là những đường ghi đó buộc phải bịa ra một nhân viên.
INSERT INTO public.inventory_txn (
    clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type, ref_id,
    performed_by_staff_id
)
VALUES (
    'a0000000-0000-4000-8000-000000000001',
    '60000000-0000-0000-0000-0000000000b1',
    'DISPENSE', -10, 'Đồng bộ từ POS', 'pos_sync',
    '70000000-0000-0000-0000-0000000000b1', NULL
);

DO $final_balance$
DECLARE
    on_hand numeric;
BEGIN
    SELECT quantity_on_hand INTO on_hand
      FROM public.drug_batch WHERE id = '60000000-0000-0000-0000-0000000000b1';
    IF on_hand <> 90 THEN
        RAISE EXCEPTION 'balance is % after +100 and -10', on_hand;
    END IF;
END
$final_balance$;

ROLLBACK;
