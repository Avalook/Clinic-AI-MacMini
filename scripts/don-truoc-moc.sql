-- Dọn dữ liệu khách GIẢ từ một mốc thời gian TRỞ VỀ TRƯỚC (30/09/2026).
--
-- ĐỪNG CHẠY TAY FILE NÀY — chạy qua `scripts/don-truoc-moc.sh`: nó sao lưu
-- trước, dừng các dịch vụ đang ghi, chuyển tệp kết quả sang thư mục cách ly,
-- rồi bật lại.
--
-- Việc XOÁ do hàm `public.don_khach_thu` (migration 20261001240000) làm — CÙNG
-- hàm với màn quản trị `/settings/don-du-lieu-thu`. File này chỉ CHỌN khách
-- theo mốc và in danh sách để soát:
--
--   KHÁCH BỊ XOÁ = mọi dữ liệu của họ đều ≤ mốc:
--     hồ sơ tạo ≤ mốc, VÀ mọi lịch hẹn có giờ khám ≤ mốc và tạo ≤ mốc,
--     VÀ mọi lượt khám check-in (hoặc tạo) ≤ mốc.
--   Khách có dù chỉ MỘT lịch/lượt sau mốc → GIỮ NGUYÊN khách đó cùng MỌI dữ liệu
--   (kể cả phần trước mốc), in riêng ở mục "KHÁCH LẪN" để người soát quyết.
--
-- Có mốc, hàm còn dọn: sổ sự kiện / hẹn giờ / biên nhận / thông báo ≤ mốc trỏ
-- vào thứ không còn tồn tại, bộ nhớ chống bấm trùng ≤ mốc, nhóm lỗi + cảnh báo
-- có lần cuối ≤ mốc. Các chốt an toàn: xem đầu migration.
--
-- Mặc định CHẠY THỬ: làm thật toàn bộ rồi ROLLBACK. Chỉ `-v that=1` COMMIT.
--
-- Biến psql:
--   moc='2026-09-29 17:45'   BẮT BUỘC. Giờ Việt Nam nếu không ghi múi giờ.
--   that=1                   COMMIT thật (thiếu = chạy thử, cuộn lại)
--
-- Đầu ra có các dòng `TEP|<vi_tri>|<khoa>` — tệp kết quả của các dòng bị xoá;
-- `don-truoc-moc.sh` đọc chúng để chuyển tệp SAU khi COMMIT.

\set ON_ERROR_STOP on
\if :{?that}
\else
  \set that 0
\endif
\if :{?moc}
\else
  \echo 'THIẾU mốc: chạy với -v moc=''2026-09-29 17:45'''
  SELECT 1/0 AS thieu_moc;
\endif

SELECT (:'that' = '1') AS lam_that \gset

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL TIME ZONE 'Asia/Ho_Chi_Minh';

DO $$
BEGIN
  IF to_regprocedure('public.don_khach_thu(uuid, uuid[], boolean, timestamptz, uuid, text, text)') IS NULL THEN
    RAISE EXCEPTION 'Chưa có hàm don_khach_thu — áp migration 20261001240000_don_du_lieu_thu.sql trước';
  END IF;
END $$;

CREATE TEMP TABLE tham_so ON COMMIT DROP AS
SELECT :'moc'::timestamptz AS moc;

\echo
\echo '════ MỐC ════'
SELECT to_char(moc, 'HH24:MI "ngày" DD/MM/YYYY (TZH)') AS moc FROM tham_so;

