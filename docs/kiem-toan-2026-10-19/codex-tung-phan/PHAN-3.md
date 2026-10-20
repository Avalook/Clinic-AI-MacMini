# Đề bài cho Codex: xác minh độc lập phần 3/4 (10 mục mức cao)

Bạn là người soát lỗi độc lập, KHÔNG phải người viết báo cáo. Nhiệm vụ: với từng mục dưới đây, tự đọc code và cho biết khẳng định có đúng không. Mục tiêu là bắt báo động giả và bắt chỗ báo cáo thổi phồng, không phải xác nhận cho đẹp. Một kết luận "bác bỏ" có bằng chứng giá trị hơn mười kết luận "đúng" hời hợt.

## Quy tắc
- CHỈ ĐỌC. Không sửa code, không chạy ứng dụng, API, test, database, VPS, production. Không mở `.env*`, không đọc dữ liệu bệnh nhân. Không đưa khoá hay bí mật vào đâu cả.
- Chỉ lấy bằng chứng từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`, ví dụ: `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:ĐƯỜNG/DẪN`. Không dùng working tree.
- Đừng đọc kết luận của báo cáo trước khi tự đọc code. Đọc dẫn chứng ban đầu như gợi ý chỗ bắt đầu, rồi tự lần ngược: ai gọi, kiểm quyền ở đâu, trigger hay ràng buộc nào ở cơ sở dữ liệu (`supabase/migrations`), UI có chặn bù không.
- Không chắc thì ghi `KHONG_XAC_DINH` và nói thiếu gì. Không đoán.
- Tiếng Việt, ngắn gọn.

## Kết quả cần nộp
Ghi một tệp `docs/kiem-toan-2026-10-19/dot-2-doc-toan-bo/KET-QUA-CODEX-3.json` (mảng, mỗi mục một đối tượng):
```json
{"id": "SEC-020", "ket_luan": "DUNG | DUNG_MOT_PHAN | BAC_BO | KHONG_XAC_DINH",
  "muc_do_dung": "CAO | VUA | THAP | KHONG_AP_DUNG",
  "ly_do": "2–5 câu: đường đi bạn đã lần, chốt nào bạn đã kiểm",
  "bang_chung": [{"path": "...", "line": 1, "end_line": 5, "y": "..."}],
  "chot_chan_da_tim_thay": "trigger/ràng buộc/kiểm tra khác làm lỗi không xảy ra, hoặc rỗng",
  "ghi_chu_sua": "1–2 câu nếu đúng: sửa ở đâu là gọn nhất"}
