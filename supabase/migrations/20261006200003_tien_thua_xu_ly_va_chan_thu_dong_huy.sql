-- PHẦN E — LUẬT TIỀN KHI BỎ / HOÀN TÁC CHỈ ĐỊNH (Tuyền chốt 06/10/2026).
--
-- 1. `tien_thua_giu_lai` (E2a): khách không lấy lại tiền thừa → quầy ghi "giữ
--    lại" kèm lý do, ai, lúc nào; huỷ được (hoàn tác) tới khi check-out. Một
--    lượt chỉ MỘT lần giữ lại còn hiệu lực (chỉ mục duy nhất từng phần) — hai
--    máy bấm cùng lúc thì một máy thua. Check-out còn tiền thừa mà chưa hoàn /
--    chưa giữ lại thì máy chủ chặn (services/tien_thua_service.py).
--
-- 2. KHÔNG THU DÒNG ĐÃ HUỶ (E4): trigger BEFORE INSERT trên `payment_bill_line`
--    từ chối dòng chỉ định (và phụ thu của chỉ định) đã bỏ / không làm. Khoá
--    dòng chỉ định FOR SHARE → lệnh bỏ chỉ định đang chạy song song phải đợi
--    (hoặc lệnh thu đợi lệnh bỏ): không bao giờ có dòng thu trỏ vào chỉ định
--    đã huỷ, kể cả một đường ghi mới sau này quên khoá lượt.
--
-- 3. TIỀN KHÁM ĐÃ HOÀN HẾT KHÔNG CÒN "PHỦ" (E5/E7): bỏ dịch vụ khám đã thu →
--    tiền thừa → quầy hoàn → tick lại (hoàn tác) phải thành NỢ MỚI. Trước đây
--    lần thu PAID đã hoàn hết vẫn giữ phủ nên khoản ấy kẹt (không nợ, không
--    thu lại được). Chỉ áp cho nguồn `exam` — chỉ định hoàn tác sau khi đã hoàn
--    thì máy chủ tạo chỉ định MỚI (nguồn mới) nên không cần nới ở đây.
--
-- 4. Bất biến `bat_bien_tien_chi_dinh` thêm loại KET_DA_HOAN: chỉ định CÒN HIỆU
--    LỰC mà phần đã thu đã hoàn hết = kẹt (phải là khoản chưa thu, hoặc bỏ đi).
--
-- Chạy lại được.

-- ── 1. Giữ lại tiền thừa ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.tien_thua_giu_lai (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id   uuid NOT NULL,
    so_tien    bigint NOT NULL CHECK (so_tien > 0),
    ly_do      text NOT NULL CHECK (length(btrim(ly_do)) BETWEEN 3 AND 500),
    boi        uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    luc        timestamptz NOT NULL DEFAULT now(),
    huy_luc    timestamptz,
    huy_boi    uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    ly_do_huy  text CHECK (ly_do_huy IS NULL OR length(ly_do_huy) <= 500)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tien_thua_giu_lai_song
    ON public.tien_thua_giu_lai (clinic_id, visit_id) WHERE huy_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_tien_thua_giu_lai_luc
    ON public.tien_thua_giu_lai (clinic_id, luc);

COMMENT ON TABLE public.tien_thua_giu_lai IS
'Tiền thừa khách không lấy lại (06/10/2026, E2a): lý do, ai, lúc nào; huỷ = hoàn tác (huy_luc). Một lần còn hiệu lực mỗi lượt.';

ALTER TABLE public.tien_thua_giu_lai ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tien_thua_giu_lai_select_own_clinic ON public.tien_thua_giu_lai;
CREATE POLICY tien_thua_giu_lai_select_own_clinic ON public.tien_thua_giu_lai
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.tien_thua_giu_lai TO service_role;


-- ── 2. Không thu dòng của chỉ định đã huỷ ──────────────────────────────────
CREATE OR REPLACE FUNCTION public.payment_bill_line_chi_dinh_con_hieu_luc()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    don record;
BEGIN
    IF NEW.source_type = 'service_order' THEN
        SELECT o.exec_status, o.execution_status, o.service_name INTO don
          FROM public.service_order o
         WHERE o.clinic_id = NEW.clinic_id AND o.id::text = NEW.source_id
           FOR SHARE;
    ELSIF NEW.source_type = 'phu_thu' THEN
        SELECT o.exec_status, o.execution_status, o.service_name INTO don
          FROM public.luot_phu_thu p
          JOIN public.service_order o
            ON o.clinic_id = p.clinic_id AND o.id = p.service_order_id
         WHERE p.clinic_id = NEW.clinic_id AND p.id::text = NEW.source_id
           FOR SHARE OF o;
    ELSE
        RETURN NEW;
    END IF;
    IF FOUND AND (don.exec_status IN ('cancelled', 'not_performed', 'draft')
                  OR coalesce(don.execution_status, '') = 'CANCELLED') THEN
        RAISE EXCEPTION
            'payment_bill_line: chỉ định “%” đã bỏ / không làm — không thu được',
            don.service_name
            USING ERRCODE = 'check_violation',
                  CONSTRAINT = 'payment_bill_line_chi_dinh_con_hieu_luc';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_payment_bill_line_chi_dinh_con_hieu_luc ON public.payment_bill_line;
CREATE TRIGGER trg_payment_bill_line_chi_dinh_con_hieu_luc
    BEFORE INSERT ON public.payment_bill_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_bill_line_chi_dinh_con_hieu_luc();


-- ── 3. Tiền khám đã hoàn hết không còn phủ ─────────────────────────────────
CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam', 'phu_thu', 'vat_tu') THEN
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


-- ── 4. Bất biến: thêm KET_DA_HOAN ──────────────────────────────────────────
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
     WHERE g.co_chi_dinh AND NOT g.da_bo AND g.so_dong_con > 1
    UNION ALL
    -- 06/10/2026 (E5): còn hiệu lực mà đã hoàn hết = kẹt (không nợ, không thu
    -- lại được, cửa làm chặn) — phải thành khoản chưa thu hoặc bỏ đi.
    SELECT g.visit_id, 'KET_DA_HOAN',
           format('chỉ định %s còn hiệu lực nhưng đã hoàn hết %s', g.order_id, g.da_hoan)
      FROM gan g
     WHERE g.co_chi_dinh AND NOT g.da_bo AND g.da_thu > 0 AND g.da_hoan >= g.da_thu;
$$;
