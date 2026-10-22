-- KIỂM DỮ LIỆU PROD, LƯỢT 4 — CHỈ ĐỌC, CHỈ TRẢ SỐ (22/10/2026).
-- Không in mã phiếu, tên, số điện thoại, mã lô hay dữ liệu khách.
-- Chạy:
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres -X -q -t -A' < docs/ban-do/hieu/kiem-du-lieu-prod-4.sql

\set ON_ERROR_STOP off

-- K1: đối chiếu thực thu theo ngày của báo cáo với sổ payment_cycle/payment_refund.
-- Cùng luật báo cáo: PAID/VOIDED ghi theo paid_at VN; huỷ phiếu sau khi ca đã
-- chốt giữ khoản thu ở ngày paid_at và trừ ở ngày closed_at; hoàn COMPLETED
-- trừ theo ngày tạo. Mỗi ngày chỉ xuất số ngày lệch và tổng chênh có dấu.
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
WITH bien AS (
    SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 29 AS tu,
           (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS den
), ngay AS (
    SELECT generate_series(tu::timestamp, den::timestamp, interval '1 day')::date AS d
      FROM bien
), chu_ky AS (
    SELECT pc.payment_cycle_id, pc.clinic_id, pc.visit_id, pc.amount,
           pc.status, pc.paid_at, pc.closed_at,
           coalesce(v.location_id, ah.location_id) AS location_id,
           (pc.status = 'VOIDED' AND pc.paid_at IS NOT NULL AND pc.closed_at IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM public.chot_so_ca k
                 WHERE k.clinic_id = pc.clinic_id
                   AND k.location_id = coalesce(v.location_id, ah.location_id)
                   AND k.tu_luc <= pc.paid_at AND pc.paid_at < k.den_luc
                   AND k.chot_luc < pc.closed_at
                   AND (k.mo_luc IS NULL OR k.mo_luc > pc.closed_at)
            )) AS huy_sau_chot
      FROM public.payment_cycle pc
      LEFT JOIN public.visit v
        ON v.visit_id = pc.visit_id AND v.clinic_id = pc.clinic_id
      LEFT JOIN public.appointment ah
        ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
     WHERE pc.status IN ('PAID', 'VOIDED') AND pc.paid_at IS NOT NULL
       AND (
           (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             BETWEEN (SELECT tu FROM bien) AND (SELECT den FROM bien)
           OR (pc.status = 'VOIDED' AND pc.closed_at IS NOT NULL
               AND (pc.closed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   BETWEEN (SELECT tu FROM bien) AND (SELECT den FROM bien))
       )
), dong_bao_cao AS (
    -- Khoản thu thường: thu và huỷ cùng ngày triệt tiêu; huỷ sau chốt thì
    -- giữ tiền ở ngày thu, phần huỷ được ghi thành dòng điều chỉnh ngày huỷ.
    SELECT (paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d,
           CASE WHEN status = 'PAID' OR huy_sau_chot THEN amount ELSE 0 END::numeric AS net
      FROM chu_ky
    UNION ALL
    SELECT (closed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, -amount::numeric
      FROM chu_ky WHERE status = 'VOIDED' AND huy_sau_chot
    UNION ALL
    SELECT (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, -r.amount::numeric
      FROM public.payment_refund r, bien b
     WHERE r.status = 'COMPLETED'
       AND (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN b.tu AND b.den
), theo_bao_cao AS (
    SELECT d, coalesce(sum(net), 0) AS thuc_thu FROM dong_bao_cao
     WHERE d BETWEEN (SELECT tu FROM bien) AND (SELECT den FROM bien) GROUP BY d
), dong_so_goc AS (
    -- Sổ gốc theo ngày phát sinh tiền: thu PAID theo paid_at; VOIDED triệt
    -- tiêu tại ngày paid_at; hoàn COMPLETED trừ theo ngày tạo. Chênh ngày huỷ
    -- sau chốt (nếu có) chính là phần báo cáo dời sang ngày closed_at.
    SELECT (paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS d,
           CASE WHEN status = 'PAID' THEN amount ELSE 0 END::numeric AS net
      FROM chu_ky
    UNION ALL
    SELECT (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, -r.amount::numeric
      FROM public.payment_refund r, bien b
     WHERE r.status = 'COMPLETED'
       AND (r.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN b.tu AND b.den
), theo_so_goc AS (
    SELECT d, coalesce(sum(net), 0) AS thuc_thu FROM dong_so_goc
     WHERE d BETWEEN (SELECT tu FROM bien) AND (SELECT den FROM bien) GROUP BY d
), doi_chieu AS (
    SELECT n.d, coalesce(b.thuc_thu, 0) AS bao_cao,
           coalesce(s.thuc_thu, 0) AS so_goc
      FROM ngay n LEFT JOIN theo_bao_cao b USING (d)
                 LEFT JOIN theo_so_goc s USING (d)
)
SELECT jsonb_build_object(
    'ngay_lech', count(*) FILTER (WHERE bao_cao <> so_goc),
    'tong_chenh_co_dau', coalesce(sum(bao_cao - so_goc), 0),
    'tong_chenh_tuyet_doi', coalesce(sum(abs(bao_cao - so_goc)), 0)
)::text FROM doi_chieu;
ROLLBACK;

-- K2: lô có tồn vật lý khác tổng sổ biến động (tính mọi loại giao dịch).
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object(
    'lo_lech', count(*) FILTER (WHERE b.quantity_on_hand <> coalesce(t.tong, 0)),
    'tong_lo', count(*)
)::text
  FROM public.drug_batch b
  LEFT JOIN (
      SELECT drug_batch_id, sum(quantity) AS tong
        FROM public.inventory_txn GROUP BY drug_batch_id
  ) t ON t.drug_batch_id = b.id;
ROLLBACK;

-- K3: phiếu đã thu rồi huỷ ở một ngày VN khác ngày thu VN.
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object(
    'voided_khac_ngay', count(*)
)::text
  FROM public.payment_cycle pc
 WHERE pc.status = 'VOIDED' AND pc.paid_at IS NOT NULL AND pc.closed_at IS NOT NULL
   AND (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       <> (pc.closed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
ROLLBACK;
