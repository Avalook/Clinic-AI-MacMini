-- Liệu trình — quầy thu đúng số tiền khi huỷ buổi / dừng liệu trình (31/10/2026).
--
-- Tái hiện bằng test thật (10 ca a…e3, `test_lieu_trinh_tien_dung_db.py`):
--
--   (4) Huỷ một buổi LẺ ĐÃ THU của gói → tiền thành "tiền thừa" của lượt, gói tụt
--       về "chưa trả 1 buổi" và đòi thu lại. Tuyền chốt: tiền GIỮ LẠI TRONG GÓI
--       (thành trả trước 1 buổi). Không đổi sổ tiền (không dòng thu / hoàn mới):
--       dòng thu lẻ của chỉ định đã huỷ được TÍNH là 1 buổi đã trả của liệu trình
--       nó vừa rời (`lieu_trinh_dong_giu`). Hoàn tác huỷ → chỉ định sống lại, gắn
--       lại buổi lẻ như cũ, dòng ấy thôi được tính — tự về đúng như trước.
--   (5) [Trả hết] chốt số cứng lúc bấm: huỷ buổi hôm nay trước khi thu → hoá đơn
--       thiếu 1 buổi. Nay lưu CỜ `tra_het`; hoá đơn tính lại số buổi mỗi lần dựng
--       (`lieu_trinh_tra_truoc_so_buoi`), lúc ghi dòng hoá đơn thì chốt vào dòng.
--   (2) Dừng liệu trình: buổi đã kê CHƯA BẮT ĐẦU, chưa thu lẻ rời gói (go_cach
--       'DUNG', bỏ phủ) — quầy không còn tính buổi nào là "buổi của liệu trình
--       đã dừng"; mở lại / hoàn tác dừng gắn lại đúng các buổi ấy (phủ lại nếu
--       còn tiền). Trả trước chưa thu của liệu trình đã dừng không vào hoá đơn.
--
-- Không sửa dữ liệu cũ (trigger chỉ chạy khi có lệnh mới). Chạy lại được.

-- ── 1. Cột / giá trị mới ────────────────────────────────────────────────────
ALTER TABLE public.lieu_trinh_buoi
    DROP CONSTRAINT IF EXISTS lieu_trinh_buoi_go_cach_check;
ALTER TABLE public.lieu_trinh_buoi
    ADD CONSTRAINT lieu_trinh_buoi_go_cach_check
    CHECK (go_cach IN ('TU_DONG', 'TAY', 'CHUYEN', 'DUNG'));

ALTER TABLE public.lieu_trinh_tra_truoc
    ADD COLUMN IF NOT EXISTS tra_het boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.lieu_trinh_tra_truoc.tra_het IS
'[Trả hết]: số buổi tính lại mỗi lần dựng hoá đơn (lieu_trinh_tra_truoc_so_buoi); lúc ghi dòng hoá đơn thì chốt vào so_buoi.';

-- ── 2. Tiền buổi lẻ đã thu GIỮ LẠI trong gói ────────────────────────────────
-- Liệu trình đang giữ tiền của MỘT chỉ định: chỉ định không còn sống (huỷ /
-- không làm / khách bỏ) và lần gắn MỚI NHẤT của nó bị gỡ TỰ ĐỘNG (tức là do
-- chính việc huỷ) — gỡ tay / chuyển / dừng liệu trình thì không giữ. NULL = không.
CREATE OR REPLACE FUNCTION public.lieu_trinh_giu_tien_cua_chi_dinh(p_clinic uuid, p_order uuid)
RETURNS uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT CASE WHEN x.go_cach = 'TU_DONG' THEN x.lieu_trinh_id END
      FROM (SELECT b.lieu_trinh_id, b.go_cach
              FROM public.lieu_trinh_buoi b
             WHERE b.clinic_id = p_clinic AND b.service_order_id = p_order
             ORDER BY (b.go_luc IS NULL) DESC, b.gan_luc DESC, b.id DESC
             LIMIT 1) x
      JOIN public.service_order o ON o.clinic_id = p_clinic AND o.id = p_order
     WHERE NOT public.lieu_trinh_chi_dinh_song(
               o.exec_status, o.execution_status, o.selection_status);
