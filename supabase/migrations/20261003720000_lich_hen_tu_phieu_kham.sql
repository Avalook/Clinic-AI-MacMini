-- Bác sĩ đặt LỊCH HẸN THẬT ngay ở ô "Ngày tái khám" của phiếu (Tuyền 02/10/2026).
--
-- Trước đây ô ngày chỉ sinh một việc gọi cho CSKH (nhac_tai_kham) — không có
-- giờ nên không lên lịch hẹn. Nay dưới ô ngày có khung chọn bác sĩ + giờ (hoặc
-- "Chưa phân bác sĩ"), bấm là ra một dòng `appointment` thật.
--
-- `hen_tu_visit_id` = lượt khám mà bác sĩ đặt lịch này từ phiếu của nó. Hai
-- việc cần nó:
--   1. Màn phiếu tìm lại ĐÚNG lịch mình đã đặt (hiện, huỷ để đặt lại).
--   2. Việc gọi của CSKH sinh từ CHÍNH lượt ấy KHÔNG tự đóng "đã có lịch": Tuyền
--      chốt việc gọi vẫn đúng chuẩn — CSKH vẫn gọi chốt giờ / phân bác sĩ. Lịch
--      khách tự đặt (hoặc CSKH đặt) thì vẫn đóng việc như cũ.

ALTER TABLE public.appointment
    ADD COLUMN IF NOT EXISTS hen_tu_visit_id uuid
        REFERENCES public.visit (visit_id) ON DELETE SET NULL;

COMMENT ON COLUMN public.appointment.hen_tu_visit_id IS
    'Lượt khám mà bác sĩ đặt lịch tái khám này từ phiếu (02/10/2026). NULL = '
    'lịch đặt ở màn Đặt lịch / CSKH như thường.';

-- Một lượt khám = MỘT lịch tái khám còn sống (ép ở Postgres, không khoá trong
-- Python — SO-LUAT Phần 6): bấm đúp hay hai tab cùng đặt thì cái thứ hai bị từ
-- chối. Muốn đổi giờ: huỷ lịch cũ trên phiếu rồi đặt lại (hoàn tác được).
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointment_mot_lich_song_tu_luot
    ON public.appointment (clinic_id, hen_tu_visit_id)
    WHERE hen_tu_visit_id IS NOT NULL
      AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED', 'CHECKED_IN');

CREATE INDEX IF NOT EXISTS idx_appointment_hen_tu_visit
    ON public.appointment (clinic_id, hen_tu_visit_id)
    WHERE hen_tu_visit_id IS NOT NULL;

-- Bản đầy đủ của 20260929950000, chỉ thêm MỘT điều kiện: không đóng việc gọi
-- của chính lượt đã đặt lịch này.
CREATE OR REPLACE FUNCTION public.nhac_tai_kham_dong_khi_co_lich()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF NEW.status NOT IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED', 'CHECKED_IN') THEN
        RETURN NEW;
    END IF;
    WITH dong AS (
    UPDATE public.nhac_tai_kham n
       SET trang_thai = 'KHONG_CAN',
           dong_vi = 'DA_CO_LICH',
           ghi_chu = 'Khách đã có lịch hẹn',
           appointment_id = NEW.id,
           dong_luc = now(),
           updated_at = now()
     WHERE n.clinic_id = NEW.clinic_id
       AND n.clinic_patient_id = NEW.clinic_patient_id
       AND n.nguon = 'PHIEU_KHAM'
       AND n.luot_goi = 1
       AND n.trang_thai = 'CHO_GOI'
       AND (NEW.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= n.han_goi
       -- Lịch bác sĩ đặt từ phiếu của chính lượt này: việc gọi giữ nguyên.
       AND n.nguon_visit_id IS DISTINCT FROM NEW.hen_tu_visit_id
    RETURNING n.id
    )
    UPDATE public.hen_gio h
       SET trang_thai = 'BO_QUA', lam_luc = now(), ket_qua = 'da_co_lich'
      FROM dong
     WHERE h.loai = 'nhac_tai_kham.den_han' AND h.ve_cai_gi = dong.id
       AND h.trang_thai = 'CHO';
    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.nhac_tai_kham_dong_khi_co_lich() IS
    'Lịch hẹn còn sống rơi từ hạn gọi trở đi → việc mời tái khám (từ phiếu) tự '
    'đóng "đã có lịch" (29/09/2026) — trừ lịch bác sĩ đặt từ phiếu của chính '
    'lượt ấy (02/10/2026).';
