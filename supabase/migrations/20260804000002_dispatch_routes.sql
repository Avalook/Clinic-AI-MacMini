-- TUYẾN ĐIỀU PHỐI — ba thứ tự khám, và không được đóng cứng cái nào.
--
-- Yêu cầu khách hàng (Notion §4 Trưởng ca — Điều phối chi tiết): sau khi bác sĩ
-- khám, bệnh nhân cần xét nghiệm máu có thể đi một trong ba đường:
--
--     siêu âm  → lấy máu  → đọc KQ  → ra về
--     lấy máu  → siêu âm  → đọc KQ  → ra về
--     siêu âm  → đọc KQ   → lấy máu → ra về
--
-- Tiêu chí kỹ thuật đi kèm nói thẳng: *"Không được cố định hệ thống chỉ theo
-- một thứ tự khám"* và *"hoặc tuyến khác được cấu hình sẵn"*. Nên tuyến là DỮ
-- LIỆU, không phải ba nhánh `if` trong mã. Phòng khám thêm tuyến thứ tư là thêm
-- một dòng, không phải một lần phát hành.

CREATE TABLE IF NOT EXISTS public.route_template (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    code        text NOT NULL,
    name        text NOT NULL,
    -- Danh sách node_code theo thứ tự. Mảng chứ không phải bảng con: một tuyến
    -- luôn được đọc và ghi TRỌN VẸN, không ai sửa riêng bước thứ ba của một
    -- tuyến mẫu.
    steps       text[] NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    sort        integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_route_template_code UNIQUE (clinic_id, code),
    CONSTRAINT route_template_has_steps CHECK (array_length(steps, 1) >= 1)
);

COMMENT ON TABLE public.route_template IS
    'Tuyến điều phối sau khám: thứ tự các bước. Ba tuyến gốc theo yêu cầu khách '
    'hàng; phòng khám thêm tuyến mới bằng cách thêm dòng.';

-- ---------------------------------------------------------------------------
-- Tuyến ĐANG ÁP DỤNG cho một lượt khám
-- ---------------------------------------------------------------------------
-- Một lượt có thể đổi tuyến giữa chừng (ngoại lệ, bắt buộc lý do). Nên đây là
-- bảng LỊCH SỬ, mỗi lần chọn là một dòng mới — không UPDATE đè.
--
-- *"Mọi lần đổi thứ tự/chuyển phòng phải lưu được quy trình trước, quy trình
-- sau, người đổi, thời gian và lý do"* — giữ nguyên dòng cũ là cách duy nhất
-- trả lời được câu đó mà không phải tin vào một bảng log riêng.

CREATE TABLE IF NOT EXISTS public.visit_route (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id     uuid NOT NULL,
    template_id  uuid REFERENCES public.route_template(id),
    -- Chụp lại các bước tại thời điểm áp dụng. Tuyến mẫu có thể bị sửa về sau;
    -- lượt khám này đã đi theo thứ tự NÀY, và điều đó không được đổi theo.
    steps        text[] NOT NULL,
    -- Bước đã hoàn tất trước khi tuyến được áp — phần không bị đổi thứ tự.
    kept_steps   text[] NOT NULL DEFAULT '{}',
    is_exception boolean NOT NULL DEFAULT false,
    reason       text,
    applied_by   uuid NOT NULL,
    applied_at   timestamptz NOT NULL DEFAULT now(),
    superseded_at timestamptz,
    CONSTRAINT visit_route_has_steps CHECK (array_length(steps, 1) >= 1),
    -- Đổi tuyến giữa chừng thì PHẢI có lý do. Đây là ràng buộc nghiệp vụ của
    -- khách hàng, không phải một lời nhắc trên giao diện.
    CONSTRAINT visit_route_exception_needs_reason
        CHECK (NOT is_exception OR nullif(btrim(coalesce(reason, '')), '') IS NOT NULL)
);

COMMENT ON TABLE public.visit_route IS
    'Tuyến đang áp cho một lượt khám. Append-only: đổi tuyến = dòng mới, dòng cũ '
    'đóng bằng superseded_at. Trả lời được "trước/sau, ai đổi, lúc nào, vì sao".';

CREATE INDEX IF NOT EXISTS idx_visit_route_current
    ON public.visit_route (clinic_id, visit_id) WHERE superseded_at IS NULL;

-- Mỗi lượt khám chỉ có MỘT tuyến đang hiệu lực. Hai tuyến cùng lúc nghĩa là hai
-- bộ phận đọc hai thứ tự khác nhau cho cùng một bệnh nhân.
CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_route_one_active
    ON public.visit_route (visit_id) WHERE superseded_at IS NULL;

-- ---------------------------------------------------------------------------
-- Ngưỡng cảnh báo — cấu hình được, theo từng phòng
-- ---------------------------------------------------------------------------
-- *"Ngưỡng chờ lâu/quá tải phải cho phép quản lý cấu hình theo từng phòng và
-- thay đổi theo giai đoạn cao điểm."* Nên nó là dữ liệu, và mặc định nằm ở mức
-- phòng khám để một phòng mới không bị bỏ quên mà không có ngưỡng nào.

