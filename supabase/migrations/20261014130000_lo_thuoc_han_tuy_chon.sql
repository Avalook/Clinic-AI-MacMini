-- G3a: hạn có thể bổ sung sau.
ALTER TABLE public.drug_batch ALTER COLUMN expiry_date DROP NOT NULL;

-- Khoá cùng hàng lô với sửa hạn: không có cửa kiểm hạn xong rồi hạn bị đổi
-- trước lúc ghi sổ. Chỉ kiểm bán/giao, các bút toán hoàn/huỷ giữ nguyên.
CREATE OR REPLACE FUNCTION public.gac_lo_het_han() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
DECLARE han date;
BEGIN
    IF NEW.txn_type NOT IN ('SALE', 'DISPENSE') THEN RETURN NEW; END IF;
    SELECT expiry_date INTO han FROM public.drug_batch
     WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id FOR UPDATE;
    IF han < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date THEN
        RAISE EXCEPTION 'Lô này đã hết hạn — đổi lô hoặc hoàn phần chưa giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_het_han';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_gac_lo_het_han_gan ON public.prescription_allocation;
DROP TRIGGER IF EXISTS trg_gac_lo_het_han_so ON public.inventory_txn;
CREATE TRIGGER trg_gac_lo_het_han_so
BEFORE INSERT ON public.inventory_txn
FOR EACH ROW EXECUTE FUNCTION public.gac_lo_het_han();
NOTIFY pgrst, 'reload schema';
