-- Quyền phân loại mặt hàng cần duyệt và duyệt phiếu vật tư chỉ thuộc Quản lý.
-- Mọi trigger cũ được thay tại đây để đóng cả đường ghi trực tiếp vào database.

UPDATE public.quyen_preset
   SET khoi = array_remove(khoi, 'duyet_vat_tu')
 WHERE ma <> 'MANAGEMENT' AND khoi @> ARRAY['duyet_vat_tu'];

UPDATE public.capability_grant g
   SET revoked_at = coalesce(g.revoked_at, now()),
       revoked_by = coalesce(g.revoked_by, g.granted_by, g.staff_id),
       ly_do = coalesce(g.ly_do, 'Thu hồi: duyệt vật tư chỉ dành cho Quản lý')
 WHERE g.capability = 'vat_tu.approve'
   AND g.revoked_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM public.clinic_membership m
        WHERE m.clinic_id = g.clinic_id AND m.staff_id = g.staff_id
          AND m.is_active AND m.role = 'MANAGEMENT'
   );

CREATE OR REPLACE FUNCTION public.vat_tu_approve_chi_quan_ly_gac_grant()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.capability = 'vat_tu.approve' AND NEW.revoked_at IS NULL
    THEN
        PERFORM 1 FROM public.clinic_membership m
         WHERE m.clinic_id = NEW.clinic_id AND m.staff_id = NEW.staff_id
           AND m.is_active AND m.role = 'MANAGEMENT'
         FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'vat_tu.approve chỉ cấp được cho tài khoản Quản lý'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS vat_tu_approve_chi_quan_ly_gac_grant
    ON public.capability_grant;
CREATE TRIGGER vat_tu_approve_chi_quan_ly_gac_grant
    BEFORE INSERT OR UPDATE OF capability, clinic_id, staff_id, revoked_at
    ON public.capability_grant
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_approve_chi_quan_ly_gac_grant();

CREATE OR REPLACE FUNCTION public.vat_tu_approve_thu_khi_doi_vai()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.role IS DISTINCT FROM OLD.role OR NEW.is_active IS DISTINCT FROM OLD.is_active THEN
        IF NEW.role <> 'MANAGEMENT' OR NOT NEW.is_active THEN
            UPDATE public.capability_grant
               SET revoked_at = coalesce(revoked_at, now()),
                   revoked_by = coalesce(revoked_by, granted_by, NEW.staff_id),
                   ly_do = coalesce(ly_do, 'Tự thu: vai trò không còn là Quản lý')
             WHERE clinic_id = NEW.clinic_id AND staff_id = NEW.staff_id
               AND capability = 'vat_tu.approve' AND revoked_at IS NULL;
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS vat_tu_approve_thu_khi_doi_vai ON public.clinic_membership;
CREATE TRIGGER vat_tu_approve_thu_khi_doi_vai
    AFTER UPDATE OF role, is_active ON public.clinic_membership
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_approve_thu_khi_doi_vai();

