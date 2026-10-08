-- SỔ SỬA / BỎ CHỈ ĐỊNH (Khối 2, Tuyền chốt 06/10/2026).
--
-- Thao tác sửa chỉ định đã có (ô tích đầu dòng → huy-chi-dinh). Cái còn thiếu:
-- biết AI thêm / bỏ / hoàn tác cái gì, LÚC NÀO, ở BÀN BÁC SĨ NÀO, ai ra chỉ định
-- gốc, đã thu bao nhiêu → tiền thừa bao nhiêu, lý do, bác sĩ chính được báo lúc
-- nào, ai hoàn tác. Đủ bốn nhóm Khám · CLS · Điều trị · Thuốc.
--
-- GHI Ở ĐÂU:
--   * Chỉ định dịch vụ (`service_order`) và dịch vụ khám tick ở phiếu
--     (`luot_phi_kham`): TRIGGER — đường ghi nào vào hai bảng ấy cũng để lại vết,
--     kể cả đường thêm sau này, và ghi trong CÙNG giao dịch với thao tác. Lệnh
--     Python chỉ đặt ngữ cảnh (người bấm, vai đang dùng, lý do) bằng
--     `set_config(..., true)` — sống tới hết giao dịch, cùng kiểu
--     `clinicai.amendment_id` / `clinicai.lan_*` đã có.
--   * Thuốc: đơn lưu nguyên gói (mỗi lần lưu là cả đơn) — Python so đơn
--     trước/sau trong `luu_don_chua_ky` rồi ghi thẳng vào bảng này.
--
-- BẤT BIẾN ÉP Ở POSTGRES:
--   * Mỗi dòng BỎ chỉ được hoàn tác MỘT lần (`uq_so_sua_chi_dinh_hoan_tac`) —
--     bác sĩ chính bấm Hoàn tác ở hai máy cùng lúc thì một bên thua.
--   * Sổ không xoá được; cột "ai, lúc nào, làm gì" không sửa được.
--   * Hàm `bat_bien_tien_chi_dinh` cho bộ canh gác + mô phỏng: tổng thu − hoàn
--     − tiền thừa khớp phần đã thu của chỉ định còn hiệu lực.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.so_sua_chi_dinh (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Thứ tự ổn định trong cùng một giao dịch (now() như nhau).
    stt                  bigint GENERATED ALWAYS AS IDENTITY,
    clinic_id            uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id             uuid NOT NULL,
    nhom                 text NOT NULL,
    hanh_dong            text NOT NULL,
    service_order_id     uuid REFERENCES public.service_order (id) ON DELETE SET NULL,
    luot_phi_kham_id     uuid REFERENCES public.luot_phi_kham (id) ON DELETE SET NULL,
    -- Dòng đơn (prescription.id) — không khoá ngoại: đính chính thay dòng mới.
    dong_thuoc_id        uuid,
    ma_muc               text,
    ten_muc              text NOT NULL,
    -- THUỐC: {truoc:{…}, sau:{…}}; BỎ chỉ định: {truoc:{trạng thái cũ}}.
    chi_tiet             jsonb NOT NULL DEFAULT '{}'::jsonb,
    boi_staff_id         uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    boi_ten              text,
    boi_vai              text,
    luc                  timestamptz NOT NULL DEFAULT now(),
    -- Thuốc tự lưu mỗi 1,5 giây: cùng người sửa cùng dòng trong 10 phút gộp
    -- vào dòng sổ đang mở (như lịch sử sửa phiếu) — `sua_luc` là lần gộp cuối.
    sua_luc              timestamptz NOT NULL DEFAULT now(),
    phong_kham_ten       text,
    bac_si_chinh_id      uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    bac_si_chinh_ten     text,
    chi_dinh_goc_boi_id  uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    chi_dinh_goc_boi_ten text,
    da_thu               bigint NOT NULL DEFAULT 0,
    tien_thua            bigint NOT NULL DEFAULT 0,
    ly_do                text,
    da_bao_bac_si_luc    timestamptz,
    thong_bao_id         uuid REFERENCES public.thong_bao (id) ON DELETE SET NULL,
    hoan_tac_cua         uuid REFERENCES public.so_sua_chi_dinh (id) ON DELETE RESTRICT,
    hoan_tac_boi_id      uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    hoan_tac_boi_ten     text,
    hoan_tac_luc         timestamptz,

    CONSTRAINT so_sua_chi_dinh_nhom
        CHECK (nhom IN ('KHAM', 'CLS', 'DIEU_TRI', 'THUOC')),
    CONSTRAINT so_sua_chi_dinh_hanh_dong
        CHECK (hanh_dong IN ('THEM', 'BO', 'HOAN_TAC', 'DOI')),
    CONSTRAINT so_sua_chi_dinh_tien_khong_am
        CHECK (da_thu >= 0 AND tien_thua >= 0 AND tien_thua <= da_thu),
    -- Dòng HOÀN TÁC luôn trỏ về đúng dòng BỎ nó rút lại, và ngược lại.
    CONSTRAINT so_sua_chi_dinh_hoan_tac_tro_ve
        CHECK ((hanh_dong = 'HOAN_TAC') = (hoan_tac_cua IS NOT NULL)),
    -- Chỉ dòng BỎ mới có "ai hoàn tác".
    CONSTRAINT so_sua_chi_dinh_hoan_tac_chi_o_dong_bo
        CHECK (hoan_tac_luc IS NULL OR hanh_dong = 'BO'),
    CONSTRAINT so_sua_chi_dinh_hoan_tac_co_nguoi
        CHECK ((hoan_tac_luc IS NULL) = (hoan_tac_boi_ten IS NULL)),
    CONSTRAINT so_sua_chi_dinh_doi_chi_thuoc
        CHECK (hanh_dong <> 'DOI' OR nhom = 'THUOC'),
    CONSTRAINT so_sua_chi_dinh_ly_do_ngan
        CHECK (ly_do IS NULL OR length(ly_do) <= 500)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_so_sua_chi_dinh_hoan_tac
    ON public.so_sua_chi_dinh (hoan_tac_cua) WHERE hoan_tac_cua IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_so_sua_chi_dinh_luot
    ON public.so_sua_chi_dinh (clinic_id, visit_id, stt DESC);
CREATE INDEX IF NOT EXISTS ix_so_sua_chi_dinh_chi_dinh
    ON public.so_sua_chi_dinh (service_order_id, stt DESC)
 WHERE service_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_so_sua_chi_dinh_phi_kham
    ON public.so_sua_chi_dinh (luot_phi_kham_id, stt DESC)
 WHERE luot_phi_kham_id IS NOT NULL;

COMMENT ON TABLE public.so_sua_chi_dinh IS
'Sổ thêm / bỏ / hoàn tác chỉ định (Khám · CLS · Điều trị · Thuốc): ai, vai, lúc nào, bàn bác sĩ nào, chỉ định gốc của ai, tiền đã thu → tiền thừa, lý do, báo bác sĩ chính, ai hoàn tác (Khối 2, 06/10/2026).';

ALTER TABLE public.so_sua_chi_dinh ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS so_sua_chi_dinh_select_own_clinic ON public.so_sua_chi_dinh;
CREATE POLICY so_sua_chi_dinh_select_own_clinic ON public.so_sua_chi_dinh
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.so_sua_chi_dinh TO service_role;


-- ── Sổ chỉ ghi thêm ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.so_sua_chi_dinh_chi_ghi_them()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Sổ sửa chỉ định không xoá được (dòng %).', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    -- "Ai, lúc nào, làm gì với cái gì" không đổi. Khoá ngoại SET NULL (xoá
    -- nhân sự / chỉ định) vẫn được — đó là Postgres dọn tham chiếu, không phải
    -- sửa sổ; tên đã chụp lại ở cột *_ten.
    IF NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id <> OLD.visit_id
       OR NEW.nhom <> OLD.nhom
       OR NEW.hanh_dong <> OLD.hanh_dong
       OR NEW.luc <> OLD.luc
       OR NEW.hoan_tac_cua IS DISTINCT FROM OLD.hoan_tac_cua
       OR (NEW.boi_staff_id IS NOT NULL
           AND NEW.boi_staff_id IS DISTINCT FROM OLD.boi_staff_id)
       OR (NEW.service_order_id IS NOT NULL
           AND NEW.service_order_id IS DISTINCT FROM OLD.service_order_id)
       OR (OLD.hoan_tac_luc IS NOT NULL
           AND NEW.hoan_tac_luc IS DISTINCT FROM OLD.hoan_tac_luc)
       -- Chỉ dòng THUỐC đang mở mới gộp (đổi tên / chi tiết).
       OR (OLD.nhom <> 'THUOC'
           AND (NEW.ten_muc <> OLD.ten_muc OR NEW.chi_tiet <> OLD.chi_tiet))
    THEN
        RAISE EXCEPTION 'Sổ sửa chỉ định chỉ ghi thêm — không sửa được dòng %.', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_so_sua_chi_dinh_chi_ghi_them ON public.so_sua_chi_dinh;
