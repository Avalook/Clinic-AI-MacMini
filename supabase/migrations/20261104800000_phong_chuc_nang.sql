-- CHỨC NĂNG GẮN VỚI PHÒNG — "đứng đâu làm việc đó" (Tuyền 04/11/2026).
--
-- Trước: phòng → khối mở cho người xếp lịch nằm trong `quyen_theo_lich_bang()`
-- (khớp TIỀN TỐ mã việc của phòng) — bảng ẩn, không màn nào sửa. Lỗi thấy được:
-- Thu ngân tầng 2/3 (LUOTKHAM-14) chỉ được Tiếp đón, không có thu tiền.
--
-- 1. `phong_chuc_nang`: chức năng tại chỗ của TỪNG phòng, sửa được trên màn Cấu
--    trúc phòng khám. GIEO SẴN đúng bằng bảng tra tiền tố × việc của phòng hôm
--    nay, nên ngày đầu quyền y hệt (test so hai cách).
-- 2. `v_quyen_thuc_te` đọc bảng mới thay bảng tra.
-- 3. Phòng gắn thêm việc / bật "phòng đối tác" → tick sẵn chức năng mặc định của
--    việc ấy (như bảng tra cũ tự làm); bỏ tick sau đó vẫn giữ. Gỡ việc KHÔNG tự
--    bỏ tick (khác bảng tra cũ) — bỏ là việc của người quản lý trên màn.

-- ── 1. Chức năng mặc định của một việc (bảng tra cũ, khớp tiền tố DÀI NHẤT) ──
CREATE OR REPLACE FUNCTION public.chuc_nang_mac_dinh_cua_viec(p_node_code text)
RETURNS TABLE (work_pack text, theo_phong boolean)
LANGUAGE sql
STABLE
AS $fn$
    WITH khop AS (
        SELECT b.tien_to
          FROM (SELECT DISTINCT tien_to FROM public.quyen_theo_lich_bang()) b
         WHERE p_node_code LIKE b.tien_to || '%'
         ORDER BY length(b.tien_to) DESC
         LIMIT 1
    )
    SELECT DISTINCT b.work_pack, b.theo_phong
      FROM khop k
      JOIN public.quyen_theo_lich_bang() b ON b.tien_to = k.tien_to
$fn$;

COMMENT ON FUNCTION public.chuc_nang_mac_dinh_cua_viec(text) IS
'Chức năng tick sẵn khi phòng gắn việc này (bảng tra tiền tố cũ, 04/11/2026).';

-- ── 2. Bảng chức năng của phòng ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.phong_chuc_nang (
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    room_id     uuid NOT NULL REFERENCES public.clinic_room (id) ON DELETE CASCADE,
    work_pack   text NOT NULL REFERENCES public.work_pack (ma),
    -- true = chỉ làm được ở ĐÚNG phòng này (Thực hiện dịch vụ); false = đứng
    -- phòng này hôm nay thì có khối ấy toàn phòng khám (như bảng tra cũ).
    theo_phong  boolean NOT NULL DEFAULT false,
    tao_luc     timestamptz NOT NULL DEFAULT now(),
    tao_boi     uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    PRIMARY KEY (room_id, work_pack)
);

CREATE INDEX IF NOT EXISTS ix_phong_chuc_nang_clinic
    ON public.phong_chuc_nang (clinic_id);

COMMENT ON TABLE public.phong_chuc_nang IS
'Chức năng tại chỗ của phòng: ai xếp lịch đứng phòng này hôm nay thì có các khối này (04/11/2026). Sửa ở Cấu trúc phòng khám.';

ALTER TABLE public.phong_chuc_nang ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS phong_chuc_nang_select_own_clinic ON public.phong_chuc_nang;
CREATE POLICY phong_chuc_nang_select_own_clinic ON public.phong_chuc_nang
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.phong_chuc_nang TO service_role;

-- Gieo: mọi phòng (kể cả đang tắt — bật lại thì như cũ) × việc của phòng.
INSERT INTO public.phong_chuc_nang (clinic_id, room_id, work_pack, theo_phong)
SELECT DISTINCT rn.clinic_id, rn.room_id, m.work_pack, m.theo_phong
  FROM public.clinic_room_node rn
  JOIN public.clinic_room r ON r.id = rn.room_id AND r.clinic_id = rn.clinic_id
 CROSS JOIN LATERAL public.chuc_nang_mac_dinh_cua_viec(rn.node_code) m
ON CONFLICT (room_id, work_pack) DO NOTHING;

INSERT INTO public.phong_chuc_nang (clinic_id, room_id, work_pack, theo_phong)
SELECT r.clinic_id, r.id, 'doi_tac', false
  FROM public.clinic_room r
 WHERE r.la_doi_tac
ON CONFLICT (room_id, work_pack) DO NOTHING;

