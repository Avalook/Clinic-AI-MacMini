# Bản giao việc: đọc kỹ một phần mã ClinicAI (chỉ đọc)

ClinicAI là phần mềm quản lý phòng khám Dr4Women (FastAPI + Next.js + Postgres tự dựng). Chủ sản phẩm muốn một báo cáo kiểm toán ĐẦY ĐỦ, rồi đề xuất thiết kế để hệ thống "đóng gọn, bán được cho nhiều phòng khám". Bạn phụ trách đọc KỸ một danh sách tệp và tìm lỗ hổng, sai lệch logic, điểm yếu kiến trúc, rủi ro vận hành.

## Quy tắc cứng
- CHỈ ĐỌC. Không sửa bất kỳ tệp nào của repo. Không chạy ứng dụng, API, test, database, provider, VPS, production. Không mở secrets (.env*), không đọc dữ liệu bệnh nhân.
- Chỉ lấy nội dung code từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong repo `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`. KHÔNG đọc working tree của bạn hay của repo khác làm bằng chứng.
- Cách đọc một tệp (zsh): `W=/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini; S=956ba4f236b1c92f1280d2097018c199e90ce8c7; rtk proxy git -C "$W" show "${S}:ĐƯỜNG/DẪN" | cat -n`
  - BẮT BUỘC viết `${S}` có ngoặc nhọn (zsh hiểu nhầm `$S:src`). BẮT BUỘC dùng `rtk proxy git` (hook RTK nén/hỏng output của `git show`).
  - Đường dẫn có ngoặc đơn hoặc `[ ]` phải để trong dấu nháy kép.
  - Tool cắt output quá lớn: đọc từng đoạn ≤ ~25.000 ký tự (dùng `sed -n 'a,bp'` sau `cat -n`). Nếu thấy "Output too large" hoặc "[full output...]", đọc lại đoạn nhỏ hơn. Không kết luận từ phần bị cắt.
- Danh sách tệp của bạn nằm ở tệp .tsv (mỗi dòng: đường dẫn, số byte, git blob sha1). ĐỌC HẾT TỪNG TỆP, từng dòng. Tệp quá nhỏ/hiển nhiên (hằng số, style) vẫn đọc nhưng ghi ngắn. Nếu không đọc được hết một tệp, ghi đúng sự thật trong coverage (full_read=false và lý do). Không bịa đã đọc.
- Đã có 212 phát hiện (xem `known-findings.txt`: id, mức, tiêu đề). Không lặp lại. Nếu bạn thấy thêm bằng chứng cho phát hiện có sẵn, ghi vào `extends` với id đó. Chỉ tạo phát hiện MỚI khi khác bản chất.

## Mục tiêu sản phẩm (thước đo của chủ)
Phòng khám ngày càng ít phụ thuộc: trí nhớ cá nhân, gọi điện hỏi nhau, chat đuổi việc, vài người "gánh team", chữa cháy, kiểm tra thủ công, phản ứng sau khi bệnh nhân phàn nàn. Hệ thống phải giúp: thực tế dễ thấy (Reality), thời gian "chưa biết" ngắn (Unknown), ownership rõ, phát hiện vấn đề sớm, con người bị gián đoạn ít hơn nhưng đúng lúc, bệnh nhân ít chờ trong bất định, nhân viên làm việc bền vững, quyết định dựa bằng chứng, lỗi lặp lại thành cải tiến hệ thống. AI hỗ trợ người, không thay người. Mỗi phát hiện nên gắn 1–3 mục tiêu này vào `alignment`.

