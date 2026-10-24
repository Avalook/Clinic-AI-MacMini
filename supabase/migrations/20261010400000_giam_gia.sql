-- GIẢM GIÁ Ở QUẦY THU (Tuyền chốt 09/10/2026) — kiểu KiotViet.
--
-- Hai kiểu: % hoặc số tiền. Hai phạm vi: một DÒNG hoá đơn, hoặc cả HOÁ ĐƠN
-- (lượt, loại tiền). Giảm dòng trước, giảm hoá đơn sau — % hoá đơn tính trên tổng
-- đã trừ giảm dòng; phần giảm hoá đơn chia theo tỉ lệ vào các dòng
-- (`bill_service.ap_giam_gia`). Người thu tiền đúng loại bấm được, không giới
-- hạn (kể cả 100%); lý do chữ tự do, bắt buộc (ép ở service — xem cuối mục 1).
--
-- Ý định giảm là một dòng `giam_gia` CHƯA DÙNG (payment_cycle_id rỗng). Lúc thu,
-- cùng giao dịch: ảnh chụp dòng hoá đơn ghi `giam` từng dòng, và giảm giá được
-- GẮN vào lần thu (`payment_cycle_id`, `so_tien_ap`). Lần thu bị huỷ / hoàn tác /
-- huỷ lần chờ → giảm giá trả về CHƯA DÙNG (áp lại được khi thu lại).
--
--   payment_bill_line.line_total = số SAU giảm (phải thu); line_total + giam =
--   round(unit_price × quantity). Mọi chỗ đang cộng line_total (hoàn tiền, tiền
--   thừa, nợ, tiền của chỉ định, báo cáo) tự đúng theo số đã thu thật.
--
-- Chạy lại được.

-- ── 1. Bảng giảm giá — chỉ thêm ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.giam_gia (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('thuoc', 'dich_vu')),
    pham_vi          text NOT NULL CHECK (pham_vi IN ('DONG', 'HOA_DON')),
    source_type      text,
    source_id        text,
    kieu             text NOT NULL CHECK (kieu IN ('PHAN_TRAM', 'SO_TIEN')),
    gia_tri          numeric(14, 2) NOT NULL,
    -- Lý do: KHÔNG đặt CHECK độ dài ở đây. Bản che dữ liệu staging
    -- (scripts/staging-che-du-lieu.sql) thay chữ tự do — một CHECK độ dài sẽ làm
    -- nạp staging mỗi đêm dừng. Service ép 1–500 ký tự.
    ly_do            text NOT NULL,
    tao_boi          uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    tao_luc          timestamptz NOT NULL DEFAULT now(),
    huy_luc          timestamptz,
    huy_boi          uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ly_do_huy        text,
    payment_cycle_id uuid REFERENCES public.payment_cycle (payment_cycle_id)
                         ON DELETE RESTRICT,
    so_tien_ap       numeric(14, 0) CHECK (so_tien_ap >= 0),
    CONSTRAINT giam_gia_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT,
    CONSTRAINT giam_gia_gia_tri_hop_le CHECK (
        gia_tri > 0
        AND (kieu <> 'PHAN_TRAM' OR gia_tri <= 100)
        AND (kieu <> 'SO_TIEN' OR gia_tri = trunc(gia_tri))),
    -- Nguồn (dòng) có khi và chỉ khi giảm theo DÒNG.
    CONSTRAINT giam_gia_nguon_theo_pham_vi CHECK (
        (pham_vi = 'DONG') = (source_type IS NOT NULL AND source_id IS NOT NULL)
        AND (pham_vi = 'DONG' OR (source_type IS NULL AND source_id IS NULL))),
    CONSTRAINT giam_gia_gan_di_cung CHECK (
        (payment_cycle_id IS NULL) = (so_tien_ap IS NULL)),
    -- Không huỷ được giảm giá đang gắn một lần thu (hoàn tác lần thu trước).
    CONSTRAINT giam_gia_khong_huy_khi_da_gan CHECK (
        huy_luc IS NULL OR payment_cycle_id IS NULL),
    CONSTRAINT giam_gia_huy_di_cung CHECK (
        (huy_luc IS NULL) = (huy_boi IS NULL))
);

