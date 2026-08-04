-- PHÒNG — thứ mà mô hình node không nói được, và điều phối thì không thể thiếu.
--
-- `node_definition` mô tả BƯỚC ("Thực hiện siêu âm"), không mô tả CHỖ. Nhưng cả
-- việc của Trưởng ca xoay quanh chỗ: SA1 đang 9 người chờ còn SA2 rảnh thì
-- chuyển bớt sang. Không có phòng thì "chuyển phòng" là một câu không viết được.
--
-- Phòng khám xác nhận (Quang, 2026-08-04): có SA1, SA2 VÀ SA3; Tiếp nhận
-- (check-in) và Sinh hiệu là hai trạm thật, không phải bước ảo.
--
-- MỘT BẢNG, KHÔNG PHẢI MỘT CỘT TEXT. Phòng có sức chứa, có người trực, có thứ
-- tự hiển thị trên TV, và sẽ có ngưỡng cảnh báo riêng. Nhét vào `work_item.
-- payload->>'room'` thì mọi câu hỏi ("SA2 chứa được mấy người?") thành một phép
-- quét toàn bảng trên JSON không chỉ mục.

CREATE TABLE IF NOT EXISTS public.clinic_room (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id  uuid REFERENCES public.clinic_location(id) ON DELETE SET NULL,
    code         text NOT NULL,
    name         text NOT NULL,
    -- Bước mà phòng này phục vụ. Nhiều phòng cùng một node là chuyện thường —
    -- đó chính là SA1/SA2/SA3 của node DICHVU-SIEUAM.
    node_code    text NOT NULL,
    -- Bao nhiêu người được phục vụ ĐỒNG THỜI. Không phải sức chứa hàng chờ.
    capacity     integer NOT NULL DEFAULT 1,
    -- Có nhận bệnh nhân mới không. Phòng đang sửa máy thì tắt cờ này chứ không
    -- xoá dòng — lịch sử điều phối vẫn phải trỏ về được.
    accepting    boolean NOT NULL DEFAULT true,
    sort         integer NOT NULL DEFAULT 0,
    -- Hiện trên TV phòng chờ hay không. Phòng nội bộ (kho, hành chính) thì không.
    show_on_tv   boolean NOT NULL DEFAULT true,
    is_active    boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT clinic_room_capacity_sane CHECK (capacity BETWEEN 1 AND 50),
    CONSTRAINT uq_clinic_room_code UNIQUE (clinic_id, code)
);

COMMENT ON TABLE public.clinic_room IS
    'Phòng vật lý phục vụ một bước (node). Nhiều phòng cùng node = SA1/SA2/SA3. '
    'Trưởng ca điều phối theo phòng, không theo node.';
COMMENT ON COLUMN public.clinic_room.capacity IS
    'Số người phục vụ ĐỒNG THỜI, không phải sức chứa hàng chờ.';

CREATE INDEX IF NOT EXISTS idx_clinic_room_node
    ON public.clinic_room (clinic_id, node_code) WHERE is_active;

-- ---------------------------------------------------------------------------
-- work_item biết mình đang ở phòng nào
-- ---------------------------------------------------------------------------
-- NULL = chưa xếp phòng (bước không gắn phòng, hoặc đang chờ Trưởng ca xếp).
-- Không đặt NOT NULL: phần lớn bước trong hệ thống không có phòng, và ép chúng
-- mang một phòng giả sẽ làm mọi phép đếm tải sai.

ALTER TABLE public.work_item
    ADD COLUMN IF NOT EXISTS room_id uuid REFERENCES public.clinic_room(id);

COMMENT ON COLUMN public.work_item.room_id IS
    'Phòng đang xử lý bước này. NULL = bước không gắn phòng hoặc chưa xếp.';

CREATE INDEX IF NOT EXISTS idx_work_item_room_open
    ON public.work_item (clinic_id, room_id, status)
 WHERE status IN ('PENDING', 'IN_PROGRESS') AND room_id IS NOT NULL;

-- Phòng phải cùng phòng khám với công việc. Một dòng trỏ sang phòng của phòng
-- khám khác là rò rỉ dữ liệu, không phải lỗi hiển thị.
CREATE OR REPLACE FUNCTION public.work_item_room_matches_clinic()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF NEW.room_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.clinic_room r
         WHERE r.id = NEW.room_id AND r.clinic_id = NEW.clinic_id
    ) THEN
        RAISE EXCEPTION 'Phòng % không thuộc phòng khám của công việc này',
            NEW.room_id;
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_work_item_room_clinic ON public.work_item;
CREATE TRIGGER trg_work_item_room_clinic
    BEFORE INSERT OR UPDATE OF room_id, clinic_id ON public.work_item
    FOR EACH ROW EXECUTE FUNCTION public.work_item_room_matches_clinic();