-- Mặt hàng cần duyệt bán: capability vẫn cần bật, đồng thời membership của
-- người duyệt phải là MANAGEMENT tại đúng phòng khám.
CREATE OR REPLACE FUNCTION public.luot_vat_tu_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    sp record;
    trung uuid;
    actor uuid := nullif(current_setting('app.staff_id', true), '')::uuid;
    co_lego boolean := false;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT s."group", s.active, s.unit_price, s.can_ql_duyet, s.clinic_id
          INTO sp FROM public.service_price s WHERE s.id = NEW.service_price_id;
        IF NOT FOUND OR sp."group" <> 'vat_tu' OR sp.clinic_id <> NEW.clinic_id THEN
            RAISE EXCEPTION 'luot_vat_tu: không phải vật tư của phòng khám này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT sp.active OR coalesce(sp.unit_price, 0) <= 0 THEN
            RAISE EXCEPTION 'luot_vat_tu: vật tư chưa có giá hoặc đã ngưng bán — không bán được'
                USING ERRCODE = 'check_violation';
        END IF;
        IF actor IS NOT NULL AND actor IS DISTINCT FROM NEW.chon_boi THEN
            RAISE EXCEPTION 'luot_vat_tu: người chọn phải trùng với người thao tác đã xác thực'
                USING ERRCODE = 'check_violation';
        END IF;
        IF sp.can_ql_duyet AND (
               actor IS DISTINCT FROM NEW.duyet_boi
               OR NEW.chon_boi IS DISTINCT FROM NEW.duyet_boi
               OR NOT EXISTS (
               SELECT 1
                 FROM public.v_quyen_thuc_te q
                 JOIN public.clinic_membership m
                   ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id
                  AND m.is_active AND m.role = 'MANAGEMENT'
                 JOIN public.staff s2 ON s2.id = q.staff_id AND s2.is_active
                WHERE q.clinic_id = NEW.clinic_id AND q.staff_id = NEW.duyet_boi
                  AND q.capability = 'vat_tu.approve'
                  AND q.scope_type = 'CLINIC')) THEN
            RAISE EXCEPTION 'luot_vat_tu: chỉ Quản lý có quyền đang thao tác mới được duyệt bán (kèm lý do)'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    SELECT s.can_ql_duyet INTO sp
      FROM public.service_price s
     WHERE s.id = OLD.service_price_id AND s.clinic_id = OLD.clinic_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'luot_vat_tu: không tìm thấy mặt hàng của dòng'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.chon_boi IS DISTINCT FROM OLD.chon_boi
       OR NEW.duyet_boi IS DISTINCT FROM OLD.duyet_boi
       OR NEW.duyet_ly_do IS DISTINCT FROM OLD.duyet_ly_do THEN
        SELECT EXISTS (
            SELECT 1
              FROM public.v_quyen_thuc_te q
              JOIN public.clinic_membership m
                ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id
               AND m.is_active AND m.role = 'MANAGEMENT'
              JOIN public.staff s2 ON s2.id = q.staff_id AND s2.is_active
             WHERE q.clinic_id = OLD.clinic_id AND q.staff_id = actor
               AND q.capability = 'vat_tu.approve'
               AND q.scope_type = 'CLINIC')
          INTO co_lego;
        IF NOT co_lego OR actor IS DISTINCT FROM NEW.chon_boi
           OR actor IS DISTINCT FROM NEW.duyet_boi THEN
            RAISE EXCEPTION 'luot_vat_tu: chỉ Quản lý đang thao tác mới ghi được dấu vết duyệt'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF sp.can_ql_duyet OR EXISTS (
           SELECT 1 FROM public.service_price s
            WHERE s.id = NEW.service_price_id
              AND s.clinic_id = OLD.clinic_id
              AND s.can_ql_duyet) THEN
        SELECT EXISTS (
            SELECT 1
              FROM public.v_quyen_thuc_te q
              JOIN public.clinic_membership m
                ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id
               AND m.is_active AND m.role = 'MANAGEMENT'
              JOIN public.staff s2 ON s2.id = q.staff_id AND s2.is_active
             WHERE q.clinic_id = OLD.clinic_id AND q.staff_id = actor
               AND q.capability = 'vat_tu.approve'
               AND q.scope_type = 'CLINIC')
          INTO co_lego;
        IF NOT co_lego THEN
            RAISE EXCEPTION 'luot_vat_tu: chỉ Quản lý có quyền mới sửa hoặc bỏ mặt hàng cần duyệt'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF NEW.so_luong IS DISTINCT FROM OLD.so_luong
       OR NEW.don_gia IS DISTINCT FROM OLD.don_gia
       OR (NEW.bo_luc IS NOT NULL AND OLD.bo_luc IS NULL) THEN
        SELECT bl.payment_cycle_id INTO trung
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = OLD.clinic_id
           AND bl.source_type = 'vat_tu' AND bl.source_id = OLD.id::text
           AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
         LIMIT 1;
        IF trung IS NOT NULL THEN
            RAISE EXCEPTION
                'luot_vat_tu: dòng đã nằm trong lần thu % — hoàn tác lần thu trước khi đổi', trung
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Phiếu nhập chờ duyệt: chỉ Quản lý có capability được duyệt / từ chối.
CREATE OR REPLACE FUNCTION public.vat_tu_nhap_cho_duyet_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    co_lego boolean;
    actor uuid := nullif(current_setting('app.staff_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Không xoá yêu cầu nhập vật tư — rút lại hoặc từ chối'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.trang_thai <> 'CHO_DUYET' THEN
            RAISE EXCEPTION 'Yêu cầu nhập vật tư mới phải ở trạng thái chờ duyệt'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.clinic_location
                        WHERE id = NEW.location_id AND clinic_id = NEW.clinic_id)
           OR NOT EXISTS (SELECT 1 FROM public.clinic_membership
                           WHERE clinic_id = NEW.clinic_id AND staff_id = NEW.tao_boi
                             AND is_active) THEN
            RAISE EXCEPTION 'Yêu cầu nhập vật tư sai cơ sở / người lập'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.trang_thai <> 'CHO_DUYET' THEN
        RAISE EXCEPTION 'Yêu cầu nhập vật tư đã quyết — không sửa nữa'
            USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.clinic_id, NEW.location_id, NEW.ma_yeu_cau, NEW.khoa_gui, NEW.dong,
        NEW.ghi_chu, NEW.tao_boi, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.clinic_id, OLD.location_id, OLD.ma_yeu_cau, OLD.khoa_gui, OLD.dong,
        OLD.ghi_chu, OLD.tao_boi, OLD.tao_luc) THEN
        RAISE EXCEPTION 'Không sửa nội dung yêu cầu nhập vật tư đã gửi'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.trang_thai = 'CHO_DUYET' THEN
        RAISE EXCEPTION 'Yêu cầu đang chờ — phải duyệt, từ chối hoặc rút lại'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM public.v_quyen_thuc_te q
          JOIN public.clinic_membership m
            ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id
           AND m.is_active AND m.role = 'MANAGEMENT'
         WHERE q.clinic_id = NEW.clinic_id AND q.staff_id = NEW.quyet_boi
           AND q.capability = 'vat_tu.approve' AND q.scope_type = 'CLINIC')
      INTO co_lego;
    IF NEW.trang_thai IN ('DA_DUYET', 'TU_CHOI')
       AND (NEW.quyet_boi IS NULL OR NOT co_lego
            OR NEW.quyet_boi IS DISTINCT FROM actor) THEN
        RAISE EXCEPTION 'Chỉ Quản lý đang thao tác có quyền Duyệt vật tư mới duyệt / từ chối được'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.trang_thai = 'RUT_LAI'
       AND (NEW.quyet_boi IS NULL OR
            (NEW.quyet_boi <> OLD.tao_boi AND NOT co_lego)) THEN
        RAISE EXCEPTION 'Chỉ người lập hoặc Quản lý có quyền duyệt mới rút lại được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Các giá trị có cờ duyệt chỉ được đọc qua FastAPI (service_role), nơi kiểm tra
-- membership + capability và giới hạn nhân viên vào yêu cầu của chính họ.
-- Không để PostgREST mở đường vòng cho mọi tài khoản authenticated.
DROP POLICY IF EXISTS vat_tu_nhap_cho_duyet_select_own_clinic
    ON public.vat_tu_nhap_cho_duyet;
REVOKE ALL ON public.vat_tu_nhap_cho_duyet FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.vat_tu_nhap_cho_duyet TO service_role;

DROP POLICY IF EXISTS service_price_select_authenticated ON public.service_price;
DROP POLICY IF EXISTS service_price_select_own_clinic ON public.service_price;
REVOKE ALL ON public.service_price FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.service_price TO service_role;

NOTIFY pgrst, 'reload schema';
