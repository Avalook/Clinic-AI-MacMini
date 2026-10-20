# Round 30 — xuất hóa đơn, danh mục thuốc và bàn giao lượt khám

Snapshot exact-main: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc tĩnh; source hash được đối chiếu với cây ghim. Không chạy ClinicAI/tests/API/DB/provider/VPS/production; không đọc secrets/PHI.

## Kết quả

- Không thêm finding canonical. Luồng mốc “khám xong”, hoàn tác và “làm trước, thu sau” nhất quán trong phần đã trace; các test được đọc, không chạy.
- Giữ bốn câu hỏi sản phẩm/nghiệp vụ trong `round30_observations.json`: (1) tải XLSX một hóa đơn nhiều thuế suất; (2) refund không gắn dòng chỉ cảnh báo ở preview; (3) hai ID thương hiệu thuốc cùng alias; (4) event chốt hóa đơn 0đ khi xác nhận lại bằng key mới.
- Không suy ra lỗi kế toán, kê đơn sai hoặc incident từ các quan sát trên. Cần owner kế toán/dược/catalog chốt contract, hoặc fault/synthetic test trước khi nâng mức.
- Không trùng finding mới với ledger; không đổi severity hoặc disposition finding cũ.

## Cổng sản phẩm được đề xuất

1. Mẫu kế toán phải nghiệm thu trên file được mở độc lập khỏi preview; lựa chọn nhiều thuế suất hoặc bị chặn an toàn, hoặc xuất theo mẫu đã được kế toán ký nhận.
2. Mọi exception refund theo hóa đơn phải đi cùng artifact tải hoặc làm export fail có giải thích rõ.
3. Catalog kê đơn cần danh tính thuốc ổn định, có chủ dữ liệu và policy tương đương/brand rõ ràng.
4. Audit event phải phân biệt sự kiện chuyển trạng thái với thao tác xác nhận của người dùng; retry cùng key và thao tác mới cần semantics riêng.

## Coverage

`round30.coverage.json` ghi path, hash, line count, vùng đã đọc và prior/current status. Lát bàn giao đã đọc toàn bộ ba service lõi (`chot_0d.py`, `moc_kham_xong.py`, `lam_truoc_thu_sau.py`) cùng trace UI/API/service/test trực tiếp. Lát hóa đơn, thuế và danh mục ghi rõ full-read so với trace chọn lọc. Không chạy bất kỳ test nào trong vòng này.

Full source audit vẫn mở; không dùng trạng thái path để suy thành phần trăm hành vi đã hiểu hoặc tuyên bố sẵn sàng bán rộng.
