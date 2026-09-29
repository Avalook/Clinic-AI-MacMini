-- KHO THUỐC KIỂU KIOTVIET (Tuyền 29/09/2026: "ai cho vào có lịch sử ghi hết lại").
--
-- Thêm ba thứ, KHÔNG đổi cách tồn được tính (tồn vẫn chỉ đổi qua
-- `inventory_txn` + trigger `inventory_txn_apply`):
--   1. `drug_catalog.ton_toi_thieu` — ngưỡng cảnh báo sắp hết hàng mỗi thuốc.
--   2. `phieu_kho` — phiếu NHẬP (nhà cung cấp, số hoá đơn, ngày) và phiếu KIỂM
--      kho; mỗi phiếu một mã PN…/KK… duy nhất trong phòng khám.
--   3. `phieu_kho_dong` — từng dòng của phiếu: nhập (thuốc, lô, số, giá nhập)
--      hoặc kiểm (tồn máy / thực tế / lệch), trỏ về đúng dòng sổ kho đã ghi.
--
-- Bất biến ép Ở ĐÂY, không ở Python (SO-LUAT Phần 6):
--   * gửi trùng một lệnh = một phiếu: UNIQUE (clinic_id, khoa_gui);
--   * mã phiếu không trùng: UNIQUE (clinic_id, ma_phieu);
--   * dòng kiểm: lệch = thực tế − tồn máy, thực tế ≥ 0, lệch ≠ 0 ⇔ có dòng sổ;
--   * dòng cùng loại với phiếu (khoá ngoại ghép qua `loai`);
--   * phiếu và dòng CHỈ THÊM — UPDATE/DELETE bị trigger chặn, như sổ kho.
--
-- Chạy lại nhiều lần được.

-- ── 1. Ngưỡng tồn tối thiểu ─────────────────────────────────────────────
ALTER TABLE public.drug_catalog
    ADD COLUMN IF NOT EXISTS ton_toi_thieu numeric(12,3);
ALTER TABLE public.drug_catalog DROP CONSTRAINT IF EXISTS drug_catalog_ton_toi_thieu_khong_am;
ALTER TABLE public.drug_catalog ADD CONSTRAINT drug_catalog_ton_toi_thieu_khong_am
    CHECK (ton_toi_thieu IS NULL OR ton_toi_thieu >= 0);
COMMENT ON COLUMN public.drug_catalog.ton_toi_thieu IS
    'Tồn tối thiểu (đơn vị tồn). Tổng tồn ≤ ngưỡng → cảnh báo sắp hết hàng. NULL = không canh.';