CREATE TABLE IF NOT EXISTS public.dispatch_threshold (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    -- NULL = ngưỡng MẶC ĐỊNH của phòng khám, áp cho mọi phòng chưa khai riêng.
    room_id       uuid REFERENCES public.clinic_room(id) ON DELETE CASCADE,
    wait_minutes  integer NOT NULL DEFAULT 20,
    max_waiting   integer NOT NULL DEFAULT 8,
    updated_by    uuid,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dispatch_threshold_sane
        CHECK (wait_minutes BETWEEN 1 AND 480 AND max_waiting BETWEEN 1 AND 200)
);

COMMENT ON COLUMN public.dispatch_threshold.room_id IS
    'NULL = ngưỡng mặc định của phòng khám. Phòng chưa khai riêng thì dùng nó — '
    'không phòng nào được ở trạng thái "không có ngưỡng".';

-- Một ngưỡng cho mỗi phòng, và một ngưỡng mặc định. Chỉ mục riêng cho nhánh
-- NULL vì UNIQUE thường coi hai NULL là khác nhau.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatch_threshold_room
    ON public.dispatch_threshold (clinic_id, room_id) WHERE room_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatch_threshold_default
    ON public.dispatch_threshold (clinic_id) WHERE room_id IS NULL;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.route_template      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.visit_route         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispatch_threshold  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS route_template_select ON public.route_template;
CREATE POLICY route_template_select ON public.route_template
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS route_template_write ON public.route_template;
CREATE POLICY route_template_write ON public.route_template
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])));

-- Tuyến của lượt khám: mọi vai lâm sàng phải ĐỌC được (bộ phận nhận cần biết
-- mình là bước tiếp theo), nhưng chỉ Trưởng ca/Quản lý được GHI.
DROP POLICY IF EXISTS visit_route_select ON public.visit_route;
CREATE POLICY visit_route_select ON public.visit_route
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS visit_route_write ON public.visit_route;
CREATE POLICY visit_route_write ON public.visit_route
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])));

DROP POLICY IF EXISTS dispatch_threshold_select ON public.dispatch_threshold;
CREATE POLICY dispatch_threshold_select ON public.dispatch_threshold
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS dispatch_threshold_write ON public.dispatch_threshold;
CREATE POLICY dispatch_threshold_write ON public.dispatch_threshold
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT', 'TRUONG_CA'])));

GRANT SELECT ON public.route_template, public.visit_route,
    public.dispatch_threshold TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.route_template, public.visit_route,
    public.dispatch_threshold TO authenticated;

-- ---------------------------------------------------------------------------
-- Seed: ba tuyến khách hàng đã chốt + ngưỡng mặc định
-- ---------------------------------------------------------------------------
-- Các bước dùng đúng node_code đã có trong node_definition, không đặt tên mới.

INSERT INTO public.route_template (clinic_id, code, name, steps, sort)
SELECT c.id, v.code, v.name, v.steps, v.sort
  FROM public.clinic c
  CROSS JOIN (VALUES
      ('TUYEN-A', 'Siêu âm → Lấy máu → Đọc KQ',
       ARRAY['DICHVU-SIEUAM', 'DICHVU-LAYMAU-MAU', 'DICHVU-DUYET-KETQUA',
             'THUOC-04', 'LUOTKHAM-14'], 10),
      ('TUYEN-B', 'Lấy máu → Siêu âm → Đọc KQ',
       ARRAY['DICHVU-LAYMAU-MAU', 'DICHVU-SIEUAM', 'DICHVU-DUYET-KETQUA',
             'THUOC-04', 'LUOTKHAM-14'], 20),
      ('TUYEN-C', 'Siêu âm → Đọc KQ → Lấy máu',
       ARRAY['DICHVU-SIEUAM', 'DICHVU-DUYET-KETQUA', 'DICHVU-LAYMAU-MAU',
             'THUOC-04', 'LUOTKHAM-14'], 30)
  ) AS v(code, name, steps, sort)
ON CONFLICT (clinic_id, code) DO NOTHING;

INSERT INTO public.dispatch_threshold (clinic_id, room_id, wait_minutes, max_waiting)
SELECT c.id, NULL, 20, 8 FROM public.clinic c
ON CONFLICT DO NOTHING;

DO $verify$
DECLARE v_r int; v_t int; v_bad text;
BEGIN
    SELECT count(*) INTO v_r FROM public.route_template WHERE is_active;
    SELECT count(*) INTO v_t FROM public.dispatch_threshold;
    -- Mọi bước trong tuyến mẫu phải là node CÓ THẬT. Một node_code gõ sai sẽ
    -- thành một bước không bao giờ tới lượt, và không có gì báo.
    SELECT string_agg(DISTINCT s, ', ') INTO v_bad
      FROM public.route_template rt, unnest(rt.steps) s
     WHERE NOT EXISTS (
        SELECT 1 FROM public.node_definition n
         WHERE n.code = s AND n.clinic_id = rt.clinic_id);
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'Tuyến mẫu trỏ tới node không tồn tại: %', v_bad;
    END IF;
    RAISE NOTICE 'route_template: % tuyến; dispatch_threshold: % dòng', v_r, v_t;
END
$verify$;
