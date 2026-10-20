# Round 15 — Ngân sách kết nối PostgreSQL

Nguồn: exact main `956ba4f236b1c92f1280d2097018c199e90ce8c7`. Đây là phép cộng trần cấu hình, không phải số connection runtime.

- Mỗi API process có pool request (mặc định 20, nhận 2–60), checkpointer PostgreSQL tối đa 10, ChangeBroker giữ một kết nối LISTEN, và giám sát pool có thể mở pool cảnh báo tối đa 1.
- Compose mặc định chạy API, `su-kien`, `day-tep`; hai worker có pool tối đa 10. Auth và PostgREST mỗi bên được giới hạn 10. Không có số replica khai báo; Dockerfile gọi một tiến trình uvicorn mặc định.
- Production ở API=60: trần đã biết 112. API mặc định 20: 72. 100 là con số budget trong comment, không được production Compose pin; actual max_connections/runtime chưa đọc.
- Staging DB pin 60. API mặc định 10: tổng đã biết 52; override API=20: 62. `day-tep` và Realtime tắt trong compose staging mặc định.
- Chưa cộng Realtime (không có pool cap explicit trong compose production), admin/migration reserve, replica bổ sung, và các optional worker/notification/POS profile. Một số pool chỉ mở theo tải.
- Test hiện tại kiểm tra API pool default/range và DSN/JIT, chưa có phép tính budget theo topology. Canh gác chỉ đo API pool; chưa thấy monitor tổng connections PostgreSQL hoặc preflight triển khai.

## Phát hiện

`INF-020` — MEDIUM / `confirmed_static`. Một topology được chấp nhận có thể vượt ngưỡng DB đã ghi trong cấu hình. Không chứng minh production đang dùng pool 60, không khẳng định đã cạn connection, và chưa đo runtime. Đề xuất tổng hợp budget từ cùng deployment config, tính replica × pool, cộng reserve, pin DB cap, chặn deploy khi vượt, và theo dõi connection toàn server.

## Phạm vi đọc

Đọc trọn 4 module/test mới trong lát này; trace có mục tiêu các điểm lắp pool ở main, worker, Compose, staging, checkpointer và test cấu hình. File `worker.py`, `main.py`, Compose lớn vẫn chưa được đọc hết chỉ vì các vùng này đã được trace. Các pool trực tiếp trong CLI replay/import/conversion được ghi nhận là tác vụ một lần, không cộng vào topology steady-state.
