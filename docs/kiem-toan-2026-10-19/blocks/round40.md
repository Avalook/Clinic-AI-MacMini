# Round 40 — migration runner và ledger

Nguồn ứng dụng là Git main ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`; không chạy test, PostgreSQL, DB, app, API, production hay deploy. Kết quả là mở rộng INF-008, không tạo ID trùng cho cùng bất biến “schema commit nhưng ledger chưa ghi”.

`apply-pending-migrations.sh` nói mỗi migration và row ledger nằm trong một transaction. Tuy nhiên, runner nối `BEGIN;`, nội dung file, `INSERT ... schema_migrations`, `COMMIT;` vào cùng stdin psql; structural `git grep` exact pinned SHA tìm thấy **23 migration files** có standalone `BEGIN;` và `COMMIT;`. Một `COMMIT` bên trong file kết thúc transaction đang chạy trước khi script tới row ledger. Nếu runner dừng tại khoảng giữa, lần tiếp theo vẫn xem version là pending và replay migration.

Đây là gap kiểm soát nguyên tử có điều kiện; chưa chạy failure injection, không có bằng chứng migration hiện tại gây data loss hoặc production incident. Một số file được xem có `DROP IF EXISTS`, `ON CONFLICT`/replace pattern; chưa khẳng định mọi migration đều nguy hiểm khi replay. INF-008 giữ mức MEDIUM vì finding hiện tại đã có đường local bootstrap gặp baseline `CREATE FUNCTION` không idempotent; phần runner production được ghi là extension có giới hạn, không nâng severity.

Đề xuất thống nhất contract: migration files không tự quản transaction khi runner chịu trách nhiệm giao dịch; lint cấm `BEGIN`/`COMMIT` top-level; mỗi schema update và ledger row cùng commit. Chạy fault-injection trên disposable DB để dừng đúng giữa schema commit và ledger update, rồi xác nhận retry an toàn. Không thử điều này với production.

PostgreSQL docs giải thích explicit transaction control kết thúc transaction hiện hành; đây là ngữ nghĩa hỗ trợ diễn giải, không phải bằng chứng ClinicAI: [Protocol Flow](https://www.postgresql.org/docs/current/protocol-flow.html), [COMMIT](https://www.postgresql.org/docs/current/sql-commit.html). Coverage và hashes: `blocks/round40.coverage.json`. Full source audit chưa hoàn tất.
