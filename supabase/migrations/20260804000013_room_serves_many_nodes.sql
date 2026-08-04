-- MỘT PHÒNG PHỤC VỤ NHIỀU BƯỚC — vì cái quyết định chuyên khoa là BÁC SĨ ngồi
-- trong đó, không phải bốn bức tường.
--
-- HIỆN TRẠNG. `clinic_room.node_code` là MỘT cột, nên mỗi phòng chỉ phục vụ
-- đúng một bước. Bốn phòng khám KB01–KB04 đều đang ghim vào `KHAM-PHUKHOA`,
-- trong khi phòng khám có năm chuyên khoa và đã khai đủ năm node:
--
--     KHAM-PHUKHOA · KHAM-SANKHOA · KHAM-NAMKHOA · KHAM-NOITIET
--     KHAM-HIEMMUON-VOSINH
--
-- Hệ quả: một ca Nam khoa hay Nội tiết vẫn bị hệ thống xếp vào bước "khám phụ
-- khoa", và `move_visit_to_station` sẽ TỪ CHỐI chuyển bệnh nhân Nam khoa vào
-- KB02 vì "Phòng đã chọn không phục vụ bước KHAM-NAMKHOA".
--
-- VÌ SAO LÀ BẢNG NỐI, KHÔNG PHẢI MỘT CỘT `text[]`.
--
-- Mảng thì gọn hơn nhưng không khoá ngoại được. Gõ sai một mã node trong mảng
-- không có gì báo — nó chỉ lặng lẽ khiến không phòng nào phục vụ bước đó, và
-- Trưởng ca sẽ thấy danh sách phòng trống rỗng mà không hiểu vì sao. Bảng nối
-- khoá ngoại tới `node_definition (clinic_id, code)`, nên mã sai bị chặn ngay
-- lúc khai.
--
-- Nó cũng đúng về mặt tenant: phòng khám khác khai bộ node khác, và khoá ngoại
-- đi kèm `clinic_id` nên không ai mượn được node của phòng khám bên cạnh.

CREATE TABLE IF NOT EXISTS public.clinic_room_node (
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    room_id   uuid NOT NULL REFERENCES public.clinic_room(id) ON DELETE CASCADE,
    node_code text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (room_id, node_code),
    CONSTRAINT clinic_room_node_node_fk
        FOREIGN KEY (clinic_id, node_code)
        REFERENCES public.node_definition (clinic_id, code) ON DELETE RESTRICT
);

COMMENT ON TABLE public.clinic_room_node IS
    'Phòng này phục vụ được những bước nào. Nhiều-nhiều, vì chuyên khoa do bác '
    'sĩ ngồi trong phòng quyết định chứ không phải do bốn bức tường.';

CREATE INDEX IF NOT EXISTS idx_clinic_room_node_lookup
    ON public.clinic_room_node (clinic_id, node_code);

-- ---------------------------------------------------------------------------
-- Nạp từ dữ liệu đang có
-- ---------------------------------------------------------------------------
-- Mọi phòng giữ đúng bước nó đang phục vụ — không phòng nào mất khả năng cũ.

INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)
SELECT r.clinic_id, r.id, r.node_code
  FROM public.clinic_room r
 WHERE r.node_code IS NOT NULL
ON CONFLICT DO NOTHING;

-- BỐN PHÒNG KHÁM PHỤC VỤ CẢ NĂM CHUYÊN KHOA.
--
-- KB01–KB04 là bốn phòng khám giống nhau: một cái bàn, một ghế, một giường
-- khám. Chuyên khoa đến từ bác sĩ được xếp vào đó — báo cáo onsite cho thấy
-- BS Thành và các bác sĩ phụ dùng chung dãy phòng này.
--
-- Nếu sau này có phòng cần thiết bị riêng (soi cổ tử cung, ghế khám nam khoa),
-- quản lý phòng khám chỉ việc bỏ bớt dòng ở đây — không ai phải sửa code.

INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)
SELECT r.clinic_id, r.id, n.code
  FROM public.clinic_room r
 CROSS JOIN LATERAL (
     SELECT code FROM public.node_definition
      WHERE clinic_id = r.clinic_id AND code LIKE 'KHAM-%'
 ) n
 WHERE r.code IN ('KB01', 'KB02', 'KB03', 'KB04')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- `clinic_room.node_code` từ nay là BƯỚC CHÍNH, không phải bước duy nhất
-- ---------------------------------------------------------------------------
-- Vẫn giữ cột, vì bảng điều phối cần một bước để xếp nhóm và hiện tiêu đề —
-- "phòng này thuộc khu nào". Nhưng nó phải nằm TRONG danh sách bước mà phòng
-- phục vụ, nếu không hai chỗ sẽ nói hai điều khác nhau và không ai biết chỗ
-- nào đúng.

