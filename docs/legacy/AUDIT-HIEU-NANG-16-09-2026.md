> LỖI THỜI (chuyển legacy 01/10/2026): phép đo hiệu năng 16/09, đúng tại thời điểm — đừng làm theo.

# Audit hiệu năng — 16/09/2026

**Chưa sửa gì.** Đây là Phase 1–3: hiểu → đo → xếp hạng. Mọi con số dưới đây lấy
từ `pg_stat_statements`, `pg_stat_user_tables` và `/ops/telemetry` của stack thật
đang chạy, không phải từ đọc code rồi đoán.

> Nguyên tắc dẫn đường: **không tối ưu thứ chưa chứng minh là nút thắt**, và
> **đúng đắn quan trọng hơn nhanh**.

## 0. Bản đồ hệ thống

```
Trình duyệt
   │
   ├─ proxy.ts (middleware Next)   ← CHẠY MỌI REQUEST
   │     ├─ supabase.auth.getUser()  → GoTrue → 4 truy vấn DB
   │     └─ SELECT staff             → PostgREST → 1 truy vấn
   │
   ├─ Server Component / BFF (app/api/*)
   │     ├─ fetchFromBackend → FastAPI  (đường ĐÚNG)
   │     └─ supabase.from(...)          (đường TẮT — còn 71 tệp)
   │
FastAPI ── asyncpg pool ── Postgres (CÙNG MÁY với API)
   │
   └─ RabbitMQ → worker (việc nền)
```

Tình trạng chung: **hệ không chậm ở tải hiện tại.** p50 11,8ms · p95 123ms ·
p99 151ms · 0 request vượt 1s. Mọi việc dưới đây là chuẩn bị cho tải thật, không
phải chữa bệnh đang có.

---

## 1. Nút thắt — xếp theo Tác động × Rủi ro sửa

| ID | Vấn đề | Tác động | Rủi ro sửa | Ưu tiên |
|---|---|---|---|---|
| OPT-001 | Middleware xác thực lại ở MỌI request → ~5 truy vấn DB mỗi lần | **Rất cao** | Trung bình (chạm bảo mật) | P1 |
| OPT-002 | Bảng tuần đặt lịch toả ra (số bác sĩ + 1) × 7 lời gọi sức chứa | **Cao** | Trung bình | P1 |
| OPT-003 | `/appointments/policy` gọi lại mỗi lần render trang | Thấp | Rất thấp | P2 |
| OPT-004 | 71 tệp giao diện còn chạm thẳng database | Trung bình | Cao (việc dài) | P2 |

---

### OPT-001 — Middleware trả tiền xác thực ở mọi request

**Ở đâu:** `src/dashboard/proxy.ts` (matcher phủ mọi đường trừ tài nguyên tĩnh).

**Đang làm gì:** mỗi request — kể cả mỗi lần chuyển trang, mỗi lời gọi `/api/*`
từ trình duyệt — chạy `supabase.auth.getUser()` rồi `SELECT staff`.

**Bằng chứng** (`pg_stat_statements`, một stack chỉ có tôi dùng cả ngày):

| Truy vấn | Số lần | TB | Tổng | % thời gian DB |
|---|---:|---:|---:|---:|
| `SELECT staff … WHERE auth_user_id` (PostgREST) | 11.704 | 8,32ms | 97,3s | **18,2%** |
| `SELECT users …` (GoTrue xác minh) | 28.256 | 2,25ms | 63,5s | 11,9% |
| `SELECT sessions …` | 28.471 | 0,87ms | 24,7s | 4,6% |
| `SELECT identities …` | 28.467 | 0,58ms | 16,6s | 3,1% |
| `SELECT mfa_amr_claims …` | 28.380 | 0,38ms | 10,9s | 2,0% |
| `set_config(...)` (PostgREST dựng phiên) | 20.685 | 2,25ms | 46,6s | 8,7% |

Cộng lại: **gần 49% toàn bộ thời gian database của hệ là để trả lời câu
"anh là ai"** — lặp lại ở từng request.