CREATE TRIGGER trg_so_sua_chi_dinh_chi_ghi_them
    BEFORE UPDATE OR DELETE ON public.so_sua_chi_dinh
    FOR EACH ROW EXECUTE FUNCTION public.so_sua_chi_dinh_chi_ghi_them();

-- Màn mở (Lịch sử sửa, Hành trình khách) tự tải lại qua dòng SSE chung.
DROP TRIGGER IF EXISTS trg_notify_so_sua_chi_dinh ON public.so_sua_chi_dinh;
CREATE TRIGGER trg_notify_so_sua_chi_dinh
    AFTER INSERT OR UPDATE ON public.so_sua_chi_dinh
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();


-- ── Nhóm của một dịch vụ: KHAM · CLS · DIEU_TRI ───────────────────────────
-- Phí khám: cùng luật `danh_muc_dich_vu` (nhóm hàng "Phí khám"/"Tiền khám", mã
-- KHAM_*, gắn loại khám). Điều trị: phòng thủ thuật hoặc nhóm hàng Thủ thuật /
-- Sàn chậu. Còn lại là cận lâm sàng.
CREATE OR REPLACE FUNCTION public.nhom_chi_dinh(
    p_clinic_id uuid, p_service_code text, p_node_code text
)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT CASE
        WHEN coalesce(p_node_code, '') LIKE 'KHAM-%'
          OR coalesce(p_service_code, '') LIKE 'KHAM\_%'
          OR EXISTS (
              SELECT 1 FROM public.service_price sp
               WHERE sp.clinic_id = p_clinic_id
                 AND sp.service_code = p_service_code
                 AND sp."group" = 'dich_vu'
                 AND (coalesce(sp.category, '') LIKE 'Phí khám%'
                      OR coalesce(sp.category, '') LIKE 'Tiền khám%'
                      OR EXISTS (SELECT 1 FROM public.loai_kham_phi l
                                  WHERE l.service_price_id = sp.id)))
            THEN 'KHAM'
        WHEN coalesce(p_node_code, '') = 'DICHVU-THUTHUAT'
          OR EXISTS (
              SELECT 1 FROM public.service_price sp
               WHERE sp.clinic_id = p_clinic_id
                 AND sp.service_code = p_service_code
                 AND sp."group" = 'dich_vu'
                 AND (coalesce(sp.category, '') LIKE 'Thủ thuật%'
                      OR coalesce(sp.category, '') LIKE 'Sàn chậu%'))
            THEN 'DIEU_TRI'
        ELSE 'CLS'
    END;
