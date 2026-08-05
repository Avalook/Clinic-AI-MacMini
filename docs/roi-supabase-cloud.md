# Rời Supabase cloud — về Mac trước, sang Viettel IDC sau

Quang chốt 05/08/2026: chuyển database khỏi Supabase cloud. Tạm về Mac mini,
rồi khi mua gói Viettel IDC thì bê sang.

Chọn **đường A**: tự dựng trọn bộ Supabase (Postgres + GoTrue + PostgREST +
Realtime). Lý do: ứng dụng **không phải sửa dòng nào** — cùng JWT, cùng RLS,
cùng hình dạng API — và cùng bộ container chạy được ở cả Mac lẫn Viettel.

Hai đường còn lại đã cân nhắc và loại:

| | vì sao loại |
|---|---|
| Postgres trần, tự làm auth + realtime | phải sửa 28 file auth + 8 file realtime + 57 file query, và tự chịu trách nhiệm bảo mật đăng nhập |
| Lai — Postgres về Mac, auth vẫn ở cloud | `auth.users` nằm ở database khác với `public.staff`, mà hai hàm RLS đang nối qua đó. Sẽ phải đồng bộ tay giữa hai database |

---

## Supabase là bốn thứ, không phải một

Đo trên chính mã nguồn dự án (05/08/2026):

| thành phần | dùng ở đâu | trạng thái |
|---|---|---|
| Postgres | tất cả | dữ liệu chỉ **22 MB** |
| Auth (GoTrue) | **28 file** frontend · 9 tài khoản | khó nhất |
| PostgREST | **57 file** query thẳng | nhiều nhưng cơ học |
| Realtime | **8 file** (lễ tân, điều phối, siêu âm) | vừa |
| Storage | **0 file** | không dùng — ảnh siêu âm đã ở đĩa Mac |

Hai điều làm việc chuyển dễ hơn tưởng:

- **RLS gần như không dính Supabase Auth**: 49/55 policy gọi `current_clinic_ids()`,
  **0 policy** gọi `auth.uid()`. Điểm nối duy nhất là hai hàm `current_staff_id`
  và `current_staff_department`.
- Dữ liệu 22 MB, sao lưu hằng đêm đã kiểm khôi phục được.

---

## Giai đoạn 0 — đo drift *(xong 05/08)*

Dựng Postgres 17 trắng, chạy trọn 73 migration, so 1700 đối tượng với prod.

**Kết quả: 0 khác biệt về bảng, 0 về ràng buộc.** Cấu trúc lõi khớp. Trong 64
khác biệt còn lại, phần lớn không phải drift thật — 35 "hàm thiếu" chỉ là
pgcrypto/uuid-ossp đặt ở schema `extensions` thay vì `public`.

**Ba drift thật, tất cả cùng một gốc:** `20260714000001_baseline_schema.sql`
được **đánh dấu đã áp mà chưa bao giờ chạy** trên prod.

1. **`visit.exam_completed_at` không tồn tại trên prod** — mà trang chủ Lễ tân
   `SELECT` nó. Mỗi lần tải trang bắn một truy vấn chắc chắn hỏng ra Seoul rồi
   mới đi đường lùi, và cột "thời lượng khám" chưa bao giờ hiện.
   → đã vá ở PR #24 (trỏ sang `finalized_at`, cột có thật và đang được ghi).
2. **Ba bảng thiếu `clinic_id`** — `patient_contact_channel`,
   `patient_next_of_kin`, `visit_amendment`. Cả ba rỗng và RLS bật với 0 policy
   nên chưa lộ gì, nhưng nằm ngoài mô hình nhiều phòng khám.
3. **Bảy hàm thiếu** — `event_log_append_only_guard` (đã vấp thật khi cứu
   migration kho thuốc), `generate_patient_code`, `generate_lab_result_code`,
   `set_updated_at_timestamp`, `prevent_dead_letter_modification`, 2 hàm `kb_*`.

### Điều này quyết định cách chuyển

**Dựng database mới TỪ MIGRATION, không phải từ `pg_dump` của prod.**

- chuỗi migration chạy sạch trên Postgres trắng — đã chứng minh
- nó **tự vá** cả ba drift ở trên, miễn phí
- `pg_dump` sẽ bê nguyên chúng sang máy mới

Rồi **chỉ đổ dữ liệu**. Ba bảng lệch cột đều rỗng nên không có gì phải chuyển.

**Bằng chứng:** database dựng từ migration có **58 policy**, prod có **55** —
ba cái chênh đúng là ba policy thiếu ở mục 2.

---

## Giai đoạn 1 — dựng bộ Supabase trên Mac *(xong 05/08)*

