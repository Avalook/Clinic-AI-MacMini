# Round 11 — Triage các lát source

Ngày 19/10/2026. Nguồn là snapshot exact-main `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Chỉ đọc tĩnh; không chạy test/runtime, không truy cập DB/VPS/secrets/PHI và không sửa app/migration.

## Quyết định

| Candidate | Kết quả | Lý do |
|---|---|---|
| CAND-CLIN-REC-001 | Thêm **SEC-020**, HIGH, `confirmed_static` | Route hồ sơ khám CSKH dùng OR guard của đường tải tệp, bao gồm `reception.checkin.perform` và `crm.manage`; service trả nội dung lâm sàng tổng hợp, chỉ lọc clinic. Ghi rõ đây là ranh giới quyền ở source; chưa kiểm grants production hoặc xác nhận policy trường dữ liệu với chủ sản phẩm. Khác SEC-011 (đường đọc với capability lâm sàng và assignment) và SEC-019 (PostgREST lịch sử/ghi chú). |
| CAND-R11-DASH-FORM-01 | Thêm **FE-016**, MEDIUM, `confirmed_static` | Hai GET chọn mẫu phiếu không khóa trạng thái chọn; callback cũ có thể cập nhật form/revision sau callback mới. Khác FE-007 (đổi bệnh nhân) và CLIN-020/034 (revision/dữ liệu lâm sàng). Chưa chạy component test. |
| CAND-R11-DASH-FORM-02 | Thêm **FE-017**, MEDIUM, `confirmed_static` | `XemLuot` tải theo lượt đang chọn nhưng href in dùng prop lượt gốc. Khác CLIN-021 (revision chưa release trong cùng lượt). Chưa kiểm bằng browser. |
| CAND-R11-FIN-01 | Thêm **FIN-011**, MEDIUM, `confirmed_static` | Báo cáo chốt ca gồm nhiều SELECT không có snapshot đọc chung, sau đó mới INSERT snapshot và sinh `chot_luc`. Một ghi tiền commit xen giữa có thể khiến số chốt lệch mốc; giao dịch timestamp trước `chot_luc` có thể bị đưa vào `sau_chot` ở lần xem sau nếu còn trong truy vấn sống. Khác FIN-007 (trần 5.000 dòng). Chưa mô phỏng concurrency. |
| CAND-R11-FIN-02 | Thêm **FIN-012**, LOW, `confirmed_static` | Predicate `dong_tien.khop` là đồng nhất đại số theo các biến tự dựng và không so tổng với breakdown độc lập; component báo cáo hiện không hiển thị cờ này, nên tác động đã giới hạn ở guard/log. Khác FIN-005/007 (giới hạn dòng truy vấn). Chưa chạy negative unit case. |

## Kiểm tra evidence và phạm vi

Đã tính lại SHA-256 của mọi `source_hashes` và kiểm line range của cả năm candidate trên snapshot ghim; không có hash/range lỗi. Coverage của ba lát được hợp nhất theo mức đọc toàn file, trace một phần hoặc path chỉ inventory; `traced` không được coi là đọc trọn. Ba block chi tiết là `round11_clinical_records.md`, `round11_dashboard_forms.md` và `round11_finance_close.md` cùng JSON/coverage tương ứng.

Các candidate mới đều là nhận định tĩnh. Chưa có route/API authorization test cho SEC-020, concurrency test cho FIN-011, negative reconciliation test cho FIN-012, hoặc component/browser test cho FE-016/017. Không có kết luận về sự cố thực tế, dữ liệu patient/finance bị truy cập hay tiền bị mất.

## Việc còn mở

- Xác nhận policy trường hồ sơ mà CSKH được xem; bổ sung test đi qua FastAPI dependency với vai tiếp đón/CRM, cơ sở và assignment tổng hợp.
- Viết component test đảo thứ tự response khi chọn hai mẫu phiếu và kiểm link in sau khi chọn lượt cũ.
- Chạy test concurrency trên DB disposable để chốt một watermark/cutoff nhất quán; thêm test lệch độc lập cho tổng và breakdown của `dong_tien.khop`.
- Tiếp tục đọc path `scanned`/`inventoried`; round 11 chỉ bao phủ ba lát có chọn lọc, full source audit chưa xong.
