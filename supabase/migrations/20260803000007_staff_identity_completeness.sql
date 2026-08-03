-- Mỗi tài khoản phải trả lời được: ai, phòng khám nào, CƠ SỞ nào.
--
-- YÊU CẦU (Quang, 2026-08-03): "tài khoản nào thì cũng phải có id phòng khám,
-- cơ sở khám để từ giờ trở đi không bị nhầm nữa. Ví dụ bác sĩ Thành thuộc phòng
-- khám Dr4Women, cơ sở Kim Ngưu."
--
-- HAI PHẦN CỦA CÂU ĐÓ ĐANG Ở HAI TÌNH TRẠNG KHÁC NHAU:
--
--   PHÒNG KHÁM đã chặt. clinic_membership là bắt buộc, identity.py từ chối một
--   đăng nhập không có membership đang hoạt động, và mọi câu ghi đều mang
--   clinic_id.
--
--   CƠ SỞ thì không. staff.primary_location_id cho phép NULL, và 27 trong 90
--   nhân sự đang để trống. Cột đó là thứ quyết định lịch hẹn rơi vào cơ sở nào,
--   ngân sách khung giờ (block_budget) tra ở đâu, ca trực thuộc về đâu — nên
--   một giá trị trống không phải "chưa điền", nó là "đoán lúc chạy". Đó chính
--   là cái nhầm mà yêu cầu này muốn chấm dứt.
--
-- Migration này làm cơ sở trở thành bắt buộc, và gộp hai vai thu ngân.

-- (Không dùng `\set` — đó là lệnh psql, `supabase db push` không hiểu.
--  Xem chú thích trong 20260803000004.)

-- ---------------------------------------------------------------------------
-- 1. Thu ngân: ba vai gộp còn một
-- ---------------------------------------------------------------------------
-- CASHIER_THUOC / CASHIER_DV được tách ra để mỗi người chỉ thấy bảng giá của
-- mình. Thực tế phòng khám chỉ có một quầy, và việc tách làm ba thứ tệ hơn:
--
--   * NAV_ROLES phải liệt kê cả ba ở mọi mục thu ngân, quên một chỗ là một vai
--     mất màn hình mà không ai biết;
--   * roles.ts phải có isCashierRole() gom lại — tức đã tự thừa nhận ba vai này
--     luôn được đối xử như một;
--   * audit log ghi ba giá trị khác nhau cho cùng một công việc.
--
-- CASHIER vốn đã là superset (thấy cả hai bảng giá), nên gộp về CASHIER không
-- làm ai mất quyền. Hai giá trị kia được GIỮ trong enum của ứng dụng, vì
-- event_log cũ có chứa chúng và một bản ghi kiểm toán không đọc được là một bản
-- ghi kiểm toán vô dụng.

UPDATE public.clinic_membership
   SET role = 'CASHIER', updated_at = now()
 WHERE role IN ('CASHIER_THUOC', 'CASHIER_DV');

UPDATE public.staff
   SET primary_department = 'CASHIER', updated_at = now()
 WHERE primary_department IN ('CASHIER_THUOC', 'CASHIER_DV');

-- ---------------------------------------------------------------------------
-- 2. Cơ sở khám: điền cho người còn trống, rồi bắt buộc
-- ---------------------------------------------------------------------------
-- KHÔNG đoán khi có nhiều lựa chọn. Nếu phòng khám có đúng MỘT cơ sở đang hoạt
-- động thì điền vào đó là suy luận an toàn duy nhất có thể. Nhiều hơn một thì
-- dừng lại — chọn hộ giữa hai cơ sở chính là kiểu nhầm mà migration này sinh ra
-- để ngăn.

DO $backfill$
DECLARE
    v_clinic   uuid;
    v_location uuid;
    v_actives  int;
    v_filled   int;
