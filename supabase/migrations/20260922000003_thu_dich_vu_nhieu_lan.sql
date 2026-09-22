-- Service Lifecycle v1 — Slice 3: thu tiền dịch vụ NHIỀU LẦN (22/09/2026).
--
-- Contract: docs/ai/lifecycle-v1/ClinicAI-FINANCE-GATE-v1.md + CHECKPOINT §3/§5.
-- Không sửa migration lịch sử 20260919000002 (CP2); mọi thay đổi đi tiếp ở đây.
--
-- 1. Chỉ mục "một lần thu sống" tách theo loại:
--      thuoc   — GIỮ NGUYÊN luật cũ: tối đa một PENDING_VERIFICATION/PAID.
--      dich_vu — chỉ tối đa một PENDING_VERIFICATION. Nhiều lần thu PAID trên
--                cùng lượt là hợp lệ: bác sĩ thêm chỉ định sau lần thu đầu, khách
--                trả tiếp đúng phần mới (outstanding bill).
--
-- 2. payment_cycle_backfill_legacy() viết lại để KHÔNG dựa vào ON CONFLICT trên
--    chỉ mục cũ (đã bỏ). Giữ đúng luật lịch sử đã tuyên bố trong CP2: hai lần thu
--    cũ cùng "đang sống" cho một (lượt, loại) là mâu thuẫn — KHÔNG chọn hộ, bỏ
--    qua và đếm. (Bản cũ thực tế giữ lần sớm nhất nhờ ON CONFLICT + ORDER BY —
--    trái với chính chú thích của nó. Bản này bỏ qua cả nhóm.)
--
-- 3. Chốt DB chống PHỦ TRÙNG: một dòng tiền khám / chỉ định của PHÒNG KHÁM chỉ
--    được nằm trong MỘT lần thu đang giữ phủ (đang chờ xác minh, hoặc đã từng
--    nhận tiền — kể cả nay đã huỷ phiếu). Lần chờ đã huỷ mà chưa từng nhận tiền
--    không giữ phủ. Dòng đối tác tự thu không phải phủ của phòng khám.
--    Khoá advisory theo NGUỒN rồi mới kiểm: hai giao dịch cùng chụp một nguồn
--    thì nối tiếp, người sau thấy dòng người trước đã commit.
--
-- LƯU Ý CHẠY LẠI: chạy lại CP2 (20260919000002) sẽ tạo lại chỉ mục cũ trước khi
-- file này bỏ nó. Trên DB đã có nhiều lần thu dịch vụ PAID của cùng lượt, bước
-- tạo chỉ mục cũ ấy sẽ lỗi — đừng phát lại CP2 lên dữ liệu thật; khôi phục bằng
-- bản dump (schema + dữ liệu), không bằng phát lại migration.
--
-- Chạy lại được.

-- ── 1. Chỉ mục theo loại ────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_cycle_thuoc_mot_lan_song
    ON public.payment_cycle (clinic_id, visit_id)
    WHERE kind = 'thuoc' AND status IN ('PENDING_VERIFICATION', 'PAID');
CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_cycle_dich_vu_mot_lan_cho
    ON public.payment_cycle (clinic_id, visit_id)
    WHERE kind = 'dich_vu' AND status = 'PENDING_VERIFICATION';

-- ── 2. Backfill lịch sử không còn cần chỉ mục cũ ────────────────────────────
CREATE OR REPLACE FUNCTION public.payment_cycle_backfill_legacy()
RETURNS TABLE (tu_payment integer, tu_su_kien integer, su_kien_bo_qua integer)
LANGUAGE plpgsql AS $fn$
DECLARE
    a integer;
    b integer;
    uuid_re constant text :=
        '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';
