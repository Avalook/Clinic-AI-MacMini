-- NGUỒN của lần xếp phòng (Tuyền 25/09/2026 — P3):
--   * quầy thu (lego "Thanh toán dịch vụ") xếp / đổi phòng LÚC NÀO CŨNG ĐƯỢC —
--     trước khi thu (phòng dự kiến), sau khi thu, cả khi đã xếp mà nhầm;
--   * TRƯỞNG CA (lego "Điều phối khách") CAO HƠN: lần xếp hiệu lực gần nhất do
--     trưởng ca làm thì quầy thu KHÔNG đổi được nữa; trưởng ca đổi được mọi lúc.
-- Muốn phân biệt thì mỗi lần xếp phải ghi nguồn. Nguồn theo LỆNH gọi từ lego
-- nào (hai capability khác nhau), không theo vai của người bấm.
--
--   quay_thu  — màn Thanh toán dịch vụ
--   truong_ca — màn Điều phối khách
--   tu_dong   — dây H4: thu tiền xong khối Hành trình xếp thay người thu
--   khac      — màn khác (Xem lượt, phòng nhận khách…) — ngang quầy thu
-- NULL = lần xếp trước 25/09 (không rõ nguồn) — coi như KHÔNG phải trưởng ca.
--
-- Chạy lại được.

ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS routing_nguon text;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM pg_constraint WHERE conname = 'service_order_routing_nguon'
  ) THEN
    ALTER TABLE public.service_order
      ADD CONSTRAINT service_order_routing_nguon CHECK (
        routing_nguon IS NULL
        OR routing_nguon IN ('quay_thu', 'truong_ca', 'tu_dong', 'khac'));
  END IF;
END;
$$;

COMMENT ON COLUMN public.service_order.routing_nguon IS
'Nguồn của lần xếp phòng hiệu lực: quay_thu · truong_ca · tu_dong · khac. Trưởng ca đã xếp thì chỉ trưởng ca đổi được (P3, 25/09/2026).';
