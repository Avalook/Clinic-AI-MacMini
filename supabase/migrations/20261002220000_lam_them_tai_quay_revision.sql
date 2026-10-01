-- Tombstone tăng đơn điệu cho nút làm thêm: chặn lệnh cũ sau chuỗi thêm → bỏ
-- khi trạng thái nhìn bề ngoài lại trở về “chưa có” (ABA).
CREATE TABLE IF NOT EXISTS public.lam_them_tai_quay_revision (
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id     uuid NOT NULL,
    service_code text NOT NULL,
    revision     integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, visit_id, service_code),
    CONSTRAINT lam_them_revision_visit_fk
        FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit(clinic_id, visit_id) ON DELETE CASCADE
);

ALTER TABLE public.lam_them_tai_quay_revision ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.lam_them_tai_quay_revision FROM anon, authenticated;
GRANT ALL ON public.lam_them_tai_quay_revision TO service_role;
