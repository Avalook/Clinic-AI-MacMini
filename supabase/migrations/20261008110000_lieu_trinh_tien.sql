-- LIỆU TRÌNH — TIỀN TRẢ TRƯỚC (B2, docs/KE-HOACH-LIEU-TRINH.md Phần B, Q2/Q3/Q5).
--
-- "Trả trước k buổi" = một dòng hoá đơn DỊCH VỤ loại mới
-- `payment_bill_line.source_type = 'lieu_trinh'` (quantity = k, unit_price = đơn
-- giá CHỐT của liệu trình), thu qua đúng lần thu dịch vụ của lượt khách đang có
-- mặt — cùng quầy, cùng hình thức, huỷ / hoàn tác / hoàn tiền / phiếu thu như mọi
-- dòng. Ý định "thêm vào hoá đơn đang thu" là `lieu_trinh_tra_truoc` (theo lượt,
-- như `luot_vat_tu`): bill_service gom dòng chưa thu vào hoá đơn.
--
--   Số buổi đã trả = Σ quantity dòng `lieu_trinh` của lần thu PAID − Σ đã hoàn
--   (hoàn đang chờ / đã xong). Buổi PHỦ (tra_truoc) không vào hoá đơn, cổng tiền
--   coi như đã thu, không thành nợ khi về.
--
-- Mỗi khi sổ tiền đổi (lần thu đã thu / huỷ, dòng hoàn, hoàn thất bại) → chia lại
-- tiền trả trước cho các buổi (`lieu_trinh_phu_lai`): thiếu tiền thì bỏ phủ buổi
-- CHƯA bắt đầu; buổi ĐÃ làm bằng tiền trả trước mà vẫn vượt → từ chối cả lệnh
-- (#16: không hoàn tác lần thu / không hoàn tiền quá số buổi chưa dùng).
--
-- Chạy lại được.

-- ── 1. Ý định trả trước của một lượt ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lieu_trinh_tra_truoc (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id      uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id       uuid NOT NULL,
    lieu_trinh_id  uuid NOT NULL,
    so_buoi        integer NOT NULL CHECK (so_buoi BETWEEN 1 AND 200),
    don_gia        numeric(12, 0) NOT NULL CHECK (don_gia > 0),
    chon_boi       uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    chon_luc       timestamptz NOT NULL DEFAULT now(),
    bo_boi         uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    bo_luc         timestamptz,
    CONSTRAINT lieu_trinh_tra_truoc_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE CASCADE,
    CONSTRAINT lieu_trinh_tra_truoc_lt_fk FOREIGN KEY (clinic_id, lieu_trinh_id)
        REFERENCES public.lieu_trinh (clinic_id, id) ON DELETE RESTRICT
);
-- Không chỉ mục duy nhất theo (lượt, liệu trình): dòng ĐÃ THU vẫn sống (bo_luc
-- rỗng) và khách có thể trả thêm lần nữa trong cùng lượt. "Một dòng đang chọn"
-- do lệnh giữ (khoá lượt + khoá dòng liệu trình).
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_tra_truoc_luot
    ON public.lieu_trinh_tra_truoc (clinic_id, visit_id) WHERE bo_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_lieu_trinh_tra_truoc_lt
    ON public.lieu_trinh_tra_truoc (clinic_id, lieu_trinh_id);
COMMENT ON TABLE public.lieu_trinh_tra_truoc IS
'Trả trước k buổi liệu trình vào hoá đơn dịch vụ của lượt (08/10/2026). Tiền là dòng payment_bill_line source_type = lieu_trinh. Bỏ = đóng dấu bo_luc.';

ALTER TABLE public.lieu_trinh_tra_truoc ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lieu_trinh_tra_truoc_select_own_clinic ON public.lieu_trinh_tra_truoc;
CREATE POLICY lieu_trinh_tra_truoc_select_own_clinic ON public.lieu_trinh_tra_truoc
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.lieu_trinh_tra_truoc TO service_role;

DROP TRIGGER IF EXISTS trg_notify_lieu_trinh_tra_truoc ON public.lieu_trinh_tra_truoc;
CREATE TRIGGER trg_notify_lieu_trinh_tra_truoc
    AFTER INSERT OR UPDATE OR DELETE ON public.lieu_trinh_tra_truoc
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- ── 2. Hoá đơn: loại dòng mới `lieu_trinh` ─────────────────────────────────
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_source_type_check;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_source_type_check
    CHECK (source_type = ANY (ARRAY['exam', 'service_order', 'prescription',
                                    'phu_thu', 'vat_tu', 'lieu_trinh']));

ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_kind_khop_nguon;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_kind_khop_nguon
    CHECK (
        (kind = 'thuoc' AND source_type = 'prescription')
        OR (kind = 'dich_vu'
            AND source_type IN ('exam', 'service_order', 'phu_thu', 'vat_tu',
                                'lieu_trinh'))
    ) NOT VALID;
COMMENT ON CONSTRAINT payment_bill_line_kind_khop_nguon
    ON public.payment_bill_line IS
    'Tiền thuốc và tiền dịch vụ thu riêng hẳn (01/10/2026): dòng thuốc chỉ nằm trong lần thu thuốc; dòng khám / chỉ định / phụ thu / vật tư / trả trước liệu trình chỉ nằm trong lần thu dịch vụ. NOT VALID — canh dòng ghi mới, không đụng lịch sử.';

-- Chép nguyên 20261006200003, thêm 'lieu_trinh': một ý định trả trước chỉ nằm
-- trong MỘT lần thu đang giữ phủ.
CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam', 'phu_thu', 'vat_tu',
                                  'lieu_trinh') THEN
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'payment_bill_line_phu|' || NEW.clinic_id::text || '|' || NEW.source_type
        || '|' || NEW.source_id, 0));
    SELECT bl.payment_cycle_id INTO trung
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
     WHERE bl.clinic_id = NEW.clinic_id
       AND bl.source_type = NEW.source_type
       AND bl.source_id = NEW.source_id
       AND bl.billing_owner = 'CLINIC'
       AND c.status IN ('PENDING_VERIFICATION', 'PAID')
       -- Tiền khám đã HOÀN HẾT (06/10/2026, E5/E7) không còn giữ phủ.
       AND NOT (bl.source_type = 'exam' AND coalesce((
               SELECT sum(rl.quantity)
                 FROM public.payment_refund_line rl
                 JOIN public.payment_refund r
                   ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
                WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
                  AND r.status IN ('PENDING', 'COMPLETED')), 0) >= bl.quantity)
     LIMIT 1;
    IF trung IS NOT NULL THEN
        RAISE EXCEPTION
            'payment_bill_line: % % đã nằm trong lần thu % — không thu hai lần',
            NEW.source_type, NEW.source_id, trung
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'payment_bill_line_mot_lan_phu';
    END IF;
    RETURN NEW;