-- Một DÒNG / một HOÁ ĐƠN (lượt, loại) chỉ có MỘT giảm giá đang chờ — lưới cuối
-- cho hai người cùng bấm (lệnh đã khoá lượt + đối chiếu dấu hoá đơn).
CREATE UNIQUE INDEX IF NOT EXISTS uq_giam_gia_dong_dang_cho
    ON public.giam_gia (clinic_id, visit_id, kind, source_type, source_id)
    WHERE pham_vi = 'DONG' AND payment_cycle_id IS NULL AND huy_luc IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_giam_gia_hoa_don_dang_cho
    ON public.giam_gia (clinic_id, visit_id, kind)
    WHERE pham_vi = 'HOA_DON' AND payment_cycle_id IS NULL AND huy_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_giam_gia_luot
    ON public.giam_gia (clinic_id, visit_id, kind) WHERE huy_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_giam_gia_lan_thu
    ON public.giam_gia (clinic_id, payment_cycle_id) WHERE payment_cycle_id IS NOT NULL;
COMMENT ON TABLE public.giam_gia IS
'Giảm giá ở quầy thu (09/10/2026): % hoặc số tiền, theo dòng hoặc cả hoá đơn. Chưa dùng = payment_cycle_id rỗng; thu xong thì gắn lần thu + so_tien_ap. Chỉ thêm: chỉ sửa nhóm cột huỷ và cặp gắn lần thu.';

-- Chỉ thêm: cấm xoá; chỉ sửa nhóm cột huỷ (một lần) và cặp gắn lần thu.
CREATE OR REPLACE FUNCTION public.giam_gia_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'giam_gia là sổ giảm giá — không xoá (hoàn tác = đóng dấu huỷ)'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.id, NEW.clinic_id, NEW.visit_id, NEW.kind, NEW.pham_vi, NEW.source_type,
        NEW.source_id, NEW.kieu, NEW.gia_tri, NEW.ly_do, NEW.tao_boi, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.id, OLD.clinic_id, OLD.visit_id, OLD.kind, OLD.pham_vi, OLD.source_type,
        OLD.source_id, OLD.kieu, OLD.gia_tri, OLD.ly_do, OLD.tao_boi, OLD.tao_luc) THEN
        RAISE EXCEPTION 'giam_gia: chỉ sửa được nhóm cột huỷ và lần thu đã gắn'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.huy_luc IS NOT NULL
       AND (NEW.huy_luc, NEW.huy_boi, NEW.ly_do_huy, NEW.payment_cycle_id, NEW.so_tien_ap)
           IS DISTINCT FROM
           (OLD.huy_luc, OLD.huy_boi, OLD.ly_do_huy, OLD.payment_cycle_id, OLD.so_tien_ap)
    THEN
        RAISE EXCEPTION 'giam_gia: giảm giá đã hoàn tác — không sửa nữa'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_giam_gia_chi_them ON public.giam_gia;
CREATE TRIGGER trg_giam_gia_chi_them
    BEFORE UPDATE OR DELETE ON public.giam_gia
    FOR EACH ROW EXECUTE FUNCTION public.giam_gia_chi_them();

-- Khoá cycle để việc gắn không đua với huỷ lần thu. FK id đơn lẻ không
-- bảo vệ tenant/lượt/loại khi service_role bypass RLS.
CREATE OR REPLACE FUNCTION public.giam_gia_gan_dung_lan_thu()
RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
DECLARE c record;
BEGIN
    IF NEW.payment_cycle_id IS NOT NULL THEN
        SELECT clinic_id, visit_id, kind, status INTO c
          FROM public.payment_cycle WHERE payment_cycle_id = NEW.payment_cycle_id
          FOR UPDATE;
        IF c.clinic_id IS DISTINCT FROM NEW.clinic_id
           OR c.visit_id IS DISTINCT FROM NEW.visit_id
           OR c.kind IS DISTINCT FROM NEW.kind
           OR c.status NOT IN ('PENDING_VERIFICATION', 'PAID') THEN
            RAISE EXCEPTION 'Giảm giá phải gắn lần thu cùng lượt, cơ sở, loại và còn hiệu lực'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_giam_gia_gan_dung_lan_thu ON public.giam_gia;
CREATE TRIGGER trg_giam_gia_gan_dung_lan_thu
    BEFORE INSERT OR UPDATE ON public.giam_gia
    FOR EACH ROW EXECUTE FUNCTION public.giam_gia_gan_dung_lan_thu();

ALTER TABLE public.giam_gia ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS giam_gia_select_own_clinic ON public.giam_gia;
CREATE POLICY giam_gia_select_own_clinic ON public.giam_gia
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.giam_gia TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.giam_gia TO service_role;

