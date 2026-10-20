# Đề bài cho Codex: xác minh độc lập phần 1/4 (10 mục mức cao)

Bạn là người soát lỗi độc lập, KHÔNG phải người viết báo cáo. Nhiệm vụ: với từng mục dưới đây, tự đọc code và cho biết khẳng định có đúng không. Mục tiêu là bắt báo động giả và bắt chỗ báo cáo thổi phồng, không phải xác nhận cho đẹp. Một kết luận "bác bỏ" có bằng chứng giá trị hơn mười kết luận "đúng" hời hợt.

## Quy tắc
- CHỈ ĐỌC. Không sửa code, không chạy ứng dụng, API, test, database, VPS, production. Không mở `.env*`, không đọc dữ liệu bệnh nhân. Không đưa khoá hay bí mật vào đâu cả.
- Chỉ lấy bằng chứng từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`, ví dụ: `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:ĐƯỜNG/DẪN`. Không dùng working tree.
- Đừng đọc kết luận của báo cáo trước khi tự đọc code. Đọc dẫn chứng ban đầu như gợi ý chỗ bắt đầu, rồi tự lần ngược: ai gọi, kiểm quyền ở đâu, trigger hay ràng buộc nào ở cơ sở dữ liệu (`supabase/migrations`), UI có chặn bù không.
- Không chắc thì ghi `KHONG_XAC_DINH` và nói thiếu gì. Không đoán.
- Tiếng Việt, ngắn gọn.

## Kết quả cần nộp
Ghi một tệp `docs/kiem-toan-2026-10-19/dot-2-doc-toan-bo/KET-QUA-CODEX-1.json` (mảng, mỗi mục một đối tượng):
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

## Danh sách phần 1/4: SEC-038, CLIN-061, SEC-039, FIN-021, SEC-040, INF-029, INF-030, OPS-015, PHAR-005, CLIN-062

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

## Bản prod
Đã đối chiếu 20/10/2026: VPS prod đang ở commit 956ba4f2, chính là bản bạn đọc. Chỉ kết luận về prod.

Nếu hết hạn mức giữa chừng: ghi ngay kết quả các mục đã xong vào tệp KET-QUA-CODEX-1.json rồi dừng, mục chưa làm để trống.
