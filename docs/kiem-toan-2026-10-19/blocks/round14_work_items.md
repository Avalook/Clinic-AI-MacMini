# Round 14 — Work items: ownership, scope và SLA

**Nguồn:** snapshot `/tmp/clinicai-audit-main-956ba4f2`, SHA được giao `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Snapshot export không có `.git`; không tự xác minh commit. Đây là static read-only targeted trace; không chạy test/app/HTTP/DB/VPS/CI, không truy cập secrets/PHI và không sửa nguồn ứng dụng.

**Kết quả:** một candidate MEDIUM về lệnh đổi trạng thái không kiểm cơ sở của visit/appointment liên kết. Chưa xác nhận production hoặc sự cố thực tế. Không promote thêm candidate về ownership, idempotency, stale update hoặc SLA trong lát đã đọc.

## Candidate mới

### CAND-R14-WI-SCOPE-001 — Lệnh đổi trạng thái work item không kiểm tra cơ sở của lượt gắn kèm

- **Kích hoạt:** nhân viên có identity ở location A, cùng clinic và có role/quyền hợp lệ, biết UUID work item gắn visit/appointment ở location B; gọi trực tiếp `POST /api/v1/work-items/{id}/commands/{start|complete|skip|cancel}` khi transition hợp lệ.
- **Bằng chứng:** `WorkItemService.issue` khóa item và xác minh membership role/clinic (`work_item_service.py:143-168`), sau đó áp quyền khu/role và blocker. UPDATE ràng buộc status, clinic và expected_version tùy chọn (`:243-269`), nhưng không join visit/appointment hoặc so `identity.location_id`. Cùng service, worklist có join location và predicate location-scoped (`:541-617`). API đưa cả bốn lệnh qua `_run` vào cùng service (`routers/work_items.py:180-263`); identity có `location_id` bắt buộc (`identity.py:180-193`) và BFF chuyển location header (`backend-proxy.ts:115-124`).
- **Tác động:** command có thể ghi trạng thái/event cho luồng ở cơ sở khác. Riêng `skip` có thể giải phóng bước sau; các kiểm tra clinic, role/quyền workspace, transition, blocker và version vẫn chạy. Không thấy đường vượt tenant/clinic.
- **Giới hạn:** chỉ cùng clinic, phụ thuộc caller biết UUID và item có visit/appointment ở cơ sở khác. Work item không gắn lượt/lịch (như OPS locationless) hiện được chú thích là xuất hiện ở cả hai cơ sở, nên cần giữ đúng policy ấy. Không có bằng chứng production hoặc số lần xảy ra.
- **Test gap:** `test_work_item_service.py:88-156` kiểm tra clinic/membership role, không kiểm tra hai cơ sở trong cùng clinic. Test được đọc tĩnh, không chạy.
- **Acceptance:** với một clinic/hai location, identity A cùng role/quyền không thể start/complete/skip/cancel item của B; identity B tiếp tục theo gate/transition hiện hành; locationless OPS giữ policy. Lệnh bị từ chối trước UPDATE/event.

## Khử trùng và lát khác đã rà

`WORKITEM-API-001` (held) là chênh lệch BFF `reassign` và backend, không có caller UI đang hoạt động. `WORKITEM-POLICY-001` (held) là câu hỏi mine_only, không phải authorization. `CLIN-004` nói về claim/assignment/hand-off, khác quyền đổi trạng thái qua location boundary. `API-001` là scope hàng đợi (pinned code hiện đã lọc cơ sở); `API-002` và GET `/visits/{visit_id}/work-items` là đường đọc, được loại khỏi candidate mutation này. `AI-001` là giới hạn monitor 200 dòng, không đủ để kết luận mất SLA per-item.

Service khóa row trong transaction, kiểm transition, blocker cho start/complete, tăng version và ghi event cùng transaction. API có IdempotencyGuard; UI start/complete gửi expected_version. Skip/cancel không có active dashboard caller được thấy trong static scan. SLA OPS được gán due time và monitor đổi priority khi quá hạn; worklist trả due_at/priority, nhưng bảng hành động không hiển thị hai trường này. Overdue helper không có import trong dashboard caller scan. Những điểm này không tạo candidate độc lập trong lát này; AI-001 vẫn là giới hạn hiện hữu cần giữ riêng.

`findings.json` có một candidate. `coverage.json` ghi phạm vi, hashes, full/partial và test chỉ đọc. Kết quả chỉ áp dụng exact pinned snapshot; chưa xác minh production.