-- ---------------------------------------------------------------------------
-- RLS — cùng khuôn với các bảng cấu hình khác
-- ---------------------------------------------------------------------------

ALTER TABLE public.clinic_room ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinic_room_select ON public.clinic_room;
CREATE POLICY clinic_room_select ON public.clinic_room
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Chỉ Trưởng ca và Quản lý sửa được danh sách phòng. Không mở cho mọi vai:
-- đổi sức chứa một phòng là đổi cách cả ca làm việc được điều phối.
DROP POLICY IF EXISTS clinic_room_write ON public.clinic_room;
CREATE POLICY clinic_room_write ON public.clinic_room
    FOR ALL TO authenticated
    USING (clinic_id IN (
        SELECT public.current_clinic_ids_for_roles(
            ARRAY['MANAGEMENT', 'TRUONG_CA'])))
    WITH CHECK (clinic_id IN (
        SELECT public.current_clinic_ids_for_roles(
            ARRAY['MANAGEMENT', 'TRUONG_CA'])));

GRANT SELECT ON public.clinic_room TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.clinic_room TO authenticated;

-- ---------------------------------------------------------------------------
-- Seed phòng của Dr4Women
-- ---------------------------------------------------------------------------
-- Lấy đúng danh sách phòng khám xác nhận, không thêm phòng tưởng tượng.
-- `ON CONFLICT DO NOTHING` để chạy lại migration không nhân đôi.

-- GẮN LUÔN CƠ SỞ khi tạo phòng.
--
-- Bản đầu để location_id trống, và hệ quả là 12/12 phòng trên production không
-- thuộc cơ sở nào — chỉ lộ ra khi khai tầng (20260804000012). Từ khi migration
-- đó đặt NOT NULL, chèn phòng mà bỏ trống cơ sở là lỗi ngay — kể cả lần chạy
-- lại của chính migration này.
--
-- Cơ sở đầu tiên của chính phòng khám đó, không tìm theo tên: tên là dữ liệu
-- của một khách hàng, không phải hằng số sản phẩm.
INSERT INTO public.clinic_room
    (clinic_id, location_id, code, name, node_code, capacity, sort, show_on_tv)
SELECT c.id,
       (SELECT l.id FROM public.clinic_location l
         WHERE l.clinic_id = c.id AND l.is_active
         ORDER BY l.created_at, l.id LIMIT 1),
       v.code, v.name, v.node_code, v.capacity, v.sort, v.show_on_tv
  FROM public.clinic c
  CROSS JOIN (VALUES
      ('TIEPNHAN', 'Tiếp nhận',    'LUOTKHAM-01',   2, 10, true),
      ('SINHHIEU', 'Sinh hiệu',    'LUOTKHAM-03',   2, 20, true),
      ('KB01',     'Khám 1',       'KHAM-PHUKHOA',  1, 30, true),
      ('KB02',     'Khám 2',       'KHAM-PHUKHOA',  1, 31, true),
      ('KB03',     'Khám 3',       'KHAM-PHUKHOA',  1, 32, true),
      ('KB04',     'Khám 4',       'KHAM-PHUKHOA',  1, 33, true),
      ('SA1',      'Siêu âm SA1',  'DICHVU-SIEUAM', 1, 40, true),
      ('SA2',      'Siêu âm SA2',  'DICHVU-SIEUAM', 1, 41, true),
      ('SA3',      'Siêu âm SA3',  'DICHVU-SIEUAM', 1, 42, true),
      ('XETNGHIEM','Lấy máu / Xét nghiệm', 'DICHVU-LAYMAU-MAU', 2, 50, true),
      ('NHATHUOC', 'Nhà thuốc',    'THUOC-04',      1, 60, true),
      ('THUNGAN',  'Thu ngân',     'LUOTKHAM-14',   2, 70, true)
  ) AS v(code, name, node_code, capacity, sort, show_on_tv)
ON CONFLICT (clinic_id, code) DO NOTHING;

DO $verify$
DECLARE v_sa int; v_all int;
BEGIN
    SELECT count(*) INTO v_sa FROM public.clinic_room
     WHERE node_code = 'DICHVU-SIEUAM' AND is_active;
    SELECT count(*) INTO v_all FROM public.clinic_room WHERE is_active;
    IF v_sa < 3 THEN
        RAISE EXCEPTION 'Phải có đủ SA1/SA2/SA3, hiện có %', v_sa;
    END IF;
    RAISE NOTICE 'clinic_room: % phòng (% phòng siêu âm)', v_all, v_sa;
END
$verify$;