END $$;

-- Buổi đang dùng tiền trả trước KHÔNG thu lẻ lần nữa (hoá đơn đã bỏ nó; lưới
-- cuối cho đường ghi đến muộn). Khoá dòng buổi FOR SHARE: phủ lại song song phải đợi.
CREATE OR REPLACE FUNCTION public.payment_bill_line_khong_thu_buoi_da_tra()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NEW.source_type <> 'service_order' OR NEW.billing_owner <> 'CLINIC' THEN
        RETURN NEW;
    END IF;
    PERFORM 1 FROM public.lieu_trinh_buoi b
     WHERE b.clinic_id = NEW.clinic_id
       AND b.service_order_id::text = NEW.source_id
       AND b.go_luc IS NULL AND b.tra_truoc
       FOR SHARE;
    IF FOUND THEN
        RAISE EXCEPTION
            'payment_bill_line: buổi này đã trả trước trong liệu trình — không thu lẻ'
            USING ERRCODE = 'check_violation',
                  CONSTRAINT = 'payment_bill_line_buoi_da_tra_truoc';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_payment_bill_line_khong_thu_buoi_da_tra ON public.payment_bill_line;
CREATE TRIGGER trg_payment_bill_line_khong_thu_buoi_da_tra
    BEFORE INSERT ON public.payment_bill_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_bill_line_khong_thu_buoi_da_tra();

