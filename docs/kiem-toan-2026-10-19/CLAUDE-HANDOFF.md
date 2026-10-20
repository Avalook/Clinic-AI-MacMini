# Bàn giao kiểm toán ClinicAI cho Claude

## Prompt để tiếp tục

Tiếp tục cuộc kiểm toán mã nguồn ClinicAI/Dr4Women theo checkpoint này. Mục tiêu là tìm lỗ hổng, sai lệch logic, điểm yếu kiến trúc và rủi ro vận hành; sau đó đề xuất thiết kế/lộ trình để sản phẩm đóng gọn, đáng tin cậy và có thể bán cho nhiều phòng khám. Đích sản phẩm là giúp phòng khám nhìn thấy thực tế, rút ngắn thời gian chưa biết, rõ ownership, phát hiện lỗi sớm, giảm gián đoạn sai lúc, giảm thời gian bệnh nhân chờ trong bất định, quyết định dựa trên bằng chứng và biến lỗi lặp lại thành cải tiến hệ thống. AI hỗ trợ con người; không thay con người vận hành hay chăm sóc bệnh nhân.

Trước tiên đọc toàn bộ tệp này, TIEP-TUC.md, STATE.json, BAT-DAU-TU-DAY.md, NHAT-KY.md, MAIN-PHAM-VI.json và PHAT-HIEN.json. Tiếp tục từ trạng thái lưu trên đĩa, không làm lại các vòng đã có bằng chứng. Sau mỗi phần, ghi nguồn, dòng, hash, kiểm tra/phạm vi đọc và giới hạn. Chỉ kết luận “đã kiểm” khi thật sự đã đọc và đối chiếu đường đi liên quan; không dùng bộ đếm file như phần trăm hiểu hành vi.

## Checkpoint đã lưu

- Báo cáo hiện tại: v0.76, vòng 53.
- 212 phát hiện đã được nhập; OPS-014 (vòng 53) là phát hiện mới nhất: luật thứ tự bắt buộc cũ không thể chặn qua API điều phối. CLIN-060 (vòng 52) về phí khám mặc định sau khi đổi loại khám.
- Báo cáo cho người không làm kỹ thuật: BAO-CAO-DE-HIEU.html (tự chứa, đọc được trên điện thoại). Báo cáo kỹ thuật đầy đủ vẫn là BAO-CAO.html.
- Toàn bộ kiểm toán mã nguồn CHƯA hoàn tất. STATE.json giữ full_source_audit_complete=false.
- Báo cáo đọc độc lập là BAO-CAO.html. Ở checkpoint này validator hồ sơ đạt 6/6; browser QA cho riêng HTML báo cáo đạt desktop 1280px/mobile 375px, 211 thẻ, không có page error hay external request. Đây không phải kiểm thử ClinicAI và không phải chứng nhận accessibility.
- Gói tiếp quản hiện có tiep-quan-clinicai-2026-10-19.zip và MANIFEST-GOI.json. Gói chỉ gồm hồ sơ kiểm toán; nó không chứa repository, Git history, secrets, patient data hay production payload. Kiểm SHA/CRC/members được ghi trong STATE.json và manifest.
- Artifact kiểm toán chỉ được sửa trong docs/kiem-toan-2026-10-19/.

## Nguồn mã phải đối chiếu

- SHA nguồn được ghim: 956ba4f236b1c92f1280d2097018c199e90ce8c7.
- Worktree nguồn: /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini.
- Chỉ lấy bằng chứng mã nguồn từ Git blob bất biến, ví dụ `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:src/...`.
- Không dùng working tree chính làm bằng chứng: nó có thể chứa WIP khác SHA.
- Nếu Claude không truy cập được worktree trên, dừng kết luận mã nguồn và yêu cầu người dùng mở/cấp đúng repository cùng Git history. ZIP này một mình không đủ để tiếp tục đọc code.

## Ranh giới đã thống nhất cho phiên audit

Đây là đánh giá tĩnh, chỉ đọc. Đọc test được nhưng ghi rõ read-not-run. Không chạy ứng dụng ClinicAI, API, test suite, database, provider, VPS hay production; không mở secrets hoặc dữ liệu bệnh nhân. Không sửa mã ứng dụng. Có thể chạy validator/browser QA dành riêng cho trang HTML của hồ sơ. Không biến suy luận tĩnh thành khẳng định đã xảy ra ở production.

## Đầu mối visit_gate_rule — ĐÃ ĐÓNG ở vòng 53 (OPS-014)

Kết luận (static, exact-main): (1) luồng cũ — XÁC NHẬN: luật seed bắt buộc only_when_other_staff=TRUE, blocks() cho qua khi target_staff_id là None, và hai endpoint ghi (/dispatch/move, /dispatch/transfer-room) không có trường người đích nên luật không bao giờ chặn; comment hứa "chốt sẽ xét lại" nhưng không có lần xét lại. (2) luồng mới — migration 20260808000003 ghi rõ là chủ ý chuyển luật sang lúc đặt lịch (luat_bac_si_bat_buoc); KHÔNG kết luận luồng mới bỏ qua mọi luật. Chưa biết bảng visit_gate_rule ở production có dòng bật hay không. Chi tiết: blocks/round53.md, blocks/round53.coverage.json, PHAT-HIEN.json.

Câu hỏi còn mở cho chủ sản phẩm: luật thứ tự bắt buộc còn phải canh sau khi khách đến không, hay đã chuyển hẳn sang luật lúc đặt lịch?

## Việc tiếp theo

1. Xác nhận checkpoint/manifest và SHA nguồn trước khi đọc.
2. (Đã xong ở vòng 53.) Chọn tiếp đầu mối mới theo STATE.json.next_action.
3. Tiếp tục những service, router, UI/BFF, SQL migration, event consumer, test, config và vận hành còn ở trạng thái scanned/traced/inventoried trong MAIN-PHAM-VI.json. Ưu tiên authorization theo đối tượng/tenant/cơ sở, tiền–hoàn tiền–đối soát, state transition/concurrency/idempotency, outbox/worker recovery, backup/restore và đường patient-critical.
4. Mỗi phát hiện phải có trigger, tác động, evidence chính xác, mức tin cậy, kiểm tra đã/chưa chạy, giới hạn, recommendation và acceptance test khả thi.
5. Giữ full_source_audit_complete=false cho tới khi scope và gap kiểm chứng thật sự đóng. Cập nhật BAO-CAO.html, kiểm validator/browser của HTML, sau đó dựng và xác minh lại ZIP cùng manifest.

## Prompt ngắn để dán vào Claude

“Đọc docs/kiem-toan-2026-10-19/CLAUDE-HANDOFF.md và các checkpoint được liệt kê trong đó. Tiếp tục cuộc kiểm toán từ đúng trạng thái đã lưu, dùng đúng SHA nguồn bất biến, không làm lại vòng cũ, không sửa code ứng dụng, ghi rõ mọi giới hạn và chưa kết luận audit toàn bộ xong. Đầu mối visit_gate_rule đã đóng (OPS-014); tiếp tục các phần chưa đọc trong MAIN-PHAM-VI.json. Khi có cập nhật, giữ HTML và ZIP bàn giao đồng bộ, có thể khôi phục sau khi đổi tài khoản.”
