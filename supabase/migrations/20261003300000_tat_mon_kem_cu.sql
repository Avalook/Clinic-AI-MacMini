-- GỠ KHỐI "MÓN KÈM DỊCH VỤ" CŨ (C17, Tuyền 02/10/2026: "gỡ đi luôn, đừng để lại rác").
--
-- Khối tick đầu dò ở quầy thu dịch vụ trùng với "Mua thêm vật tư" (C13,
-- `luot_vat_tu`) nên UI + API + service đã gỡ. DỮ LIỆU GIỮ NGUYÊN:
--   · `luot_phu_thu` (dòng đã tick, kể cả đã thu) — KHÔNG xoá, không sửa: hoá đơn,
--     phiếu thu, lịch sử, báo cáo công nợ vẫn đọc `payment_bill_line.source_type
--     = 'phu_thu'` và dòng chưa thu vẫn nằm trong hoá đơn dịch vụ, thu được.
--   · `phu_thu_mau` — chỉ TẮT (active = false) để không còn gì tham chiếu làm
--     "món kèm chọn được"; không xoá, bật lại được bằng một câu UPDATE.
--
-- Chạy lại được (UPDATE theo điều kiện; lần hai không đổi dòng nào).

UPDATE public.phu_thu_mau SET active = false WHERE active;

COMMENT ON TABLE public.phu_thu_mau IS
'Món kèm chọn được của một dịch vụ (đầu dò Bio…) — 28/09/2026. ĐÃ GỠ KHỐI TICK (C17, 02/10/2026, thay bằng luot_vat_tu); mọi dòng active = false, giữ để tra lịch sử. luot_phu_thu cũ vẫn đọc được.';