$$;


-- ── Tiền của MỘT chỉ định: đã thu (lần thu ĐÃ THU) và đã hoàn ──────────────
-- Cùng luật `hoan_tac_service.tien_da_thu_cua_chi_dinh` (dòng của chính chỉ
-- định + phụ thu đi kèm, phòng khám thu; hoàn đang làm / đã xong).
CREATE OR REPLACE FUNCTION public.tien_cua_chi_dinh(p_clinic_id uuid, p_order_id uuid)
RETURNS TABLE (da_thu bigint, da_hoan bigint)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH dong AS (
        SELECT bl.id AS line_id, bl.line_total
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id
           AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = p_clinic_id
           AND bl.billing_owner = 'CLINIC'
           AND c.status = 'PAID'
           AND ((bl.source_type = 'service_order' AND bl.source_id = p_order_id::text)
                OR (bl.source_type = 'phu_thu' AND bl.source_id IN (
                    SELECT p.id::text FROM public.luot_phu_thu p
                     WHERE p.clinic_id = p_clinic_id
                       AND p.service_order_id = p_order_id)))
    )
    SELECT coalesce((SELECT sum(line_total) FROM dong), 0)::bigint,
           coalesce((
               SELECT sum(rl.amount)
                 FROM public.payment_refund_line rl
                 JOIN public.payment_refund r
                   ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
                WHERE rl.clinic_id = p_clinic_id
                  AND rl.payment_bill_line_id IN (SELECT line_id FROM dong)
                  AND r.status IN ('PENDING', 'COMPLETED')), 0)::bigint;
