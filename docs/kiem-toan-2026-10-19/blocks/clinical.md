# Clinical / workflow / ownership

Trạng thái: đang làm.

Đã khởi tạo inventory 158 file; chưa có kết luận.

Bước tiếp: quét cấu trúc toàn khối và truy vết lifecycle, ownership, finalization.

## Root checkpoint 2026-10-19T17:46:43.192198+07:00

Khối chưa hoàn tất. Nội dung agent ban đầu là baseline543b9787+WIP; ưu tiên PHAT-HIEN.json/main_validation cho kết luận mới.
- CLIN-001: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- CLIN-002: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
- CLIN-003: still_present_on_main — Root đối chiếu vùng code liên quan trên bản main ghim; kết luận giữ ở đúng mức bằng chứng, chưa kiểm production.
Tiếp theo: TIEP-TUC.md và MAIN-PHAM-VI.json. Không tự nâng scan thành đọc sâu.


## v0.18 — bổ sung trace

CLIN-010 HIGH/confirmed-static: reschedule CHECKED_IN có thể đổi service_type_id trên appointment mà không cập nhật visit; specialized path thì cập nhật cả hai. CLIN-011 MEDIUM/confirmed-static: dedicated reschedule history/event bỏ delta service/channel/referrer. Chưa DB test; xem PHAT-HIEN.json làm nguồn canonical.


## v0.19 — CLIN-012 / hạn kết quả mẫu đối tác

CLIN-012 MEDIUM/design_gap: H7 chỉ tạo timer nếu node `lam_ben_ngoai`; mẫu gửi đối tác là node nội bộ nhưng test xác nhận bàn đối tác nhận mẫu, tải file và trả kết quả qua bước riêng. Chưa test DB timer, chưa có bằng chứng SLA bị lỡ; cần chủ nghiệp vụ chốt policy. Canonical evidence ở `PHAT-HIEN.json`.

## v0.21 — result lifecycle, finalized phiếu và worklist completeness

- **CLIN-019 MEDIUM/design_gap:** synthetic DB probe xác nhận thu hồi tệp kết quả hiệu lực cuối cùng sau khi đối tác đã trả không gỡ `ket_qua_luc`; H7 coi kết quả đã về và bỏ cảnh báo quá hạn. Có điều kiện: code định sẵn lệnh riêng để hoàn tác marker, cần chốt owner/policy. Note: `blocks/scheduling-result-revoke-h7-followup.md`; RUN-039.
- **CLIN-020 MEDIUM/design_gap:** probe v5 save cho visit FINALIZED thành công, revision tăng nhưng không tạo amendment/reason; module v5 tự ghi nhận “hoàn tất không khóa”, còn clinical shell và mode contract khóa FINALIZED. Cần chủ sản phẩm thống nhất hợp đồng, không tự suy policy pháp lý.
- **CLIN-021 MEDIUM/design_gap:** probe release v1 → sửa v2 chưa release → `in_ket_qua` vẫn trả v2 như không phải draft. Migration nói release table chưa được nối vào đường in/gửi cấu trúc; cần chốt release gate.
- **CLIN-022 MEDIUM/confirmed_static:** worklist CSKH liệu trình dùng LIMIT 200 nhưng API không trả `has_more`/pagination và UI chỉ hiện `ds.length`; chưa chạy bộ dữ liệu >200.

Các probe v0.21 dùng DB synthetic/disposable; riêng CLIN-020/021 là service-level. Không gọi production, không dùng PHI. Chi tiết exact-source line/hash và giới hạn ở `PHAT-HIEN.json`.

## v0.22 — queue kết quả, đặt lịch và checkout

- CLIN-023: hàng duyệt kết quả lọc 60 ngày + LIMIT 200, không báo bị cắt; confirmed_static, chưa chốt SLA/retention.
- CLIN-024: unique booking/care-episode constraint chặn race nhưng UniqueViolation không được map rõ thành conflict; chưa chạy concurrency test.
- CLIN-025/026: enum patient_kind sai âm thầm thành None; datetime naive có thể TypeError khi so với UTC aware. Cả hai static, chưa HTTP probe.
- CLIN-027: checkout stale list LIMIT 300, route/proxy/UI không có paging metadata; chưa seed >300.
- Đối chiếu chính sách nghiệp vụ/SLA trước khi chọn hành vi cuối; không đọc production/PHI.

## v0.24 — retry mua thuốc/chỉ định và CSKH

CLIN-030: tạo khách mua thuốc không có key, patient insert và lượt mở tách transaction; số điện thoại rỗng cho phép duplicate sau timeout. CLIN-031: key chỉ định ngẫu nhiên mỗi request nên retry không replay. CLIN-032: recall giới hạn 500 nhưng UI bỏ bi_cat/tran. CLIN-033: đóng hẹn gọi không yêu cầu outcome/interaction. Tất cả static, chưa chạy fault injection/browser.

## Round 38 — CLIN-055

CLIN-055 MEDIUM, exact-main static: lịch sử dịch vụ lỗi/chưa xong có thể để patientKind NEW cũ đi vào POST; backend coi NEW là lệnh đóng episode đang sống và mở episode mới. Đường lỗi có điều kiện, chưa runtime/production. Không trùng CLIN-025 (enum invalid). Chi tiết/hash/ranges: `blocks/round38.md`, `blocks/round38.coverage.json`.

## Round 39 — chính sách assignment giữ mở

POST đặt chỉ định hiện guard capability nhưng không gọi helper kiểm doctor/team assignment; các đường note/authorization khác có helper đó. Không tạo finding khi chưa rõ quyền `clinical.order.place` là clinic-wide hay assignment-bound. Ngoại lệ ca trực có test chấp nhận thay lễ tân bằng CSKH; competency matrix phòng lâm sàng cần clinical owner chốt. Chi tiết exact-main, phạm vi và giới hạn ở `blocks/round39.md`/coverage.