$$;

-- Dòng thu lẻ (đã thu, còn chưa hoàn) mà liệu trình đang giữ — mỗi chỉ định là
-- 1 buổi đã trả. Quầy liệt kê để hoàn khi khách dừng.
CREATE OR REPLACE FUNCTION public.lieu_trinh_dong_giu(p_clinic uuid, p_lt uuid)
RETURNS TABLE (giu_order_id uuid, giu_line_id uuid, giu_cycle_id uuid,
               giu_visit_id uuid, giu_con numeric, giu_don_gia numeric,
               giu_paid_at timestamptz)
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT o.id, bl.id, bl.payment_cycle_id, bl.visit_id,
           bl.quantity - coalesce(h.sl, 0), bl.unit_price, c.paid_at
      FROM (SELECT DISTINCT b.service_order_id AS oid
              FROM public.lieu_trinh_buoi b
             WHERE b.clinic_id = p_clinic AND b.lieu_trinh_id = p_lt
               AND b.go_cach = 'TU_DONG') g
      JOIN public.service_order o ON o.clinic_id = p_clinic AND o.id = g.oid
      JOIN public.payment_bill_line bl
        ON bl.clinic_id = p_clinic AND bl.source_type = 'service_order'
       AND bl.source_id = o.id::text AND bl.billing_owner = 'CLINIC'
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
       AND c.status = 'PAID'
      LEFT JOIN LATERAL (
          SELECT sum(rl.quantity) AS sl
            FROM public.payment_refund_line rl
            JOIN public.payment_refund r
              ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
           WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
             AND r.status IN ('PENDING', 'COMPLETED')
      ) h ON true
     WHERE public.lieu_trinh_giu_tien_cua_chi_dinh(p_clinic, o.id) = p_lt
       AND bl.quantity - coalesce(h.sl, 0) > 0;
$$;

-- Số buổi ĐÃ TRẢ = trả trước (net hoàn) + buổi lẻ đã thu đang giữ trong gói.
-- MỘT hàm cho mọi luật đọc nó (phủ buổi, trạng thái, chặn trả vượt, bất biến).
CREATE OR REPLACE FUNCTION public.lieu_trinh_so_buoi_da_tra(p_clinic uuid, p_lt uuid)
RETURNS integer
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT (
        SELECT coalesce(sum(bl.quantity - coalesce(h.da_hoan, 0)), 0)
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
         WHERE t.clinic_id = p_clinic AND t.lieu_trinh_id = p_lt
    )::integer
    + (SELECT count(DISTINCT g.giu_order_id)
         FROM public.lieu_trinh_dong_giu(p_clinic, p_lt) g)::integer;
$$;

-- Sổ tiền đổi ở lần thu có dòng LẺ của buổi liệu trình (huỷ phiếu, hoàn, xác
-- minh chuyển khoản) cũng phải chia lại tiền trả trước: dòng ấy có thể đang
-- được giữ trong gói.
CREATE OR REPLACE FUNCTION public.lieu_trinh_cua_lan_thu(p_clinic uuid, p_cycle uuid)
RETURNS SETOF uuid
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT DISTINCT x.lt FROM (
        SELECT t.lieu_trinh_id AS lt
          FROM public.payment_bill_line bl
          JOIN public.lieu_trinh_tra_truoc t
            ON t.clinic_id = bl.clinic_id AND t.id::text = bl.source_id
         WHERE bl.clinic_id = p_clinic AND bl.payment_cycle_id = p_cycle
           AND bl.source_type = 'lieu_trinh'
        UNION
        SELECT b.lieu_trinh_id
          FROM public.payment_bill_line bl
          JOIN public.lieu_trinh_buoi b
            ON b.clinic_id = bl.clinic_id
           AND b.service_order_id = CASE
                   WHEN bl.source_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                   THEN bl.source_id::uuid END
         WHERE bl.clinic_id = p_clinic AND bl.payment_cycle_id = p_cycle
           AND bl.source_type = 'service_order'
    ) x
     ORDER BY 1;
