# Round 11 — Chốt ca, đối soát và projection hóa đơn

**Snapshot:** `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`  
**Cách làm:** đọc tĩnh mã nguồn và test hiện có trong snapshot; không chạy test/runtime, không truy cập DB/VPS/secrets/PHI, không sửa app hay migration. Chỉ tạo ba artifact Round 11 được giao.

## Kết quả

Có hai candidate mới, đều là nhận định static trên đúng snapshot; không phải bằng chứng sự cố production.

### CAND-R11-FIN-01 — Snapshot chốt ca không có điểm cắt đọc nhất quán

`ChotSoCaService.chot()` gọi `BaoCaoCuoiNgayService.bao_cao()` để dựng báo cáo, serialize JSON, rồi mới mở transaction riêng để INSERT bản chốt. Báo cáo cuối ngày chạy tuần tự nhiều SELECT trên kết nối lấy từ pool mà không mở transaction đọc chung; phần tồn kho còn được ghép qua một kết nối khác. Migration để `chot_luc` mặc định bằng `now()` lúc INSERT, sau khi các lượt đọc đã kết thúc.

**Trigger:** lúc nhân viên chốt ca, một lần thu/hoàn hoặc thay đổi tiền được commit giữa các SELECT dùng để dựng báo cáo, hoặc sau SELECT liên quan nhưng trước khi INSERT chốt. Ví dụ, lần thu có `paid_at` trước `chot_luc` nhưng commit sau khi query thu đã đọc; snapshot thiếu khoản đó, còn thời điểm ghi nhận lại đặt bản chốt sau khoản thu.

**Ảnh hưởng:** số lưu có thể ghép các thành phần lấy tại những thời điểm khác nhau. Với giao dịch nằm trong các truy vấn sống, lần xem sau thường làm khoản lệch hiện ra trong `sau_chot`; vấn đề được xác nhận ở đây là khoản có timestamp trước `chot_luc` có thể bị phân loại thành phát sinh sau chốt. Không có đủ bằng chứng để khẳng định tiền bị mất khỏi cả snapshot lẫn delta, và chưa có bằng chứng production bị ảnh hưởng.

**Đề xuất:** định nghĩa một cutoff chốt có thể kiểm toán; dựng tất cả thành phần báo cáo từ cùng một snapshot DB và cùng cutoff, rồi ghi bản chốt theo quy tắc tuần tự hóa/khóa phù hợp với các đường ghi tiền. Nếu không khóa đường ghi, các truy vấn phải dùng cùng watermark và phép phân loại giao dịch sau chốt phải dựa trên cùng mốc đó.

**Chấp nhận khi:** có kiểm thử concurrency cố định thứ tự để một giao dịch được commit giữa các bước đọc và giữa bước đọc cuối với INSERT; snapshot phải phản ánh một cutoff duy nhất, khoản trước cutoff nằm trong số đã chốt, khoản sau cutoff chỉ nằm trong delta, và tổng ngày/ca không nhân đôi hoặc bỏ mất giao dịch. Kiểm thử đóng/mở khóa hiện tại vẫn giữ nguyên hành vi.

**Bằng chứng:** `chot_so_ca_service.py` 103–111, 182–229; `bao_cao_cuoi_ngay_service.py` 1194–1207, 1222–1303, 1358–1369; migration `20261014149000_chot_so_ca.sql` 13–23; test `test_chot_so_ca_db.py` 95–163, 257–318. Test đã đọc chỉ chạy các thay đổi tuần tự; phần concurrency kiểm tra nhiều lệnh chốt cùng khóa, không đồng thời thay đổi sổ tiền trong lúc dựng snapshot.

**Giới hạn:** nhận định dựa trên cấu trúc lời gọi và transaction trong code, không chạy mô phỏng concurrency; chưa xác nhận tần suất hoặc incident production. FIN-007 giữ riêng vấn đề cap 5.000 dòng của truy vấn báo cáo: khác trigger và failure mode, không được tính lại ở candidate này.