COMMENT ON COLUMN public.clinic_room.node_code IS
    'Bước CHÍNH của phòng — dùng để xếp nhóm trên bảng điều phối. Danh sách '
    'bước phòng phục vụ nằm ở clinic_room_node; cột này phải là một trong số '
    'đó (trigger clinic_room_primary_node_is_served).';

CREATE OR REPLACE FUNCTION public.clinic_room_primary_node_is_served()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    IF NEW.node_code IS NULL THEN
        RETURN NEW;
    END IF;
    -- Lúc INSERT thì bảng nối chưa có dòng nào cho phòng này (chưa có id để
    -- tham chiếu), nên chỉ kiểm khi bảng nối ĐÃ có dữ liệu cho phòng đó.
    IF EXISTS (SELECT 1 FROM public.clinic_room_node WHERE room_id = NEW.id)
       AND NOT EXISTS (
           SELECT 1 FROM public.clinic_room_node
            WHERE room_id = NEW.id AND node_code = NEW.node_code
       )
    THEN
        RAISE EXCEPTION
            'Phòng % lấy bước chính là % nhưng không phục vụ bước đó',
            NEW.code, NEW.node_code
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_clinic_room_primary_node ON public.clinic_room;
CREATE TRIGGER trg_clinic_room_primary_node
    BEFORE INSERT OR UPDATE OF node_code ON public.clinic_room
    FOR EACH ROW EXECUTE FUNCTION public.clinic_room_primary_node_is_served();

-- ---------------------------------------------------------------------------
-- Chuyển phòng: kiểm theo DANH SÁCH bước, không theo một cột
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.move_visit_to_station(p_clinic_id uuid, p_visit_id uuid, p_node_code text, p_room_id uuid, p_actor uuid, p_reason text DEFAULT NULL::text, p_event_type text DEFAULT 'dispatch.moved'::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_old_node text;
    v_old_room uuid;
    v_node_version uuid;
    v_patient uuid;
    v_appt uuid;
    v_item uuid;
BEGIN
    SELECT current_node_code, current_room_id, clinic_patient_id, appointment_id
      INTO v_old_node, v_old_room, v_patient, v_appt
      FROM public.visit
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy lượt khám % ở phòng khám này', p_visit_id;
    END IF;

    -- ĐỔI DUY NHẤT Ở ĐÂY: đọc bảng nối clinic_room_node thay vì cột đơn
    -- r.node_code. Một phòng khám phục vụ được cả năm chuyên khoa, và trước
    -- thay đổi này việc chuyển một ca Nam khoa vào KB02 bị từ chối vì phòng
    -- "chỉ phục vụ" KHAM-PHUKHOA.
    --
    -- Phần còn lại của hàm giữ NGUYÊN VĂN bản đang chạy — nó có những chi tiết
    -- không nhìn ra khi viết lại từ đầu (giữ current_node_since khi ở lại cùng
    -- bước, trả về work_item_id, v.v.).
    IF p_room_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.clinic_room r
          JOIN public.clinic_room_node rn ON rn.room_id = r.id
         WHERE r.id = p_room_id AND r.clinic_id = p_clinic_id
           AND rn.node_code = p_node_code AND r.is_active
    ) THEN
        RAISE EXCEPTION 'Phòng đã chọn không phục vụ bước %', p_node_code;
    END IF;

    IF p_node_code IS DISTINCT FROM v_old_node THEN
        -- CHỈ đóng bước đang rời. Không đụng tới các bước chưa tới lượt —
        -- chúng là việc còn phải làm, không phải việc đã xong.
        IF v_old_node IS NOT NULL THEN
            UPDATE public.work_item
               SET status = 'COMPLETED', finished_at = now(), updated_at = now()
             WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
               AND node_code = v_old_node
               AND status IN ('PENDING', 'IN_PROGRESS');
        END IF;

        SELECT v.id INTO v_node_version
          FROM public.node_definition_version v
          JOIN public.node_definition n ON n.id = v.node_definition_id
         WHERE n.code = p_node_code AND n.clinic_id = p_clinic_id
         ORDER BY v.version DESC LIMIT 1;
        IF v_node_version IS NULL THEN
            RAISE EXCEPTION 'Bước % chưa được khai trong node_definition',
                p_node_code;
        END IF;

        -- IN_PROGRESS, không phải PENDING: bệnh nhân ĐANG Ở đây. Bảng tải từng
        -- phòng đếm "đang phục vụ" bằng IN_PROGRESS và "đang chờ" bằng PENDING;
        -- để nguyên PENDING thì mọi phòng vĩnh viễn hiện "đang phục vụ 0".
        INSERT INTO public.work_item
            (clinic_id, node_code, node_version_id, clinic_patient_id, visit_id,
             appointment_id, status, room_id, started_at, finished_at, payload)
        VALUES (p_clinic_id, p_node_code, v_node_version, v_patient, p_visit_id,
                v_appt, 'IN_PROGRESS', p_room_id, now(), NULL,
                jsonb_build_object('moved_from', v_old_node, 'reason', p_reason))
        ON CONFLICT (clinic_id, visit_id, node_code)
            WHERE visit_id IS NOT NULL AND status <> 'CANCELLED'
        DO UPDATE SET status = 'IN_PROGRESS',
                      room_id = EXCLUDED.room_id,
                      started_at = coalesce(work_item.started_at, now()),
                      finished_at = NULL,
                      updated_at = now()
        RETURNING id INTO v_item;
    ELSE
        UPDATE public.work_item
           SET room_id = p_room_id, updated_at = now()
         WHERE clinic_id = p_clinic_id AND visit_id = p_visit_id
           AND node_code = p_node_code
           AND status IN ('PENDING', 'IN_PROGRESS')
        RETURNING id INTO v_item;

        IF v_item IS NULL THEN
            RAISE EXCEPTION
                'Lượt khám không có bước % nào đang mở để đổi phòng', p_node_code;
        END IF;
    END IF;

    UPDATE public.visit
       SET previous_node_code = CASE WHEN p_node_code IS DISTINCT FROM v_old_node
                                     THEN v_old_node ELSE previous_node_code END,
           current_node_code   = p_node_code,
           current_room_id     = p_room_id,
           -- Đổi phòng KHÔNG làm mới đồng hồ chờ: người đã đợi 20 phút ở SA1
           -- sang SA2 vẫn là người đã đợi 20 phút.
           current_node_since  = CASE WHEN p_node_code IS DISTINCT FROM v_old_node
                                      THEN now() ELSE current_node_since END,
           status = CASE WHEN status = 'OPEN' THEN 'IN_PROGRESS' ELSE status END,
           updated_at = now()
     WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id;

    INSERT INTO public.event_log
        (clinic_id, event_type, aggregate_type, aggregate_id, payload, metadata,
         source, event_published)
    VALUES (p_clinic_id, p_event_type, 'visit', p_visit_id,
            jsonb_build_object(
                'from_node', v_old_node, 'to_node', p_node_code,
                'from_room', v_old_room, 'to_room', p_room_id,
                'reason', p_reason, 'work_item_id', v_item),
            jsonb_build_object('actor_auth_user_id', p_actor),
            'api:dispatch', FALSE);

    RETURN v_item;
