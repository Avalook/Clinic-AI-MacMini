-- LÀM THÊM TẠI QUẦY (Tuyền 01/10/2026, sau buổi thực nghiệm thật).
--
-- "Lễ tân hay người đo sinh hiệu: thêm option làm thêm NƯỚC TIỂU cho từng bệnh
-- nhân ngay từ khi check-in — nhiều việc làm luôn được ở bàn đo sinh hiệu mà
-- không cần bác sĩ chỉ định … QUẢN LÝ ĐIỀU KHIỂN được nút này — gắn thêm hay
-- bớt. Và nó phải xuất hiện trên HÀNH TRÌNH KHÁCH."
--
-- Ba việc:
--
--   1. `lam_them_tai_quay` — DANH SÁCH nút do quản lý quản (dữ liệu, không code
--      cứng): dịch vụ nào (mã trong bảng giá), bật/tắt, thứ tự, hiện ở Tiếp đón
--      / Đo sinh hiệu / cả hai, nhãn ngắn trên nút. Mặc định: Tổng phân tích
--      nước tiểu (CLS_NUOC_TIEU) bật ở cả hai — chỉ khi phòng khám có dịch vụ ấy.
--
--   2. Chỉ định KHÔNG qua phiên khám: `service_order.consultation_id` bỏ NOT
--      NULL; cột mới `nguon_lam_them` ('tiep_don' | 'sinh_hieu') ghi chỉ định
--      tạo ở quầy. Ràng buộc: không có phiên khám thì PHẢI có nguồn quầy — chỉ
--      định của bác sĩ vẫn luôn gắn phiên như cũ. Mọi màn đọc chỉ định theo
--      LƯỢT (visit_id), không theo phiên, nên chỉ định quầy tự đi đúng luồng:
--      quầy thu, cửa làm (FinanceGate), xếp phòng `phong_lam_duoc`, hàng phòng.
--
--   3. Một nút một chỉ định SỐNG mỗi lượt — ép ở Postgres (chỉ mục duy nhất từng
--      phần), không ở Python: hai người bấm cùng lúc (lễ tân + điều dưỡng) thì
--      người sau nhận lại chỉ định của người trước, không ra hai dòng.
--
-- Lần chỉ định (`lan_chi_dinh`): chỉ định quầy KHÔNG có lần (NULL, như mang
-- sang) — "Lần 1, 2…" là lần BÁC SĨ chốt chỉ định; nước tiểu tick lúc check-in
-- không được đẩy lần đầu của bác sĩ thành "Lần 2".
--
-- Chạy lại được.

-- ── 1. Chỉ định không qua phiên khám ────────────────────────────────────────
ALTER TABLE public.service_order ALTER COLUMN consultation_id DROP NOT NULL;
ALTER TABLE public.service_order ADD COLUMN IF NOT EXISTS nguon_lam_them text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'service_order_nguon_lam_them'
                      AND conrelid = 'public.service_order'::regclass) THEN
        ALTER TABLE public.service_order ADD CONSTRAINT service_order_nguon_lam_them
            CHECK (nguon_lam_them IS NULL
                   OR nguon_lam_them IN ('tiep_don', 'sinh_hieu'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'service_order_phien_hoac_quay'
                      AND conrelid = 'public.service_order'::regclass) THEN
        ALTER TABLE public.service_order ADD CONSTRAINT service_order_phien_hoac_quay
            CHECK (consultation_id IS NOT NULL OR nguon_lam_them IS NOT NULL);
    END IF;
END $$;

COMMENT ON COLUMN public.service_order.nguon_lam_them IS
'Chỉ định LÀM THÊM TẠI QUẦY (01/10/2026): tiep_don = lễ tân tick lúc check-in, sinh_hieu = người đo sinh hiệu tick. NULL = bác sĩ / thư ký chỉ định trong phiên khám. Chỉ định quầy không có consultation_id.';

-- Một dịch vụ làm thêm SỐNG mỗi lượt (đã huỷ thì không tính).
CREATE UNIQUE INDEX IF NOT EXISTS uq_service_order_lam_them_song
    ON public.service_order (clinic_id, visit_id, service_code)
    WHERE nguon_lam_them IS NOT NULL AND exec_status <> 'cancelled';

-- ── 2. Lần chỉ định: chỉ định quầy không có lần ────────────────────────────
CREATE OR REPLACE FUNCTION public.gan_lan_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  khoa text;
  lan text;
BEGIN
  -- Mang sang (dòng của lượt trước chuyển visit_id sang lượt này): bỏ số lần của
  -- lượt cũ — nó không thuộc lần nào ở lượt mới.
  -- Làm thêm tại quầy (01/10/2026): không phải lần chốt của bác sĩ.
  IF NEW.mang_tu_visit_id IS NOT NULL OR NEW.nguon_lam_them IS NOT NULL THEN
    NEW.lan_chi_dinh := NULL;
    RETURN NEW;
  END IF;
  IF NEW.lan_chi_dinh IS NOT NULL OR NEW.visit_id IS NULL OR NEW.exec_status IN ('draft', 'cancelled') THEN
    RETURN NEW;
  END IF;
  -- Sửa dòng: chỉ đánh số lúc NHÁP được duyệt (thư ký ghi nháp, bác sĩ duyệt —
  -- lần tính theo lúc duyệt). Dòng cũ chưa có số giữ nguyên NULL.
  IF TG_OP = 'UPDATE' AND OLD.exec_status IS DISTINCT FROM 'draft' THEN
    RETURN NEW;
  END IF;
  khoa := 'clinicai.lan_' || replace(NEW.visit_id::text, '-', '');
  lan := nullif(current_setting(khoa, true), '');
  IF lan IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext('lan_chi_dinh:' || NEW.visit_id::text));
    SELECT (coalesce(max(o.lan_chi_dinh), 0) + 1)::text INTO lan
      FROM public.service_order o
     WHERE o.visit_id = NEW.visit_id AND o.clinic_id = NEW.clinic_id;
    PERFORM set_config(khoa, lan, true);  -- chỉ sống trong giao dịch này
  END IF;
  NEW.lan_chi_dinh := lan::smallint;
  RETURN NEW;
