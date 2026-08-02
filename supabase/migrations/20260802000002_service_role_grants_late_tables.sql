-- service_role bị bỏ quên trên mọi bảng sinh sau 20260730000008.
--
-- 20260730000008 cấp `ALL TO service_role` bằng cách quét pg_class, và cấp
-- `SELECT TO authenticated` bằng cách quét pg_policy. Cả hai vòng lặp chỉ nhìn
-- thấy những bảng tồn tại LÚC NÓ CHẠY. Bảng nào ra đời sau đó thì không ai cấp
-- quyền hộ — và policy chỉ thu hẹp quyền sẵn có chứ không tạo ra quyền.
--
-- Đo trên một Postgres 17 sạch, apply chuỗi migration đúng MỘT lượt (hình dạng
-- của `supabase db push`, không phải hình dạng replay-2-lần của CI):
--
--     visit_amendment            service_role: KHÔNG INSERT được
--     patient_contact_channel    service_role: KHÔNG INSERT được
--     patient_next_of_kin        service_role: KHÔNG INSERT được
--
-- 20260801000003 có nhớ viết tay `GRANT SELECT ... TO authenticated` cho cả ba,
-- nên đường ĐỌC vẫn chạy và lỗi này im lặng cho tới lần ghi đầu tiên qua client
-- service_role. Bảng đắt nhất trong ba: visit_amendment — vết đính chính hồ sơ
-- mà Thông tư 13 bắt phải giữ. Ghi hỏng ở đó là hỏng đúng thứ không được hỏng.
--
-- Quét lại toàn bộ thay vì kể tên ba bảng: cách này chữa luôn mọi bảng khác đã
-- lọt qua khe giữa hai mốc thời gian, và chạy lại bao nhiêu lần cũng vô hại.
-- Chỗ chặn tái phát không nằm ở đây mà ở gate invariants của CI — nó suy ra
-- danh sách bảng lúc chạy, nên bảng thứ 51 không cần ai nhớ ra nó.

DO $service_role_grants$
DECLARE
    t record;
    healed integer := 0;
BEGIN
    FOR t IN
        SELECT c.oid, c.relname
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relkind = 'r'
           AND NOT has_table_privilege('service_role', c.oid, 'INSERT')
    LOOP
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t.relname);
        RAISE NOTICE 'service_role grant restored on %', t.relname;
        healed := healed + 1;
    END LOOP;

    RAISE NOTICE 'service_role grants healed on % tables', healed;
END
$service_role_grants$;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
