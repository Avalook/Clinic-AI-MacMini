# Đề bài cho Codex: xác minh độc lập 40 mục mức cao

Bạn là người soát lỗi độc lập, KHÔNG phải người viết báo cáo. Nhiệm vụ: với từng mục dưới đây, tự đọc code và cho biết khẳng định có đúng không. Mục tiêu là bắt báo động giả và bắt chỗ báo cáo thổi phồng, không phải xác nhận cho đẹp. Một kết luận "bác bỏ" có bằng chứng giá trị hơn mười kết luận "đúng" hời hợt.

## Quy tắc
- CHỈ ĐỌC. Không sửa code, không chạy ứng dụng, API, test, database, VPS, production. Không mở `.env*`, không đọc dữ liệu bệnh nhân. Không đưa khoá hay bí mật vào đâu cả.
- Chỉ lấy bằng chứng từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`, ví dụ: `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:ĐƯỜNG/DẪN`. Không dùng working tree.
- Đừng đọc kết luận của báo cáo trước khi tự đọc code. Đọc dẫn chứng ban đầu như gợi ý chỗ bắt đầu, rồi tự lần ngược: ai gọi, kiểm quyền ở đâu, trigger hay ràng buộc nào ở cơ sở dữ liệu (`supabase/migrations`), UI có chặn bù không.
- Không chắc thì ghi `KHONG_XAC_DINH` và nói thiếu gì. Không đoán.
- Tiếng Việt, ngắn gọn.

## Kết quả cần nộp
Ghi một tệp `docs/kiem-toan-2026-10-19/dot-2-doc-toan-bo/KET-QUA-CODEX.json` (mảng, mỗi mục một đối tượng):
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

## Danh sách (40 mục)

### CLIN-001 (cũ) — Hành trình suy rằng đã đọc kết quả khi dịch vụ ngoài vẫn chờ kết quả
- **Khẳng định cần kiểm:** Điều kiện doc_trong_phien chỉ kiểm dịch vụ đã bắt đầu trước lúc khám chính hoàn tất, không kiểm đã có kết quả hoặc bằng chứng bác sĩ đọc.
- **Điều kiện xảy ra:** Lấy mẫu gửi đối tác xong, chưa có kết quả; phiên PRIMARY hoàn tất sau lúc lấy mẫu.
- **Dẫn chứng ban đầu:** `src/clinicai/services/hanh_trinh_khach_service.py:736-764`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-003 (cũ) — Lưu ngày tái khám có thể mất việc gọi mà màn vẫn báo lưu thành công
- **Khẳng định cần kiểm:** Đồng bộ nhắc tái khám rollback riêng khi lỗi, phiếu vẫn commit; frontend không dùng hen_tai_kham.LOİ. Cùng ngày lưu lại không đủ điều kiện thử đồng bộ vì chỉ chạy khi ngày đổi.
- **Điều kiện xảy ra:** htk.dong_bo lỗi đúng lúc bác sĩ thay ngày hẹn; lần lưu khác giữ nguyên ngày.
- **Dẫn chứng ban đầu:** `src/clinicai/services/phieu_kham_service.py:510-541`; `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:284-316`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### DB-001 (cũ) — RPC SECURITY DEFINER cho phép gọi vượt FastAPI và tin tenant/actor do người gọi truyền
- **Khẳng định cần kiểm:** Các hàm gắn/gỡ buổi liệu trình chạy quyền owner, nhận clinic/actor làm tham số nhưng không đối chiếu danh tính. Không REVOKE EXECUTE FROM PUBLIC; đường /rest/v1 public chuyển thẳng PostgREST.
- **Điều kiện xảy ra:** Người gọi qua PostgREST biết UUID clinic/order/liệu trình và gọi RPC gắn/gỡ buổi trực tiếp.
- **Dẫn chứng ban đầu:** `supabase/migrations/20261008100000_lieu_trinh.sql:283-340`; `docker/supabase/init/01-vai-va-extension.sql:161-166`; `caddy/Caddyfile:151-154`; `docker/supabase/Caddyfile:29-31`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### DB-002 (cũ) — Các đường phục hồi không tái lập ACL thiết kế: nhánh cấp quá rộng, nhánh khác bỏ quyền
- **Khẳng định cần kiểm:** Hai script staging cấp blanket ALL/EXECUTE, ghi đè một số ACL thu hẹp. Một đường restore-db tổng quát khác nạp dump public --no-acl nhưng không reconcile migration ledger/ACL; vì vậy hai kiểu phục hồi có thể tạo ACL khác thiết kế theo hai hướng. Mô phỏng blanket grant trên main đã tái hiện; đường restore tổng quát là static gap, chưa chạy.
- **Điều kiện xảy ra:** Chạy staging restore scripts có blanket grant; hoặc khôi phục dump public-only vào DB mới rồi coi restore-db.sh là hoàn tất và tiếp tục dùng/migrate mà chưa chạy bước ACL reconcile.
- **Dẫn chứng ban đầu:** `scripts/staging-nap-ban-sao.sh:229-232`; `scripts/staging-tu-ban-sao.sh:104-109`; `supabase/migrations/20260915000007_prescription_draft_column_privacy.sql:1-18`; `supabase/migrations/20260805000005_clinic_secret.sql:145-158`; `scripts/restore-db.sh:128-140`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### DB-004 (cũ) — Danh mục riêng của Dr4Women bị trộn vào chuỗi nâng cấp dùng cho mọi phòng khám
- **Khẳng định cần kiểm:** Một migration duyệt mọi clinic đã có drug_catalog, chuẩn hóa về danh mục/giá cụ thể và tắt thuốc ngoài tập chọn. Điều này phù hợp một đợt dữ liệu riêng nhưng không phải cơ chế nâng cấp sản phẩm an toàn cho khách độc lập.
- **Điều kiện xảy ra:** Chạy lại hàm chuan_hoa_danh_muc_thuoc_kiotviet() trong seed/bootstrap hoặc áp đợt data migration này cho DB có nhiều clinic. Runner migration bình thường không tự áp lại migration đã ghi sổ.
- **Dẫn chứng ban đầu:** `supabase/migrations/20260925000014_danh_muc_thuoc_kiotviet.sql:54-57`; `supabase/migrations/20260925000014_danh_muc_thuoc_kiotviet.sql:617-643`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### FIN-002 (cũ) — Nhà thuốc cắt nhiều danh sách mà không báo dữ liệu chưa đầy đủ
- **Khẳng định cần kiểm:** Bảng bán thuốc lấy tối đa 300 dòng trước khi nhóm thành lượt; lịch sử giao giới hạn 200 dòng; màn tư vấn giới hạn 100 dòng; thẻ kho giới hạn 1.000 dòng. Trace bổ sung: danh sách phiếu kho giới hạn 100 phiếu theo loại/location. Các helper chỉ ghi cảnh báo log; API/UI không cho biết tổng số, cursor hoặc rằng kết quả đã bị cắt.
- **Điều kiện xảy ra:** Tập dữ liệu phù hợp vượt 300 ở bảng bán, 200 ở lịch sử giao, 100 ở tư vấn, 1.000 ở thẻ kho hoặc 100 phiếu nhập/kiểm theo location và loại. Chưa có số liệu vận hành chứng minh cơ sở nào vượt các ngưỡng.
- **Dẫn chứng ban đầu:** `src/clinicai/services/ban_thuoc_service.py:194-257`; `src/clinicai/services/ban_thuoc_service.py:539-549`; `src/dashboard/app/(dashboard)/pharmacy/PharmacyBoard.tsx:44-66`; `src/dashboard/app/(dashboard)/pharmacy/PharmacyBoard.tsx:67-211`; `src/clinicai/services/pharmacy_service.py:227-235`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### FIN-003 (cũ) — Thử lại thao tác thêm thuốc ở quầy có thể tạo thêm dòng mới
- **Khẳng định cần kiểm:** Đường thêm thuốc không nhận idempotency key; dòng thiếu id luôn sinh UUID/source_ref ngẫu nhiên, trong khi FE giữ bản nháp khi request lỗi. Round 47 trace thêm BFF `/api/quay-thuoc`: thao tác them không forward Idempotency-Key; backend service tạo UUID mới cho dòng thiếu id trên mỗi lần gọi. Đây là đường giao diện khác cùng lỗi command idempotency, không phải finding mới.
- **Điều kiện xảy ra:** DB đã commit lần thêm nhưng response mất mạng; nhân viên bấm lưu lại cùng dữ liệu.
- **Dẫn chứng ban đầu:** `src/clinicai/api/v1/routers/quay_thuoc.py:90-116`; `src/clinicai/services/quay_thuoc_service.py:384-545`; `src/dashboard/app/(dashboard)/thu-ngan/ChinhDonQuay.tsx:167-186`; `src/dashboard/app/api/quay-thuoc/route.ts:34-55`; `src/clinicai/services/quay_thuoc_service.py:529-555`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

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

### SEC-011 (cũ) — API đọc lâm sàng chưa áp dụng đầy đủ capability và phạm vi phân công
- **Khẳng định cần kiểm:** Preset TKYK có capability y khoa nên qua cua_y_khoa, nhưng một số API đọc chỉ scope theo clinic hoặc tin patient_id/visit_id/appointment_id do caller cung cấp. GET clinical-forms, clinical-forms/history và clinical-records/in-theo-lich không kiểm bệnh nhân thuộc bác sĩ được phân. clinical-records/doc có kiểm patient_id nhưng nhánh appointment_id tìm visit chỉ theo clinic+appointment rồi ghép SOAP/sinh hiệu/đơn theo visit đó, không xác nhận cùng bệnh nhân. Bổ sung các mặt cùng root cause: RPC PostgREST `read_prescription_draft(uuid)` là SECURITY DEFINER, role+clinic gate nhưng không gọi patient assignment guard; và API đọc liệu trình theo patient/visit cũng chỉ kiểm capability QUYEN_DOC. Bổ s
- **Điều kiện xảy ra:** Nhân viên TKYK có capability y khoa gọi API bằng mã bệnh nhân, lượt khám hoặc lịch hẹn cùng clinic ngoài danh sách bác sĩ mình được phân; hoặc ghép patient_id được phép với appointment_id của người khác. Thêm trường hợp TKYK đã gắn bác sĩ gọi trực tiếp PostgREST trên appointment/nháp/dữ liệu phân lô
- **Dẫn chứng ban đầu:** `src/clinicai/permissions/catalogue.py:723-735`; `src/clinicai/permissions/y_khoa.py:27-56`; `src/clinicai/services/thu_ky_bac_si.py:120-131`; `src/clinicai/api/v1/routers/clinical_forms.py:39-75`; `src/clinicai/services/clinical_form_service.py:83-109`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-010 (cũ) — Dời lịch đã check-in và đổi dịch vụ có thể làm lịch lệch loại khám của lượt
- **Khẳng định cần kiểm:** Transition reschedule cho phép trạng thái CHECKED_IN. Nhánh này nhận service_type_id và cập nhật appointment; nó không cập nhật visit đang mở. Luồng đổi dịch vụ chuyên biệt có kiểm trạng thái rồi cập nhật cả appointment và visit. Bàn khám chọn phiếu theo service_type_id của visit, nên lịch và lượt có thể chỉ sang hai dịch vụ khác nhau.
- **Điều kiện xảy ra:** Lịch đã check-in nhưng giờ hẹn vẫn còn phía trước; người có booking.manage dời lịch và chọn dịch vụ khác qua reschedule thay vì endpoint đổi dịch vụ chuyên biệt.
- **Dẫn chứng ban đầu:** `src/dashboard/app/(dashboard)/patients/AppointmentBooking.tsx:290-310`; `src/clinicai/api/v1/routers/booking.py:718-735`; `src/clinicai/services/booking_service.py:416-423`; `src/clinicai/services/booking_service.py:1837-1868`; `src/clinicai/services/booking_service.py:1416-1433`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-012 (cũ) — Thu hồi kỹ năng có thể để sót capability sau lỗi giữa chuỗi; bấm lại không tự đồng bộ
- **Khẳng định cần kiểm:** KyNangService xóa assignment trước rồi thu từng lego qua nhiều transaction riêng. Nếu một lần thu giữa chuỗi lỗi, trạng thái kỹ năng đã tắt nhưng capability còn lại. Retry thấy skill đã tắt và trả already trước khi đối soát lại quyền.
- **Điều kiện xảy ra:** Quản lý bỏ một kỹ năng đang cấp nhiều lego; DB/service lỗi sau khi đã thu một lego; quản lý thử lại thao tác bỏ kỹ năng.
- **Dẫn chứng ban đầu:** `src/clinicai/services/ky_nang_service.py:229-253`; `src/clinicai/services/ky_nang_service.py:251-286`; `src/clinicai/services/permission_service.py:392-428`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-013 (cũ) — Nhật ký tạo bệnh nhân giữ nguyên CCCD và thông tin liên hệ
- **Khẳng định cần kiểm:** Sự kiện patient.created lưu họ tên, ngày sinh, hai số điện thoại và số CCCD nguyên văn trong event_log. Endpoint audit lấy payload đó và trả lại cho người có audit.view; chính sách database cho phép Quản lý, Trưởng ca và CSKH đọc nhật ký cùng phòng khám.
- **Điều kiện xảy ra:** Nhân viên có quyền tạo hồ sơ nhập dữ liệu liên hệ/CCCD; sau đó người có quyền audit.view mở nhật ký trong ngày.
- **Dẫn chứng ban đầu:** `src/clinicai/services/patient_service.py:211-237`; `src/clinicai/services/audit_log_service.py:68-88`; `src/clinicai/services/audit_log_service.py:215-240`; `src/clinicai/api/v1/routers/audit_log.py:22-36`; `supabase/migrations/20260803000004_realtime_and_audit_scope.sql:54-64`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-015 (cũ) — Deploy kiểm Caddyfile mới trong file tạm nhưng restart với bind-mount cũ
- **Khẳng định cần kiểm:** Compose bind-mount một file Caddyfile riêng. Khi source đổi, deploy copy bản mới vào /tmp/Caddyfile.moi và validate file tạm, nhưng chỉ restart cùng container. Restart giữ inode bind-mount tại /etc/caddy/Caddyfile, nên Caddy vẫn đọc cấu hình cũ; không kiểm lại sau restart.
- **Điều kiện xảy ra:** Deploy thay Caddyfile hoặc CADDY_FILE và nhánh so sánh phát hiện khác nội dung.
- **Dẫn chứng ban đầu:** `docker-compose.yml:63-70`; `scripts/deploy-backend.sh:321-340`; `scripts/deploy-backend.sh:332-339`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-016 (cũ) — TKYK có thể ghi ghi chú khám hoặc thai kỳ ngoài phạm vi bệnh nhân được phân
- **Khẳng định cần kiểm:** POST/PATCH thai kỳ yêu cầu clinical.record.write; service kiểm clinic và trạng thái nhưng không gọi kiem_khach. Đường đọc cùng service có gate này, và helper giới hạn TKYK theo bác sĩ được phân. Preset TKYK gồm quyền ghi hồ sơ, nên ID cùng clinic có thể mở đường ghi ngoài phân công. Thêm PUT ghi_chu_luot: route chỉ kiểm quyền đổi trong hồ sơ và visit status, không gọi assignment helper, nên TKYK có thể lưu ghi chú tự do cho lượt cùng clinic của bác sĩ khác. Round 45 bổ sung PATCH hồ sơ hành chính: clinical.record.write gọi update theo clinic + ID nhưng không helper assignment.
- **Điều kiện xảy ra:** TKYK có quyền ghi, được phân cho bác sĩ A nhưng gửi patient_id hoặc pregnancy_id cùng clinic thuộc bệnh nhân bác sĩ B.
- **Dẫn chứng ban đầu:** `src/clinicai/api/v1/routers/thai_ky.py:59-85`; `src/clinicai/services/thai_ky_service.py:370-390`; `src/clinicai/services/thai_ky_service.py:392-430`; `src/clinicai/services/thai_ky_service.py:469-488`; `src/clinicai/services/thu_ky_bac_si.py:120-147`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-019 (cũ) — Lịch sử biểu mẫu lâm sàng và ghi chú lượt đọc được theo clinic, chưa theo vai
- **Khẳng định cần kiểm:** form_instance_lich_su lưu du_lieu cũ của mọi form_instance dưới dạng JSON; luot_ghi_chu lưu nội dung ghi chú tự do của visit. Cả hai bật RLS, nhưng policy cho authenticated chỉ dùng current_clinic_ids() và đều GRANT SELECT trực tiếp cho authenticated. Policy không lọc vai lâm sàng hoặc bệnh nhân được phân.
- **Điều kiện xảy ra:** Người dùng có JWT authenticated và membership active trong clinic truy vấn trực tiếp form_instance_lich_su hoặc luot_ghi_chu qua public REST/SQL. Policy hiện hành chỉ kiểm clinic_id nên cho phép đọc các dòng thuộc clinic đó, kể cả người ngoài nhóm lâm sàng.
- **Dẫn chứng ban đầu:** `supabase/migrations/20261007630000_form_instance_lich_su.sql:18-40`; `supabase/migrations/20261007630000_form_instance_lich_su.sql:42-59`; `supabase/migrations/20261007630000_form_instance_lich_su.sql:74-81`; `supabase/migrations/20261007640000_luot_ghi_chu.sql:18-33`; `supabase/migrations/20261007640000_luot_ghi_chu.sql:41-47`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-019 (cũ) — Tín hiệu backup có thể xanh dù bản sao ngoài VPS chưa được xác nhận
- **Khẳng định cần kiểm:** Backup cục bộ được xác minh và gửi heartbeat thành công trước khi systemd chạy uploader Viettel CFS. Lỗi uploader bị bỏ qua ở cấp unit; cờ offsite hiện có chỉ phản ánh R2, còn trạng thái Ops tổng thể không dùng kết quả CFS. Vì vậy monitor có thể tiếp tục xanh khi lần sao lưu ngoài VPS thất bại. Đây là lỗi đường điều khiển tĩnh, không chứng minh CFS đang lỗi hay đã mất dữ liệu.
- **Điều kiện xảy ra:** Timer backup nightly hoặc 15 phút chạy backup-db.sh thành công trên ổ cục bộ trong lúc /mnt/viettel-cfs không mount, mất kết nối, mất seal, hoặc upload/checksum CFS thất bại. Bước upload báo lỗi nhưng systemd bỏ qua mã lỗi; các lượt backup cục bộ tiếp theo lại đẩy trạng thái Kuma thành công.
- **Dẫn chứng ban đầu:** `scripts/backup-db.sh:579-595`; `scripts/backup-db.sh:598-616`; `scripts/backup-db.sh:623-650`; `scripts/systemd/clinicai-backup.service:24-30`; `scripts/systemd/clinicai-backup-15p.service:24-30`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-020 (cũ) — Quyền tải tệp kết quả mở được toàn bộ hồ sơ khám
- **Khẳng định cần kiểm:** GET /cskh/ho-so-kham/{appointment_id} dùng alias _KET_QUA_DOC_GUARD của _TEP_TAI_LEN_GUARD. cua_quyen cho qua nếu có bất kỳ một quyền nào; danh sách này gồm reception.checkin.perform và crm.manage, đồng thời moi_phong=True chấp nhận quyền cấp ở một phòng bất kỳ. HoSoKhamService.doc chỉ giới hạn dữ liệu theo clinic_id, rồi trả một bản tổng hợp có thông tin nhận diện/liên hệ, form_data lâm sàng, kết quả chỉ định, đơn thuốc và giá trị xét nghiệm. Route không có cửa đọc bệnh án riêng, bộ lọc cơ sở hoặc kiểm tra bệnh nhân được phân công.
- **Điều kiện xảy ra:** Nhân viên đã xác thực có một trong các capability của _TEP_TAI_LEN_GUARD (ví dụ reception.checkin.perform được cấp theo phòng, hoặc crm.manage) gọi endpoint với appointment_id hợp lệ trong cùng clinic. Giao diện CSKH hiện cũng gọi endpoint này từ lịch sử khám để mở hồ sơ và lấy visit_id cho luồng in
- **Dẫn chứng ban đầu:** `src/clinicai/api/v1/routers/cskh.py:673-679`; `src/clinicai/permissions/cua_quyen.py:27-49`; `src/clinicai/api/v1/routers/cskh.py:774-798`; `src/clinicai/services/ho_so_kham_service.py:40-72`; `src/clinicai/services/ho_so_kham_service.py:105-171`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-036 (cũ) — TKYK có thể chốt kết quả xét nghiệm ngoài phạm vi bác sĩ được phân
- **Khẳng định cần kiểm:** POST kết quả /review gác bằng capability result.review.approve; preset TKYK có capability này. Hàng chờ đọc gọi khach_duoc_xem để giới hạn bệnh nhân theo bác sĩ được phân, nhưng lệnh review không gọi helper đó. Service khóa chính kết quả bằng lab_result_id + clinic_id + clinic_patient_id do caller gửi, rồi đánh is_finalized=true và đóng task; nó không kiểm patient có thuộc phạm vi TKYK hay không. Endpoint release trả allowed=true cho kết quả đã finalized. Đây là thiếu object-level authorization trong một lệnh ghi/chốt, khác SEC-011 vốn tập trung đường đọc và SEC-016 ghi chú/tha kỳ; cần biết UUID cùng clinic và có capability. Chưa chứng minh thông báo đã gửi cho bệnh nhân.
- **Điều kiện xảy ra:** TKYK có capability result.review.approve, được phân công cho bác sĩ A nhưng biết lab_result_id và clinic_patient_id của kết quả cùng clinic thuộc bác sĩ B, rồi gọi POST /lab/results/{id}/review.
- **Dẫn chứng ban đầu:** `src/clinicai/api/v1/routers/lab.py:63-68`; `src/clinicai/permissions/catalogue.py:723-735`; `src/clinicai/api/v1/routers/lab.py:145-168`; `src/clinicai/api/v1/routers/lab.py:187-202`; `src/clinicai/services/lab_safety_service.py:197-221`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-038 (mới) — Staging công khai trên Internet dùng chung mật khẩu/hash với prod, giữ nguyên PII thật của nhân sự và chạy mã nhánh chưa duyệt
- **Khẳng định cần kiểm:** Staging được nạp lại mỗi đêm từ bản sao prod, bao gồm toàn bộ auth.users/identities của prod (hash mật khẩu giữ nguyên, 'tài khoản/mật khẩu y hệt prod'). Không có lớp chặn truy cập ở rìa (không basic auth, không allowlist IP): ai có tài khoản prod là vào được, và tên miền staging được Caddy prod phát công khai. Bộ che dữ liệu chỉ che khách; nhân sự (họ tên, SĐT, email, ngày sinh, số CCCD) được ghi là 'giu' (giữ nguyên). Staging lại chạy mã của nhánh đang thử (STAGING_REF) và dùng chung VPS, Caddy, ổ đĩa với prod.
- **Điều kiện xảy ra:** Một lỗ hổng trong mã nhánh đang thử (SSRF, SQL injection, lộ endpoint ops), hoặc kẻ tấn công thử mật khẩu yếu trên cổng đăng nhập staging công khai, hoặc ai đó đọc được DB/backup của staging.
- **Dẫn chứng ban đầu:** `caddy/Caddyfile.staging:14-15`; `caddy/staging-tren-prod.caddy.mau:10-23`; `scripts/staging-nap-ban-sao.sh:189-194`; `scripts/staging-che-du-lieu.sql:7-8`; `scripts/staging-che-du-lieu.sql:215-220`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-061 (mới) — Hoàn tất kết quả biến mọi câu điền sẵn chưa chỉnh thành “người dùng xác nhận”, kể cả câu khẳng định tim thai và chữ giữ chỗ “??”
- **Khẳng định cần kiểm:** Mẫu kết quả cận lâm sàng có sẵn câu mặc định mô tả bình thường (vd siêu âm thai sớm: tim_thai = “dương tính”; kết luận “… tương đương ?? tuần ?? ngày. Tim thai dương tính.”; nhiều ô “…”). Khi mở phiếu, engine gieo các câu này vào du_lieu với nguon = TEMPLATE_DEFAULT và giao diện ghi nhãn “(câu điền sẵn)” trong lúc còn nháp. Khi bấm Hoàn tất, engine đổi hàng loạt mọi ô TEMPLATE_DEFAULT thành USER; không chặn, không nhắc ô nào còn là câu mẫu hay còn chữ giữ chỗ, vì hàm đếm ô trống chỉ coi ô rỗng là trống. Sau Hoàn tất không còn dấu vết nào phân biệt câu người đã khám với câu mẫu chưa ai chạm.
- **Điều kiện xảy ra:** Người nhập (điều dưỡng/bác sĩ) bấm Hoàn tất mà không sửa một ô còn câu mẫu; ví dụ siêu âm thai sớm khi chưa ghi nhận được tim thai, hoặc quên thay “?? tuần ?? ngày” trong kết luận.
- **Dẫn chứng ban đầu:** `src/clinicai/services/form_engine_service.py:793-796`; `src/clinicai/services/form_engine_service.py:1459-1466`; `src/clinicai/services/form_engine_service.py:1552-1570`; `src/clinicai/phieu_kham/mau_ket_qua_v3.json:44-44`; `src/clinicai/phieu_kham/mau_ket_qua_v3.json:68-68`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-039 (mới) — Hồ sơ lâm sàng: kiểm phạm vi thư ký theo patient_id nhưng ghép lượt theo appointment_id không ràng buộc cùng bệnh nhân, và nhật ký mở hồ sơ ghi sai khách
- **Khẳng định cần kiểm:** `doc_ho_so` chỉ kiểm thư ký được phân (TKYK) với `patient_id` do người gọi gửi. Khi có `appointment_id` (không có `visit_id`), lượt được lấy bằng `appointment_id` + `clinic_id`, KHÔNG kèm `clinic_patient_id = patient_id`. Các cổng đọc (bệnh án, đơn thuốc, sinh hiệu) sau đó chỉ lọc theo `visit_id` + `clinic_id`, nên SOAP, đơn thuốc nháp, đơn thuốc và sinh hiệu của lượt thuộc bệnh nhân khác được ghép vào phản hồi của `patient_id` mà thư ký được phép xem. Router lại ghi nhật ký mở hồ sơ theo `patient_id` người gọi gửi, không theo bệnh nhân thực sự bị đọc.
- **Điều kiện xảy ra:** Một tài khoản có vai TKYK đã được phân theo bác sĩ (khach_duoc_xem trả danh sách) gọi GET /clinical-records/doc?patient_id=<khách được phân>&appointment_id=<lịch của khách ngoài phạm vi>. Cần biết UUID một lịch hẹn (UUID này xuất hiện ở nhiều API danh sách lịch).
- **Dẫn chứng ban đầu:** `src/clinicai/services/ho_so_lam_sang_doc.py:80-89`; `src/clinicai/services/ho_so_lam_sang_doc.py:101-117`; `src/clinicai/services/ho_so_lam_sang_doc.py:118-127`; `src/clinicai/services/clinical_record_service.py:884-909`; `src/clinicai/services/clinical_prescription_service.py:191-208`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### FIN-021 (mới) — Cờ “cần đối soát” của lần thu là dấu vĩnh viễn: không có chủ, hạn, nhắc hay lệnh đóng, trong khi thuốc đã thu tiền có thể bị kẹt không giao được
- **Khẳng định cần kiểm:** Khi xác minh chuyển khoản/QR, payment_service gắn can_doi_soat + doi_soat_ly_do (hoá đơn đổi, chưa ghi bán thuốc, lệch số tiền ngân hàng) và chỉ ghi một dòng event_log. Trigger payment_cycle_guard cấm đổi các cột này sau khi PAID, nên không có lệnh nào “đã đối soát xong”. Không thấy việc (work item/thông báo/canh gác) nào được sinh ra cho người chịu trách nhiệm. Màn Nhà thuốc có giai đoạn CAN_DOI_SOAT nhưng ở giai đoạn này không nút ghi nào được mở.
- **Điều kiện xảy ra:** Một lần thu thuốc CK/QR được xác nhận khi phân lô chưa ghi bán được (khong_ban_duoc), hoá đơn đã đổi, hoặc số tiền ngân hàng thực nhận khác phần chuyển khoản. Cũng áp cho cờ THU_CU_KHONG_TRUY_DUOC của hoá đơn dịch vụ.
- **Dẫn chứng ban đầu:** `src/clinicai/services/payment_service.py:1193-1234`; `src/clinicai/services/payment_service.py:1266-1296`; `supabase/migrations/20261014147000_ck_so_tien_thuc_nhan.sql:52-57`; `src/clinicai/services/ban_thuoc_service.py:99-104`; `src/clinicai/services/ban_thuoc_service.py:133-165`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### SEC-040 (mới) — Mở toàn bộ capability cho mọi tài khoản nội bộ và bỏ rào chứng chỉ: ký/hoàn tất khám, hoàn tiền, huỷ lô không còn gắn với hành nghề hay phân quyền tối thiểu
- **Khẳng định cần kiểm:** Migration 20260930900000 cấp mọi capability của mọi khối (trừ 4 khối quản trị) cho mọi tài khoản nội bộ đang hoạt động trong MỌI phòng khám, thêm các khối ấy vào gói mẫu của mọi vai (tài khoản tạo sau cũng có) và tắt cờ quyen_theo_lich cho mọi phòng khám. Cột chung_chi_lam_sang còn nhưng 'không lệnh nào đọc nó để chặn' và có test khẳng định không quyền nào đòi chứng chỉ. Hồ sơ nhân sự có số CCHN và phạm vi hành nghề nhưng chỉ được lưu, không dùng để cho phép hay chặn thao tác nào. Màn Phân quyền nói thẳng 'Đang mở toàn bộ cho mọi nhân sự'.
- **Điều kiện xảy ra:** Một thu ngân/lễ tân/thư ký bấm hoàn tất khám, ký kết quả, kê hay giao thuốc, huỷ lô, sửa giá thuốc, hoàn tiền (các capability này nằm trong khối được cấp mở), hoặc một phòng khám mới được tạo từ cùng mã nguồn và gói mẫu.
- **Dẫn chứng ban đầu:** `supabase/migrations/20260930900000_mo_full_lego.sql:8-36`; `supabase/migrations/20260930900000_mo_full_lego.sql:38-52`; `src/clinicai/permissions/catalogue.py:24-30`; `src/tests/test_clinical_cluster.py:215-229`; `src/tests/services/test_clinical_sign.py:49-67`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-029 (mới) — Không có thành phần nào tự dựng lại stack sau khi Docker daemon hoặc máy chủ khởi động lại; cụm 'self-heal' trong mẫu env không tồn tại trong repo
- **Khẳng định cần kiểm:** Việc đưa dịch vụ trở lại chỉ dựa vào `restart: unless-stopped` của Docker và vào lần chạy tay của deploy-backend.sh. Các healthcheck 'nhịp tim' của su-kien/day-tep/relay chỉ đánh dấu unhealthy, mà Docker Engine không khởi động lại container unhealthy. Mẫu env prod nhắc 'deploy + self-heal' nhưng repo (đến SHA kiểm toán) chỉ có 4 unit systemd (backup, backup-15p, ops-status, staging-nap), không có unit/hook/autoheal nào đưa compose project lên lại hay restart container unhealthy. Database nằm ở compose project khác (clinicai_db) nên khoá `depends_on` của ứng dụng không buộc thứ tự khi khởi động lại máy.
- **Điều kiện xảy ra:** Docker daemon khởi động lại, máy chủ reboot, hoặc một worker (su-kien, day-tep, relay) treo vòng lặp mà tiến trình không thoát: container chuyển unhealthy nhưng không được restart.
- **Dẫn chứng ban đầu:** `.env.prod.example:19-20`; `docker-compose.yml:307-313`; `docker-compose.yml:376-390`; `docker-compose.supabase.yml:24-25`; `scripts/deploy-backend.sh:371-412`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### INF-030 (mới) — Toàn bộ giám sát và cảnh báo nằm trên chính VPS được giám sát, không có điểm kiểm từ bên ngoài; monitor 'cổng vào công khai' chỉ gọi route /health tĩnh bên trong mạng docker
- **Khẳng định cần kiểm:** Uptime Kuma, Dozzle, bộ canh gác `canh_bao` (trong su-kien), relay Telegram và ops-status đều chạy trên cùng VPS và cùng Docker daemon. Monitor 'Caddy — cổng vào công khai' gọi `http://caddy:80/health` từ trong mạng nội bộ; Caddy trả chuỗi 'ok' cố định cho đường này nên nó không chứng minh DNS, TLS, tường lửa hay đường vào từ ngoài. Danh sách monitor của Kuma 1.x được bấm tay trong volume; `check-monitoring.sh` tự thừa nhận không chứng minh Kuma đang theo dõi. Nếu VPS, Docker hay Kuma ngừng, cảnh báo cũng ngừng và sự im lặng trông như 'khoẻ'.
- **Điều kiện xảy ra:** Host/Docker ngừng, mất volume Kuma, mất đường mạng ra Telegram, hoặc cổng 443 công khai hỏng trong khi nội bộ vẫn trả 200.
- **Dẫn chứng ban đầu:** `monitoring/monitors.json:36-48`; `caddy/Caddyfile:147-150`; `docker-compose.yml:429-460`; `scripts/check-monitoring.sh:50-71`; `monitoring/README.md:3-16`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### OPS-015 (mới) — Script xoá dữ liệu khách chỉ chặn bằng cụm gõ tay, không có chốt kỹ thuật 'chưa có dữ liệu thật', không giới hạn theo phòng khám và có bản xoá cả nhật ký
- **Khẳng định cần kiểm:** scripts/xoa-du-lieu-test.sh đọc DATABASE_URL từ .env.prod mặc định, rồi xoá patient, visit, payment, lab_result, clinical_record… và cả event_log (sổ chỉ-thêm) sau khi người chạy gõ 'XOA HET'. Không có bước kiểm 'hệ thống đã đón bệnh nhân thật chưa' (khác với scripts/xoa-du-lieu-khach-truoc-khi-mo-cua.sql vốn còn chặn khi có lượt FINALIZED/AMENDED). Cả hai script xoá toàn bảng, không lọc clinic_id. undo-roster-fixture.sh cũng xoá staff trên DB đọc từ .env.prod với chốt chặn chỉ đếm 12 nhóm tham chiếu.
- **Điều kiện xảy ra:** Người vận hành chạy script trên máy có .env.prod (hoặc ENV_FILE trỏ nhầm), hoặc ai đó chép script sang một bản triển khai nhiều phòng khám dùng chung DB; sau khi có dữ liệu thật nhưng chưa có lượt đã ký (ví dụ chỉ mới có lịch hẹn, phiếu thu, kết quả đang chờ duyệt).
- **Dẫn chứng ban đầu:** `scripts/xoa-du-lieu-test.sh:20-29`; `scripts/xoa-du-lieu-test.sh:80-82`; `scripts/xoa-du-lieu-test.sh:116-196`; `scripts/xoa-du-lieu-khach-truoc-khi-mo-cua.sql:33-40`; `scripts/xoa-du-lieu-khach-truoc-khi-mo-cua.sql:75-101`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### PHAR-005 (mới) — Cấp thuốc chỉ kiểm lượt đã có lần thu thuốc PAID, không kiểm dòng đơn có nằm trong hoá đơn đã thu
- **Khẳng định cần kiểm:** `PharmacyService.cap_phat` tra lần thu `kind='thuoc' AND status='PAID'` theo CẢ LƯỢT rồi coi mọi dòng đơn của lượt là đã thu. Nhánh giao không lô (`drug_batch_id` rỗng) và nhánh giao thẳng từ lô (`_cap_phat_cu`) chỉ chặn bằng `purchased_qty` hoặc `quantity_num` của dòng, không đối chiếu `payment_bill_line`. Khi bác sĩ đính chính đơn SAU lúc thu tiền (dòng thay thế/dòng thêm có id mới, không kế thừa số mua, phân lô, tiền), dòng mới chưa nằm trong hoá đơn nào nhưng vẫn qua được cổng này.
- **Điều kiện xảy ra:** Có thể xảy ra nếu: lượt đã thu tiền thuốc (PAID); bác sĩ lưu lại đơn và đi đường ĐÍNH CHÍNH (thêm hoặc thay dòng); lần thu hiện có không gắn lô (luồng thu không chờ kho / legacy) hoặc dòng mới chưa có phân lô; dược sĩ bấm giao dòng mới (UI cũng dùng cờ cấp lượt `gd == DA_THU` để hiện nút `giao_khong
- **Dẫn chứng ban đầu:** `src/clinicai/services/pharmacy_service.py:710-723`; `src/clinicai/services/pharmacy_service.py:731-758`; `src/clinicai/services/pharmacy_service.py:958-966`; `src/clinicai/services/pharmacy_service.py:1240-1248`; `src/clinicai/services/dinh_chinh_don.py:12-20`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### CLIN-062 (mới) — Lưu đơn thuốc là ghi đè cả đơn từ ảnh chụp của trình duyệt: ảnh cũ hoặc rỗng có thể xoá/đính chính bỏ dòng thuốc của người khác
- **Khẳng định cần kiểm:** Mục E (đơn thuốc) tự lưu bằng lệnh luu-don gửi TOÀN BỘ danh sách dòng thuốc mà tab đang giữ. Máy chủ so gói với các dòng hiện hành của lượt (đơn là của LƯỢT, bác sĩ chính và bàn tư vấn dùng chung) và coi dòng nào có trong CSDL mà không có trong gói là dòng bị bỏ: xoá cứng nếu chưa ai đụng, hoặc 'đính chính' nếu đã có dấu vết. Không có token phiên bản/hash đơn trong request. Phía trình duyệt, sự kiện 'prescription' chỉ gộp lại SỐ LƯỢNG do quầy điền vào dòng đã có (gopSoLuongQuayDien), không bao giờ thêm dòng mới của người khác vào danh sách đang giữ. Nếu lần nạp đơn lúc mở phiếu lỗi (napDon trả null) thì danh sách khởi tạo là rỗng và màn vẫn cho thêm thuốc. Khi máy chủ đòi lý do đính chính, m
- **Điều kiện xảy ra:** Có thể xảy ra nếu: (a) bác sĩ chính mở phiếu, sau đó bàn tư vấn/thư ký lưu thêm dòng thuốc vào cùng lượt, rồi bác sĩ sửa một ô bất kỳ của đơn; hoặc (b) lần đọc đơn lúc mở phiếu bị lỗi mạng/5xx, bác sĩ bấm '+ Thuốc ngoài danh mục' hoặc chọn thuốc từ danh mục; hoặc (c) tab để lâu, quầy đã sửa số lượng
- **Dẫn chứng ban đầu:** `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:309-364`; `src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:225-262`; `src/dashboard/lib/phieu-kham.ts:785-805`; `src/clinicai/services/dinh_chinh_don.py:1-30`; `src/clinicai/services/dinh_chinh_don.py:241-261`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### FE-029 (mới) — Bốn ô đếm và bộ lọc hàng đợi của màn Quản lý khách hàng chỉ tính trên 50 khách của trang đang xem, trang lại xếp theo hoạt động gần nhất chứ không theo độ gấp
- **Khẳng định cần kiểm:** Màn /customers là hàng đợi làm việc chính của CSKH. Backend phân trang 50 khách/trang, xếp theo 'hoạt động gần nhất' (ngày tạo, lúc đặt lịch, giờ hẹn đã qua, lượt khám). Phần giao diện tính các ô 'Cần xử lý hôm nay', 'Quá SLA', 'Chờ xác nhận', 'Đã hoàn thành' và bộ lọc theo ô bằng rows.filter(...) trên đúng 50 dòng đã tải. Nhãn ô không nói đây là số của trang. Thanh trang chỉ hiện 'Trang x/y · N khách'.
- **Điều kiện xảy ra:** Phòng khám có hơn 50 khách trong khoảng ngày/bộ lọc đang chọn, và có khách quá hạn nằm ở trang 2 trở đi (thường là khách có hoạt động cũ nhất, tức nhóm dễ bị bỏ quên nhất). CSKH nhìn ô 'Quá SLA = 0' trên trang 1 và kết luận không có việc quá hạn.
- **Dẫn chứng ban đầu:** `src/dashboard/app/(dashboard)/customers/CustomersView.tsx:860-891`; `src/dashboard/app/(dashboard)/customers/CustomersView.tsx:1348-1381`; `src/dashboard/app/(dashboard)/customers/page.tsx:142-183`; `src/dashboard/app/(dashboard)/customers/page.tsx:1141-1174`; `src/clinicai/services/danh_sach_khach_cskh.py:253-256`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### OPS-016 (mới) — Kịch bản SQL trong fixtures ghi thẳng auth.users, đặt lại mật khẩu và xoá dữ liệu mà không có chốt môi trường; một bản đã từng chạy nhầm lên prod
- **Khẳng định cần kiểm:** Các tệp supabase/fixtures/*.sql (staff_logins, luot_kham_demo, tai_khoan_chi_xem_kho, cskh_ba_nguoi_that, clinic_roster...) chỉ ghi 'LOCAL/STAGING ONLY' trong comment. Không có câu lệnh nào tự kiểm môi trường (ví dụ từ chối khi có bệnh nhân không phải DEMO, hoặc yêu cầu cờ rõ ràng). Chúng upsert thẳng vào auth.users/auth.identities, ON CONFLICT DO UPDATE đặt lại encrypted_password về giá trị công khai trong repo và bật lại is_active, xoá cứng clinic_membership của vai khác, và DELETE auth.users 'clinic@dr4women.local'. scripts/undo-roster-fixture.sh ghi lại sự cố thật: clinic_roster.sql đã được nạp nhầm lên prod, tạo 35 dòng staff trùng người.
- **Điều kiện xảy ra:** Người vận hành chạy nhầm `psql $PROD -f supabase/fixtures/staff_logins.sql` (hoặc luot_kham_demo/tai_khoan_chi_xem_kho) vì chúng nằm cạnh các kịch bản vận hành thật như cskh_ba_nguoi_that.sql, tai_khoan_theo_nguoi.sql, lich_lam_viec_tuan_mau.sql.
- **Dẫn chứng ban đầu:** `supabase/fixtures/staff_logins.sql:13-14`; `supabase/fixtures/staff_logins.sql:83-90`; `supabase/fixtures/staff_logins.sql:132-142`; `supabase/fixtures/clinic_roster.sql:38-40`; `scripts/undo-roster-fixture.sh:1-22`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.

### DB-008 (mới) — seed.sql không có chốt chặn: chạy lại trên DB đang sống vẫn kích hoạt 13 hàm đồng bộ ghi đè giá, danh mục thuốc và hướng dẫn dùng của mọi phòng khám
- **Khẳng định cần kiểm:** Phần đầu seed.sql là INSERT thuần (không ON CONFLICT) nên trên DB đã có dữ liệu chúng chỉ báo lỗi trùng khoá; nhưng phần đuôi (dòng 3719-3758) gọi 13 hàm SQL đồng bộ danh mục và các hàm này CHẠY ĐƯỢC LẠI mà không kiểm DB đích có phải DB mới hay không. chuan_hoa_danh_muc_thuoc_kiotviet() lặp qua MỌI clinic có drug_catalog, đặt lại tên/giá/đơn vị/cách dùng/lưu ý theo bản chuẩn Dr4Women (kể cả ghi NULL đè chữ do dược sĩ nhập) và tắt (is_active=false) mọi mặt hàng ngoài 82 mã chuẩn. dong_bo_danh_muc_dich_vu() đặt lại tên, nhóm, active=true, bên thu và giá (khi giá Excel > 0 hoặc thu hộ) của dịch vụ khớp tên. Bản migration của chính các hàm này có chốt IF EXISTS(staff), còn seed thì không. README
- **Điều kiện xảy ra:** Có thể xảy ra nếu một người vận hành chạy psql -f seed.sql (README) hoặc supabase db reset/seed trỏ nhầm vào DB đã có khách (staging đã nạp bản sao prod, prod, hoặc DB của phòng khám thứ hai). Không cần quyền đặc biệt ngoài quyền DB. psql mặc định tiếp tục sau lỗi trùng khoá nên phần đuôi vẫn chạy.
- **Dẫn chứng ban đầu:** `supabase/seed.sql:3717-3758`; `supabase/seed.sql:1-9`; `supabase/migrations/20260925000014_danh_muc_thuoc_kiotviet.sql:54-54`; `supabase/migrations/20260925000014_danh_muc_thuoc_kiotviet.sql:626-643`; `supabase/migrations/20260925000014_danh_muc_thuoc_kiotviet.sql:648-657`
- **Cần trả lời riêng:** (1) đường đi từ giao diện/API tới dòng lỗi có thật không; (2) có chốt nào khác (trigger, ràng buộc, kiểm ở tầng khác) chặn mất không; (3) mức "cao" có đúng không.


## Bản prod
Đã đối chiếu 20/10/2026 bằng lệnh chỉ đọc trên VPS: thư mục chạy thật ở commit 956ba4f2, ba container prod dựng lại 19/10 13:11 đến 13:12. Bản bạn đọc chính là bản khách đang dùng. Chỉ kết luận về prod; bỏ qua staging và local.
