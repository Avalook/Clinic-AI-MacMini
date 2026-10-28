# Bảng phân loại RÁC — soạn 17/10/2026 18:43 (CHỈ ĐỌC — chưa xoá gì)

Soạn bằng script đọc (git, gh, du, lsof). Quy tắc: **không gỡ gì khi chưa được duyệt**; mục `NGUY_HIEM` (commit chỉ có ở máy này) và `XEM_LAI` phải hỏi người làm ra nó trước.

## 1. Worktree trên Mac (cỡ riêng từng cái, đã bỏ phần tính trùng)

| Loại | Số | Dung lượng | Nghĩa |
|---|---|---|---|
| GIU | 51 | 28.0 GB | đang dùng / PR mở / có thay đổi dở |
| LUU_TRU | 26 | 18.0 GB | ứng viên gỡ (đã vào main hoặc PR đóng, sạch, không tiến trình) |
| XEM_LAI | 12 | 6.2 GB | chưa vào main, không PR — hỏi chủ |
| NGUY_HIEM | 2 | 0.9 GB | commit chưa đẩy — KHÔNG gỡ |

### 1.1 KHÔNG GỠ — commit chỉ có ở máy này (2)

| GB | Ngày | Nhánh | Thư mục | Lý do |
|---|---|---|---|---|
| 0.83 | 2026-10-07 | `claude/performance-check-b328e6` | `performance-check-b328e6` | 1 commit CHỈ có ở máy này (chưa đẩy) — gỡ là MẤT |
| 0.03 | 2026-10-17 | `claude/bo-context-chung` | `bo-context-chung` | 1 commit CHỈ có ở máy này (chưa đẩy) — gỡ là MẤT |

### 1.2 XEM LẠI — hỏi chủ trước (12)

| GB | Ngày | Nhánh | Thư mục | Lý do |
|---|---|---|---|---|
| 1.59 | 2026-09-28 | `claude/doi-vai-nhan-su` | `stop-agents-dot3-wip-4b90e6` | 1 commit chưa vào main, không PR |
| 0.86 | 2026-10-13 | `codex/staging-1310-405-406-407` | `Dr4Women-MacMini` | 1 commit chưa vào main, không PR |
| 0.79 | 2026-10-16 | `claude/doi-tac-chung-khung-phong` | `agent-a31551bb825cf927e` | 8 commit chưa vào main, không PR |
| 0.75 | 2026-10-16 | `claude/phong-doi-tac-luong-chung` | `agent-ac90348ddac577a72` | 1 commit chưa vào main, không PR |
| 0.75 | 2026-10-06 | `claude/dong-bo-mat-khau-gotrue` | `agent-a7cec2f72b8137d2f` | 1 commit chưa vào main, không PR |
| 0.68 | 2026-10-09 | `claude/ket-qua-dieu-tri-ve-chi-dinh` | `agent-aeb7f41dbefe5efcf` | 1 commit chưa vào main, không PR |
| 0.64 | 2026-10-08 | `claude/hao-nam-vi-tri-so-do` | `login-facility-selection-cd0d0c` | 1 commit chưa vào main, không PR |
| 0.05 | 2026-10-06 | `claude/tai-kham-dich-vu-da-ngung` | `xac-nhan-van-de-f65d40` | 1 commit chưa vào main, không PR |
| 0.03 | 2026-10-16 | `claude/doi-tac-mo-lai-phong` | `goofy-spence-da7eae` | 12 commit chưa vào main, không PR |
| 0.03 | 2026-10-06 | `claude/patient-qr-scan-feature-9b4b4d` | `patient-qr-scan-feature-9b4b4d` | 1 commit chưa vào main, không PR |
| 0.03 | 2026-10-06 | `claude/thiet-ke-da-co-so` | `mac-m4-pro-tuning-75a7dd` | 1 commit chưa vào main, không PR |
| 0.03 | 2026-10-01 | `claude/phat-hanh-mot-lenh` | `agent-a41bb6b53d1d0ede6` | 1 commit chưa vào main, không PR |

### 1.3 LƯU TRỮ — ứng viên gỡ sau khi duyệt (26)

