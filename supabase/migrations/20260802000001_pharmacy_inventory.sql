-- PHARMACY + INVENTORY — kho đầy đủ (lô, hạn dùng, nhập-xuất-tồn).
--
-- User chốt: làm ĐỦ mô hình kho, không chỉ cấp phát theo đơn.
--   * drug_batch      — lô thuốc: hạn dùng, số lượng tồn, giá nhập
--   * inventory_txn   — mọi biến động tồn kho (nhập/xuất/điều chỉnh/huỷ)
--   * PHARMACIST      — vai mới, thêm vào node_definition + work_item
--   * node cấp phát   — chuỗi 4 bước: soạn → kiểm tra → tư vấn → bàn giao
--
-- Tenant-scoped (clinic_id) + RLS read-only cho authenticated (ADR-0012):
-- mọi ghi qua service_role / FastAPI.

-- ---------------------------------------------------------------------------
-- 1. Thêm PHARMACIST vào các check constraint hiện có
-- ---------------------------------------------------------------------------

ALTER TABLE public.node_definition DROP CONSTRAINT IF EXISTS node_definition_roles_known;
ALTER TABLE public.node_definition ADD CONSTRAINT node_definition_roles_known CHECK (
    actor_roles <@ ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC', 'CASHIER_DV',
        'PHARMACIST'
    ]::text[]
);

ALTER TABLE public.work_item DROP CONSTRAINT IF EXISTS work_item_assigned_role_known;
ALTER TABLE public.work_item ADD CONSTRAINT work_item_assigned_role_known
    CHECK (assigned_role IS NULL OR assigned_role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));

-- Vai chỉ dùng được khi GẮN ĐƯỢC vào người. Không nới hai constraint dưới đây
-- thì không tạo nổi một dược sĩ nào: staff INSERT hỏng ở primary_department,
-- clinic_membership hỏng ở role, và mọi màn /pharmacy vĩnh viễn không ai vào.
ALTER TABLE public.staff DROP CONSTRAINT IF EXISTS staff_primary_department_check;
ALTER TABLE public.staff ADD CONSTRAINT staff_primary_department_check
    CHECK (primary_department = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));

