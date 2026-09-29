-- TRẢ "ĐO MẬT ĐỘ XƯƠNG" (DICHVU-DXA) VỀ PHÒNG "ĐO SINH HIỆU" (Tuyền 29/09/2026 chiều).
--
-- Migration 20260929970000 gỡ DXA khỏi phòng Đo sinh hiệu vì hiểu nhầm một câu
-- chốt cũ. Tuyền đính chính: DXA ĐANG làm ở phòng Đo sinh hiệu — gắn lại.
-- Chỉ THÊM (phòng Đối tác vẫn giữ DXA như trước). Chạy lại được.

INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
SELECT ph.clinic_id, ph.id, 'DICHVU-DXA'
  FROM public.clinic_room ph
 WHERE lower(btrim(ph.name)) = lower('Đo sinh hiệu')
   AND EXISTS (SELECT 1 FROM public.node_definition nd
                WHERE nd.clinic_id = ph.clinic_id AND nd.code = 'DICHVU-DXA')
ON CONFLICT (room_id, node_code) DO NOTHING;