## Tìm gì (ưu tiên)
1. Quyền theo đối tượng/tenant/cơ sở: endpoint/RPC/view/BFF chỉ kiểm quyền chung mà không kiểm bệnh nhân/cơ sở/phân công; tin tenant hay actor do người gọi gửi lên; PII lộ ra danh sách/log/nhật ký.
2. Tiền, hoàn tiền, đối soát, tồn kho, lô: tính sai, làm tròn, cắt dòng, hai sổ không khớp.
3. Chuyển trạng thái, đồng thời, idempotency: retry/mất phản hồi tạo bản ghi trùng, hai người ghi đè nhau, thứ tự khoá, TOCTOU.
4. Sự thật hiển thị: danh sách bị cắt (LIMIT, cap) mà UI nói "hết"; lỗi tải bị hiển thị thành 0/rỗng; báo thành công khi chưa; dữ liệu cũ không đánh dấu.
5. Ownership/việc rơi: việc không có người nhận, không có hạn, không có nhắc, chỉ sinh khi ai đó mở màn.
6. Outbox/worker/timer/dead-letter, backup/restore, health giả xanh, cảnh báo im lặng.
7. Tính đóng gói/bán được: dữ liệu hay tên riêng Dr4Women ghi cứng trong lõi, cấu hình không theo tenant, thiếu quy trình tạo phòng khám mới, giả định một cơ sở, ghi cứng múi giờ/ngôn ngữ/danh mục.
8. Đường lâm sàng nguy hiểm cho bệnh nhân: kết quả, đơn thuốc, kê/giao thuốc, tái khám, đối tác.
9. Với tệp test: bất biến quan trọng nào KHÔNG có test; test nào kiểm sai thứ; test nào khẳng định hành vi sai.
10. Điểm tốt cũng quan trọng: mẫu thiết kế đáng giữ và nhân rộng.

## Cách ghi nhận
- Chỉ ghi phát hiện khi bạn đã đọc đường đi liên quan (gọi từ đâu, kiểm ở đâu). Có thể tra thêm tệp ngoài danh sách bằng `git show` để chứng minh (ghi rõ trong evidence), nhưng ưu tiên đọc hết danh sách của bạn.
- Dùng ngôn ngữ điều kiện: "có thể xảy ra nếu…". Không khẳng định đã xảy ra ở production. Không suy diễn quá bằng chứng. Nếu chưa chắc, đưa vào `held` kèm lý do thay vì `findings`.
- Mỗi phát hiện: trigger cụ thể, tác động, evidence chính xác (đường dẫn + dòng đầu/cuối + ý), mức tin cậy, giới hạn, recommendation, acceptance test khả thi.
- Viết tiếng Việt, rõ ràng.

## Đầu ra
Ghi MỘT tệp JSON UTF-8 vào đường dẫn đầu ra được giao (thư mục scratchpad, không phải repo), đúng schema:
```json
{
  "chunk": "S01",
  "findings": [{
    "tmp_id": "S01-1", "title": "...", "severity": "HIGH|MEDIUM|LOW",
    "category": "snake_case_ngan", "evidence_level": "confirmed_static|design_gap",
    "summary": "...", "trigger": "...", "impact": "...",
    "evidence": [{"path": "...", "line": 10, "end_line": 25, "detail": "..."}],
    "limitations": "...", "recommendation": "...", "acceptance": "...",
    "alignment": ["Reality rõ", "Ownership rõ"], "extends": [], "related_ids": []
  }],
  "extensions": [{"id": "SEC-011", "detail": "bằng chứng thêm, kèm path:line"}],
  "held": [{"title": "...", "reason": "..."}],
  "good_patterns": [{"title": "...", "detail": "...", "evidence": "path:line"}],
  "coverage": [{"path": "...", "lines": 123, "full_read": true, "note": "ngắn"}]
}
```
`coverage` phải có MỘT dòng cho MỖI tệp trong danh sách của bạn. Kiểm JSON hợp lệ (`python3 -I -c "import json;json.load(open(path))"`) trước khi kết thúc.

## Trả lời cuối (ngắn, ≤150 từ)
Số tệp đã đọc đầy đủ / tổng, số phát hiện mới theo mức, 2–3 phát hiện quan trọng nhất, đường dẫn tệp đầu ra, và những gì bạn KHÔNG làm được.
