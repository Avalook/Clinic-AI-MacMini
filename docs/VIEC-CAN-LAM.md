# Việc cần làm — gom mọi báo cáo soát (23/10/2026)

Đây là **thước đo duy nhất** cho đợt sửa tới. Không đọc lại từng báo cáo; cần chi tiết
thì theo mã nguồn ở cuối mỗi việc. Xong một việc thì gạch dòng và ghi số PR.

Code đã soát: `main` @ `00bde52` (prod chạy đúng bản này, kiểm 23/10).
Nguồn: #534 (tốc độ 23/10) · #526 tiền · #527 lego + quyền · #528 lịch + hành trình ·
#531 sự kiện + vận hành · #529 kho · #530 (trùng #534) · #494 (số đo prod 14–17/10) ·
#521 (`cau-hoi-tuyen.md`, `phat-hien.json`) · `DANG-LAM.md` 16/10 · `KIEM-TOAN-HE-THONG-2709.md` mục 6–7.

**Vài từ dùng bên dưới:**
- *Dựng lại trang*: máy chủ chạy lại cả trang (2 lần hỏi đăng nhập + 6–8 lần gọi API) rồi gửi về trình duyệt.
- *Tin SSE*: đường mở sẵn, máy chủ đẩy "bảng X vừa đổi" xuống trình duyệt để màn tự cập nhật.
- *N+1*: lấy danh sách N khách rồi hỏi database riêng cho từng khách — N lần đi về, nối đuôi nhau.
- *Migration*: tệp SQL đổi cấu trúc database; mọi thay đổi database phải đi qua nó.
- *Mức 0–3*: theo CLAUDE.md. Mức 3 = tiền, kho, quyền, migration, hạ tầng → kế hoạch ngắn Tuyền duyệt **trước**.

---

## Phần 1 — 10 việc quan trọng nhất

Xếp theo mức phòng khám bị ảnh hưởng thật.

