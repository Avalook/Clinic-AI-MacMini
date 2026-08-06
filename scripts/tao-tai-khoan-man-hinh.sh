#!/usr/bin/env bash
# Tạo tài khoản cho MÀN HÌNH TV phòng chờ (vai DISPLAY).
#
# ------------------------------------------------------------------------------
# VÌ SAO KHÔNG DÙNG TÀI KHOẢN NHÂN VIÊN
#
# Bảng gọi số phải hiện cho khách xem, nên máy chạy nó đăng nhập một lần rồi bỏ
# đó cả ngày, ở nơi công cộng, không ai trông. Đăng nhập bằng tài khoản Lễ tân
# thì bất kỳ ai đứng cạnh chỉ cần mở một tab mới là đọc được danh sách bệnh
# nhân, số điện thoại, chẩn đoán.
#
# Vai DISPLAY bị `get_current_identity` TỪ CHỐI, nên nó bị chặn ở MỌI endpoint
# theo mặc định — kể cả những endpoint chưa có RoleGuard. Đúng một đường nhận
# nó: GET /api/v1/display/queue, vốn không trả về một mẩu danh tính nào.
#
# Cần migration 20260806000003 (nới ràng buộc vai) trước khi chạy.
# ------------------------------------------------------------------------------
#
# Dùng:
#   CLINIC_DB_CONTAINER=clinicai_db MAT_KHAU='...' ./scripts/tao-tai-khoan-man-hinh.sh
#
# Chạy lại nhiều lần được: có rồi thì chỉ đặt lại mật khẩu.

set -euo pipefail

EMAIL="${EMAIL:-manhinh@dr4women.local}"
TEN="${TEN:-Màn hình phòng chờ}"

# Không đặt MAT_KHAU thì script TỰ SINH — và in ra ở cuối.
#
# Bản đầu bắt người dùng tự truyền vào và KHÔNG in lại. Ai làm theo đúng gợi ý
# `MAT_KHAU="$(openssl rand -base64 24)"` thì mật khẩu bị sinh ra rồi biến mất
# ngay trong dòng lệnh — tài khoản tạo xong mà không ai đăng nhập được.
if [[ -z "${MAT_KHAU:-}" ]]; then
  MAT_KHAU="$(openssl rand -base64 18)"
  TU_SINH=1
fi

if [[ -n "${CLINIC_DB_DSN:-}" ]]; then
  run_sql() { psql "$CLINIC_DB_DSN" -v ON_ERROR_STOP=1 "$@"; }
elif [[ -n "${CLINIC_DB_CONTAINER:-}" ]]; then
  run_sql() {
    docker exec -i "$CLINIC_DB_CONTAINER" \
      psql -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" \
           -v ON_ERROR_STOP=1 "$@"
  }
else
  echo "Đặt CLINIC_DB_CONTAINER hoặc CLINIC_DB_DSN." >&2
  exit 2
fi

# Mật khẩu đi vào SQL bằng THAM SỐ (:'pw'), không nối chuỗi — nối chuỗi là cách
# một dấu nháy trong mật khẩu biến thành lỗi cú pháp, hoặc tệ hơn.
run_sql -v pw="$MAT_KHAU" -v email="$EMAIL" -v ten="$TEN" <<'SQL'
BEGIN;

-- Cùng một cơ sở và phòng khám với phần còn lại. Lấy cái đầu tiên chứ không
-- đoán: bảng gọi số của một phòng khám không có nghĩa ở phòng khám khác.
CREATE TEMP TABLE _dich ON COMMIT DROP AS
SELECT (SELECT id FROM public.clinic ORDER BY created_at LIMIT 1)          AS clinic_id,
       (SELECT id FROM public.clinic_location ORDER BY created_at LIMIT 1) AS location_id;

-- ① Người dùng đăng nhập. GoTrue kiểm mật khẩu bằng pgcrypto crypt(), nên đặt
--    thẳng bcrypt ở đây là hợp lệ với cả GoTrue lẫn /api/v1/auth/login.
-- `instance_id` PHẢI là UUID rỗng, không được để NULL.
--
-- GoTrue lọc người dùng theo cột này. Một hàng có instance_id NULL thì GoTrue
-- KHÔNG TÌM THẤY, và thông báo trả về là "sai email hoặc mật khẩu" — đúng thứ
-- khiến người ta đi đổi mật khẩu năm lần trong khi lỗi nằm ở chỗ khác hẳn. Đã
-- gặp thật: tài khoản tạo xong, dữ liệu đủ, đăng nhập vẫn báo sai.
INSERT INTO auth.users (instance_id, id, email, encrypted_password,
                        email_confirmed_at, aud, role,
                        raw_app_meta_data, raw_user_meta_data,
                        created_at, updated_at)
SELECT '00000000-0000-0000-0000-000000000000', gen_random_uuid(), :'email',
       extensions.crypt(:'pw', extensions.gen_salt('bf')), now(),
       'authenticated', 'authenticated', '{"provider":"email"}'::jsonb, '{}'::jsonb,
       now(), now()
 WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE email = :'email');

