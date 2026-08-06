-- Trạng thái "khám dở" cho lượt khám, và ba cột kể lại vì sao.
--
-- ------------------------------------------------------------------------------
-- CHUYỆN CÓ THẬT
--
-- Khách đang khám thì có việc phải về. Hôm nay hệ thống không có chỗ nào ghi
-- điều đó. Cách duy nhất đang làm được là HUỶ LỊCH HẸN — và khi đó hồ sơ trông
-- như người ấy CHƯA TỪNG ĐẾN: mất dấu vết họ đã lấy số, đã đo sinh hiệu, đã
-- được chỉ định dịch vụ. Số thứ tự đã cấp thì bị đốt.
--
-- Hậu quả đo được trên máy chủ ngày 06/08: 35 lượt khám đang ở trạng thái
-- OPEN/IN_PROGRESS, trong đó 18 lượt check-in từ NHỮNG NGÀY TRƯỚC. Không màn
-- hình nào chạm tới 18 dòng ấy — `/visits/active` chỉ nhìn trong ngày. Chúng
-- không phải rác: mỗi dòng là một người thật đã bước vào phòng khám và không ai
-- biết chuyện gì đã xảy ra sau đó.
--
-- ------------------------------------------------------------------------------
-- VÌ SAO INCOMPLETE LÀ TRẠNG THÁI *KHÔNG-CUỐI*
--
-- FINALIZED và AMENDED là hai trạng thái CUỐI: hồ sơ đã ký, bất biến theo Thông
-- tư 13. INCOMPLETE thì khác hẳn — khách CÒN QUAY LẠI. Bác sĩ vẫn phải ghi tiếp
-- được, và vẫn phải ký lên FINALIZED được khi khám xong.
--
-- Nên nó vào DANH SÁCH TRẮNG các trạng thái ghi được, cùng OPEN và IN_PROGRESS.
-- (Trigger `visit_finalized_block_update` chỉ chặn khi OLD.status='FINALIZED',
-- nên đường INCOMPLETE → FINALIZED đi lọt tự nhiên, còn đường ngược lại thì
-- không — đúng như mong muốn.)
--
-- ------------------------------------------------------------------------------
-- CHẠY HAI LẦN VẪN ĐÚNG
--
-- Vòng `database` của CI áp lại toàn bộ migration từ 20260730 một lần nữa
-- (ci.yml), nên mọi câu ở đây phải chịu được lần thứ hai.

-- ---------------------------------------------------------------------------
-- 1. Trạng thái mới
-- ---------------------------------------------------------------------------
ALTER TABLE public.visit
    DROP CONSTRAINT IF EXISTS visit_status_check;

ALTER TABLE public.visit
    ADD CONSTRAINT visit_status_check CHECK (
        status = ANY (ARRAY[
            'OPEN',         -- đã đến, chưa bắt đầu
            'IN_PROGRESS',  -- đang khám
            'INCOMPLETE',   -- khám dở, khách về giữa chừng — CHƯA phải trạng thái cuối
            'FINALIZED',    -- đã ký, bất biến
            'AMENDED'       -- đã ký rồi đính chính, bất biến
        ])
    );

COMMENT ON CONSTRAINT visit_status_check ON public.visit IS
    'INCOMPLETE = khách về giữa chừng. KHÔNG phải trạng thái cuối: hồ sơ còn '
    'ghi được và còn ký lên FINALIZED được, vì khách còn quay lại.';

-- ---------------------------------------------------------------------------
-- 2. Ba cột kể lại chuyện gì đã xảy ra
-- ---------------------------------------------------------------------------
-- Không bắt CSKH đi đào `event_log` để biết vì sao phải gọi lại một người. Lý
-- do nằm ngay trên dòng dữ liệu mà họ đang nhìn.
ALTER TABLE public.visit
    ADD COLUMN IF NOT EXISTS incomplete_at     timestamptz,
    ADD COLUMN IF NOT EXISTS incomplete_reason text,
    ADD COLUMN IF NOT EXISTS incomplete_by     uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.visit.incomplete_reason IS
    'Vì sao lượt khám dừng giữa chừng, do người đóng lượt ghi. Bắt buộc khi '
    'đóng ở trạng thái INCOMPLETE — một lượt dở không lý do là một người bệnh '
    'không ai biết phải gọi lại để nói gì.';

-- Lý do và trạng thái phải đi cùng nhau. Không có ràng buộc này thì
-- `incomplete_reason` sẽ dần trở thành một cột lúc có lúc không, và danh sách
-- gọi lại của CSKH sẽ có những dòng trống mà không ai giải thích được.
ALTER TABLE public.visit
    DROP CONSTRAINT IF EXISTS visit_incomplete_can_ly_do;

ALTER TABLE public.visit
    ADD CONSTRAINT visit_incomplete_can_ly_do CHECK (
        status <> 'INCOMPLETE'
        OR nullif(btrim(coalesce(incomplete_reason, '')), '') IS NOT NULL
    );

-- ---------------------------------------------------------------------------
-- 3. Tra nhanh danh sách phải gọi lại
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_visit_kham_do
    ON public.visit (clinic_id, incomplete_at DESC)
 WHERE status = 'INCOMPLETE';

-- ---------------------------------------------------------------------------
-- 4. Lượt tồn — cái đang có 18 dòng
-- ---------------------------------------------------------------------------
-- Chỉ mục cho câu hỏi "còn lượt nào mở từ hôm trước không". Không có nó thì câu
-- truy vấn ấy quét toàn bảng, và một màn hình quét toàn bảng là một màn hình
-- sớm muộn bị ai đó tắt đi.
CREATE INDEX IF NOT EXISTS idx_visit_con_mo
    ON public.visit (clinic_id, checked_in_at)
 WHERE status IN ('OPEN', 'IN_PROGRESS');