ALTER TABLE public.clinic_membership DROP CONSTRAINT IF EXISTS clinic_membership_role_check;
ALTER TABLE public.clinic_membership ADD CONSTRAINT clinic_membership_role_check
    CHECK (role = ANY (ARRAY[
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));

-- ---------------------------------------------------------------------------
-- 2. drug_batch — lô thuốc
-- ---------------------------------------------------------------------------

-- clinic_id KHÔNG có DEFAULT: 20260730000014 đã xoá `default_clinic_id()` khỏi
-- mọi bảng, nhưng nó chạy TRƯỚC file này nên bảng mới không được nó dọn hộ.
-- Để DEFAULT lại thì phòng khám #2 ghi thiếu clinic_id sẽ âm thầm rơi vào
-- Dr4Women — sai lặng lẽ, tệ hơn hẳn NOT NULL violation.
CREATE TABLE IF NOT EXISTS public.drug_batch (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid NOT NULL,
    drug_catalog_id uuid NOT NULL,
    batch_code text NOT NULL,                -- mã lô (vd LOT-2026-001)
    expiry_date date NOT NULL,               -- hạn dùng
    quantity_on_hand numeric(12,3) DEFAULT 0 NOT NULL,  -- tồn hiện tại
    unit text DEFAULT 'viên' NOT NULL,       -- đơn vị (viên/hộp/chai/ống)
    cost_price numeric(12,0),                -- giá nhập
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT drug_batch_pkey PRIMARY KEY (id),
    CONSTRAINT drug_batch_clinic_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT drug_batch_catalog_fkey FOREIGN KEY (drug_catalog_id)
        REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,
    CONSTRAINT uq_drug_batch_clinic_code UNIQUE (clinic_id, batch_code)
);

CREATE INDEX IF NOT EXISTS idx_drug_batch_clinic ON public.drug_batch (clinic_id);
CREATE INDEX IF NOT EXISTS idx_drug_batch_catalog ON public.drug_batch (drug_catalog_id);
CREATE INDEX IF NOT EXISTS idx_drug_batch_expiry ON public.drug_batch (expiry_date)
    WHERE quantity_on_hand > 0;

-- ---------------------------------------------------------------------------
-- 3. inventory_txn — mọi biến động tồn kho (append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.inventory_txn (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid NOT NULL,
    drug_batch_id uuid NOT NULL,
    txn_type text NOT NULL,                  -- RECEIVE / DISPENSE / ADJUST / DISCARD
    quantity numeric(12,3) NOT NULL,         -- dương = nhập, âm = xuất
    reason text,                             -- lý do (nhập hàng, cấp thuốc, hết hạn...)
    ref_type text,                           -- prescription / manual / adjustment
    ref_id uuid,                             -- prescription.id nếu cấp thuốc
    performed_by_staff_id uuid,
    performed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT inventory_txn_pkey PRIMARY KEY (id),
    CONSTRAINT inventory_txn_clinic_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_txn_batch_fkey FOREIGN KEY (drug_batch_id)
        REFERENCES public.drug_batch(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_txn_staff_fkey FOREIGN KEY (performed_by_staff_id)
        REFERENCES public.staff(id) ON DELETE SET NULL,
    CONSTRAINT inventory_txn_type_check CHECK (
        txn_type IN ('RECEIVE', 'DISPENSE', 'ADJUST', 'DISCARD')
    ),
    CONSTRAINT inventory_txn_qty_sign_check CHECK (
        (txn_type = 'RECEIVE' AND quantity > 0)
        OR (txn_type IN ('DISPENSE', 'DISCARD') AND quantity < 0)
        OR (txn_type = 'ADJUST' AND quantity <> 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_inventory_txn_clinic ON public.inventory_txn (clinic_id);
CREATE INDEX IF NOT EXISTS idx_inventory_txn_batch ON public.inventory_txn (drug_batch_id);
CREATE INDEX IF NOT EXISTS idx_inventory_txn_ref ON public.inventory_txn (ref_type, ref_id)
    WHERE ref_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. Trigger: cập nhật quantity_on_hand khi có txn mới
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.inventory_txn_apply()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE public.drug_batch
       SET quantity_on_hand = quantity_on_hand + NEW.quantity,
           updated_at = now()
     WHERE id = NEW.drug_batch_id;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS inventory_txn_apply_trigger ON public.inventory_txn;
CREATE TRIGGER inventory_txn_apply_trigger
    AFTER INSERT ON public.inventory_txn
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_apply();

-- ---------------------------------------------------------------------------
-- 5. RLS — read-only cho authenticated, ghi qua service_role
-- ---------------------------------------------------------------------------

ALTER TABLE public.drug_batch ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_txn ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS drug_batch_select_own_clinic ON public.drug_batch;
CREATE POLICY drug_batch_select_own_clinic
    ON public.drug_batch FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS inventory_txn_select_own_clinic ON public.inventory_txn;
CREATE POLICY inventory_txn_select_own_clinic
    ON public.inventory_txn FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Grant phải viết tay ở đây. 20260730000008 suy grant từ pg_policy, nhưng nó
-- chạy TRƯỚC file này — bảng sinh sau không có ai cấp quyền hộ, và policy chỉ
-- thu hẹp quyền sẵn có chứ không tạo ra quyền. Thiếu hai dòng dưới đây thì mọi
-- màn /pharmacy trả permission denied dù policy trông hoàn toàn đúng.
GRANT ALL ON public.drug_batch, public.inventory_txn TO service_role;
GRANT SELECT ON public.drug_batch, public.inventory_txn TO authenticated;

-- ---------------------------------------------------------------------------
-- 6. Node cấp phát thuốc — chuỗi 4 bước (soạn → kiểm tra → tư vấn → bàn giao)
-- ---------------------------------------------------------------------------

INSERT INTO public.node_definition
    (clinic_id, code, name, flow_group, workspace, actor_roles, priority, is_group)
VALUES
('a0000000-0000-4000-8000-000000000001', 'THUOC-01', 'Soạn thuốc theo đơn', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'THUOC-02', 'Kiểm tra trước bàn giao', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'THUOC-03', 'Tư vấn dùng thuốc', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'THUOC-04', 'Bàn giao thuốc', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false)
ON CONFLICT ON CONSTRAINT uq_node_definition_clinic_code DO UPDATE SET
    name        = EXCLUDED.name,
    flow_group  = EXCLUDED.flow_group,
    workspace   = EXCLUDED.workspace,
    actor_roles = EXCLUDED.actor_roles,
    priority    = EXCLUDED.priority,
    is_group    = EXCLUDED.is_group,
    updated_at  = now();

-- Freeze version 1
INSERT INTO public.node_definition_version (clinic_id, node_definition_id, version, snapshot)
SELECT n.clinic_id, n.id, n.current_version,
       jsonb_build_object(
           'code', n.code, 'name', n.name, 'flow_group', n.flow_group,
           'workspace', n.workspace, 'actor_roles', to_jsonb(n.actor_roles),
           'priority', n.priority, 'is_group', n.is_group, 'config', n.config
       )
FROM public.node_definition n
WHERE n.code IN ('THUOC-01', 'THUOC-02', 'THUOC-03', 'THUOC-04')
ON CONFLICT ON CONSTRAINT uq_node_definition_version DO NOTHING;

-- Chuỗi phụ thuộc: soạn → kiểm tra → tư vấn → bàn giao
INSERT INTO public.node_dependency
    (clinic_id, predecessor_code, successor_code, dependency_type, is_blocking)
VALUES
('a0000000-0000-4000-8000-000000000001', 'THUOC-01', 'THUOC-02', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'THUOC-02', 'THUOC-03', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'THUOC-03', 'THUOC-04', 'FS', true)
ON CONFLICT ON CONSTRAINT uq_node_dependency DO UPDATE SET
    dependency_type = EXCLUDED.dependency_type,
    is_blocking     = EXCLUDED.is_blocking;