$$;


-- ── Ngữ cảnh của lượt: bác sĩ chính + phòng khám của bác sĩ ấy hôm đó ─────
CREATE OR REPLACE FUNCTION public.so_chi_dinh_ngu_canh(p_clinic_id uuid, p_visit_id uuid)
RETURNS TABLE (bac_si_chinh_id uuid, bac_si_chinh_ten text, phong_kham_ten text)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH bs AS (
        SELECT coalesce(
                   v.attending_doctor_id,
                   (SELECT c.doctor_staff_id FROM public.consultation c
                     WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
                       AND c.kind = 'PRIMARY'
                     ORDER BY c.created_at DESC LIMIT 1)) AS id,
               (coalesce(v.checked_in_at, v.created_at)
                   AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay
          FROM public.visit v
         WHERE v.clinic_id = p_clinic_id AND v.visit_id = p_visit_id
    )
    SELECT bs.id, s.full_name,
           (SELECT r.name
              FROM public.work_roster w
              JOIN public.vi_tri_lam_viec vt
                ON vt.clinic_id = w.clinic_id AND vt.code = w.station
              JOIN public.clinic_room r ON r.id = vt.room_id
             WHERE w.clinic_id = p_clinic_id AND w.staff_id = bs.id
               AND w.work_date = bs.ngay AND w.status <> 'REJECTED'
               AND vt.room_id IS NOT NULL
             ORDER BY vt.sort LIMIT 1)
      FROM bs
      LEFT JOIN public.staff s ON s.id = bs.id;
$$;


-- ── Người bấm: GUC của lệnh Python, không có thì người ghi trên dòng ───────
CREATE OR REPLACE FUNCTION public.so_chi_dinh_nguoi(
    p_clinic_id uuid, p_mac_dinh uuid
)
RETURNS TABLE (staff_id uuid, ten text, vai text)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH ai AS (
        SELECT coalesce(
            nullif(current_setting('clinicai.so_nguoi', true), '')::uuid,
            p_mac_dinh) AS id
    )
    SELECT ai.id, s.full_name,
           coalesce(
               nullif(current_setting('clinicai.so_vai', true), ''),
               (SELECT m.role FROM public.clinic_membership m
                 WHERE m.clinic_id = p_clinic_id AND m.staff_id = ai.id
                   AND m.is_active
                 ORDER BY m.created_at LIMIT 1))
      FROM ai
      LEFT JOIN public.staff s ON s.id = ai.id;
$$;


-- ── Trigger: chỉ định dịch vụ ─────────────────────────────────────────────
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
                  'routing_status', OLD.routing_status))
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


-- ── Trigger: dịch vụ khám tick ở phiếu (nhóm KHAM) ────────────────────────
CREATE OR REPLACE FUNCTION public.ghi_so_sua_phi_kham()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    hd      text;
    ai      record;
    nc      record;
    sp      record;
    bo_id   uuid;
    v_ly_do text := nullif(btrim(current_setting('clinicai.so_ly_do', true)), '');