-- Che 3 số giữa của số điện thoại: 0334567897 → 0334***897.
CREATE FUNCTION pg_temp.che(sdt text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN sdt IS NULL OR length(sdt) < 7 THEN sdt
              ELSE left(sdt, length(sdt) - 6) || '***' || right(sdt, 3) END
$$;

-- ── 1. Phân loại khách ──────────────────────────────────────────────────
CREATE TEMP TABLE khach ON COMMIT DROP AS
SELECT p.clinic_patient_id AS id, p.clinic_id, p.patient_code AS ma, p.full_name AS ten,
       p.phone_primary AS sdt, p.created_at AS tao,
       (SELECT count(*) FROM public.appointment a
         WHERE a.clinic_patient_id = p.clinic_patient_id) AS so_lich,
       (SELECT min(a.slot_start) FROM public.appointment a
         WHERE a.clinic_patient_id = p.clinic_patient_id) AS lich_dau,
       (SELECT max(greatest(a.slot_start, a.created_at)) FROM public.appointment a
         WHERE a.clinic_patient_id = p.clinic_patient_id) AS lich_cuoi,
       (SELECT count(*) FROM public.visit v
         WHERE v.clinic_patient_id = p.clinic_patient_id) AS so_luot,
       (SELECT min(coalesce(v.checked_in_at, v.created_at)) FROM public.visit v
         WHERE v.clinic_patient_id = p.clinic_patient_id) AS luot_dau,
       (SELECT max(greatest(v.created_at, coalesce(v.checked_in_at, v.created_at)))
          FROM public.visit v
         WHERE v.clinic_patient_id = p.clinic_patient_id) AS luot_cuoi,
       false AS xoa, false AS nghi_thu, false AS lan
FROM public.patient p;

UPDATE khach k SET
  xoa = k.tao <= t.moc
        AND coalesce(k.lich_cuoi, '-infinity') <= t.moc
        AND coalesce(k.luot_cuoi, '-infinity') <= t.moc,
  -- có dữ liệu ≤ mốc nhưng cũng có dữ liệu sau mốc
  lan = (k.lich_dau <= t.moc OR k.luot_dau <= t.moc)
        AND NOT (k.tao <= t.moc
                 AND coalesce(k.lich_cuoi, '-infinity') <= t.moc
                 AND coalesce(k.luot_cuoi, '-infinity') <= t.moc),
  nghi_thu = k.ten ~* '(test|tes |thử|giả|smoke|demo|claude|kiểm thử|abc|cde)'
             OR k.sdt ~ '(\d)\1{5}'
FROM tham_so t;

-- ── 2. Danh sách để SOÁT ────────────────────────────────────────────────
\echo
\echo '════ KHÁCH SẼ XOÁ (mọi dữ liệu ≤ mốc) ════'
SELECT row_number() OVER (ORDER BY coalesce(lich_dau, luot_dau, tao), ma) AS stt,
       ma, ten, pg_temp.che(sdt) AS sdt, to_char(tao, 'DD/MM HH24:MI') AS tao_ho_so,
       so_lich, so_luot,
       to_char(coalesce(lich_dau, luot_dau), 'DD/MM HH24:MI') AS lich_luot_dau,
       to_char(greatest(lich_cuoi, luot_cuoi), 'DD/MM HH24:MI') AS cuoi,
       CASE WHEN nghi_thu THEN '' ELSE 'TÊN NHƯ THẬT — soát' END AS luu_y
FROM khach WHERE xoa ORDER BY 1;

\echo
\echo '════ LỊCH HẸN SẼ XOÁ ════'
SELECT to_char(a.slot_start, 'DD/MM HH24:MI') AS gio_kham, a.so_booking AS so,
       k.ten, pg_temp.che(k.sdt) AS sdt, a.status, a.is_walkin AS vang_lai
FROM public.appointment a JOIN khach k ON k.id = a.clinic_patient_id
WHERE k.xoa
ORDER BY a.slot_start, a.so_booking;

\echo
\echo '════ LƯỢT KHÁM SẼ XOÁ ════'
SELECT to_char(coalesce(v.checked_in_at, v.created_at), 'DD/MM HH24:MI') AS check_in,
       a.so_booking AS so, k.ten, pg_temp.che(k.sdt) AS sdt, v.status,
       (v.appointment_id IS NULL) AS khong_lich
FROM public.visit v JOIN khach k ON k.id = v.clinic_patient_id
LEFT JOIN public.appointment a ON a.id = v.appointment_id
WHERE k.xoa
ORDER BY coalesce(v.checked_in_at, v.created_at);

\echo
\echo '════ KHÁCH LẪN — có lịch/lượt ≤ mốc NHƯNG cũng có sau mốc → GIỮ NGUYÊN, cần người quyết ════'
SELECT ma, ten, pg_temp.che(sdt) AS sdt, so_lich, so_luot,
       to_char(coalesce(least(lich_dau, luot_dau), lich_dau, luot_dau), 'DD/MM HH24:MI') AS dau,
       to_char(greatest(lich_cuoi, luot_cuoi), 'DD/MM HH24:MI') AS cuoi,
       CASE WHEN nghi_thu THEN 'NGHI THỬ' ELSE '' END AS luu_y
FROM khach WHERE lan ORDER BY greatest(lich_cuoi, luot_cuoi);

\echo
\echo '════ KHÁCH GIỮ LẠI (sau mốc) ════'
SELECT row_number() OVER (ORDER BY coalesce(least(lich_dau, luot_dau), lich_dau, luot_dau, tao), ma) AS stt,
       to_char(coalesce(least(lich_dau, luot_dau), lich_dau, luot_dau), 'DD/MM HH24:MI') AS lich_luot_dau,
       ten, pg_temp.che(sdt) AS sdt, so_lich, so_luot,
       CASE WHEN nghi_thu THEN 'NGHI THỬ' ELSE '' END AS luu_y
FROM khach WHERE NOT xoa ORDER BY 1;

\echo
\echo '════ KHÁCH NGHI THỬ SAU MỐC — KHÔNG xoá, người quyết ════'
SELECT ma, ten, pg_temp.che(sdt) AS sdt, to_char(tao, 'DD/MM HH24:MI') AS tao_ho_so,
       to_char(greatest(lich_cuoi, luot_cuoi), 'DD/MM HH24:MI') AS cuoi
FROM khach WHERE NOT xoa AND nghi_thu ORDER BY tao;

-- ── 3. Xoá (hàm dùng chung; làm thật trong giao dịch này) ───────────────
-- Mỗi phòng khám một lần gọi (hiện chỉ có một).
CREATE TEMP TABLE kq ON COMMIT DROP AS
SELECT c.id AS clinic_id,
       public.don_khach_thu(
         c.id,
         ARRAY(SELECT k.id FROM khach k WHERE k.xoa AND k.clinic_id = c.id),
         true, (SELECT moc FROM tham_so), NULL,
         'scripts/don-truoc-moc.sh', 'script_moc') AS r
FROM public.clinic c;

\echo
\echo '════ SỐ DÒNG XOÁ THEO BẢNG ════'
SELECT bang, so FROM (
  SELECT e.key AS bang, sum(e.value::bigint) AS so, 0 AS thu_tu
  FROM kq, jsonb_each_text(kq.r->'so_dong') e GROUP BY e.key
  UNION ALL
  SELECT 'TỔNG', coalesce(sum(e.value::bigint), 0), 1
  FROM kq, jsonb_each_text(kq.r->'so_dong') e
) x ORDER BY thu_tu, bang;

SELECT 'CÒN: khách' AS muc, count(*) FROM public.patient
UNION ALL SELECT 'CÒN: lịch hẹn', count(*) FROM public.appointment
UNION ALL SELECT 'CÒN: lượt khám', count(*) FROM public.visit
UNION ALL SELECT 'GIỮ: nhân sự', count(*) FROM public.staff
UNION ALL SELECT 'GIỮ: phòng', count(*) FROM public.clinic_room
UNION ALL SELECT 'GIỮ: giá', count(*) FROM public.service_price
UNION ALL SELECT 'GIỮ: danh mục thuốc', count(*) FROM public.drug_catalog
UNION ALL SELECT 'GIỮ: lô thuốc', count(*) FROM public.drug_batch
UNION ALL SELECT 'GIỮ: ca trực', count(*) FROM public.work_roster;

\echo
\echo '════ TỆP KẾT QUẢ SẼ CHUYỂN SANG THƯ MỤC CÁCH LY ════'
\pset format unaligned
\pset tuples_only on
SELECT 'TEP|' || (t->>'vi_tri') || '|' || (t->>'khoa')
FROM kq, jsonb_array_elements(kq.r->'tep') t ORDER BY 1;
SELECT 'SO_TEP|' || count(*) FROM kq, jsonb_array_elements(kq.r->'tep') t;
\pset tuples_only off
\pset format aligned

\if :lam_that
COMMIT;
\echo '>>> ĐÃ XOÁ THẬT (COMMIT).'
\else
ROLLBACK;
\echo '>>> CHẠY THỬ: mọi thay đổi đã cuộn lại, chưa xoá gì.'
\endif