**Vì sao đắt:** `getUser()` của supabase-js LUÔN đi mạng tới GoTrue (nó cố ý
không tin chữ ký ở client). Mỗi lần gọi kéo theo 4 truy vấn trong schema `auth`.
Cộng thêm một vòng PostgREST cho `staff`.

**Đề xuất** (cần Tuyền chốt, vì nó chạm bảo mật):
1. **Xác minh JWT tại chỗ** (chữ ký + hạn) thay cho `getUser()` ở middleware —
   bỏ được 4 truy vấn/request. Chữ ký vẫn là chữ ký; thứ mất đi là khả năng
   nhận ra một phiên vừa bị thu hồi **trong vòng đời token (1 giờ)**.
2. **Nhớ tạm câu trả lời `staff`** theo `auth_user_id`, hạn 60s, trong tiến
   trình. Cái giá: một nhân viên vừa bị khoá còn vào được tối đa 60 giây.
3. **Bỏ qua middleware cho request tải trước của Next** (prefetch RSC) — đây là
   phần thuần lãng phí, không mất gì cả.

Làm (3) trước: lãi thật, rủi ro gần bằng không. (1) và (2) là đánh đổi bảo mật —
phải là quyết định của Tuyền, không phải một lần "tối ưu" lặng lẽ.

**Kiểm chứng:** đếm lại `calls` của 6 truy vấn trên trước/sau, trên cùng một
kịch bản `scripts/tests/buoi-kham-that.py --ghi 5`.

---

### OPT-002 — Bảng tuần đặt lịch toả ra N×7 lời gọi

**Ở đâu:** `src/clinicai/services/capacity_service.py::bang_tuan`.

**Đang làm gì:** mỗi ô của lưới là một lời gọi `quote()` riêng:

```python
ket_qua = await asyncio.gather(*(mot_o(bs, d) for bs, _, _ in hang for d in ngay))
```

Với 3 bác sĩ + hàng "Chưa phân bác sĩ" × 7 ngày = **28 lời gọi** cho một lần mở
màn Đặt lịch. Mỗi lời gọi chạy truy vấn sức chứa — cái đắt nhất trong các truy
vấn của ứng dụng:

| Truy vấn | Số lần | TB | Tổng | % |
|---|---:|---:|---:|---:|
| `WITH hours AS (SELECT … clinic_hours_for_date …)` | 2.489 | **21,24ms** | 52,9s | 9,9% |

**Vì sao đáng lo:** nó tuyến tính theo SỐ BÁC SĨ. Hôm nay 4 hàng → 28 lời gọi
≈ 590ms công việc DB (chạy 6 luồng song song nên người dùng thấy ~100ms). Phòng
khám thật 10 bác sĩ → 77 lời gọi ≈ **1,6 giây công việc DB cho một lần mở màn**.
Chốt `Semaphore(6)` giữ cho nó không nuốt hết pool — nghĩa là nó đã được biết là
nặng, chỉ chưa được sửa.

**Đề xuất:** cho `quote()` nhận KHOẢNG NGÀY và DANH SÁCH bác sĩ, trả lưới trong
một lượt. Luật sức chứa không đổi, chỉ đổi hình dạng truy vấn.

**Rủi ro:** trung bình — sức chứa là tim của đặt lịch, và trigger
`enforce_slot_capacity` phải vẫn nhìn thấy cùng một con số.
**Bắt buộc:** chạy đối chiếu ô-với-ô giữa bản cũ và bản mới trên cùng một tuần
trước khi đổi; lệch một ô là dừng.

---

### OPT-003 — `/appointments/policy` gọi lại mỗi lần render

Đã có `cache()` của React nên chỉ một lần mỗi lượt render — nhưng mỗi lần chuyển
trang là một lượt render mới. Đo một lần mở `/reception/queue`: 4 lời gọi
backend (`/me` 0,6ms · `policy` 4,5ms · `thong-bao` 3,9ms · `work-items` 34ms).