BEGIN
    IF coalesce(current_setting('clinicai.so_bo_qua', true), '') = 'on' THEN
        RETURN NULL;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.bo_luc IS NOT NULL THEN
            RETURN NULL;
        END IF;
        hd := 'THEM';
        SELECT * INTO ai FROM public.so_chi_dinh_nguoi(NEW.clinic_id, NEW.chon_boi);
    ELSIF OLD.bo_luc IS NULL AND NEW.bo_luc IS NOT NULL THEN
        hd := 'BO';
        SELECT * INTO ai FROM public.so_chi_dinh_nguoi(NEW.clinic_id, NEW.bo_boi);
    ELSE
        RETURN NULL;
    END IF;
    SELECT * INTO nc FROM public.so_chi_dinh_ngu_canh(NEW.clinic_id, NEW.visit_id);
    SELECT s.name, coalesce(s.ma_kiotviet, s.service_code) AS ma INTO sp
      FROM public.service_price s WHERE s.id = NEW.service_price_id;

    -- Tick lại đúng dịch vụ khám vừa bỏ bằng nút Hoàn tác: dòng HOÀN TÁC trỏ về
    -- dòng BỎ ấy (lệnh đặt `clinicai.so_hoan_tac_cua`).
    bo_id := nullif(current_setting('clinicai.so_hoan_tac_cua', true), '')::uuid;
    IF hd = 'THEM' AND bo_id IS NOT NULL THEN
        hd := 'HOAN_TAC';
        UPDATE public.so_sua_chi_dinh
           SET hoan_tac_boi_id = ai.staff_id,
               hoan_tac_boi_ten = coalesce(ai.ten, 'Không rõ'),
               hoan_tac_luc = now()
         WHERE id = bo_id AND hoan_tac_luc IS NULL;
    ELSE
        bo_id := NULL;
    END IF;

    INSERT INTO public.so_sua_chi_dinh
        (clinic_id, visit_id, nhom, hanh_dong, luot_phi_kham_id, ma_muc, ten_muc,
         boi_staff_id, boi_ten, boi_vai, phong_kham_ten, bac_si_chinh_id,
         bac_si_chinh_ten, chi_dinh_goc_boi_id, chi_dinh_goc_boi_ten, ly_do,
         hoan_tac_cua)
    VALUES
        (NEW.clinic_id, NEW.visit_id, 'KHAM', hd, NEW.id, sp.ma,
         coalesce(sp.name, 'Dịch vụ khám'),
         ai.staff_id, ai.ten, ai.vai, nc.phong_kham_ten, nc.bac_si_chinh_id,
         nc.bac_si_chinh_ten, NEW.chon_boi,
         (SELECT full_name FROM public.staff WHERE id = NEW.chon_boi),
         CASE WHEN hd IN ('BO', 'HOAN_TAC') THEN left(v_ly_do, 500) END,
         bo_id);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_so_sua_phi_kham ON public.luot_phi_kham;
CREATE TRIGGER trg_so_sua_phi_kham
    AFTER INSERT OR UPDATE OF bo_luc ON public.luot_phi_kham
    FOR EACH ROW EXECUTE FUNCTION public.ghi_so_sua_phi_kham();


