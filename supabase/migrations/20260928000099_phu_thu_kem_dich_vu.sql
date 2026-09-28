-- PHỤ THU KÈM DỊCH VỤ — tick "thêm đầu dò" ở THU TIỀN DỊCH VỤ (Tuyền 28/09/2026).
--
-- "Thêm ô tick vào thu dịch vụ là thêm đầu dò và điền được giá vào." Phòng
-- khám: "Tập máy Bio điều trị (chưa bao gồm đầu dò)" (SP000146), "Đo trương lực
-- cơ sàn chậu máy Bio (ko bao gồm đầu dò)" (SP000145) — khách mua đầu dò Bio
-- (SP000152 1 lần 300.000đ / SP000153 nhiều lần 900.000đ) thu CÙNG tiền dịch
-- vụ. Kho gắn sau (không trừ kho ở đây).
--
-- 1. `phu_thu_mau`: dịch vụ (bảng giá) → món kèm chọn được + giá mặc định.
-- 2. `luot_phu_thu`: món kèm đã tick cho MỘT chỉ định, giá đã chốt (sửa được
--    trước khi thu). Bỏ tick = đóng dấu, không xoá.
-- 3. Hoá đơn: loại dòng mới `phu_thu` — cùng chốt "không thu hai lần" với tiền
--    khám / chỉ định (`payment_bill_line_mot_lan_phu`).
--
-- Chạy lại được.

ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_source_type_check;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_source_type_check
    CHECK (source_type = ANY (ARRAY['exam', 'service_order', 'prescription',
                                    'phu_thu']));

CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam', 'phu_thu') THEN
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

CREATE TABLE IF NOT EXISTS public.phu_thu_mau (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_price_id uuid NOT NULL REFERENCES public.service_price(id)
                         ON DELETE CASCADE,
    ten              text NOT NULL,
    gia_mac_dinh     numeric CHECK (gia_mac_dinh IS NULL OR gia_mac_dinh >= 0),
    drug_catalog_id  uuid REFERENCES public.drug_catalog(id) ON DELETE SET NULL,
    thu_tu           integer NOT NULL DEFAULT 0,
    active           boolean NOT NULL DEFAULT true,
    CONSTRAINT phu_thu_mau_mot_ten UNIQUE (clinic_id, service_price_id, ten)
);

COMMENT ON TABLE public.phu_thu_mau IS
'Món kèm chọn được của một dịch vụ (vd đầu dò Bio kèm Tập máy Bio) + giá mặc định. 28/09/2026.';

INSERT INTO public.phu_thu_mau
    (clinic_id, service_price_id, ten, gia_mac_dinh, drug_catalog_id, thu_tu)
SELECT sp.clinic_id, sp.id, v.ten, v.gia,
       (SELECT d.id FROM public.drug_catalog d
         WHERE d.clinic_id = sp.clinic_id AND d.ma_hang = v.ma_kho
         ORDER BY d.is_active DESC, d.created_at LIMIT 1),
       v.thu_tu
  FROM public.service_price sp
 CROSS JOIN (VALUES
       ('Đầu dò Bio 1 lần', 300000::numeric, 'SP000152', 1),
       ('Đầu dò Bio nhiều lần', 900000::numeric, 'SP000153', 2)
     ) AS v(ten, gia, ma_kho, thu_tu)
 WHERE sp.ma_kiotviet IN ('SP000145', 'SP000146') AND sp.active
ON CONFLICT (clinic_id, service_price_id, ten) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.luot_phu_thu (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    service_order_id uuid NOT NULL REFERENCES public.service_order(id)
                         ON DELETE RESTRICT,
    phu_thu_mau_id   uuid NOT NULL REFERENCES public.phu_thu_mau(id)
                         ON DELETE RESTRICT,
    ten              text NOT NULL,
    don_gia          numeric NOT NULL CHECK (don_gia >= 0),
    chon_boi         uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    chon_luc         timestamptz NOT NULL DEFAULT now(),
    bo_boi           uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    bo_luc           timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS luot_phu_thu_mot_dong_song
    ON public.luot_phu_thu (clinic_id, service_order_id, phu_thu_mau_id)
    WHERE bo_luc IS NULL;
CREATE INDEX IF NOT EXISTS luot_phu_thu_theo_luot
    ON public.luot_phu_thu (clinic_id, visit_id);

COMMENT ON TABLE public.luot_phu_thu IS
'Món kèm đã tick cho một chỉ định + giá chốt (sửa được trước khi thu). Thu cùng tiền dịch vụ (payment_bill_line.source_type = phu_thu).';

ALTER TABLE public.phu_thu_mau ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.luot_phu_thu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS phu_thu_mau_select_own_clinic ON public.phu_thu_mau;
CREATE POLICY phu_thu_mau_select_own_clinic ON public.phu_thu_mau
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS luot_phu_thu_select_own_clinic ON public.luot_phu_thu;
CREATE POLICY luot_phu_thu_select_own_clinic ON public.luot_phu_thu
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.phu_thu_mau TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.luot_phu_thu TO service_role;
