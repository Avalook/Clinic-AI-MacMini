-- Lịch trực chỉ có hiệu lực khi TUẦN ĐÃ ĐƯỢC ÁP DỤNG (migration 20260808000001).
--
-- Bất biến cần giữ có hai vế, và vế thứ hai mới là vế dễ mất:
--
--   1. Tuần ĐÃ áp dụng  → lịch trực là luật: bác sĩ không có tên = không nhận đặt.
--   2. Tuần CHƯA áp dụng → im lặng cho đặt. KHÔNG được coi là "cả phòng khám nghỉ".
--
-- Vế 2 là quyết định cũ của phòng khám: CSKH nhận đặt trước cả tháng, lúc ấy
-- lịch trực chưa xếp. Coi "chưa xếp" là "không đi làm" sẽ khoá sạch tương lai.
-- Khi thêm khái niệm "áp dụng", rất dễ vô tình biến "chưa áp dụng" thành "nghỉ"
-- — và triệu chứng sẽ là phòng khám không đặt được lịch nào quá tuần này, mà
-- không báo lỗi gì cả.
--
-- Bài này khẳng định HÀNH VI, không khẳng định hình dạng câu SQL.
-- Mọi thứ rollback.

BEGIN;

-- Dựng phòng khám riêng: CI chỉ chạy migration, không nạp seed.
INSERT INTO public.clinic (id, code, name)
VALUES ('c0000000-0000-4000-8000-0000000a0001', 'TEST-ADT', 'Phòng khám kiểm thử')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.clinic_location (id, clinic_id, code, name)
VALUES ('c0000000-0000-4000-8000-0000000a0002',
        'c0000000-0000-4000-8000-0000000a0001', 'CS1', 'Cơ sở 1')
ON CONFLICT (id) DO NOTHING;

-- `staff` KHÔNG mang clinic_id: ai làm cho phòng khám nào nằm ở clinic_membership
-- (ADR-0009), để một người biệt phái sang phòng khám thứ hai không phải nhân đôi
-- hồ sơ. Bài này không cần membership vì nó chỉ tra work_roster ↔ roster_week.
INSERT INTO public.staff (id, primary_location_id, full_name, primary_department)
VALUES ('c0000000-0000-4000-8000-0000000a0003',
        'c0000000-0000-4000-8000-0000000a0002', 'BS Kiểm Thử', 'DOCTOR')
ON CONFLICT (id) DO NOTHING;

-- Hai tuần, cùng một bác sĩ, cùng trạng thái APPROVED trên từng dòng.
-- Khác nhau ĐÚNG MỘT thứ: tuần nào có dòng trong roster_week.
INSERT INTO public.work_roster
    (clinic_id, week_start, work_date, shift, station, staff_id, staff_name, status)
VALUES
    ('c0000000-0000-4000-8000-0000000a0001', DATE '2026-09-07', DATE '2026-09-07',
     'FULL', 'LICH_KHAM', 'c0000000-0000-4000-8000-0000000a0003', 'BS Kiểm Thử', 'APPROVED'),
    ('c0000000-0000-4000-8000-0000000a0001', DATE '2026-09-14', DATE '2026-09-14',
     'FULL', 'LICH_KHAM', 'c0000000-0000-4000-8000-0000000a0003', 'BS Kiểm Thử', 'APPROVED');

INSERT INTO public.roster_week (clinic_id, week_start)
VALUES ('c0000000-0000-4000-8000-0000000a0001', DATE '2026-09-07');

DO $$
DECLARE
    da_ap   boolean;
    chua_ap boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.work_roster w
          JOIN public.roster_week rw
            ON rw.clinic_id = w.clinic_id AND rw.week_start = w.week_start
         WHERE w.clinic_id = 'c0000000-0000-4000-8000-0000000a0001'
           AND w.work_date = DATE '2026-09-07' AND w.status = 'APPROVED'
    ) INTO da_ap;

    SELECT EXISTS (
        SELECT 1 FROM public.work_roster w
          JOIN public.roster_week rw
            ON rw.clinic_id = w.clinic_id AND rw.week_start = w.week_start
         WHERE w.clinic_id = 'c0000000-0000-4000-8000-0000000a0001'
           AND w.work_date = DATE '2026-09-14' AND w.status = 'APPROVED'
    ) INTO chua_ap;

    IF NOT da_ap THEN
        RAISE EXCEPTION 'Tuần ĐÃ áp dụng phải được coi là đã xếp ca.';
    END IF;
    IF chua_ap THEN
        RAISE EXCEPTION
            'Tuần CHƯA áp dụng bị coi là đã xếp ca — lịch dự kiến đang được '
            'dùng như lịch đã chốt. Đây đúng là lỗi ngày 07/08/2026.';
    END IF;
END $$;

-- Tuần LUÔN bắt đầu thứ Hai: hai dòng cùng một tuần thì câu hỏi "tuần này đã áp
-- dụng chưa" có hai câu trả lời.
DO $$
BEGIN
    BEGIN
        INSERT INTO public.roster_week (clinic_id, week_start)
        VALUES ('c0000000-0000-4000-8000-0000000a0001', DATE '2026-09-13'); -- Chủ nhật
        RAISE EXCEPTION 'Nhận cả ngày không phải thứ Hai làm mốc tuần.';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END $$;

ROLLBACK;
