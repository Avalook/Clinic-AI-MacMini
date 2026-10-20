# Round 32 — quyền đọc, định danh, việc nền và luồng chỉ định

Source evidence chỉ lấy từ Git SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`; primary working tree khác SHA và có WIP. Chỉ đọc mã/migration/test; không chạy ClinicAI, API, DB, provider, VPS hay production; không đọc secrets/PHI.

## Kết quả mới

- **CLIN-047 MEDIUM — race tạo hồ sơ cùng CCCD.** CCCD SELECT xảy ra trước advisory lock theo phone; DB không còn unique CCCD. Hai transaction overlap với phone khác/rỗng có thể cùng qua guard rồi insert. Static inference; chưa mô phỏng. Khác CLIN-008 (PATCH) và CLIN-030 (retry sau mất response).
- **SEC-033 MEDIUM — TOCTOU capability khi duyệt draft.** `doi_quyen` chạy trên connection trước transaction; transaction sau kiểm membership/ê-kíp/draft/version nhưng không recheck capability. Thu hồi đúng khoảng giữa có thể để request đang chạy duyệt. Chưa reproduce.
- **CLIN-048 LOW — duyệt draft cũ không vào timeline.** Nhánh legacy cập nhật state và ghi `orders.authorized` trong event_log; timeline projection tiêu thụ domain_event. Chỉ áp dụng nếu còn draft cũ; event_log vẫn là audit record.

## Finding mở rộng và dedupe

- **INF-017** mở rộng từ event `DEAD` sang timer `CHET`: cả hai bị giới hạn 24 giờ; timer giữ `den_gio` cũ. INF-022 vẫn nói về khôi phục từng record. Chưa xác minh production có record cũ.
- **SEC-011** thêm GET phí khám: cùng clinic, cần identity/session nhưng không có capability/assignment guard ở endpoint/service đọc. Không kết luận anonymous hoặc cross-clinic.
- UI `duyet-chi-dinh` đi qua `/api/luot-kham` → `authorize-orders`; không vướng route legacy 410. Retry chỉ định trùng CLIN-031. Clinical form/result/lab và fee không tạo finding mới.
- Giá quote so với current price khi thu giữ ở `round32_observations.json` vì chưa có policy để gọi là lỗi.

`round32.coverage.json` lưu hashes, ranges và test read-not-run. Ledger chỉ nâng path theo phần trace; không hàm ý full-file hay behavioral coverage. Source audit còn mở: nhiều path vẫn scanned/inventoried và một số finding cần kiểm chứng động.
