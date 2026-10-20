# Kiểm toán POS outbox — round 12

Nguồn kiểm toán: snapshot exact-main `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc tĩnh source, migration và tests liên quan. Không chạy test/runtime, không truy cập DB/VPS, secrets hoặc PHI; không sửa source, migration hay ledger.

## Kết quả

Không có candidate riêng mới được promote trong luồng POS outbox sau khi truy hết đường tạo invoice/void, transaction enqueue, relay, adapter, worker và tests. Nguồn cho thấy payment cycle mới có ID riêng; invoice được enqueue cùng transaction ghi nhận thanh toán, còn void lấy cùng causal lock với relay, chuyển invoice còn PENDING sang DEAD và enqueue lệnh void. Relay giữ row lock logic và causal lock trong lúc giao, kiểm tra lại PENDING sau khi lấy lock, rồi mới đánh dấu SENT/retry/DEAD. Các nhánh hiện có được bao phủ bởi unit tests mô phỏng adapter.

Các rủi ro gần kề đã được đối chiếu nhưng không mở lại: thiếu UI/chủ sở hữu phục hồi DLQ và adapter thực tế (INF-011); aging cảnh báo delivery DEAD (INF-017); retry cap chung khi worker chết sau claim (INF-018); các vấn đề worker/event/notification INF-005/004/012. Kiến trúc POS adapter hiện tại còn từ chối delivery thay vì triển khai giao tiếp nhà cung cấp; đây là phạm vi adapter/khả năng dùng đã có, không phải lỗi mới của transaction outbox. Contract `PosPort` yêu cầu adapter chịu gọi lặp cùng reference như một invoice; chưa có adapter hoạt động để xác minh hợp đồng đó với vendor.

## Những điểm đã trace

- `payment_service.py`: khi ghi thanh toán, chu kỳ mới được tạo và invoice outbox được enqueue trong transaction; khoản 0 đồng không enqueue invoice. Khi huỷ, payment cycle được cập nhật, khóa causal được lấy, invoice PENDING bị huỷ và sự kiện `invoice_void` được enqueue trong cùng transaction. Việc thu lại sau huỷ dùng cycle ID mới, nên unique key theo `(clinic_id, kind, subject_id)` không chặn invoice của cycle mới.
- `pos_outbox.py` và migration: enqueue dùng `ON CONFLICT ... DO NOTHING`; các bảng trạng thái/unique key/row index nhất quán với khóa idempotency theo cycle. Cancel chỉ cập nhật invoice PENDING.
- `pos_relay.py`: worker chọn due PENDING; tuần tự hoá theo outbox row rồi theo payment cycle; đọc lại status trước khi push. Retry được phân biệt retryable/permanent, exception bất ngờ cũng vào backoff, và chạm số lần tối đa thì DEAD.
- `worker.py` và `pos_config.py`: relay được gọi bởi worker loop; adapter cấu hình theo clinic/secret, thiếu hoặc sai cấu hình không giả vờ thành công mà đi qua null adapter và DEAD. Vận hành/khả năng nhận biết và phục hồi đã thuộc findings đối chiếu.
- Tests hiện có kiểm thử success, retry, permanent rejection, exhaustion, generic exception, unknown kind, null/misconfigured adapter và thứ tự khóa. Không có test tích hợp DB cho race giữa void/push hoặc test phản hồi vendor bị mất sau khi vendor đã tạo invoice; song adapter hợp đồng phải idempotent theo clinic reference. Đây là khoảng trống validation của provider, chưa đủ bằng chứng để kết luận duplicate thực tế vì adapter vendor hiện từ chối.

## Giới hạn và hướng nghiệm thu

Phạm vi đọc và SHA-256 từng file nằm trong [coverage JSON](round12_pos_outbox.coverage.json). Snapshot không chứa tài liệu thiết kế POS được liệt kê trong manifest kiểm toán, nên kết quả dựa trên source/migration/test snapshot. Không suy đoán cấu hình worker production, tình trạng DLQ hiện tại, delivery vendor, semantics API KiotViet hoặc dữ liệu khách hàng. Không chạy tests theo chỉ thị của vòng audit.

Khi bổ sung adapter vendor, nghiệm thu cần dùng môi trường test của nhà cung cấp: giả lập timeout sau khi vendor đã nhận invoice, retry cùng clinic reference không tạo invoice thứ hai; void đến trước/sau invoice được xử lý an toàn; xác nhận mapping tiền tệ/thời gian/rounding; và kiểm thử concurrency void-vs-relay qua PostgreSQL. Đây là tiêu chí acceptance cho adapter tương lai, không phải candidate finding của snapshot hiện tại.

Chi tiết kết quả máy đọc được nằm trong [findings JSON](round12_pos_outbox.findings.json). Không sửa canonical ledger.