-- ── 3. Tick sẵn khi phòng gắn việc mới / thành phòng đối tác ────────────────
CREATE OR REPLACE FUNCTION public.phong_chuc_nang_tick_san_viec()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    INSERT INTO public.phong_chuc_nang (clinic_id, room_id, work_pack, theo_phong)
    SELECT NEW.clinic_id, NEW.room_id, m.work_pack, m.theo_phong
      FROM public.chuc_nang_mac_dinh_cua_viec(NEW.node_code) m
    ON CONFLICT (room_id, work_pack) DO NOTHING;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_phong_chuc_nang_tick_san_viec ON public.clinic_room_node;
CREATE TRIGGER trg_phong_chuc_nang_tick_san_viec
    AFTER INSERT ON public.clinic_room_node
    FOR EACH ROW EXECUTE FUNCTION public.phong_chuc_nang_tick_san_viec();

CREATE OR REPLACE FUNCTION public.phong_chuc_nang_tick_san_doi_tac()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    IF NEW.la_doi_tac AND (TG_OP = 'INSERT' OR NOT OLD.la_doi_tac) THEN
        INSERT INTO public.phong_chuc_nang (clinic_id, room_id, work_pack, theo_phong)
        VALUES (NEW.clinic_id, NEW.id, 'doi_tac', false)
        ON CONFLICT (room_id, work_pack) DO NOTHING;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_phong_chuc_nang_tick_san_doi_tac ON public.clinic_room;
CREATE TRIGGER trg_phong_chuc_nang_tick_san_doi_tac
    AFTER INSERT OR UPDATE OF la_doi_tac ON public.clinic_room
    FOR EACH ROW EXECUTE FUNCTION public.phong_chuc_nang_tick_san_doi_tac();

-- ── 4. Quyền thực tế đọc bảng mới ───────────────────────────────────────────
-- Giữ nguyên mọi nhánh khác của bản 20260929000001 (đã cấp, trưởng ca, có ca
-- thì xem lịch); chỉ nhánh "phòng có việc" + "phòng đối tác" đổi sang bảng.
CREATE OR REPLACE VIEW public.v_quyen_thuc_te AS
WITH lich_hom_nay AS (
    SELECT w.clinic_id, w.staff_id, w.station
      FROM public.work_roster w
     WHERE w.staff_id IS NOT NULL
       AND w.status <> 'REJECTED'
       AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
), phong_hom_nay AS (
    SELECT DISTINCT l.clinic_id, l.staff_id, r.id AS room_id
      FROM lich_hom_nay l
      JOIN public.vi_tri_lam_viec v
        ON v.clinic_id = l.clinic_id AND v.code = l.station
       AND v.is_active AND v.room_id IS NOT NULL
      JOIN public.clinic_room r
        ON r.id = v.room_id AND r.clinic_id = v.clinic_id AND r.is_active
)
SELECT q.clinic_id, q.staff_id, q.capability, q.work_pack, q.scope_type, q.scope_id
  FROM public.v_quyen_hieu_luc q
UNION
SELECT l.clinic_id, l.staff_id, c.ma AS capability, c.work_pack,
       CASE WHEN l.theo_phong THEN 'ROOM' ELSE 'CLINIC' END AS scope_type,
       CASE WHEN l.theo_phong THEN l.room_id END AS scope_id
  FROM (
        -- Chức năng của phòng đứng hôm nay.
        SELECT DISTINCT p.clinic_id, p.staff_id, p.room_id, f.work_pack,
               f.theo_phong
          FROM phong_hom_nay p
          JOIN public.phong_chuc_nang f
            ON f.room_id = p.room_id AND f.clinic_id = p.clinic_id
        UNION
        -- Vị trí không gắn phòng (trưởng ca).
        SELECT DISTINCT l.clinic_id, l.staff_id, NULL::uuid, b.work_pack, false
          FROM lich_hom_nay l
          JOIN public.vi_tri_lam_viec v
            ON v.clinic_id = l.clinic_id AND v.code = l.station AND v.is_active
          JOIN public.quyen_theo_vi_tri_bang() b ON b.ma_vi_tri = l.station
        UNION
        -- Có ca hôm nay thì xem được Lịch làm việc.
        SELECT DISTINCT l.clinic_id, l.staff_id, NULL::uuid, 'lich_lam_viec', false
          FROM lich_hom_nay l
       ) l
  JOIN public.capability c ON c.work_pack = l.work_pack;

COMMENT ON VIEW public.v_quyen_thuc_te IS
'Quyền thực tế = quyền đã cấp ∪ quyền theo lịch hôm nay (đứng phòng = chức năng của phòng ấy trong phong_chuc_nang, 04/11/2026; vị trí trưởng ca = Điều phối; có ca = xem lịch). Cửa hỏi quyền đọc view này.';

GRANT SELECT ON public.v_quyen_thuc_te TO authenticated, service_role;
