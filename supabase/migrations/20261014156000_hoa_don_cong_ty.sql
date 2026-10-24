-- HOÁ ĐƠN CÔNG TY + ĐÁNH DẤU XUẤT MISA (G5c · Antigravity 14/10/2026).
--
-- Bảng hoa_don_cong_ty: thông tin công ty theo payment_cycle (snapshot lúc tick).
-- Bảng khach_cong_ty: nhiều công ty/khách, điền sẵn lần trước, ghi trước vào hồ sơ.
-- Bảng hoa_don_misa_xuat: đánh dấu "đã xuất MISA" + bản chụp tổng.
-- Thuế KHÔNG chạm vận hành. Chạy lại được.

-- ─── 1. MST validator (nhắc nhở, không chặn) ───────────────────────────────
-- MST hợp lệ: 10 số, hoặc 10 số + "-" + 3 số (mã đơn vị phụ thuộc).
-- Hàm chỉ dùng để UI hỏi; ràng buộc DB không CHECK MST (theo đề bài: chỉ nhắc).
CREATE OR REPLACE FUNCTION public.mst_co_ve_hop_le(mst text)
RETURNS boolean
LANGUAGE sql IMMUTABLE
AS $$
    SELECT mst ~ '^[0-9]{10}(-[0-9]{3})?$'
$$;

-- ─── 2. Bảng khach_cong_ty ─────────────────────────────────────────────────
-- Liên kết khách ↔ công ty mặc định (điền sẵn lần trước).
-- Nhiều công ty/khách: một khách có thể gắn nhiều công ty, công ty mặc định = is_mac_dinh.
CREATE TABLE IF NOT EXISTS public.khach_cong_ty (
    id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id        uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    clinic_patient_id uuid       NOT NULL,
    ten_cong_ty      text        NOT NULL CHECK (char_length(btrim(ten_cong_ty)) BETWEEN 1 AND 400),
    dia_chi_cong_ty  text        NOT NULL DEFAULT '' CHECK (char_length(dia_chi_cong_ty) <= 500),
    ma_so_thue       text        NOT NULL DEFAULT '' CHECK (char_length(ma_so_thue) <= 20),
    email_nhan_hd    text        NOT NULL DEFAULT '' CHECK (char_length(email_nhan_hd) <= 254),
    is_mac_dinh      boolean     NOT NULL DEFAULT true,
    ghi_chu          text        NOT NULL DEFAULT '',
    tao_boi          uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    tao_luc          timestamptz NOT NULL DEFAULT now(),
    sua_boi          uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT khach_cong_ty_fk_patient
        FOREIGN KEY (clinic_patient_id)
        REFERENCES public.patient (clinic_patient_id) ON DELETE CASCADE
);

-- Chỉ một công ty mặc định mỗi khách/phòng khám.
CREATE UNIQUE INDEX IF NOT EXISTS uq_khach_cong_ty_mac_dinh
    ON public.khach_cong_ty (clinic_id, clinic_patient_id)
    WHERE is_mac_dinh = true;

-- RLS: nhân viên cùng phòng khám.
ALTER TABLE public.khach_cong_ty ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS khach_cong_ty_clinic ON public.khach_cong_ty;
CREATE POLICY khach_cong_ty_clinic ON public.khach_cong_ty
    USING (clinic_id = (SELECT c.id FROM public.clinic c
           JOIN public.clinic_membership m ON m.clinic_id = c.id
           WHERE m.staff_id = auth.uid() LIMIT 1));

COMMENT ON TABLE public.khach_cong_ty IS
'Công ty mặc định của khách (để điền sẵn hoá đơn). Nhiều công ty/khách được. (G5c 14/10/2026)';

-- ─── 3. Bảng hoa_don_cong_ty ───────────────────────────────────────────────
-- Snapshot thông tin công ty tại thời điểm tick "hoá đơn công ty" cho payment_cycle.
-- Đổi thông tin công ty sau khi xuất → snapshot này không đổi.
CREATE TABLE IF NOT EXISTS public.hoa_don_cong_ty (
    id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id        uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    payment_cycle_id uuid        NOT NULL,
    -- snapshot tại thời điểm tick
    ten_cong_ty      text        NOT NULL CHECK (char_length(btrim(ten_cong_ty)) BETWEEN 1 AND 400),
    dia_chi_cong_ty  text        NOT NULL DEFAULT '',
    ma_so_thue       text        NOT NULL DEFAULT '',
    email_nhan_hd    text        NOT NULL DEFAULT '',
    -- nguồn gốc
    khach_cong_ty_id uuid        REFERENCES public.khach_cong_ty (id) ON DELETE SET NULL,
    ghi_boi          uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    ghi_luc          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hoa_don_cong_ty_fk_cycle
        FOREIGN KEY (payment_cycle_id, clinic_id)
        REFERENCES public.payment_cycle (payment_cycle_id, clinic_id) ON DELETE CASCADE
);

