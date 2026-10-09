-- LÀM TẠI BÀN KHÁM chuyển chỉ định đã có phòng sang phòng bàn khám (Tuyền
-- 09/10/2026): báo cáo theo phòng phải đếm đúng nơi làm. Lần làm giữ PHÒNG CŨ
-- để hoàn tác (Huỷ bắt đầu tại bàn khám) trả chỉ định về đúng phòng ấy và đưa
-- khách về lại hàng chờ của nó.
--
-- Cột cho phép rỗng, KHÔNG DEFAULT (không ghi lại cả bảng). Chạy lại được.

ALTER TABLE public.service_execution_attempt
    ADD COLUMN IF NOT EXISTS phong_truoc_ban_kham uuid;

COMMENT ON COLUMN public.service_execution_attempt.phong_truoc_ban_kham IS
'Lần làm tại bàn khám (noi_lam = BAN_KHAM) đã CHUYỂN chỉ định từ phòng này sang phòng bàn khám; NULL = không chuyển (chưa có phòng, hoặc đã ở phòng bàn khám, hoặc không biết phòng bàn khám). Huỷ bắt đầu trả chỉ định về phòng này. 09/10/2026.';
