# Round 29 — hồ sơ khách, giám sát và tiền liệu trình

Snapshot cố định: 956ba4f236b1c92f1280d2097018c199e90ce8c7 (main). Chỉ đọc tĩnh; không truy cập production/PHI, không gọi API, không chạy ClinicAI hay test.

## Kết quả

- FIN-017 MEDIUM: hồ sơ khách lấy năm lượt gần nhất để tính khoản còn phải thu, nhưng cộng đã trả trên toàn lịch sử. Nợ còn mở ở lượt cũ hơn có thể vắng khỏi số tổng. Chưa xác minh dữ liệu/volume thực.
- OPS-009 MEDIUM: dispatch overview giới hạn 400 lượt; KPI giám sát tính từ danh sách đó nhưng không có metadata báo cắt. Chỉ kích hoạt nếu clinic vượt ngưỡng phù hợp bộ lọc.
- FIN-004 mở rộng: đường hoàn tiền làm tròn từng lần có thể nhận prepay liệu trình; UI cho số buổi lẻ. Chưa chạy DB probe riêng.
- INF-007 mở rộng: prepay liệu trình đi qua route hoàn tiền commit nghiệp vụ rồi lưu receipt; chưa fault-inject riêng.
- FE-002 mở rộng: trạng thái kết nối/timestamp chung ở màn giám sát không xác nhận freshness của bốn panel.
- FE-004 mở rộng: lỗi tom-tat lần đầu có thể bị hiện thành AI chưa bật.

Hai phát hiện mới còn trên main ghim ở mức confirmed_static. Điều kiện tác động chưa được xác minh production; các test liên quan chỉ được đọc, không chạy. Full source audit còn mở.