-- ── 3. Sổ tiền thật: số buổi đã trả (thay bản 0 của B1) ────────────────────
CREATE OR REPLACE FUNCTION public.lieu_trinh_so_buoi_da_tra(p_clinic uuid, p_lt uuid)
RETURNS integer
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT coalesce(sum(bl.quantity - coalesce(h.da_hoan, 0)), 0)::integer
      FROM public.lieu_trinh_tra_truoc t
      JOIN public.payment_bill_line bl
        ON bl.clinic_id = t.clinic_id AND bl.source_type = 'lieu_trinh'
       AND bl.source_id = t.id::text AND bl.billing_owner = 'CLINIC'
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
       AND c.status = 'PAID'
      LEFT JOIN LATERAL (
          SELECT sum(rl.quantity) AS da_hoan
            FROM public.payment_refund_line rl
            JOIN public.payment_refund r
              ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
           WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
             AND r.status IN ('PENDING', 'COMPLETED')
      ) h ON true
     WHERE t.clinic_id = p_clinic AND t.lieu_trinh_id = p_lt;
$$;

-- ── 4. Gác ý định trả trước ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.lieu_trinh_tra_truoc_gac()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt record;
    trung uuid;
    da_dat integer;
BEGIN
    -- Hai quầy cùng bấm trả trước một liệu trình → xếp hàng sau dòng liệu trình.
    SELECT * INTO lt FROM public.lieu_trinh
     WHERE clinic_id = NEW.clinic_id AND id = NEW.lieu_trinh_id FOR UPDATE;
    IF TG_OP = 'UPDATE' AND (
           NEW.so_buoi IS DISTINCT FROM OLD.so_buoi
           OR NEW.don_gia IS DISTINCT FROM OLD.don_gia
           OR (NEW.bo_luc IS NOT NULL AND OLD.bo_luc IS NULL)) THEN
        SELECT bl.payment_cycle_id INTO trung
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = OLD.clinic_id AND bl.source_type = 'lieu_trinh'
           AND bl.source_id = OLD.id::text AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
         LIMIT 1;
        IF trung IS NOT NULL THEN
            RAISE EXCEPTION
                'lieu_trinh_tra_truoc: dòng đã nằm trong lần thu % — hoàn tác lần thu trước khi đổi',
                trung
                USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_tra_truoc_da_thu';
        END IF;
    END IF;
    IF NEW.bo_luc IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF lt.trang_thai = 'DUNG' THEN
        RAISE EXCEPTION 'lieu_trinh_tra_truoc: liệu trình đã dừng — mở lại trước khi trả trước'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_tra_truoc_da_dung';
    END IF;
    IF NEW.don_gia IS DISTINCT FROM lt.don_gia THEN
        RAISE EXCEPTION 'lieu_trinh_tra_truoc: đơn giá phải là đơn giá chốt của liệu trình'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_don_gia_chot';
    END IF;
    -- Đã trả + đang chờ thu (chưa nằm trong lần thu PAID, kể cả đang chờ xác minh
    -- chuyển khoản) + buổi đã thu lẻ + lần này ≤ số buổi.
    SELECT coalesce(sum(t.so_buoi), 0) INTO da_dat
      FROM public.lieu_trinh_tra_truoc t
      -- Lượt đã check-out mà dòng chưa thu: khách không trả — không giữ chỗ nữa.
      JOIN public.visit v
        ON v.clinic_id = t.clinic_id AND v.visit_id = t.visit_id
       AND v.closed_at IS NULL
     WHERE t.clinic_id = NEW.clinic_id AND t.lieu_trinh_id = NEW.lieu_trinh_id
       AND t.bo_luc IS NULL AND t.id <> NEW.id
       AND NOT EXISTS (
           SELECT 1 FROM public.payment_bill_line bl
             JOIN public.payment_cycle c
               ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
            WHERE bl.clinic_id = t.clinic_id AND bl.source_type = 'lieu_trinh'
              AND bl.source_id = t.id::text
              AND c.status = 'PAID');
    da_dat := da_dat + public.lieu_trinh_so_buoi_da_tra(NEW.clinic_id, NEW.lieu_trinh_id)
        + (SELECT count(*) FROM public.lieu_trinh_buoi b
            WHERE b.clinic_id = NEW.clinic_id AND b.lieu_trinh_id = NEW.lieu_trinh_id
              AND b.go_luc IS NULL AND NOT b.tra_truoc
              AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id));
    IF da_dat + NEW.so_buoi > lt.so_buoi THEN
        RAISE EXCEPTION 'lieu_trinh_tra_truoc: liệu trình % buổi, đã trả / đang chờ thu % buổi — chỉ trả trước thêm được % buổi',
            lt.so_buoi, da_dat, greatest(lt.so_buoi - da_dat, 0)
            USING ERRCODE = 'check_violation', CONSTRAINT = 'lieu_trinh_tra_vuot';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_tra_truoc_gac ON public.lieu_trinh_tra_truoc;
