-- SỬA / XOÁ CHỈ ĐỊNH THOẢI MÁI Ở MỌI LẦN (Tuyền thử staging, chốt 06/10/2026).
--
-- 1. `luot_lan_chi_dinh`: LẦN là thứ máy chủ GIỮ, không phụ thuộc màn. Nút "+"
--    cạnh các tab "Lần 1 · Lần 2" mở lần mới (kể cả chưa tick gì, ra/vào màn
--    vẫn còn). Khoá chính (lượt, lần) — hai máy bấm "+" cùng lúc: hàm
--    `mo_lan_chi_dinh` tuần tự hoá bằng advisory lock, lần rỗng thì dùng lại.
-- 2. Chỉ định vào ĐÚNG lần của tab đang chọn: lệnh đặt
--    `clinicai.lan_chon_<visit>` = số lần; trigger `gan_lan_chi_dinh` dùng số
--    ấy (lệnh đã kiểm lần tồn tại). Không đặt = lần hiện tại (lớn nhất).
-- 3. Bỏ chỉ định ĐANG LÀM / ĐÃ LÀM được (không chặn nữa): sổ ghi thêm phòng
--    và các chỗ chờ bị đóng (`clinicai.so_hang_cho`) để hoàn tác trả đúng
--    trạng thái cũ. Kết quả / phiếu / tệp không bị xoá.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.luot_lan_chi_dinh (
    clinic_id uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id  uuid NOT NULL,
    lan       smallint NOT NULL CHECK (lan BETWEEN 1 AND 999),
    mo_boi    uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    mo_luc    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, visit_id, lan)
);
COMMENT ON TABLE public.luot_lan_chi_dinh IS
'Lần chỉ định đã MỞ của lượt (nút "+", 06/10/2026). Lần của lượt = hợp các lần ở đây với lan_chi_dinh của chỉ định.';
ALTER TABLE public.luot_lan_chi_dinh ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS luot_lan_chi_dinh_select_own_clinic ON public.luot_lan_chi_dinh;
CREATE POLICY luot_lan_chi_dinh_select_own_clinic ON public.luot_lan_chi_dinh
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.luot_lan_chi_dinh TO service_role;

DROP TRIGGER IF EXISTS trg_notify_luot_lan_chi_dinh ON public.luot_lan_chi_dinh;
CREATE TRIGGER trg_notify_luot_lan_chi_dinh
    AFTER INSERT OR UPDATE OR DELETE ON public.luot_lan_chi_dinh
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- Các lần của lượt (đã mở ∪ đã có chỉ định), tăng dần.
CREATE OR REPLACE FUNCTION public.cac_lan_chi_dinh(p_clinic_id uuid, p_visit_id uuid)
RETURNS smallint[]
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT coalesce(array_agg(l ORDER BY l), '{}')::smallint[]
      FROM (SELECT o.lan_chi_dinh AS l FROM public.service_order o
             WHERE o.clinic_id = p_clinic_id AND o.visit_id = p_visit_id
               AND o.lan_chi_dinh IS NOT NULL
            UNION
            SELECT m.lan FROM public.luot_lan_chi_dinh m
             WHERE m.clinic_id = p_clinic_id AND m.visit_id = p_visit_id) x;
$$;

CREATE OR REPLACE FUNCTION public.lan_chi_dinh_cua_luot(p_clinic_id uuid, p_visit_id uuid)
RETURNS TABLE (hien_tai smallint, ke_tiep smallint, mo_moi_duoc boolean)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH ht AS (
        SELECT (SELECT max(x) FROM unnest(public.cac_lan_chi_dinh(p_clinic_id,
                                                                p_visit_id)) x) AS lan
    ), song AS (
        SELECT EXISTS (
            SELECT 1 FROM public.service_order o, ht
             WHERE o.clinic_id = p_clinic_id AND o.visit_id = p_visit_id
               AND o.lan_chi_dinh = ht.lan
               AND o.exec_status NOT IN ('cancelled', 'draft')
               AND coalesce(o.execution_status, '') <> 'CANCELLED') AS co
    )
    SELECT ht.lan::smallint,
           (CASE WHEN ht.lan IS NULL THEN 1
                 WHEN song.co THEN ht.lan + 1
                 ELSE ht.lan END)::smallint,
           coalesce(song.co, false)
      FROM ht, song;
$$;