```
Sau đó tóm tắt: số mục DUNG / DUNG_MOT_PHAN / BAC_BO / KHONG_XAC_DINH và 3 mục bạn thấy báo cáo yếu nhất.

## Bối cảnh ngắn
ClinicAI là phần mềm quản lý phòng khám (FastAPI + Next.js + Postgres tự dựng, nhiều lớp quyền theo "lego"). Một số quyết định là CÓ CHỦ Ý của chủ sản phẩm, ví dụ mở rộng quyền nội bộ và luật chọn cơ sở làm việc; nếu một mục chỉ trái với quyết định đó, ghi `DUNG_MOT_PHAN` và nói rõ đó là chủ ý. Hệ thống đang đón bệnh nhân thật nên "mức cao" chỉ đúng khi hậu quả với bệnh nhân, tiền hoặc dữ liệu là đáng kể.

## Danh sách phần 3/4: INF-001, INF-002, INF-003, INF-006, INF-007, AI-001, CLIN-005, CLIN-006, CLIN-007, SEC-010

### INF-001 (cũ) — Kiểm tra backup báo đạt dù thiếu auth và tệp kết quả chờ đẩy
- **Khẳng định cần kiểm:** verify-backup.sh không kiểm một số companion auth/media dù backup ghi manifest. Ngoài tep_ket_qua pending, query backup bỏ qua anh_chuyen_khoan dù worker đẩy bảng này và ảnh có thể còn duy nhất trên VPS; archive DB thiếu ảnh chứng từ chuyển khoản chưa lên CFS.
- **Điều kiện xảy ra:** Bản sao public còn nguyên, companion auth hoặc tệp kết quả chưa đẩy bị mất/hỏng; hoặc backup đã bỏ sót tệp vì trần dung lượng.
- **Dẫn chứng ban đầu:** `scripts/verify-backup.sh:83-136`; `scripts/backup-db.sh:493-516`; `scripts/backup-db.sh:424-424`; `scripts/backup-db.sh:438-490`; `src/clinicai/services/day_tep.py:111-116`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-002 (cũ) — Cảnh báo Telegram thất bại lần đầu không được gửi lại khi sự cố còn mở
- **Khẳng định cần kiểm:** _mo chỉ trả True lúc cảnh báo mới; ap_dung chỉ gửi cho thay đổi trạng thái. gui_telegram_ops=False không tạo pending delivery/retry.
- **Điều kiện xảy ra:** Mất mạng, timeout/429 hoặc Telegram tạm lỗi đúng lúc phát hiện sự cố.
- **Dẫn chứng ban đầu:** `src/clinicai/services/canh_gac.py:183-197`; `src/clinicai/services/canh_gac.py:207-248`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-003 (cũ) — Guard chống chạy phép thử trên production dùng sai tên môi trường
- **Khẳng định cần kiểm:** Hai script tạo tài khoản/đo giữ chỗ chỉ chặn APP_ENV=prod; template prod hiện hành dùng APP_ENV=production.
- **Điều kiện xảy ra:** Người vận hành nạp cấu hình prod rồi chạy scripts/tests/do-giu-cho.py hoặc do-tam-cskh.py.
- **Dẫn chứng ban đầu:** `scripts/tests/do-giu-cho.py:143-153`; `scripts/tests/do-tam-cskh.py:109-117`; `scripts/tests/do-tam-cskh.py:242-249`; `.env.prod.example:13-16`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-006 (cũ) — Khôi phục đầy đủ DB + đăng nhập + file chưa được chứng minh bởi các script hiện hành
- **Khẳng định cần kiểm:** restore-db.sh khôi phục public nhưng không tự kiểm/khôi phục companion auth và pending-media. restore-drill chỉ seed UUID auth, không thử login. Backup bỏ CFS tar khi marker có mặt và ghi media_artifact=none; repo chưa chứng minh snapshot độc lập của kho gốc. Restore-db hiện dừng ở public schema; không dựng migration ledger tương ứng, trong khi migration runner xem ledger rỗng là mọi migration đang pending. Vì dump dùng --no-acl, đường restore cũng cần bước ACL reconcile rõ ràng trước khi coi stack sẵn sàng Backup manifest and restore-drill comments still name Supabase Cloud PITR/auth backup even though the documented deployment is self-hosted; the cloud dependency contract is stale/ambiguou
- **Điều kiện xảy ra:** Mất VPS hoặc mất/sai dữ liệu CFS; cần dựng phòng khám mới từ backup và chứng minh tài khoản vào được, tệp bệnh án mở được.; sau đó chạy apply-pending-migrations.sh hoặc cấp người dùng trước khi reconcile ledger/ACL.
- **Dẫn chứng ban đầu:** `scripts/restore-db.sh:207-267`; `scripts/restore-drill.sh:121-168`; `scripts/backup-db.sh:352-390`; `scripts/backup-db.sh:503-516`; `scripts/restore-db.sh:128-140`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-007 (cũ) — Nghiệp vụ đã commit nhưng mất receipt có thể bị thực hiện lại sau lease
- **Khẳng định cần kiểm:** IdempotencyGuard giữ PROCESSING bằng pool riêng; cả route CSKH và POST /payments/hoan-tien commit nghiệp vụ rồi mới save receipt. Lease hết cho phép chạy lại mà không đối soát domain đã ghi. Nhánh hoàn tiền áp dụng cả khoản prepay liệu trình; mất receipt sau commit có thể khiến retry hoàn lặp phần tương ứng. Round 37 adds POST /pharmacy/khach-tra: stock return/refund/event commit in the service transaction, then router persists the idempotency receipt. If receipt persistence is lost after commit, lease reclaim can retry; not fault-injected.
- **Điều kiện xảy ra:** Một thao tác commit thành công nhưng lưu receipt lỗi/process chết; sau PROCESSING_TTL 5 phút gửi lại cùng key và payload. Đã tái hiện cả ghi tương tác CSKH và hoàn tiền từng phần. Same commit-to-receipt gap applies if a pharmacy return commits but receipt save fails or process stops.
- **Dẫn chứng ban đầu:** `src/clinicai/api/idempotency.py:108-136`; `src/clinicai/api/idempotency.py:182-210`; `src/clinicai/api/v1/routers/cskh.py:519-547`; `src/clinicai/api/v1/routers/payment.py:392-405`; `src/clinicai/services/hoan_tien_service.py:119-131`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### AI-001 (cũ) — Agent đóng nhận định còn đúng khi truy vấn bị giới hạn số dòng
- **Khẳng định cần kiểm:** SQL dùng LIMIT 200; đối soát coi tập trả về là đầy đủ và đóng HET mọi khóa vắng mặt. Có log bang_bi_cat nhưng cờ cắt không chặn đóng.
- **Điều kiện xảy ra:** Trên 200 việc quá hạn và đối tượng ngoài tập trả về đã có nhận định mở.
- **Dẫn chứng ban đầu:** `src/clinicai/services/agent_giam_sat.py:262-275`; `src/clinicai/services/agent_giam_sat.py:335-360`; `src/clinicai/services/agent_giam_sat.py:445-454`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-005 (cũ) — Đổi lịch đồng thời check-in có thể kéo lịch đã đến về CONFIRMED
- **Khẳng định cần kiểm:** KEEP_STATUS lấy status từ SELECT không khóa; _update chấp nhận cả _ALIVE thay vì status/revision đã đọc. Patch luôn ghi status cũ.
- **Điều kiện xảy ra:** A đổi lịch đọc CONFIRMED; B check-in commit CHECKED_IN và mở visit; A tiếp tục UPDATE với status=CONFIRMED.
- **Dẫn chứng ban đầu:** `src/clinicai/services/booking_service.py:955-1002`; `src/clinicai/services/booking_service.py:1048-1052`; `src/clinicai/services/booking_service.py:1764-1765`; `src/clinicai/services/booking_service.py:2113-2124`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-006 (cũ) — Ẩn thông báo đính chính cũ có thể che cả lần đính chính mới
- **Khẳng định cần kiểm:** Nguồn chuông result.corrected chỉ ghép event_type:aggregate_id, bỏ ban_thu; chuông cũ còn mở thì DO NOTHING. Ẩn cá nhân theo id chuông tiếp tục che lần sửa mới.
- **Điều kiện xảy ra:** Kết quả đã đính chính lần 2, bác sĩ dùng Ẩn tất cả; cùng phiếu được đính chính lần 3 trong khi chuông cũ chưa Đã xử lý.
- **Dẫn chứng ban đầu:** `src/clinicai/services/form_engine_service.py:895-929`; `src/clinicai/events/consumers/chuong.py:189-195`; `src/clinicai/events/consumers/chuong.py:331-354`; `src/clinicai/services/thong_bao_service.py:346-355`; `src/clinicai/services/thong_bao_service.py:410-428`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-007 (cũ) — Giao thuốc không qua phân lô chấp nhận lô của thuốc khác dòng đơn
- **Khẳng định cần kiểm:** Trong đường giao thẳng (lần thu legacy hoặc không có allocation), backend kiểm clinic/cơ sở/đơn vị/hạn/tồn nhưng thiếu đối chiếu thuốc của lô với drug_catalog_id đã xác định ở dòng đơn.
- **Điều kiện xảy ra:** Thuốc A đã xác định và đã thu tiền, không có allocation; người có quyền pharmacy.dispense gửi ID lô thuốc B cùng cơ sở và đơn vị. Công tắc yêu cầu kho/phân lô lúc thu được tắt trong probe; đây cũng là giá trị mặc định source, chưa đọc cấu hình prod.
- **Dẫn chứng ban đầu:** `src/clinicai/services/pharmacy_service.py:726-770`; `src/clinicai/services/pharmacy_service.py:1248-1294`; `src/clinicai/api/v1/routers/pharmacy.py:1032-1056`; `supabase/migrations/20260920000002_tien_thuoc_cp6_dinh_chinh_don.sql:580-590`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-010 (cũ) — API hồ sơ chia sẻ cho phép nhân viên thiếu quyền y khoa đọc form bằng cách tự đặt cùng mã bệnh nhân
- **Khẳng định cần kiểm:** GET /patients/{patient_id}/shared-form nhận viewing_patient_id do caller truyền. may_surface() cho phép vô điều kiện khi hai ID bằng nhau; service sau đó truy vấn form_data của bệnh nhân đó trong clinic. Route chỉ dùng get_current_identity, vốn chặn DISPLAY/PARTNER nhưng không yêu cầu capability y khoa; các route clinical-form chuẩn dùng cua_y_khoa.
- **Điều kiện xảy ra:** Nhân viên thường có membership hợp lệ nhưng không có quyền đọc hồ sơ y khoa gọi endpoint với patient_id bằng viewing_patient_id của bệnh nhân cùng clinic.
- **Dẫn chứng ban đầu:** `src/clinicai/api/v1/routers/consent.py:50-71`; `src/clinicai/services/consent_service.py:69-97`; `src/clinicai/services/consent_service.py:194-245`; `src/clinicai/api/identity.py:638-659`; `src/clinicai/api/v1/routers/clinical_forms.py:23-50`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

## Bản prod
Đã đối chiếu 20/10/2026: VPS prod đang ở commit 956ba4f2, chính là bản bạn đọc. Chỉ kết luận về prod.

Nếu hết hạn mức giữa chừng: ghi ngay kết quả các mục đã xong vào tệp KET-QUA-CODEX-3.json rồi dừng, mục chưa làm để trống.
