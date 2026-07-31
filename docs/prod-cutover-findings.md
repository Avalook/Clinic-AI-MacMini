# Cutover production — kết quả dry-run 01/08/2026

Chạy `supabase db push --dry-run` lên database production thật, sau khi đã có
một bản backup định danh đúng (`clinicai_production_atfmxvdfnbeenrdbbllp_*`).

**Kết luận: KHÔNG được chạy `supabase db push` lên production.** Lý do bên dưới.

---

## 1. Dry-run nói gì

CLI báo sẽ đẩy **cả 31 migration**, bắt đầu từ `20260714000001_baseline_schema.sql`.

Nó nghĩ production trống, vì production **không có** bảng theo dõi của Supabase CLI:

| | |
|---|---|
| `supabase_migrations.schema_migrations` | **không tồn tại** |
| `public.schema_migrations` | **55 dòng** — quy ước của repo cũ |

Và `baseline_schema.sql` chứa **32 câu `CREATE TABLE` trần**, **0 câu `IF NOT EXISTS`**.

Nghĩa là push sẽ chạy `CREATE TABLE public.patient (...)` lên một bảng **đang có
bệnh nhân thật**, và dừng lại ở migration thứ hai. Không phải mất dữ liệu, nhưng
cũng không phải cutover — chỉ là một lần chạy hỏng giữa chừng trên hệ đang phục
vụ bệnh nhân.

**Hai lịch sử schema này không cùng huyết thống.** Production không được dựng bởi
các migration trong repo này; nó do repo cũ dựng bằng SQL riêng. Chúng giao nhau
nhưng không nối tiếp nhau.

## 2. Khoảng cách schema thật

| | Số bảng |
|---|---|
| Production | 35 |
| Đích (repo này) | 44 |
| Chung | 32 |
| **Chỉ có ở production** | **3** |
| Chỉ có ở đích | 12 |

**12 bảng đích còn thiếu ở prod:** `clinic`, `clinic_membership`,
`clinical_form_catalogue`, `follow_up_case`, `idempotency_key`,
`node_definition`, `node_definition_version`, `node_dependency`, `pos_outbox`,
`work_item`, `work_item_dependency`, `work_item_event`.

## 3. Phát hiện quan trọng nhất: 3 bảng chỉ có ở production

| Bảng | Số dòng | Ghi chú |
|---|---|---|
| **`visit_amendment`** | **3.326** | **Bảng lớn nhất production.** Lịch sử đính chính hồ sơ |
| `patient_contact_channel` | 14 | Kênh liên hệ bệnh nhân |
| `patient_next_of_kin` | 10 | Người thân |

`visit_amendment` có **3.326 dòng** và **không tồn tại trong schema đích**. Đây là
vết đính chính hồ sơ — đúng thứ Thông tư 13/2025 yêu cầu bệnh án điện tử phải
giữ. Một lần rebuild ngây thơ sẽ **xoá sạch nó**.

Nó cũng đi kèm function `visit_amendment_append_only` — function duy nhất có ở
production mà repo này không có.

## 4. Khối lượng dữ liệu thật

**~4.438 dòng** trên toàn bộ production. Nhỏ. Đây là tin tốt: mọi phương án đều
khả thi ở quy mô này, và kiểm chứng được từng dòng nếu cần.

## 5. Ba phương án

### (a) `migration repair` — đánh dấu đã áp dụng rồi push phần mới
Yêu cầu schema prod **khớp** với những gì các migration đó tạo ra. Nó không khớp
(35 vs 44 bảng, không có `clinic_id`). **Loại.**

### (b) Migration tiến tới — viết migration mới biến đổi schema prod hiện tại
Đúng nguyên tắc, nhưng phải viết tay một bản diff 12 bảng + `clinic_id` cho 27
bảng + RLS, và chỉ chạy được đúng một lần. Rủi ro nằm ở chỗ không diễn tập được
trên chính dữ liệu thật.

### (c) Dựng mới rồi chuyển dữ liệu sang — **đề xuất**
Ở mức 4.438 dòng, đây là phương án **diễn tập được**: dựng schema đích sạch từ 31
migration, chuyển dữ liệu, so số dòng từng bảng, chạy toàn bộ test, rồi mới đổi.
Làm được bao nhiêu lần tuỳ thích trước khi đụng vào production.

Điều kiện bắt buộc của (c): **giữ 3 bảng chỉ-có-ở-prod**. Chúng phải được thêm vào
schema đích bằng migration trước, không phải bỏ lại.

## 5b. Hotfix `f_unaccent` — đã viết và đã chứng minh, **chưa áp lên production**

Backup production hiện **không khôi phục được**: `pg_dump` mở dump bằng
`search_path = ''`, còn `f_unaccent` của production gọi `unaccent(...)` không ghi
rõ schema; `patient.full_name_unaccent` là cột GENERATED nên dòng bệnh nhân đầu
tiên được COPY là restore chết. Repo này vốn đã đúng — chỉ bản của production sai.

Đã chứng minh trên **bản sao thật của production (48 bệnh nhân)**:

| Bước | Kết quả |
|---|---|
| Khôi phục production vào postgres:17 (có workaround) | 48 bệnh nhân |
| Áp `supabase/hotfix/20260801_prod_f_unaccent_qualify.sql` | OK — `Nguyễn Thị Hằng → Nguyen Thi Hang` |
| Cột GENERATED sau khi sửa | nguyên vẹn, đúng |
| Dump lại rồi khôi phục **KHÔNG workaround** | **sạch, 48 bệnh nhân** |

Câu lệnh áp lên production (một câu, giữ nguyên oid, không đổi kết quả hàm, chạy
lại nhiều lần vẫn an toàn):

```bash
psql "$(grep '^DATABASE_URL=' .env.prod | cut -d= -f2- | sed 's/postgresql+asyncpg:/postgresql:/')" \
     -v ON_ERROR_STOP=1 -f supabase/hotfix/20260801_prod_f_unaccent_qualify.sql
```

Sau khi áp, chạy lại `bash scripts/restore-drill.sh` trên bản backup production
kế tiếp — nó phải xanh mà **không cần** dòng `sed` trong drill.

## 6. Việc phải làm trước khi bàn tiếp

1. Thêm `visit_amendment`, `patient_contact_channel`, `patient_next_of_kin` (kèm
   trigger append-only) vào schema đích bằng migration mới.
2. Viết script chuyển dữ liệu, chạy trên bản sao, **so từng bảng theo số dòng**.
3. Quyết `clinic_id` cho dữ liệu cũ — tất cả thuộc Dr4Women, nhưng phải ghi rõ.
4. Chỉ khi (1)–(3) xanh mới bàn tới lịch cutover.

**Chưa có gì bị thay đổi trên production.** Toàn bộ phần trên là đọc và dry-run.
