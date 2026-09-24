# TH-01 — Thực hiện dịch vụ (Lifecycle v1 Slice 5)

| | |
|---|---|
| **Mã** | TH-01 |
| **Module chủ** | `execution` |
| **Trạng thái** | ĐÃ CODE 23/09 — backend + 15 test + **màn phòng đã chuyển** (`/phong/[ma]`); chưa bấm thật trên trình duyệt |
| **Contract** | `docs/ai/lifecycle-v1/ClinicAI-EXECUTION-v1.md` (đóng băng 22/09) |

## 0. Một chỉ định, nhiều lần làm

Máy siêu âm hỏng lúc 10:05 thì **lần làm #1** dừng; **lần #2** ở phòng khác bắt
đầu lúc 10:18. Luật cũ "mỗi chỉ định chỉ được bắt đầu một lần" sai với đời thật.
Luật đúng: **mỗi lần làm chỉ được bắt đầu một lần**.

## 1. Trigger
Phòng dịch vụ · vai: ai có khối "Thực hiện dịch vụ" (mặc định bác sĩ, BS siêu âm,
điều dưỡng SA, thư ký y khoa, trưởng ca).

## 2. Command

```text
StartService         POST /luot-kham/orders/{id}/execution/bat-dau
CompleteService      POST /luot-kham/orders/{id}/execution/xong        + attempt_id
MarkNotPerformed     POST /luot-kham/orders/{id}/execution/khong-lam   + lý do
InterruptService     POST /luot-kham/orders/{id}/execution/gian-doan   + attempt_id + lý do
PrepareServiceRetry  POST /luot-kham/orders/{id}/execution/lam-lai     + attempt_id bị dừng
```

**`attempt_id` bắt buộc** khi Xong và Gián đoạn. Không phải thủ tục thừa: một
request mạng cũ của lần #1 tới muộn **không được** đóng lần #2 đang chạy.

## 3. Events

| Sự kiện | Khi nào |
|---|---|
| `service.started` | mở một lần làm |
| `service.completed` | lần làm ấy xong — **khác** `result.ready` |
| `service.not_performed` | tới lượt mà cuối cùng không làm (kèm cờ **đã thu tiền**) |
| `service.interrupted` | đang làm thì phải dừng |
| `service.retry_prepared` | người quyết định làm lại |

## 4. Bốn thứ KHÔNG BAO GIỜ tự động

Khi dừng giữa chừng hoặc không làm được, hệ thống **không** tự hoàn tiền, **không**
tự đánh dấu đã xong, **không** tự mở lần làm mới, **không** tự chọn phòng khác.
Mỗi thứ là một quyết định của người, và có lệnh riêng.

Riêng "làm lại" cố ý là lệnh **riêng**, không để `StartService` tự hiểu — vì làm
lại có thể cần bác sĩ đồng ý, đổi phòng, sửa máy, hỏi lại khách, xử lý tiền.

## 5. "Chờ làm" là tính ra, không lưu

Lược đồ chỉ nhận: `PENDING · IN_PROGRESS · COMPLETED · CANCELLED · NOT_PERFORMED
· INTERRUPTED`. **"Chờ làm" (`WAITING`) không phải giá trị lưu được**: nó là kết
luận — đang PENDING + khách đã chọn + tiền đủ + đã xếp phòng + không có lần làm
nào đang chạy.

Lưu nó thành một giá trị riêng nghĩa là Thu tiền và Xếp phòng cũng phải nhớ ghi
`execution_status`; ngày nào một trong hai quên là hàng chờ sai mà không ai biết.

## 6. Constraint — ép ở đâu

| Luật | Ép ở đâu |
|---|---|
| Mỗi chỉ định tối đa một lần làm đang chạy | **Postgres** (chỉ mục duy nhất một phần) |
| Số thứ tự lần làm không trùng | **Postgres** |
| Một lượt chỉ có một chỗ chờ "đang làm" | **Postgres** (`uq_queue_entry_one_serving`) |
| Đã xong thì phải biết ai xong, lúc nào | **Postgres** (CHECK) |
| Lý do "Khác" phải có ghi chú | **Postgres** + lệnh |
| Lệnh cũ không đóng lần làm mới | **Lệnh** (`attempt_id` + `FOR UPDATE`) |
| Màn hình cũ không ghi đè | **Lệnh** (`expected_execution_revision`) |
| Chưa đủ tiền thì không bắt đầu | **Lệnh** (FinanceGate) |

## 7. Hotspot — chưa chốt

1. **Ai được đánh dấu "không làm được" và "dừng giữa chừng"?** Hai việc này đụng
   tiền đã thu. Hiện cho cả người đứng phòng; có nên chỉ trưởng ca?
