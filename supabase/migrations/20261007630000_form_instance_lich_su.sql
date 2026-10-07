-- LỊCH SỬ SỬA MỌI PHIẾU KẾT QUẢ — không cái gì sau đè cái trước (Tuyền chốt
-- 07/10/2026). Áp cho MỌI `form_instance` (phiếu kết quả phòng, phiếu điều trị ở
-- bàn khám…), không đổi code màn nào.
--
-- `form_instance` giữ BẢN HIỆN TẠI: tự lưu ghi đè `du_lieu` mỗi 1,5 giây, và bàn
-- khám / phòng cùng ghi một phiếu (phiếu điều trị). Lần sửa SAU khi đã Hoàn tất
-- đã có ảnh chụp ở `result_correction` + `visit_amendment`; còn nháp (trước Hoàn
-- tất) thì bản trước mất hẳn. Nay: trigger BEFORE UPDATE chụp bản CŨ vào bảng
-- chỉ-thêm `form_instance_lich_su` mỗi khi `du_lieu` hoặc `trang_thai` đổi.
--
-- Ghi bằng TRIGGER (không ở Python): đường ghi nào vào phiếu cũng để lại vết,
-- kể cả đường thêm sau này. Không gộp như `phieu_kham_lich_su`: mỗi bản cũ là
-- một dòng, đọc lại được nguyên văn. `sua_boi` = người gây ra lần đổi (người
-- bấm Hoàn tất nếu lần ấy là Hoàn tất, không thì người gõ).
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.form_instance_lich_su (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    form_instance_id uuid NOT NULL,
    service_order_id uuid NOT NULL,
    form_id          text NOT NULL,
    -- Bản CŨ (trước lần đổi này).
    revision         integer NOT NULL,
    du_lieu          jsonb NOT NULL,
    trang_thai       text NOT NULL,
    sua_boi          uuid REFERENCES public.staff (id),
    sua_luc          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT form_instance_lich_su_phieu_fk FOREIGN KEY (clinic_id, form_instance_id)
        REFERENCES public.form_instance (clinic_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_form_instance_lich_su_phieu
    ON public.form_instance_lich_su (clinic_id, form_instance_id, sua_luc DESC);
CREATE INDEX IF NOT EXISTS ix_form_instance_lich_su_chi_dinh
    ON public.form_instance_lich_su (clinic_id, service_order_id);

COMMENT ON TABLE public.form_instance_lich_su IS
'Bản cũ của phiếu kết quả mỗi lần du_lieu / trang_thai đổi (07/10/2026). Trigger ghi; chỉ thêm.';

CREATE OR REPLACE FUNCTION public.ghi_lich_su_form_instance()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.du_lieu IS DISTINCT FROM OLD.du_lieu
       OR NEW.trang_thai IS DISTINCT FROM OLD.trang_thai THEN
        INSERT INTO public.form_instance_lich_su
            (clinic_id, form_instance_id, service_order_id, form_id, revision,
             du_lieu, trang_thai, sua_boi)
        VALUES
            (OLD.clinic_id, OLD.id, OLD.service_order_id, OLD.form_id, OLD.revision,
             OLD.du_lieu, OLD.trang_thai,
             CASE WHEN NEW.hoan_tat_luc IS DISTINCT FROM OLD.hoan_tat_luc
                  THEN NEW.hoan_tat_boi ELSE NEW.nhap_boi END);
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_form_instance_lich_su ON public.form_instance;
CREATE TRIGGER trg_form_instance_lich_su
    BEFORE UPDATE ON public.form_instance
    FOR EACH ROW EXECUTE FUNCTION public.ghi_lich_su_form_instance();

-- Chỉ thêm, không sửa, không xoá (cùng nếp result_correction).
DROP TRIGGER IF EXISTS trg_form_instance_lich_su_chi_them ON public.form_instance_lich_su;
CREATE TRIGGER trg_form_instance_lich_su_chi_them
    BEFORE UPDATE OR DELETE ON public.form_instance_lich_su
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

ALTER TABLE public.form_instance_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS form_instance_lich_su_select_own_clinic
    ON public.form_instance_lich_su;
CREATE POLICY form_instance_lich_su_select_own_clinic ON public.form_instance_lich_su
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.form_instance_lich_su TO authenticated;
GRANT SELECT, INSERT ON public.form_instance_lich_su TO service_role;
