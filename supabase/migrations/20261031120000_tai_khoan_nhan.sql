-- TÀI KHOẢN NGÂN HÀNG NHẬN CHUYỂN KHOẢN (31/10/2026).
--
-- Trước: hình thức thu chỉ có Tiền mặt / Chuyển khoản — không biết tiền chuyển
-- khoản vào TÀI KHOẢN nào, kế toán phải đoán khi đối chiếu sao kê từng ngân hàng.
--
-- 1. `tai_khoan_nhan` — danh mục tài khoản nhận do Quản lý tự thêm / sửa / tắt
--    (bao nhiêu cũng được). Thuộc một cơ sở, hoặc `location_id` NULL = dùng chung.
--    Không xoá (luật "mọi thao tác hoàn tác được"): tắt `dang_dung`, bật lại được.
--    Mỗi cơ sở (và nhóm "dùng chung") tối đa MỘT tài khoản mặc định — ép bằng chỉ
--    mục duy nhất; mặc định thì phải đang dùng (CHECK) — tắt tài khoản mặc định là
--    bỏ luôn mặc định trong cùng lệnh.
-- 2. `payment_cycle.tai_khoan_nhan_id` — tài khoản nhận phần CHUYỂN KHOẢN của lần
--    thu (một lần thu có tối đa một phần chuyển khoản). NULL = chưa phân loại
--    (lần thu cũ, hoặc chưa cài tài khoản nào). Khoá ngoại kèm clinic_id: không
--    gắn được tài khoản của phòng khám khác.
-- 3. `payment_refund.tai_khoan_nhan_id` — hoàn chuyển khoản đi từ tài khoản nào.
-- 4. `payment_cycle_guard`: chép nguyên bản 20261014147000, chỉ thêm MỘT lối
--    cập nhật: đổi `tai_khoan_nhan_id` khi trạng thái giữ nguyên (sửa tài khoản
--    chọn nhầm — vết nằm ở event_log `payment.receiving_account_changed`). Mọi
--    cột đã ghi khác vẫn bất biến.
-- 5. Báo tin SSE cho `tai_khoan_nhan` (quầy thu thấy ngay tài khoản mới / vừa tắt).
--
-- Không đụng `don_khach_thu`: bảng mới không chứa dữ liệu khách; hai cột mới trỏ
-- vào danh mục (không bị xoá khi dọn khách thử).
--
-- Chạy lại được.

-- ── 1. Danh mục ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.tai_khoan_nhan (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    location_id    uuid REFERENCES public.clinic_location (id) ON DELETE RESTRICT,
    ten_goi        text NOT NULL,
    ngan_hang      text NOT NULL,
    so_tai_khoan   text NOT NULL,
    chu_tai_khoan  text NOT NULL,
    mac_dinh       boolean NOT NULL DEFAULT false,
    dang_dung      boolean NOT NULL DEFAULT true,
    tao_luc        timestamptz NOT NULL DEFAULT now(),
    tao_boi        uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    sua_luc        timestamptz NOT NULL DEFAULT now(),
    sua_boi        uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    CONSTRAINT tai_khoan_nhan_id_clinic UNIQUE (id, clinic_id),
    CONSTRAINT tai_khoan_nhan_chu_hop_le CHECK (
        length(btrim(ten_goi)) BETWEEN 1 AND 60
        AND length(btrim(ngan_hang)) BETWEEN 1 AND 100
        AND so_tai_khoan ~ '^[0-9A-Za-z]{4,30}$'
        AND length(btrim(chu_tai_khoan)) BETWEEN 1 AND 120),
    CONSTRAINT tai_khoan_nhan_mac_dinh_dang_dung CHECK (NOT mac_dinh OR dang_dung)
);

