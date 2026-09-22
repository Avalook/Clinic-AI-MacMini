-- Service Lifecycle v1 — Slice 1: nền schema (22/09/2026).
--
-- Contract: docs/ai/lifecycle-v1/ (CHECKPOINT §2, SELECTION §2/§6, ROUTING §2–3,
-- EXECUTION §2–4). Chỉ THÊM, không viết lại lịch sử:
--   * service_order có thêm ba trục selection / routing / execution, TÁCH khỏi
--     exec_status cũ. Cột mới để NULL cho mọi dòng hiện có — NULL là tương thích
--     (legacy/draft), không phải trạng thái domain thứ tư. KHÔNG suy ngược từ
--     exec_status, room_id, payment hay queue: dữ liệu cũ không có bằng chứng về
--     lựa chọn của khách hay lần thực hiện.
--   * WAITING không được lưu: nó là trạng thái hiệu lực (PENDING + đã chọn + đủ
--     tài chính + đã xếp phòng + không có attempt đang chạy), tính ở read model.
--     Lưu nó thì Payment/Router cùng phải ghi execution_status (CHECKPOINT §2).
--   * service_selection_state: revision Selection theo LƯỢT. Không có dòng =
--     revision 0.
--   * service_execution_attempt: mỗi lần thực sự Start là một dòng. NOT_PERFORMED
--     không sinh attempt (không có giá trị đó trong status).
--
-- Chưa làm ở đây (để Slice 3): nới chỉ mục một-lần-thu-sống cho kind=dich_vu.
-- Hàm lịch sử payment_cycle_backfill_legacy() dùng
-- ON CONFLICT (clinic_id, visit_id, kind) WHERE status IN (...) nên cần chỉ mục
-- uq_payment_cycle_mot_lan_song đúng như cũ.
--
-- Chạy lại được: mọi lệnh dùng IF NOT EXISTS / DROP ... IF EXISTS.

-- ── service_order: ba trục mới ─────────────────────────────────────────────
-- DEFAULT hằng số trên cột NOT NULL không viết lại bảng (PG ≥ 11).
ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS selection_status   text,
    ADD COLUMN IF NOT EXISTS routing_status     text,
    ADD COLUMN IF NOT EXISTS routing_revision   integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS execution_status   text,
    ADD COLUMN IF NOT EXISTS execution_revision integer NOT NULL DEFAULT 0;

-- selection_status KHÔNG có DEFAULT 'PENDING': draft vẫn nằm chung bảng, và
-- chỉ order chính thức tạo sau cutover mới được đặt PENDING (SELECTION §2).
ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_selection_status;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_selection_status CHECK (
        selection_status IS NULL
        OR selection_status IN ('PENDING', 'SELECTED', 'NOT_SELECTED'));

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_routing_status;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_routing_status CHECK (
        routing_status IS NULL
        OR routing_status IN ('UNASSIGNED', 'ASSIGNED', 'REASSIGNMENT_REQUIRED'));

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_routing_revision;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_routing_revision CHECK (routing_revision >= 0);

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_execution_status;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_execution_status CHECK (
        execution_status IS NULL
        OR execution_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED',
                                'CANCELLED', 'NOT_PERFORMED', 'INTERRUPTED'));

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_execution_revision;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_execution_revision CHECK (execution_revision >= 0);

COMMENT ON COLUMN public.service_order.selection_status IS
    'Lifecycle v1 — lựa chọn của khách. NULL = legacy/draft (không phải trạng thái).';
COMMENT ON COLUMN public.service_order.routing_status IS
    'Lifecycle v1 — phòng chính thức. NULL = legacy, không suy từ room_id.';
COMMENT ON COLUMN public.service_order.execution_status IS
    'Lifecycle v1 — thực hiện. WAITING không lưu (trạng thái hiệu lực). '
    'NULL = legacy, không suy từ exec_status.';

-- ── service_selection_state: revision Selection theo lượt ───────────────────
CREATE TABLE IF NOT EXISTS public.service_selection_state (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id     uuid NOT NULL,
    revision     integer NOT NULL CHECK (revision >= 1),
    confirmed_by uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    confirmed_at timestamptz NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, visit_id),
    -- Cùng vòng đời với service_order của lượt (service_order_visit_fk CASCADE).
    CONSTRAINT service_selection_state_visit_fk
        FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit(clinic_id, visit_id) ON DELETE CASCADE
);