```bash
docker compose --env-file .env.supabase-local -f docker-compose.supabase.yml \
  -p clinicai_db up -d
./scripts/supabase-local-nap.sh
```

Chạy song song, **không đụng prod**: project name riêng, mạng riêng, cổng
54331 (API) / 54332 (Postgres). Stack prod vẫn trỏ Supabase cloud.

Đã chứng minh chạy suốt bằng một tài khoản thật — tạo, đăng nhập, truy vấn,
rồi xoá:

- `auth.uid()` → `staff` → `clinic`: `current_staff_id()` trả đúng id
- `anon` đọc `patient` → `permission denied`
- người chưa gắn nhân sự → `[]` (đóng mặc định)
- websocket realtime → `101 Switching Protocols`

### Năm chỗ vấp khi dựng

Không cái nào đoán ra được từ tài liệu. Hai cái đầu là loại tệ nhất: triệu
chứng ở màn hình giống hệt lúc dịch vụ chết hẳn, nên rất dễ đi tìm sai chỗ.

| | triệu chứng | nguyên nhân |
|---|---|---|
| 1 | GoTrue khởi động lại vô hạn | tạo `auth.uid()` bằng `postgres` trước → GoTrue (`supabase_auth_admin`) không `CREATE OR REPLACE` đè được: *must be owner of function uid*. Phải để GoTrue tạo trước rồi mới nâng thân hàm |
| 2 | "đăng nhập được nhưng màn nào cũng trống" | GoTrue tạo `auth.uid()` chỉ đọc GUC kiểu cũ; PostgREST v12 đặt claim dạng JSON. Không nâng thân hàm thì `auth.uid()` luôn NULL |
| 3 | migration đổ giữa chừng | thiếu publication `supabase_realtime`; câu `ALTER PUBLICATION ... ADD TABLE` không có dạng `IF NOT EXISTS` |
| 4 | realtime 502 | thiếu vai `supabase_admin` — vai mà Realtime dùng để đọc WAL |
| 5 | realtime 404 rồi 403 | Realtime nghe ở `/socket/websocket` chứ không `/realtime/v1/websocket`; và nó lấy tenant từ **subdomain của Host** — thấy `127.0.0.1` thì đọc ra tenant tên `127` |

### Gateway là Caddy, không phải Kong

Supabase cloud dùng Kong. Ở đây Caddy đã chạy sẵn cho stack chính và cấu hình
định tuyến chỉ có bốn dòng. Thêm Kong là thêm một hệ cấu hình nữa để học và để
hỏng.

### Storage không dựng

Đo được **0 file** dùng — ảnh siêu âm lưu thẳng trên đĩa Mac từ 04/08. Dựng một
dịch vụ không ai gọi là thêm một thứ phải vá lỗi bảo mật hằng tháng.

---

## Giai đoạn 2 — đưa dữ liệu sang *(chưa làm)*

- lược đồ: đã dựng từ migration ở Giai đoạn 1
- dữ liệu `public`: `pg_dump --data-only` (22 MB)
- **`auth.users` + `auth.identities`**: 9 tài khoản. Mật khẩu là hash nên
  chuyển được; `staff.auth_user_id` phải giữ nguyên id, nếu không mọi nhân sự
  mất liên kết đăng nhập và nhận 403 ở mọi thao tác ghi
- ba bảng lệch cột ở Giai đoạn 0 đều rỗng — không có gì để chuyển

## Giai đoạn 3 — cắt chuyển *(chưa làm)*

Đổi `NEXT_PUBLIC_SUPABASE_URL` + `DATABASE_URL`, chạy thử toàn bộ màn hình,
**giữ Supabase cloud nguyên vẹn làm đường lùi ~1 tuần**.

## Giai đoạn 4 — sang Viettel IDC *(chưa làm)*

Cùng bộ compose, khác máy. Thêm: sao lưu ngoài site, TLS, tường lửa.

---

## Lưu ý vận hành

**Trên máy đang có sẵn một stack Supabase CLI local** (`supabase start`) chiếm
cổng 54321/54322. Bộ này dùng 54331/54332 để không đụng. Stack CLI ấy do CLI
quản lý và `supabase db reset` xoá sạch được — **không dùng làm nơi chứa dữ
liệu thật**.

**Khoá nằm ở `.env.supabase-local`**, đã bị `.gitignore` chặn. `JWT_SECRET` là
thứ GoTrue ký token và PostgREST/Realtime kiểm token — đổi nó là vô hiệu mọi
phiên đăng nhập đang mở, và hai khoá anon/service phải sinh lại theo.
