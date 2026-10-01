-- Tách hẳn tiền thuốc và tiền dịch vụ ở sổ thu (Tuyền 01/10/2026):
-- "không cho node thuốc thu hộ tiền dịch vụ" — thuốc và dịch vụ thu RIÊNG HẲN.
--
-- Mỗi lần thu (`payment_cycle`) đã chỉ có MỘT loại (`kind`), nhưng dòng hoá đơn
-- chụp lúc thu (`payment_bill_line`) chưa có ràng buộc loại dòng ↔ loại lần thu:
-- một lỗi code ghi dòng thuốc vào lần thu dịch vụ (hay ngược lại) sẽ lọt vào sổ
-- và hiện lẫn ở phiếu thu / báo cáo. Ràng buộc này ép ở Postgres (SO-LUAT Phần 6):
--
--   kind = 'thuoc'   ⇔ source_type = 'prescription'
--   kind = 'dich_vu' ⇔ source_type IN ('exam', 'service_order', 'phu_thu')
--
-- Và dòng phải cùng loại với LẦN THU chứa nó (`payment_cycle.kind`): trigger bên
-- dưới (CHECK không nhìn sang bảng khác được). Lần thu chưa có (ghi dòng trước
-- lần thu) thì để qua — chỉ chặn khi CÓ lần thu và loại khác nhau.
--
-- NOT VALID: chỉ canh dòng GHI MỚI; dòng cũ giữ nguyên (sổ chỉ thêm, không sửa
-- lịch sử). Kiểm dòng cũ có lệch không (kỳ vọng 0):
--   SELECT kind, source_type, count(*) FROM payment_bill_line
--    WHERE NOT ((kind = 'thuoc' AND source_type = 'prescription')
--            OR (kind = 'dich_vu' AND source_type IN ('exam','service_order','phu_thu')))
--    GROUP BY 1, 2;
--
-- Chạy lại được.

CREATE OR REPLACE FUNCTION public.payment_bill_line_khop_loai_lan_thu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    loai_lan text;
BEGIN
    SELECT c.kind INTO loai_lan
      FROM public.payment_cycle c
     WHERE c.clinic_id = NEW.clinic_id
       AND c.payment_cycle_id = NEW.payment_cycle_id;
    IF loai_lan IS NOT NULL AND loai_lan <> NEW.kind THEN
        RAISE EXCEPTION
            'Dòng hoá đơn % không được nằm trong lần thu % — thuốc và dịch vụ thu riêng hẳn',
            NEW.kind, loai_lan
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_payment_bill_line_khop_loai_lan_thu
    ON public.payment_bill_line;
CREATE TRIGGER trg_payment_bill_line_khop_loai_lan_thu
    BEFORE INSERT ON public.payment_bill_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_bill_line_khop_loai_lan_thu();

ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_kind_khop_nguon;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_kind_khop_nguon
    CHECK (
        (kind = 'thuoc' AND source_type = 'prescription')
        OR (kind = 'dich_vu'
            AND source_type IN ('exam', 'service_order', 'phu_thu'))
    ) NOT VALID;

COMMENT ON CONSTRAINT payment_bill_line_kind_khop_nguon
    ON public.payment_bill_line IS
    'Tiền thuốc và tiền dịch vụ thu riêng hẳn (01/10/2026): dòng thuốc chỉ nằm trong lần thu thuốc, dòng khám / chỉ định / phụ thu chỉ nằm trong lần thu dịch vụ. NOT VALID — canh dòng ghi mới, không đụng lịch sử.';
