-- PHARMACY + INVENTORY — kho đầy đủ (lô, hạn dùng, nhập-xuất-tồn).
-- NHÀ THUỐC + TỒN KHO — kho đầy đủ (lô, hạn dùng, nhập-xuất-tồn).
--
-- User chốt: làm ĐỦ mô hình kho, không chỉ cấp phát theo đơn.
--   * drug_batch      — lô thuốc: hạn dùng, số lượng tồn, giá nhập
--   * inventory_txn   — mọi biến động tồn kho (nhập/xuất/điều chỉnh/huỷ)
--   * PHARMACIST      — vai mới, thêm vào node_definition + work_item
--   * node cấp phát   — chuỗi 4 bước: soạn → kiểm tra → tư vấn → bàn giao
--
-- Tenant-scoped (clinic_id) + RLS read-only cho authenticated (ADR-0012):
-- mọi ghi qua service_role / FastAPI.
-- Phạm vi theo tenant (clinic_id) + RLS chỉ-đọc cho authenticated (ADR-0012):
-- mọi ghi qua service_role / FastAPI.

-- ---------------------------------------------------------------------------
-- 1. Thêm PHARMACIST vào các check constraint hiện có
-- ---------------------------------------------------------------------------

-- Xóa constraint cũ nếu tồn tại (để thêm lại với danh sách vai trò mới)
ALTER TABLE public.node_definition DROP CONSTRAINT IF EXISTS node_definition_roles_known;
-- Thêm constraint mới cho phép vai trò PHARMACIST trong node_definition
ALTER TABLE public.node_definition ADD CONSTRAINT node_definition_roles_known CHECK (
    actor_roles <@ ARRAY[  -- Kiểm tra actor_roles là tập con của danh sách cho phép
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC', 'CASHIER_DV',
        'PHARMACIST'  -- Vai trò dược sĩ mới
    ]::text[]
);

