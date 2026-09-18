-- KHÁCH ƯU TIÊN LÀ CỜ TRÊN HỒ SƠ + LỄ TÂN KÉO THỨ TỰ KHÁM (15/09/2026).
--
-- LUẬT (Tuyền chốt 15/09 tối): "giờ chả có ghế ưu tiên gì cả đâu, bỏ đi". Thay
-- bằng:
--   · hồ sơ khách nào ưu tiên/VIP thì ĐÁNH DẤU trên hồ sơ, kèm LÝ DO, để lễ tân
--     biết;
--   · khám vẫn theo thứ tự check-in, nhưng hôm nào cần thì lễ tân tự KÉO người
--     đó lên trước ai đó (theo chỉ đạo trưởng ca) — không luật nào tự đẩy.
--
-- Trước bản này: vé "ƯT…" từng tự chen lên đầu hàng (bỏ làn 15/09 sáng, còn
-- nhãn), cờ `appointment.is_priority_slot` không có đường ghi nào, và không có
-- cách nào đổi thứ tự bằng tay.
--
-- THỨ TỰ TAY LÀ MỘT MỐC, KHÔNG PHẢI SỐ THỨ TỰ. `visit.thu_tu_tay_ms` là mili
-- giây "coi như check-in lúc này": kéo X vào giữa A và B thì X nhận trung điểm
-- mốc của A và B. Không phải đánh số lại cả hàng, hai lễ tân kéo hai người
-- khác nhau không đè nhau, và người check-in sau đó vẫn tự đứng cuối.

ALTER TABLE public.patient
    ADD COLUMN IF NOT EXISTS uu_tien        boolean     NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS uu_tien_ly_do  text,
    ADD COLUMN IF NOT EXISTS uu_tien_boi    uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS uu_tien_luc    timestamptz;

ALTER TABLE public.patient DROP CONSTRAINT IF EXISTS patient_uu_tien_phai_co_ly_do;
ALTER TABLE public.patient ADD CONSTRAINT patient_uu_tien_phai_co_ly_do
    CHECK (NOT uu_tien OR length(btrim(coalesce(uu_tien_ly_do, ''))) > 0);

COMMENT ON COLUMN public.patient.uu_tien IS
    'Khách ưu tiên/VIP — chỉ là dấu cho lễ tân, không tự đổi thứ tự khám '
    '(20260915000016).';

ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS thu_tu_tay_ms   double precision,
    ADD COLUMN IF NOT EXISTS thu_tu_tay_boi  uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS thu_tu_tay_luc  timestamptz;

COMMENT ON COLUMN public.visit.thu_tu_tay_ms IS
    'Mốc xếp hàng do lễ tân kéo tay (epoch ms, thay giờ check-in khi xếp). NULL = '
    'theo giờ check-in (20260915000016).';