-- ── 2. Phiếu kho ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.phieu_kho (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    loai           text NOT NULL CHECK (loai IN ('NHAP', 'KIEM')),
    ma_phieu       text NOT NULL,
    nha_cung_cap   text,
    so_hoa_don     text,
    ngay_chung_tu  date,
    ghi_chu        text,
    tao_boi        uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc        timestamptz NOT NULL DEFAULT now(),
    -- Khoá chống gửi trùng của lần bấm (Idempotency-Key). Bắt buộc: gửi lại
    -- cùng khoá = cùng phiếu, không ghi sổ lần hai.
    khoa_gui       text NOT NULL CHECK (length(khoa_gui) BETWEEN 1 AND 200),
    CONSTRAINT uq_phieu_kho_ma UNIQUE (clinic_id, ma_phieu),
    CONSTRAINT uq_phieu_kho_khoa UNIQUE (clinic_id, khoa_gui),
    CONSTRAINT uq_phieu_kho_id_clinic_loai UNIQUE (id, clinic_id, loai),
    CONSTRAINT phieu_kho_ncc_chi_o_phieu_nhap CHECK (
        loai = 'NHAP' OR (nha_cung_cap IS NULL AND so_hoa_don IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS phieu_kho_theo_ngay
    ON public.phieu_kho (clinic_id, loai, tao_luc DESC);

COMMENT ON TABLE public.phieu_kho IS
    'Phiếu nhập / phiếu kiểm kho (29/09/2026). Chỉ thêm. Dòng sổ kho của phiếu: '
    'inventory_txn.ref_type = ''phieu_kho'', ref_id = phieu_kho.id.';

CREATE TABLE IF NOT EXISTS public.phieu_kho_dong (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    phieu_kho_id      uuid NOT NULL,
    loai              text NOT NULL,
    stt               integer NOT NULL CHECK (stt > 0),
    drug_catalog_id   uuid NOT NULL REFERENCES public.drug_catalog(id) ON DELETE RESTRICT,
    drug_batch_id     uuid NOT NULL,
    -- NHAP
    so_luong          numeric(12,3),
    gia_nhap          numeric(12,0) CHECK (gia_nhap IS NULL OR gia_nhap >= 0),
    -- KIEM
    ton_may           numeric(12,3),
    thuc_te           numeric(12,3) CHECK (thuc_te IS NULL OR thuc_te >= 0),
    lech              numeric(12,3),
    inventory_txn_id  uuid REFERENCES public.inventory_txn(id) ON DELETE RESTRICT,
    CONSTRAINT phieu_kho_dong_phieu_fkey FOREIGN KEY (phieu_kho_id, clinic_id, loai)
        REFERENCES public.phieu_kho (id, clinic_id, loai) ON DELETE RESTRICT,
    CONSTRAINT phieu_kho_dong_lo_fkey FOREIGN KEY (drug_batch_id, clinic_id)
        REFERENCES public.drug_batch (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT uq_phieu_kho_dong_stt UNIQUE (phieu_kho_id, stt),
    CONSTRAINT uq_phieu_kho_dong_lo UNIQUE (phieu_kho_id, drug_batch_id),
    CONSTRAINT uq_phieu_kho_dong_txn UNIQUE (inventory_txn_id),
    CONSTRAINT phieu_kho_dong_du_bo CHECK (
        CASE loai
            WHEN 'NHAP' THEN
                so_luong IS NOT NULL AND so_luong > 0
                AND ton_may IS NULL AND thuc_te IS NULL AND lech IS NULL
                AND inventory_txn_id IS NOT NULL
            WHEN 'KIEM' THEN
                so_luong IS NULL AND gia_nhap IS NULL
                AND ton_may IS NOT NULL AND ton_may >= 0
                AND thuc_te IS NOT NULL
                AND lech IS NOT NULL AND lech = thuc_te - ton_may
                AND (lech = 0) = (inventory_txn_id IS NULL)
            ELSE false
        END
    )
);

CREATE INDEX IF NOT EXISTS phieu_kho_dong_theo_phieu
    ON public.phieu_kho_dong (clinic_id, phieu_kho_id);

COMMENT ON TABLE public.phieu_kho_dong IS
    'Dòng phiếu nhập / kiểm kho. Kiểm: lệch = thực tế − tồn máy; lệch ≠ 0 thì có '
    'đúng một dòng ADJUST trong sổ kho. Chỉ thêm.';

-- ── 3. Chỉ thêm — dùng lại hàm chặn của sổ kho ─────────────────────────
DROP TRIGGER IF EXISTS phieu_kho_chi_them ON public.phieu_kho;
CREATE TRIGGER phieu_kho_chi_them
    BEFORE UPDATE OR DELETE ON public.phieu_kho
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_append_only_guard();

DROP TRIGGER IF EXISTS phieu_kho_dong_chi_them ON public.phieu_kho_dong;
CREATE TRIGGER phieu_kho_dong_chi_them
    BEFORE UPDATE OR DELETE ON public.phieu_kho_dong
    FOR EACH ROW EXECUTE FUNCTION public.inventory_txn_append_only_guard();

-- Sổ kho: TRUNCATE cũng là xoá. Trigger hàng không bắt được TRUNCATE.
DROP TRIGGER IF EXISTS inventory_txn_khong_truncate ON public.inventory_txn;
CREATE TRIGGER inventory_txn_khong_truncate
    BEFORE TRUNCATE ON public.inventory_txn
    FOR EACH STATEMENT EXECUTE FUNCTION public.inventory_txn_append_only_guard();

-- ── 4. Chỉ mục cho thẻ kho / xuất-nhập-tồn theo thời gian ──────────────
CREATE INDEX IF NOT EXISTS idx_inventory_txn_lo_thoi_gian
    ON public.inventory_txn (drug_batch_id, performed_at);
CREATE INDEX IF NOT EXISTS idx_inventory_txn_clinic_thoi_gian
    ON public.inventory_txn (clinic_id, performed_at);

-- ── 5. RLS — chỉ đọc trong phòng khám của mình, ghi qua FastAPI ─────────
ALTER TABLE public.phieu_kho ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phieu_kho_dong ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS phieu_kho_select_own_clinic ON public.phieu_kho;
CREATE POLICY phieu_kho_select_own_clinic
    ON public.phieu_kho FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

DROP POLICY IF EXISTS phieu_kho_dong_select_own_clinic ON public.phieu_kho_dong;
CREATE POLICY phieu_kho_dong_select_own_clinic
    ON public.phieu_kho_dong FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT, INSERT ON public.phieu_kho, public.phieu_kho_dong TO service_role;
GRANT SELECT ON public.phieu_kho, public.phieu_kho_dong TO authenticated;
