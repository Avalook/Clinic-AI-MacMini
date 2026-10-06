---
paths:
  - "src/clinicai/**"
  - "src/tests/**"
---

# Sửa backend (FastAPI · service · sự kiện)

- **Router mỏng;** luật nghiệp vụ nằm trong hàm dịch vụ `src/clinicai/services/`
  (Python thuần, test được).
- Hàm nhận ngày/giờ từ người dùng phải **trả giá trị rỗng thay vì ném**, và phải
  có test cho đầu vào rác. Đã có ba lần 500 vì luật này bị bỏ qua.
- Mọi bất biến có kẽ hở tranh chấp phải **ép ở Postgres** (ràng buộc, khoá trong
  SQL), không tự cài khoá trong Python. Xem `docs/SO-LUAT.md` Phần 6.
- **Sự kiện mới** khai ở `src/clinicai/events/catalogue.py` (không khai thì
  `emit_event` từ chối). Thêm bên nghe = thêm consumer, không sửa nơi phát.
  Consumer được đăng ký bằng **tên chuỗi** trong catalogue — "không ai import"
  không có nghĩa là code chết.
- Đổi router/service/route → chạy `python3 scripts/ban-do-code.py` rồi commit
  `docs/BAN-DO-CODE.md` (CI `--kiem` đỏ nếu quên).
- pytest dùng DB chung `chung_test_db`
  (`postgresql://postgres:postgres@127.0.0.1:55600/postgres`) — không tự dựng
  container DB, không reset DB chung. Chi tiết: `docs/CHAY-TEST.md`.
- Kiểu: CI chạy **mypy strict** (`ignore_missing_imports`). LSP pyright của Claude
  Code dùng `pyrightconfig.json` với `useLibraryCodeForTypes: false` — thư viện không
  công bố kiểu (không `py.typed`, vd asyncpg) coi là Unknown, ĐÚNG như mypy coi là
  Any; đừng bật lại (asyncpg sẽ sinh ~970 lỗi giả `PoolConnectionProxy`). Pyright báo
  mà mypy không báo thì kiểm tay, đừng sửa mù.
