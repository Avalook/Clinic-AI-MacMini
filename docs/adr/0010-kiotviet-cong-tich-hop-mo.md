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

## Trạng thái thực hiện (cập nhật 2026-07-30, W7)

**Cổng đã mở, và ClinicAI không phụ thuộc gì vào nó.**

- **Port**: `src/clinicai/ports/pos.py` — `PosPort` (Protocol) với 4 verb
  `push_invoice` / `void_invoice` / `push_stock_movement` / `pull_catalog`, cùng
  `PosInvoice` / `PosStockMovement` / `PosCatalogItem` thuần dataclass. `pull_catalog`
  ghi rõ trong docstring: **chỉ để đối soát**, không được ghi ngược vào ledger.
- **Adapter mặc định** `NullPosAdapter` (`POS_ADAPTER=none`) — nhận rồi bỏ, nhưng vẫn
  hành xử như adapter thật để relay *thoát hàng* thay vì để outbox phình mãi, và để
  đường code đó được chạy ở production chứ không chỉ trong test.
- **Cấu hình 2 tầng**: `POS_ADAPTER` (mức deployment, tắt được cả hệ thống bằng một chỗ)
  và `clinic.settings->'pos'->>'adapter'` (mức tenant, đè lên) — vì multi-tenant không
  thể giả định mọi phòng khám dùng chung một cái quầy. **Dùng POS nào** là cấu hình
  (`clinic.settings`); **đăng nhập POS bằng gì** là bí mật và nằm ở bảng `clinic_secret`
  scope `pos` — không policy, không grant cho `authenticated` (`20260802000004`). Trước
  đó credential nằm chung trong `clinic.settings`, mà `clinic` thì đã `GRANT SELECT` cho
  `authenticated`: policy lọc dòng, không lọc cột, nên mọi nhân sự đăng nhập đều đọc
  được `client_secret` bằng anon key. Không bao giờ trong code.
- **Outbox có transaction**: bảng `pos_outbox` (`20260730000007`). Dòng outbox được ghi
  **trong cùng transaction với payment** — payment commit thì push chắc chắn đã vào hàng
  đợi; payment rollback thì không có gì trong hàng đợi. Đẩy đi sau, nên **KiotViet sập
  không làm hỏng được lượt thu tiền**.
- **Relay + retry + DLQ**: `pos_relay.py`, chạy bằng `python -m clinicai.worker
  --pos-relay` hoặc compose `--profile pos`. Claim từng dòng bằng advisory lock (2 relay
  chạy song song không đẩy trùng), backoff 1′ → 5′ → 25′ → 125′, hết `max_attempts` thì
  chuyển **DEAD**. Dead-letter là kết cục trung thực: tiền đã thu, POS chưa biết, phải có
  người nhìn. Im lặng hoặc retry vô hạn đều giấu chuyện đó đi.

**Tại sao `pos_outbox` riêng chứ không dùng `event_log`:** `event_published` là **một
boolean dùng chung cho mọi consumer**. Notification relay đã claim event bằng cách lật cờ
đó, nên relay thứ hai đọc cùng cờ sẽ ăn trộm thông báo của nhau. Một cái cờ không phục vụ
được hai consumer. *(Nâng `event_log` lên theo dõi delivery per-consumer là việc nên làm
khi có consumer thứ ba.)*

**Adapter KiotViet cố ý CHƯA hiện thực HTTP.** Không ai ở đây có credential hay sandbox,
mà một client viết mò từ tài liệu còn tệ hơn không có: nó trông như đã xong, nó đã được
nối vào relay, và hôm bật lên thì phòng khám phát hiện endpoint nào đoán sai — ngay trước
mặt bệnh nhân. Nên adapter mang đủ phần biết được (cấu hình, tên, hình dạng mapping) và
**từ chối to tiếng** bằng `PosDeliveryError(retryable=False)` → vào thẳng DEAD. Để hoàn
thiện cần: `retailer`, `client_id`/`client_secret`, `branch_id`, và bảng ánh xạ
`service_code` → mã sản phẩm KiotViet.

**Ranh giới được test giữ**: `src/tests/test_pos_port.py::TestBoundary` fail nếu bất kỳ
file nào trong `services/` (trừ `pos_relay`/`pos_config`) import `clinicai.adapters`, và
khẳng định `payment_service.py` chỉ chạm `pos_outbox`, không hề biết chữ "kiotviet".