### CAND-R11-FIN-02 — Cờ `dong_tien.khop` là phép đồng nhất, không phải đối soát độc lập

Trong `dong_tien()`, `dong_tien_vao` được định nghĩa là `tien_thu + no + giam_gia - no_thu_duoc`; `thuc_thu.tong` được định nghĩa là `tien_thu - tra_lai`. Sau đó `khop` so sánh `dong_tien_vao - tra_lai - no - giam_gia + no_thu_duoc` với chính `thuc_thu.tong`. Thế các định nghĩa vào thì hai vế giống hệt nhau với mọi đầu vào số nguyên. Predicate không so tổng với các phần tiền mặt/chuyển khoản, không kiểm tổng theo loại tiền và không đối chiếu với nguồn sổ độc lập. Nhánh warning khi `khop` false vì vậy không thể phát hiện các lệch đó.

**Trigger:** có mismatch trong dữ liệu đầu vào của projection, ví dụ `tong.thu` khác tổng `theo_hinh_thuc`, nhưng các giá trị được dùng để dựng công thức vẫn là số nguyên.

**Ảnh hưởng:** trường `khop` và logger không phát hiện được mismatch giữa tổng và breakdown; test hiện chỉ xác nhận `khop=True` cho các bộ dữ liệu nhất quán. Component báo cáo hiện không render trường này, nên chưa thấy bằng chứng người dùng đang nhận một dấu “khớp” trên UI; tác động hiện tại là mất một kiểm tra/telemetry mà code có vẻ định dùng.

**Đề xuất:** tách “công thức số học đã áp dụng” khỏi “đối soát dữ liệu”. Tạo invariant từ các tổng độc lập đã có (tổng từng hình thức so với tổng thu/hoàn, tổng tiền thực thu so với phép cộng các thành phần; kiểm tra riêng sổ nợ) và trả về `false`/`unknown` khi nguồn thiếu hoặc lệch. Giữ log/cảnh báo gắn định danh phạm vi nhưng không ghi thông tin nhạy cảm.

**Chấp nhận khi:** test cố ý làm lệch `tong.thu` với tổng các dòng `theo_hinh_thuc` và làm lệch tổng TM/CK với số tổng; kiểm tra phải báo mismatch. Các ca thu chia TM+CK, hoàn, nợ thu được và giảm giá vẫn đối chiếu đúng.

**Bằng chứng:** `tom_tat_tai_chinh_service.py` 35–85; consumer warning trong `bao_cao_cuoi_ngay_service.py` 1373–1382; test `test_tom_tat_tai_chinh.py` 59–108 chỉ assert true cho các ca hợp lệ. Snapshot hash của từng file ở `round11_finance_close.findings.json`.

**Giới hạn:** static; chưa tạo input mâu thuẫn rồi chạy hàm. Không có bằng chứng sổ thực tế đang lệch. Không trùng FIN-007: FIN-007 là giới hạn số dòng truy vấn; candidate này là guard đại số không độc lập.

## Dedup và phạm vi

- Đọc các mô tả canonical FIN-001..010, DB-006/007, INF-007 cùng `finance.md`, `finance-main-round2.md`, `round9_api_admin_finance.md`. Không tái cấp ID canonical và không lặp các finding cũ.
- FIN-001..010, DB-006/007, INF-007 không được chép lại. Những candidate ở đây khác trigger/failure mode: khoảng đua khi ghi snapshot chốt ca; và predicate đối soát `khop` không thể thất bại.
- Đã rà projection thuần hóa đơn, service danh sách hóa đơn và test đối chiếu liên quan theo các đoạn trong coverage. Không thấy candidate riêng đủ chắc ngoài hai mục trên; test xfail về hoàn cũ không theo dòng đã ghi rõ là vấn đề chờ quyết định nghiệp vụ, không được tự nâng thành finding mới.
- Block này không khẳng định đã đọc hết codebase; coverage chỉ giới hạn các file/đoạn nêu trong `round11_finance_close.coverage.json`.
