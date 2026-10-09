-- QUẦY THUỐC BÁN THEO ĐƠN CŨ (09/10/2026).
--
-- Khách cũ quay lại quầy chỉ để mua tiếp thuốc của lần khám trước. Lượt bán lẻ
-- (`visit.ban_le`, mig 20260930600000) giờ ghi được nó bán THEO ĐƠN của lượt
-- khám nào: `don_goc_visit_id`. Nhờ nối này, "số đã mua" của đơn gốc cộng được
-- cả các lần mua lẻ sau (ban_theo_don_service), và báo cáo về sau biết lần bán
-- nào bám đơn bác sĩ nào.
--
-- Bất biến ép Ở ĐÂY (SO-LUAT Phần 6):
--   * chỉ lượt BÁN LẺ mới mang đơn gốc, và không tự trỏ chính mình (CHECK);
--   * đơn gốc là lượt KHÁM (không phải bán lẻ) của CHÍNH khách đó, cùng phòng
--     khám (trigger — CHECK không nhìn sang dòng khác được).
-- Gỡ nối (hoàn tác) = đặt về NULL; luôn hợp lệ.
--
-- Chạy lại nhiều lần được.

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS don_goc_visit_id uuid
        REFERENCES public.visit (visit_id) ON DELETE SET NULL;

COMMENT ON COLUMN public.visit.don_goc_visit_id IS
  'Lượt bán lẻ bán theo đơn thuốc của lượt KHÁM nào (09/10/2026). NULL = bán '
  'không theo đơn. Chỉ lượt ban_le mới có; gỡ được khi tiền thuốc chưa thu.';

DO $ck$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'visit_don_goc_chi_ban_le'
           AND conrelid = 'public.visit'::regclass
    ) THEN
        ALTER TABLE public.visit
            ADD CONSTRAINT visit_don_goc_chi_ban_le CHECK (
                don_goc_visit_id IS NULL
                OR (ban_le AND don_goc_visit_id <> visit_id)
            );
    END IF;
END
$ck$;

CREATE OR REPLACE FUNCTION public.visit_don_goc_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.don_goc_visit_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.visit g
         WHERE g.visit_id = NEW.don_goc_visit_id
           AND g.clinic_id = NEW.clinic_id
           AND g.clinic_patient_id = NEW.clinic_patient_id
           AND NOT g.ban_le
    ) THEN
        RAISE EXCEPTION 'Đơn gốc phải là lượt khám của chính khách này'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_visit_don_goc_guard ON public.visit;
CREATE TRIGGER trg_visit_don_goc_guard
    BEFORE INSERT OR UPDATE OF don_goc_visit_id ON public.visit
    FOR EACH ROW EXECUTE FUNCTION public.visit_don_goc_guard();

-- "Đã mua" của một đơn gốc = lần thu ở chính lượt gốc + mọi lượt bán lẻ nối về nó.
CREATE INDEX IF NOT EXISTS idx_visit_don_goc
    ON public.visit (clinic_id, don_goc_visit_id)
 WHERE don_goc_visit_id IS NOT NULL;