-- Mỗi payment_cycle chỉ có một bản ghi công ty.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hoa_don_cong_ty_cycle
    ON public.hoa_don_cong_ty (clinic_id, payment_cycle_id);

-- RLS
ALTER TABLE public.hoa_don_cong_ty ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_cong_ty_clinic ON public.hoa_don_cong_ty;
CREATE POLICY hoa_don_cong_ty_clinic ON public.hoa_don_cong_ty
    USING (clinic_id = (SELECT c.id FROM public.clinic c
           JOIN public.clinic_membership m ON m.clinic_id = c.id
           WHERE m.staff_id = auth.uid() LIMIT 1));

COMMENT ON TABLE public.hoa_don_cong_ty IS
'Snapshot thông tin công ty cho payment_cycle (G5c 14/10/2026). Đổi công ty sau xuất → snapshot không đổi.';

-- ─── 4. Bảng hoa_don_cong_ty_lich_su ───────────────────────────────────────
-- Lịch sử sửa thông tin công ty sau khi đã xuất MISA.
CREATE TABLE IF NOT EXISTS public.hoa_don_cong_ty_lich_su (
    id                   uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    hoa_don_cong_ty_id   uuid        NOT NULL REFERENCES public.hoa_don_cong_ty (id) ON DELETE CASCADE,
    clinic_id            uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    cu_ten               text        NOT NULL DEFAULT '',
    cu_dia_chi           text        NOT NULL DEFAULT '',
    cu_ma_so_thue        text        NOT NULL DEFAULT '',
    cu_email             text        NOT NULL DEFAULT '',
    moi_ten              text        NOT NULL DEFAULT '',
    moi_dia_chi          text        NOT NULL DEFAULT '',
    moi_ma_so_thue       text        NOT NULL DEFAULT '',
    moi_email            text        NOT NULL DEFAULT '',
    sua_boi              uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc              timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.hoa_don_cong_ty_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_cong_ty_ls_clinic ON public.hoa_don_cong_ty_lich_su;
CREATE POLICY hoa_don_cong_ty_ls_clinic ON public.hoa_don_cong_ty_lich_su
    USING (clinic_id = (SELECT c.id FROM public.clinic c
           JOIN public.clinic_membership m ON m.clinic_id = c.id
           WHERE m.staff_id = auth.uid() LIMIT 1));

COMMENT ON TABLE public.hoa_don_cong_ty_lich_su IS
'Lịch sử thay đổi thông tin công ty trên hoá đơn sau khi xuất MISA (G5c 14/10/2026).';

-- ─── 5. Bảng hoa_don_misa_xuat ─────────────────────────────────────────────
-- Đánh dấu "đã xuất sang MISA" cho một kỳ (từ ngày → đến ngày) + ai xuất + bản chụp tổng.
CREATE TABLE IF NOT EXISTS public.hoa_don_misa_xuat (
    id          uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id   uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    tu_ngay     date        NOT NULL,
    den_ngay    date        NOT NULL,
    co_so       text,
    so_hoa_don  integer     NOT NULL DEFAULT 0,
    tong_tien   bigint      NOT NULL DEFAULT 0,
    xuat_boi    uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    xuat_luc    timestamptz NOT NULL DEFAULT now(),
    ghi_chu     text        NOT NULL DEFAULT '',
    -- Bản chụp tổng (JSON mảng hoá đơn nhỏ: stt, ma_phieu, tong, ten_cong_ty)
    ban_chup    jsonb       NOT NULL DEFAULT '[]'
);

ALTER TABLE public.hoa_don_misa_xuat ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_misa_clinic ON public.hoa_don_misa_xuat;
CREATE POLICY hoa_don_misa_clinic ON public.hoa_don_misa_xuat
    USING (clinic_id = (SELECT c.id FROM public.clinic c
           JOIN public.clinic_membership m ON m.clinic_id = c.id
           WHERE m.staff_id = auth.uid() LIMIT 1));

COMMENT ON TABLE public.hoa_don_misa_xuat IS
'Đánh dấu đã xuất sang MISA + bản chụp tổng kỳ (G5c 14/10/2026).';

-- ─── 6. Trigger notify ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.trg_notify_hoa_don_cong_ty()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('row_change',
        json_build_object('table','hoa_don_cong_ty','op',TG_OP,
            'clinic_id', COALESCE(NEW.clinic_id, OLD.clinic_id))::text);
    RETURN NULL;
END;$$;

DROP TRIGGER IF EXISTS trg_notify_hoa_don_cong_ty ON public.hoa_don_cong_ty;
CREATE TRIGGER trg_notify_hoa_don_cong_ty
    AFTER INSERT OR UPDATE OR DELETE ON public.hoa_don_cong_ty
    FOR EACH ROW EXECUTE FUNCTION public.trg_notify_hoa_don_cong_ty();
