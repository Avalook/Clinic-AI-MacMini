# Round 13 — vòng đời lịch hẹn (cancel / reschedule / no-show / undo)

Snapshot được kiểm toán: `/tmp/clinicai-audit-main-956ba4f2`, exact-main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Audit tĩnh trên phần vòng đời được giao và callers/tests trực tiếp; không chạy test/runtime/DB, không truy cập VPS/PHI/secrets và không sửa source/migration.

## CAND-BOOK-LIFE-001 — Có thể đánh dấu lịch tương lai là “Không đến”

**Mức: MEDIUM · confirmed-static.** `no_show` chỉ kiểm trạng thái lịch thuộc `_PRE_ARRIVAL`; không kiểm giờ hẹn đã tới hay đã qua. UI lịch tuần chỉ giới hạn thao tác vào ngày hôm nay, nhưng hiện nút “Không đến” cho mọi lịch trước khi đến trong ngày mà không xét `slot_start`. Do đó, một lịch hẹn 10:00 có thể bị đánh NO_SHOW lúc 09:00 từ giao diện hiện có, hoặc lịch ngày xa hơn có thể bị đánh qua PATCH backend.

**Trigger:** Nhân viên lễ tân/quản lý có `reception.checkin.perform` bấm “Không đến” ở lịch tương lai trong ngày; hoặc gửi action `no_show` qua route cho một lịch tương lai.

**Impact:** Lịch đổi sang `NO_SHOW`, không còn giữ ghế và biến mất khỏi lưới tuần. Nếu bệnh nhân vẫn đến theo giờ hẹn, đội vận hành có thể không thấy lịch, và chỗ có thể được cấp cho booking khác. Đây là sai trạng thái có thể tránh được bằng chốt thời gian tại server.

**Evidence exact-main:** `src/clinicai/services/booking_service.py` SHA-256 `583b6667005658acbbcc7e063e9d8220b2a3d02fc3136b078d2710e67c07ecb1`, lines 383–389 cho phép `no_show` từ `_PRE_ARRIVAL`; lines 1036–1039 chỉ xác nhận status trước khi đi tiếp và không có điều kiện thời gian. `src/dashboard/app/(dashboard)/home/WeeklyAppointmentsTable.tsx` SHA-256 `b164e6621ad09d07269bd325f676a12bce4a6412fd7ae38f2eb979500d58bb0a`, lines 1023–1045 ẩn nút với ngày khác hôm nay nhưng không xét giờ hẹn cho các lịch hôm nay. `NO_SHOW` nằm trong nhóm `DEAD_STATUSES` tại `src/clinicai/core/trang_thai_lich.py:23-29`; lịch tuần dùng nhóm này để ẩn và trả ghế ở `src/clinicai/services/week_appointments_service.py:55-57` (SHA-256 `f1ef9400d2de467c032a5b7a0a6b450a4f710184749d0d112ddfb8ed2b1d0e96`). Caller Next và FastAPI đều chuyển action `no_show` xuống service.

**Acceptance:** Quy định ngưỡng “được coi là không đến” cho sản phẩm rồi enforce ở service/backend theo giờ hẹn và chính sách grace period của phòng khám; UI chỉ bật nút khi điều kiện đó thỏa. Có test service/route xác nhận lịch tương lai (kể cả giờ muộn hơn trong cùng ngày) bị từ chối, lịch đã tới ngưỡng được chấp nhận, và trạng thái không đổi khi bị từ chối.

**Giới hạn / dedupe:** Chưa thử endpoint hoặc DB. Không trùng CLIN-005 (race check-in/reschedule), CLIN-010/011 (reschedule/service/history), CLIN-024 (unique violation), CLIN-026 (datetime timezone), CLIN-028/029 (UI patch), FE-012/015, API-001 hoặc SEC-007. Các nhánh đã đọc cho thấy `_update` vẫn dùng compare trạng thái để xử lý concurrent transition; không lập finding race mới. Phần reschedule từ CHECKED_IN đã được CLIN-010 kiểm toán; tác động số queue cũ thuộc cùng trường hợp checked-in đó nên không tách thêm finding.

## Kết quả lát audit

Một candidate vòng đời mới được ghi nhận: no-show có thể đánh trước giờ hẹn. Không phát hiện candidate cancel/undo/decline khác đủ bằng chứng trong phần đã đọc. Coverage phân biệt file/đoạn đã đọc trọn với trace một phần; không hàm ý toàn module hoặc toàn repository đã được audit.
