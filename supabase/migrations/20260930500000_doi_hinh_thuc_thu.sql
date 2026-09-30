-- ĐỔI HÌNH THỨC THU SAU KHI ĐÃ THU (V7 — Tuyền chốt 30/09/2026: "thu nhầm tiền
-- mặt mà khách chuyển khoản thì ai cũng phải sửa được").
--
-- `payment_cycle.method` VẪN BẤT BIẾN (trigger trg_payment_cycle_guard giữ
-- nguyên): nó là hình thức GHI LÚC THU. Mỗi lần đổi là MỘT DÒNG trong sổ chỉ
-- thêm `payment_cycle_doi_hinh_thuc`; hình thức HIỆU LỰC = dòng mới nhất (không
-- có dòng nào thì là `payment_cycle.method`). Mọi chỗ đọc hình thức (báo cáo
-- cuối ngày, lịch sử quầy thu, bản in phiếu thu, bảng giao dịch) đọc qua
-- `hinh_thuc_hieu_luc(...)` để không chỗ nào tự dựng luật "dòng mới nhất".
--
-- Luật ép ở Postgres (tranh chấp → DB chặn, không nhờ ứng dụng):
--   * chỉ đổi phiếu ĐANG ĐÃ THU (PAID) — phiếu đã huỷ không đổi;
--   * phiếu có khoản hoàn đang chờ / đã hoàn không đổi (tiền hoàn đã đi theo
--     hình thức cũ, đổi nữa là sổ quỹ lệch);
--   * `method_cu` phải đúng hình thức hiệu lực lúc ghi — hai người đổi cùng lúc
--     thì người sau bị từ chối, không có chuỗi đổi "nhảy cóc";
--   * khoá dòng `payment_cycle` (FOR UPDATE) trước khi đọc — cùng thứ tự với
--     trigger hoàn tiền, nên đổi hình thức và tạo khoản hoàn xếp hàng nhau.
-- Mã giao dịch TUỲ CHỌN (như lúc thu, mig 20260925000007). Lý do tuỳ chọn.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.payment_cycle_doi_hinh_thuc (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    cycle_id    uuid NOT NULL,
    -- NULL = phiếu cũ trước CP2 (legacy) không biết hình thức lúc thu.
    method_cu   text CHECK (method_cu IN ('CASH', 'TRANSFER', 'QR')),
    method_moi  text NOT NULL CHECK (method_moi IN ('CASH', 'TRANSFER', 'QR')),
    reference   text CHECK (reference IS NULL
                            OR char_length(btrim(reference)) BETWEEN 1 AND 100),
    ly_do       text CHECK (ly_do IS NULL OR char_length(ly_do) <= 500),
    boi         uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    luc         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payment_cycle_doi_hinh_thuc_cycle_fkey
        FOREIGN KEY (cycle_id, clinic_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id)
        ON DELETE RESTRICT,
    CONSTRAINT payment_cycle_doi_hinh_thuc_khac_cu
        CHECK (method_cu IS DISTINCT FROM method_moi)
);

CREATE INDEX IF NOT EXISTS ix_payment_cycle_doi_hinh_thuc_cycle
    ON public.payment_cycle_doi_hinh_thuc (clinic_id, cycle_id, id DESC);
CREATE INDEX IF NOT EXISTS ix_payment_cycle_doi_hinh_thuc_luc
    ON public.payment_cycle_doi_hinh_thuc (clinic_id, luc);

COMMENT ON TABLE public.payment_cycle_doi_hinh_thuc IS
'Sổ đổi hình thức thu (V7, 30/09/2026). payment_cycle.method = hình thức lúc thu, bất biến; hình thức hiệu lực = dòng mới nhất ở đây. Chỉ thêm.';

-- ── Hình thức / mã giao dịch HIỆU LỰC ────────────────────────────────────
-- SQL thuần, STABLE → planner gập vào câu gọi (subquery theo chỉ mục).
CREATE OR REPLACE FUNCTION public.hinh_thuc_hieu_luc(
    p_clinic uuid, p_cycle uuid, p_goc text)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    SELECT coalesce(
        (SELECT d.method_moi FROM public.payment_cycle_doi_hinh_thuc d
          WHERE d.clinic_id = p_clinic AND d.cycle_id = p_cycle
          ORDER BY d.id DESC LIMIT 1),
        p_goc)
$fn$;

CREATE OR REPLACE FUNCTION public.ma_gd_hieu_luc(
    p_clinic uuid, p_cycle uuid, p_goc text)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    SELECT CASE WHEN x.id IS NULL THEN p_goc ELSE x.reference END
      FROM (SELECT NULL::bigint AS id) z
      LEFT JOIN LATERAL (
           SELECT d.id, d.reference FROM public.payment_cycle_doi_hinh_thuc d
            WHERE d.clinic_id = p_clinic AND d.cycle_id = p_cycle
            ORDER BY d.id DESC LIMIT 1) x ON true
$fn$;

-- ── Chỉ thêm + luật khi thêm ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.payment_cycle_doi_hinh_thuc_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lan record;
    hien_tai text;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_cycle_doi_hinh_thuc là sổ chỉ thêm — không % được', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT status, method INTO lan FROM public.payment_cycle
     WHERE payment_cycle_id = NEW.cycle_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy phiếu thu này'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF lan.status <> 'PAID' THEN
        RAISE EXCEPTION 'Chỉ đổi hình thức phiếu đang đã thu (phiếu này: %)', lan.status
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM public.payment_refund r
                WHERE r.clinic_id = NEW.clinic_id
                  AND r.payment_cycle_id = NEW.cycle_id
                  AND r.status IN ('PENDING', 'COMPLETED')) THEN
        RAISE EXCEPTION 'Phiếu đã có khoản hoàn — không đổi hình thức được'
            USING ERRCODE = 'check_violation';
    END IF;
    hien_tai := public.hinh_thuc_hieu_luc(NEW.clinic_id, NEW.cycle_id, lan.method);
    IF NEW.method_cu IS DISTINCT FROM hien_tai THEN
        RAISE EXCEPTION 'Hình thức vừa được đổi (đang là %) — tải lại rồi đổi', hien_tai
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_payment_cycle_doi_hinh_thuc_guard
    ON public.payment_cycle_doi_hinh_thuc;
CREATE TRIGGER trg_payment_cycle_doi_hinh_thuc_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.payment_cycle_doi_hinh_thuc
    FOR EACH ROW EXECUTE FUNCTION public.payment_cycle_doi_hinh_thuc_guard();

-- TRUNCATE cũng là xoá; trigger hàng không bắt được.
DROP TRIGGER IF EXISTS trg_payment_cycle_doi_hinh_thuc_khong_truncate
    ON public.payment_cycle_doi_hinh_thuc;
CREATE TRIGGER trg_payment_cycle_doi_hinh_thuc_khong_truncate
    BEFORE TRUNCATE ON public.payment_cycle_doi_hinh_thuc
    FOR EACH STATEMENT EXECUTE FUNCTION public.payment_cycle_doi_hinh_thuc_guard();

-- ── Quyền — đọc trong phòng khám của mình, ghi qua FastAPI ────────────────
ALTER TABLE public.payment_cycle_doi_hinh_thuc ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_cycle_doi_hinh_thuc_select_own_clinic
    ON public.payment_cycle_doi_hinh_thuc;
CREATE POLICY payment_cycle_doi_hinh_thuc_select_own_clinic
    ON public.payment_cycle_doi_hinh_thuc
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.payment_cycle_doi_hinh_thuc TO authenticated;
GRANT SELECT, INSERT ON public.payment_cycle_doi_hinh_thuc TO service_role;
