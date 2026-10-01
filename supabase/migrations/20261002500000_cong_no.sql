-- CÔNG NỢ KHI CHECK-OUT (Tuyền chốt 01/10/2026, sau sự cố 30/09: khách về mà
-- dịch vụ đã làm chưa thu, check-out không thấy nợ).
--
-- Check-out (và "về giữa chừng") khi khách còn khoản CHƯA THU → máy chủ CHẶN.
-- Hai đường qua: thu ngay ở quầy, hoặc "Ghi nợ" kèm lý do — một dòng ở bảng
-- này. Thu nợ sau ở quầy (đường thu có sẵn) → bên nhận sự kiện `cong_no` đổi
-- dòng sang DA_THU khi lượt hết nợ.
--
-- Bảng CỦA khối Công nợ (`modules.py`, ma="cong_no"). Check-out chỉ ĐỌC.
--
-- Một lượt có TỐI ĐA MỘT dòng CHƯA_THU (hai người bấm cùng lúc: một người thua
-- ở chỉ mục). Ghi nợ lại khi khoản nợ đổi = cập nhật chính dòng ấy (số tiền,
-- các dòng, lý do, người ghi) — sự kiện `cong_no.ghi` giữ dấu từng lần.
-- Không xoá; huỷ (HUY) phải có người, lúc, lý do. DA_THU/HUY là trạng thái cuối.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.cong_no (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id          uuid NOT NULL,
    clinic_patient_id uuid NOT NULL
                           REFERENCES public.patient (clinic_patient_id)
                           ON DELETE RESTRICT,
    so_tien           numeric(12, 0) NOT NULL CHECK (so_tien >= 0),
    -- Ảnh chụp các khoản nợ lúc ghi: [{loai, source_type, source_id, ten,
    -- so_tien}]. Check-out so nợ HIỆN TẠI với tập này để biết đã phủ đủ chưa.
    dong              jsonb NOT NULL DEFAULT '[]'::jsonb
                           CHECK (jsonb_typeof(dong) = 'array'),
    ly_do             text NOT NULL CHECK (length(btrim(ly_do)) BETWEEN 3 AND 500),
    ghi_boi           uuid NOT NULL REFERENCES public.staff (id),
    ghi_luc           timestamptz NOT NULL DEFAULT now(),
    trang_thai        text NOT NULL DEFAULT 'CHUA_THU'
                           CHECK (trang_thai IN ('CHUA_THU', 'DA_THU', 'HUY')),
    thu_luc           timestamptz,
    huy_luc           timestamptz,
    huy_boi           uuid REFERENCES public.staff (id),
    ly_do_huy         text,
    CONSTRAINT cong_no_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    -- Mỗi trạng thái mang đúng dấu vết của nó.
    CONSTRAINT cong_no_trang_thai_co_dau_vet CHECK (
        (trang_thai = 'CHUA_THU' AND thu_luc IS NULL AND huy_luc IS NULL
             AND huy_boi IS NULL AND ly_do_huy IS NULL)
        OR (trang_thai = 'DA_THU' AND thu_luc IS NOT NULL AND huy_luc IS NULL)
        OR (trang_thai = 'HUY' AND huy_luc IS NOT NULL AND huy_boi IS NOT NULL
            AND length(btrim(coalesce(ly_do_huy, ''))) BETWEEN 3 AND 500))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cong_no_luot_chua_thu
    ON public.cong_no (clinic_id, visit_id)
    WHERE trang_thai = 'CHUA_THU';
CREATE INDEX IF NOT EXISTS ix_cong_no_chua_thu
    ON public.cong_no (clinic_id, ghi_luc DESC)
    WHERE trang_thai = 'CHUA_THU';
CREATE INDEX IF NOT EXISTS ix_cong_no_khach
    ON public.cong_no (clinic_id, clinic_patient_id, ghi_luc DESC);

COMMENT ON TABLE public.cong_no IS
'Khoản khách còn nợ lúc check-out, lễ tân ghi kèm lý do (01/10/2026). '
'CHUA_THU → DA_THU (lượt hết nợ sau khi thu ở quầy) hoặc HUY (có lý do).';

-- Không xoá; dòng đã DA_THU/HUY không đổi nữa; dòng CHƯA_THU chỉ được ghi lại
-- (cùng lượt, cùng khách) hoặc chuyển sang DA_THU/HUY.
CREATE OR REPLACE FUNCTION public.cong_no_chi_chuyen_tiep()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'cong_no: không xoá — huỷ kèm lý do'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.trang_thai <> 'CHUA_THU'
       OR (NEW.clinic_id, NEW.visit_id, NEW.clinic_patient_id)
          IS DISTINCT FROM (OLD.clinic_id, OLD.visit_id, OLD.clinic_patient_id) THEN
        RAISE EXCEPTION 'cong_no: chỉ sửa được khoản nợ đang CHƯA THU của chính lượt ấy'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_cong_no_chi_chuyen_tiep ON public.cong_no;
CREATE TRIGGER trg_cong_no_chi_chuyen_tiep
    BEFORE UPDATE OR DELETE ON public.cong_no
    FOR EACH ROW EXECUTE FUNCTION public.cong_no_chi_chuyen_tiep();

-- Tin thay đổi cho màn đang mở (SSE: LISTEN/NOTIFY → /api/events/stream).
DROP TRIGGER IF EXISTS trg_notify_cong_no ON public.cong_no;
CREATE TRIGGER trg_notify_cong_no
    AFTER INSERT OR UPDATE OR DELETE ON public.cong_no
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

ALTER TABLE public.cong_no ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cong_no_select_own_clinic ON public.cong_no;
CREATE POLICY cong_no_select_own_clinic ON public.cong_no
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.cong_no TO service_role;