-- Quầy kia / màn lịch sử thấy ngay (LIVE_TABLES trong RealtimeRefresher.tsx).
DROP TRIGGER IF EXISTS trg_notify_giam_gia ON public.giam_gia;
CREATE TRIGGER trg_notify_giam_gia
    AFTER INSERT OR UPDATE OR DELETE ON public.giam_gia
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- ── 2. Ảnh chụp dòng hoá đơn: cột `giam` ───────────────────────────────────
ALTER TABLE public.payment_bill_line
    ADD COLUMN IF NOT EXISTS giam numeric(14, 0) NOT NULL DEFAULT 0;
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_giam_khong_am;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_giam_khong_am CHECK (giam >= 0);
-- Dòng đối tác tự thu không phải khoản của phòng khám — không giảm.
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_doi_tac_khong_giam;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_doi_tac_khong_giam
    CHECK (billing_owner = 'CLINIC' OR giam = 0);
-- Phải thu + giảm = tiền gốc (đơn giá × số lượng, làm tròn tới 1đ). NOT VALID:
-- canh dòng ghi mới, không đụng lịch sử.
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_giam_khop_goc;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_giam_khop_goc
    CHECK (line_total IS NULL OR line_total + giam = round(unit_price * quantity))
    NOT VALID;
COMMENT ON COLUMN public.payment_bill_line.giam IS
    'Tiền giảm của dòng lúc thu (09/10/2026). line_total là số SAU giảm.';

-- ── 3. Tổng giảm của một lần thu khớp tổng giảm giá đã gắn (hoãn tới COMMIT) ─
CREATE OR REPLACE FUNCTION public.giam_gia_kiem_tong_lan_thu(p_clinic uuid, p_cycle uuid)
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_status text;
    v_dong numeric;
    v_giam numeric;
BEGIN
    IF p_cycle IS NULL THEN
        RETURN;
    END IF;
    SELECT status INTO v_status FROM public.payment_cycle
     WHERE clinic_id = p_clinic AND payment_cycle_id = p_cycle;
    -- Lần thu đã huỷ / huỷ chờ: giảm giá đã trả về, ảnh chụp giữ nguyên — không so.
    IF v_status IS NULL OR v_status NOT IN ('PENDING_VERIFICATION', 'PAID') THEN
        RETURN;
    END IF;
    SELECT coalesce(sum(giam), 0) INTO v_dong FROM public.payment_bill_line
     WHERE clinic_id = p_clinic AND payment_cycle_id = p_cycle;
    SELECT coalesce(sum(so_tien_ap), 0) INTO v_giam FROM public.giam_gia
     WHERE clinic_id = p_clinic AND payment_cycle_id = p_cycle;
    IF v_dong <> v_giam THEN
        RAISE EXCEPTION 'Lần thu %: tổng giảm các dòng % ≠ tổng giảm giá đã gắn %',
            p_cycle, v_dong, v_giam
            USING ERRCODE = 'check_violation',
                  CONSTRAINT = 'giam_gia_tong_khop_lan_thu';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION public.giam_gia_tong_khop_tu_dong()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM public.giam_gia_kiem_tong_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_payment_bill_line_giam_tong_khop ON public.payment_bill_line;
CREATE CONSTRAINT TRIGGER trg_payment_bill_line_giam_tong_khop
    AFTER INSERT ON public.payment_bill_line
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.giam_gia_tong_khop_tu_dong();

CREATE OR REPLACE FUNCTION public.giam_gia_tong_khop_tu_giam()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM public.giam_gia_kiem_tong_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    IF TG_OP = 'UPDATE' AND OLD.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id THEN
        PERFORM public.giam_gia_kiem_tong_lan_thu(OLD.clinic_id, OLD.payment_cycle_id);
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_giam_gia_tong_khop ON public.giam_gia;
CREATE CONSTRAINT TRIGGER trg_giam_gia_tong_khop
    AFTER INSERT OR UPDATE ON public.giam_gia
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.giam_gia_tong_khop_tu_giam();

