-- Chỉ mục cho "lượt check-in HÔM NAY" (perf, 14/10/2026).
--
-- Mười một câu hot (nhan_tai_phong, service_routing, service_execution,
-- luot_kham_doc, luot_treo, lan_bac_si, agent_tom_tat) cùng lọc
--     (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = <hôm nay>
-- Biểu thức này KHÔNG dùng được chỉ mục trên `checked_in_at` (có sẵn
-- `idx_visit_con_mo` nhưng theo cột trần) → mỗi lần quét cả bảng visit (14k lượt
-- và tăng dần). Đo prod (pg_stat_statements từ 16/09): đếm khách theo phòng
-- (`dem_theo_phong`) 22.119 lần × 38,9 ms.
--
-- Chỉ mục BIỂU THỨC khớp từng chữ với câu trên (`timezone(text, timestamptz)` và
-- `timestamp::date` đều IMMUTABLE nên được phép). Chỉ thêm chỉ mục — không đổi
-- bảng, không đổi RLS, không đổi kết quả. Bảng ~14k dòng: dựng vài chục ms;
-- CREATE INDEX CONCURRENTLY không chạy được trong giao dịch của sổ migration.
-- Idempotent.

CREATE INDEX IF NOT EXISTS idx_visit_ngay_check_in
    ON public.visit (clinic_id, ((checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date));