END;
$$;

-- ── 3. Danh sách nút do quản lý quản ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lam_them_tai_quay (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    service_code text NOT NULL,
    -- Chữ trên nút ("Nước tiểu"); trống = tên dịch vụ trong bảng giá.
    nhan         text,
    bat          boolean NOT NULL DEFAULT true,
    thu_tu       integer NOT NULL DEFAULT 0,
    o_tiep_don   boolean NOT NULL DEFAULT true,
    o_sinh_hieu  boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    updated_by   uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    PRIMARY KEY (clinic_id, service_code),
    CONSTRAINT lam_them_tai_quay_nhan_ngan
        CHECK (nhan IS NULL OR char_length(nhan) BETWEEN 1 AND 40),
    -- Bật mà không hiện ở đâu là cấu hình câm — tắt thì nói tắt.
    CONSTRAINT lam_them_tai_quay_hien_o_dau
        CHECK (NOT bat OR o_tiep_don OR o_sinh_hieu)
);

COMMENT ON TABLE public.lam_them_tai_quay IS
'Nút "+ dịch vụ" ở Tiếp đón / Đo sinh hiệu (01/10/2026): lễ tân / người đo tick là chỉ định ngay, không cần bác sĩ. Quản lý thêm / bớt / bật / tắt ở /settings/day-noi. Luật ở services/lam_them_tai_quay_service.py.';

-- Mã phải là DỊCH VỤ trong bảng giá của cùng phòng khám (không khoá ngoại tới
-- service_price — xem lý do ở 20261001210000_phong_lam_theo_dich_vu.sql).
CREATE OR REPLACE FUNCTION public.lam_them_tai_quay_co_dich_vu()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.service_price sp
                    WHERE sp.clinic_id = NEW.clinic_id AND sp."group" = 'dich_vu'
                      AND sp.service_code = NEW.service_code) THEN
        RAISE EXCEPTION 'Không có dịch vụ % trong bảng giá', NEW.service_code
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_lam_them_tai_quay_co_dich_vu ON public.lam_them_tai_quay;
CREATE TRIGGER trg_lam_them_tai_quay_co_dich_vu
    BEFORE INSERT OR UPDATE OF service_code, clinic_id ON public.lam_them_tai_quay
    FOR EACH ROW EXECUTE FUNCTION public.lam_them_tai_quay_co_dich_vu();

-- RLS theo mẫu clinic_room_service: đọc trong phòng khám của mình, KHÔNG ghi
-- từ trình duyệt — ghi chỉ qua API.
ALTER TABLE public.lam_them_tai_quay ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lam_them_tai_quay_select ON public.lam_them_tai_quay;
CREATE POLICY lam_them_tai_quay_select ON public.lam_them_tai_quay
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));
GRANT SELECT ON public.lam_them_tai_quay TO authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.lam_them_tai_quay FROM authenticated;

-- Quản lý đổi danh sách → nút ở quầy hiện / ẩn ngay (dòng SSE chung).
DROP TRIGGER IF EXISTS trg_notify_lam_them_tai_quay ON public.lam_them_tai_quay;
CREATE TRIGGER trg_notify_lam_them_tai_quay
    AFTER INSERT OR UPDATE OR DELETE ON public.lam_them_tai_quay
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- Mặc định: Nước tiểu bật ở cả hai — chỉ phòng khám có dịch vụ ấy; đã có dòng
-- (quản lý đã chỉnh) thì không đè.
INSERT INTO public.lam_them_tai_quay
    (clinic_id, service_code, nhan, bat, thu_tu, o_tiep_don, o_sinh_hieu)
SELECT DISTINCT sp.clinic_id, sp.service_code, 'Nước tiểu', true, 10, true, true
  FROM public.service_price sp
 WHERE sp.service_code = 'CLS_NUOC_TIEU' AND sp."group" = 'dich_vu'
ON CONFLICT (clinic_id, service_code) DO NOTHING;