-- Nút "+": mở lần kế (lần lớn nhất đang rỗng thì dùng lại). Trả số lần.
CREATE OR REPLACE FUNCTION public.mo_lan_chi_dinh(
    p_clinic_id uuid, p_visit_id uuid, p_boi uuid
)
RETURNS smallint
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    kt smallint;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('lan_chi_dinh:' || p_visit_id::text));
    SELECT l.ke_tiep INTO kt FROM public.lan_chi_dinh_cua_luot(p_clinic_id, p_visit_id) l;
    -- Chưa có lần nào: lần 1 cũng ghi lại (để lần 2 mở được ngay sau đó).
    IF NOT EXISTS (SELECT 1 FROM public.luot_lan_chi_dinh m
                    WHERE m.clinic_id = p_clinic_id AND m.visit_id = p_visit_id) THEN
        INSERT INTO public.luot_lan_chi_dinh (clinic_id, visit_id, lan, mo_boi)
        SELECT p_clinic_id, p_visit_id, x, p_boi
          FROM unnest(public.cac_lan_chi_dinh(p_clinic_id, p_visit_id)) x
        ON CONFLICT DO NOTHING;
    END IF;
    INSERT INTO public.luot_lan_chi_dinh (clinic_id, visit_id, lan, mo_boi)
    VALUES (p_clinic_id, p_visit_id, kt, p_boi)
    ON CONFLICT DO NOTHING;
    RETURN kt;
END;
$$;

CREATE OR REPLACE FUNCTION public.gan_lan_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  khoa text;
  lan text;
  thay text;
  chon text;
  ht smallint;
  kt smallint;
BEGIN
  IF NEW.mang_tu_visit_id IS NOT NULL OR NEW.nguon_lam_them IS NOT NULL THEN
    NEW.lan_chi_dinh := NULL;
    RETURN NEW;
  END IF;
  IF NEW.lan_chi_dinh IS NOT NULL OR NEW.visit_id IS NULL OR NEW.exec_status IN ('draft', 'cancelled') THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.exec_status IS DISTINCT FROM 'draft' THEN
    RETURN NEW;
  END IF;
  khoa := 'clinicai.lan_' || replace(NEW.visit_id::text, '-', '');
  lan := nullif(current_setting(khoa, true), '');
  IF lan IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext('lan_chi_dinh:' || NEW.visit_id::text));
    -- Tab đang chọn (06/10/2026) — lệnh đã kiểm lần tồn tại.
    chon := nullif(current_setting(
        'clinicai.lan_chon_' || replace(NEW.visit_id::text, '-', ''), true), '');
    IF chon IS NOT NULL AND chon ~ '^[0-9]{1,3}$' AND chon::int >= 1 THEN
      lan := chon;
    ELSE
      SELECT l.hien_tai, l.ke_tiep INTO ht, kt
        FROM public.lan_chi_dinh_cua_luot(NEW.clinic_id, NEW.visit_id) l;
      thay := nullif(current_setting(
          'clinicai.lan_moi_' || replace(NEW.visit_id::text, '-', ''), true), '');
      IF thay IS NOT NULL AND thay ~ '^[0-9]{1,4}$'
         AND coalesce(ht, 0) <= thay::int THEN
        lan := kt::text;
      ELSE
        lan := coalesce(ht, 1)::text;
      END IF;
    END IF;
    PERFORM set_config(khoa, lan, true);
  END IF;
  NEW.lan_chi_dinh := lan::smallint;
  RETURN NEW;
END;
$$;


-- ── Sổ: ghi thêm phòng + chỗ chờ bị đóng khi BỎ ───────────────────────────
CREATE OR REPLACE FUNCTION public.ghi_so_sua_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    hd          text;
    mac_dinh    uuid;
    ai          record;
    nc          record;
    v_da_thu    bigint := 0;
    v_da_hoan   bigint := 0;
    goc         uuid;
    bo_id       uuid;
    v_ly_do     text := nullif(btrim(current_setting('clinicai.so_ly_do', true)), '');
