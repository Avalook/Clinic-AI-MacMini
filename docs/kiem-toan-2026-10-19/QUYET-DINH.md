# Quyết định và câu hỏi mở

## Đã chốt

- Audit/thiết kế trước, triển khai sửa ứng dụng là đợt sau.
- Context lưu repo; người dùng có thể tiếp tục bằng tài khoản khác.
- HTML tự chứa, nội dung tiếng Việt, có bằng chứng và giới hạn; không biến giả thuyết thành sự thật.
- Đánh giá theo vận hành phòng khám và khả năng thương mại hóa, không theo số công nghệ được dùng.

## Cần quyết định sau khi có chứng cứ

- Mô hình bán: triển khai riêng từng khách, SaaS dùng chung, hay kết hợp.
- Quy mô khách mục tiêu, mức cam kết dịch vụ và ngân sách vận hành.
- Chỉ số alignment và ngưỡng mục tiêu sau khi có baseline đo được.
- Nội dung pháp lý/chứng nhận chỉ kết luận khi có căn cứ và đánh giá chuyên môn phù hợp.


## Cần chủ sản phẩm chốt sau lát cắt workflow v0.19

- Mẫu nội bộ gửi đối tác: có cam kết SLA/nhắc CSKH khi kết quả chưa về không? Nếu có, quy định theo loại dịch vụ/đối tác và owner; nếu không, ghi cách theo dõi thủ công ngoài app. CLIN-012 hiện là design_gap có điều kiện.
- Metadata tiến độ thực hiện dịch vụ trong cùng clinic có thể được mọi nhân viên đăng nhập xem, hay cần capability theo bàn/ca? Reviewer workflow chưa đủ căn cứ để xếp endpoint metadata-only thành finding bảo mật.


## Cần chốt sau checkpoint v0.20

- Ma trận roster rỗng do chưa khai có tiếp tục mở cho mọi vị trí không? Khi đã khai rồi tắt hết, khuyến nghị từ chối mặc định.
- Ai được xem CCCD/SĐT trong audit và bao lâu cần giữ lịch sử? Khuyến nghị audit vận hành không lưu giá trị định danh thô.
- Khi đổi cấu hình phòng trong lúc có lượt đang chờ/xếp, hệ thống phải tự xếp lại, báo conflict hay giao owner xử lý? Cần định nghĩa SLA và trạng thái an toàn.
- Có nghiệp vụ hợp lệ nào cần hoàn tác lần thực hiện mới nhất mà không chỉ định attempt cụ thể không? Khuyến nghị request luôn nhắm đúng attempt/revision.


## Cần chốt sau checkpoint v0.21

- Thu hồi tệp kết quả đã trả: có tự gỡ marker và mở lại H7 khi không còn bản hiệu lực, hay bắt buộc thao tác Hoàn tác trả kết quả? Nếu là thao tác tay, vai/owner và hạn xử lý là gì? (CLIN-019)
- FINALIZED áp dụng giống nhau cho phiếu khám v5 và clinical record không? Nếu cho sửa sau khi chốt, có cần amendment/reason/approval, version và audit nào? (CLIN-020)
- Bản sửa structured result chưa release được in dưới dạng gì? Cổng release áp dụng cả print hay chỉ gửi bệnh nhân/đối tác? (CLIN-021)
- Sản phẩm ban đầu chỉ nhắm một clinic mỗi tài khoản hay cần bác sĩ/nhân viên luân phiên nhiều clinic? Câu trả lời ảnh hưởng FE-009 và tenant onboarding DB-005.
- POS có nằm trong gói đầu tiên không? Nếu có, ai xử lý giao dịch DEAD, SLA và cách đối soát bên ngoài; nếu chưa có operator recovery thì giữ profile tắt (INF-011).
- Các khoản VOIDED sau đó GIU_LAI trả thuốc có còn là phải thu hay thành khoản clinic phải trả? Chốt định nghĩa ledger trước khi sửa PHAR-001/reconciliation.

## Cần chốt sau checkpoint v0.22

- Hàng duyệt kết quả: SLA/retention bao lâu, việc quá 60 ngày chuyển sang overdue queue nào, ai sở hữu?
- Booking: patient_kind chỉ nhận NEW/RETURN hay cho phép None; API phải reject datetime không có offset ra sao? Chốt conflict contract khi unique race.
- Phòng: accepting=false có nên ẩn hẳn khỏi hàng sắp đến hay hiện nhãn tạm dừng? List/count/write phải cùng một policy.
- Relay: fairness theo clinic/event type, max retry, dead-letter owner và SLO oldest pending là gì?
- Checkout/thẻ kho: tải đầy đủ hay dùng cursor/total? Chốt retention và tuổi việc ưu tiên.
- Security: TKYK/siêu âm có phải assignment-limited trên từng file/ảnh hay role capability rộng hơn được chủ ý? Chốt ma trận quyền rồi test cặp identity/patient tổng hợp.