BEGIN
    -- 1. Dòng `payment` hiện có (trạng thái mới nhất của lần thu hiện hành).
    --    Không đổi so với CP2.
    INSERT INTO public.payment_cycle (
        payment_cycle_id, clinic_id, visit_id, kind, payment_id, amount,
        bill_revision, method, status, legacy, created_by, created_at, paid_at,
        confirmed_by, closed_at, closed_by, close_reason
    )
    SELECT p.payment_cycle_id, p.clinic_id, p.visit_id, p.kind, p.id, p.amount,
           p.bill_revision, NULL, p.status, true, p.paid_by_staff_id,
           coalesce(p.paid_at, p.created_at), coalesce(p.paid_at, p.created_at),
           p.paid_by_staff_id, p.voided_at, p.voided_by_staff_id, p.void_reason
      FROM public.payment p
     WHERE p.amount IS NOT NULL AND p.amount > 0
       AND p.status IN ('PAID', 'VOIDED')
       AND EXISTS (SELECT 1 FROM public.visit v
                    WHERE v.visit_id = p.visit_id AND v.clinic_id = p.clinic_id)
    ON CONFLICT (payment_cycle_id) DO NOTHING;
    GET DIAGNOSTICS a = ROW_COUNT;

    -- 2. Lần thu cũ chỉ còn trong sổ sự kiện (dòng payment đã bị tái dùng).
    WITH ghi AS (
        SELECT DISTINCT ON (e.payload ->> 'payment_cycle_id')
               e.clinic_id,
               (e.payload ->> 'payment_cycle_id')::uuid AS cid,
               (e.payload ->> 'visit_id')::uuid         AS vid,
               e.payload ->> 'kind'                     AS kind,
               (e.payload ->> 'amount')::bigint         AS amount,
               e.occurred_at,
               e.metadata ->> 'clinic_staff_id'         AS ai
          FROM public.event_log e
         WHERE e.event_type = 'payment.recorded'
           AND e.payload ->> 'payment_cycle_id' ~ uuid_re
           AND e.payload ->> 'visit_id' ~ uuid_re
           AND e.payload ->> 'kind' IN ('thuoc', 'dich_vu')
           AND e.payload ->> 'amount' ~ '^[0-9]+$'
           AND (e.payload ->> 'amount')::bigint > 0
         ORDER BY e.payload ->> 'payment_cycle_id', e.occurred_at
    ), huy AS (
        SELECT DISTINCT ON (e.payload ->> 'payment_cycle_id')
               (e.payload ->> 'payment_cycle_id')::uuid AS cid,
               e.occurred_at,
               e.payload ->> 'void_reason'              AS ly_do,
               e.metadata ->> 'clinic_staff_id'         AS ai
          FROM public.event_log e
         WHERE e.event_type = 'payment.voided'
           AND e.payload ->> 'payment_cycle_id' ~ uuid_re
         ORDER BY e.payload ->> 'payment_cycle_id', e.occurred_at
    ), ung_vien AS (
        SELECT g.*, h.cid AS huy_cid, h.occurred_at AS huy_luc, h.ly_do,
               h.ai AS huy_ai
          FROM ghi g
          LEFT JOIN huy h ON h.cid = g.cid
    )
    INSERT INTO public.payment_cycle (
        payment_cycle_id, clinic_id, visit_id, kind, amount, method, status,
        legacy, created_by, created_at, paid_at, confirmed_by,
        closed_at, closed_by, close_reason
    )
    SELECT u.cid, u.clinic_id, u.vid, u.kind, u.amount, NULL,
           CASE WHEN u.huy_cid IS NULL THEN 'PAID' ELSE 'VOIDED' END,
           true,
           (SELECT s.id FROM public.staff s WHERE s.id::text = u.ai),
           u.occurred_at, u.occurred_at,
           (SELECT s.id FROM public.staff s WHERE s.id::text = u.ai),
           u.huy_luc,
           (SELECT s.id FROM public.staff s WHERE s.id::text = u.huy_ai),
           u.ly_do
      FROM ung_vien u
     WHERE EXISTS (SELECT 1 FROM public.visit v
                    WHERE v.visit_id = u.vid AND v.clinic_id = u.clinic_id)
       AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                        WHERE c.payment_cycle_id = u.cid)
       -- Lần thu chỉ có "đã thu" mà không có "đã huỷ", trong khi cùng (lượt,
       -- loại) đã có một lần thu KHÁC — ở dòng `payment` hiện tại hay trong sổ,
       -- kể cả lần đó đã huỷ — là mâu thuẫn: bỏ qua và đếm (CP2, giữ nguyên).
       AND (u.huy_cid IS NOT NULL OR (
            NOT EXISTS (SELECT 1 FROM public.payment p
                         WHERE p.clinic_id = u.clinic_id AND p.visit_id = u.vid
                           AND p.kind = u.kind
                           AND p.payment_cycle_id IS DISTINCT FROM u.cid)
            AND NOT EXISTS (SELECT 1 FROM public.payment_cycle c
                             WHERE c.clinic_id = u.clinic_id AND c.visit_id = u.vid
                               AND c.kind = u.kind
                               AND c.payment_cycle_id <> u.cid)
            -- Thay ON CONFLICT của CP2: hai ứng viên "đang sống" cùng (lượt,
            -- loại) trong CÙNG lần chạy cũng là mâu thuẫn — không chọn lần nào,
            -- bỏ qua cả hai và đếm.
            AND NOT EXISTS (SELECT 1 FROM ung_vien k
                             WHERE k.clinic_id = u.clinic_id AND k.vid = u.vid
                               AND k.kind = u.kind AND k.cid <> u.cid
                               AND k.huy_cid IS NULL)))
     ORDER BY u.occurred_at;
    GET DIAGNOSTICS b = ROW_COUNT;

    RETURN QUERY
    SELECT a, b,
           (SELECT count(DISTINCT e.payload ->> 'payment_cycle_id')::integer
              FROM public.event_log e
             WHERE e.event_type = 'payment.recorded'
               AND NOT EXISTS (
                   SELECT 1 FROM public.payment_cycle c
                    WHERE c.payment_cycle_id::text = e.payload ->> 'payment_cycle_id'));
END
$fn$;

-- Chỉ mục cũ bỏ SAU khi hàm không còn nhắc tới nó.
DROP INDEX IF EXISTS public.uq_payment_cycle_mot_lan_song;

-- ── 3. Chốt chống phủ trùng dòng phòng khám ─────────────────────────────────
CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam') THEN
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
       AND bl.payment_cycle_id <> NEW.payment_cycle_id
       AND (c.status = 'PENDING_VERIFICATION' OR c.paid_at IS NOT NULL)
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

DROP TRIGGER IF EXISTS trg_payment_bill_line_mot_lan_phu ON public.payment_bill_line;
CREATE TRIGGER trg_payment_bill_line_mot_lan_phu
    BEFORE INSERT ON public.payment_bill_line
    FOR EACH ROW EXECUTE FUNCTION public.payment_bill_line_mot_lan_phu();