BEGIN
    IF coalesce(current_setting('clinicai.so_bo_qua', true), '') = 'on' THEN
        RETURN NULL;
    END IF;
    IF TG_OP = 'INSERT' THEN
        -- Nhập hồ sơ cũ (performed / not_performed) và nháp không phải "thêm".
        IF NEW.exec_status IN ('draft', 'cancelled', 'performed', 'not_performed') THEN
            RETURN NULL;
        END IF;
        hd := 'THEM';
        mac_dinh := coalesce(NEW.authorized_by, NEW.recorded_by);
    ELSIF OLD.exec_status IS DISTINCT FROM NEW.exec_status THEN
        IF NEW.exec_status = 'cancelled' AND OLD.exec_status <> 'draft' THEN
            hd := 'BO';
            mac_dinh := NEW.cancelled_by;
        ELSIF OLD.exec_status = 'cancelled' THEN
            hd := 'HOAN_TAC';
            mac_dinh := NULL;
        ELSIF OLD.exec_status = 'draft' THEN
            hd := 'THEM';   -- nháp được duyệt = chỉ định thật từ lúc này
            mac_dinh := coalesce(NEW.authorized_by, NEW.recorded_by);
        ELSE
            RETURN NULL;
        END IF;
    ELSE
        RETURN NULL;
    END IF;

    SELECT * INTO ai FROM public.so_chi_dinh_nguoi(NEW.clinic_id, mac_dinh);
    SELECT * INTO nc FROM public.so_chi_dinh_ngu_canh(NEW.clinic_id, NEW.visit_id);
    goc := coalesce(NEW.authorized_by, NEW.recorded_by);

    IF hd = 'HOAN_TAC' THEN
        bo_id := nullif(current_setting('clinicai.so_hoan_tac_cua', true), '')::uuid;
        IF bo_id IS NULL THEN
            SELECT s.id INTO bo_id FROM public.so_sua_chi_dinh s
             WHERE s.service_order_id = NEW.id AND s.hanh_dong = 'BO'
               AND s.hoan_tac_luc IS NULL
             ORDER BY s.stt DESC LIMIT 1;
        END IF;
        IF bo_id IS NULL THEN
            RETURN NULL;   -- huỷ từ trước khi có sổ: không có dòng BỎ để trỏ về
        END IF;
        UPDATE public.so_sua_chi_dinh
           SET hoan_tac_boi_id = ai.staff_id,
               hoan_tac_boi_ten = coalesce(ai.ten, 'Không rõ'),
               hoan_tac_luc = now()
         WHERE id = bo_id AND hoan_tac_luc IS NULL;
    END IF;

    IF hd = 'BO' THEN
        SELECT t.da_thu, t.da_hoan INTO v_da_thu, v_da_hoan
          FROM public.tien_cua_chi_dinh(NEW.clinic_id, NEW.id) t;
    END IF;

    INSERT INTO public.so_sua_chi_dinh
        (clinic_id, visit_id, nhom, hanh_dong, service_order_id, ma_muc, ten_muc,
         chi_tiet, boi_staff_id, boi_ten, boi_vai, phong_kham_ten,
         bac_si_chinh_id, bac_si_chinh_ten, chi_dinh_goc_boi_id,
         chi_dinh_goc_boi_ten, da_thu, tien_thua, ly_do, hoan_tac_cua)
    VALUES
        (NEW.clinic_id, NEW.visit_id,
         public.nhom_chi_dinh(NEW.clinic_id, NEW.service_code, NEW.node_code),
         hd, NEW.id, NEW.service_code, NEW.service_name,
         CASE WHEN hd = 'BO' THEN jsonb_build_object('truoc', jsonb_build_object(
                  'exec_status', OLD.exec_status,
                  'execution_status', OLD.execution_status,
                  'selection_status', OLD.selection_status,
                  'routing_status', OLD.routing_status,
                  'room_id', OLD.room_id),
                  -- Chỗ chờ ở phòng lệnh bỏ sắp đóng (06/10/2026): hoàn tác
                  -- trả lại đúng trạng thái, kể cả đang làm.
                  'hang_cho', coalesce(nullif(current_setting('clinicai.so_hang_cho',
                                                              true), '')::jsonb,
                                       '[]'::jsonb))
              ELSE '{}'::jsonb END,
         ai.staff_id, ai.ten, ai.vai, nc.phong_kham_ten,
         nc.bac_si_chinh_id, nc.bac_si_chinh_ten,
         goc, (SELECT full_name FROM public.staff WHERE id = goc),
         coalesce(v_da_thu, 0),
         least(greatest(coalesce(v_da_thu, 0) - coalesce(v_da_hoan, 0), 0),
               coalesce(v_da_thu, 0)),
         CASE WHEN hd = 'BO' THEN left(coalesce(v_ly_do, NEW.cancel_reason), 500)
              WHEN hd = 'HOAN_TAC' THEN left(v_ly_do, 500)
              ELSE NULL END,
         CASE WHEN hd = 'HOAN_TAC' THEN bo_id ELSE NULL END);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_so_sua_chi_dinh ON public.service_order;
CREATE TRIGGER trg_so_sua_chi_dinh
    AFTER INSERT OR UPDATE OF exec_status ON public.service_order
    FOR EACH ROW EXECUTE FUNCTION public.ghi_so_sua_chi_dinh();


