# Đề bài cho Codex: xác minh độc lập phần 2/4 (10 mục mức cao)

Bạn là người soát lỗi độc lập, KHÔNG phải người viết báo cáo. Nhiệm vụ: với từng mục dưới đây, tự đọc code và cho biết khẳng định có đúng không. Mục tiêu là bắt báo động giả và bắt chỗ báo cáo thổi phồng, không phải xác nhận cho đẹp. Một kết luận "bác bỏ" có bằng chứng giá trị hơn mười kết luận "đúng" hời hợt.

## Quy tắc
- CHỈ ĐỌC. Không sửa code, không chạy ứng dụng, API, test, database, VPS, production. Không mở `.env*`, không đọc dữ liệu bệnh nhân. Không đưa khoá hay bí mật vào đâu cả.
- Chỉ lấy bằng chứng từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`, ví dụ: `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:ĐƯỜNG/DẪN`. Không dùng working tree.
- Đừng đọc kết luận của báo cáo trước khi tự đọc code. Đọc dẫn chứng ban đầu như gợi ý chỗ bắt đầu, rồi tự lần ngược: ai gọi, kiểm quyền ở đâu, trigger hay ràng buộc nào ở cơ sở dữ liệu (`supabase/migrations`), UI có chặn bù không.
- Không chắc thì ghi `KHONG_XAC_DINH` và nói thiếu gì. Không đoán.
- Tiếng Việt, ngắn gọn.

## Kết quả cần nộp
Ghi một tệp `docs/kiem-toan-2026-10-19/dot-2-doc-toan-bo/KET-QUA-CODEX-2.json` (mảng, mỗi mục một đối tượng):
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

## Danh sách phần 2/4: FE-029, OPS-016, DB-008, CLIN-001, CLIN-003, DB-001, DB-002, DB-004, FIN-002, FIN-003

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

## Bản prod
Đã đối chiếu 20/10/2026: VPS prod đang ở commit 956ba4f2, chính là bản bạn đọc. Chỉ kết luận về prod.

Nếu hết hạn mức giữa chừng: ghi ngay kết quả các mục đã xong vào tệp KET-QUA-CODEX-2.json rồi dừng, mục chưa làm để trống.
