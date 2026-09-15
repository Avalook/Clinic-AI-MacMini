-- Lát cắt 1 của luồng khám: sinh hiệu → bác sĩ khám → duyệt chỉ định → điều phối
-- → thực hiện dịch vụ → quay lại bác sĩ → kết thúc khám.
--
-- Hợp đồng: demo-clinicai/docs/handoff/DANH-GIA-THIET-KE-CLAUDE-20260911-v2.md §3.
--
-- CHẠY SONG SONG VỚI LUỒNG CŨ, KHÔNG THAY NÓ. Các màn cũ (`/truong-ca`, bàn khám,
-- `move_visit_to_station`) giữ nguyên hành vi. Luồng mới có bảng riêng, lệnh
-- riêng, màn riêng `/luot-kham`, để lát này review và thử được mà không làm
-- hỏng thứ đang chạy. Gỡ luồng cũ là việc của lát sau, khi luồng mới đã đúng.
--
-- BA TRỤC TÁCH RIÊNG (contract I3). Trạng thái THỰC HIỆN nằm ở `service_order`,
-- YÊU CẦU của vòng đọc nằm ở `round_requirement`, kết quả theo phiên bản để
-- lát sau. Không trục nào ghi đè trục khác.
--
-- Mọi bảng mang `clinic_id` và trỏ về lượt khám bằng khoá GHÉP (clinic_id,
-- visit_id): một dòng không thể trỏ sang lượt khám của phòng khám khác, kể cả
-- khi code quên lọc. Backend chạy bằng quyền chủ nên RLS không chặn nó —
-- khoá ghép là lớp chặn ở chính dữ liệu.

