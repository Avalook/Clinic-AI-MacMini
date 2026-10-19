-- Tầng là danh mục theo từng cơ sở, có thứ tự và ẩn mềm.
-- `clinic_room.floor` vẫn được giữ để các báo cáo/màn cũ tương thích; floor_id
-- là định danh chuẩn và trigger bên dưới giữ hai cột đồng bộ.

CREATE TABLE IF NOT EXISTS public.clinic_floor (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id uuid NOT NULL,
    name text NOT NULL,
    sort_order integer NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT clinic_floor_location_tenant_fkey
        FOREIGN KEY (location_id, clinic_id)
        REFERENCES public.clinic_location(id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT clinic_floor_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT clinic_floor_sort_nonnegative CHECK (sort_order >= 0),
    CONSTRAINT clinic_floor_name_length CHECK (char_length(name) <= 40),
    CONSTRAINT clinic_floor_location_name_key UNIQUE (location_id, name),
    CONSTRAINT clinic_floor_identity_scope_key
        UNIQUE (id, clinic_id, location_id)
);

COMMENT ON TABLE public.clinic_floor IS
    'Danh mục tầng theo cơ sở. Xoá trên giao diện là is_active=false.';
COMMENT ON COLUMN public.clinic_floor.name IS
    'Nhãn tự do: Tầng 1, Trệt, B1… clinic_room.floor giữ bản tương thích.';

CREATE INDEX IF NOT EXISTS idx_clinic_floor_order
    ON public.clinic_floor (clinic_id, location_id, is_active, sort_order, id);

WITH grouped AS (
    SELECT r.clinic_id,
           r.location_id,
           btrim(r.floor) AS name,
           min(coalesce(r.sort, 0)) AS first_room_sort
      FROM public.clinic_room r
     WHERE r.floor IS NOT NULL AND btrim(r.floor) <> ''
     GROUP BY r.clinic_id, r.location_id, btrim(r.floor)
), ranked AS (
    SELECT grouped.*,
           row_number() OVER (
               PARTITION BY clinic_id, location_id
               ORDER BY first_room_sort, name
           ) * 10 AS floor_sort
      FROM grouped
)
INSERT INTO public.clinic_floor
    (clinic_id, location_id, name, sort_order, is_active)
SELECT clinic_id, location_id, name, floor_sort, true
  FROM ranked
ON CONFLICT (location_id, name) DO NOTHING;

ALTER TABLE public.clinic_room
    ADD COLUMN IF NOT EXISTS floor_id uuid;

UPDATE public.clinic_room r
   SET floor_id = f.id,
       floor = f.name
  FROM public.clinic_floor f
 WHERE f.clinic_id = r.clinic_id
   AND f.location_id = r.location_id
   AND f.name = btrim(r.floor)
   AND r.floor IS NOT NULL
   AND r.floor_id IS NULL;

ALTER TABLE public.clinic_room
    DROP CONSTRAINT IF EXISTS clinic_room_floor_scope_fkey;
ALTER TABLE public.clinic_room
    ADD CONSTRAINT clinic_room_floor_scope_fkey
    FOREIGN KEY (floor_id, clinic_id, location_id)
    REFERENCES public.clinic_floor(id, clinic_id, location_id)
    ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_clinic_room_floor_id
    ON public.clinic_room (clinic_id, location_id, floor_id);

-- Các vị trí được người dùng thêm sau đợt gieo ma trận 16/09 chưa có bất kỳ
-- dòng phạm vi nào. Khi một vai đã có phạm vi ở vị trí khác, cơ chế fail-open
-- không còn áp dụng và màn xếp ca chỉ còn thấy các vai chưa từng được cấu hình
-- (thường là Đối tác). Chỉ bù vị trí hoàn toàn chưa được cấu hình để không mở
-- rộng lại những vị trí mà quản lý đã chủ động giới hạn.
WITH unscoped_station AS (
    SELECT v.clinic_id, v.code AS tram_ma
      FROM public.vi_tri_lam_viec v
     WHERE v.is_active
       AND NOT EXISTS (
           SELECT 1
             FROM public.vai_duoc_vao_tram p
            WHERE p.clinic_id = v.clinic_id
              AND p.tram_ma = v.code
       )
), active_role AS (
    -- Lưới lịch và backend kiểm theo staff.primary_department, không theo vai
    -- membership của tài khoản (một bác sĩ có thể đồng thời là MANAGEMENT).
    SELECT DISTINCT m.clinic_id, s.primary_department AS role
      FROM public.clinic_membership m
      JOIN public.staff s ON s.id = m.staff_id AND s.is_active
     WHERE m.is_active
       AND s.primary_department IS NOT NULL
       AND s.primary_department <> 'DISPLAY'
)
INSERT INTO public.vai_duoc_vao_tram
    (clinic_id, tram_ma, vai, is_active, ghi_chu)
SELECT s.clinic_id, s.tram_ma, r.role, true,
       'bù vị trí chưa có phạm vi — mọi vai đang hoạt động'
  FROM unscoped_station s
  JOIN active_role r ON r.clinic_id = s.clinic_id
ON CONFLICT (clinic_id, tram_ma, vai) DO NOTHING;

CREATE OR REPLACE FUNCTION public.sync_clinic_room_floor()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    selected_floor public.clinic_floor%ROWTYPE;
BEGIN
    -- Nhánh tương thích cho client/bài cũ ghi nhãn `floor` trực tiếp. Nếu
    -- floor_id không đổi mà nhãn đổi, resolve (hoặc tạo) danh mục theo nhãn.
    -- API mới gửi floor_id nên nhánh chuẩn bên dưới vẫn dùng định danh.
    IF NEW.floor IS DISTINCT FROM OLD.floor
       AND NEW.floor_id IS NOT DISTINCT FROM OLD.floor_id THEN
        IF NEW.floor IS NULL OR btrim(NEW.floor) = '' THEN
            NEW.floor := NULL;
            NEW.floor_id := NULL;
        ELSE
            NEW.floor := btrim(NEW.floor);
            SELECT * INTO selected_floor
              FROM public.clinic_floor f
             WHERE f.clinic_id = NEW.clinic_id
               AND f.location_id = NEW.location_id
               AND f.name = NEW.floor;
            IF NOT FOUND THEN
                INSERT INTO public.clinic_floor
                    (clinic_id, location_id, name, sort_order)
                VALUES (
                    NEW.clinic_id,
                    NEW.location_id,
                    NEW.floor,
                    coalesce((SELECT max(sort_order) + 10
                                FROM public.clinic_floor
                               WHERE location_id = NEW.location_id
                                 AND is_active), 10)
                )
                ON CONFLICT (location_id, name) DO UPDATE
                    SET is_active = true, updated_at = now()
                RETURNING * INTO selected_floor;
            ELSIF NOT selected_floor.is_active THEN
                UPDATE public.clinic_floor f
                   SET is_active = true,
                       sort_order = coalesce((
                           SELECT max(other.sort_order) + 10
                             FROM public.clinic_floor other
                            WHERE other.location_id = NEW.location_id
                              AND other.is_active
                       ), 10),
                       updated_at = now()
                 WHERE f.id = selected_floor.id
                RETURNING * INTO selected_floor;
            END IF;
            NEW.floor_id := selected_floor.id;
            NEW.floor := selected_floor.name;
        END IF;
    ELSIF NEW.floor_id IS NOT NULL THEN
        SELECT * INTO selected_floor
          FROM public.clinic_floor f
         WHERE f.id = NEW.floor_id
           AND f.clinic_id = NEW.clinic_id
           AND f.location_id = NEW.location_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Tầng không thuộc cơ sở của phòng.'
                USING ERRCODE = '23503';
        END IF;
        NEW.floor := selected_floor.name;
    ELSIF NEW.floor IS NULL OR btrim(NEW.floor) = '' THEN
        NEW.floor := NULL;
        NEW.floor_id := NULL;
    ELSE
        NEW.floor := btrim(NEW.floor);
        SELECT * INTO selected_floor
          FROM public.clinic_floor f
         WHERE f.clinic_id = NEW.clinic_id
           AND f.location_id = NEW.location_id
           AND f.name = NEW.floor;
        IF FOUND THEN
            NEW.floor_id := selected_floor.id;
        END IF;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_sync_clinic_room_floor ON public.clinic_room;
CREATE TRIGGER trg_sync_clinic_room_floor
    BEFORE INSERT OR UPDATE OF floor, floor_id, clinic_id, location_id
    ON public.clinic_room
    FOR EACH ROW EXECUTE FUNCTION public.sync_clinic_room_floor();

CREATE OR REPLACE FUNCTION public.sync_clinic_floor_name_to_rooms()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.name IS DISTINCT FROM OLD.name THEN
        UPDATE public.clinic_room
           SET floor = NEW.name,
               updated_at = now()
         WHERE floor_id = NEW.id;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_sync_clinic_floor_name ON public.clinic_floor;
CREATE TRIGGER trg_sync_clinic_floor_name
    AFTER UPDATE OF name ON public.clinic_floor
    FOR EACH ROW EXECUTE FUNCTION public.sync_clinic_floor_name_to_rooms();

-- Hai hàm chỉ dành cho trigger. PostgreSQL mặc định cho PUBLIC quyền EXECUTE;
-- thu hồi để chúng không trở thành API ghi dữ liệu ngoài ý muốn.
REVOKE ALL ON FUNCTION public.sync_clinic_room_floor()
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sync_clinic_floor_name_to_rooms()
    FROM PUBLIC, anon, authenticated;

ALTER TABLE public.clinic_floor ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.clinic_floor FROM anon, authenticated;
GRANT ALL ON public.clinic_floor TO service_role;

DO $$
BEGIN
    IF to_regprocedure('public.notify_row_change()') IS NOT NULL THEN
        EXECUTE 'DROP TRIGGER IF EXISTS trg_notify_clinic_floor ON public.clinic_floor';
        EXECUTE 'CREATE TRIGGER trg_notify_clinic_floor '
                'AFTER INSERT OR UPDATE OR DELETE ON public.clinic_floor '
                'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()';
    END IF;
END
$$;

NOTIFY pgrst, 'reload schema';
