-- Chỉ định dịch vụ THƯ KÝ NHẬP chờ BÁC SĨ DUYỆT.
--
-- LUẬT (Tuyền chốt 15/09/2026): bác sĩ đọc, thư ký y khoa nhập; màn bác sĩ
-- hiện song song theo thời gian thực; bác sĩ thấy ổn thì duyệt. Chưa duyệt thì
-- CHỈ bác sĩ và thư ký thấy — trưởng ca, phòng dịch vụ, thu ngân chưa được thấy
-- và chưa có việc gì để làm. CONTEXT v1.0: "bác sĩ duyệt chỉ định → điều phối".
--
-- VÌ SAO LÀ BẢNG RIÊNG, KHÔNG PHẢI MỘT TRẠNG THÁI MỚI TRÊN work_item.
-- Chỉ định đã duyệt LÀ work_item của phòng thực hiện (order_services), và có
-- nhiều nơi đọc work_item bằng `status <> 'CANCELLED'` (tính tiền, tuyến, bảng
-- phòng). Thêm trạng thái "chờ duyệt" nghĩa là mọi nơi đó phải nhớ loại nó ra;
-- sót một nơi là thu ngân thu tiền một dịch vụ bác sĩ chưa duyệt. Để nháp ở
-- đây thì không nơi nào cần biết nó tồn tại cho tới khi bác sĩ duyệt —
-- lúc đó mới gọi order_services như bác sĩ tự chỉ định.

CREATE TABLE IF NOT EXISTS public.service_order_draft (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id          uuid        NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id           uuid        NOT NULL REFERENCES public.visit(visit_id) ON DELETE RESTRICT,
    service_codes      text[]      NOT NULL DEFAULT '{}'::text[],
    recorded_by        uuid        NOT NULL REFERENCES public.staff(id),
    version            integer     NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    approved_at        timestamptz,
    approved_by        uuid        REFERENCES public.staff(id),
    discarded_at       timestamptz,
    discarded_by       uuid        REFERENCES public.staff(id),
    discard_reason     text,
    CONSTRAINT service_order_draft_ket_thuc_mot_kieu
        CHECK (approved_at IS NULL OR discarded_at IS NULL),
    CONSTRAINT service_order_draft_duyet_co_nguoi
        CHECK ((approved_at IS NULL) = (approved_by IS NULL)),
    CONSTRAINT service_order_draft_bo_co_nguoi
        CHECK ((discarded_at IS NULL) = (discarded_by IS NULL)),
    CONSTRAINT service_order_draft_duyet_phai_co_dich_vu
        CHECK (approved_at IS NULL OR cardinality(service_codes) > 0)
);

COMMENT ON TABLE public.service_order_draft IS
    'Chỉ định dịch vụ thư ký nhập, chờ bác sĩ duyệt. Duyệt → order_services tạo '
    'việc ở phòng thực hiện. Chưa duyệt chỉ DOCTOR/ULTRASOUND_DOCTOR/TKYK đọc '
    '(20260915000008).';

-- Một lượt khám chỉ có MỘT bản nháp đang mở: thư ký nhập thêm là gộp vào đó,
-- bác sĩ duyệt một lần là đủ, không có hai bản nháp tranh nhau.
CREATE UNIQUE INDEX IF NOT EXISTS uq_service_order_draft_mo
    ON public.service_order_draft (clinic_id, visit_id)
 WHERE approved_at IS NULL AND discarded_at IS NULL;

-- Bản nháp đã kết thúc (duyệt hoặc bỏ) là lịch sử: không sửa, không xoá.
CREATE OR REPLACE FUNCTION public.service_order_draft_khoa_sau_ket_thuc()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Không xoá bản nháp chỉ định — bỏ nháp bằng discarded_at'
            USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.approved_at IS NOT NULL OR OLD.discarded_at IS NOT NULL THEN
        RAISE EXCEPTION 'Bản nháp chỉ định đã duyệt hoặc đã bỏ — không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.version := OLD.version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_service_order_draft_khoa ON public.service_order_draft;
CREATE TRIGGER trg_service_order_draft_khoa
    BEFORE UPDATE OR DELETE ON public.service_order_draft
    FOR EACH ROW EXECUTE FUNCTION public.service_order_draft_khoa_sau_ket_thuc();

-- Màn bác sĩ và thư ký cập nhật theo thời gian thực. Payload chỉ {bảng,
-- phòng khám}; nội dung đọc lại qua API có kiểm vai.
DROP TRIGGER IF EXISTS trg_notify_service_order_draft ON public.service_order_draft;
CREATE TRIGGER trg_notify_service_order_draft
    AFTER INSERT OR UPDATE ON public.service_order_draft
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

ALTER TABLE public.service_order_draft ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_order_draft_select_bac_si_thu_ky
    ON public.service_order_draft;
CREATE POLICY service_order_draft_select_bac_si_thu_ky
    ON public.service_order_draft
    FOR SELECT TO authenticated
    USING (
        clinic_id IN (
            SELECT public.current_clinic_ids_for_roles(
                ARRAY['DOCTOR', 'ULTRASOUND_DOCTOR', 'TKYK']
            )
        )
    );

-- Quyền bảng như mọi bảng dữ liệu phòng khám: client CHỈ ĐỌC (và RLS ở trên
-- còn thu hẹp về bác sĩ/thư ký); ghi đi qua FastAPI.
GRANT SELECT ON public.service_order_draft TO authenticated;
GRANT ALL ON public.service_order_draft TO service_role;