-- ---------------------------------------------------------------------------
-- 0. Đích cho khoá ghép
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_clinic_visit
    ON public.visit (clinic_id, visit_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinic_room_clinic_id
    ON public.clinic_room (clinic_id, id);

-- ---------------------------------------------------------------------------
-- 1. Trạng thái luồng của một lượt khám
-- ---------------------------------------------------------------------------
-- Bảng riêng một-một thay vì thêm cột vào `visit`: `visit` đang có trigger,
-- view và bài kiểm của luồng cũ. Thêm cột ở đó là buộc cả hai luồng vào nhau.
CREATE TABLE IF NOT EXISTS public.encounter_flow (
    visit_id          uuid PRIMARY KEY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    vitals_status     text NOT NULL DEFAULT 'pending',
    plan_check_status text NOT NULL DEFAULT 'none',
    route_decision    text,
    route_decided_at  timestamptz,
    route_reason      text,
    content_revision  integer NOT NULL DEFAULT 0,
    finished_at       timestamptz,
    version           integer NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT encounter_flow_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT encounter_flow_vitals_status
        CHECK (vitals_status IN ('pending', 'recorded')),
    CONSTRAINT encounter_flow_plan_check_status
        CHECK (plan_check_status IN ('none', 'pending', 'applied', 'rejected', 'abandoned')),
    CONSTRAINT encounter_flow_route
        CHECK (route_decision IS NULL OR route_decision IN ('PRIMARY', 'SERVICES')),
    -- Đích ghi một lần (I10): có đích thì phải có lúc quyết, và ngược lại.
    CONSTRAINT encounter_flow_route_pair
        CHECK ((route_decision IS NULL) = (route_decided_at IS NULL))
);

-- ---------------------------------------------------------------------------
-- 2. Sinh hiệu — mỗi lần đo một dòng, không sửa đè
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.vital_measurement (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id     uuid NOT NULL,
    systolic     smallint NOT NULL,
    diastolic    smallint NOT NULL,
    pulse        smallint,
    temperature  numeric(3,1),
    weight_kg    numeric(5,1),
    height_cm    numeric(4,1),
    recorded_by  uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vital_measurement_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    -- Lưới an toàn cuối. Câu tiếng Việt cho người dùng do service trả trước.
    CONSTRAINT vital_measurement_bp_range
        CHECK (systolic BETWEEN 50 AND 260 AND diastolic BETWEEN 30 AND 180
               AND systolic > diastolic),
    CONSTRAINT vital_measurement_pulse_range
        CHECK (pulse IS NULL OR pulse BETWEEN 20 AND 250),
    CONSTRAINT vital_measurement_temperature_range
        CHECK (temperature IS NULL OR temperature BETWEEN 34 AND 43),
    CONSTRAINT vital_measurement_weight_range
        CHECK (weight_kg IS NULL OR weight_kg BETWEEN 1 AND 300),
    CONSTRAINT vital_measurement_height_range
        CHECK (height_cm IS NULL OR height_cm BETWEEN 30 AND 230)
);
CREATE INDEX IF NOT EXISTS idx_vital_measurement_visit
    ON public.vital_measurement (clinic_id, visit_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3. Phiên khám — vòng 1 khám ban đầu, vòng ≥2 đọc kết quả
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.consultation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    round_no         smallint NOT NULL,
    kind             text NOT NULL,
    status           text NOT NULL DEFAULT 'queued',
    doctor_staff_id  uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    started_by       uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    started_at       timestamptz,
    completed_by     uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    completed_at     timestamptz,
    outcome          text,
    version          integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT consultation_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT uq_consultation_round UNIQUE (visit_id, round_no),
    CONSTRAINT uq_consultation_clinic_id UNIQUE (clinic_id, id),
    CONSTRAINT consultation_round_positive CHECK (round_no >= 1),
    CONSTRAINT consultation_kind CHECK (kind IN ('PRIMARY', 'REVIEW')),
    CONSTRAINT consultation_kind_round CHECK ((kind = 'PRIMARY') = (round_no = 1)),
    CONSTRAINT consultation_status
        CHECK (status IN ('queued', 'in_progress', 'completed', 'cancelled')),
    CONSTRAINT consultation_outcome
        CHECK (outcome IS NULL OR outcome IN ('NO_SERVICES', 'SERVICES', 'DONE', 'MORE_SERVICES')),
    -- Loại phiên quyết định kết quả nào hợp lệ (T-C4). Service trả câu trước;
    -- ràng buộc này là lưới cho mọi đường ghi khác.
    CONSTRAINT consultation_outcome_kind
        CHECK (outcome IS NULL
               OR (kind = 'PRIMARY' AND outcome IN ('NO_SERVICES', 'SERVICES'))
               OR (kind = 'REVIEW' AND outcome IN ('DONE', 'MORE_SERVICES'))),
    CONSTRAINT consultation_completed_pair
        CHECK ((status = 'completed') = (completed_at IS NOT NULL AND outcome IS NOT NULL))
);

-- Ghi chú khám: chỉ thêm, không sửa. `recorded_by` là người GÕ — thư ký gõ hộ
-- thì tên thư ký nằm ở đây, và việc duyệt chỉ định vẫn chỉ bác sĩ làm được.
CREATE TABLE IF NOT EXISTS public.consultation_note (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    consultation_id  uuid NOT NULL,
    body             text NOT NULL,
    recorded_by      uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT consultation_note_consultation_fk FOREIGN KEY (clinic_id, consultation_id)
        REFERENCES public.consultation (clinic_id, id) ON DELETE CASCADE,
    CONSTRAINT consultation_note_body
        CHECK (length(btrim(body)) > 0 AND length(body) <= 20000)
);

-- ---------------------------------------------------------------------------
-- 4. Chỉ định — MỖI DỊCH VỤ MỘT DÒNG
-- ---------------------------------------------------------------------------
-- Không gộp theo node như `order_services`: node COMPLETED không chứng minh cả
-- ba dịch vụ trong nó đã làm (S10). Thêm chỉ định là thêm dòng, không bao giờ
-- sửa dòng đã làm (I4).
CREATE TABLE IF NOT EXISTS public.service_order (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id             uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id              uuid NOT NULL,
    consultation_id       uuid NOT NULL,
    service_code          text NOT NULL,
    service_name          text NOT NULL,
    node_code             text NOT NULL,
    source                text NOT NULL DEFAULT 'VISIT_ORDER',
    exec_status           text NOT NULL,
    recorded_by           uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    authorized_by         uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    authorized_at         timestamptz,
    room_id               uuid,
    assigned_by           uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    assigned_at           timestamptz,
    performed_by          uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    started_at            timestamptz,
    finished_at           timestamptz,
    not_performed_reason  text,
    result_note           text,
    hold_until_round      smallint,
    cancelled_by          uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    cancel_reason         text,
    version               integer NOT NULL DEFAULT 1,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT service_order_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT service_order_consultation_fk FOREIGN KEY (clinic_id, consultation_id)
        REFERENCES public.consultation (clinic_id, id) ON DELETE CASCADE,
    CONSTRAINT service_order_node_fk FOREIGN KEY (clinic_id, node_code)
        REFERENCES public.node_definition (clinic_id, code) ON DELETE RESTRICT,
    CONSTRAINT service_order_room_fk FOREIGN KEY (clinic_id, room_id)
        REFERENCES public.clinic_room (clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_service_order_clinic_id UNIQUE (clinic_id, id),
    CONSTRAINT service_order_source CHECK (source IN ('VISIT_ORDER', 'PRIOR_PLAN')),
    CONSTRAINT service_order_exec_status
        CHECK (exec_status IN ('draft', 'authorized', 'assigned', 'in_progress',
                               'performed', 'not_performed', 'cancelled')),
    -- Qua khỏi nháp là phải có người duyệt (I2, I12).
    CONSTRAINT service_order_authorized
        CHECK (exec_status IN ('draft', 'cancelled')
               OR (authorized_by IS NOT NULL AND authorized_at IS NOT NULL)),
    CONSTRAINT service_order_room_when_assigned
        CHECK (exec_status NOT IN ('assigned', 'in_progress', 'performed', 'not_performed')
               OR room_id IS NOT NULL),
    CONSTRAINT service_order_not_performed_reason
        CHECK (exec_status <> 'not_performed'
               OR nullif(btrim(coalesce(not_performed_reason, '')), '') IS NOT NULL),
    CONSTRAINT service_order_hold_round CHECK (hold_until_round IS NULL OR hold_until_round >= 2)
);
CREATE INDEX IF NOT EXISTS idx_service_order_visit
    ON public.service_order (clinic_id, visit_id, created_at);

-- ---------------------------------------------------------------------------
-- 5. Vòng đọc kết quả và tập yêu cầu của nó
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.review_round (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id    uuid NOT NULL,
    round_no    smallint NOT NULL,
    status      text NOT NULL DEFAULT 'collecting',
    locked_by   uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    locked_at   timestamptz NOT NULL DEFAULT now(),
    ready_at    timestamptz,
    closed_at   timestamptz,
    version     integer NOT NULL DEFAULT 1,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT review_round_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT uq_review_round UNIQUE (visit_id, round_no),
    CONSTRAINT uq_review_round_clinic_id UNIQUE (clinic_id, id),
    CONSTRAINT review_round_no CHECK (round_no >= 2),
    CONSTRAINT review_round_status
        CHECK (status IN ('collecting', 'ready', 'in_review', 'closed'))
);

CREATE TABLE IF NOT EXISTS public.round_requirement (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    round_id          uuid NOT NULL,
    service_order_id  uuid NOT NULL,
    need              text NOT NULL,
    status            text NOT NULL DEFAULT 'open',
    waived_by         uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    waived_reason     text,
    followup_owner    uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    followup_due      date,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT round_requirement_round_fk FOREIGN KEY (clinic_id, round_id)
        REFERENCES public.review_round (clinic_id, id) ON DELETE CASCADE,
    CONSTRAINT round_requirement_order_fk FOREIGN KEY (clinic_id, service_order_id)
        REFERENCES public.service_order (clinic_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_round_requirement UNIQUE (round_id, service_order_id),
    CONSTRAINT round_requirement_need CHECK (need IN ('PERFORMED', 'VALID_RESULT')),
    CONSTRAINT round_requirement_status CHECK (status IN ('open', 'satisfied', 'waived')),
    -- Miễn yêu cầu phải có người và lý do (I2).
    CONSTRAINT round_requirement_waived
        CHECK (status <> 'waived'
               OR (waived_by IS NOT NULL
                   AND nullif(btrim(coalesce(waived_reason, '')), '') IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- 6. Hàng chờ — xếp theo lúc thực sự đủ điều kiện vào hàng
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.queue_entry (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    lane             text NOT NULL,
    doctor_staff_id  uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    room_id          uuid,
    reason           text NOT NULL,
    ref_id           uuid NOT NULL,
    status           text NOT NULL,
    eligible_at      timestamptz,
    called_at        timestamptz,
    serving_at       timestamptz,
    done_at          timestamptz,
    version          integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT queue_entry_visit_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT queue_entry_room_fk FOREIGN KEY (clinic_id, room_id)
        REFERENCES public.clinic_room (clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT queue_entry_lane CHECK (lane IN ('DOCTOR', 'ROOM')),
    CONSTRAINT queue_entry_reason CHECK (reason IN ('PRIMARY', 'SERVICE', 'REVIEW')),
    CONSTRAINT queue_entry_lane_reason
        CHECK ((lane = 'DOCTOR') = (reason IN ('PRIMARY', 'REVIEW'))),
    CONSTRAINT queue_entry_room_lane CHECK (lane <> 'ROOM' OR room_id IS NOT NULL),
    CONSTRAINT queue_entry_status
        CHECK (status IN ('blocked', 'waiting', 'called', 'serving', 'done', 'left', 'cancelled')),
    CONSTRAINT queue_entry_waiting_has_time
        CHECK (status NOT IN ('waiting', 'called', 'serving') OR eligible_at IS NOT NULL)
);
-- Một dòng SỐNG cho mỗi việc (T-R3): nhận kết quả hai lần không sinh hai chỗ chờ.
CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_entry_live
    ON public.queue_entry (visit_id, reason, ref_id)
    WHERE status NOT IN ('done', 'left', 'cancelled');
-- Một người chỉ đang ở MỘT chỗ (I9). Chặn ở dữ liệu, không chỉ ở code: hai bác
-- sĩ cùng bấm gọi một khách thì đúng một người được.
CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_entry_one_serving
    ON public.queue_entry (visit_id)
    WHERE status = 'serving';
CREATE INDEX IF NOT EXISTS idx_queue_entry_lane
    ON public.queue_entry (clinic_id, lane, status, eligible_at);

-- ---------------------------------------------------------------------------
-- 7. Biên nhận lệnh — cùng transaction với việc nghiệp vụ
-- ---------------------------------------------------------------------------
-- Khoá gắn NGƯỜI GỌI: người khác đoán được khoá cũng không nhận được kết quả
-- của người này. Chỉ lưu ID và trạng thái, không lưu nội dung y khoa.
CREATE TABLE IF NOT EXISTS public.command_receipt (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    actor_staff_id   uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    action           text NOT NULL,
    idempotency_key  text NOT NULL,
    payload_hash     text NOT NULL,
    target_ref       uuid NOT NULL,
    result           jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_command_receipt UNIQUE (clinic_id, actor_staff_id, action, idempotency_key),
    CONSTRAINT command_receipt_key_length CHECK (length(idempotency_key) BETWEEN 8 AND 200)
);

-- ---------------------------------------------------------------------------
-- 8. RLS và quyền: đọc theo phòng khám, không ai ghi từ trình duyệt
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- clinic_id đứng đầu một chỉ mục trên MỌI bảng theo phòng khám
-- ---------------------------------------------------------------------------
-- multi_tenant_foundation.sql đòi điều này: mọi lần đọc đều lọc clinic_id. Sáu
-- bảng kia đã có qua UNIQUE (clinic_id, id); ba bảng dưới thì chưa. Cột thứ hai
-- chọn theo đúng câu service hay hỏi.
CREATE INDEX IF NOT EXISTS idx_encounter_flow_clinic
    ON public.encounter_flow (clinic_id, visit_id);
CREATE INDEX IF NOT EXISTS idx_round_requirement_clinic
    ON public.round_requirement (clinic_id, round_id);
CREATE INDEX IF NOT EXISTS idx_consultation_note_clinic
    ON public.consultation_note (clinic_id, consultation_id, created_at);

DO $rls$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('encounter_flow',    'current_clinical_clinic_ids'),
            ('vital_measurement', 'current_clinical_clinic_ids'),
            ('consultation',      'current_clinical_clinic_ids'),
            ('consultation_note', 'current_clinical_clinic_ids'),
            ('service_order',     'current_clinic_ids'),
            ('review_round',      'current_clinic_ids'),
            ('round_requirement', 'current_clinic_ids'),
            ('queue_entry',       'current_clinic_ids')
        ) AS v(tbl, fn)
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tbl);
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = t.tbl
               AND policyname = t.tbl || '_select_own_clinic'
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated '
                'USING (clinic_id IN (SELECT public.%I()))',
                t.tbl || '_select_own_clinic', t.tbl, t.fn);
        END IF;
        EXECUTE format('GRANT SELECT ON public.%I TO authenticated', t.tbl);
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t.tbl);
    END LOOP;
END
$rls$;

ALTER TABLE public.command_receipt ENABLE ROW LEVEL SECURITY;
DO $receipt_policy$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'command_receipt'
           AND policyname = 'command_receipt_select_own'
    ) THEN
        CREATE POLICY command_receipt_select_own ON public.command_receipt
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids())
                   AND actor_staff_id = public.current_staff_id());
    END IF;
END
$receipt_policy$;
GRANT SELECT ON public.command_receipt TO authenticated;
GRANT ALL ON public.command_receipt TO service_role;

COMMENT ON TABLE public.service_order IS
    'Chỉ định, mỗi dịch vụ một dòng (lát 1 luồng khám). Điều phối chỉ đọc dòng '
    'đã có authorized_by; chuyển phòng không đổi trạng thái thực hiện.';
COMMENT ON TABLE public.queue_entry IS
    'Hàng chờ theo bác sĩ/phòng, xếp theo eligible_at. Một dòng sống mỗi việc, '
    'một dòng serving mỗi lượt khám.';
