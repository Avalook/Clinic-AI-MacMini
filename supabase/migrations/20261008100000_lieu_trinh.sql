-- LIỆU TRÌNH ĐIỀU TRỊ NHIỀU BUỔI — mô hình (B1, docs/KE-HOACH-LIEU-TRINH.md Phần B,
-- Tuyền chốt Q1–Q5 ngày 08/10/2026).
--
-- Liệu trình = SỔ KẾ HOẠCH (bao nhiêu buổi, đơn giá chốt, ghi chú tần suất) +
-- (B2) sổ tiền trả trước. MỖI BUỔI vẫn là MỘT `service_order` thường — không tạo
-- trước N chỉ định "ma" (sẽ hiện ở Sắp đến mọi phòng, hàng chờ, quầy và bị
-- `mang_sang_luot_moi` bê sang lượt sau).
--
--   lieu_trinh          — kế hoạch của một khách cho MỘT dịch vụ nhóm DIEU_TRI.
--                         `trang_thai` là giá trị SUY RA (trigger), không ai ghi
--                         tay: DUNG khi có `dung_luc`; còn lại DANG_LAM khi khách
--                         đã nhận (CSKH đăng ký / có buổi khách chọn / đã làm /
--                         đã trả trước), XONG khi số buổi đã làm ≥ số buổi kế
--                         hoạch, không thì DE_XUAT.
--   lieu_trinh_lich_su  — chỉ-thêm: mỗi lần kế hoạch đổi (người sửa hay hệ thống
--                         tự thêm buổi / tự đổi trạng thái) một dòng bản cũ → mới.
--   lieu_trinh_buoi     — nối chỉ định ↔ liệu trình (số buổi, buổi này dùng tiền
--                         trả trước chưa). Gỡ = đóng dấu `go_luc`, không xoá.
--
-- GẮN BUỔI Ở MỘT CHỖ (Postgres): có ≥6 đường tạo chỉ định (bàn khám, quầy, lượt
-- đặt lịch Điều trị, hoàn tác bỏ, chuyển lượt thật…) → trigger trên
-- `service_order`, cùng giao dịch với lệnh tạo / đổi trạng thái:
--   * thêm chỉ định còn sống mà khách có ĐÚNG MỘT liệu trình DANG_LAM cùng dịch vụ
--     → gắn buổi kế (2 liệu trình cùng dịch vụ → không gắn, thẻ bắt chọn);
--   * chỉ định bị huỷ / không làm / khách không chọn → buổi tự gỡ (trả buổi về);
--   * hoàn tác (sống lại) → gắn lại đúng liệu trình cũ nếu lần gỡ là tự động.
--
-- Bất biến (khoá dòng `lieu_trinh` FOR UPDATE trước mọi thay đổi buổi):
--   * một chỉ định thuộc ≤ 1 liệu trình (chỉ mục duy nhất từng phần);
--   * `buoi_so` không trùng trong các buổi còn sống của một liệu trình;
--   * buổi dùng tiền trả trước ≤ số buổi đã trả (`lieu_trinh_so_buoi_da_tra` —
--     bản B1 luôn 0; B2 thay bằng sổ tiền thật);
--   * số buổi kế hoạch ≥ số buổi đang gắn và ≥ số buổi đã trả;
--   * đơn giá không đổi khi đã có tiền trả trước.
--
-- Chạy lại được.

