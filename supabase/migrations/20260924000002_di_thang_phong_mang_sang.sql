-- NHÓM 2 — dây H2 (Tuyền chốt 24/09/2026, docs/BAN-DO-DAY-NOI-LEGO.md "Bản chốt 24/09"):
--
--   H2  Check-in lịch THỦ THUẬT / SÀN CHẬU → không qua tư vấn, không qua bác sĩ
--       chính: chỉ định hẹn từ lượt trước MANG SANG lượt này, đã trả thì vào thẳng
--       hàng phòng, chưa trả thì chờ lễ tân thu (H4 xếp phòng sau khi thu).
--   Mọi lượt: chỉ định ĐÃ TRẢ TIỀN mà CHƯA LÀM ở lượt trước → mang sang, không thu lại.
--
-- Chạy lại được (IF NOT EXISTS).

-- 1. Loại lịch nào đi thẳng phòng — DÂY NGHIỆP VỤ, quản lý chỉnh được.
ALTER TABLE public.service_type
    ADD COLUMN IF NOT EXISTS di_thang_phong boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.service_type.di_thang_phong IS
'Check-in loại lịch này thì khách đi thẳng phòng làm chỉ định hẹn từ lượt trước, không qua tư vấn/bác sĩ chính, không tính tiền khám (dây H2). Quản lý chỉnh được.';

-- Thủ thuật đi thẳng phòng. Sàn chậu cũng vậy (Tuyền 24/09) — mã chưa có ở nhánh
-- này thì câu UPDATE không chạm dòng nào; quản lý bật trên màn khi thêm loại ấy.
UPDATE public.service_type
   SET di_thang_phong = true
 WHERE code IN ('THU_THUAT', 'SAN_CHAU')
   AND NOT di_thang_phong;

-- 2. Chỉ định mang sang từ lượt trước: giữ NGUỒN để kể lại được.
ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS mang_tu_visit_id uuid,
    ADD COLUMN IF NOT EXISTS mang_sang_luc timestamptz;

COMMENT ON COLUMN public.service_order.mang_tu_visit_id IS
'Lượt khám cũ mà chỉ định này được mang sang từ đó (chưa làm). NULL = chỉ định của chính lượt này.';

CREATE INDEX IF NOT EXISTS ix_service_order_mang_sang
    ON public.service_order (clinic_id, visit_id)
    WHERE mang_tu_visit_id IS NOT NULL;
