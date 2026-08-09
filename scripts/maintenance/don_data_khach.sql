-- =====================================================================
-- don_data_khach.sql — DỌN DỮ LIỆU KHÁCH, GIỮ NGUYÊN MỌI THỨ CỦA PHÒNG KHÁM
-- =====================================================================
-- Quang, 09/08/2026: *"riêng cái gì của phòng khám đừng xoá, chỉ khách thôi"*.
--
-- KHÁC `reset_clinical_data.sql` Ở MỘT ĐIỂM SỐNG CÒN: file kia dọn luôn
-- `work_roster`. Chạy nó là mất sạch lịch trực vừa dựng. Đừng dùng file kia cho
-- việc này.
--
-- 🗑️ ĐI: patient và toàn bộ thứ treo dưới nó — lịch hẹn, lượt khám, bệnh án,
--        đơn thuốc, thanh toán, siêu âm, xét nghiệm, sổ chăm sóc, nhắc tái
--        khám, việc CSKH.
--
-- ✅ GIỮ: clinic, clinic_location, service_type, staff, clinic_membership,
--         tài khoản đăng nhập (auth.users), work_roster, roster_week,
--         vai_duoc_vao_tram, luat_cskh, work_session, và `event_log`.
--
--         event_log là NHẬT KÝ VẬN HÀNH của phòng khám, không phải hồ sơ khách:
--         nó ghi "ai làm gì lúc mấy giờ". Bỏ nhật ký khi dọn dữ liệu thử là bỏ
--         luôn khả năng truy lại chính lần dọn này.
--
-- CÁCH CHẠY (sao lưu TRƯỚC — một transaction, lỗi thì quay về, nhưng chạy đúng
-- thì không có đường lùi):
--
--   ssh clinic-vps 'docker exec -i clinicai_db pg_dump -U postgres -d postgres \
--     --no-owner > ~/prod_truoc_khi_don_20260809.sql'
--
--   ssh clinic-vps 'docker exec -i clinicai_db psql -U postgres -d postgres \
--     -v ON_ERROR_STOP=1' < scripts/maintenance/don_data_khach.sql
-- =====================================================================

BEGIN;

\echo '--- TRƯỚC ---'
SELECT 'patient' AS bang, count(*) FROM public.patient
UNION ALL SELECT 'appointment', count(*) FROM public.appointment
UNION ALL SELECT 'visit', count(*) FROM public.visit
UNION ALL SELECT 'work_roster (GIỮ)', count(*) FROM public.work_roster
UNION ALL SELECT 'staff (GIỮ)', count(*) FROM public.staff;

-- ── MỞ CHỐT APPEND-ONLY ──────────────────────────────────────────────────
--
-- `patient`, `appointment`, `visit`, `clinical_record`, `lab_result` được CỐ Ý
-- đặt append-only (trigger prevent_hard_delete, baseline 20260714000001):
-- *"row id kept for audit"*. Không mở thì lệnh dừng ngay ở bảng đầu tiên.
--
-- ĐÂY LÀ MỘT LẦN VƯỢT RÀO CÓ CHỦ Ý, không phải một dòng dọn dẹp vô hại. Nó
-- chấp nhận được vì phòng khám CHƯA chạy thật: bốn hồ sơ trên prod đều do chính
-- chúng ta tạo khi thử máy (07–09/08). Sau ngày khách nhập thật thì KHÔNG được
-- chạy file này nữa — mất bệnh án là mất vĩnh viễn, và cái chốt này có mặt đúng
-- để chặn chuyện đó.
--
-- Mở theo TÊN từng trigger: `DISABLE TRIGGER USER` tắt luôn mọi trigger nghiệp
-- vụ khác, còn `session_replication_role = replica` tắt cả kiểm khoá ngoại. DDL
-- trong Postgres nằm trong transaction, nên lỗi giữa chừng là mọi thứ — kể cả
-- mấy dòng này — quay về như cũ.
DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT * FROM (VALUES
        ('patient','trg_patient_no_delete'),
        ('appointment','trg_appointment_no_delete'),
        ('visit','trg_visit_no_delete'),
        ('clinical_record','trg_clinical_record_no_delete'),
        ('lab_result','trg_lab_result_no_delete')
    ) AS v(bang, trg)
    LOOP
        IF to_regclass('public.' || t.bang) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER %I', t.bang, t.trg);
        END IF;
    END LOOP;
END $$;