CREATE TRIGGER trg_lieu_trinh_tra_truoc_gac
    BEFORE INSERT OR UPDATE ON public.lieu_trinh_tra_truoc
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_tra_truoc_gac();

-- ── 5. Sổ tiền đổi → chia lại tiền trả trước cho các buổi ──────────────────
-- Liệu trình chạm bởi các dòng `lieu_trinh` của một lần thu.
CREATE OR REPLACE FUNCTION public.lieu_trinh_cua_lan_thu(p_clinic uuid, p_cycle uuid)
RETURNS SETOF uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT DISTINCT t.lieu_trinh_id
      FROM public.payment_bill_line bl
      JOIN public.lieu_trinh_tra_truoc t
        ON t.clinic_id = bl.clinic_id AND t.id::text = bl.source_id
     WHERE bl.clinic_id = p_clinic AND bl.payment_cycle_id = p_cycle
       AND bl.source_type = 'lieu_trinh'
     ORDER BY 1;
$$;

CREATE OR REPLACE FUNCTION public.lieu_trinh_tinh_lai_theo_lan_thu(p_clinic uuid, p_cycle uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt uuid;
BEGIN
    FOR lt IN SELECT public.lieu_trinh_cua_lan_thu(p_clinic, p_cycle) LOOP
        PERFORM 1 FROM public.lieu_trinh WHERE clinic_id = p_clinic AND id = lt
           FOR UPDATE;
        PERFORM public.lieu_trinh_tinh_lai(p_clinic, lt);
    END LOOP;
END $$;

-- (a) Lần thu đổi trạng thái (xác minh chuyển khoản → PAID, huỷ phiếu → VOIDED).
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_doi_lan_thu()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.kind = 'dich_vu' THEN
        PERFORM public.lieu_trinh_tinh_lai_theo_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_doi_lan_thu ON public.payment_cycle;
CREATE TRIGGER trg_lieu_trinh_sau_doi_lan_thu
    AFTER UPDATE OF status ON public.payment_cycle
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION public.lieu_trinh_sau_doi_lan_thu();

-- (b) Dòng `lieu_trinh` vừa ghi vào ảnh chụp hoá đơn (lần thu tiền mặt ghi PAID
-- trước rồi mới ghi dòng). HOÃN tới cuối giao dịch: mọi dòng của lần thu (cả
-- buổi hôm nay thu lẻ) đã có mặt → không phủ nhầm buổi đang được thu lẻ.
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_ghi_dong_tra_truoc()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    lt uuid;
BEGIN
    SELECT lieu_trinh_id INTO lt FROM public.lieu_trinh_tra_truoc
     WHERE clinic_id = NEW.clinic_id AND id::text = NEW.source_id;
    IF lt IS NOT NULL THEN
        PERFORM 1 FROM public.lieu_trinh WHERE clinic_id = NEW.clinic_id AND id = lt
           FOR UPDATE;
        PERFORM public.lieu_trinh_tinh_lai(NEW.clinic_id, lt);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_ghi_dong_tra_truoc ON public.payment_bill_line;
CREATE CONSTRAINT TRIGGER trg_lieu_trinh_sau_ghi_dong_tra_truoc
    AFTER INSERT ON public.payment_bill_line
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.source_type = 'lieu_trinh')
    EXECUTE FUNCTION public.lieu_trinh_sau_ghi_dong_tra_truoc();

