# HG-01 — Hẹn giờ (viên gạch cho mọi luật "quá … phút")

| | |
|---|---|
| **Mã** | HG-01 |
| **Module chủ** | hạ tầng dùng chung (`events/hen_gio.py`) |
| **Trạng thái** | ĐÃ CODE 23/09 — 7 test; dùng đầu tiên ở module Trách nhiệm |

## 0. Vì sao

Rất nhiều luật của phòng khám có chữ **"quá … phút"**:

- khách chờ quá 20 phút thì báo trưởng ca;
- việc đối soát tiền để quá 4 giờ thì nhắc lại;
- khách hẹn tái khám mà chưa tới thì gọi.

Trước lát này hệ thống **không có chỗ nào để hẹn một việc trong tương lai**, nên
mọi luật loại ấy đều phải có người nhớ hộ — và người thì quên.

## 1. Vì sao không dùng máy chủ quy trình

Temporal và Camunda giải đúng bài này. Nhưng mỗi cái là **một máy chủ + một
database + một đội worker** nữa để trông, và giá trị họ bán chính là thứ mình đã
có sẵn: một bảng Postgres và một vòng lặp. Ở quy mô một phòng khám, thêm một hệ
thống để trông là thêm một chỗ hỏng lúc 7 giờ sáng.

## 2. Hai luật, cả hai đều có hệ khác trả giá để học

**Luật 1 — hẹn ghi CÙNG giao dịch với việc sinh ra nó.** Mở việc ở một giao
dịch rồi hẹn nhắc ở giao dịch khác thì có ngày việc mở mà lời nhắc không bao giờ
tới. Đúng loại hỏng không ai phát hiện cho tới lúc cần.

**Luật 2 — tới giờ phải KIỂM LẠI hiện trạng.** Lời nhắc đặt lúc 10:00 cho 10:20
không biết chuyện lúc 10:05 người ta đã xử lý xong. Bắn một lời nhắc sai là cách
nhanh nhất để người trực học cách bỏ qua **mọi** lời nhắc — sau đó lời nhắc đúng
cũng vô dụng.

Vì luật 2, mỗi loại hẹn tự trả lời "giờ còn cần làm nữa không?", và **"hết cần"
là một kết thúc bình thường**, không phải lỗi.

## 3. Ép ở đâu

| Luật | Ép ở đâu |
|---|---|
| Một loại hẹn + một đối tượng = một cái đang chờ | **Postgres** (chỉ mục duy nhất một phần) |
| Worker chết giữa chừng thì hẹn quay lại hàng | thuê có hạn + `thu_hoi_hen_treo` |
| Hỏng thì thử lại, quá 5 lần thì CHẾT có tiếng | vòng chạy |
| Loại hẹn không ai nhận → CHẾT, không im lặng nuốt | vòng chạy |

## 4. Dùng đầu tiên: việc không được để lâu

| Việc | Hạn | Tới hạn mà còn mở |
|---|---|---|
| Đối soát tiền (khách đã trả mà không làm) | 4 giờ | nâng lên ưu tiên cao nhất (P0) |
| Quyết định làm lại | 8 giờ | nâng lên P0 |

Đối soát tiền gắt hơn vì đó là tiền của khách.

## 5. Given / When / Then (7 test)

```text
G1  Chưa tới giờ → chưa làm
G2  Tới giờ → làm, ghi "đã làm"
G3  Người ta xử lý xong trước → KHÔNG nhắc, ghi "hết cần"
G4  Hẹn hai lần cho một chuyện → chỉ một cái
G5  Xong sớm → gỡ hẹn
G6  Worker chết giữa chừng → thu hồi được
G7  Đường trọn vẹn: sự kiện → việc có hạn → tới hạn → P0
```

## 6. Chạy ở đâu

Cùng tiến trình với người đưa tin: `python -m clinicai.worker --su-kien`. Tách
một tiến trình nữa chỉ để chạy một vòng lặp là thêm một thứ phải trông mà không
được gì.

## 7. Hotspot

1. **Chưa ai bắn Telegram khi việc quá hạn** — relay đang tắt có chủ ý. Hiện chỉ
   nâng ưu tiên để nổi đầu bảng.
2. **"Khách chờ quá 20 phút"** chưa nối: cần chốt mốc đếm từ lúc nào (check-in
   hay lúc vào hàng chờ phòng).

## Phụ lục

| Thứ | Ở đâu |
|---|---|
| Bảng | `supabase/migrations/20260923000008_hen_gio.sql` |
| Hạ tầng | `src/clinicai/events/hen_gio.py` |
| Dùng đầu tiên | `src/clinicai/events/consumers/trach_nhiem.py` |
| Test | `src/tests/services/test_hen_gio_db.py` |
