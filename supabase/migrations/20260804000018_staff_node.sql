-- AI LÀM ĐƯỢC VIỆC GÌ — khai được, không viết cứng.
--
-- Yêu cầu của Quang (04/08/2026): *"bác sĩ đó có thể khám cả 5 dịch vụ khám,
-- hay bác sĩ đó chỉ khám 2-3 loại dịch vụ, hay bác sĩ đó chỉ siêu âm. như thế
-- mới có sự linh hoạt được, để khi sang phòng khám khác họ có cấu trúc khác"*.
--
-- Năm "dịch vụ khám" ấy CHÍNH LÀ năm node đã khai: KHAM-PHUKHOA, KHAM-SANKHOA,
-- KHAM-NAMKHOA, KHAM-NOITIET, KHAM-HIEMMUON-VOSINH. Còn "chỉ siêu âm" là
-- DICHVU-SIEUAM. Nên không cần từ vựng mới — dùng đúng bộ node đang có.
--
-- ĐỐI XỨNG VỚI `clinic_room_node`. Phòng phục vụ những bước nào; người làm được
-- những bước nào. Cùng một hình dạng, cùng khoá ngoại tới node_definition
-- (clinic_id, code), cùng cách khai. Hai bảng cùng dạng thì người đọc code chỉ
-- phải hiểu một lần, và màn cấu hình dùng chung được một mẫu.
--
-- VÌ SAO KHÔNG DÙNG `staff_capability` CÓ SẴN.
--
-- Bảng đó tồn tại, 0 dòng, chưa ai dùng — và có ba vấn đề:
--   · `capability` là text TỰ DO, không khoá ngoại: gõ 'KHAM-PHU-KHOA' thay vì
--     'KHAM-PHUKHOA' thì im lặng không khớp gì.
--   · KHÔNG có clinic_id. Đúng thứ Quang vừa nói phải có: *"mọi thứ code
--     backend là phải có id phòng khám, id cơ sở"*.
--   · Không có phạm vi cơ sở, mà một bác sĩ có thể chỉ làm ở một cơ sở.
-- Để nguyên nó (0 dòng, không ai đọc), dựng bảng đúng bên cạnh.

CREATE TABLE IF NOT EXISTS public.staff_node (
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    staff_id   uuid NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    node_code  text NOT NULL,
    -- NULL = làm được ở MỌI cơ sở của phòng khám này. Có giá trị = chỉ cơ sở
    -- đó. Một bác sĩ trực Kim Ngưu thứ Ba và Hào Nam thứ Năm thì khai hai dòng.
    location_id uuid REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Khoá thay thế, KHÔNG dùng (staff_id, node_code, location_id) làm khoá
    -- chính: khoá chính không chứa NULL được, nên nó sẽ âm thầm ép location_id
    -- thành NOT NULL và mất luôn nghĩa "mọi cơ sở". Hai chỉ mục duy nhất bên
    -- dưới mới là thứ giữ tính duy nhất, và chúng phân biệt được NULL.
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    CONSTRAINT staff_node_node_fk
        FOREIGN KEY (clinic_id, node_code)
        REFERENCES public.node_definition (clinic_id, code) ON DELETE RESTRICT
);

COMMENT ON TABLE public.staff_node IS
    'Người này làm được những bước nào (khám phụ khoa / nam khoa / siêu âm…). '
    'Đối xứng với clinic_room_node: phòng phục vụ bước nào, người làm bước nào.';

CREATE INDEX IF NOT EXISTS idx_staff_node_lookup
    ON public.staff_node (clinic_id, node_code);

-- PRIMARY KEY có location_id (nullable) nên hai dòng cùng (staff, node) mà một
-- dòng location NULL và một dòng có giá trị vẫn lọt. Chặn: khai "mọi cơ sở" thì
-- không khai thêm cơ sở lẻ nào nữa — hai cách nói cùng một điều là hai chỗ để
-- lệch khi sửa.
CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_node_all_locations
    ON public.staff_node (staff_id, node_code)
    WHERE location_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_node_per_location
    ON public.staff_node (staff_id, node_code, location_id)
    WHERE location_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.staff_node_no_mixed_scope()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF NEW.location_id IS NULL THEN
        IF EXISTS (SELECT 1 FROM public.staff_node
                    WHERE staff_id = NEW.staff_id AND node_code = NEW.node_code
                      AND location_id IS NOT NULL) THEN
            RAISE EXCEPTION
                'Đã khai bước % cho từng cơ sở — bỏ các dòng đó trước khi khai '
                '"mọi cơ sở"', NEW.node_code
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM public.staff_node
                   WHERE staff_id = NEW.staff_id AND node_code = NEW.node_code
                     AND location_id IS NULL) THEN
        RAISE EXCEPTION
            'Người này đã làm được bước % ở MỌI cơ sở — không cần khai riêng '
            'từng nơi', NEW.node_code
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_staff_node_scope ON public.staff_node;
CREATE TRIGGER trg_staff_node_scope
    BEFORE INSERT OR UPDATE ON public.staff_node
    FOR EACH ROW EXECUTE FUNCTION public.staff_node_no_mixed_scope();

-- ---------------------------------------------------------------------------
-- Nạp từ những gì đã biết
-- ---------------------------------------------------------------------------
-- KHÔNG đoán ai khám được gì. Chỉ chép lại đúng điều đã khai ở nơi khác:
-- vai trong phòng khám. Bác sĩ siêu âm → làm được bước siêu âm. Bác sĩ khám →
-- năm chuyên khoa, vì hôm nay chưa ai khai hẹp hơn và bốn phòng khám cũng đang
-- phục vụ cả năm. Quản lý phòng khám thu hẹp lại ở màn cấu hình khi cần.

INSERT INTO public.staff_node (clinic_id, staff_id, node_code)
SELECT m.clinic_id, m.staff_id, n.code
  FROM public.clinic_membership m
  JOIN public.node_definition n ON n.clinic_id = m.clinic_id
 WHERE m.is_active
   AND (
        (m.role = 'ULTRASOUND_DOCTOR' AND n.code = 'DICHVU-SIEUAM')
     OR (m.role = 'DOCTOR'            AND n.code LIKE 'KHAM-%')
   )
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- RLS — đọc cho mọi vai, ghi CHỈ backend (ADR-0012)
-- ---------------------------------------------------------------------------
-- Không tạo chính sách ghi cho `authenticated`: mọi lệnh ghi đi qua FastAPI,
-- nơi dùng service role và bỏ qua RLS. Chín chính sách ghi lọt lưới hai tuần
-- trước đã phải gỡ ở 20260804000016 — đừng thêm cái thứ mười.

ALTER TABLE public.staff_node ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS staff_node_select ON public.staff_node;
CREATE POLICY staff_node_select ON public.staff_node
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

GRANT SELECT ON public.staff_node TO authenticated;

DO $verify$
DECLARE
    n_bs int;
    n_sa int;
BEGIN
    SELECT count(DISTINCT staff_id) INTO n_bs FROM public.staff_node
     WHERE node_code LIKE 'KHAM-%';
    SELECT count(DISTINCT staff_id) INTO n_sa FROM public.staff_node
     WHERE node_code = 'DICHVU-SIEUAM';
    RAISE NOTICE 'khai năng lực: % bác sĩ khám, % người siêu âm', n_bs, n_sa;
END
$verify$;