-- (c) Dòng hoàn tiền của dòng `lieu_trinh` (Q5: dừng giữa chừng, hoàn buổi dư).
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_ghi_dong_hoan()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.payment_bill_line bl
                WHERE bl.clinic_id = NEW.clinic_id AND bl.id = NEW.payment_bill_line_id
                  AND bl.source_type = 'lieu_trinh') THEN
        PERFORM public.lieu_trinh_tinh_lai_theo_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_ghi_dong_hoan ON public.payment_refund_line;
CREATE TRIGGER trg_lieu_trinh_sau_ghi_dong_hoan
    AFTER INSERT ON public.payment_refund_line
    FOR EACH ROW EXECUTE FUNCTION public.lieu_trinh_sau_ghi_dong_hoan();

-- (d) Khoản hoàn đổi trạng thái (thất bại / huỷ → tiền quay lại đã trả).
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_doi_hoan()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.kind = 'dich_vu' THEN
        PERFORM public.lieu_trinh_tinh_lai_theo_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_doi_hoan ON public.payment_refund;
CREATE TRIGGER trg_lieu_trinh_sau_doi_hoan
    AFTER UPDATE OF status ON public.payment_refund
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION public.lieu_trinh_sau_doi_hoan();

-- ── 6. Bất biến cho bộ canh gác (canh_gac) + mô phỏng ──────────────────────
--   PHU_VUOT   buổi đang dùng tiền trả trước > số buổi đã trả (net hoàn);
--   AM         đã hoàn nhiều hơn đã thu (số buổi đã trả âm);
--   THU_TRUNG  buổi dùng tiền trả trước mà vẫn có dòng thu lẻ giữ phủ;
--   VUOT_KE_HOACH  đã trả + đã thu lẻ > số buổi kế hoạch.
CREATE OR REPLACE FUNCTION public.bat_bien_lieu_trinh(p_clinic_id uuid)
RETURNS TABLE (lieu_trinh_id uuid, loai text, chi_tiet text)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    WITH lt AS (
        SELECT l.id, l.so_buoi,
               public.lieu_trinh_so_buoi_da_tra(l.clinic_id, l.id) AS da_tra,
               (SELECT count(*) FROM public.lieu_trinh_buoi b
                 WHERE b.lieu_trinh_id = l.id AND b.go_luc IS NULL AND b.tra_truoc)
                   AS phu,
               (SELECT count(*) FROM public.lieu_trinh_buoi b
                 WHERE b.lieu_trinh_id = l.id AND b.go_luc IS NULL AND b.tra_truoc
                   AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id))
                   AS phu_trung,
               (SELECT count(*) FROM public.lieu_trinh_buoi b
                 WHERE b.lieu_trinh_id = l.id AND b.go_luc IS NULL AND NOT b.tra_truoc
                   AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id))
                   AS tra_le
          FROM public.lieu_trinh l
         WHERE l.clinic_id = p_clinic_id
           AND (EXISTS (SELECT 1 FROM public.lieu_trinh_tra_truoc t
                         WHERE t.clinic_id = l.clinic_id AND t.lieu_trinh_id = l.id)
                OR EXISTS (SELECT 1 FROM public.lieu_trinh_buoi b
                            WHERE b.lieu_trinh_id = l.id AND b.tra_truoc))
    )
    SELECT id, 'PHU_VUOT', format('%s buổi dùng tiền trả trước > %s buổi đã trả', phu, da_tra)
      FROM lt WHERE phu > da_tra
    UNION ALL
    SELECT id, 'AM', format('số buổi đã trả âm (%s)', da_tra) FROM lt WHERE da_tra < 0
    UNION ALL
    SELECT id, 'THU_TRUNG', format('%s buổi dùng tiền trả trước vẫn có dòng thu lẻ', phu_trung)
      FROM lt WHERE phu_trung > 0
    UNION ALL
    SELECT id, 'VUOT_KE_HOACH',
           format('đã trả %s + thu lẻ %s > %s buổi kế hoạch', da_tra, tra_le, so_buoi)
      FROM lt WHERE da_tra + tra_le > so_buoi;
$$;
COMMENT ON FUNCTION public.bat_bien_lieu_trinh(uuid) IS
'Bất biến tiền liệu trình (08/10/2026): PHU_VUOT · AM · THU_TRUNG · VUOT_KE_HOACH. Rỗng = sổ khớp. Bộ canh gác cộng vào TIEN_CHI_DINH.';