-- ── Lượt chuyển từ hồ sơ cũ (Notion, 20261006100000): chỉ xem ─────────────
CREATE OR REPLACE FUNCTION public.la_luot_ho_so_cu(p_visit_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT EXISTS (SELECT 1 FROM lich_su_notion.luot_that t
                    WHERE t.visit_id = p_visit_id);
$$;


-- ── BẤT BIẾN TIỀN CHỈ ĐỊNH ────────────────────────────────────────────────
-- Mỗi lượt có lần thu dịch vụ từ `p_tu`:
--   A = Σ đã thu (PAID) − Σ đã hoàn trên dòng chỉ định + phụ thu của lượt
--   B = Σ (đã thu − đã hoàn) của chỉ định CÒN HIỆU LỰC
--   C = Σ (đã thu − đã hoàn) của chỉ định đã bỏ / không làm = TIỀN THỪA ở quầy
-- Phải có A = B + C (lệch = dòng thu trỏ vào chỉ định không thuộc lượt / đã
-- mất), không chỉ định nào hoàn quá số thu (AM), không chỉ định còn hiệu lực
-- nào bị thu HAI lần mà chưa hoàn lần nào (THU_TRUNG). Trả về các dòng VI PHẠM (rỗng = ổn).
CREATE OR REPLACE FUNCTION public.bat_bien_tien_chi_dinh(
    p_clinic_id uuid, p_tu timestamptz
)
RETURNS TABLE (visit_id uuid, loai text, chi_tiet text)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH luot AS (
        SELECT DISTINCT c.visit_id
          FROM public.payment_cycle c
         WHERE c.clinic_id = p_clinic_id AND c.status = 'PAID'
           AND c.kind = 'dich_vu' AND coalesce(c.paid_at, c.created_at) >= p_tu
    ),
    dong AS (
        SELECT bl.visit_id, bl.id AS line_id, bl.line_total, bl.source_type,
               CASE WHEN bl.source_type = 'service_order' THEN bl.source_id
                    ELSE (SELECT p.service_order_id::text FROM public.luot_phu_thu p
                           WHERE p.clinic_id = bl.clinic_id
                             AND p.id::text = bl.source_id)
               END AS order_id,
               coalesce((SELECT sum(rl.amount)
                           FROM public.payment_refund_line rl
                           JOIN public.payment_refund r
                             ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
                          WHERE rl.clinic_id = bl.clinic_id
                            AND rl.payment_bill_line_id = bl.id
                            AND r.status IN ('PENDING', 'COMPLETED')), 0) AS da_hoan
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = p_clinic_id AND c.status = 'PAID'
           AND bl.billing_owner = 'CLINIC'
           AND bl.source_type IN ('service_order', 'phu_thu')
           AND bl.visit_id IN (SELECT visit_id FROM luot)
    ),
    theo_chi_dinh AS (
        SELECT d.visit_id, d.order_id,
               sum(d.line_total) AS da_thu, sum(d.da_hoan) AS da_hoan,
               -- Dòng CHÍNH của chỉ định (không tính phụ thu đi kèm) còn giữ tiền.
               count(*) FILTER (WHERE d.source_type = 'service_order'
                                  AND d.da_hoan < d.line_total) AS so_dong_con
          FROM dong d WHERE d.order_id IS NOT NULL
         GROUP BY d.visit_id, d.order_id
    ),
    gan AS (
        SELECT t.*, o.id IS NOT NULL AS co_chi_dinh,
               o.exec_status IN ('cancelled', 'not_performed') AS da_bo
          FROM theo_chi_dinh t
          LEFT JOIN public.service_order o
            ON o.clinic_id = p_clinic_id AND o.id::text = t.order_id
           -- KHÔNG ép cùng lượt: chỉ định đã trả mang sang lượt sau (H2) vẫn
           -- là của khoản thu ở lượt trước.
    ),
    tong AS (
        SELECT g.visit_id,
               sum(g.da_thu - g.da_hoan) AS a,
               sum(g.da_thu - g.da_hoan) FILTER (WHERE g.co_chi_dinh AND NOT g.da_bo) AS b,
               sum(g.da_thu - g.da_hoan) FILTER (WHERE g.co_chi_dinh AND g.da_bo) AS c
          FROM gan g GROUP BY g.visit_id
    )
    SELECT t.visit_id, 'LECH_TONG',
           format('thu−hoàn %s ≠ còn hiệu lực %s + tiền thừa %s',
                  t.a, coalesce(t.b, 0), coalesce(t.c, 0))
      FROM tong t
     WHERE t.a <> coalesce(t.b, 0) + coalesce(t.c, 0)
    UNION ALL
    SELECT g.visit_id, 'AM', format('chỉ định %s hoàn %s > thu %s', g.order_id, g.da_hoan, g.da_thu)
      FROM gan g WHERE g.da_hoan > g.da_thu
    UNION ALL
    SELECT g.visit_id, 'THU_TRUNG',
           format('chỉ định %s còn hiệu lực đang giữ %s dòng thu chưa hoàn', g.order_id, g.so_dong_con)
      FROM gan g
     WHERE g.co_chi_dinh AND NOT g.da_bo AND g.so_dong_con > 1;
$$;

COMMENT ON FUNCTION public.bat_bien_tien_chi_dinh(uuid, timestamptz) IS
'Bất biến tiền chỉ định: thu − hoàn = phần của chỉ định còn hiệu lực + tiền thừa (chỉ định đã bỏ). Trả dòng vi phạm (Khối 2, 06/10/2026).';
