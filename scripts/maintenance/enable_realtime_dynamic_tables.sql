-- Bật Supabase Realtime cho MỌI bảng động (dữ liệu đổi khi vận hành) để cả app
-- cập nhật tức thì qua RealtimeRefresher (app/(dashboard)/RealtimeRefresher.tsx).
-- Bỏ qua bảng tra cứu tĩnh (province/ward/service_type/service_price/drug_catalog/
-- booking_channel/clinic_location) — không đổi lúc vận hành nên không cần realtime.
--
-- Idempotent: chỉ ADD bảng CHƯA nằm trong publication `supabase_realtime`, nên
-- chạy lại nhiều lần không lỗi (vài bảng như appointment/visit/payment có thể đã
-- bật từ trước). Chạy trên CẢ fzw (dev) lẫn atf (prod).

DO $$
DECLARE
  t TEXT;
  dynamic_tables TEXT[] := ARRAY[
    'appointment',
    'visit',
    'patient',
    'work_roster',
    'staff_task',
    'payment',
    'prescription',
    'service_log',
    'lab_result',
    'cskh_action',
    'cskh_log',
    'clinical_record',
    'ultrasound_record',
    'clinical_form_response',
    'patient_medical_profile',
    'pregnancy',
    'work_session',
    'staff'
  ];
BEGIN
  FOREACH t IN ARRAY dynamic_tables LOOP
    -- Bảng phải tồn tại (DB có thể chưa apply hết migration) và chưa ở publication.
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = t
    ) AND NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = t
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t);
      -- REPLICA IDENTITY FULL: để sự kiện DELETE/UPDATE mang đủ dữ liệu cũ (cần cho
      -- filter realtime như staff_id=eq.* trong RosterNotifier). An toàn, idempotent.
      EXECUTE format('ALTER TABLE public.%I REPLICA IDENTITY FULL', t);
    END IF;
  END LOOP;
END $$;
