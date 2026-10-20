# Round 9 — ranh giới AI, tools, graphs, orchestrator và event bus

Nguồn cố định: snapshot `main` SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` tại `/tmp/clinicai-audit-main-956ba4f2`. Lát này đọc trọn 61 file trong `tools/`, `graphs/`, `orchestrator/`, `llm/`, `event_bus/`; đối chiếu các điểm khởi tạo app, router lab/ops, service chi phí và test liên quan. Đây là static audit. Không gọi LLM thật, không chạy app, không dùng DB/production/PHI, và không sửa application code hay migration.

## AI-004 — ứng dụng bỏ qua đồng hồ chi phí và trần LLM

**Mức:** MEDIUM · **Độ chắc:** xác nhận tĩnh ở cách khởi tạo client và đường gọi; chưa chứng minh hóa đơn hay chi phí thực tế trên production.

Khi `ANTHROPIC_API_KEY` có mặt, FastAPI tạo client dùng chung bằng `AnthropicClient()` mà không truyền pool DB (`src/clinicai/main.py:154–163`), rồi inject chính client đó vào orchestrator (`main.py:174–181`). Constructor mặc định `pool=None`. Trong `chat()`, client chỉ đọc trần chi phí và ghi lần gọi khi `self._pool` khác `None` (`src/clinicai/llm/anthropic_client.py:117–155`). Router lab lấy singleton từ `app.state` và dùng nó để chạy triage (`src/clinicai/api/v1/routers/lab.py:214–219, 240–258`). Vì thế các lần gọi qua singleton này không xuất hiện trong `llm_lan_goi`; trần `LLM_TRAN_NGAY_USD` không được áp dụng cho chúng, nên màn `/ops/llm/chi-phi` có thể thiếu chi phí tương ứng.

Ngay cả khi một caller khác tự truyền pool, control hiện tại cũng chưa phải hard cap đồng thời: `chan_neu_vuot_tran()` đọc tổng chi phí bằng truy vấn riêng trước khi gọi provider, còn dòng usage chỉ được chèn sau lời gọi. Hai request song song có thể cùng thấy phần dư và cùng đi tiếp. `ghi_lan_goi()` còn nuốt lỗi ghi ledger sau khi log lỗi, vì không thể thu hồi chi phí provider đã phát sinh. Những chi tiết này làm giảm độ tin cậy của chính sách ngân sách và số liệu vận hành; không có bằng chứng trong lượt này rằng hệ thống đã vượt ngân sách hay ghi hóa đơn sai.

Test DB hiện có khởi tạo client với `pool=pool` và kiểm tra chặn ở ngưỡng theo chuỗi tuần tự (`src/tests/services/test_llm_chi_phi_db.py:45–53, 91–111`). Nó không kiểm wiring trong FastAPI lifespan, cũng không kiểm nhiều request cùng reserve một ngân sách. Đây là khoảng trống kiểm chứng, không phải bằng chứng test đang hỏng.

**Cải tiến đề xuất:** truyền metering service đã khởi tạo cùng app pool vào mọi client của app; thay check-then-call bằng reservation nguyên tử theo ngày, có giới hạn ngân sách và xử lý rõ khoản đang giữ; finalize reservation bằng usage/provider request ID sau khi trả lời; khi ledger lỗi thì phát cảnh báo bền và đánh dấu số liệu không đầy đủ. Dashboard cần cho thấy `đã xác nhận`, `đang reserve`, `chưa ghi được` và thời điểm cập nhật. Nếu reservation không sẵn sàng, sản phẩm phải fail-closed với chức năng LLM hoặc áp fallback rule-based đã định nghĩa, không được âm thầm bỏ trần.

**Nghiệm thu:** test startup app chứng minh client dùng chung có meter; test concurrency với ngân sách tổng hợp chứng minh các request không thể cùng chi vượt reservation; thử lỗi trước/sau provider và lỗi finalize để bảo đảm lần gọi luôn truy vết hoặc hiển thị thành “chưa đối soát”; dashboard phản ánh cùng tập receipt; khi meter lỗi, người dùng nhận trạng thái AI unavailable/fallback rõ ràng.

### Phạm vi đã đọc

- Đọc trọn 61 file nguồn của tools, graph, orchestration, LLM và event bus. Coverage theo file/hash nằm trong `round9_ai_runtime.coverage.json`; “đọc trọn” chỉ áp dụng các file được liệt kê, không suy rộng ra caller bên ngoài.
- Trace các điểm khởi tạo và sử dụng app singleton qua orchestrator, lab triage và trang ops; xem migration tạo ledger chi phí cùng test unit/DB liên quan.
- Không chạy test cần Postgres, không gọi API provider, không truy cập production, không kết luận sự cố đã xảy ra.
- Các quan sát khác trong luồng lab/task/schedule chưa thành finding nếu chưa đủ chứng minh tác động end-to-end; AI-002 và AI-003 hiện có bao phủ một số hành vi ack/scheduling liên quan, tránh tạo ID trùng.
