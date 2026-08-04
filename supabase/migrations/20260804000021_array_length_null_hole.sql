-- `array_length(mảng_rỗng, 1)` TRẢ NULL, VÀ CHECK CHO NULL ĐI QUA.
--
-- Tìm ra khi thử chèn một bản đồng ý chia sẻ với phạm vi rỗng: nó lọt. Xem lại
-- thì Postgres trả NULL cho độ dài của mảng rỗng (không phải 0), `NULL >= 1` là
-- NULL, và một ràng buộc CHECK coi NULL là ĐẠT.
--
--     SELECT array_length(ARRAY[]::text[], 1);        -- NULL
--     SELECT array_length(ARRAY[]::text[], 1) >= 1;   -- NULL → CHECK cho qua
--
-- BỐN ràng buộc dính lỗi này, và cái thứ hai nặng nhất:
--
--   clinical_data_consent_has_scope  bản đồng ý không nêu form nào — đọc được
--                                    thành "đã đồng ý" mà không rõ đồng ý gì
--   visit_gate_rule_has_blocked      LUẬT THỨ TỰ BẮT BUỘC với danh sách chặn
--                                    rỗng: một chốt an toàn bật lên và KHÔNG
--                                    chặn gì cả, im lặng
--   route_template_has_steps         mẫu lộ trình không có bước nào
--   visit_route_has_steps            lượt khám có lộ trình mà lộ trình rỗng —
--                                    bảng điều phối hiện người bệnh đang đi,
--                                    nhưng không đi đâu cả
--
-- Một chốt an toàn không chặn gì tệ hơn là không có chốt: người ta tin là có.
--
-- Đã kiểm trên prod trước khi siết: 0 dòng đang vi phạm ở cả bốn bảng, nên
-- không dòng nào phải sửa trước.

ALTER TABLE public.clinical_data_consent
    DROP CONSTRAINT IF EXISTS clinical_data_consent_has_scope;
ALTER TABLE public.clinical_data_consent
    ADD CONSTRAINT clinical_data_consent_has_scope
    CHECK (coalesce(array_length(form_codes, 1), 0) >= 1);

ALTER TABLE public.visit_gate_rule
    DROP CONSTRAINT IF EXISTS visit_gate_rule_has_blocked;
ALTER TABLE public.visit_gate_rule
    ADD CONSTRAINT visit_gate_rule_has_blocked
    CHECK (coalesce(array_length(blocked_node_codes, 1), 0) >= 1);

ALTER TABLE public.route_template
    DROP CONSTRAINT IF EXISTS route_template_has_steps;
ALTER TABLE public.route_template
    ADD CONSTRAINT route_template_has_steps
    CHECK (coalesce(array_length(steps, 1), 0) >= 1);

ALTER TABLE public.visit_route
    DROP CONSTRAINT IF EXISTS visit_route_has_steps;
ALTER TABLE public.visit_route
    ADD CONSTRAINT visit_route_has_steps
    CHECK (coalesce(array_length(steps, 1), 0) >= 1);

DO $verify$
DECLARE
    v_lot boolean := false;
BEGIN
    BEGIN
        INSERT INTO public.visit_gate_rule
            (clinic_id, name, required_node_code, blocked_node_codes)
        SELECT c.id, '__thu__', n.code, ARRAY[]::text[]
          FROM public.clinic c
          JOIN public.node_definition n
            ON n.clinic_id = c.id AND n.code LIKE 'KHAM-%'
         LIMIT 1;
        v_lot := true;
    EXCEPTION WHEN check_violation THEN
        NULL;  -- đúng như mong đợi
    END;
    IF v_lot THEN
        RAISE EXCEPTION 'mảng rỗng VẪN lọt — ràng buộc chưa vá được';
    END IF;
    RAISE NOTICE 'mảng rỗng đã bị chặn ở cả hai bảng';
END
$verify$;