-- ── 4. Lần thu bị huỷ / hoàn tác / huỷ lần chờ → giảm giá trả về chưa dùng ──
-- Hiếm: hoá đơn đã có một giảm giá khác đang chờ cho đúng chỗ ấy (vd thu A có
-- giảm hoá đơn, rồi giảm tiếp phần mới, rồi hoàn tác A) — hai giảm giá cùng chờ
-- một chỗ là không được; cái trả về được ĐÓNG DẤU HUỶ kèm câu giải thích, không
-- làm hỏng lệnh hoàn tác.
CREATE OR REPLACE FUNCTION public.giam_gia_tra_ve_khi_huy_lan_thu()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    g record;
BEGIN
    FOR g IN
        SELECT * FROM public.giam_gia
         WHERE clinic_id = NEW.clinic_id AND payment_cycle_id = NEW.payment_cycle_id
           AND huy_luc IS NULL
         ORDER BY tao_luc, id
         FOR UPDATE
    LOOP
        IF EXISTS (
            SELECT 1 FROM public.giam_gia x
             WHERE x.clinic_id = g.clinic_id AND x.visit_id = g.visit_id
               AND x.kind = g.kind AND x.pham_vi = g.pham_vi
               AND x.source_type IS NOT DISTINCT FROM g.source_type
               AND x.source_id IS NOT DISTINCT FROM g.source_id
               AND x.payment_cycle_id IS NULL AND x.huy_luc IS NULL
               AND x.id <> g.id)
        THEN
            UPDATE public.giam_gia
               SET payment_cycle_id = NULL, so_tien_ap = NULL,
                   huy_luc = now(),
                   huy_boi = coalesce(NEW.closed_by, g.tao_boi),
                   ly_do_huy = 'Tự hoàn tác khi huỷ lần thu: chỗ này đã có giảm giá khác đang chờ'
             WHERE id = g.id;
        ELSE
            UPDATE public.giam_gia
               SET payment_cycle_id = NULL, so_tien_ap = NULL
             WHERE id = g.id;
        END IF;
    END LOOP;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS trg_giam_gia_tra_ve ON public.payment_cycle;
CREATE TRIGGER trg_giam_gia_tra_ve
    AFTER UPDATE OF status ON public.payment_cycle
    FOR EACH ROW
    WHEN (NEW.status IN ('VOIDED', 'CANCELLED') AND OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION public.giam_gia_tra_ve_khi_huy_lan_thu();

-- ── 5. Hoàn tiền dòng CÓ giảm: chỉ tới số đã thu thật ──────────────────────
-- Chép nguyên 20260919000004, đổi đúng một chỗ: dòng có giảm (giam > 0) thì số
-- tiền hoàn = phần LUỸ KẾ của số đã thu (line_total) theo số lượng —
-- round(line_total × (đã hoàn + lần này) / số lượng) − round(line_total × đã
-- hoàn / số lượng). Hoàn hết = đúng line_total, không dư 1đ nào. Dòng không giảm
-- giữ nguyên luật cũ (số lượng × đơn giá).
CREATE OR REPLACE FUNCTION public.payment_refund_line_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    dong record;
    hoan record;
    da_hoan numeric;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment_refund_line chỉ thêm (%)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM public.payment_cycle
      WHERE payment_cycle_id = NEW.payment_cycle_id AND clinic_id = NEW.clinic_id
      FOR UPDATE;
    SELECT payment_cycle_id, status INTO hoan FROM public.payment_refund
     WHERE refund_id = NEW.refund_id AND clinic_id = NEW.clinic_id
     FOR UPDATE;
    IF hoan.payment_cycle_id IS DISTINCT FROM NEW.payment_cycle_id
       OR hoan.status NOT IN ('PENDING', 'COMPLETED') THEN
        RAISE EXCEPTION 'Dòng hoàn phải thuộc đúng lần thu của khoản hoàn còn mở'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT quantity, unit_price, line_total, giam, billing_owner INTO dong
      FROM public.payment_bill_line
     WHERE id = NEW.payment_bill_line_id AND clinic_id = NEW.clinic_id;
    IF dong.billing_owner IS DISTINCT FROM 'CLINIC' OR dong.unit_price IS NULL THEN
        RAISE EXCEPTION 'Chỉ hoàn dòng phòng khám đã thu có giá'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT coalesce(sum(l.quantity), 0) INTO da_hoan
      FROM public.payment_refund_line l
      JOIN public.payment_refund r
        ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
     WHERE l.payment_bill_line_id = NEW.payment_bill_line_id
       AND l.clinic_id = NEW.clinic_id
       AND r.status IN ('PENDING', 'COMPLETED');
    IF coalesce(dong.giam, 0) = 0 THEN
        IF NEW.amount <> round(NEW.quantity * dong.unit_price) THEN
            RAISE EXCEPTION 'Số tiền hoàn phải = số lượng × đơn giá ảnh chụp'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.amount <> round(dong.line_total * (da_hoan + NEW.quantity) / dong.quantity)
                        - round(dong.line_total * da_hoan / dong.quantity) THEN
        RAISE EXCEPTION 'Số tiền hoàn của dòng có giảm giá phải theo số đã thu (sau giảm)'
            USING ERRCODE = 'check_violation';
    END IF;
    IF da_hoan + NEW.quantity > dong.quantity THEN
        RAISE EXCEPTION 'Hoàn vượt số đã thu của dòng (% + % > %)',
            da_hoan, NEW.quantity, dong.quantity
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
