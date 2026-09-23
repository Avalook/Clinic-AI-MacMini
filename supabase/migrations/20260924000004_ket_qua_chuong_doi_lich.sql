-- NHÓM 3 — kết quả, chuông, lịch sử đổi lịch (Tuyền chốt 23–24/09/2026,
-- docs/BAN-DO-DAY-NOI-LEGO.md "Bản chốt 24/09").
--
--   * Duyệt kết quả KHÔNG bắt buộc: bác sĩ MỞ kết quả thì hệ thống TỰ ghi "đã xem
--     lúc…" (không phải bấm gì) — để biết kết quả nào chưa ai xem (H6).
--   * Tệp kết quả về → chuông cho bác sĩ, thư ký, điều dưỡng, CSKH — NGƯỜI NHẬN
--     CHỈNH ĐƯỢC (dây nghiệp vụ, bảng `day_nhan_thong_bao`).
--   * Đổi lịch phải LƯU LỊCH SỬ thay lịch để đối chiếu (từ giờ nào → giờ nào, ai
--     đổi, lý do).
--
-- Chạy lại được.

-- 1. "Đã xem" của tệp kết quả — lần xem ĐẦU TIÊN của người làm chuyên môn.
ALTER TABLE public.tep_ket_qua
    ADD COLUMN IF NOT EXISTS da_xem_luc timestamptz,
    ADD COLUMN IF NOT EXISTS da_xem_boi_staff_id uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.tep_ket_qua.da_xem_luc IS
'Lần ĐẦU bác sĩ / thư ký y khoa / bác sĩ siêu âm mở tệp này (tự ghi, không phải bấm). NULL = chưa ai chuyên môn xem.';

-- 2. Ai nhận chuông cho sự kiện nào — DÂY NGHIỆP VỤ, quản lý chỉnh trên màn.
CREATE TABLE IF NOT EXISTS public.day_nhan_thong_bao (
    clinic_id    uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    su_kien      text NOT NULL,
    -- Vai nhận (theo vai — ai đang đứng vai ấy cũng thấy).
    vai          text[] NOT NULL DEFAULT '{}',
    -- Bác sĩ chính của lượt nhận ĐÍCH DANH.
    bac_si_chinh boolean NOT NULL DEFAULT true,
    bat          boolean NOT NULL DEFAULT true,
    sua_boi      uuid REFERENCES public.staff (id),
    sua_luc      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, su_kien)
);

COMMENT ON TABLE public.day_nhan_thong_bao IS
'Dây nối chuông: sự kiện nào báo cho vai nào (+ bác sĩ chính đích danh). Không có dòng = mặc định trong code (events/consumers/chuong.py).';

ALTER TABLE public.day_nhan_thong_bao ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS day_nhan_thong_bao_select_own_clinic ON public.day_nhan_thong_bao;
CREATE POLICY day_nhan_thong_bao_select_own_clinic ON public.day_nhan_thong_bao
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.day_nhan_thong_bao TO service_role;

-- Mặc định Tuyền chốt: tệp kết quả → bác sĩ, thư ký, điều dưỡng, CSKH.
INSERT INTO public.day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh)
SELECT c.id, 'result_file.uploaded',
       ARRAY['CSKH', 'TKYK', 'NURSE_ULTRASOUND'], true
  FROM public.clinic c
ON CONFLICT (clinic_id, su_kien) DO NOTHING;
-- Phiếu kết quả hoàn tất ở phòng → bác sĩ chính "có kết quả mới" + thư ký.
INSERT INTO public.day_nhan_thong_bao (clinic_id, su_kien, vai, bac_si_chinh)
SELECT c.id, 'result.ready', ARRAY['TKYK'], true
  FROM public.clinic c
ON CONFLICT (clinic_id, su_kien) DO NOTHING;

-- 3. Lịch sử đổi lịch — mỗi lần đổi một dòng, không sửa không xoá.
CREATE TABLE IF NOT EXISTS public.appointment_doi_lich (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    appointment_id   uuid NOT NULL REFERENCES public.appointment (id) ON DELETE CASCADE,
    tu_bat_dau       timestamptz,
    tu_ket_thuc      timestamptz,
    den_bat_dau      timestamptz,
    den_ket_thuc     timestamptz,
    tu_bac_si_id     uuid,
    den_bac_si_id    uuid,
    ly_do            text,
    doi_boi_staff_id uuid REFERENCES public.staff (id),
    doi_luc          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_appointment_doi_lich_lich
    ON public.appointment_doi_lich (clinic_id, appointment_id, doi_luc);

COMMENT ON TABLE public.appointment_doi_lich IS
'Mỗi lần đổi giờ / đổi bác sĩ của một lịch hẹn: từ → đến, ai đổi, lý do (Tuyền 24/09/2026). Chỉ thêm.';

ALTER TABLE public.appointment_doi_lich ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS appointment_doi_lich_select_own_clinic ON public.appointment_doi_lich;
CREATE POLICY appointment_doi_lich_select_own_clinic ON public.appointment_doi_lich
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.appointment_doi_lich TO service_role;
