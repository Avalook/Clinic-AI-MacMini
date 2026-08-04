-- BACKEND SỞ HỮU MỌI LỆNH GHI (ADR-0012) — bỏ chín chính sách ghi lọt lưới.
--
-- Luật của hệ thống, ghi trong CLAUDE.md và ADR-0012: trình duyệt nói chuyện
-- thẳng với Supabase CHỈ để đăng nhập và nhận realtime. Mọi lệnh ghi đi qua
-- FastAPI, nơi có luật nghiệp vụ, có kiểm vai, và có nhật ký.
--
-- Chín bảng dựng trong hai tuần qua kèm theo `FOR ALL TO authenticated` — thói
-- quen chép từ mẫu RLS thông thường. Hậu quả không phải lý thuyết: một chính
-- sách ghi cho `authenticated` nghĩa là bất kỳ ai đăng nhập được đều có thể mở
-- công cụ nhà phát triển và:
--
--   • tự đổi luật thứ tự bắt buộc (visit_gate_rule) — tắt chốt an toàn;
--   • tự ghi mình đã "cho phép gửi kết quả" (clinical_release) — bỏ qua chữ ký
--     bác sĩ, thứ có giá trị pháp lý theo TT13/2011/TT-BYT;
--   • đổi sức chứa phòng, đổi tuyến điều phối, đổi ngưỡng cảnh báo.
--
-- Không ai mất chức năng gì: FastAPI dùng service role và BỎ QUA RLS, nên mọi
-- đường ghi đang chạy vẫn chạy. Cái mất đi là một cửa sau chưa ai dùng.
--
-- Bài kiểm `tenant_scoped_rls.sql` đã canh đúng điều này từ trước — nó chỉ
-- không chạy được vì chuỗi migration đứt từ 02/08, nên chín chính sách kia lọt
-- qua mà không ai thấy. Một bài kiểm không chạy là một bài kiểm không tồn tại.

DROP POLICY IF EXISTS clinic_room_write        ON public.clinic_room;
DROP POLICY IF EXISTS clinic_room_node_write   ON public.clinic_room_node;
DROP POLICY IF EXISTS route_template_write     ON public.route_template;
DROP POLICY IF EXISTS visit_route_write        ON public.visit_route;
DROP POLICY IF EXISTS dispatch_threshold_write ON public.dispatch_threshold;
DROP POLICY IF EXISTS clinical_release_write   ON public.clinical_release;
DROP POLICY IF EXISTS slot_hold_write          ON public.slot_hold;
DROP POLICY IF EXISTS visit_gate_rule_write    ON public.visit_gate_rule;
DROP POLICY IF EXISTS visit_gate_override_write ON public.visit_gate_override;

-- Thu luôn quyền ghi ở tầng GRANT. Bỏ chính sách mà để nguyên GRANT thì hôm
-- nào có người thêm lại một chính sách "cho tiện" là cửa mở lại ngay.
REVOKE INSERT, UPDATE, DELETE ON public.clinic_room        FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.clinic_room_node   FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.route_template     FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.visit_route        FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.dispatch_threshold FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.clinical_release   FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.slot_hold          FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.visit_gate_rule    FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.visit_gate_override FROM authenticated;

DO $verify$
DECLARE
    con_lai text;
BEGIN
    SELECT string_agg(tablename || '.' || policyname, ', ') INTO con_lai
      FROM pg_policies
     WHERE schemaname = 'public' AND cmd <> 'SELECT';
    IF con_lai IS NOT NULL THEN
        RAISE EXCEPTION 'còn chính sách ghi cho client: %', con_lai;
    END IF;
    RAISE NOTICE 'mọi lệnh ghi đi qua backend — không còn cửa sau nào';
END
$verify$;
