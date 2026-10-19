-- G4e · Phiếu dịch vụ hoàn tác đã trả khách; không được tạo thêm khoản hoàn.
-- Thuốc giữ CP5: có thể hoàn trên phiếu đã huỷ vì thuốc có quy trình riêng.

CREATE OR REPLACE FUNCTION public.payment_service_refund_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trang_thai_lan text;
BEGIN
    IF TG_OP NOT IN ('INSERT', 'UPDATE')
       OR NEW.kind IS DISTINCT FROM 'dich_vu'
       OR NEW.status NOT IN ('PENDING', 'COMPLETED') THEN
        RETURN NEW;
    END IF;

    SELECT status INTO trang_thai_lan
      FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.payment_cycle_id
       AND clinic_id = NEW.clinic_id
       AND kind = 'dich_vu'
     FOR UPDATE;

    IF trang_thai_lan IS DISTINCT FROM 'PAID' THEN
        RAISE EXCEPTION 'Không hoàn tiền dịch vụ trên phiếu đã hoàn tác'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_payment_service_refund_guard
    ON public.payment_refund;
CREATE TRIGGER trg_payment_service_refund_guard
    BEFORE INSERT OR UPDATE ON public.payment_refund
    FOR EACH ROW EXECUTE FUNCTION public.payment_service_refund_guard();

CREATE OR REPLACE FUNCTION public.payment_cycle_service_refund_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.kind = 'dich_vu' AND OLD.status = 'PAID' AND NEW.status = 'VOIDED'
       AND EXISTS (
           SELECT 1
             FROM public.payment_refund r
            WHERE r.clinic_id = OLD.clinic_id
              AND r.payment_cycle_id = OLD.payment_cycle_id
              AND r.kind = 'dich_vu'
              AND r.status IN ('PENDING', 'COMPLETED')
       ) THEN
        RAISE EXCEPTION 'Không hoàn tác phiếu dịch vụ còn khoản hoàn tiền'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_payment_cycle_service_refund_guard
    ON public.payment_cycle;
CREATE TRIGGER trg_payment_cycle_service_refund_guard
    BEFORE UPDATE OF status ON public.payment_cycle
    FOR EACH ROW EXECUTE FUNCTION public.payment_cycle_service_refund_guard();