-- ── ĐI TỪ LÁ LÊN GỐC ─────────────────────────────────────────────────────
--
-- SCHEMA HAI MÔI TRƯỜNG KHÔNG GIỐNG NHAU: staging còn thiếu `tuong_tac_cskh`
-- (migration mới hơn). Nên đi qua `to_regclass` và bỏ qua bảng chưa có, thay vì
-- dừng giữa chừng ở một bảng không liên quan tới việc dọn.
--
-- THỨ TỰ TRONG MẢNG LÀ THỨ TỰ ĐI. Phần lớn khoá ngoại là RESTRICT/NO ACTION nên
-- đụng `patient` trước là báo lỗi, không phải đi dây chuyền. Đổi thứ tự là hỏng.
-- MỘT RÀNG BUỘC `NOT VALID` MÀ DÒNG CŨ ĐANG VI PHẠM SẴN.
--
-- `appointment_huy_phai_co_ly_do` (lịch CANCELLED phải có `ly_do_huy_ma`) được
-- thêm dạng NOT VALID, nên các dòng huỷ từ 07/08 — huỷ bằng chữ tự do "hủy",
-- chưa có mã — được cho qua. Nhưng ĐỘNG vào một dòng như thế là Postgres kiểm
-- lại cả dòng, và lệnh cắt vòng phụ thuộc ngay dưới đây bị chặn.
--
-- Gỡ rồi gắn lại ĐÚNG dạng NOT VALID: kết thúc transaction, ràng buộc trở lại
-- y hệt trạng thái hiện giờ. Gắn lại dạng VALID mới là đổi lược đồ — và sẽ nổ,
-- vì đúng những dòng ấy vẫn vi phạm.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname = 'appointment_huy_phai_co_ly_do') THEN
        ALTER TABLE public.appointment
            DROP CONSTRAINT appointment_huy_phai_co_ly_do;
    END IF;
END $$;

DO $$
DECLARE
    bang text;
    n    bigint;
BEGIN
    -- Vòng phụ thuộc: care_episode → appointment và appointment → care_episode.
    -- Cắt một chiều trước, nếu không cả hai bảng đều tắc.
    IF to_regclass('public.appointment') IS NOT NULL THEN
        UPDATE public.appointment SET episode_id = NULL WHERE episode_id IS NOT NULL;
    END IF;

    FOREACH bang IN ARRAY ARRAY[
        'clinical_form_response', 'visit_amendment', 'clinical_record',
        'prescription', 'payment', 'ultrasound_record',
        'lab_result', 'nhac_tai_kham', 'work_item', 'follow_up_case',
        -- SỔ CHĂM SÓC PHẢI ĐI TRƯỚC `appointment`, KHÔNG PHẢI SAU.
        --
        -- `tuong_tac_cskh.appointment_id` là ON DELETE SET NULL, mà bảng ấy có
        -- CHECK `tuong_tac_can_lich_hen`: CHECK_IN/CHECK_OUT bắt buộc gắn một
        -- lịch hẹn. Nên bỏ `appointment` trước là Postgres tự set null rồi tự
        -- vi phạm chính ràng buộc của nó — một thứ chỉ lộ ra khi chạy thật, vì
        -- staging chưa có bảng này.
        'tuong_tac_cskh', 'hen_goi_lai', 'cskh_action', 'cskh_log', 'service_log',
        'visit', 'care_episode', 'appointment',
        'patient_contact_channel', 'patient_medical_profile',
        'patient_next_of_kin', 'pregnancy', 'mpi_merge_queue',
        'patient'
    ]
    LOOP
        IF to_regclass('public.' || bang) IS NULL THEN
            RAISE NOTICE 'bo qua % (khong co o database nay)', bang;
            CONTINUE;
        END IF;
        EXECUTE format('DELETE FROM public.%I', bang);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '% : % dong', rpad(bang, 24), n;
    END LOOP;
END $$;

-- Gắn lại ràng buộc vừa gỡ, ĐÚNG dạng NOT VALID như trước.
ALTER TABLE public.appointment
    ADD CONSTRAINT appointment_huy_phai_co_ly_do
    CHECK (status <> 'CANCELLED' OR ly_do_huy_ma IS NOT NULL) NOT VALID;

-- ── ĐÓNG CHỐT LẠI ────────────────────────────────────────────────────────
-- Bỏ quên chỗ này là phòng khám chạy thật với một bảng bệnh án xoá được.
DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT * FROM (VALUES
        ('patient','trg_patient_no_delete'),
        ('appointment','trg_appointment_no_delete'),
        ('visit','trg_visit_no_delete'),
        ('clinical_record','trg_clinical_record_no_delete'),
        ('lab_result','trg_lab_result_no_delete')
    ) AS v(bang, trg)
    LOOP
        IF to_regclass('public.' || t.bang) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE TRIGGER %I', t.bang, t.trg);
        END IF;
    END LOOP;
END $$;

\echo '--- SAU ---'
SELECT 'patient' AS bang, count(*) FROM public.patient
UNION ALL SELECT 'appointment', count(*) FROM public.appointment
UNION ALL SELECT 'visit', count(*) FROM public.visit
UNION ALL SELECT 'work_roster (GIỮ)', count(*) FROM public.work_roster
UNION ALL SELECT 'roster_week (GIỮ)', count(*) FROM public.roster_week
UNION ALL SELECT 'staff (GIỮ)', count(*) FROM public.staff
UNION ALL SELECT 'service_type (GIỮ)', count(*) FROM public.service_type
UNION ALL SELECT 'event_log (GIỮ)', count(*) FROM public.event_log;

COMMIT;
