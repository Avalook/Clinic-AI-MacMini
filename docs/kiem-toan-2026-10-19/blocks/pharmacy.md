# Lát cắt nhà thuốc — checkpoint v0.19

## Phát hiện tích hợp

**PHAR-001 · MEDIUM · reproduced_local.** Sau khi tiền thuốc được thu/giao rồi phiếu thu thành VOIDED, thao tác HOAN cho thuốc khách mang trả không tìm được cycle do helper chỉ chọn PAID/PENDING_VERIFICATION; transaction rollback trước `drug_return`. Service probe lẫn FastAPI ASGI probe trên DB synthetic xác nhận HOAN trả lỗi/409; GIU_LAI vẫn ghi physical return nhưng không tạo refund. DOI đi chung helper nhưng chưa chạy trực tiếp.

## Bằng chứng và giới hạn

- Exact main `956ba4f236b1c92f1280d2097018c199e90ce8c7`; chi tiết hash/line và acceptance nằm trong `PHAT-HIEN.json`.
- `probes/test_audit_1910_return_after_void_db.py` và `probes/HTTP-VOIDED-RETURN-PROBE.txt`; RUN-036 service probe và RUN-040 ASGI probe. DB tạm, seed template khác pinned seed và đã áp 42 migration; không browser/production/cổng thanh toán.
- Đường GIU_LAI là workaround được code hỗ trợ, vì vậy chưa kết luận mất tiền vĩnh viễn; cần owner và đối soát.

## Tiếp tục

Kiểm DOI, nhiều lần thu gốc, hoàn từng phần, hủy giao, disposition và báo cáo nợ; xác minh người chịu trách nhiệm từ lúc ghi GIU_LAI đến khi hoàn/đối trừ. Phạm vi này chỉ là một luồng, không phải toàn bộ nhà thuốc/kho.

## v0.22 — completeness thẻ kho

- Mở rộng FIN-002: truy vấn thẻ kho `LIMIT 1000`, chỉ log cảnh báo khi chạm trần; API trả `dong` và UI tải một lần, không cursor/total.
- Chưa có dữ liệu chứng minh cơ sở thực tế vượt ngưỡng. Acceptance nên bao gồm đủ 1.005 ledger entries và paging không mất/trùng dòng.

## Round 38 — sale/inventory contract held

Không thêm finding: extra-sale (`luot_vat_tu`/bill/payment) và kho (`vat_tu_phieu`/`vat_tu_txn`/trigger tồn) là hai lifecycle riêng trong code. Tests đọc không chốt yêu cầu sale có tự trừ tồn hay không; giữ đúng câu hỏi policy đã có ở audit 27/09. Không kết luận production mismatch. Xem `blocks/round38.md` và coverage cho hashes/ranges.
