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

## 3. Ba bảng chỉ có ở production — **đều RỖNG** (đã đính chính 01/08)

| Bảng | Số dòng thật |
|---|---|
| `visit_amendment` | **0** |
| `patient_contact_channel` | **0** |
| `patient_next_of_kin` | **0** |

> **Đính chính.** Bản đầu của tài liệu này ghi `visit_amendment` có **3.326 dòng**
> và gọi nó là "bảng lớn nhất production". **Sai.** Con số đó do lỗi regex khi
> đọc dump: biểu thức không dừng ở dấu kết thúc khối COPY của `visit_amendment`
> (khối rỗng) mà chạy tiếp sang khối `ward` ngay dưới và đếm luôn 3.321 dòng của
> `ward`. Số thật là **0**.
>
> Migration `20260801000003` **vẫn đúng và vẫn nên giữ** — ba bảng này có thật
> trong schema production và schema đích phải khớp thì mới chuyển dữ liệu được.
> Nhưng mức khẩn cấp tôi gán cho nó ("sẽ xoá 3.326 dòng lịch sử pháp lý") là
> **không có thật**. Chúng là cấu trúc rỗng.

Nó cũng đi kèm function `visit_amendment_append_only` — function duy nhất có ở
production mà repo này không có.

## 4. Khối lượng dữ liệu thật

**4.388 dòng** trên toàn bộ production — trong đó `ward` chiếm 3.321 (dữ liệu
tham chiếu hành chính). Dữ liệu lâm sàng thật chỉ khoảng **1.000 dòng**. Nhỏ. Đây là tin tốt: mọi phương án đều
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

1. ~~Thêm `visit_amendment`, `patient_contact_channel`, `patient_next_of_kin`
   (kèm trigger append-only) vào schema đích bằng migration mới.~~
   **XONG** — migration `20260801000003_adopt_prod_only_tables.sql`. Schema đích
   giờ 47 bảng, **không còn bảng nào chỉ có ở production**. Ba bảng được thêm
   `clinic_id` + RLS + khoá ngoại mà bản production chưa có; trigger append-only
   của `visit_amendment` giữ nguyên ý (đã test: UPDATE bị chặn). Gate đếm bảng
   tenant chuyển 36 → 39, và vẫn bắt được khi một bảng mất `clinic_id`.
2. Viết script chuyển dữ liệu, chạy trên bản sao, **so từng bảng theo số dòng**.
3. Quyết `clinic_id` cho dữ liệu cũ — tất cả thuộc Dr4Women, nhưng phải ghi rõ.
4. **`payment` chặn cutover** — xem §7.
5. Chỉ khi (1)–(4) xanh mới bàn tới lịch cutover.

## 7. Diễn tập chuyển dữ liệu — `scripts/rehearse-data-migration.sh`

Đã chạy thật trên bản backup production, trong container dùng-một-lần. **Không
chạm production.**

**33/34 bảng chuyển đúng từng dòng**, trong đó `ward` 3.321 · `work_roster` 436 ·
`event_log` 133 · `patient` 48 · `visit` 24 · `staff` 56. Khoá ngoại validate lại
sau khi nạp: **0 khoá gãy**.

**Một bảng chặn: `payment`.**

```
ERROR: new row for relation "payment" violates check constraint "payment_positive_amount_ch..."
```

5 dòng payment của production **đều có `amount = 0`**, còn schema đích có CHECK
bắt buộc số tiền > 0. Đây là **xung đột dữ liệu thật**, không phải lỗi script, và
cần phòng khám quyết:

- **(a)** 5 dòng đó là dữ liệu test → bỏ khi chuyển, ghi rõ trong log cutover.
- **(b)** Thanh toán 0đ là hợp lệ (miễn phí, bảo hiểm chi trả toàn bộ) → phải nới
  CHECK ở schema đích thành `>= 0`.

Không được im lặng bỏ 5 dòng đó. Nhắc lại bối cảnh: toàn bộ production có
`service_price.unit_price` rỗng, `drug_catalog.unit_price` rỗng, và cả 5 payment
đều bằng 0 — nhiều khả năng là (a), nhưng đó là kết luận của phòng khám.

**Chưa có gì bị thay đổi trên production.** Toàn bộ phần trên là đọc và dry-run.
