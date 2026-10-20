# Audit vận hành và phục hồi — round 10

Nguồn kiểm toán: snapshot exact main `/tmp/clinicai-audit-main-956ba4f2`, SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là kiểm toán tĩnh chỉ đọc. Không kết nối DB/VPS/production, không đọc secrets/PHI, không chạy test, không sửa ứng dụng/migration hoặc ledger.

## Kết quả

Có **1 candidate mới**, `CAND-OPS-001` (HIGH, `confirmed_static`): nhịp Kuma báo backup thành công trước khi systemd chạy bước đẩy Viettel CFS. Bước CFS là lệnh `ExecStart` tiếp theo nhưng có tiền tố `-`, nên lỗi upload không làm service thất bại. Trong khi đó, `backup-db.sh` ghi `succeeded=true` sau kiểm tra bản local và gửi heartbeat `status=up`; trường `offsite_uploaded` của file trạng thái chỉ phản ánh R2, không được cập nhật bởi uploader CFS. Ops service không dùng cờ này để đổi trạng thái tổng thể, và thẻ `/ops` không hiển thị nó.

Nếu CFS mất mount/không truy cập được trong khi bản local vẫn được tạo, các lần chạy sau vẫn làm mới heartbeat. Khi đó Ops/Kuma có thể cho thấy backup còn mới dù không có xác nhận bản sao ngoài VPS cho các artifact đó. Nếu VPS hỏng trong cùng khoảng thời gian, bản local không bảo vệ được. Không có bằng chứng tĩnh rằng CFS đang lỗi hoặc dữ liệu đã mất. Chi tiết trigger, caller, side-effect, giới hạn và tiêu chí nghiệm thu nằm trong [findings JSON](round10_ops_recovery.findings.json).

## Đối chiếu ledger và quy trình hiện hành

Đã so với `PHAT-HIEN.json` để tránh trùng. `INF-001` và `INF-006` đã ghi các lỗ hổng về thành phần backup và việc chưa chứng minh phục hồi đầy đủ; candidate này giữ phạm vi riêng: heartbeat/status/UI không xác nhận kết quả upload CFS. `INF-015` là lỗi nạp Caddyfile khi deploy; `DB-006` là transaction boundary của migration runner; `DB-005` là onboarding tenant. Không sửa canonical ledger.

Theo hướng dẫn hiện hành, môi trường đích là một VPS với Supabase tự host. Kiểm tra source thấy deploy prod và migration là hai bước riêng, deploy có kiểm tra source SHA/nhánh và trạng thái dirty; migration runner hỗ trợ thử khô và chỉ áp khi có `--apply`. Các vấn đề restore/đầy đủ dữ liệu không được mở rộng thành phát hiện mới vì đã có mục tương ứng trong ledger. Snapshot không kèm `docs/SO-LUAT.md`, `docs/VAN-HANH-MAY-CHU.md` hoặc `RUNBOOK-LEN-PROD-DOT-1610.md`; runbook ngoài snapshot chỉ được dùng để khử trùng, không làm evidence cho findings.

Không promote phát hiện mới về runtime CFS/Kuma, khôi phục DB thật, TLS hay tình trạng container: chúng cần trạng thái vận hành không có trong source. Các lát code, file, SHA-256 và phạm vi đọc chính xác được liệt kê trong [coverage JSON](round10_ops_recovery.coverage.json).

## Nghiệm thu candidate

Trên môi trường staging/disposable, cho backup local thành công nhưng làm CFS unmounted, upload lỗi và checksum mismatch. Từng trường hợp phải giữ cảnh báo offsite ở mức warning/critical, hiện rõ trong `/ops`, và không ghi receipt thành công. Sau khi CFS hoạt động lại, chỉ trạng thái upload có checksum khớp cho đúng bộ artifact mới đóng cảnh báo. Không dùng dữ liệu khách thật trong probe.