2. **Đã thu tiền mà không làm** → sự kiện có cờ `da_thu_tien`, nhưng **chưa ai
   nghe**. Việc đối soát tiền cần một work item có chủ — lát riêng.
3. **Hoàn tất phiếu kết quả có tự đóng dịch vụ không?** Hiện là hai lệnh tách rời.

## 8. Given / When / Then (11 test đã chạy)

```text
G1  Bắt đầu → sinh lần làm #1, hàng chờ phòng sang "đang làm", phát service.started
G2  Gửi lại cùng khoá → KHÔNG tạo lần làm thứ hai, KHÔNG phát sự kiện thứ hai
G3  Người thứ hai bấm Bắt đầu → bị chặn (màn đã cũ)
G4  Xong → đóng lần làm, đóng hàng chờ, ghi ai bấm
G5  Máy hỏng → dừng → quyết làm lại → lần #2 chạy → lệnh Xong của lần #1 tới muộn
    → EXECUTION_ATTEMPT_NOT_ACTIVE, lần #2 vẫn đang chạy
G6  Gián đoạn KHÔNG tự mở lần làm mới
G7  Lý do "Khác" mà không ghi chú → bị chặn
G8  Chưa bắt đầu mà không làm → NOT_PERFORMED, KHÔNG sinh lần làm giả
G9  Đã bắt đầu thì không dùng đường "không làm"
G10 Lễ tân không bắt đầu được (chưa được cấp khối)
G11 Màn hình cũ → VERSION_CONFLICT
```

## Phụ lục

| Thứ | Ở đâu |
|---|---|
| 5 lệnh | `src/clinicai/services/service_execution_service.py` |
| Endpoint | `src/clinicai/api/v1/routers/luot_kham.py` (`/execution/*`) |
| Đường proxy | `src/dashboard/app/api/luot-kham/route.ts` (`*-v1`) |
| 5 sự kiện | `src/clinicai/events/catalogue.py` |
| Quyền (5, một khối) | `supabase/migrations/20260923000006_quyen_thuc_hien.sql` |
| Test | `src/tests/services/test_service_execution_db.py` |

Bảng `service_execution_attempt` đã có từ Slice 1 nhưng **chưa dòng code nào ghi**
— slice này là phần ruột của nó. Hai endpoint cũ `/orders/{id}/start` và
`/complete` vẫn sống cho tới khi màn hình chuyển hết.

## Màn hình (23/09)

`phong/[ma]/PhongDichVu.tsx` đọc `?xem=thuc-hien&chi_dinh=<id>` trước khi vẽ
nút, vì mỗi lệnh phải kèm đúng `execution_revision` (và `routing_revision` cho
Bắt đầu) mà màn đang thấy. Thiếu chúng thì màn phải đoán, mà đoán sai nghĩa là
ghi đè việc người khác vừa làm.

**MỘT NÚT CHÍNH, NHIỀU SỰ THẬT PHÍA SAU** (ChatGPT tin 156, Tuyền tin 157:
*"chỉ cần 1 nút bắt đầu … xử lý thông minh phía sau, nút chỉ 1"*). Người làm
thấy đúng hai nút trong cả ca.

| Trạng thái đọc về | Nút chính | Hàng phụ |
|---|---|---|
| `PENDING` | **Bắt đầu** | Không làm được? |
| `IN_PROGRESS` | **Hoàn tất** (trong phiếu) | Phải dừng giữa chừng? |
| `INTERRUPTED` | **Làm lại** (trỏ đúng `lan_da_dung.id`) | — |
| `COMPLETED` / `NOT_PERFORMED` | — | tóm tắt · xem lại cả lượt · phiếu vẫn sửa được |

Dịch vụ KHÔNG có mẫu kết quả nào (lấy mẫu gửi đi) thì `[Hoàn tất]` gọi thẳng
lệnh đóng dịch vụ — vẫn một nút, vẫn một chỗ bấm. Bài kiểm ranh giới đếm đúng
**một** chỗ gọi `xong-v1` trong cả tệp, và chặn ba ngoại lệ trở thành nút chính.

Lịch sử các lần làm hiện thành danh sách khi có từ 2 lần trở lên — máy hỏng lúc
10:05 rồi làm lại 10:18 là chuyện phải đọc được, không phải chuyện bị ghi đè.

`attempt_id` lấy từ chính câu đọc, không suy từ `attempt_no`: số thứ tự thì
request cũ cũng đoán được, mã thì không.

Danh sách lý do (`ly_do_khong_lam`, `ly_do_gian_doan`) do máy chủ trả về. Thêm
một lý do mới ở backend là màn có ngay, không phải sửa frontend.

**Kết quả không còn đi kèm lệnh Xong.** "Đã làm xong" và "đã có kết quả" là hai
sự thật khác nhau; kết quả đi qua `PhieuKetQua` (xem `BM-01`).
