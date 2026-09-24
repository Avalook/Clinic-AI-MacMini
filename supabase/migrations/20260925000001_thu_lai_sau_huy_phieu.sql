-- Thu lại sau khi HUỶ phiếu dịch vụ (Tuyền chốt 24/09/2026).
--
-- Trước: một dòng tiền khám / chỉ định đã từng nằm trong lần thu ĐÃ NHẬN TIỀN
-- thì giữ phủ mãi, kể cả khi phiếu đã huỷ → thu nhầm, huỷ phiếu xong là lượt
-- treo, không thu lại được (FINANCE-GATE §16 "Chưa chốt"). Tiền thuốc thì
-- huỷ rồi thu lại được — hai khoản xử lý khác nhau.
--
-- Nay: chỉ lần thu ĐANG chờ xác minh hoặc ĐANG PAID mới giữ phủ. Phiếu đã
-- huỷ (VOIDED) được giữ nguyên để đối chiếu, bản mới nhất thắng. Phiếu có
-- hoàn tiền thì không huỷ được (chặn ở ``void_payment``), nên không có phiếu
-- huỷ nào mang khoản hoàn.
--
-- Cùng luật với bill_service._DA_PHU / finance_gate / service_selection_service.
-- Chạy lại được.

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
       AND c.status IN ('PENDING_VERIFICATION', 'PAID')
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
