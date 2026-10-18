-- Kho thuốc/vật tư chỉ được đọc qua FastAPI, nơi kiểm tra capability.
-- PostgREST vẫn cần schema usage cho các màn auth/realtime, nhưng người dùng
-- cùng clinic không được đọc trực tiếp sổ kho chỉ nhờ clinic membership.
-- `service_role` là backend của FastAPI và giữ quyền cần thiết.

BEGIN;

DROP POLICY IF EXISTS drug_batch_select_own_clinic ON public.drug_batch;
DROP POLICY IF EXISTS inventory_txn_select_own_clinic ON public.inventory_txn;
DROP POLICY IF EXISTS drug_return_select_own_clinic ON public.drug_return;
DROP POLICY IF EXISTS phieu_kho_select_own_clinic ON public.phieu_kho;
DROP POLICY IF EXISTS phieu_kho_dong_select_own_clinic ON public.phieu_kho_dong;
DROP POLICY IF EXISTS kiem_ke_ca_select_own_clinic ON public.kiem_ke_ca;
DROP POLICY IF EXISTS kiem_ke_ca_dong_select_own_clinic ON public.kiem_ke_ca_dong;
DROP POLICY IF EXISTS vat_tu_phieu_select_own_clinic ON public.vat_tu_phieu;
DROP POLICY IF EXISTS vat_tu_ton_select_own_clinic ON public.vat_tu_ton;
DROP POLICY IF EXISTS vat_tu_txn_select_own_clinic ON public.vat_tu_txn;
DROP POLICY IF EXISTS vat_tu_nhap_cho_duyet_select_own_clinic
    ON public.vat_tu_nhap_cho_duyet;

REVOKE ALL PRIVILEGES ON TABLE
    public.drug_batch,
    public.inventory_txn,
    public.drug_return,
    public.phieu_kho,
    public.phieu_kho_dong,
    public.kiem_ke_ca,
    public.kiem_ke_ca_dong,
    public.vat_tu_phieu,
    public.vat_tu_ton,
    public.vat_tu_txn,
    public.vat_tu_nhap_cho_duyet
FROM anon, authenticated;

GRANT SELECT ON TABLE
    public.drug_batch,
    public.inventory_txn,
    public.drug_return,
    public.phieu_kho,
    public.phieu_kho_dong,
    public.kiem_ke_ca,
    public.kiem_ke_ca_dong,
    public.vat_tu_phieu,
    public.vat_tu_ton,
    public.vat_tu_txn,
    public.vat_tu_nhap_cho_duyet
TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;
