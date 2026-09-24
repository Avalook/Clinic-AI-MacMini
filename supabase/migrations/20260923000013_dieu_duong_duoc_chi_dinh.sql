-- Điều dưỡng được đặt chỉ định (Tuyền chốt 23/09/2026).
--
-- Trong nghiệp vụ tạo chỉ định và phát sinh dịch vụ tại phòng:
--
--     bác sĩ  =  thư ký y khoa  =  điều dưỡng
--
-- Khác nhau chỉ ở chỗ AI THỰC SỰ BẤM, và chuyện đó là việc của nhật ký chứ
-- không phải của hàng rào quyền. `service_order` đã ghi người thao tác vào cả
-- `recorded_by` lẫn `authorized_by`; không bịa tên một bác sĩ khác.
--
-- KHÔNG SUY RỘNG. Đây là quyền ĐẶT CHỈ ĐỊNH. Ký bệnh án, duyệt và phát hành kết
-- quả là những quyền khác, nằm ở khối khác, và migration này không đụng tới.
--
-- HAI VIỆC, KHÔNG PHẢI MỘT:
--
--   1. nhóm mẫu `NURSE_ULTRASOUND` thêm khối `chi_dinh` — cho người VÀO LÀM
--      SAU;
--   2. cấp thật cho điều dưỡng ĐANG LÀM — nhóm mẫu chỉ áp lúc tạo nhân sự, nên
--      sửa mỗi nhóm mẫu là sáng mai họ bấm vẫn bị từ chối.
--
-- Chạy lại nhiều lần không sinh thêm gì: `ON CONFLICT DO NOTHING` trên chỉ mục
-- một phần "chưa thu hồi", và câu cấp bỏ qua ai đã có.

-- ── 1. Nhóm mẫu, cho người vào làm sau ─────────────────────────────────────
UPDATE public.quyen_preset
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(khoi || ARRAY['chi_dinh']) AS k),
       sua_luc = now()
 WHERE ma = 'NURSE_ULTRASOUND'
   AND NOT ('chi_dinh' = ANY(khoi));

-- ── 2. Cấp thật cho điều dưỡng đang làm ────────────────────────────────────
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, c.ma, c.work_pack, 'NURSE_ULTRASOUND',
       'Điều dưỡng được đặt chỉ định (chốt 23/09/2026)'
  FROM public.clinic_membership m
  JOIN public.capability c ON c.work_pack = 'chi_dinh'
 WHERE m.role = 'NURSE_ULTRASOUND'
   AND m.is_active
   AND NOT EXISTS (
       SELECT 1 FROM public.capability_grant g
        WHERE g.clinic_id = m.clinic_id
          AND g.staff_id = m.staff_id
          AND g.capability = c.ma
          AND g.revoked_at IS NULL)
ON CONFLICT DO NOTHING;
