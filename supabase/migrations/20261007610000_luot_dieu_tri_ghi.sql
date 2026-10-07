-- KHỐI 4 "ĐIỀU TRỊ" của hồ sơ khám (Tuyền chốt 07/10/2026 — T6 của
-- docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md): hai ô chữ tự do "Cảm nhận" và "Vấn
-- đề sau điều trị", theo LƯỢT, không nhét vào 7 mẫu phiếu JSON.
--
-- KHÔNG CÁI GÌ SAU ĐÈ CÁI TRƯỚC: mỗi lần tự lưu là MỘT DÒNG MỚI (`phien_ban`
-- tăng dần), màn hiện bản mới nhất; không UPDATE, không DELETE (trigger chặn).
-- Dùng được cho cả lượt không có phiếu (Điều trị, Khác).
--
-- Hai người cùng lưu một lúc: UNIQUE (clinic_id, visit_id, phien_ban) — người
-- sau nhận 409 rồi lưu lại trên bản mới (chống đè bằng `phien_ban` mong đợi).

CREATE TABLE IF NOT EXISTS public.luot_dieu_tri_ghi (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id    uuid NOT NULL,
    phien_ban   integer NOT NULL CHECK (phien_ban >= 1),
    cam_nhan    text NOT NULL DEFAULT '' CHECK (length(cam_nhan) <= 5000),
    van_de_sau  text NOT NULL DEFAULT '' CHECK (length(van_de_sau) <= 5000),
    ghi_boi     uuid NOT NULL REFERENCES public.staff (id),
    ghi_luc     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT luot_dieu_tri_ghi_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT luot_dieu_tri_ghi_mot_ban UNIQUE (clinic_id, visit_id, phien_ban)
);

COMMENT ON TABLE public.luot_dieu_tri_ghi IS
'Khối 4 "Điều trị" của hồ sơ khám theo lượt (07/10/2026): mỗi lần lưu một '
'phiên bản mới, không sửa / xoá dòng cũ; màn hiện phiên bản lớn nhất.';

CREATE OR REPLACE FUNCTION public.luot_dieu_tri_ghi_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'luot_dieu_tri_ghi: chỉ thêm phiên bản mới, không sửa / xoá'
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_luot_dieu_tri_ghi_chi_them ON public.luot_dieu_tri_ghi;
CREATE TRIGGER trg_luot_dieu_tri_ghi_chi_them
    BEFORE UPDATE OR DELETE ON public.luot_dieu_tri_ghi
    FOR EACH ROW EXECUTE FUNCTION public.luot_dieu_tri_ghi_chi_them();

-- Hai màn cùng mở một lượt (bác sĩ + thư ký) thấy bản mới ngay.
DROP TRIGGER IF EXISTS trg_notify_luot_dieu_tri_ghi ON public.luot_dieu_tri_ghi;
CREATE TRIGGER trg_notify_luot_dieu_tri_ghi
    AFTER INSERT ON public.luot_dieu_tri_ghi
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

ALTER TABLE public.luot_dieu_tri_ghi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS luot_dieu_tri_ghi_select_own_clinic ON public.luot_dieu_tri_ghi;
CREATE POLICY luot_dieu_tri_ghi_select_own_clinic ON public.luot_dieu_tri_ghi
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.luot_dieu_tri_ghi TO service_role;
