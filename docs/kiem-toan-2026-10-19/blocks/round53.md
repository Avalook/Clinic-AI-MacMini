# Round 53 — luật thứ tự bắt buộc (visit_gate_rule) không chặn được qua API

Source SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7. Review used immutable Git blobs via git show. Tests read only and not run. No ClinicAI application, API, DB, provider, VPS, production, secrets or PHI was accessed.

## Finding

- Added OPS-014 MEDIUM: luật seed 'BS Thành khám trước' bắt buộc only_when_other_staff=TRUE. blocks() cho qua khi target_staff_id là None. Hai endpoint ghi tới gate (/dispatch/move, /dispatch/transfer-room) không có trường người đích nên luật không bao giờ chặn; comment hứa kiểm lại khi có người nhưng không có lần kiểm lại. Lượt luồng mới bị move() từ chối; dispatch_order không gọi gate.
- Phân biệt hai khả năng của handoff: (1) luồng cũ — XÁC NHẬN tĩnh là cờ không thể chặn qua API. (2) luồng mới — dùng cơ chế khác (luat_bac_si_bat_buoc lúc đặt lịch), migration 20260808000003 ghi rõ đây là chủ ý chuyển thời điểm thi hành; KHÔNG kết luận luồng mới 'bỏ qua mọi luật'.
- Không biết bảng visit_gate_rule có dòng đang bật ở production hay không (seed khớp theo tên cố định). Không có bằng chứng sự cố.

## Recommendation

Chốt chủ ý sản phẩm rồi hoặc gỡ luật cũ khỏi cấu hình/màn để không ai tin nó đang canh, hoặc truyền người đích và kiểm lại trong transaction, cộng chốt tương đương ở luồng mới. Test API-level cho target không xác định.

Exact ranges and hashes: blocks/round53.coverage.json and PHAT-HIEN.json. Full source audit remains incomplete.