| GB | Ngày | Nhánh | Thư mục | Lý do |
|---|---|---|---|---|
| 1.06 | 2026-10-12 | `codex/bao-cao-giao-dien` | `Dr4Women-MacMini` | PR #397 đã đóng/merge, nhánh còn trên remote |
| 0.88 | 2026-10-16 | `claude/giam-cham-trang-chu-quan-ly-khach` | `agent-a577866d1c3698328` | nhánh đã vào main, PR #481 |
| 0.88 | 2026-10-16 | `claude/phan-hoi-thuoc-hien-o-bang-khach` | `agent-a03525bfda092ffe1` | nhánh đã vào main, PR #483 |
| 0.88 | 2026-10-16 | `claude/quay-thuoc-de-thay-don-cu` | `agent-a2ea68eec0602a313` | nhánh đã vào main, PR #482 |
| 0.87 | 2026-10-16 | `claude/form-tao-khach-them-email` | `agent-abf8b23f9072ad2cd` | nhánh đã vào main, PR #480 |
| 0.87 | 2026-10-15 | `claude/g8b-man-duyet-nhap` | `agent-a1c59380f60889519` | nhánh đã vào main |
| 0.87 | 2026-10-15 | `claude/sua-chi-dinh-mat` | `agent-a3bc1c1fce33c42fe` | nhánh đã vào main |
| 0.87 | 2026-10-14 | `claude/viec-ton-hoan-thuoc-nut` | `g4d-financial-reconciliation-medicine-e918ee` | nhánh đã vào main |
| 0.87 | 2026-10-14 | `claude/g6-kiem-ke-giao-dien` | `gifted-turing-3f89d3` | nhánh đã vào main |
| 0.87 | 2026-10-16 | `claude/bao-cao-hang-hoa-link-kiem-ke` | `agent-adf7c5017fcef0a92` | nhánh đã vào main |
| 0.87 | 2026-10-14 | `claude/g7-kho-quay` | `stoic-lehmann-d75eec` | nhánh đã vào main |
| 0.86 | 2026-10-15 | `claude/luu-ho-so-sang-quan-ly-khach` | `agent-ac488ba4fca50da3b` | nhánh đã vào main, PR #475 |
| 0.84 | 2026-10-14 | `claude/g5b-thue-gtgt` | `laughing-galileo-d0106f` | nhánh đã vào main |
| 0.84 | 2026-10-14 | `g8a-lam` | `magical-hawking-1e21cd` | nhánh đã vào main |
| 0.84 | 2026-10-15 | `claude/goi-xac-nhan-lich-dat-ho-a` | `agent-af86b25bc8cb77513` | nhánh đã vào main, PR #476 |
| 0.83 | 2026-10-08 | `(detached)` | `inspiring-nightingale-73990b` | nhánh đã vào main |
| 0.83 | 2026-10-07 | `(detached)` | `agent-a9db6b4cc549454a2` | nhánh đã vào main |
| 0.82 | 2026-10-02 | `(detached)` | `wt-dot4` | nhánh đã vào main |
| 0.82 | 2026-10-01 | `(detached)` | `wt-dot3` | nhánh đã vào main |
| 0.75 | 2026-10-16 | `claude/vat-tu-hang-loat-theo-loai` | `agent-aa385a3c66dc15c80` | nhánh đã vào main |
| 0.64 | 2026-10-16 | `claude/vai-ke-toan` | `agent-aed4fb9df363d796e` | nhánh đã vào main |
| 0.06 | 2026-10-01 | `(detached)` | `agent-afc37e03f4b75157f` | nhánh đã vào main |
| 0.03 | 2026-10-14 | `gop-staging-1410` | `gop-staging-1410` | nhánh đã vào main |
| 0.03 | 2026-10-14 | `claude/form-data-loss-tab-switch-c0673c` | `check-issue-ad88cd` | nhánh đã vào main |
| 0.03 | 2026-10-14 | `claude/patient-count-by-location-789b11` | `patient-count-by-location-789b11` | nhánh đã vào main |
| 0.03 | 2026-10-14 | `antigravity/vat-tu-kho` | `wt-antigravity-g8a` | nhánh đã vào main |