### 1. Đông khách thì màn tự nháy, bấm gì cũng phải chờ
- **Phòng khám thấy:** "Tối đông, đang gõ thì màn giật, bấm nút phải đợi."
- **Gốc:** mỗi lần ai đó ghi, mọi tab đang mở bị dựng lại ~3 lần, vì worker sự kiện nghỉ cứng 1 giây giữa các vòng (`src/clinicai/worker.py:329-333`) và mọi màn thường nghe chung 41 bảng, kể cả bảng tự lưu phiếu khám 1,5 giây/lần (`src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:88-147`). Đo prod 14/10: 1 lần ghi = 9,8 lần dựng lại trang.
- **Sửa:** worker thức ngay khi có tin (PR-A). Mỗi màn chỉ nghe bảng nó vẽ, bỏ 3 bảng tự lưu khỏi tập dựng trang, đưa check-out / trưởng ca vào nhóm "màn tự tải" (PR-B). Nhịp hỏi 60 giây chỉ chạy khi SSE chết (PR-D).
- **Mức 2** (riêng #492 mức 3 vì có migration) · 3–4 PR · đã có: #491, #492 (phải đổi giờ migration). Nguồn: #534 C1–C5, C8 · #530 A1, A2, C1 · #494 G1, G2.

### 2. Mở trang nào cũng chậm, và chậm thêm mỗi ngày
- **Phòng khám thấy:** "Bàn khám, phòng gần như trống mà mở mất cả giây."
- **Gốc:** layout gọi `/phan-quyen/toi` ở mọi lần dựng trang. Hàm `CashierScopeService.days()` chạy một câu SQL cho **mỗi ngày trực từ trước tới nay** × 2 quầy với người không đứng quầy thu: ~200–500 câu, thêm ~2 câu mỗi ngày (`src/clinicai/services/cashier_scope_service.py:243-312`). Việc 1 nhân thẳng vào đây.
- **Sửa:** một câu lấy mọi ca của người đó, gom theo ngày bằng Python, giữ nguyên nghĩa; bỏ lần đọc `clinic.settings` thứ hai.
- **Mức 3** (chạm quyền, nhưng ~80 dòng, duyệt nhanh) · 1 PR (PR-I) · chưa có. Nguồn: #534 C3, Q12 · #530 D1, D3.

### 3. Quầy thu và check-out chậm; bấm Thu chờ ~7 giây
- **Phòng khám thấy:** "Thu xong phải đợi mấy giây mới gọi được khách tiếp; màn check-out tải lâu."
- **Gốc:** bảng quầy tính hoá đơn từng khách nối đuôi (N+1): 9–10 câu/khách + 3–5 câu/chỉ định → 300–2.000 câu mỗi lần tải (`src/clinicai/services/cashier_board_service.py:708-760` → `bill_service.py:853-981`). Nút Thu chờ hết 2 lượt tải bảng (`src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:338-399`). Check-out ~20–25 câu/lượt (`checkout_service.py:1051-1098`). Câu chọn khách `WITH v AS` trung bình 4,3 giây (`cashier_board_service.py:151-387`). Worker sổ nợ 5–9 nghìn câu mỗi 10 phút (`so_no_service.py:528-614`).
- **Sửa:** tách `hoa_don_con_no` thành "đọc gộp N lượt" + "hàm dựng dùng chung"; lệnh thu vẫn gọi đúng hàm ấy nên số trên màn = số lúc thu (PR-J). Rồi bảng quầy (K), phòng dùng chung (L), nút nhả ngay khi ghi xong (M), check-out (N), sổ nợ (O). Câu 4,3 giây chỉ sửa sau `EXPLAIN ANALYZE` trên staging local (S).
- **Mức 3** (lõi tiền) · 6–7 PR · chưa có. Nguồn: #534 Q1–Q6, K1, N1, Q4 · #530 B1, B4, D2.

### 4. Tiền khách trả có thể sai
- **Phòng khám thấy:** "Khách kêu trả tiền khám hai lần"; "két hụt sau khi hoàn tiền"; "hai màn báo cáo ra hai số."
- **Gốc:** (a) đã thu phí khám mặc định rồi tick "Dịch vụ khám" → đòi thêm đủ tiền, phí cũ không thành tiền thừa (`bill_service.py:880-926`, `tien_thua_service.py:72-83`); (b) hoàn tiền được trên phiếu đã huỷ → tiền ra hai lần (`hoan_tien_service.py:323-338`); (c) hộp Hoàn tác hiện số trước giảm giá (`QuayThuNgan.tsx:377`); (d) hai báo cáo dùng hai mốc ngày cho huỷ/hoàn (`bao_cao_cuoi_ngay_service.py:943-1006` vs `danh_sach_hoa_don_service.py:63-96`); (e) "Đánh dấu đã xuất MISA" dựng lại danh sách lúc bấm → sót hoá đơn (`hoa_don_misa_service.py:79-117`).
- **Sửa:** Tuyền chốt 6 câu ở #526 (A1, A2, C1, C2, B6, D4) và câu phí tái khám 150k/400k (#521 câu 1). Rồi mỗi lỗ một PR nhỏ kèm test bất biến tiền.
- **Mức 3** · 3–4 PR · đã có: #508 (chặn hoàn sau huỷ — chờ câu A2). Nguồn: #526 A1–A3, C1–C4, D1 · #521 câu 1–2.

### 5. Giao thuốc mà kho không trừ; màn kho không tự cập nhật
- **Phòng khám thấy:** "Bán Androgel rồi mà tồn không giảm"; "kho bên kia nhập rồi, màn tôi vẫn số cũ."
- **Gốc:** lô nhập theo "hộp", thuốc bán theo "gói" → lọc lô theo đơn vị không ra lô nào, giao thuốc ghi tiền mà không trừ kho (`src/clinicai/services/pharmacy_service.py:1092`); prod 110/160 lô lệch đơn vị (đo 16/10). Ba bảng `drug_batch`, `inventory_txn`, `phieu_kho` không có trigger báo tin; nhập lô không ghi sự kiện (`pharmacy_service.py:542`).
- **Sửa:** Tuyền duyệt kế hoạch quy đổi #498 (1 hộp = N gói lúc nhập) rồi làm. Thêm trigger + màn nghe 3 bảng, ghi sự kiện nhập lô (2 test chờ sẵn ở #529 sẽ chuyển xanh). Nạp tồn thật sau khi đơn vị đúng.
- **Mức 3** · 3 PR · đã có: #497 (chỉ báo đúng nguyên nhân), #498 (kế hoạch), #529 (test). Nguồn: `DANG-LAM.md` 16/10 · #529 · `KIEM-TOAN` 7.2.

### 6. Bấm nhầm thì không gỡ được, hoặc gỡ xong màn kẹt
- **Phòng khám thấy:** "Bấm nhầm Không đến là phải đặt lịch lại"; "hoàn tác check-in xong khách hiện 'Về giữa chừng', mất nút Check-in"; "hoàn tác bỏ chỉ định, kết quả không về bác sĩ."
- **Gốc:** hoàn tác bỏ chỉ định không dựng lại yêu cầu kết quả (`hoan_tac_service.py:824`); hoàn tác check-in để lại trạng thái sai (`tiep_don_service.py:151,163`, `booking_service.py:2813`); Không đến / Huỷ lịch không có đường khôi phục (`booking_service.py:324-425`); Bắt đầu khám, Không làm được, Miễn kết quả chưa có hoàn tác (`luot_kham_service.py:1874,2984`, `service_execution_service.py:648`). Trái CLAUDE.md mục 7.
- **Sửa:** làm 3.1 + 2.1 trước, rồi 1.1, rồi nhóm 3.2–3.4. Mỗi nhóm kèm test "hoàn tác rồi làm lại" và kịch bản bấm ở mọi màn liên quan. Khoá cứng thai kỳ, thuốc trả, khoản hoàn: chờ Tuyền chốt (#521 câu 3, #526 D4).
- **Mức 2** · 3 PR · chưa có. Nguồn: #528 1.1, 2.1–2.3, 3.1–3.4 · #526 D4 · #521 câu 3.

### 7. Người ngoài đọc được dữ liệu khách; tự xếp ca để vượt quyền
- **Phòng khám thấy:** không thấy gì — đó mới là chỗ nguy. "Tài khoản đối tác, tivi phòng chờ mở được danh sách khách, tiền, xét nghiệm."
- **Gốc:** PostgREST (`/rest/v1` — cổng đọc thẳng database của Supabase tự dựng, đang mở ra Internet) cho mọi tài khoản đã đăng nhập đọc bảng khách, tiền (`supabase/migrations/20260730000004_tenant_scoped_rls.sql:149-171`, `20260730000008_table_grants.sql:48-59`). Ai cũng tự xếp mình vào ca "Điều phối" được → thu/hoàn tiền dù đã tắt lego (`cashier_scope_service.py:386`, `payment_service.py:342`). Người lạ ghi được ảnh 8MB/lần lên đĩa (`src/dashboard/app/api/console/feedback/route.ts:17-41`).
- **Sửa:** khoá `/rest/v1`, chỉ chừa 2 bảng đăng nhập cần (#532). Cấm tự xếp mình vào ca Điều phối, tiền theo ca vẫn đòi lego. Kiểm phiên trước khi ghi đĩa.
- **Mức 3** · 3 PR · đã có: #532 (Tuyền chạy trước lệnh ACL chỉ đọc ở #527). Nguồn: #527 C1–C3, C7, B1 · `KIEM-TOAN` 7.2.

### 8. Sao lưu có thể dừng mà không ai biết; ảnh/video chỉ có một bản
- **Phòng khám thấy:** không thấy gì — cho tới ngày cần khôi phục.
- **Gốc:** khoá sao lưu là một thư mục; tiến trình bị giết giữa chừng thì khoá kẹt, mọi lần sau tự từ chối (`scripts/backup-db.sh:127-134`). Unit sao lưu không giới hạn giờ, không báo khi hỏng (`scripts/systemd/clinicai-backup*.service`); /ops hiện "không rõ" chứ không đỏ (`scripts/collect_ops_status.py:195-216`). Ảnh/video trên ổ CFS (ổ mạng Viettel gắn vào VPS) không có bản thứ hai, hợp đồng CFS ghi hết hạn 16/10 (`backup-db.sh:349-357`). Docker có thể bật API trước khi CFS gắn xong — ứng viên sự cố 14/10 (`docker-compose.yml:216-222`). Màn "Dọn dữ liệu thử" xoá cứng được cả khách thật sau khi gõ XOA (`don_du_lieu_thu_service.py:277`).
- **Sửa:** một PR script: khoá có hạn, `TimeoutStartSec` + `OnFailure`, /ops tô đỏ, canh gác kiểm tuổi bản sao. "Dọn dữ liệu thử" chỉ nhận khách có dấu thử. Ảnh/video: Tuyền chốt nơi đặt bản thứ hai + gia hạn CFS. Docker chờ CFS: kế hoạch mức 3.
- **Mức 2** (script) + **3** (hạ tầng) · 3 PR · đã có: #518 (nạp staging chết 2 đêm 20–21/10). Nguồn: #531 C1–C7 · `KIEM-TOAN` mục 6 câu 6, 7.2.

### 9. Người khác đã làm mà màn mình không đổi
- **Phòng khám thấy:** "Thu ngân thu rồi mà màn check-out vẫn báo chưa thu, phải F5."
- **Gốc:** trình duyệt tự nối lại SSE thì không bắt kịp quãng mất (`RealtimeRefresher.tsx:248-259`); bộ nghe của API nối lại không báo màn nào (`src/clinicai/core/change_broker.py:91-114`); hàng chờ 8 tin đầy thì bỏ tin (`change_broker.py:45,131-135`); gọi AI tóm tắt cuối ngày nằm ngay trong vòng giao tin, chặn chuông/hàng chờ tới 600 giây (`worker.py:290-329`, `agent_tom_tat.py:236-255`).
- **Sửa:** nối lại hoặc hàng đầy → gửi tin "không rõ bảng" để màn hỏi lại hết (PR-C, vài dòng mỗi bên). Tách gọi AI ra task riêng có giới hạn giờ.
- **Mức 2** · 2 PR · chưa có. Nguồn: #531 A1–A3 · #534 C6–C7 · #494 S3b.

### 10. Đang làm thì bị văng ra trang đăng nhập
- **Phòng khám thấy:** "Một người bấm Đăng xuất là máy khác dùng chung tài khoản cũng bị đá ra."
- **Gốc:** `signOut()` mặc định thu hồi phiên ở **mọi** máy (`src/dashboard/app/(auth)/login/actions.ts:50,61,70,97`). Log 14–17/10: 113 lần đăng xuất, 96 lần máy bị đá.
- **Sửa:** đổi sang `scope: "local"` — đã viết xong, có bài canh.
- **Mức 2** · 1 PR · đã có: #490 (kế hoạch 17/10 ghi "Xong" nhưng chưa vào `main`). Nguồn: #494 G5 · #530 A3.

---

## Phần 2 — Xử lý 56 PR đang mở

Đếm 23/10 có **56** PR mở (không phải 30). Tóm tắt: **24 nên merge · 20 nên đóng · 12 cần Tuyền quyết.**
"Chỉ .md" = không cần CI máy (CLAUDE.md). "Xung đột" = không merge thẳng được vào `main`.

**Nhóm trùng nhau:**
- **Bản đồ (5 bản lồng nhau):** #513 ⊂ #514 ⊂ #516 ⊂ #517 ⊂ #521 — mỗi PR chứa trọn PR trước. Trên `main` đã có `BAN-DO-CODE`, `BAN-DO-SUA`, `BAN-DO-DAY-NOI-LEGO`, `SITEMAP`, `GIAI-THICH-CODE`. Đề xuất: merge riêng #513 (bài kiểm thật), đóng #514/#516/#517, #521 để Tuyền chọn.
- **Sổ học:** #533 và #535 (bản 2). **Soát tốc độ:** #530 và #534. **Đợt 17/10:** #493 = #490 + #491 + #492.
- **SĐT:** chuỗi #501 → #502 → #503 → #504 → #505. **Đơn vị kho:** #497, #498, #529. **Test cô lập:** #488, #511. **Dọn code:** #411–#414.

| PR | Việc | Đề xuất | Lý do ngắn |
|---|---|---|---|
| #535 | Sổ học bản 2 | Cần Tuyền quyết | Muốn có sổ học thì giữ bản này (có `--kiem`); ~8k dòng sinh |
| #534 | Soát tốc độ 23/10 | Nên merge | Kho chi tiết cho việc 1–3; chỉ .md |
| #533 | Sổ học bản 1 | Nên đóng | Trùng #535, cũ hơn |
| #532 | Khoá `/rest/v1` | Cần Tuyền quyết | Mức 3: duyệt + chạy lệnh ACL chỉ đọc → staging (việc 7) |
| #531 | Soát khối 5 | Nên merge | Kho chi tiết việc 8–9; chỉ .md |
| #530 | Soát khối 1 tốc độ | Nên đóng | #534 mới hơn, đủ hơn |
| #529 | Soát kho + 2 test chờ | Nên merge | Có tệp test → chạy CI |
| #528 | Soát khối 3 | Nên merge | Kho chi tiết việc 6; chỉ .md |
| #527 | Soát khối 4 | Nên merge | Kho chi tiết việc 7; chỉ .md |
| #526 | Soát khối 2 | Nên merge | Kho chi tiết việc 4; chỉ .md |
| #524 | Nhắc lượt chưa Hoàn tất > 2 giờ | Nên merge | Tuyền đã duyệt 22/10; prod có 26 lượt kẹt |
| #522 | "Hôm nay" theo giờ VN + nhóm quyền tắt | Nên merge | Nhỏ; sửa `queue.py:104` |
| #521 | Bản đồ lớp "hiểu" | Cần Tuyền quyết | ~200k dòng, chứa luôn #513–#517; đề xuất chỉ giữ `cau-hoi-tuyen.md` + `phat-hien.json` |
| #520 | Giá: "sửa lần cuối" + nút Lịch sử | Nên merge | Sau #519 |
| #519 | Vết đổi giá | Nên merge | Không migration |
| #518 | Staging nạp ACL qua stdin | Nên merge | Gấp: nạp staging chết 2 đêm |
| #517 | Bản đồ v2 | Nên đóng | Nằm trọn trong #521 |
| #516 | Bản đồ web | Nên đóng | Nằm trọn trong #521 |
| #515 | Bàn giao 21/10 + kế hoạch dọn repo | Nên đóng | Phát hiện đã vào #512/#513; tệp này thay vai trò |
| #514 | BAN-DO-KHOI | Nên đóng | Nằm trọn trong #521 |
| #513 | Khai chủ bảng + bánh cóc ghi chéo | Nên merge | Không đổi hành vi; #527 kiểm khớp `main` |
| #512 | Chuông nhận chéo + sổ nợ nghe đối tác | Nên merge | Lỗi chuông treo thật |
| #511 | Cô lập 3 bài test đỏ ngẫu nhiên | Nên merge | Chỉ test |
| #508 | Chặn hoàn tiền sau huỷ phiếu | Cần Tuyền quyết | Chờ câu A2 (#526), rồi merge |
| #505 | SĐT: hiện tên khách mọi màn | Cần Tuyền quyết | Chờ duyệt #501; 78 commit sau `main` |
| #504 | SĐT: tìm theo dạng chuẩn | Cần Tuyền quyết | Như trên; xung đột |
| #503 | SĐT: hàm chung backend | Cần Tuyền quyết | Như trên; xung đột |
| #502 | SĐT: thành phần tên khách | Cần Tuyền quyết | Như trên |
| #501 | Kế hoạch SĐT (mức 3) | Cần Tuyền quyết | Duyệt hay bỏ cả chuỗi |
| #498 | Kế hoạch quy đổi hộp ↔ gói | Cần Tuyền quyết | Gốc việc 5 |
| #497 | Báo lô lệch đơn vị | Nên merge | Làm lại trên `main` (xung đột) |
| #494 | Kế hoạch ổn định 17/10 | Nên đóng | S1–S3a ở #490–#492; số đo đã chép vào đây |
| #493 | Gộp đợt 17/10 | Nên đóng | Xung đột; merge từng #490–#492 |
| #492 | Phiếu khám tự lưu không phát tin | Nên merge | Mức 3: đổi giờ migration bị trùng rồi lên staging |
| #491 | `/patients/new` tự tải | Nên merge | Nhỏ (việc 1) |
| #490 | Đăng xuất chỉ máy này | Nên merge | Việc 10 |
| #489 | Hoàn tác nhận mẫu đối tác | Nên merge | Lỗi còn trên prod; cập nhật theo `main` |
| #488 | Cô lập 3 bài DB | Nên đóng | Xung đột; mở lại chỉ khi `ci-may` còn đỏ đúng 3 bài này |
| #484 | Bỏ "BS " thừa | Nên đóng | `main` đã có `ten_bac_si` + `doctor-name.ts` |
| #477 | Deploy prod bắt buộc ghim SHA | Nên merge | `main` vẫn tự `git pull` khi thiếu biến; mức 3 nhỏ |
| #432 | Hướng dẫn quản lý cho chị Hà | Nên merge | Chỉ .md; Tuyền lướt lại tên màn |
| #419 | Kế hoạch đợt 14/10 | Nên đóng | Đợt đã qua |
| #418 | Log request chậm + bể 20 | Nên đóng | `main` đã có `core/telemetry.py` + chỉnh bể qua biến môi trường |
| #414 | Gỡ 2 script e2e | Nên đóng | Hai script đã không còn trên `main` |
| #413 | Gỡ code Python mồ côi | Nên merge | Gom #411–#413 làm lại thành 1 PR trên `main` |
| #412 | Gỡ 3 component mồ côi | Nên merge | Như trên (đang xung đột) |
| #411 | Gỡ lib/script mồ côi | Nên merge | Như trên |
| #393 | Báo cáo ca của tôi | Nên đóng | WIP dừng 09/10, chưa CI, xung đột |
| #372 | Bài học đợt Hào Nam | Cần Tuyền quyết | Nội dung đúng nhưng sửa `CLAUDE.md` |
| #349 | Ẩn lượt Notion cũ ở màn theo ngày | Cần Tuyền quyết | Còn cần không? Xung đột, phải làm lại |
| #306 | E2E Playwright 6 luồng | Nên đóng | 509 commit sau `main`, test chập chờn |
| #242 | Điền tên BS lịch 28/09 | Nên đóng | Lịch sử git cũ, không chung gốc với `main` |
| #170 | Bàn giao external review | Nên đóng | Như trên |
| #169 | Ký bệnh án không khoá luồng | Nên đóng | Như trên |
| #151 | HTTP trần vì chưa có tên miền | Nên đóng | Như trên; đã có tên miền |
| #144 | Quầy lễ tân hai nút tròn | Nên đóng | Như trên |

---

## Phần 3 — Băn khoăn của Tuyền → câu hỏi rõ

| Băn khoăn | Nó là việc nào | Có bằng chứng chưa / cần đo gì |
|---|---|---|
| **Chậm** | Việc 1, 2, 3 (và 9) | **Có.** Prod 14/10: p95 1,5s, p99 3,1s; 1 lần ghi = 9,8 lần dựng lại trang; câu quầy thu 4,3s. Đo lại trước/sau mỗi PR bằng cùng lệnh ở #494 mục 7 |
| **Tuỳ biến chưa cao** | Không nằm trong 10 việc | **Chưa có bằng chứng** phòng khám bị cản hằng ngày. #531 ghi: cấu hình Dr4Women nằm trong code, giờ ca chỉ theo phòng khám chứ không theo cơ sở, SĐT/tên in không sửa trên màn. Cần đếm: 5 lần gần nhất phải sửa code chỉ vì đổi cấu hình |
| **Lego chưa hữu hiệu** | Việc 7 (phần quyền) | **Có**, ở quyền: tự xếp ca Điều phối vượt lego; tắt hết lego thì vai cũ quay lại (#527 C7–C9). Phần ranh giới khối (97 chỗ ghi chéo, bảng `visit` bị 11 tệp ghi) là nợ kiến trúc, **chưa thấy lỗi phòng khám** do nó; #513 chặn không cho nặng thêm |
| **SQL chưa tốt** | Việc 2, 3 | **Có** ở N+1 và câu 4,3s. Phần còn lại (so `id::text` ~41 chỗ, `lich_vuot_suc_chua()` quét mọi phòng khám) cần `EXPLAIN ANALYZE` trên staging local trước khi sửa |
| **Logic chưa ổn** | Việc 4, 5, 6 | **Có**, cụ thể từng dòng code ở trên. Đa số cần Tuyền chốt nghiệp vụ trước (6 câu tiền, quy đổi đơn vị, khoá cứng) |
| **Dung lượng / luồng chưa tốt** | Một phần việc 8, 9 | **Một phần.** Luồng: AI tóm tắt chặn vòng sự kiện (việc 9). Dung lượng: `event_delivery` không bao giờ dọn, CFS giữ ×N bản 15 phút (#531 A4, C5). **Chưa có số đo ổ.** Cần: `df -h`, 10 bảng lớn nhất (`pg_total_relation_size`), số dòng `event_delivery`, tổng dung lượng CFS |

---

## Phần 4 — Thứ tự làm 4 tuần tới

Mỗi việc: một nhánh, một worktree, một PR ≤ ~400 dòng (không tính test, migration, tệp sinh),
dải giờ migration và cổng 32xx/82xx riêng. Mức 3 = viết kế hoạch trong PR draft, Tuyền duyệt rồi mới code.

**Tuyền làm ngay đầu tuần 1** (không code, mở khoá cho các tuần sau):
1. Dọn PR theo Phần 2: đóng 20 PR, merge các PR "nên merge" không cần CI (chỉ .md).
2. Chốt 6 câu tiền (#526) + phí tái khám (#521 câu 1) + quy đổi đơn vị (#498) + khoá cứng (#521 câu 3).
3. Chạy lệnh ACL chỉ đọc ở #527 và 4 lệnh chỉ đọc ở cuối #531; trả lời câu gia hạn CFS.

| Tuần | Việc | Song song được? | Chờ Tuyền duyệt? |
|---|---|---|---|
| **1** | **Việc 10** — merge #490 (+ #491, #522, #518, #512, #489, #513 cùng một lượt CI) | Có | Không |
| | **Việc 1** — PR-A (worker thức ngay) ‖ PR-B (bảng theo màn) | A và B khác tệp, song song | Không (mức 2) |
| | **Việc 8** — PR script sao lưu (khoá có hạn, timeout, /ops đỏ) | Có | Không (mức 2) |
| **2** | **Việc 2** — PR-I (`days()` một câu) | Có | **Có** (mức 3, kế hoạch rất ngắn) |
| | **Việc 7** — #532 khoá `/rest/v1`; PR vá ca Điều phối | Có | **Có** (mức 3) |
| | **Việc 4** — #508 + PR phí khám hai lần + PR hộp Hoàn tác | Có, khác tệp | **Có** (cần câu trả lời tiền) |
| | → **Đợt staging 1** cuối tuần 2: mọi PR tuần 1–2, đo lại số dựng trang | | |
| **3** | **Việc 3 (phần 1)** — PR-J (đọc gộp hoá đơn) ‖ PR-L (phòng dùng chung) ‖ PR-M (nút Thu) | J, L, M song song | **Có** (mức 3) |
| | **Việc 6 (phần 1)** — PR 3.1 (kết quả về bác sĩ) + 2.1 (hoàn tác check-in) | Có | Không (mức 2) |
| | **Việc 9** — PR-C (tin "không rõ bảng") + tách gọi AI | Sau PR-B (cùng tệp `RealtimeRefresher.tsx`) | Không (mức 2) |
| **4** | **Việc 3 (phần 2)** — PR-K (bảng quầy) → PR-N (check-out) | K và N chờ J | **Có** |
| | **Việc 5** — PR quy đổi đơn vị; PR trigger + sự kiện kho | Có | **Có** (cần duyệt #498) |
| | **Việc 6 (phần 2)** — PR 1.1 (khôi phục Không đến / Huỷ lịch) | Có | Không |
| | → **Đợt staging 2** cuối tuần 4 → đạt thì merge cả đợt, deploy prod một lần | | |

Để sau tuần 4: việc 3 phần cuối (PR-O sổ nợ, PR-S câu 4,3s sau EXPLAIN), Docker chờ CFS
(mức 3 hạ tầng), nhóm hoàn tác 3.2–3.4, chuỗi SĐT nếu Tuyền duyệt #501.
