-- PHÒNG KHÁM CHỈ CÓ MỘT CƠ SỞ THÌ KHÔNG CÓ GÌ ĐỂ ĐOÁN.
--
-- `staff.primary_location_id` là NOT NULL từ 20260803000007 — đúng: một dòng
-- nhân sự không có cơ sở là một dòng chưa đủ để làm việc. Nhưng ràng buộc đó
-- bắt MỌI đường tạo nhân sự phải tự điền cơ sở, kể cả khi phòng khám chỉ có
-- đúng một chỗ để chọn.
--
-- Hệ quả thấy được: sáu bài kiểm schema trong repo tạo nhân sự mà không khai
-- cơ sở, và tất cả cùng đỏ. Nhưng đó chỉ là chỗ lộ ra trước; cùng vấn đề sẽ đợi
-- ở màn thêm nhân sự, ở script nhập liệu, ở mọi lần khôi phục.
--
-- LUẬT NÀY KHÔNG MỚI. Chính 20260803000007 đã quyết đúng như vậy khi backfill:
-- một cơ sở thì gán, nhiều cơ sở mà chưa rõ thì DỪNG và bắt người quyết. Trigger
-- này chỉ áp cùng luật đó cho những dòng sinh ra SAU migration kia, thay vì để
-- nó chỉ đúng một lần rồi thôi.
--
-- Dr4Women hôm nay có HAI cơ sở đang hoạt động, nên trigger không điền hộ —
-- người tạo nhân sự vẫn phải chọn, và vẫn nhận đúng lỗi NOT NULL nếu quên. Đó
-- là chủ ý: đoán sai cơ sở của một nhân viên là xếp họ vào nhầm toà nhà.

CREATE OR REPLACE FUNCTION public.staff_default_primary_location()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_clinic uuid;
    v_count  int;
BEGIN
    IF NEW.primary_location_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Phòng khám của nhân sự này: lấy từ membership nếu đã có, không thì phòng
    -- khám mặc định (triển khai một tenant).
    SELECT m.clinic_id INTO v_clinic
      FROM public.clinic_membership m
     WHERE m.staff_id = NEW.id AND m.is_active
     LIMIT 1;
    IF v_clinic IS NULL THEN
        SELECT public.default_clinic_id() INTO v_clinic;
    END IF;
    IF v_clinic IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT count(*) INTO v_count
      FROM public.clinic_location
     WHERE clinic_id = v_clinic AND is_active;

    -- ĐÚNG MỘT cơ sở mới điền. Hai cơ sở trở lên thì để nguyên NULL và ràng
    -- buộc NOT NULL sẽ nói — đoán hộ ở đây là xếp một người vào nhầm toà nhà,
    -- rồi mọi bảng lọc theo cơ sở sẽ giấu họ đi.
    IF v_count = 1 THEN
        SELECT id INTO NEW.primary_location_id
          FROM public.clinic_location
         WHERE clinic_id = v_clinic AND is_active;
    END IF;

    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_staff_default_primary_location ON public.staff;
CREATE TRIGGER trg_staff_default_primary_location
    BEFORE INSERT ON public.staff
    FOR EACH ROW EXECUTE FUNCTION public.staff_default_primary_location();

DO $verify$
DECLARE
    v_sites int;
BEGIN
    SELECT count(*) INTO v_sites FROM public.clinic_location WHERE is_active;
    RAISE NOTICE
        'nhân sự tự nhận cơ sở khi phòng khám có đúng 1 chỗ (hiện có % chỗ '
        'đang hoạt động)', v_sites;
END
$verify$;
