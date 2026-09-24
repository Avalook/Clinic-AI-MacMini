-- Chốt chống phủ trùng: chặn cả khi TRÙNG TRONG CÙNG một lần thu (review
-- PR #178, 22/09/2026).
--
-- Bản 20260922000003 loại chính lần thu đang chèn
-- (`bl.payment_cycle_id <> NEW.payment_cycle_id`), nên một người ghi khác vẫn
-- chụp được cùng tiền khám / cùng chỉ định HAI LẦN trong một lần thu. Dấu vết
-- tiền phải duy nhất theo NGUỒN, bất kể cùng hay khác lần thu.
--
-- Trong BEFORE INSERT, dòng mới chưa tồn tại — không cần loại gì: dòng cùng
-- nguồn đã chèn trước đó (kể cả trong cùng giao dịch / cùng lần thu) sẽ thấy và
-- bị chặn. Phạm vi giữ nguyên: chỉ dòng PHÒNG KHÁM thu, nguồn service_order /
-- exam; không đụng dòng thuốc (prescription) hay dòng đối tác.
--
-- Chỉ thay thân hàm; trigger giữ nguyên. Không sửa migration cũ. Chạy lại được.

CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam') THEN
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'payment_bill_line_phu|' || NEW.clinic_id::text || '|' || NEW.source_type
        || '|' || NEW.source_id, 0));
    SELECT bl.payment_cycle_id INTO trung
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
     WHERE bl.clinic_id = NEW.clinic_id
       AND bl.source_type = NEW.source_type
       AND bl.source_id = NEW.source_id
       AND bl.billing_owner = 'CLINIC'
       AND (c.status = 'PENDING_VERIFICATION' OR c.paid_at IS NOT NULL)
     LIMIT 1;
    IF trung IS NOT NULL THEN
        RAISE EXCEPTION
            'payment_bill_line: % % đã nằm trong lần thu % — không thu hai lần',
            NEW.source_type, NEW.source_id, trung
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'payment_bill_line_mot_lan_phu';
    END IF;
    RETURN NEW;
END $$;
