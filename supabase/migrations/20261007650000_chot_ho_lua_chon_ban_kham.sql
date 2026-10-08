-- LÀM TẠI BÀN KHÁM chốt hộ ĐÚNG MỘT chỉ định (sửa review đợt 07/10/2026).
--
-- Bản trước: [Làm tại bàn khám] trên chỉ định khách chưa chốt gọi "chốt mọi
-- chỉ định đang chờ khách quyết" của cả lượt → cả CLS khách chưa đồng ý cũng
-- thành "khách làm", quầy hiện nợ oan, check-out bị chặn, hoàn tác không gỡ.
-- Nay chỉ chốt đúng chỉ định bác sĩ đang làm, và lần làm GHI LẠI là nó đã chốt
-- hộ — hoàn tác Bắt đầu trả lựa chọn về đúng như trước (chỉ khi không ai chốt
-- lại lượt ấy sau đó: lựa chọn người sau không bị đè).
--
--   chot_lua_chon_tu   selection_status của chỉ định TRƯỚC khi lần làm chốt hộ
--                      (NULL = lần làm này không chốt hộ gì).
--   chot_lua_chon_rev  revision của `service_selection_state` NGAY SAU lần chốt
--                      hộ — hoàn tác chỉ trả lại khi revision vẫn bằng số này.
--
-- Chạy lại được.

ALTER TABLE public.service_execution_attempt
    ADD COLUMN IF NOT EXISTS chot_lua_chon_tu text,
    ADD COLUMN IF NOT EXISTS chot_lua_chon_rev integer;

COMMENT ON COLUMN public.service_execution_attempt.chot_lua_chon_tu IS
    'Lần làm tại bàn khám đã chốt hộ lựa chọn của khách cho CHỈ ĐỊNH NÀY: trạng thái lựa chọn trước đó (NULL = không chốt hộ).';
COMMENT ON COLUMN public.service_execution_attempt.chot_lua_chon_rev IS
    'Revision lựa chọn của lượt ngay sau lần chốt hộ — hoàn tác Bắt đầu chỉ trả lại lựa chọn khi chưa ai chốt lại sau đó.';
