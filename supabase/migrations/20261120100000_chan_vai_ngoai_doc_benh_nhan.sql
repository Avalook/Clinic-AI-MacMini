-- R-042 — tài khoản ĐỐI TÁC (PARTNER) và MÀN HÌNH (DISPLAY) không được đọc
-- patient / appointment / lab_result / staff qua /rest/v1.
--
-- VÌ SAO. W3 (20260730000004) chỉ khoanh theo PHÒNG KHÁM: là thành viên đang
-- hoạt động của phòng khám thì đọc được mọi dòng của nó. Từ khi có vai PARTNER
-- (20260916000007 — người của phòng xét nghiệm ngoài) và DISPLAY (màn hình
-- phòng chờ), "là thành viên" không còn nghĩa là "người trong nhà". Mà
-- `/rest/v1` mở ra internet qua Caddy: tài khoản đối tác cầm JWT của chính nó
-- gọi thẳng `GET /rest/v1/patient` là đọc được hồ sơ khách (kiểm toán R-042).
--
-- VÌ SAO RESTRICTIVE, KHÔNG SỬA POLICY CŨ. Policy RESTRICTIVE được AND với mọi
-- policy PERMISSIVE. Sau này ai thêm một policy đọc rộng hơn cho bốn bảng này
-- thì vai ngoài vẫn bị chặn — không phải nhớ sửa lại ở đây.
--
-- KHÔNG LÀM HỎNG APP: trình duyệt không đọc bốn bảng này qua /rest/v1 (supabase
-- phía trình duyệt chỉ dùng `.auth.*`); màn đối tác và màn phòng chờ đọc qua
-- FastAPI, mà FastAPI nối DB bằng vai bỏ qua RLS. Chỗ duy nhất đọc qua phiên
-- người dùng là `proxy.ts` tra CHÍNH dòng `staff` của mình — giữ bằng nhánh
-- `id = current_staff_id()` ở policy staff bên dưới.
--
-- MỘT NGƯỜI NHIỀU VAI: `clinic_membership` cho một người nhiều vai trong một
-- phòng khám (khoá (clinic_id, staff_id, role)). Có ít nhất một vai TRONG NHÀ
-- ở phòng khám đó thì vẫn đọc như cũ — chỉ chặn người CHỈ có vai ngoài.

CREATE OR REPLACE FUNCTION public.current_internal_clinic_ids()
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
    SELECT m.clinic_id
    FROM public.clinic_membership m
    WHERE m.staff_id = public.current_staff_id()
      AND m.is_active
      AND m.role NOT IN ('PARTNER', 'DISPLAY')
$$;

COMMENT ON FUNCTION public.current_internal_clinic_ids() IS
  'Phòng khám mà người gọi có ít nhất một vai TRONG NHÀ (không phải PARTNER/'
  'DISPLAY). Dùng cho policy RESTRICTIVE chặn vai ngoài đọc dữ liệu khách (R-042).';

REVOKE ALL ON FUNCTION public.current_internal_clinic_ids() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_internal_clinic_ids()
    TO authenticated, service_role;

-- Ba bảng có clinic_id: dòng chỉ hiện khi người gọi là người trong nhà của
-- đúng phòng khám sở hữu dòng đó.
DO $chan_vai_ngoai$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['patient', 'appointment', 'lab_result'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',
                       t || '_chan_vai_ngoai', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR SELECT '
            'TO authenticated '
            'USING (clinic_id IN (SELECT public.current_internal_clinic_ids()))',
            t || '_chan_vai_ngoai', t
        );
    END LOOP;
END
$chan_vai_ngoai$;

-- staff không có clinic_id. Vai ngoài chỉ thấy dòng của chính mình (proxy.ts
-- cần nó để biết phiên gắn với một nhân viên đang làm việc).
DROP POLICY IF EXISTS staff_chan_vai_ngoai ON public.staff;
CREATE POLICY staff_chan_vai_ngoai ON public.staff
    AS RESTRICTIVE FOR SELECT TO authenticated
    USING (
        id = public.current_staff_id()
        OR EXISTS (SELECT 1 FROM public.current_internal_clinic_ids())
    );

NOTIFY pgrst, 'reload schema';