### 1.4 GIỮ (không động) — tóm tắt

1 tệp: 12, có tiến: 9, 2 tệp: 3, 4 tệp: 3, checkout CHUNG: 1, PR #502: 1, 13 tệp: 1, PR #414: 1 — tổng 28.0 GB.

## 2. Nhánh remote chưa vào main

PR còn mở **38** · PR đã đóng/merge **8** · **mồ côi 27** (không PR). Ngoài ra **355** nhánh đã vào main (xoá được, mỗi nhánh gần như không tốn đĩa).

### 2.1 PR đã đóng/merge nhưng nhánh còn lại (8)

| Ngày | Nhánh | Commit chưa vào main | PR | Người | Commit cuối |
|---|---|---|---|---|---|
| 2026-08-17 | `hoan-tac-dong-bo-chip` | 1 | #139 | Quang | Hoàn tác xong mà chip danh sách vẫn kể chuyện cũ — 6 overlay |
| 2026-08-18 | `rut-lai-ngoai-luot` | 3 | #141 | Quang Dang | Lối rút dự phòng phải NHÌN THẤY được — đổi sang tông cảnh bá |
| 2026-08-18 | `tra-lai-gach-ngang-hoan-tac` | 1 | #140 | Quang Dang | Hoàn tác phải còn dòng gạch ngang — PR 139 lọc nhầm từ nguồn |
| 2026-08-19 | `them-tai-lieu-giai-thich-code` | 1 | #142 | Quang Dang | Tài liệu giải thích code từ A tới Z — 8.317 dòng, 16 phần |
| 2026-08-20 | `them-bang-dieu-khien` | 1 | #143 | Quang Dang | Bảng điều khiển terminal: suc-khoe.sh — một lệnh xem hết |
| 2026-08-21 | `claude/charming-mcclintock-d227f5` | 2 | #153 | Quang | Bỏ bầu-tab-chủ: Web Locks không tồn tại ở nơi cần nó |
| 2026-08-21 | `claude/sharp-bouman-ed84b4` | 1 | #150 | Quang | Caddy câm suốt lúc trang treo — thêm access log JSON để phân |
| 2026-10-12 | `codex/bao-cao-giao-dien` | 2 | #397 | Quang | feat: báo cáo cuối ngày gọn cho quản lý duyệt |

### 2.2 Mồ côi — không PR, chưa vào main (27)

