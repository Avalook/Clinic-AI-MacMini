# Round 12 — đặt lịch, slot hold và booking policy

Snapshot được kiểm toán: `/tmp/clinicai-audit-main-956ba4f2`, exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là audit tĩnh; không chạy test/runtime/DB, không truy cập VPS/PHI/secrets và không sửa source hay migration.

## CAND-BOOK-SLOT-001 — Cờ “đang bị luật có ngày đè” bật trước ngày bắt đầu

**Mức: LOW · confirmed-static.** Khi một luật tạm có `date_start` trong tương lai nhưng `date_end >= current_date` giao với khung phút của luật thường trực, `BookingOverrideService.list_rules()` vẫn trả `shadowed=true`. Query chỉ loại luật đã hết hạn bằng `date_end >= current_date` và phép `EXISTS` chỉ so bác sĩ + khung phút; thiếu điều kiện `date_start <= current_date` (và giao khoảng ngày với ngày hiệu lực của standing rule). UI dùng cờ này để hiện nguyên văn “đang bị luật có ngày đè”.

**Trigger:** Quản lý tạo luật ngày cho tuần sau, khoảng ngày kết thúc còn ở tương lai, phủ giờ của luật thường trực; người vận hành mở bảng luật trước khi tới `date_start`.

**Impact:** Bảng cấu hình nói luật thường trực đang bị đè dù ngoại lệ chưa có hiệu lực hôm nay. Người vận hành có thể hiểu sai con số đang áp dụng; resolver/trigger đặt lịch vẫn chọn luật theo ngày thực tế, nên bằng chứng không chỉ ra quyết định nhận lịch sai ở backend.

**Evidence exact-main:** `src/clinicai/services/booking_override_service.py` SHA-256 `81077ad2213351226519726b4d02d85a9ee7c6ab9f2c59ad1c1c7bc7bc77717a`, lines 282–309 (đặc biệt 287, 303–309); UI `src/dashboard/app/(dashboard)/settings/OverridePolicyCard.tsx` SHA-256 `169037149d02af750d1d14c095a691fdfc6814fe548f5329af3ca931c0a17e3c`, lines 439–445. Ngày bắt đầu tương lai được chấp nhận bởi request/service (config route và `validate_rule`); resolver chỉ áp dụng slot override trong `date_start..date_end` theo migration `20260803000009_slot_override_minute_granularity.sql`.

**Acceptance:** Có kiểm thử `list_rules()` với luật tạm bắt đầu ngày mai/tuần sau và cùng khung với standing rule: badge “đang bị đè” phải false trước ngày bắt đầu, true trong ngày hiệu lực, false sau ngày kết thúc. Nếu badge muốn diễn đạt “có một ngày trong tương lai sẽ bị đè”, đổi copy/contract và test đúng nghĩa đó thay vì gọi là “đang”.

**Giới hạn:** Không đánh giá mức độ người dùng thực sự dựa vào badge; không chạy test hoặc xác minh production data. Không trùng các finding CLIN-005/010/011/024/026/028/029, FE-012/015, API-001 hay SEC-007.

## Kết quả lát audit

Một candidate mới, mức thấp, có thể tái hiện từ nhánh dữ liệu tương lai nêu trên. Không phát hiện candidate booking/slot-hold khác đủ bằng chứng trong phần đã đọc. Đã kiểm chéo finding ledger và các block liên quan; không ghi lại các finding được yêu cầu loại trừ. Độ phủ chi tiết và phần chưa đọc trọn nằm trong `round12_booking_slots.coverage.json`.