ALTER TABLE public.service_selection_state ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_selection_state_select_own_clinic
    ON public.service_selection_state;
CREATE POLICY service_selection_state_select_own_clinic
    ON public.service_selection_state
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.service_selection_state TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.service_selection_state TO service_role;

COMMENT ON TABLE public.service_selection_state IS
    'Lifecycle v1 — revision Selection theo lượt. Không có dòng = revision 0.';

-- ── service_execution_attempt: mỗi lần thực sự Start ────────────────────────
CREATE TABLE IF NOT EXISTS public.service_execution_attempt (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id                 uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_order_id          uuid NOT NULL,
    attempt_no                integer NOT NULL CHECK (attempt_no >= 1),
    -- Dịch vụ không cần phòng thì không có phòng để chụp.
    room_id_snapshot          uuid,
    routing_revision_snapshot integer NOT NULL CHECK (routing_revision_snapshot >= 0),
    status                    text NOT NULL
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'INTERRUPTED')),
    started_by                uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    started_at                timestamptz NOT NULL,
    completed_by              uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    completed_at              timestamptz,
    interrupted_by            uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    interrupted_at            timestamptz,
    interruption_reason_code  text,
    interruption_reason_note  text,
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_service_execution_attempt_clinic_id UNIQUE (clinic_id, id),
    CONSTRAINT uq_service_execution_attempt_no
        UNIQUE (clinic_id, service_order_id, attempt_no),
    -- Attempt là lịch sử thực hiện: không để xoá order kéo theo mất dấu vết.
    CONSTRAINT service_execution_attempt_order_fk
        FOREIGN KEY (clinic_id, service_order_id)
        REFERENCES public.service_order(clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_execution_attempt_room_fk
        FOREIGN KEY (clinic_id, room_id_snapshot)
        REFERENCES public.clinic_room(clinic_id, id) ON DELETE RESTRICT,
    -- Trường hoàn thành có ⇔ COMPLETED.
    CONSTRAINT service_execution_attempt_completed_fields CHECK (
        (status = 'COMPLETED'
            AND completed_by IS NOT NULL AND completed_at IS NOT NULL
            AND completed_at >= started_at)
        OR (status <> 'COMPLETED'
            AND completed_by IS NULL AND completed_at IS NULL)),
    -- Trường gián đoạn + lý do có ⇔ INTERRUPTED.
    CONSTRAINT service_execution_attempt_interrupted_fields CHECK (
        (status = 'INTERRUPTED'
            AND interrupted_by IS NOT NULL AND interrupted_at IS NOT NULL
            AND interrupted_at >= started_at
            AND interruption_reason_code IS NOT NULL)
        OR (status <> 'INTERRUPTED'
            AND interrupted_by IS NULL AND interrupted_at IS NULL
            AND interruption_reason_code IS NULL
            AND interruption_reason_note IS NULL)),
    -- Mã lý do theo EXECUTION §11; OTHER phải có ghi chú.
    CONSTRAINT service_execution_attempt_reason_code CHECK (
        interruption_reason_code IS NULL
        OR interruption_reason_code IN ('EQUIPMENT_FAILURE', 'PATIENT_REQUEST',
            'CLINICAL_SAFETY', 'TECHNICAL_FAILURE', 'STAFF_UNAVAILABLE', 'OTHER')),
    CONSTRAINT service_execution_attempt_other_has_note CHECK (
        interruption_reason_code IS DISTINCT FROM 'OTHER'
        OR nullif(btrim(coalesce(interruption_reason_note, '')), '') IS NOT NULL)
);

-- Tối đa một attempt đang chạy cho mỗi order.
CREATE UNIQUE INDEX IF NOT EXISTS uq_service_execution_attempt_mot_dang_chay
    ON public.service_execution_attempt (clinic_id, service_order_id)
    WHERE status = 'IN_PROGRESS';

ALTER TABLE public.service_execution_attempt ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_execution_attempt_select_own_clinic
    ON public.service_execution_attempt;
CREATE POLICY service_execution_attempt_select_own_clinic
    ON public.service_execution_attempt
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.service_execution_attempt TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.service_execution_attempt TO service_role;

COMMENT ON TABLE public.service_execution_attempt IS
    'Lifecycle v1 — một dòng mỗi lần Start thực sự. Không có attempt cho '
    'NOT_PERFORMED.';