$$;

-- Dòng hoàn của dòng trả trước HOẶC của dòng lẻ thuộc buổi liệu trình.
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_ghi_dong_hoan()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.payment_bill_line bl
                WHERE bl.clinic_id = NEW.clinic_id AND bl.id = NEW.payment_bill_line_id
                  AND bl.source_type IN ('lieu_trinh', 'service_order')) THEN
        PERFORM public.lieu_trinh_tinh_lai_theo_lan_thu(NEW.clinic_id, NEW.payment_cycle_id);
    END IF;
    RETURN NULL;
END $$;

-- ── 3. [Trả hết] = cờ, số buổi tính lại ─────────────────────────────────────
-- Số buổi một dòng trả trước CHƯA THU đang đòi: liệu trình đã dừng → 0; chọn
-- số cụ thể → đúng số ấy; [Trả hết] → phần còn trả trước được ở lượt này, CÙNG
-- luật `toi_da_tra_truoc` của quầy (lieu_trinh_tien.py): số buổi − đã trả − đã
-- thu lẻ − đang chờ thu ở lượt khác − buổi của lượt này trong hoá đơn; liệu
-- trình đã làm đủ → 0.
CREATE OR REPLACE FUNCTION public.lieu_trinh_tra_truoc_so_buoi(p_clinic uuid, p_id uuid)
RETURNS integer
LANGUAGE sql STABLE
SET search_path = public
AS $$
    SELECT CASE
        WHEN l.trang_thai = 'DUNG' THEN 0
        WHEN NOT t.tra_het THEN t.so_buoi
        WHEN l.trang_thai = 'XONG' THEN 0
        ELSE greatest(
            l.so_buoi
            - public.lieu_trinh_so_buoi_da_tra(l.clinic_id, l.id)
            - (SELECT count(*) FROM public.lieu_trinh_buoi b
                WHERE b.clinic_id = l.clinic_id AND b.lieu_trinh_id = l.id
                  AND b.go_luc IS NULL AND NOT b.tra_truoc
                  AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id))
            - (SELECT coalesce(sum(t2.so_buoi), 0) FROM public.lieu_trinh_tra_truoc t2
                 JOIN public.visit v
                   ON v.clinic_id = t2.clinic_id AND v.visit_id = t2.visit_id
                  AND v.closed_at IS NULL
                WHERE t2.clinic_id = l.clinic_id AND t2.lieu_trinh_id = l.id
                  AND t2.bo_luc IS NULL AND t2.visit_id <> t.visit_id
                  AND NOT EXISTS (
                      SELECT 1 FROM public.payment_bill_line bl
                        JOIN public.payment_cycle c
                          ON c.clinic_id = bl.clinic_id
                         AND c.payment_cycle_id = bl.payment_cycle_id
                       WHERE bl.clinic_id = t2.clinic_id AND bl.source_type = 'lieu_trinh'
                         AND bl.source_id = t2.id::text AND c.status = 'PAID'))
            - (SELECT count(*) FROM public.lieu_trinh_buoi b
                 JOIN public.service_order o
                   ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
                WHERE b.clinic_id = l.clinic_id AND b.lieu_trinh_id = l.id
                  AND b.go_luc IS NULL AND NOT b.tra_truoc
                  AND o.visit_id = t.visit_id
                  AND NOT public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id)),
            0)::integer
    END
      FROM public.lieu_trinh_tra_truoc t
      JOIN public.lieu_trinh l ON l.clinic_id = t.clinic_id AND l.id = t.lieu_trinh_id
     WHERE t.clinic_id = p_clinic AND t.id = p_id;
$$;

-- Ghi dòng hoá đơn của [Trả hết] → chốt số buổi vào dòng ý định (đối chiếu ảnh
-- chụp khi xác minh chuyển khoản, cộng "đang chờ thu" ở lượt khác).
CREATE OR REPLACE FUNCTION public.lieu_trinh_tra_het_chot_so()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.quantity >= 1 THEN
        UPDATE public.lieu_trinh_tra_truoc
           SET so_buoi = NEW.quantity::integer
         WHERE clinic_id = NEW.clinic_id AND id::text = NEW.source_id
           AND tra_het AND so_buoi <> NEW.quantity::integer;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_tra_het_chot_so ON public.payment_bill_line;
