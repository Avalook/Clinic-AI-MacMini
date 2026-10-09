-- GHI CHÚ TỰ DO CỦA LƯỢT "KHÁC" (Tuyền chốt 07/10/2026 — bấm thử staging):
-- hồ sơ lượt "Khác" chỉ cần MỘT ô chữ to tự do (+ kê chỉ định như có sẵn).
--
-- Vì sao bảng mới, không tái dùng chỗ có sẵn:
--   * `consultation_note` (ô tư vấn, mỗi lần lưu một dòng) — dòng của phiên
--     PRIMARY được `mang_sang` / `bang` liệt kê HẾT theo thứ tự ghi (lối ghi chú
--     cũ): mỗi lần tự lưu thành một đoạn lặp ở mục "A" của phiếu khám.
--   * `appointment.notes` — ghi chú lúc ĐẶT, sửa đè, không lịch sử.
--   * `phieu_kham_luot` — gắn 7 mẫu phiếu khám JSON.
--
-- KHÔNG CÁI GÌ SAU ĐÈ CÁI TRƯỚC: mỗi lần lưu là MỘT DÒNG MỚI (`phien_ban` tăng
-- dần), màn hiện bản mới nhất; không UPDATE / DELETE (trigger chặn). Hai người
-- cùng lưu: UNIQUE (clinic_id, visit_id, phien_ban) — người sau nhận 409 rồi lưu
-- lại trên bản mới.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.luot_ghi_chu (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id    uuid NOT NULL,
    phien_ban   integer NOT NULL CHECK (phien_ban >= 1),
    noi_dung    text NOT NULL DEFAULT '' CHECK (length(noi_dung) <= 20000),
    ghi_boi     uuid NOT NULL REFERENCES public.staff (id),
    ghi_luc     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT luot_ghi_chu_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT luot_ghi_chu_mot_ban UNIQUE (clinic_id, visit_id, phien_ban)
);

COMMENT ON TABLE public.luot_ghi_chu IS
'Ô chữ tự do của hồ sơ lượt "Khác" (07/10/2026): mỗi lần lưu một phiên bản '
'mới, không sửa / xoá dòng cũ; màn và bản in đọc phiên bản lớn nhất.';

-- Chỉ thêm (cùng hàm của result_correction / form_instance_lich_su).
DROP TRIGGER IF EXISTS trg_luot_ghi_chu_chi_them ON public.luot_ghi_chu;
CREATE TRIGGER trg_luot_ghi_chu_chi_them
    BEFORE UPDATE OR DELETE ON public.luot_ghi_chu
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

ALTER TABLE public.luot_ghi_chu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS luot_ghi_chu_select_own_clinic ON public.luot_ghi_chu;
CREATE POLICY luot_ghi_chu_select_own_clinic ON public.luot_ghi_chu
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.luot_ghi_chu TO authenticated;
GRANT SELECT, INSERT ON public.luot_ghi_chu TO service_role;