-- ── 1. Bảng ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lieu_trinh (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL REFERENCES public.patient (clinic_patient_id)
                          ON DELETE RESTRICT,
    service_code      text NOT NULL,
    service_name      text NOT NULL,
    so_buoi           integer NOT NULL CHECK (so_buoi BETWEEN 1 AND 200),
    -- Q2: đơn giá CHỐT lúc tạo = giá bảng giá lúc ấy; đổi bảng giá sau không đụng.
    don_gia           numeric(12, 0) NOT NULL CHECK (don_gia >= 0),
    ghi_chu_lo_trinh  text CHECK (ghi_chu_lo_trinh IS NULL
                                  OR char_length(ghi_chu_lo_trinh) <= 1000),
    trang_thai        text NOT NULL DEFAULT 'DE_XUAT'
                          CHECK (trang_thai IN ('DE_XUAT', 'DANG_LAM', 'XONG', 'DUNG')),
    nguon             text NOT NULL CHECK (nguon IN ('BAC_SI', 'CSKH')),
    nguon_visit_id    uuid,
    nguon_order_id    uuid,
    de_xuat_boi       uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    dang_ky_boi       uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    dang_ky_luc       timestamptz,
    dung_boi          uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    dung_luc          timestamptz,
    ly_do_dung        text CHECK (ly_do_dung IS NULL OR char_length(ly_do_dung) <= 500),
    revision          integer NOT NULL DEFAULT 1,
    -- Nhãn của lần đổi gần nhất (vào lịch sử): TAO, DIEU_CHINH, DANG_KY, DUNG,
    -- MO_LAI, HOAN_TAC, TU_THEM_BUOI, TU_TRANG_THAI (TU_DONG = lệnh "tính lại").
    hanh_dong         text NOT NULL DEFAULT 'TAO',
    sua_boi           uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    sua_luc           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lieu_trinh_clinic_id UNIQUE (clinic_id, id),
    CONSTRAINT lieu_trinh_dung_di_cung CHECK ((trang_thai = 'DUNG') = (dung_luc IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_khach
    ON public.lieu_trinh (clinic_id, clinic_patient_id, service_code);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_dich_vu_trang_thai
    ON public.lieu_trinh (clinic_id, service_code, trang_thai);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_trang_thai
    ON public.lieu_trinh (clinic_id, trang_thai, tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_nguon_luot
    ON public.lieu_trinh (clinic_id, nguon_visit_id) WHERE nguon_visit_id IS NOT NULL;
COMMENT ON TABLE public.lieu_trinh IS
'Liệu trình điều trị nhiều buổi (08/10/2026): kế hoạch số buổi + đơn giá chốt của một khách cho một dịch vụ nhóm DIEU_TRI. trang_thai do trigger suy ra; sửa có revision; lịch sử ở lieu_trinh_lich_su.';

CREATE TABLE IF NOT EXISTS public.lieu_trinh_lich_su (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    lieu_trinh_id  uuid NOT NULL,
    -- revision SAU lần đổi này (dòng TAO mang revision 1).
    revision       integer NOT NULL,
    hanh_dong      text NOT NULL,
    ban_cu         jsonb NOT NULL,
    ban_moi        jsonb NOT NULL,
    boi            uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    luc            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT lieu_trinh_lich_su_lt_fk FOREIGN KEY (clinic_id, lieu_trinh_id)
        REFERENCES public.lieu_trinh (clinic_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_lich_su_lt
    ON public.lieu_trinh_lich_su (clinic_id, lieu_trinh_id, revision DESC);
COMMENT ON TABLE public.lieu_trinh_lich_su IS
'Lịch sử sửa liệu trình (08/10/2026): bản cũ → bản mới mỗi lần đổi. Trigger ghi; chỉ thêm.';

CREATE TABLE IF NOT EXISTS public.lieu_trinh_buoi (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    lieu_trinh_id    uuid NOT NULL,
    service_order_id uuid NOT NULL,
    buoi_so          integer NOT NULL CHECK (buoi_so >= 1),
    -- Buổi này trừ vào tiền đã trả trước (không vào hoá đơn, cổng tiền coi như đã thu).
    tra_truoc        boolean NOT NULL DEFAULT false,
    gan_luc          timestamptz NOT NULL DEFAULT now(),
    gan_boi          uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    gan_cach         text NOT NULL CHECK (gan_cach IN ('TU_DONG', 'TAY')),
    go_luc           timestamptz,
    go_boi           uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    -- TU_DONG: chỉ định huỷ / không làm / không chọn; TAY: người gỡ; CHUYEN: gắn
    -- sang liệu trình khác.
    go_cach          text CHECK (go_cach IN ('TU_DONG', 'TAY', 'CHUYEN')),
    CONSTRAINT lieu_trinh_buoi_lt_fk FOREIGN KEY (clinic_id, lieu_trinh_id)
        REFERENCES public.lieu_trinh (clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT lieu_trinh_buoi_order_fk FOREIGN KEY (clinic_id, service_order_id)
        REFERENCES public.service_order (clinic_id, id) ON DELETE CASCADE,
    CONSTRAINT lieu_trinh_buoi_go_di_cung CHECK ((go_luc IS NULL) = (go_cach IS NULL)),
    CONSTRAINT lieu_trinh_buoi_go_khong_phu CHECK (go_luc IS NULL OR NOT tra_truoc)
);
-- Một chỉ định thuộc ≤ 1 liệu trình; số buổi không trùng — trong buổi còn sống.
CREATE UNIQUE INDEX IF NOT EXISTS uq_lieu_trinh_buoi_chi_dinh_song
    ON public.lieu_trinh_buoi (clinic_id, service_order_id) WHERE go_luc IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_lieu_trinh_buoi_so_song
    ON public.lieu_trinh_buoi (lieu_trinh_id, buoi_so) WHERE go_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_buoi_lt
    ON public.lieu_trinh_buoi (clinic_id, lieu_trinh_id);
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_buoi_chi_dinh
    ON public.lieu_trinh_buoi (clinic_id, service_order_id);
COMMENT ON TABLE public.lieu_trinh_buoi IS
'Buổi của liệu trình (08/10/2026): chỉ định ↔ liệu trình, số buổi, buổi dùng tiền trả trước. Trigger trên service_order gắn/gỡ; gỡ = đóng dấu go_luc.';

-- ── 2. RLS (CHỈ ĐỌC — ghi qua lệnh FastAPI) + tin thời gian thực ──────────
ALTER TABLE public.lieu_trinh ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lieu_trinh_select_own_clinic ON public.lieu_trinh;
CREATE POLICY lieu_trinh_select_own_clinic ON public.lieu_trinh
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.lieu_trinh TO service_role;

ALTER TABLE public.lieu_trinh_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lieu_trinh_lich_su_select_own_clinic ON public.lieu_trinh_lich_su;
CREATE POLICY lieu_trinh_lich_su_select_own_clinic ON public.lieu_trinh_lich_su
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.lieu_trinh_lich_su TO service_role;

ALTER TABLE public.lieu_trinh_buoi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lieu_trinh_buoi_select_own_clinic ON public.lieu_trinh_buoi;
CREATE POLICY lieu_trinh_buoi_select_own_clinic ON public.lieu_trinh_buoi
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.lieu_trinh_buoi TO service_role;

DROP TRIGGER IF EXISTS trg_notify_lieu_trinh ON public.lieu_trinh;
CREATE TRIGGER trg_notify_lieu_trinh
    AFTER INSERT OR UPDATE OR DELETE ON public.lieu_trinh
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_notify_lieu_trinh_lich_su ON public.lieu_trinh_lich_su;
CREATE TRIGGER trg_notify_lieu_trinh_lich_su
    AFTER INSERT OR UPDATE OR DELETE ON public.lieu_trinh_lich_su
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_notify_lieu_trinh_buoi ON public.lieu_trinh_buoi;
CREATE TRIGGER trg_notify_lieu_trinh_buoi
    AFTER INSERT OR UPDATE OR DELETE ON public.lieu_trinh_buoi
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_lieu_trinh_lich_su_chi_them ON public.lieu_trinh_lich_su;
CREATE TRIGGER trg_lieu_trinh_lich_su_chi_them
    BEFORE UPDATE OR DELETE ON public.lieu_trinh_lich_su
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

-- ── 3. Hàm nền ─────────────────────────────────────────────────────────────
-- Chỉ định "còn sống" theo nghĩa liệu trình: cùng luật "còn tính tiền" của hoá
-- đơn (bill_service._CON_TINH_TIEN) + khách không bỏ.
CREATE OR REPLACE FUNCTION public.lieu_trinh_chi_dinh_song(
    p_exec text, p_execution text, p_selection text
) RETURNS boolean
LANGUAGE sql IMMUTABLE
AS $$
    SELECT coalesce(p_exec, '') NOT IN ('draft', 'cancelled', 'not_performed')
       AND coalesce(p_execution, '') NOT IN ('CANCELLED', 'NOT_PERFORMED')
       AND coalesce(p_selection, '') <> 'NOT_SELECTED';
$$;

-- Số buổi ĐÃ TRẢ TRƯỚC (net hoàn). B1: chưa có sổ tiền → 0. B2 thay thân hàm.
CREATE OR REPLACE FUNCTION public.lieu_trinh_so_buoi_da_tra(p_clinic uuid, p_lt uuid)
RETURNS integer
LANGUAGE sql STABLE
SET search_path = public
AS $$ SELECT 0 $$;

-- Chỉ định đã có dòng thu LẺ (trả từng buổi) đang giữ phủ → không cần tiền trả trước.
CREATE OR REPLACE FUNCTION public.lieu_trinh_buoi_da_thu_le(p_clinic uuid, p_order uuid)
RETURNS boolean
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = p_clinic
           AND bl.source_type = 'service_order'
           AND bl.source_id = p_order::text
           AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID'));
$$;

-- Chia lại tiền trả trước cho các buổi còn sống (người gọi đã khoá liệu trình):
--   * phủ nhiều hơn số đã trả (hoàn tiền / huỷ lần thu) → bỏ phủ buổi CHƯA bắt
--     đầu, số buổi lớn trước; buổi đã làm / đang làm mà vẫn vượt → TỪ CHỐI cả
--     lệnh (không bao giờ có buổi đã làm "trả bằng tiền đã hoàn");
--   * phủ ít hơn (vừa trả thêm / một buổi phủ bị gỡ) → phủ buổi chưa thu lẻ,
--     số buổi nhỏ trước.
CREATE OR REPLACE FUNCTION public.lieu_trinh_phu_lai(p_clinic uuid, p_lt uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    paid integer := public.lieu_trinh_so_buoi_da_tra(p_clinic, p_lt);
    covered integer;
    r record;
BEGIN
    SELECT count(*) INTO covered FROM public.lieu_trinh_buoi
     WHERE clinic_id = p_clinic AND lieu_trinh_id = p_lt
       AND go_luc IS NULL AND tra_truoc;
    IF covered > paid THEN
        FOR r IN
            SELECT b.id
              FROM public.lieu_trinh_buoi b
              JOIN public.service_order o
                ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
             WHERE b.clinic_id = p_clinic AND b.lieu_trinh_id = p_lt
               AND b.go_luc IS NULL AND b.tra_truoc
               AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
               AND o.exec_status IN ('authorized', 'assigned')
             ORDER BY b.buoi_so DESC
             LIMIT covered - paid
        LOOP
            UPDATE public.lieu_trinh_buoi SET tra_truoc = false WHERE id = r.id;
            covered := covered - 1;
        END LOOP;
        IF covered > paid THEN
            RAISE EXCEPTION
                'lieu_trinh: % buổi đã làm bằng tiền trả trước nhưng chỉ còn % buổi đã trả — không hoàn / huỷ quá số buổi chưa dùng',
                covered, paid
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_phu_vuot';
        END IF;
    ELSIF covered < paid THEN
        FOR r IN
            SELECT b.id
              FROM public.lieu_trinh_buoi b
             WHERE b.clinic_id = p_clinic AND b.lieu_trinh_id = p_lt
               AND b.go_luc IS NULL AND NOT b.tra_truoc
               AND NOT public.lieu_trinh_buoi_da_thu_le(p_clinic, b.service_order_id)
             ORDER BY b.buoi_so
             LIMIT paid - covered
        LOOP
            UPDATE public.lieu_trinh_buoi SET tra_truoc = true WHERE id = r.id;
        END LOOP;
    END IF;
END $$;

-- "Tính lại" một liệu trình: trigger BEFORE UPDATE suy trạng thái / tự thêm buổi.
CREATE OR REPLACE FUNCTION public.lieu_trinh_tinh_lai(p_clinic uuid, p_lt uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM public.lieu_trinh_phu_lai(p_clinic, p_lt);
    UPDATE public.lieu_trinh SET hanh_dong = 'TU_DONG', sua_boi = NULL
     WHERE clinic_id = p_clinic AND id = p_lt;
END $$;

-- Gắn MỘT chỉ định làm buổi kế của liệu trình. Trả id buổi.
CREATE OR REPLACE FUNCTION public.lieu_trinh_gan_buoi(
    p_clinic uuid, p_lt uuid, p_order uuid, p_cach text, p_boi uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    so integer;
    paid integer;
    covered integer;
    moi uuid;
BEGIN
    PERFORM 1 FROM public.lieu_trinh
     WHERE clinic_id = p_clinic AND id = p_lt FOR UPDATE;
    SELECT min(n) INTO so
      FROM generate_series(1, (SELECT count(*)::int + 1 FROM public.lieu_trinh_buoi
                                WHERE lieu_trinh_id = p_lt AND go_luc IS NULL)) n
     WHERE NOT EXISTS (SELECT 1 FROM public.lieu_trinh_buoi b
                        WHERE b.lieu_trinh_id = p_lt AND b.go_luc IS NULL
                          AND b.buoi_so = n);
    paid := public.lieu_trinh_so_buoi_da_tra(p_clinic, p_lt);
    SELECT count(*) INTO covered FROM public.lieu_trinh_buoi
     WHERE lieu_trinh_id = p_lt AND go_luc IS NULL AND tra_truoc;
    INSERT INTO public.lieu_trinh_buoi
        (clinic_id, lieu_trinh_id, service_order_id, buoi_so, tra_truoc,
         gan_boi, gan_cach)
    VALUES (p_clinic, p_lt, p_order, so,
            paid > covered AND NOT public.lieu_trinh_buoi_da_thu_le(p_clinic, p_order),
            p_boi, p_cach)
    RETURNING id INTO moi;
    PERFORM public.lieu_trinh_tinh_lai(p_clinic, p_lt);
    RETURN moi;
END $$;

-- Gỡ buổi còn sống của một chỉ định (nếu có). Trả id liệu trình đã gỡ khỏi.
CREATE OR REPLACE FUNCTION public.lieu_trinh_go_buoi(
    p_clinic uuid, p_order uuid, p_cach text, p_boi uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt uuid;
BEGIN
    SELECT lieu_trinh_id INTO lt FROM public.lieu_trinh_buoi
     WHERE clinic_id = p_clinic AND service_order_id = p_order AND go_luc IS NULL;
    IF lt IS NULL THEN
        RETURN NULL;
    END IF;
    PERFORM 1 FROM public.lieu_trinh WHERE clinic_id = p_clinic AND id = lt FOR UPDATE;
    UPDATE public.lieu_trinh_buoi
       SET go_luc = now(), go_boi = p_boi, go_cach = p_cach, tra_truoc = false
     WHERE clinic_id = p_clinic AND service_order_id = p_order AND go_luc IS NULL;
    PERFORM public.lieu_trinh_tinh_lai(p_clinic, lt);
    RETURN lt;
END $$;

-- Liệu trình DANG_LAM duy nhất của khách cho dịch vụ này (NULL nếu 0 hoặc ≥ 2).
CREATE OR REPLACE FUNCTION public.lieu_trinh_ung_vien_duy_nhat(
    p_clinic uuid, p_visit uuid, p_service_code text
) RETURNS uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT CASE WHEN count(*) = 1 THEN (array_agg(lt.id))[1] END
      FROM public.lieu_trinh lt
      JOIN public.visit v
        ON v.clinic_id = lt.clinic_id AND v.clinic_patient_id = lt.clinic_patient_id
     WHERE lt.clinic_id = p_clinic AND v.visit_id = p_visit
       AND lt.service_code = p_service_code AND lt.trang_thai = 'DANG_LAM';
$$;

-- ── 4. Trigger trên liệu trình ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public._lieu_trinh_ban(r public.lieu_trinh)
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT jsonb_build_object(
        'so_buoi', r.so_buoi, 'don_gia', r.don_gia,
        'ghi_chu_lo_trinh', r.ghi_chu_lo_trinh, 'trang_thai', r.trang_thai,
        'dang_ky_luc', r.dang_ky_luc, 'dang_ky_boi', r.dang_ky_boi,
        'dung_luc', r.dung_luc, 'dung_boi', r.dung_boi, 'ly_do_dung', r.ly_do_dung);
$$;

-- BEFORE INSERT/UPDATE: gác + suy trạng thái + tự thêm buổi + revision + lịch sử.
CREATE OR REPLACE FUNCTION public.lieu_trinh_truoc_khi_ghi()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    so_song integer := 0;
    da_lam integer := 0;
    co_nhan boolean := false;
    paid integer := 0;
    tu_dong boolean := NEW.hanh_dong = 'TU_DONG';
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.service_type st
              JOIN public.service_price sp
                ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id
             WHERE st.clinic_id = NEW.clinic_id AND st.nhom = 'DIEU_TRI'
               AND sp.service_code = NEW.service_code) THEN
            RAISE EXCEPTION 'lieu_trinh: dịch vụ % không thuộc nhóm Điều trị', NEW.service_code
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_chi_dieu_tri';
        END IF;
    ELSE
        IF NEW.clinic_patient_id IS DISTINCT FROM OLD.clinic_patient_id
           OR NEW.service_code IS DISTINCT FROM OLD.service_code
           OR NEW.clinic_id IS DISTINCT FROM OLD.clinic_id THEN
            RAISE EXCEPTION 'lieu_trinh: không đổi khách / dịch vụ của liệu trình'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_bat_bien';
        END IF;
        SELECT count(*),
               count(*) FILTER (WHERE coalesce(o.execution_status, '') = 'COMPLETED'
                                   OR (o.execution_status IS NULL
                                       AND o.exec_status = 'performed')),
               coalesce(bool_or(o.selection_status = 'SELECTED'
                                OR coalesce(o.execution_status, '')
                                   IN ('IN_PROGRESS', 'COMPLETED')
                                OR o.exec_status IN ('in_progress', 'performed')), false)
          INTO so_song, da_lam, co_nhan
          FROM public.lieu_trinh_buoi b
          JOIN public.service_order o
            ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
         WHERE b.clinic_id = NEW.clinic_id AND b.lieu_trinh_id = NEW.id
           AND b.go_luc IS NULL;
        paid := public.lieu_trinh_so_buoi_da_tra(NEW.clinic_id, NEW.id);
        IF NEW.don_gia IS DISTINCT FROM OLD.don_gia AND paid > 0 THEN
            RAISE EXCEPTION 'lieu_trinh: đã trả trước % buổi — không đổi đơn giá', paid
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_don_gia_chot';
        END IF;
        IF tu_dong THEN
            -- Làm quá số buổi kế hoạch (#13): tự thêm buổi, không chặn.
            NEW.so_buoi := greatest(NEW.so_buoi, so_song);
        ELSIF NEW.so_buoi < so_song THEN
            RAISE EXCEPTION 'lieu_trinh: đang có % buổi gắn liệu trình — gỡ buổi trước khi giảm số buổi',
                so_song
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_so_buoi_duoi_gan';
        END IF;
        IF NEW.so_buoi < paid AND NEW.so_buoi < OLD.so_buoi THEN
            RAISE EXCEPTION 'lieu_trinh: đã trả trước % buổi — hoàn tiền phần dư trước rồi giảm số buổi',
                paid
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_so_buoi_duoi_da_tra';
        END IF;
    END IF;

    -- Trạng thái suy ra — không ai ghi tay.
    NEW.trang_thai := CASE
        WHEN NEW.dung_luc IS NOT NULL THEN 'DUNG'
        WHEN NEW.dang_ky_luc IS NOT NULL OR co_nhan OR da_lam > 0 OR paid > 0 THEN
            CASE WHEN da_lam >= NEW.so_buoi THEN 'XONG' ELSE 'DANG_LAM' END
        ELSE 'DE_XUAT'
    END;

    IF TG_OP = 'INSERT' THEN
        NEW.revision := 1;
        NEW.sua_luc := now();
        RETURN NEW;
    END IF;

    IF public._lieu_trinh_ban(NEW) = public._lieu_trinh_ban(OLD)
       AND NEW.nguon_order_id IS NOT DISTINCT FROM OLD.nguon_order_id THEN
        -- Không đổi gì của kế hoạch (lệnh "tính lại" không có gì mới, bấm lại):
        -- bỏ hẳn lượt ghi — không tăng revision, không lịch sử, không tin.
        RETURN NULL;
    END IF;
    IF tu_dong THEN
        NEW.hanh_dong := CASE WHEN NEW.so_buoi <> OLD.so_buoi THEN 'TU_THEM_BUOI'
                              ELSE 'TU_TRANG_THAI' END;
        NEW.sua_boi := NULL;
    END IF;
    NEW.revision := OLD.revision + 1;
    NEW.sua_luc := now();
    INSERT INTO public.lieu_trinh_lich_su
        (clinic_id, lieu_trinh_id, revision, hanh_dong, ban_cu, ban_moi, boi)
    VALUES (NEW.clinic_id, NEW.id, NEW.revision, NEW.hanh_dong,
            public._lieu_trinh_ban(OLD), public._lieu_trinh_ban(NEW), NEW.sua_boi);
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_truoc_khi_ghi ON public.lieu_trinh;
CREATE TRIGGER trg_lieu_trinh_truoc_khi_ghi
    BEFORE INSERT OR UPDATE ON public.lieu_trinh
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_truoc_khi_ghi();

-- Dòng TAO của lịch sử (cần id → AFTER INSERT).
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_khi_tao()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.lieu_trinh_lich_su
        (clinic_id, lieu_trinh_id, revision, hanh_dong, ban_cu, ban_moi, boi)
    VALUES (NEW.clinic_id, NEW.id, NEW.revision, 'TAO', '{}'::jsonb,
            public._lieu_trinh_ban(NEW), coalesce(NEW.sua_boi, NEW.de_xuat_boi));
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_khi_tao ON public.lieu_trinh;
CREATE TRIGGER trg_lieu_trinh_sau_khi_tao
    AFTER INSERT ON public.lieu_trinh
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_sau_khi_tao();

-- ── 5. Gác buổi ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.lieu_trinh_buoi_gac()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt record;
    o record;
    paid integer;
    covered integer;
BEGIN
    -- Mọi thay đổi buổi xếp hàng sau dòng liệu trình (hai phòng cùng lúc).
    SELECT * INTO lt FROM public.lieu_trinh
     WHERE clinic_id = NEW.clinic_id AND id = NEW.lieu_trinh_id FOR UPDATE;
    IF TG_OP = 'INSERT' THEN
        SELECT so.service_code, v.clinic_patient_id INTO o
          FROM public.service_order so
          JOIN public.visit v ON v.clinic_id = so.clinic_id AND v.visit_id = so.visit_id
         WHERE so.clinic_id = NEW.clinic_id AND so.id = NEW.service_order_id;
        IF NOT FOUND OR o.clinic_patient_id <> lt.clinic_patient_id
           OR o.service_code <> lt.service_code THEN
            RAISE EXCEPTION 'lieu_trinh_buoi: chỉ định không cùng khách / cùng dịch vụ với liệu trình'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_buoi_khop';
        END IF;
        IF lt.trang_thai = 'DUNG' THEN
            RAISE EXCEPTION 'lieu_trinh_buoi: liệu trình đã dừng — mở lại trước khi gắn buổi'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_buoi_da_dung';
        END IF;
    ELSIF NEW.service_order_id IS DISTINCT FROM OLD.service_order_id
          OR NEW.lieu_trinh_id IS DISTINCT FROM OLD.lieu_trinh_id
          OR (OLD.go_luc IS NOT NULL AND NEW.go_luc IS NULL) THEN
        RAISE EXCEPTION 'lieu_trinh_buoi: buổi đã gỡ / đã gắn không sửa lại — gắn buổi mới'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_buoi_bat_bien';
    END IF;
    IF NEW.tra_truoc AND NEW.go_luc IS NULL
       AND (TG_OP = 'INSERT' OR NOT OLD.tra_truoc) THEN
        paid := public.lieu_trinh_so_buoi_da_tra(NEW.clinic_id, NEW.lieu_trinh_id);
        SELECT count(*) INTO covered FROM public.lieu_trinh_buoi
         WHERE lieu_trinh_id = NEW.lieu_trinh_id AND go_luc IS NULL AND tra_truoc
           AND id <> NEW.id;
        IF covered + 1 > paid THEN
            RAISE EXCEPTION 'lieu_trinh_buoi: hết buổi đã trả trước (% đã trả, % đang dùng)',
                paid, covered
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_phu_vuot';
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_buoi_gac ON public.lieu_trinh_buoi;
CREATE TRIGGER trg_lieu_trinh_buoi_gac
    BEFORE INSERT OR UPDATE ON public.lieu_trinh_buoi
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_buoi_gac();

-- ── 6. Trigger trên chỉ định — MỘT chỗ cho mọi đường tạo / đổi ─────────────
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_them_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt uuid;
BEGIN
    IF NOT public.lieu_trinh_chi_dinh_song(
           NEW.exec_status, NEW.execution_status, NEW.selection_status) THEN
        RETURN NULL;
    END IF;
    -- Đường nhanh: phòng khám không có liệu trình đang làm nào của dịch vụ này.
    IF NOT EXISTS (SELECT 1 FROM public.lieu_trinh
                    WHERE clinic_id = NEW.clinic_id AND service_code = NEW.service_code
                      AND trang_thai = 'DANG_LAM') THEN
        RETURN NULL;
    END IF;
    lt := public.lieu_trinh_ung_vien_duy_nhat(NEW.clinic_id, NEW.visit_id, NEW.service_code);
    IF lt IS NOT NULL THEN
        PERFORM public.lieu_trinh_gan_buoi(NEW.clinic_id, lt, NEW.id, 'TU_DONG', NULL);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_them_chi_dinh ON public.service_order;
CREATE TRIGGER trg_lieu_trinh_sau_them_chi_dinh
    AFTER INSERT ON public.service_order
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_sau_them_chi_dinh();

CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_sua_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    song_moi boolean := public.lieu_trinh_chi_dinh_song(
        NEW.exec_status, NEW.execution_status, NEW.selection_status);
    song_cu boolean := public.lieu_trinh_chi_dinh_song(
        OLD.exec_status, OLD.execution_status, OLD.selection_status);
    lt uuid;
    cu record;
BEGIN
    SELECT lieu_trinh_id INTO lt FROM public.lieu_trinh_buoi
     WHERE clinic_id = NEW.clinic_id AND service_order_id = NEW.id AND go_luc IS NULL;
    IF lt IS NOT NULL THEN
        IF NOT song_moi THEN
            -- Huỷ / không làm / khách không chọn → trả buổi về liệu trình (#4, #7).
            PERFORM public.lieu_trinh_go_buoi(NEW.clinic_id, NEW.id, 'TU_DONG', NULL);
        ELSE
            -- Bắt đầu / xong / hoàn tác xong (#8) → đếm lại đã làm, trạng thái.
            PERFORM 1 FROM public.lieu_trinh WHERE clinic_id = NEW.clinic_id AND id = lt
               FOR UPDATE;
            PERFORM public.lieu_trinh_tinh_lai(NEW.clinic_id, lt);
        END IF;
        RETURN NULL;
    END IF;
    IF NOT song_moi OR song_cu THEN
        RETURN NULL;
    END IF;
    -- Sống lại (hoàn tác bỏ / khách chọn lại — #17): gắn lại đúng liệu trình cũ
    -- nếu lần gỡ gần nhất là TỰ ĐỘNG; người đã gỡ tay thì để nguyên.
    SELECT b.lieu_trinh_id, b.go_cach, l.trang_thai INTO cu
      FROM public.lieu_trinh_buoi b
      JOIN public.lieu_trinh l ON l.clinic_id = b.clinic_id AND l.id = b.lieu_trinh_id
     WHERE b.clinic_id = NEW.clinic_id AND b.service_order_id = NEW.id
     ORDER BY b.go_luc DESC
     LIMIT 1;
    IF FOUND THEN
        IF cu.go_cach = 'TU_DONG' AND cu.trang_thai <> 'DUNG' THEN
            PERFORM public.lieu_trinh_gan_buoi(
                NEW.clinic_id, cu.lieu_trinh_id, NEW.id, 'TU_DONG', NULL);
        END IF;
        RETURN NULL;
    END IF;
    lt := public.lieu_trinh_ung_vien_duy_nhat(NEW.clinic_id, NEW.visit_id, NEW.service_code);
    IF lt IS NOT NULL THEN
        PERFORM public.lieu_trinh_gan_buoi(NEW.clinic_id, lt, NEW.id, 'TU_DONG', NULL);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_sua_chi_dinh ON public.service_order;
CREATE TRIGGER trg_lieu_trinh_sau_sua_chi_dinh
    AFTER UPDATE ON public.service_order
    FOR EACH ROW
    WHEN (OLD.exec_status IS DISTINCT FROM NEW.exec_status
          OR OLD.execution_status IS DISTINCT FROM NEW.execution_status
          OR OLD.selection_status IS DISTINCT FROM NEW.selection_status)
    EXECUTE FUNCTION public.lieu_trinh_sau_sua_chi_dinh();
