-- Tuần lịch trực ĐÃ ÁP DỤNG — tách "đã xếp" khỏi "đã chốt".
--
-- VÌ SAO CẦN. Phòng khám công bố lịch trực theo tuần, thường vào đầu tuần. Mà
-- CSKH nhận đặt lịch trước cả tháng. Trước migration này hệ thống chỉ biết hai
-- trạng thái: có dòng lịch trực, hoặc không có. Nên một tuần mới xếp nháp và
-- một tuần đã chốt trông hệt nhau.
--
-- Chuyện đó vừa nổ ra thật ngày 07/08/2026: 26 tuần lịch được trải ra từ mẫu
-- tuần tháng 6 và ghi thẳng `status = 'APPROVED'` tới 31/01/2027. Từ lúc đó màn
-- đặt lịch nói chắc nịch "BS Thành trực ngày 12/12" trong khi phòng khám chưa
-- hề quyết. Sai kiểu đó không ai phát hiện được — nó chỉ vỡ khi bệnh nhân tới
-- nơi và không có bác sĩ.
--
-- MỘT NGUỒN SỰ THẬT, KHÔNG PHẢI HAI.
--
-- Cách rẻ hơn là suy "tuần đã áp dụng" = mọi dòng của tuần đều APPROVED. Không
-- chọn cách ấy: nó biến một phép suy N-dòng thành định nghĩa, nên thêm một ca
-- vào tuần đã chốt là cả tuần lặng lẽ thành chưa chốt. Và nó không trả lời được
-- "ai áp dụng, lúc nào" — thứ bắt buộc phải có khi lịch trực bắt đầu quyết định
-- việc nhận đặt hay từ chối.
--
-- Nên: `work_roster.status` giữ nguyên ý nghĩa cũ (vòng đời của MỘT dòng phân
-- công), còn bảng này là sự thật duy nhất cho câu "TUẦN này đã áp dụng chưa".
-- Có dòng ở đây = đã áp dụng. Không có = chưa.

CREATE TABLE IF NOT EXISTS public.roster_week (
    clinic_id           uuid        NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    week_start          date        NOT NULL,
    applied_at          timestamptz NOT NULL DEFAULT now(),
    applied_by_staff_id uuid        REFERENCES public.staff(id) ON DELETE SET NULL,
    note                text,
    PRIMARY KEY (clinic_id, week_start),
    -- Tuần LUÔN bắt đầu thứ Hai. Thiếu chốt này thì hai dòng cùng một tuần
    -- (một ghi thứ Hai, một ghi Chủ nhật) cùng tồn tại và câu hỏi "tuần này đã
    -- áp dụng chưa" có hai câu trả lời.
    CONSTRAINT roster_week_bat_dau_thu_hai
        CHECK (extract(isodow FROM week_start) = 1)
);

COMMENT ON TABLE public.roster_week IS
    'Tuần lịch trực đã được quản lý bấm Áp dụng. Có dòng = đã chốt.';

CREATE INDEX IF NOT EXISTS idx_roster_week_clinic ON public.roster_week (clinic_id, week_start);

ALTER TABLE public.roster_week ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'roster_week'
           AND policyname = 'roster_week_select_own_clinic'
    ) THEN
        -- CHỈ ĐỌC cho client. Ghi đi qua FastAPI bằng vai dịch vụ, cùng lý do
        -- với mọi bảng luật khác: client tự ghi được nghĩa là client tự chốt
        -- được lịch trực của phòng khám.
        CREATE POLICY roster_week_select_own_clinic ON public.roster_week
            FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- CHÍNH SÁCH KHÔNG CẤP QUYỀN. Một policy RLS chỉ LỌC những dòng mà vai đã có
-- quyền đọc; thiếu GRANT thì bảng vô hình hoàn toàn, và ở đây triệu chứng sẽ là
-- MỌI tuần đều trông như chưa áp dụng — mãi mãi, không báo lỗi gì. Bài canh
-- tenant_scoped_rls.sql bắt đúng chuyện này.
GRANT SELECT ON public.roster_week TO authenticated;

-- Tuần ĐANG DÙNG được đánh dấu đã áp dụng, để phòng khám không mất lịch giữa
-- chừng lúc migration chạy. Mọi tuần sau đó là dự kiến cho tới khi có người bấm.
INSERT INTO public.roster_week (clinic_id, week_start, note)
SELECT c.id,
       (current_date - (extract(isodow FROM current_date)::int - 1))::date,
       'Tuần đang chạy lúc thêm khái niệm áp dụng (20260808000001).'
  FROM public.clinic c
 WHERE EXISTS (
         SELECT 1 FROM public.work_roster w
          WHERE w.clinic_id = c.id
            AND w.week_start = (current_date - (extract(isodow FROM current_date)::int - 1))::date
       )
ON CONFLICT (clinic_id, week_start) DO NOTHING;

DO $$
DECLARE n int; m int;
BEGIN
    SELECT count(*) INTO n FROM public.roster_week;
    SELECT count(DISTINCT week_start) INTO m FROM public.work_roster;
    RAISE NOTICE 'Lịch trực: % tuần có dòng, % tuần đã áp dụng. Phần còn lại là DỰ KIẾN.', m, n;
END $$;