BEGIN
    FOR v_clinic IN SELECT id FROM public.clinic LOOP
        SELECT count(*) INTO v_actives
          FROM public.clinic_location
         WHERE clinic_id = v_clinic AND is_active;

        IF v_actives = 0 THEN
            RAISE EXCEPTION
                'Phòng khám % không có cơ sở nào đang hoạt động — tạo cơ sở trước.',
                v_clinic;
        ELSIF v_actives > 1 THEN
            -- Chỉ dừng khi thật sự CÓ người cần điền. Một phòng khám nhiều cơ sở
            -- mà mọi nhân sự đã gắn đúng chỗ thì không có gì để quyết.
            IF EXISTS (
                SELECT 1 FROM public.staff s
                  JOIN public.clinic_membership m
                    ON m.staff_id = s.id AND m.clinic_id = v_clinic AND m.is_active
                 WHERE s.primary_location_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Phòng khám % có % cơ sở đang hoạt động và còn nhân sự chưa gắn '
                    'cơ sở. Gán tay trước khi chạy migration này — không đoán hộ.',
                    v_clinic, v_actives;
            END IF;
            CONTINUE;
        END IF;

        SELECT id INTO v_location
          FROM public.clinic_location
         WHERE clinic_id = v_clinic AND is_active;

        UPDATE public.staff s
           SET primary_location_id = v_location, updated_at = now()
          FROM public.clinic_membership m
         WHERE m.staff_id = s.id
           AND m.clinic_id = v_clinic
           AND s.primary_location_id IS NULL;

        GET DIAGNOSTICS v_filled = ROW_COUNT;
        RAISE NOTICE 'phòng khám %: gắn cơ sở cho % nhân sự', v_clinic, v_filled;
    END LOOP;
END
$backfill$;

-- Sau backfill, một dòng staff không có cơ sở là một dòng chưa đủ để làm việc.
-- NOT NULL nói điều đó ở nơi duy nhất không thể quên: database.
ALTER TABLE public.staff
    ALTER COLUMN primary_location_id SET NOT NULL;

COMMENT ON COLUMN public.staff.primary_location_id IS
    'Cơ sở làm việc chính. BẮT BUỘC từ 20260803000007: cột này quyết định lịch '
    'hẹn thuộc cơ sở nào và block_budget tra ở đâu, nên NULL không phải "chưa '
    'điền" mà là "đoán lúc chạy".';

-- ---------------------------------------------------------------------------
-- 3. Cơ sở phải thuộc đúng phòng khám của nhân sự
-- ---------------------------------------------------------------------------
-- NOT NULL mới chỉ bảo đảm CÓ một cơ sở. Nó không ngăn được việc gắn nhân sự
-- của phòng khám A vào cơ sở của phòng khám B — đúng loại nhầm lẫn xuyên tenant
-- mà cả W2/W3 dựng lên để chặn, chỉ là ở một cột chưa ai để ý.
--
-- Trigger chứ không phải CHECK: ràng buộc này phải đọc hai bảng khác, và CHECK
-- không được phép làm thế.

CREATE OR REPLACE FUNCTION public.staff_location_matches_clinic()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_loc_clinic uuid;
BEGIN
    IF NEW.primary_location_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT clinic_id INTO v_loc_clinic
      FROM public.clinic_location
     WHERE id = NEW.primary_location_id;

    -- Nhân sự chưa có membership (vừa INSERT, trigger membership chạy sau) thì
    -- chưa kiểm được — để lần UPDATE sau bắt. Chặn ở đây sẽ làm hỏng chính
    -- đường tạo nhân sự.
    IF NOT EXISTS (
        SELECT 1 FROM public.clinic_membership m
         WHERE m.staff_id = NEW.id AND m.clinic_id = v_loc_clinic
    ) AND EXISTS (
        SELECT 1 FROM public.clinic_membership m WHERE m.staff_id = NEW.id
    ) THEN
        RAISE EXCEPTION
            'Cơ sở % không thuộc phòng khám nào mà nhân sự % là thành viên.',
            NEW.primary_location_id, NEW.id;
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_staff_location_matches_clinic ON public.staff;
CREATE TRIGGER trg_staff_location_matches_clinic
    BEFORE INSERT OR UPDATE OF primary_location_id ON public.staff
    FOR EACH ROW EXECUTE FUNCTION public.staff_location_matches_clinic();

COMMENT ON FUNCTION public.staff_location_matches_clinic() IS
    'Cơ sở làm việc phải nằm trong một phòng khám mà nhân sự có membership. '
    'NOT NULL chỉ bảo đảm có cơ sở; cái này bảo đảm ĐÚNG cơ sở.';
