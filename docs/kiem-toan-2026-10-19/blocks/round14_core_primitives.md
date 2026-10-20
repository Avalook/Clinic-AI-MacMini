# Vòng 14 — tiện ích lõi, ngày/giờ và quan sát

Snapshot: `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là lượt đọc tĩnh các file trong `round14_core_primitives.coverage.json`; hash và số dòng được đối chiếu với snapshot.

Đã đọc trọn clock/date helpers, lựa chọn cơ sở, phone normalization, mã vị trí, GS1, helpers quan sát, bootstrap Sentry và các test trực tiếp đã liệt kê. Một đoạn test phone được đọc có mục tiêu; các test không được chạy. Không thấy candidate mới trong lát này.

`main.py` vẫn nối bootstrap Sentry sau `SENTRY_DSN` gate, trong khi quy tắc dự án đánh dấu Sentry là dịch vụ đã chết. Code đặt `send_default_pii=False`, `include_local_variables=False` và `max_request_body_size="never"`; chưa kiểm tra env/runtime nên đây chỉ là policy/configuration drift, không phải bằng chứng Sentry đang hoạt động.

Giới hạn: không chạy test, app, DB hay production; chưa đọc mọi caller của phone/date helpers, chưa audit toàn bộ `core/`.
