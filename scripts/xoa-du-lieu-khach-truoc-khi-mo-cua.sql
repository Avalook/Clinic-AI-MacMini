-- XOÁ SẠCH dữ liệu khách và lượt khám — CHỈ dùng TRƯỚC KHI phòng khám mở cửa.
--
-- ⚠️ ĐÂY LÀ NGOẠI LỆ CÓ CHỦ Ý, KHÔNG PHẢI CÁCH LÀM THƯỜNG NGÀY.
--
-- `patient`, `appointment`, `visit` có ba chốt `*_no_delete` ở Postgres, và
-- chúng tồn tại vì một lý do đúng: hồ sơ bệnh án không được biến mất. Ngày
-- thường muốn bỏ một lịch hẹn thì HUỶ nó (đổi trạng thái), muốn bỏ một hồ sơ
-- thì TẮT nó (`is_active = false`) — dấu vết ở lại.
--
-- Tệp này tắt ba chốt ấy trong đúng một giao dịch, và chỉ được chạy khi:
--
--   1. Phòng khám CHƯA đón bệnh nhân thật lần nào, và
--   2. Mọi dòng đang có đều là dữ liệu chạy thử, và
--   3. Người chạy CỐ Ý muốn một hệ thống trắng để bàn giao.
--
-- Sau ngày mở cửa, chạy tệp này là xoá bệnh án thật. Nó có chốt tự dừng ở dưới
-- để chuyện đó không xảy ra vì một lần gõ nhầm.
--
--   docker exec -i clinicai_db psql -U postgres < scripts/xoa-du-lieu-khach-truoc-khi-mo-cua.sql
--
-- Thứ KHÔNG bị xoá: nhân sự, tài khoản đăng nhập, phòng/tầng, danh mục dịch vụ,
-- danh mục thuốc, lịch trực. Chỉ khách và mọi thứ dính vào khách.

BEGIN;

-- ── Chốt tự dừng ────────────────────────────────────────────────────────────
DO $$
DECLARE
    so_ky integer;
BEGIN
    -- Một lượt khám đã KÝ nghĩa là có bác sĩ đặt tên mình vào đó. Hệ thống chưa
    -- mở cửa thì không thể có dòng nào như vậy.
    SELECT count(*) INTO so_ky FROM public.visit
     WHERE status IN ('FINALIZED', 'AMENDED');
    IF so_ky > 0 THEN
        RAISE EXCEPTION
            'DỪNG: có % lượt khám đã ký. Hệ thống này đã đón bệnh nhân thật — '
            'không được xoá. Muốn dọn thì huỷ/tắt từng bản ghi.', so_ky;
    END IF;
END $$;

-- SÁU bảng dùng chung chốt `prevent_hard_delete`, không phải ba. Bản đầu của
-- tệp này chỉ tắt ba cái tên trong tài liệu (patient/appointment/visit) rồi
-- chết giữa chừng ở `payment` — may mà chết, vì nếu nó im lặng bỏ qua thì hệ
-- còn lại một khoản thu mồ côi trỏ tới lượt khám đã biến mất.
ALTER TABLE public.patient         DISABLE TRIGGER trg_patient_no_delete;
ALTER TABLE public.appointment     DISABLE TRIGGER trg_appointment_no_delete;
ALTER TABLE public.visit           DISABLE TRIGGER trg_visit_no_delete;
ALTER TABLE public.clinical_record DISABLE TRIGGER trg_clinical_record_no_delete;
ALTER TABLE public.lab_result      DISABLE TRIGGER trg_lab_result_no_delete;
ALTER TABLE public.payment         DISABLE TRIGGER trg_payment_no_delete;
ALTER TABLE public.vital_measurement
    DISABLE TRIGGER trg_vital_measurement_chi_them;
ALTER TABLE public.visit_amendment
    DISABLE TRIGGER trg_visit_amendment_append_only;
