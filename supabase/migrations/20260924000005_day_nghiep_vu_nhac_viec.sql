-- NHÓM 5 — khối chỉnh dây + tự nhắc việc (Tuyền chốt 23–24/09/2026).
--
--   * "Đường nối H1–H8 phải CUSTOM được (không khoá cứng)". Chia dây: NGHIỆP VỤ
--     chỉnh được trên màn / LÕI khoá trong code. Dây nghiệp vụ của Hành trình:
--       h4_tu_xep_phong              bật/tắt tự xếp phòng sau khi thu tiền
--       h6_bao_cskh_khi_ve_con_viec  khách về mà còn việc dở → báo CSKH
--       h7_ket_qua_doi_tac_qua_han_ngay  mấy ngày thì báo "kết quả đối tác quá hạn"
--       h8_nhac_check_out_phut       trả tiền xong bao lâu chưa check-out → nhắc lễ tân
--     Không có dòng = mặc định trong code (services/day_noi_service.py).
--   * "Nhắc tái khám: theo hẹn của bác sĩ, HOẶC tự tạo việc cho chính mình để
--     tự nhắc" — bảng nhac_viec_ca_nhan, tới giờ hệ thống réo chuông cho người ấy.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.day_nghiep_vu (
    clinic_id uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    ma        text NOT NULL,
    gia_tri   jsonb NOT NULL,
    sua_boi   uuid REFERENCES public.staff (id),
    sua_luc   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, ma)
);

COMMENT ON TABLE public.day_nghiep_vu IS
'Dây nối nghiệp vụ quản lý chỉnh trên màn (bật/tắt, thời hạn). Không có dòng = mặc định trong code. Dây LÕI (dòng thời gian, trách nhiệm tiền) không nằm ở đây.';

ALTER TABLE public.day_nghiep_vu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS day_nghiep_vu_select_own_clinic ON public.day_nghiep_vu;
CREATE POLICY day_nghiep_vu_select_own_clinic ON public.day_nghiep_vu
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.day_nghiep_vu TO service_role;

CREATE TABLE IF NOT EXISTS public.nhac_viec_ca_nhan (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    staff_id          uuid NOT NULL REFERENCES public.staff (id),
    clinic_patient_id uuid,
    visit_id          uuid,
    noi_dung          text NOT NULL CHECK (length(btrim(noi_dung)) BETWEEN 1 AND 500),
    nhac_luc          timestamptz NOT NULL,
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    xong_luc          timestamptz
);

CREATE INDEX IF NOT EXISTS ix_nhac_viec_ca_nhan_nguoi
    ON public.nhac_viec_ca_nhan (clinic_id, staff_id, nhac_luc);

COMMENT ON TABLE public.nhac_viec_ca_nhan IS
'Việc một người tự hẹn nhắc chính mình (vd gọi lại khách về tái khám). Tới nhac_luc hệ thống réo chuông cho đúng người ấy.';

ALTER TABLE public.nhac_viec_ca_nhan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS nhac_viec_ca_nhan_select_own_clinic ON public.nhac_viec_ca_nhan;
CREATE POLICY nhac_viec_ca_nhan_select_own_clinic ON public.nhac_viec_ca_nhan
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.nhac_viec_ca_nhan TO service_role;

-- Quyền chỉnh dây nối — khối "Danh mục" (quản lý có sẵn), cấp thêm được.
INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES ('config.wiring.manage', 'Chỉnh dây nối nghiệp vụ (tư vấn, tự xếp phòng, chuông, vị trí)',
        'danh_muc', 'catalogue', 'operational', false)
ON CONFLICT (ma) DO NOTHING;

SELECT public.cap_quyen_cho_moi_thanh_vien();
