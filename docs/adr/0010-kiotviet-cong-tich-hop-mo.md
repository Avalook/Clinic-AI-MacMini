# ADR-0010 — KiotViet: mở sẵn cổng tích hợp (anti-corruption layer), không phụ thuộc

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "kiotviet nên thiết kế theo kiểu mở cửa sẵn để chờ kết nối hệ thống của mình tới nó" |
| **Liên quan** | memory `clinicai-payment-inventory-inhouse`, DOD §9, ADR-0012 |

## Context
DOD §9 từng đặt KiotViet làm hệ thống thu ngân/kho. Quyết định 2026-07-30: **ClinicAI tự
sở hữu payment + inventory** (nguồn sự thật nằm trong ClinicAI). Nhưng phòng khám có thể
đã dùng KiotViet, hoặc khách hàng tương lai sẽ dùng — nên không đóng cửa.

## Decision
1. **Nguồn sự thật là ClinicAI.** `payment` + ledger + tồn kho nằm trong DB ClinicAI.
   KiotViet (nếu bật) là **hệ thống ngoài được đồng bộ tới**, không phải nguồn đọc.
2. **Port + Adapter.** Định nghĩa interface thuần Python trong `services/`
   (`PosPort`: `push_invoice`, `push_stock_movement`, `pull_catalog`) — logic nghiệp vụ
   chỉ biết interface. `adapters/kiotviet/` hiện thực interface đó; mặc định là
   `NullPosAdapter` (no-op).
3. **Bật/tắt bằng env + cấu hình theo tenant**, không bằng code: `POS_ADAPTER=none|kiotviet`
   ở mức hệ thống, và bảng cấu hình `clinic` giữ credential từng phòng khám (ADR-0009).
4. **Đồng bộ qua outbox, không đồng bộ trực tiếp trong transaction** (ADR-0002): phát
   event `payment.recorded` / `stock.moved` → worker đẩy sang KiotViet, retry + DLQ.
   KiotViet sập **không** được làm hỏng luồng thu ngân.
5. **Không nhận webhook ghi đè.** Dữ liệu từ KiotViet vào ClinicAI chỉ ở dạng đối soát
   (reconciliation report), không tự sửa ledger.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Port + adapter, mặc định tắt (chọn)** | bán được cho phòng khám có/không KiotViet; không lệ thuộc API bên thứ 3 | phải giữ một lớp trừu tượng dù hiện chưa dùng |
| B. Bỏ hẳn KiotViet | ít code hơn | mất khách hàng đã đầu tư KiotViet; làm lại sau đắt hơn |
| C. KiotViet là nguồn sự thật | không phải xây payment/inventory | mất quyền kiểm soát dữ liệu, không audit được, đi ngược quyết định in-house |

## Consequences
**Tích cực:** thêm POS khác (hoặc phần mềm kế toán) sau này = viết 1 adapter; ClinicAI
chạy độc lập hoàn toàn khi tắt.
**Tiêu cực:** một lớp interface "chưa ai dùng" cần được test bằng `NullPosAdapter` +
một adapter giả trong test, nếu không nó sẽ mục.
**Kiểm chứng:** test khẳng định service payment không import gì từ `adapters/`.