ALTER TABLE public.service_order_draft
    DISABLE TRIGGER trg_service_order_draft_khoa;

-- HAI SỔ Ở LẠI, CÓ CHỦ Ý: `inventory_txn` (kho) và `event_log` (ai làm gì).
-- Chúng ghi VIỆC ĐÃ XẢY RA chứ không phải hồ sơ của khách; xoá chúng là làm số
-- tồn và lịch sử thao tác không còn giải thích được. Tuyền yêu cầu dọn "dữ liệu
-- khách và lượt khám" — hai sổ này không thuộc nhóm đó.

-- Xoá từ NGOÀI vào TRONG: thứ phụ thuộc trước, thứ được phụ thuộc sau. Sai thứ
-- tự thì vướng khoá ngoại và cả giao dịch quay đầu.
-- SỔ KHO Ở LẠI, KHÔNG XOÁ.
--
-- `inventory_txn` có chốt chỉ-ghi-thêm của riêng nó, và chốt ấy ĐÚNG: những lần
-- nhập và xuất thuốc đã thực sự xảy ra, kể cả khi chúng sinh ra từ một lượt
-- khám thử. Xoá sổ kho là làm số tồn hiện tại không giải thích được bằng lịch
-- sử — đúng cái bệnh mà sổ sinh ra để chữa. Sổ trỏ tới đơn thuốc bằng cặp
-- (ref_type, ref_id) chứ không phải khoá ngoại, nên đơn xoá đi thì sổ vẫn còn.
DELETE FROM public.prescription;
DELETE FROM public.payment;
DELETE FROM public.lab_result;
DELETE FROM public.ultrasound_record;
DELETE FROM public.clinical_form_response;
DELETE FROM public.clinical_record;
DELETE FROM public.visit_amendment;
DELETE FROM public.vital_measurement;
DELETE FROM public.queue_entry;
DELETE FROM public.service_order_draft;
DELETE FROM public.service_order;
DELETE FROM public.consultation_note;
DELETE FROM public.consultation;
DELETE FROM public.review_round;
DELETE FROM public.work_item_dependency;
DELETE FROM public.work_item;
DELETE FROM public.encounter_flow;
DELETE FROM public.service_log;
DELETE FROM public.cskh_action;
-- VÒNG KHOÁ NGOẠI: `appointment.episode_id → care_episode` và
-- `care_episode.opened_appointment_id → appointment` trỏ vào nhau. Không có
-- thứ tự xoá nào gỡ được cả hai, nên phải cắt một sợi trước.
UPDATE public.appointment SET episode_id = NULL WHERE episode_id IS NOT NULL;
DELETE FROM public.care_episode;
DELETE FROM public.visit;
DELETE FROM public.appointment;
DELETE FROM public.patient;

ALTER TABLE public.patient         ENABLE TRIGGER trg_patient_no_delete;
ALTER TABLE public.appointment     ENABLE TRIGGER trg_appointment_no_delete;
ALTER TABLE public.visit           ENABLE TRIGGER trg_visit_no_delete;
ALTER TABLE public.clinical_record ENABLE TRIGGER trg_clinical_record_no_delete;
ALTER TABLE public.lab_result      ENABLE TRIGGER trg_lab_result_no_delete;
ALTER TABLE public.payment         ENABLE TRIGGER trg_payment_no_delete;
ALTER TABLE public.vital_measurement
    ENABLE TRIGGER trg_vital_measurement_chi_them;
ALTER TABLE public.visit_amendment
    ENABLE TRIGGER trg_visit_amendment_append_only;
ALTER TABLE public.service_order_draft
    ENABLE TRIGGER trg_service_order_draft_khoa;

SELECT (SELECT count(*) FROM public.patient)     AS con_khach,
       (SELECT count(*) FROM public.appointment) AS con_lich,
       (SELECT count(*) FROM public.visit)       AS con_luot,
       (SELECT count(*) FROM public.staff)       AS nhan_su_giu_nguyen;

COMMIT;