END
$function$;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.clinic_room_node ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clinic_room_node_select ON public.clinic_room_node;
CREATE POLICY clinic_room_node_select ON public.clinic_room_node
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids()));

-- Khai phòng phục vụ bước nào là việc CẤU HÌNH, không phải việc vận hành hằng
-- ngày — nên chỉ quản lý, không mở cho Trưởng ca.
DROP POLICY IF EXISTS clinic_room_node_write ON public.clinic_room_node;
CREATE POLICY clinic_room_node_write ON public.clinic_room_node
    FOR ALL TO authenticated
    USING (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT'])))
    WITH CHECK (clinic_id IN (SELECT public.current_clinic_ids_for_roles(
        ARRAY['MANAGEMENT'])));

GRANT SELECT ON public.clinic_room_node TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.clinic_room_node TO authenticated;

-- Xoá cơ sở: cột location_id nay NOT NULL nên `ON DELETE SET NULL` sẽ ném lỗi
-- not-null thay vì nói thẳng "còn phòng đang thuộc cơ sở này". Đổi cho câu lỗi
-- khớp với ý định.
ALTER TABLE public.clinic_room
    DROP CONSTRAINT IF EXISTS clinic_room_location_id_fkey;
ALTER TABLE public.clinic_room
    ADD CONSTRAINT clinic_room_location_id_fkey
    FOREIGN KEY (location_id) REFERENCES public.clinic_location(id)
    ON DELETE RESTRICT;

DO $verify$
DECLARE
    kb int;
    tong int;
BEGIN
    SELECT count(*) INTO kb FROM public.clinic_room_node rn
      JOIN public.clinic_room r ON r.id = rn.room_id
     WHERE r.code = 'KB01';
    SELECT count(*) INTO tong FROM public.clinic_room_node;
    IF kb < 5 THEN
        RAISE EXCEPTION 'KB01 mới phục vụ % bước, mong đợi ít nhất 5', kb;
    END IF;
    RAISE NOTICE 'phòng ↔ bước: % cặp; KB01 phục vụ % chuyên khoa', tong, kb;
END
$verify$;