UPDATE auth.users
   SET encrypted_password = extensions.crypt(:'pw', extensions.gen_salt('bf')),
       instance_id = '00000000-0000-0000-0000-000000000000',
       email_confirmed_at = coalesce(email_confirmed_at, now()),
       -- CHUỖI RỖNG, KHÔNG PHẢI NULL.
       --
       -- GoTrue viết bằng Go và đọc mấy cột này vào kiểu `string`, vốn không
       -- chứa được NULL. Một hàng có NULL ở đây làm GoTrue nổ ngay lúc truy vấn,
       -- và thông báo nó trả về là:
       --
       --     {"code":500,"msg":"Database error querying schema"}
       --
       -- Màn đăng nhập dịch cái đó thành "đăng nhập thất bại", nên người dùng
       -- đi đổi mật khẩu nhiều lần trong khi lỗi nằm ở chỗ hoàn toàn khác. Đã
       -- gặp thật: tài khoản đủ dữ liệu, mật khẩu đúng, GoTrue vẫn 500 — trong
       -- khi cửa đăng nhập của chính ứng dụng (/api/v1/auth/login, đọc bằng
       -- asyncpg) thì trả 200 bình thường. Chính sự lệch đó chỉ ra thủ phạm.
       confirmation_token       = coalesce(confirmation_token, ''),
       recovery_token           = coalesce(recovery_token, ''),
       email_change             = coalesce(email_change, ''),
       email_change_token_new   = coalesce(email_change_token_new, ''),
       updated_at = now()
 WHERE email = :'email';

-- ② Nhân sự. `employment_type` = SYSTEM để báo cáo nhân sự không đếm cái tivi
--    như một người đang làm việc.
INSERT INTO public.staff (id, auth_user_id, full_name, short_name,
                          primary_department, primary_location_id,
                          employment_type, is_active)
SELECT gen_random_uuid(), u.id, :'ten', 'TV', 'DISPLAY', d.location_id,
       'SYSTEM', true
  FROM auth.users u, _dich d
 WHERE u.email = :'email'
   AND NOT EXISTS (SELECT 1 FROM public.staff s WHERE s.auth_user_id = u.id);

UPDATE public.staff s
   SET is_active = true, primary_department = 'DISPLAY'
  FROM auth.users u
 WHERE u.email = :'email' AND s.auth_user_id = u.id;

-- ③ Vai trong phòng khám.
INSERT INTO public.clinic_membership (id, staff_id, clinic_id, role, is_active)
SELECT gen_random_uuid(), s.id, d.clinic_id, 'DISPLAY', true
  FROM public.staff s
  JOIN auth.users u ON u.id = s.auth_user_id, _dich d
 WHERE u.email = :'email'
   AND NOT EXISTS (
       SELECT 1 FROM public.clinic_membership m
        WHERE m.staff_id = s.id AND m.clinic_id = d.clinic_id
   );

UPDATE public.clinic_membership m
   SET role = 'DISPLAY', is_active = true
  FROM public.staff s
  JOIN auth.users u ON u.id = s.auth_user_id
 WHERE m.staff_id = s.id AND u.email = :'email';

-- ④ Mật khẩu cho cửa đăng nhập của chính ứng dụng (/api/v1/auth/login).
INSERT INTO public.app_credential (staff_id, email, password_hash)
SELECT s.id, :'email', extensions.crypt(:'pw', extensions.gen_salt('bf'))
  FROM public.staff s
  JOIN auth.users u ON u.id = s.auth_user_id
 WHERE u.email = :'email'
    ON CONFLICT (staff_id) DO UPDATE
   SET password_hash = EXCLUDED.password_hash,
       failed_attempts = 0,
       locked_until = NULL;

COMMIT;
SQL

echo ""
echo "Xong. Tài khoản màn hình: $EMAIL"
echo ""
run_sql -t -A -v email="$EMAIL" <<'SQL'
SELECT '  vai: ' || m.role || ' · cơ sở: ' || coalesce(l.name, '?')
  FROM public.staff s
  JOIN auth.users u ON u.id = s.auth_user_id
  JOIN public.clinic_membership m ON m.staff_id = s.id
  LEFT JOIN public.clinic_location l ON l.id = s.primary_location_id
 WHERE u.email = :'email';
SQL
echo ""
echo "  ┌────────────────────────────────────────────────┐"
printf "  │ Email    : %-35s │\n" "$EMAIL"
printf "  │ Mật khẩu : %-35s │\n" "$MAT_KHAU"
echo "  └────────────────────────────────────────────────┘"
if [[ -n "${TU_SINH:-}" ]]; then
  echo ""
  echo "  (Mật khẩu do script tự sinh. LƯU LẠI NGAY — nó không hiện lần nữa,"
  echo "   và chạy lại script sẽ sinh một mật khẩu KHÁC.)"
fi
echo ""
echo "Trên máy tivi: đăng nhập bằng tài khoản này rồi mở /display."
echo "Đăng nhập xong nó sẽ tự chuyển tới đó — vai này không vào bảng điều khiển được."
