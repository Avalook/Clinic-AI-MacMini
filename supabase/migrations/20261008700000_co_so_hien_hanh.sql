-- MỞ CƠ SỞ THỨ HAI (Hào Nam, 08/10/2026): phòng của một lượt PHẢI cùng cơ sở
-- với lượt.
--
-- Vì sao ở Postgres: hai chỗ chọn phòng theo node của CẢ phòng khám, không lọc
-- cơ sở — `place_visit_at_first_station` (check-in → trạm đầu) và
-- `move_visit_to_station` (điều phối gọi thẳng API). Có hai cơ sở cùng node là
-- khách Hào Nam bị đặt vào phòng Kim Ngưu — kiểu "cơ sở lạc" 24/09, lần này mỗi
-- ngày. Sửa từng chỗ gọi thì chỗ thứ ba mai lại lọt; chốt ở bảng thì mọi đường
-- ghi phòng (hàm SQL, service, gọi tay) đều đi qua (SO-LUAT Phần 6).
--
-- Cơ sở của lượt = coalesce(visit.location_id, appointment.location_id) — cùng
-- luật `co_so_cua_luot` (service_routing_service.py). Không biết cơ sở của lượt
-- hoặc của phòng thì KHÔNG chặn: dữ liệu cũ / fixture thiếu cột không được thành
-- lỗi cứng giữa quầy.

-- ── 1. Cơ sở của một lượt — một chỗ duy nhất trong SQL ────────────────────────
CREATE OR REPLACE FUNCTION public.co_so_cua_luot(p_visit_id uuid)
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path TO 'pg_catalog', 'public'
AS $$
    SELECT coalesce(v.location_id, a.location_id)
      FROM public.visit v
      LEFT JOIN public.appointment a ON a.id = v.appointment_id
     WHERE v.visit_id = p_visit_id
$$;

-- ── 2. Chốt: phòng khác cơ sở với lượt → từ chối ──────────────────────────────
CREATE OR REPLACE FUNCTION public.chan_phong_khac_co_so()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_room uuid;
    v_co_so_phong uuid;
    v_co_so_luot uuid;
BEGIN
    IF TG_TABLE_NAME = 'visit' THEN
        v_room := NEW.current_room_id;
        v_co_so_luot := coalesce(
            NEW.location_id,
            (SELECT a.location_id FROM public.appointment a
              WHERE a.id = NEW.appointment_id));
    ELSE
        v_room := NEW.room_id;
        v_co_so_luot := public.co_so_cua_luot(NEW.visit_id);
    END IF;

    IF v_room IS NULL OR v_co_so_luot IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT location_id INTO v_co_so_phong
      FROM public.clinic_room WHERE id = v_room;

    IF v_co_so_phong IS NOT NULL AND v_co_so_phong <> v_co_so_luot THEN
        RAISE EXCEPTION
            'Phòng này thuộc cơ sở khác với lượt khám — chọn phòng ở đúng cơ sở của khách'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_visit_phong_cung_co_so ON public.visit;
CREATE TRIGGER trg_visit_phong_cung_co_so
    BEFORE INSERT OR UPDATE OF current_room_id, location_id ON public.visit
    FOR EACH ROW EXECUTE FUNCTION public.chan_phong_khac_co_so();

DROP TRIGGER IF EXISTS trg_work_item_phong_cung_co_so ON public.work_item;
CREATE TRIGGER trg_work_item_phong_cung_co_so
    BEFORE INSERT OR UPDATE OF room_id ON public.work_item
    FOR EACH ROW EXECUTE FUNCTION public.chan_phong_khac_co_so();

-- ── 3. Check-in → trạm đầu: chọn phòng ở cơ sở của lượt ──────────────────────
CREATE OR REPLACE FUNCTION public.place_visit_at_first_station(
    p_clinic_id uuid,
    p_visit_id  uuid,
    p_actor     uuid
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_node text;
    v_room uuid;
    v_co_so uuid;
BEGIN
    -- Đã có vị trí thì không đặt lại: check-in lần hai (hoặc một lần bấm nhầm
    -- rồi bấm lại) không được kéo bệnh nhân từ phòng siêu âm về quầy sinh hiệu.
    IF EXISTS (SELECT 1 FROM public.visit
                WHERE visit_id = p_visit_id AND clinic_id = p_clinic_id
                  AND current_node_code IS NOT NULL) THEN
        RETURN NULL;
    END IF;

    v_co_so := public.co_so_cua_luot(p_visit_id);

    SELECT w.node_code, r.id
      INTO v_node, v_room
      FROM public.work_item w
      JOIN public.clinic_room r
        ON r.node_code = w.node_code AND r.clinic_id = w.clinic_id
       AND r.is_active AND r.accepting
       AND (v_co_so IS NULL OR r.location_id = v_co_so)
     WHERE w.clinic_id = p_clinic_id AND w.visit_id = p_visit_id
       AND w.status = 'PENDING'
     ORDER BY r.sort, w.created_at
     LIMIT 1;

    IF v_node IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN public.move_visit_to_station(
        p_clinic_id, p_visit_id, v_node, v_room, p_actor,
        'Tiếp nhận — vào trạm đầu tiên', 'dispatch.checkin');
END
$function$;

REVOKE ALL ON FUNCTION public.place_visit_at_first_station(uuid, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.place_visit_at_first_station(uuid, uuid, uuid)
    TO authenticated, service_role;

-- ── 4. SĐT + tên in trên phiếu theo cơ sở ────────────────────────────────────
-- Phiếu khám / kết quả đã in tên + địa chỉ CƠ SỞ. Hào Nam treo biển pháp nhân
-- khác ("Phòng khám chuyên khoa Phụ sản 4WOMEN"): `ten_in` rỗng = in tên phòng
-- khám như cũ; có giá trị thì phiếu của cơ sở đó in tên này.
ALTER TABLE public.clinic_location ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE public.clinic_location ADD COLUMN IF NOT EXISTS ten_in text;

DO $verify$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_visit_phong_cung_co_so')
       OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_work_item_phong_cung_co_so') THEN
        RAISE EXCEPTION 'thiếu trigger phòng cùng cơ sở';
    END IF;
END
$verify$;