| Ngày | Nhánh | Commit chưa vào main | PR | Người | Commit cuối |
|---|---|---|---|---|---|
| 2026-09-16 | `claude/vps-domain-viettel-setup-9ccbc3` | 1 |  | Quang | Dựng lại toàn bộ trên VPS mới + nối Viettel Storage làm bản  |
| 2026-09-21 | `codex/auto-lot-from-main` | 3 |  | Quang | fix(dashboard): đổi nhãn hiển thị NURSE_ULTRASOUND thành Điề |
| 2026-09-21 | `hotfix/prod-rx-auto-lot` | 5 |  | Quang | fix(dashboard): đổi nhãn hiển thị NURSE_ULTRASOUND thành Điề |
| 2026-09-21 | `hotfix/prod-rx-simple-payment` | 2 |  | Quang | style(tests): satisfy backend ruff checks |
| 2026-09-23 | `claude/7-phieu-kh-m-forms-0dc921` | 1 |  | Quang | feat(phieu-kham): bảy phiếu khám làm dữ liệu trên Form Engin |
| 2026-09-28 | `claude/cskh-dat-lich` | 1 |  | Quang | fix(ky-nang): CSKH có Đặt lịch + Thêm bệnh nhân, Lễ tân có Đ |
| 2026-09-28 | `claude/doi-vai-nhan-su` | 1 |  | Quang | chore(ops): script chuyển vai một nhân sự (đổi tên đăng nhập |
| 2026-09-30 | `feature/ops-traffic-report` | 2 |  | Quang | feat(ops): thay GoAccess bang dashboard thuan Dr4Women giao  |
| 2026-09-30 | `luu/auto-lot-2109` | 4 |  | Quang | wip(luu-tru): việc dở 21/09 trên codex/auto-lot-from-main —  |
| 2026-10-01 | `claude/phat-hanh-mot-lenh` | 1 |  | Quang | WIP(phat-hanh): cấu hình công khai dashboard nạp LÚC CHẠY (m |
| 2026-10-06 | `claude/dong-bo-mat-khau-gotrue` | 1 |  | Quang | WIP đồng bộ mật khẩu GoTrue → app_credential (phương án A) — |
| 2026-10-06 | `claude/patient-qr-scan-feature-9b4b4d` | 1 |  | Quang | WIP kế hoạch quét QR khách + khách mới tự khai (đã chốt 4/5  |
| 2026-10-06 | `claude/tai-kham-dich-vu-da-ngung` | 1 |  | Quang | WIP tái khám dịch vụ đã ngừng: báo rõ + mở ô chọn dịch vụ (c |
| 2026-10-06 | `claude/thiet-ke-da-co-so` | 1 |  | Quang | WIP thiết kế đa cơ sở + phòng khám đối tác (ADR 0015, 0016)  |
| 2026-10-08 | `claude/hao-nam-vi-tri-so-do` | 1 |  | Quang | scripts: vị trí lịch làm việc Hào Nam theo sơ đồ 4 tầng (Tuy |
| 2026-10-09 | `claude/ket-qua-dieu-tri-ve-chi-dinh` | 1 |  | Quang | WIP (chưa test, chưa CI): kết quả điều trị như CLS + lượt Đi |
| 2026-10-09 | `dot/0910-giamsat` | 1 |  | Quang | Thử staging: main + PR #391 (trung tâm giám sát AI) |
| 2026-10-09 | `dot/0910-nhe` | 3 |  | Quang | Đợt 0910-nhe: gộp claude/dat-lich-khung-dang-chay-0910 |
| 2026-10-12 | `codex/thu-ngan-ngay-truc` | 1 |  | Quang | feat: giới hạn thu ngân theo lịch trực |
| 2026-10-13 | `codex/staging-1310-405-406-407` | 1 |  | Quang | chore: gop staging 1310 them khach cho goi dat lich |
| 2026-10-14 | `claude/g4d-test-hoan-thuoc-cheo` | 3 |  | Quang | docs: sinh lại BAN-DO-CODE |
| 2026-10-16 | `claude/doi-tac-chung-khung-phong` | 8 |  | Quang | feat(đối tác): /doi-tac dùng CHUNG khung phòng dịch vụ + sửa |
| 2026-10-16 | `claude/phong-doi-tac-luong-chung` | 1 |  | Quang | feat(đối tác): Phòng đối tác chạy chung luồng phòng; /doi-ta |
| 2026-10-16 | `gop-staging-1410m` | 6 |  | Quang | docs(runbook 16/10): 29 migration; hai script dữ liệu đối tá |
| 2026-10-17 | `claude/mo-phong-quy-doi-tra` | 22 |  | Quang | test(kho): tài khoản thử chỉ-xem kho (fixture) + bài HTTP va |
| 2026-10-17 | `claude/sua-nho-1710` | 2 |  | Quang | test(agent giám sát): bỏ trần 200 dòng trong riêng file test |
| 2026-10-17 | `dot/1710-kho` | 14 |  | Quang | docs(runbook): cập nhật kiểm thêm trên local (mô phỏng 120 h |

### 2.3 PR còn mở — giữ (38)

| Ngày | Nhánh | Commit chưa vào main | PR | Người | Commit cuối |
|---|---|---|---|---|---|
| 2026-08-21 | `huong-dan-https` | 1 | #151 | Quang Dang | Chưa có tên miền — đó là lý do gốc của HTTP trần, không phải |
| 2026-08-21 | `moc-gio-kham-le-tan` | 4 | #144 | Quang Dang | API nuốt mất ba khoá thứ tự gọi — response_model lọc im lặng |
| 2026-09-18 | `claude/fix-ky-khoa-kham-xong` | 1 | #169 | Quang | Ký bệnh án không còn khoá luồng khám: vẫn "Khám xong" và thu |
| 2026-09-19 | `claude/chatgpt-review-handoff` | 1 | #170 | Quang | Tài liệu bàn giao cho external review (ChatGPT): HANDOFF, MA |
| 2026-09-28 | `claude/lich-bs-linh` | 3 | #242 | Quang | chore(quyen): bác sĩ mới chép đúng 8 quyền đang dùng của bác |
| 2026-10-01 | `antigravity/e2e-luong-chinh` | 7 | #306 | Quang | test(e2e): thêm luồng 6 hoàn tác (fixme flaky ui) |
| 2026-10-06 | `claude/an-luot-cu-man-theo-ngay` | 1 | #349 | Quang | Ẩn lượt hồ sơ cũ Notion ở các màn vận hành theo ngày |
| 2026-10-08 | `claude/bai-hoc-0810` | 1 | #372 | Quang | Docs: soát trước khi code — 7 bài học đợt mở Hào Nam (CLAUDE |
| 2026-10-09 | `claude/bao-cao-ca-cua-toi` | 3 | #393 | Quang | fix: báo tin hoàn tiền cho ca và giữ tương thích kiểm biên |
| 2026-10-13 | `claude/don-code-thua-1310` | 1 | #413 | Quang | chore: gỡ code Python không ai gọi (lớp ghi service_log đã n |
| 2026-10-13 | `claude/don-code-thua-1310-giao-dien` | 1 | #412 | Quang | chore(giao-dien): gỡ 3 component không ai render (RosterBell |
| 2026-10-13 | `claude/don-code-thua-1310-lib-mo-coi` | 1 | #411 | Quang | chore: gỡ lib/giao diện/script mồ côi (không ai import, khôn |
| 2026-10-13 | `claude/don-code-thua-1310-script` | 1 | #414 | Quang | chore(scripts): gỡ 2 script e2e chạy trên stack Supabase CLI |
| 2026-10-13 | `claude/giam-gia-bao-cao` | 1 | #410 | Quang | feat(báo cáo): ô Giảm giá ở khối Tài chính hiện số thật từ s |
| 2026-10-14 | `claude/do-thoi-gian-api` | 1 | #418 | Quang | feat(vận hành): ghi log request chậm + cảnh báo bể kết nối đ |
| 2026-10-14 | `claude/financial-reconciliation-medicine-man` | 2 | #419 | Quang | docs: bàn giao 14/10 — đợt dòng tiền/thuốc/vật tư/kế toán (D |
| 2026-10-14 | `claude/huong-dan-4-man-quan-ly` | 2 | #432 | Quang | docs: Kế toán là gói mẫu lego, không phải vai (luật 27/09 ch |
| 2026-10-15 | `claude/deploy-bat-buoc-ghim-sha` | 1 | #477 | Quang | fix(deploy): prod bắt buộc ghim SHA, không còn tự git pull;  |
| 2026-10-16 | `claude/customer-phone-sync-issue-849148` | 2 | #486 | Quang | test(xuất hoá đơn): test thuộc tính L2 theo luật mới — H = S |
| 2026-10-16 | `claude/nostalgic-solomon-ba377b` | 1 | #484 | Quang | fix: không ghép "BS " thừa trước tên bác sĩ đã có chức danh |
| 2026-10-16 | `claude/test-co-lap-1610` | 1 | #488 | Quang | test: cô lập 3 bài DB chập chờn khi CI chạy -n 4 --dist load |
| 2026-10-16 | `dot/1610-doi-tac` | 12 | #489 | Quang | fix(đối tác): Hoàn tác nhận mẫu ở Phòng đối tác mở lại lần l |
| 2026-10-17 | `claude/ke-hoach-on-dinh` | 1 | #494 | Quang | docs: kế hoạch ổn định + hợp nhất hệ thống (17/10) kèm số đo |
| 2026-10-17 | `claude/ke-hoach-quy-doi-don-vi` | 1 | #498 | Quang | docs(kế hoạch): quy đổi hộp ↔ gói lúc nhập + màn thuốc khách |
| 2026-10-17 | `claude/ke-hoach-sdt` | 5 | #501 | Quang | docs(kế hoạch SĐT): ghi 3 chỗ logic cũ phải nới khi nhận số  |
| 2026-10-17 | `claude/kho-don-vi-dan-duong` | 1 | #497 | Quang | feat(kho): nói rõ khi lô lệch đơn vị (nhập hộp, bán gói), kh |
| 2026-10-17 | `claude/kho-sua-muc-1` | 2 | #496 | Quang | test(sổ nợ): lấy giờ sự kiện từ DB, không từ đồng hồ máy Mac |
| 2026-10-17 | `claude/kiem-logic-kho-thuoc` | 5 | #495 | Quang | docs(bản đồ code): sinh lại BAN-DO-CODE.md cho 4 file test đ |
| 2026-10-17 | `claude/quy-doi-don-vi-luc-nhap` | 5 | #499 | Quang | fix(giao diện): hệ số rác thì ô quy đổi không hiện '= N' / ' |
| 2026-10-17 | `claude/s1-signout-local` | 1 | #490 | Quang | fix(đăng nhập): đăng xuất chỉ thu hồi phiên máy này, không đ |
| 2026-10-17 | `claude/s2-phieu-kham-notify` | 1 | #492 | Quang | perf(realtime): phiếu khám tự lưu không còn phát tin cho cả  |
| 2026-10-17 | `claude/s3a-patients-new-tu-tai` | 1 | #491 | Quang | perf(làm mới): /patients/new là màn tự tải — hết dựng lại fo |
| 2026-10-17 | `claude/thuoc-tra-cho-kiem` | 3 | #500 | Quang | test(vật tư): test hàng loạt dùng tiền tố VT_TEST_ để không  |
| 2026-10-17 | `codex/sdt-h0-ten-khach` | 1 | #502 | Quang | feat: thêm thành phần tên khách và trình bày số điện thoại c |
| 2026-10-17 | `codex/sdt-h1-hien-ten-khach` | 2 | #505 | Quang | feat: show customer identity across operations screens |
| 2026-10-17 | `codex/sdt-s1-ham-chung` | 4 | #503 | Quang | fix: giữ guard SĐT canonical cho lời gọi dịch vụ trực tiếp |
| 2026-10-17 | `codex/sdt-s2-tim-kiem` | 5 | #504 | Quang | fix: tìm SĐT theo dạng chuẩn ở các danh sách khách |
| 2026-10-17 | `dot/1710-on-dinh` | 7 | #493 | Quang | test(kho thuốc): bảng tạm drug_batch thêm cột noi_chua — hết |

## 3. Sao lưu và thư mục lớn trên Mac (chưa động — chờ chủ quyết)

| GB | Mục | Ghi chú |
|---|---|---|
| 24 | `ClinicAI-Backups/notion-import-20261005` | bản nhập Notion 05/10; còn cần không? |
| 5,5 | `ClinicAI-Backups/tep` | gương tệp đính kèm (keo-ve) — thường phải GIỮ |
| 5,4 | `ClinicAI-Backups/repo-truoc-khi-go-min` | bản repo trước lần dọn mìn — cất ra ổ ngoài? |
| 1,6 | `ClinicAI-Backups/ban-sao` | sao lưu DB hằng đêm — GIỮ (chính sách giữ 90 ngày) |

## 4. VPS (đã đo 17/10, chỉ đọc)

| Mục | Cỡ | Ghi chú |
|---|---|---|
| `/home/clinicai/lich-su-notion` | 4,2 GB | nhập Notion xong? còn bản trên Mac |
| `/home/clinicai/backups` | 4,7 GB | chính sách giữ 2 ngày (15 phút) + 7 ngày (đêm) — kiểm có dư |
| `_cu` | 611 MB | thư mục cũ |
| `clinicai/.release-source-prod` | 843 MB, 29 bản | giữ vài bản gần nhất |
| Volume Docker không gắn container | 8 cái | liệt kê tên trước khi quyết |
| Tệp lẻ | 2 | `setup-kuma-before-pr399.patch`, `giamsat-cho-phat-hanh.caddy.da-go` |
| Đĩa | 40/48 GB (83%) | còn 8,4 GB — ngưỡng deploy staging cần ≥ 8 GB trống |
