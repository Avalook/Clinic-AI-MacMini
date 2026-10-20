# Đề bài cho Codex: xác minh độc lập phần 4/4 (10 mục mức cao)

Bạn là người soát lỗi độc lập, KHÔNG phải người viết báo cáo. Nhiệm vụ: với từng mục dưới đây, tự đọc code và cho biết khẳng định có đúng không. Mục tiêu là bắt báo động giả và bắt chỗ báo cáo thổi phồng, không phải xác nhận cho đẹp. Một kết luận "bác bỏ" có bằng chứng giá trị hơn mười kết luận "đúng" hời hợt.

## Quy tắc
- CHỈ ĐỌC. Không sửa code, không chạy ứng dụng, API, test, database, VPS, production. Không mở `.env*`, không đọc dữ liệu bệnh nhân. Không đưa khoá hay bí mật vào đâu cả.
- Chỉ lấy bằng chứng từ Git blob bất biến của SHA `956ba4f236b1c92f1280d2097018c199e90ce8c7` trong `/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini`, ví dụ: `git -C /Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini show 956ba4f236b1c92f1280d2097018c199e90ce8c7:ĐƯỜNG/DẪN`. Không dùng working tree.
- Đừng đọc kết luận của báo cáo trước khi tự đọc code. Đọc dẫn chứng ban đầu như gợi ý chỗ bắt đầu, rồi tự lần ngược: ai gọi, kiểm quyền ở đâu, trigger hay ràng buộc nào ở cơ sở dữ liệu (`supabase/migrations`), UI có chặn bù không.
- Không chắc thì ghi `KHONG_XAC_DINH` và nói thiếu gì. Không đoán.
- Tiếng Việt, ngắn gọn.

## Kết quả cần nộp
Ghi một tệp `docs/kiem-toan-2026-10-19/dot-2-doc-toan-bo/KET-QUA-CODEX-4.json` (mảng, mỗi mục một đối tượng):
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

## Danh sách phần 4/4: SEC-011, CLIN-010, SEC-012, SEC-013, INF-015, SEC-016, SEC-019, INF-019, SEC-020, SEC-036

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

## Bản prod
Đã đối chiếu 20/10/2026: VPS prod đang ở commit 956ba4f2, chính là bản bạn đọc. Chỉ kết luận về prod.

Nếu hết hạn mức giữa chừng: ghi ngay kết quả các mục đã xong vào tệp KET-QUA-CODEX-4.json rồi dừng, mục chưa làm để trống.
