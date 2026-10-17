-- THUỐC KHÁCH TRẢ: LỆNH QUYẾT ĐỊNH XỬ LÝ (17/10/2026, kế hoạch KE-HOACH-QUY-DOI-DON-VI-VA-THUOC-TRA, việc B).
--
-- Hiện trạng (CP5, 19/09): khách trả thuốc → sổ kho `RETURN_RECEIVED` (+tồn vật lý) và
-- `drug_return.disposition = NULL` ("đã nhận lại, CHƯA quyết"). Phần ấy bị TRỪ khỏi
-- `drug_batch_kha_dung()` nên không tự bán lại — nhưng không có lệnh nào quyết, vì trigger
-- `drug_return_guard` cấm mọi UPDATE (HOLD J1/J2). Thuốc nằm ở đó vĩnh viễn.
--
-- Nay cho ĐÚNG MỘT quyết định, một lần, không sửa lại:
--   BAN_LAI — nhập lại bán được: chỉ đặt quyết định; `drug_batch_kha_dung` thôi trừ phần này.
--   HUY     — huỷ: đặt quyết định VÀ trỏ tới dòng sổ DISCARD (tồn vật lý giảm) cùng giao dịch.
-- Mọi sửa khác, mọi xoá, mọi sửa lần hai vẫn bị chặn ở Postgres.
--
-- Chỉ THÊM (4 cột nullable + ràng buộc + nới trigger + GRANT UPDATE theo cột). Không đụng dòng cũ.
-- Hoàn tác (trước khi có quyết định nào): khôi phục `drug_return_guard` ở
-- 20260919000004_tien_thuoc_cp5_hoan_tra.sql, rồi DROP COLUMN 4 cột mới.
--
-- Chạy lại được, không BEGIN/COMMIT.

ALTER TABLE public.drug_return
    ADD COLUMN IF NOT EXISTS disposition_reason  text,
    ADD COLUMN IF NOT EXISTS disposition_txn_id  uuid;

ALTER TABLE public.drug_return DROP CONSTRAINT IF EXISTS drug_return_xu_ly_hop_le;
ALTER TABLE public.drug_return ADD CONSTRAINT drug_return_xu_ly_hop_le CHECK (
    -- Chưa quyết: không có gì kèm theo.
    (disposition IS NULL AND disposition_reason IS NULL AND disposition_txn_id IS NULL)
    -- Bán lại: lý do tuỳ chọn, không có dòng huỷ.
    OR (disposition = 'BAN_LAI' AND disposition_txn_id IS NULL)
    -- Huỷ: BẮT lý do và BẮT có dòng DISCARD (huỷ mà tồn không giảm là sai sổ).
    OR (disposition = 'HUY' AND disposition_txn_id IS NOT NULL
        AND length(btrim(coalesce(disposition_reason, ''))) >= 3)
);

-- Dòng DISCARD phải là của đúng phòng khám và đúng LÔ của lần trả.
ALTER TABLE public.drug_return DROP CONSTRAINT IF EXISTS drug_return_huy_txn_fkey;
ALTER TABLE public.drug_return ADD CONSTRAINT drug_return_huy_txn_fkey
    FOREIGN KEY (disposition_txn_id, clinic_id, drug_batch_id)
    REFERENCES public.inventory_txn (id, clinic_id, drug_batch_id) ON DELETE RESTRICT;

-- Một dòng DISCARD chỉ phục vụ một lần trả.
CREATE UNIQUE INDEX IF NOT EXISTS uq_drug_return_huy_txn
    ON public.drug_return (disposition_txn_id) WHERE disposition_txn_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.drug_return_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    xuat record;
    da_tra numeric;
    cot_xu_ly text[] := ARRAY['disposition', 'disposition_by', 'disposition_at',
                              'disposition_reason', 'disposition_txn_id'];
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'drug_return: không xoá lần khách trả thuốc'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Quyết định xử lý: ĐÚNG MỘT lần, chuyển NULL → BAN_LAI | HUY, người quyết là
        -- nhân sự đang hoạt động của phòng khám. Mọi cột khác bất biến.
        IF OLD.disposition IS NOT NULL THEN
            RAISE EXCEPTION 'drug_return: lần trả này đã xử lý (%) — không sửa lại', OLD.disposition
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.disposition IS NULL OR NEW.disposition NOT IN ('BAN_LAI', 'HUY') THEN
            RAISE EXCEPTION 'drug_return: quyết định xử lý phải là BAN_LAI hoặc HUY'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (to_jsonb(NEW) - cot_xu_ly) IS DISTINCT FROM (to_jsonb(OLD) - cot_xu_ly) THEN
            RAISE EXCEPTION 'drug_return: chỉ được đặt quyết định xử lý, không sửa cột khác'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.clinic_membership m
                        WHERE m.clinic_id = NEW.clinic_id AND m.staff_id = NEW.disposition_by
                          AND m.is_active) THEN
            RAISE EXCEPTION 'drug_return: người quyết không thuộc phòng khám'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO xuat FROM public.inventory_txn
     WHERE id = NEW.original_dispense_txn_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF xuat.txn_type IS DISTINCT FROM 'DISPENSE'
       OR xuat.ref_id IS DISTINCT FROM NEW.prescription_id
       OR xuat.allocation_id IS DISTINCT FROM NEW.allocation_id
       OR NEW.disposition IS NOT NULL
       -- Dòng đơn phải thuộc ĐÚNG lượt khai trên lần trả (lineage/audit).
       OR NOT EXISTS (SELECT 1 FROM public.prescription r
                       WHERE r.id = NEW.prescription_id AND r.clinic_id = NEW.clinic_id
                         AND r.visit_id = NEW.visit_id) THEN
        RAISE EXCEPTION 'Khách trả thuốc phải trỏ đúng DISPENSE gốc của dòng đơn'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(returned_qty), 0) INTO da_tra FROM public.drug_return
     WHERE original_dispense_txn_id = NEW.original_dispense_txn_id
       AND clinic_id = NEW.clinic_id;
    IF da_tra + NEW.returned_qty > -xuat.quantity THEN
        RAISE EXCEPTION 'Trả vượt số đã xuất (% + % > %)',
            da_tra, NEW.returned_qty, -xuat.quantity
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Backend chỉ được đặt các cột quyết định (không phải cả dòng).
GRANT UPDATE (disposition, disposition_by, disposition_at, disposition_reason,
              disposition_txn_id)
    ON public.drug_return TO service_role;

NOTIFY pgrst, 'reload schema';