Luật đặt lịch đổi vài tháng một lần. Nhớ tạm 60s trong tiến trình → bớt ~4,5ms
mỗi trang. **Lãi nhỏ, rủi ro gần bằng không** — làm cùng lúc với OPT-001(3).

---

### OPT-004 — 71 tệp giao diện còn chạm thẳng database

Đây là món nợ kiến trúc đã ghi trong `CLAUDE.md` ("13/08 còn 42/63 route"), nay
đếm lại theo tệp: **71**. Vừa là vấn đề đúng-đắn (luật nghiệp vụ rò ra TSX) vừa
là vấn đề hiệu năng (PostgREST dựng lại phiên mỗi request — xem `set_config`
20.685 lần, 8,7% thời gian DB).

Không sửa ồ ạt. Mỗi lần chạm vào một màn thì kéo màn ấy về FastAPI.

---

## 2. Rủi ro ĐÚNG-ĐẮN (quan trọng hơn hiệu năng)

| Việc | Tình trạng |
|---|---|
| Khoá lạc quan khi hai người cùng sửa | ✅ có: `revision` (bệnh án), `version` (chỉ định) → 409 |
| Chống gửi trùng (idempotency) | ✅ có: `Idempotency-Key` ở các cửa ghi |
| Bất biến ép ở Postgres, không chỉ ở Python | ✅ có: trigger sức chứa, cấm xoá cứng 3 bảng, CHECK sinh hiệu |
| Hai tab đè nháp của nhau | ✅ vừa vá (`lib/ma-tab.ts`) |
| Một tài khoản hai máy đá nhau | ✅ vừa vá (`REFRESH_TOKEN_REUSE_INTERVAL=10`) |

---

## 3. Những thứ KHÔNG nên làm lúc này

- **Thêm Redis.** `docs/SO-LUAT.md` Phần 7 đã cân nhắc và loại ở quy mô này.
  Nút thắt đo được không phải thiếu cache dùng chung — là gọi lặp ở middleware.
- **Đổi đường ray chỉ định** (`work_item` → `service_order`). Xem
  `DANG-LAM` mục −0002: nó viết lại phần thực hiện của cả hệ.
- **Thêm index hàng loạt.** Chưa thấy truy vấn nào chậm vì thiếu index; các
  bảng nghiệp vụ còn nhỏ (visit 118, work_item 832 dòng). Thêm index bây giờ là
  trả phí ghi để mua một thứ chưa cần.
- **Tối ưu frontend render.** Chưa đo được vấn đề nào; đừng đụng trước khi có
  số.

---

## 4. Thứ tự triển khai an toàn

1. OPT-001(3) bỏ qua middleware cho prefetch + OPT-003 cache policy — lãi ngay,
   rủi ro gần bằng không, một PR.
2. Hỏi Tuyền về OPT-001(1)(2): đánh đổi "phiên bị thu hồi chậm nhận ra".
3. OPT-002 gộp lưới tuần — PR riêng, kèm đối chiếu ô-với-ô.
4. OPT-004 kéo dần từng màn, mỗi lần chạm tới.

## 5. Chỉ số còn thiếu để lần sau khỏi phải đoán

Đã có: p50/p95/p99 theo route, 2xx/4xx/5xx, đếm request chậm, CPU/RAM/đĩa
container, tuổi backup, **mốc diễn tập phục hồi**, **phiên bản đang deploy**.

Còn thiếu:
- **số truy vấn DB mỗi request** — chỉ số bắt N+1 nhanh nhất; không có nó thì
  phải ngồi đọc `pg_stat_statements` như hôm nay.
- **req/s và số người đang dùng** — để biết một con số p95 là của 3 người hay
  300 người.
- **độ sâu hàng đợi RabbitMQ + việc nền hỏng**.
- **chỉ số nghiệp vụ**: lượt khám/giờ, check-in, tỉ lệ hoàn tất. Hệ có thể
  "xanh" toàn bộ trong khi phòng khám đứng hình.
- **ngưỡng cảnh báo có phân cấp** đẩy qua Telegram (kênh đã có).
