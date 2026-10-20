# Kiểm tra chất lượng hồ sơ — 19/10/2026

- Root kiểm sự tồn tại, dòng 1-based và hash mọi nguồn baseline của 22 hồ sơ.
- Đối chiếu nguồn main ghim, đọc diff và vùng liên quan; không giả định main=prod.
- FIN-001/DB-003 được chuyển sang đã có bản sửa trên main; DB-001/DB-002 là xử lý một phần.
- Độc lập tái hiện 5 quan sát baseline, 3 quan sát main và điều kiện upgrade ACL có GRANT cũ.
- Các claim audit02/10 về double refund/void không được chép thành lỗi mới vì chưa có chuỗi chứng minh đúng contract.
- RUN-003/004 đỏ được giữ và giải thích schema lệch; không sửa test/DB để che kết quả.
- Không có review bảo mật độc lập bên thứ ba; agent specialist bị quota cắt ngang.
- Main full semantic audit, UI fault injection và restore/capacity/accessibility còn cần làm.

## Công cụ xuất báo cáo

- Dữ liệu chèn HTML đều escape; Markdown tắt raw HTML; script dùng textContent, không innerHTML/eval/network.
- HTML dùng CSP với hash script, không tải font/CDN/tracker.
- 5 kiểm structural/data consistency đạt; Ruff của repo đạt cho các file Python mới trong hồ sơ.
- Browser QA headless1280/375: không tràn trang; tìm CLIN-001=1; lọc patched=2;
  chuẩn bị in mở22 hồ sơ rồi khôi phục filter; không pageerror, không request ngoài file.
- Đã xem screenshot desktop/mobile. Đây chỉ là QA của báo cáo, không phải kiểm UI ClinicAI.

## Toàn vẹn thay đổi

So mọi file trong baseline với SHA-256 ban đầu: không file nào đổi do audit.
Không commit/push/merge, không deploy, không áp migration lên prod hoặc DB dev.
Probe ACL chỉ viết privilege trong transaction của DB tạm và rollback, sau đó xóa DB tạm.
Các file audit là untracked; muốn chuyển môi trường phải mang thư mục/gói ZIP theo.

## Bổ sung kiểm main runtime

RUN-009 xác nhận2 lỗi bằng test service+Postgres trên exact-main checkout (42 migration thiếu đã áp DB tạm). RUN-010 có31 positive-control tests xanh. Không đổi app hay migration. Phân biệt với RUN-003/004 sai phiên bản. Checkout main audit vẫn giữ để tiếp quản, đường dẫn trong STATE.