-- Xóa constraint cũ nếu tồn tại
ALTER TABLE public.work_item DROP CONSTRAINT IF EXISTS work_item_assigned_role_known;
-- Thêm constraint mới cho phép vai trò PHARMACIST trong work_item
ALTER TABLE public.work_item ADD CONSTRAINT work_item_assigned_role_known
    CHECK (assigned_role IS NULL OR assigned_role = ANY (ARRAY[  -- Kiểm tra vai trò được gán
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));  -- Vai trò dược sĩ mới

-- Vai chỉ dùng được khi GẮN ĐƯỢC vào người. Không nới hai constraint dưới đây
-- thì không tạo nổi một dược sĩ nào: staff INSERT hỏng ở primary_department,
-- clinic_membership hỏng ở role, và mọi màn /pharmacy vĩnh viễn không ai vào.
-- Xóa constraint cũ nếu tồn tại
ALTER TABLE public.staff DROP CONSTRAINT IF EXISTS staff_primary_department_check;
-- Thêm constraint mới cho phép vai trò PHARMACIST trong staff
ALTER TABLE public.staff ADD CONSTRAINT staff_primary_department_check
    CHECK (primary_department = ANY (ARRAY[  -- Kiểm tra phòng ban chính
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));  -- Vai trò dược sĩ mới

-- Xóa constraint cũ nếu tồn tại
ALTER TABLE public.clinic_membership DROP CONSTRAINT IF EXISTS clinic_membership_role_check;
-- Thêm constraint mới cho phép vai trò PHARMACIST trong clinic_membership
ALTER TABLE public.clinic_membership ADD CONSTRAINT clinic_membership_role_check
    CHECK (role = ANY (ARRAY[  -- Kiểm tra vai trò thành viên
        'DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'RECEPTION', 'CSKH',
        'MANAGEMENT', 'CASHIER', 'TKYK', 'TRUONG_CA', 'CASHIER_THUOC',
        'CASHIER_DV', 'PHARMACIST']));  -- Vai trò dược sĩ mới

-- ---------------------------------------------------------------------------
-- 2. drug_batch — lô thuốc
-- ---------------------------------------------------------------------------

-- clinic_id KHÔNG có DEFAULT: 20260730000014 đã xoá `default_clinic_id()` khỏi
-- mọi bảng, nhưng nó chạy TRƯỚC file này nên bảng mới không được nó dọn hộ.
-- Để DEFAULT lại thì phòng khám #2 ghi thiếu clinic_id sẽ âm thầm rơi vào
-- Dr4Women — sai lặng lẽ, tệ hơn hẳn NOT NULL violation.
-- Tạo bảng drug_batch (lô thuốc) nếu chưa tồn tại
CREATE TABLE IF NOT EXISTS public.drug_batch (
    id uuid DEFAULT gen_random_uuid() NOT NULL,  -- ID tự sinh ngẫu nhiên
    clinic_id uuid NOT NULL,  -- ID phòng khám (bắt buộc, không có DEFAULT)
    drug_catalog_id uuid NOT NULL,  -- ID thuốc trong danh mục
    batch_code text NOT NULL,                -- mã lô (vd LOT-2026-001)
    expiry_date date NOT NULL,               -- hạn dùng
    quantity_on_hand numeric(12,3) DEFAULT 0 NOT NULL,  -- tồn hiện tại
    unit text DEFAULT 'viên' NOT NULL,       -- đơn vị (viên/hộp/chai/ống)
    cost_price numeric(12,0),                -- giá nhập
    received_at timestamp with time zone DEFAULT now() NOT NULL,  -- thời gian nhập kho
    created_at timestamp with time zone DEFAULT now() NOT NULL,  -- thời gian tạo
    updated_at timestamp with time zone DEFAULT now() NOT NULL,  -- thời gian cập nhật
    CONSTRAINT drug_batch_pkey PRIMARY KEY (id),  -- Khóa chính
    CONSTRAINT drug_batch_clinic_fkey FOREIGN KEY (clinic_id)  -- Khóa ngoại đến phòng khám
        REFERENCES public.clinic(id) ON DELETE RESTRICT,  -- Không cho xóa phòng khám đang có lô thuốc
    CONSTRAINT drug_batch_catalog_fkey FOREIGN KEY (drug_catalog_id)  -- Khóa ngoại đến danh mục thuốc
        REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,  -- Không cho xóa thuốc đang có lô
    CONSTRAINT uq_drug_batch_clinic_code UNIQUE (clinic_id, batch_code)  -- Mã lô duy nhất trong phòng khám
);

-- Tạo index cho cột clinic_id để tăng tốc truy vấn theo phòng khám
CREATE INDEX IF NOT EXISTS idx_drug_batch_clinic ON public.drug_batch (clinic_id);
-- Tạo index cho cột drug_catalog_id để tăng tốc truy vấn theo thuốc
CREATE INDEX IF NOT EXISTS idx_drug_batch_catalog ON public.drug_batch (drug_catalog_id);
-- Tạo index một phần cho cột expiry_date chỉ khi còn tồn kho (tăng tốc tìm lô sắp hết hạn)
CREATE INDEX IF NOT EXISTS idx_drug_batch_expiry ON public.drug_batch (expiry_date)
    WHERE quantity_on_hand > 0;

-- ---------------------------------------------------------------------------
-- 3. inventory_txn — mọi biến động tồn kho (append-only)
-- ---------------------------------------------------------------------------

-- Tạo bảng inventory_txn (giao dịch tồn kho) nếu chưa tồn tại
CREATE TABLE IF NOT EXISTS public.inventory_txn (
    id uuid DEFAULT gen_random_uuid() NOT NULL,  -- ID tự sinh ngẫu nhiên
    clinic_id uuid NOT NULL,  -- ID phòng khám
    drug_batch_id uuid NOT NULL,  -- ID lô thuốc
    txn_type text NOT NULL,                  -- RECEIVE / DISPENSE / ADJUST / DISCARD
    quantity numeric(12,3) NOT NULL,         -- dương = nhập, âm = xuất
    reason text,                             -- lý do (nhập hàng, cấp thuốc, hết hạn...)
    ref_type text,                           -- prescription / manual / adjustment
    ref_id uuid,                             -- prescription.id nếu cấp thuốc
    performed_by_staff_id uuid,  -- ID nhân viên thực hiện
    performed_at timestamp with time zone DEFAULT now() NOT NULL,  -- thời gian thực hiện
    created_at timestamp with time zone DEFAULT now() NOT NULL,  -- thời gian tạo
    CONSTRAINT inventory_txn_pkey PRIMARY KEY (id),  -- Khóa chính
    CONSTRAINT inventory_txn_clinic_fkey FOREIGN KEY (clinic_id)  -- Khóa ngoại đến phòng khám
        REFERENCES public.clinic(id) ON DELETE RESTRICT,  -- Không cho xóa phòng khám đang có giao dịch
    CONSTRAINT inventory_txn_batch_fkey FOREIGN KEY (drug_batch_id)  -- Khóa ngoại đến lô thuốc
        REFERENCES public.drug_batch(id) ON DELETE RESTRICT,  -- Không cho xóa lô đang có giao dịch
    CONSTRAINT inventory_txn_staff_fkey FOREIGN KEY (performed_by_staff_id)  -- Khóa ngoại đến nhân viên
        REFERENCES public.staff(id) ON DELETE SET NULL,  -- Nếu xóa nhân viên thì đặt NULL
    CONSTRAINT inventory_txn_type_check CHECK (  -- Kiểm tra loại giao dịch hợp lệ
        txn_type IN ('RECEIVE', 'DISPENSE', 'ADJUST', 'DISCARD')
    ),
    CONSTRAINT inventory_txn_qty_sign_check CHECK (  -- Kiểm tra dấu của số lượng theo loại
        (txn_type = 'RECEIVE' AND quantity > 0)  -- Nhập kho: số lượng dương
        OR (txn_type IN ('DISPENSE', 'DISCARD') AND quantity < 0)  -- Xuất/huỷ: số lượng âm
        OR (txn_type = 'ADJUST' AND quantity <> 0)  -- Điều chỉnh: khác 0
    )
);

-- Tạo index cho cột clinic_id để tăng tốc truy vấn theo phòng khám
CREATE INDEX IF NOT EXISTS idx_inventory_txn_clinic ON public.inventory_txn (clinic_id);
-- Tạo index cho cột drug_batch_id để tăng tốc truy vấn theo lô thuốc
CREATE INDEX IF NOT EXISTS idx_inventory_txn_batch ON public.inventory_txn (drug_batch_id);
-- Tạo index một phần cho cột ref_type, ref_id khi ref_id không null (tăng tốc truy vấn theo đơn thuốc)
CREATE INDEX IF NOT EXISTS idx_inventory_txn_ref ON public.inventory_txn (ref_type, ref_id)
    WHERE ref_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. Trigger: cập nhật quantity_on_hand khi có txn mới
-- ---------------------------------------------------------------------------

-- Tạo hoặc thay thế hàm trigger cập nhật tồn kho
CREATE OR REPLACE FUNCTION public.inventory_txn_apply()
RETURNS trigger  -- Trả về trigger
LANGUAGE plpgsql  -- Ngôn ngữ PL/pgSQL
AS $$
BEGIN
    -- Cập nhật số lượng tồn của lô thuốc: tồn hiện tại + số lượng giao dịch mới
    UPDATE public.drug_batch
       SET quantity_on_hand = quantity_on_hand + NEW.quantity,  -- Cộng số lượng mới vào tồn
           updated_at = now()  -- Cập nhật thời gian
     WHERE id = NEW.drug_batch_id;  -- Chỉ cập nhật lô thuốc liên quan
    RETURN NEW;  -- Trả về dòng mới
END
$$;

-- Xóa trigger cũ nếu tồn tại
DROP TRIGGER IF EXISTS inventory_txn_apply_trigger ON public.inventory_txn;
-- Tạo trigger mới: sau khi INSERT vào inventory_txn thì gọi hàm cập nhật tồn kho
CREATE TRIGGER inventory_txn_apply_trigger
    AFTER INSERT ON public.inventory_txn  -- Sau khi chèn dòng mới
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_apply();  -- Cho mỗi dòng

-- ---------------------------------------------------------------------------
-- 5. RLS — read-only cho authenticated, ghi qua service_role
-- ---------------------------------------------------------------------------

-- Bật Row Level Security cho bảng drug_batch
ALTER TABLE public.drug_batch ENABLE ROW LEVEL SECURITY;
-- Bật Row Level Security cho bảng inventory_txn
ALTER TABLE public.inventory_txn ENABLE ROW LEVEL SECURITY;

-- Xóa policy cũ nếu tồn tại
DROP POLICY IF EXISTS drug_batch_select_own_clinic ON public.drug_batch;
-- Tạo policy cho phép authenticated đọc lô thuốc của phòng khám mình
CREATE POLICY drug_batch_select_own_clinic
    ON public.drug_batch FOR SELECT TO authenticated  -- Chỉ cho phép SELECT
    USING (clinic_id IN (SELECT public.current_clinic_ids()));  -- Chỉ đọc phòng khám hiện tại

-- Xóa policy cũ nếu tồn tại
DROP POLICY IF EXISTS inventory_txn_select_own_clinic ON public.inventory_txn;
-- Tạo policy cho phép authenticated đọc giao dịch tồn kho của phòng khám mình
CREATE POLICY inventory_txn_select_own_clinic
    ON public.inventory_txn FOR SELECT TO authenticated  -- Chỉ cho phép SELECT
    USING (clinic_id IN (SELECT public.current_clinic_ids()));  -- Chỉ đọc phòng khám hiện tại

-- Grant phải viết tay ở đây. 20260730000008 suy grant từ pg_policy, nhưng nó
-- chạy TRƯỚC file này — bảng sinh sau không có ai cấp quyền hộ, và policy chỉ
-- thu hẹp quyền sẵn có chứ không tạo ra quyền. Thiếu hai dòng dưới đây thì mọi
-- màn /pharmacy trả permission denied dù policy trông hoàn toàn đúng.
-- Cấp toàn quyền cho service_role (backend) trên cả hai bảng
GRANT ALL ON public.drug_batch, public.inventory_txn TO service_role;
-- Cấp quyền SELECT cho authenticated (người dùng đã đăng nhập)
GRANT SELECT ON public.drug_batch, public.inventory_txn TO authenticated;

-- ---------------------------------------------------------------------------
-- 6. Node cấp phát thuốc — chuỗi 4 bước (soạn → kiểm tra → tư vấn → bàn giao)
-- ---------------------------------------------------------------------------

-- Chèn 4 node định nghĩa cho quy trình cấp phát thuốc
INSERT INTO public.node_definition
    (clinic_id, code, name, flow_group, workspace, actor_roles, priority, is_group)
VALUES
('a0000000-0000-4000-8000-000000000001', 'THUOC-01', 'Soạn thuốc theo đơn', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),  -- Bước 1: Soạn thuốc
('a0000000-0000-4000-8000-000000000001', 'THUOC-02', 'Kiểm tra trước bàn giao', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),  -- Bước 2: Kiểm tra
('a0000000-0000-4000-8000-000000000001', 'THUOC-03', 'Tư vấn dùng thuốc', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false),  -- Bước 3: Tư vấn
('a0000000-0000-4000-8000-000000000001', 'THUOC-04', 'Bàn giao thuốc', 'dich_vu', 'khu_nha_thuoc', ARRAY['PHARMACIST'], 'P0', false)  -- Bước 4: Bàn giao
ON CONFLICT ON CONSTRAINT uq_node_definition_clinic_code DO UPDATE SET  -- Nếu trùng mã thì cập nhật
    name        = EXCLUDED.name,  -- Cập nhật tên
    flow_group  = EXCLUDED.flow_group,  -- Cập nhật nhóm quy trình
    workspace   = EXCLUDED.workspace,  -- Cập nhật không gian làm việc
    actor_roles = EXCLUDED.actor_roles,  -- Cập nhật vai trò thực hiện
    priority    = EXCLUDED.priority,  -- Cập nhật ưu tiên
    is_group    = EXCLUDED.is_group,  -- Cập nhật cờ nhóm
    updated_at  = now();  -- Cập nhật thời gian

-- Freeze version 1
-- Đóng băng phiên bản 1 của các node
INSERT INTO public.node_definition_version (clinic_id, node_definition_id, version, snapshot)
SELECT n.clinic_id, n.id, n.current_version,  -- Chọn dữ liệu từ node_definition
       jsonb_build_object(  -- Tạo snapshot JSON
           'code', n.code, 'name', n.name, 'flow_group', n.flow_group,
           'workspace', n.workspace, 'actor_roles', to_jsonb(n.actor_roles),
           'priority', n.priority, 'is_group', n.is_group, 'config', n.config
       )
FROM public.node_definition n  -- Từ bảng node_definition
WHERE n.code IN ('THUOC-01', 'THUOC-02', 'THUOC-03', 'THUOC-04')  -- Chỉ các node thuốc
ON CONFLICT ON CONSTRAINT uq_node_definition_version DO NOTHING;  -- Nếu trùng thì bỏ qua

-- Chuỗi phụ thuộc: soạn → kiểm tra → tư vấn → bàn giao
-- Tạo các quan hệ phụ thuộc giữa các node
INSERT INTO public.node_dependency
    (clinic_id, predecessor_code, successor_code, dependency_type, is_blocking)
VALUES
('a0000000-0000-4000-8000-000000000001', 'THUOC-01', 'THUOC-02', 'FS', true),  -- Soạn → Kiểm tra (FS = Finish-to-Start)
('a0000000-0000-4000-8000-000000000001', 'THUOC-02', 'THUOC-03', 'FS', true),  -- Kiểm tra → Tư vấn
('a0000000-0000-4000-8000-000000000001', 'THUOC-03', 'THUOC-04', 'FS', true)  -- Tư vấn → Bàn giao
ON CONFLICT ON CONSTRAINT uq_node_dependency DO UPDATE SET  -- Nếu trùng thì cập nhật
    dependency_type = EXCLUDED.dependency_type,  -- Cập nhật loại phụ thuộc
    is_blocking     = EXCLUDED.is_blocking;  -- Cập nhật cờ chặn