-- Một tài khoản mặc định cho mỗi cơ sở; NULL (dùng chung) là một nhóm riêng.
CREATE UNIQUE INDEX IF NOT EXISTS ux_tai_khoan_nhan_mot_mac_dinh
    ON public.tai_khoan_nhan (
        clinic_id, coalesce(location_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE mac_dinh;
-- Cùng một số tài khoản ở cùng ngân hàng chỉ khai một lần (dùng ở hai cơ sở thì
-- để "dùng chung").
CREATE UNIQUE INDEX IF NOT EXISTS ux_tai_khoan_nhan_so
    ON public.tai_khoan_nhan (clinic_id, lower(btrim(ngan_hang)), so_tai_khoan);

COMMENT ON TABLE public.tai_khoan_nhan IS
'Tài khoản ngân hàng nhận chuyển khoản (31/10/2026). Quản lý thêm/sửa/tắt; không xoá. location_id NULL = dùng chung mọi cơ sở. Một mặc định mỗi cơ sở.';

ALTER TABLE public.tai_khoan_nhan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tai_khoan_nhan_select_own_clinic ON public.tai_khoan_nhan;
CREATE POLICY tai_khoan_nhan_select_own_clinic ON public.tai_khoan_nhan
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.tai_khoan_nhan TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.tai_khoan_nhan TO service_role;

-- Không xoá: tắt là đủ (hoàn tác được), và lần thu cũ vẫn trỏ vào.
CREATE OR REPLACE FUNCTION public.tai_khoan_nhan_khong_xoa()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Tài khoản nhận không xoá được — tắt "đang dùng" thay vì xoá'
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_tai_khoan_nhan_khong_xoa ON public.tai_khoan_nhan;
CREATE TRIGGER trg_tai_khoan_nhan_khong_xoa
    BEFORE DELETE ON public.tai_khoan_nhan
    FOR EACH ROW EXECUTE FUNCTION public.tai_khoan_nhan_khong_xoa();

-- ── 2–3. Cột trên lần thu / khoản hoàn ─────────────────────────────────────
ALTER TABLE public.payment_cycle
    ADD COLUMN IF NOT EXISTS tai_khoan_nhan_id uuid;
ALTER TABLE public.payment_refund
    ADD COLUMN IF NOT EXISTS tai_khoan_nhan_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'payment_cycle_tai_khoan_nhan_fkey') THEN
        ALTER TABLE public.payment_cycle
            ADD CONSTRAINT payment_cycle_tai_khoan_nhan_fkey
            FOREIGN KEY (tai_khoan_nhan_id, clinic_id)
            REFERENCES public.tai_khoan_nhan (id, clinic_id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'payment_refund_tai_khoan_nhan_fkey') THEN
        ALTER TABLE public.payment_refund
            ADD CONSTRAINT payment_refund_tai_khoan_nhan_fkey
            FOREIGN KEY (tai_khoan_nhan_id, clinic_id)
            REFERENCES public.tai_khoan_nhan (id, clinic_id) ON DELETE RESTRICT;
    END IF;
END $$;

COMMENT ON COLUMN public.payment_cycle.tai_khoan_nhan_id IS
'Tài khoản nhận phần chuyển khoản của lần thu (31/10/2026). NULL = chưa phân loại. Sửa được khi trạng thái giữ nguyên (vết: event_log payment.receiving_account_changed).';
COMMENT ON COLUMN public.payment_refund.tai_khoan_nhan_id IS
'Tài khoản chuyển trả khi hoàn chuyển khoản (31/10/2026). NULL = tiền mặt / chưa phân loại.';

-- ── 4. Guard lần thu: thêm lối đổi tài khoản nhận ───────────────────────────
CREATE OR REPLACE FUNCTION public.payment_cycle_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment_cycle là sổ các lần thu — không xoá'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT (
        (OLD.status = 'PENDING_VERIFICATION' AND NEW.status IN ('PAID', 'CANCELLED'))
        OR (OLD.status = 'PAID' AND NEW.status = 'VOIDED')
        OR (OLD.status = NEW.status AND OLD.payment_id IS NULL
            AND NEW.payment_id IS NOT NULL)
        -- Sửa tài khoản nhận chọn nhầm (31/10/2026): chỉ lần thu còn hiệu lực.
        OR (OLD.status = NEW.status
            AND OLD.status IN ('PENDING_VERIFICATION', 'PAID')
            AND NEW.tai_khoan_nhan_id IS DISTINCT FROM OLD.tai_khoan_nhan_id)
    ) THEN
        RAISE EXCEPTION 'payment_cycle: không chuyển % → % được', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.payment_cycle_id <> OLD.payment_cycle_id
       OR NEW.clinic_id <> OLD.clinic_id OR NEW.visit_id <> OLD.visit_id
       OR NEW.kind <> OLD.kind OR NEW.amount <> OLD.amount
       OR NEW.bill_revision IS DISTINCT FROM OLD.bill_revision
       OR NEW.method IS DISTINCT FROM OLD.method
       OR NEW.legacy <> OLD.legacy
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at <> OLD.created_at
       OR (OLD.paid_at IS NOT NULL AND NEW.paid_at IS DISTINCT FROM OLD.paid_at)
       OR (OLD.confirmed_by IS NOT NULL
           AND NEW.confirmed_by IS DISTINCT FROM OLD.confirmed_by)
       OR (OLD.reference IS NOT NULL AND NEW.reference IS DISTINCT FROM OLD.reference)
       OR (OLD.payment_id IS NOT NULL AND NEW.payment_id IS DISTINCT FROM OLD.payment_id)
       -- Cờ, mã nguyên nhân đối soát và số ngân hàng thật nhận chỉ hình thành
       -- cùng lúc chờ → đã thu.
       OR ((NEW.can_doi_soat IS DISTINCT FROM OLD.can_doi_soat
            OR NEW.doi_soat_ly_do IS DISTINCT FROM OLD.doi_soat_ly_do
            OR NEW.so_tien_thuc_nhan IS DISTINCT FROM OLD.so_tien_thuc_nhan)
           AND NOT (OLD.status = 'PENDING_VERIFICATION' AND NEW.status = 'PAID'))
       -- Giảm giá ghi lúc INSERT, không sửa được.
       OR NEW.discount_type   IS DISTINCT FROM OLD.discount_type
       OR NEW.discount_value  IS DISTINCT FROM OLD.discount_value
       OR NEW.discount_amount <> OLD.discount_amount
       OR NEW.discount_reason IS DISTINCT FROM OLD.discount_reason
       OR NEW.discount_by     IS DISTINCT FROM OLD.discount_by
       OR NEW.original_amount IS DISTINCT FROM OLD.original_amount
    THEN
        RAISE EXCEPTION 'payment_cycle: cột đã ghi không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- ── 5. Báo tin cho màn (SSE) ────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_notify_tai_khoan_nhan ON public.tai_khoan_nhan;
CREATE TRIGGER trg_notify_tai_khoan_nhan
    AFTER INSERT OR UPDATE OR DELETE ON public.tai_khoan_nhan
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
