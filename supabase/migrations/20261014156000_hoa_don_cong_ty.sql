-- HOÁ ĐƠN CÔNG TY (G5c · Tuyền 14/10/2026, Q15 + Q19).
--
-- Khách xuất hoá đơn về CÔNG TY thì kế toán cần tên công ty + địa chỉ + mã số
-- thuế (+ email nhận hoá đơn). Thông tin lưu THEO HOÁ ĐƠN (phiếu thu =
-- payment_cycle) dưới dạng BẢN CHỤP lúc ghi; công ty còn được ghi vào HỒ SƠ khách
-- (nhiều công ty/khách) để lần sau điền sẵn. Sửa công ty trong hồ sơ KHÔNG đổi
-- bản chụp trên hoá đơn đã ghi; sửa thẳng bản chụp thì ghi lịch sử (ai, lúc nào,
-- cũ → mới).
--
-- MST sai chỉ NHẮC (không có CHECK ở đây) — luật nhắc nằm ở service.
-- Chạy lại được. Không đụng bảng vận hành.

-- ─── 1. Công ty trong hồ sơ khách (điền sẵn lần sau) ────────────────────────
CREATE TABLE IF NOT EXISTS public.khach_cong_ty (
    id                uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id         uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    clinic_patient_id uuid        NOT NULL,
    ten_cong_ty       text        NOT NULL CHECK (char_length(btrim(ten_cong_ty)) BETWEEN 1 AND 400),
    dia_chi_cong_ty   text        NOT NULL DEFAULT '' CHECK (char_length(dia_chi_cong_ty) <= 500),
    ma_so_thue        text        NOT NULL DEFAULT '' CHECK (char_length(ma_so_thue) <= 20),
    email_nhan_hd     text        NOT NULL DEFAULT '' CHECK (char_length(email_nhan_hd) <= 254),
    nguoi_mua         text        NOT NULL DEFAULT '' CHECK (char_length(nguoi_mua) <= 200),
    -- Lần gần nhất công ty này được gắn vào một hoá đơn → "điền sẵn lần trước".
    dung_luc          timestamptz,
    -- Gỡ khỏi hồ sơ = ẩn (hoàn tác được), không xoá dòng.
    an_luc            timestamptz,
    tao_boi           uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    sua_boi           uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc           timestamptz NOT NULL DEFAULT now(),
    -- `patient` chỉ khoá theo clinic_patient_id; service kiểm khách thuộc đúng
    -- phòng khám trước khi ghi.
    CONSTRAINT khach_cong_ty_fk_patient
        FOREIGN KEY (clinic_patient_id)
        REFERENCES public.patient (clinic_patient_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_khach_cong_ty_khach
    ON public.khach_cong_ty (clinic_id, clinic_patient_id);
COMMENT ON TABLE public.khach_cong_ty IS
'Công ty của khách (nhiều công ty/khách) để điền sẵn hoá đơn công ty. Ẩn = an_luc, không xoá (G5c 14/10/2026).';

ALTER TABLE public.khach_cong_ty ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS khach_cong_ty_select_own_clinic ON public.khach_cong_ty;
CREATE POLICY khach_cong_ty_select_own_clinic ON public.khach_cong_ty
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.khach_cong_ty TO service_role;

-- ─── 2. Bản chụp công ty trên MỘT hoá đơn (phiếu thu) ───────────────────────
CREATE TABLE IF NOT EXISTS public.hoa_don_cong_ty (
    id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id        uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    payment_cycle_id uuid        NOT NULL,
    ten_cong_ty      text        NOT NULL CHECK (char_length(btrim(ten_cong_ty)) BETWEEN 1 AND 400),
    dia_chi_cong_ty  text        NOT NULL DEFAULT '' CHECK (char_length(dia_chi_cong_ty) <= 500),
    ma_so_thue       text        NOT NULL DEFAULT '' CHECK (char_length(ma_so_thue) <= 20),
    email_nhan_hd    text        NOT NULL DEFAULT '' CHECK (char_length(email_nhan_hd) <= 254),
    -- Ô "Người mua" của mẫu MISA: mặc định để TRỐNG (Q19), ai muốn thì điền.
    nguoi_mua        text        NOT NULL DEFAULT '' CHECK (char_length(nguoi_mua) <= 200),
    khach_cong_ty_id uuid        REFERENCES public.khach_cong_ty (id) ON DELETE SET NULL,
    -- Bỏ chọn "xuất hoá đơn công ty" = đặt bo_luc (hoàn tác được: ghi lại là hết bỏ).
    bo_luc           timestamptz,
    ghi_boi          uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    ghi_luc          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hoa_don_cong_ty_fk_cycle
        FOREIGN KEY (payment_cycle_id, clinic_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id) ON DELETE CASCADE,
    CONSTRAINT uq_hoa_don_cong_ty_cycle UNIQUE (clinic_id, payment_cycle_id)
);
COMMENT ON TABLE public.hoa_don_cong_ty IS
'Bản chụp công ty trên hoá đơn (phiếu thu). Sửa công ty trong hồ sơ khách không đổi bản chụp này (G5c 14/10/2026).';

ALTER TABLE public.hoa_don_cong_ty ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_cong_ty_select_own_clinic ON public.hoa_don_cong_ty;
CREATE POLICY hoa_don_cong_ty_select_own_clinic ON public.hoa_don_cong_ty
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.hoa_don_cong_ty TO service_role;

-- ─── 3. Lịch sử sửa bản chụp (chỉ thêm, không sửa/xoá) ──────────────────────
CREATE TABLE IF NOT EXISTS public.hoa_don_cong_ty_lich_su (
    id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id        uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    payment_cycle_id uuid        NOT NULL,
    -- ghi (lần đầu) | sua | bo | lai (ghi lại sau khi bỏ)
    hanh_dong        text        NOT NULL CHECK (hanh_dong IN ('ghi', 'sua', 'bo', 'lai')),
    cu_ten           text        NOT NULL DEFAULT '',
    cu_dia_chi       text        NOT NULL DEFAULT '',
    cu_ma_so_thue    text        NOT NULL DEFAULT '',
    cu_email         text        NOT NULL DEFAULT '',
    cu_nguoi_mua     text        NOT NULL DEFAULT '',
    moi_ten          text        NOT NULL DEFAULT '',
    moi_dia_chi      text        NOT NULL DEFAULT '',
    moi_ma_so_thue   text        NOT NULL DEFAULT '',
    moi_email        text        NOT NULL DEFAULT '',
    moi_nguoi_mua    text        NOT NULL DEFAULT '',
    sua_boi          uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hoa_don_cong_ty_ls_cycle
    ON public.hoa_don_cong_ty_lich_su (clinic_id, payment_cycle_id, sua_luc DESC);
COMMENT ON TABLE public.hoa_don_cong_ty_lich_su IS
'Lịch sử ghi/sửa/bỏ công ty trên hoá đơn: ai, lúc nào, cũ → mới (G5c 14/10/2026).';

ALTER TABLE public.hoa_don_cong_ty_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_cong_ty_lich_su_select_own_clinic ON public.hoa_don_cong_ty_lich_su;
CREATE POLICY hoa_don_cong_ty_lich_su_select_own_clinic ON public.hoa_don_cong_ty_lich_su
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.hoa_don_cong_ty_lich_su TO service_role;