CREATE TRIGGER trg_lieu_trinh_tra_het_chot_so
    BEFORE INSERT ON public.payment_bill_line
    FOR EACH ROW WHEN (NEW.source_type = 'lieu_trinh')
    EXECUTE FUNCTION public.lieu_trinh_tra_het_chot_so();

-- ── 4. Dừng / mở lại: buổi chưa bắt đầu rời gói / về lại gói ──────────────────
-- Dừng: buổi còn gắn, CHƯA bắt đầu (chưa làm, chưa vào phòng) và CHƯA THU LẺ →
-- gỡ (go_cach 'DUNG', bỏ phủ — tiền trả trước về lại gói, hoàn được). Buổi đã
-- thu lẻ ở lại: tiền của nó là tiền của gói. Mở lại (kể cả hoàn tác dừng) →
-- gắn lại đúng các buổi ấy nếu chỉ định còn sống và chưa đi đâu khác.
CREATE OR REPLACE FUNCTION public.lieu_trinh_sau_doi_dung()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    r record;
BEGIN
    IF NEW.dung_luc IS NOT NULL AND OLD.dung_luc IS NULL THEN
        UPDATE public.lieu_trinh_buoi b
           SET go_luc = now(), go_boi = NEW.dung_boi, go_cach = 'DUNG', tra_truoc = false
          FROM public.service_order o
         WHERE b.clinic_id = NEW.clinic_id AND b.lieu_trinh_id = NEW.id
           AND b.go_luc IS NULL
           AND o.clinic_id = b.clinic_id AND o.id = b.service_order_id
           AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
           AND o.exec_status IN ('authorized', 'assigned')
           AND NOT public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id);
        PERFORM public.lieu_trinh_phu_lai(NEW.clinic_id, NEW.id);
    ELSIF NEW.dung_luc IS NULL AND OLD.dung_luc IS NOT NULL THEN
        FOR r IN
            SELECT b.service_order_id
              FROM public.lieu_trinh_buoi b
              JOIN public.service_order o
                ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
             WHERE b.clinic_id = NEW.clinic_id AND b.lieu_trinh_id = NEW.id
               AND b.go_cach = 'DUNG'
               AND public.lieu_trinh_chi_dinh_song(
                       o.exec_status, o.execution_status, o.selection_status)
               AND NOT EXISTS (
                   SELECT 1 FROM public.lieu_trinh_buoi x
                    WHERE x.clinic_id = b.clinic_id
                      AND x.service_order_id = b.service_order_id
                      AND (x.go_luc IS NULL OR x.gan_luc > b.gan_luc))
             ORDER BY b.buoi_so, b.gan_luc
        LOOP
            PERFORM public.lieu_trinh_gan_buoi(
                NEW.clinic_id, NEW.id, r.service_order_id, 'TU_DONG', NULL);
        END LOOP;
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_lieu_trinh_sau_doi_dung ON public.lieu_trinh;
CREATE TRIGGER trg_lieu_trinh_sau_doi_dung
    AFTER UPDATE OF dung_luc ON public.lieu_trinh
    FOR EACH ROW WHEN (OLD.dung_luc IS DISTINCT FROM NEW.dung_luc)
    EXECUTE FUNCTION public.lieu_trinh_sau_doi_dung();

-- ── 5. Quyền: chỉ backend gọi ───────────────────────────────────────────────
REVOKE EXECUTE ON FUNCTION
    public.lieu_trinh_giu_tien_cua_chi_dinh(uuid, uuid),
    public.lieu_trinh_dong_giu(uuid, uuid),
    public.lieu_trinh_tra_truoc_so_buoi(uuid, uuid),
    public.lieu_trinh_tra_het_chot_so(),
    public.lieu_trinh_sau_doi_dung()
FROM PUBLIC, anon;
