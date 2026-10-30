# Runbook lên prod — đợt `dot/1610-doi-tac` (soạn 16/10/2026, CHƯA chạy)

Đợt tài chính (`dot/1610-tai-chinh`) đã lên prod 16/10 @25140241 — xem `RUNBOOK-LEN-PROD-DOT-1610.md`.
Đợt này = `main`@25140241 + luồng Phòng đối tác:

- Phòng đối tác chạy CHUNG luồng phòng: Sắp đến → Nhận → Bắt đầu → **Đã nhận mẫu** → Trả kết quả (có hoàn tác).
- Xếp tay / tự xếp (quầy, trưởng ca, đổi phòng, H4 sau thu) vào Phòng đối tác — ghép theo LOẠI việc:
  việc đối tác làm trọn ⇔ phòng `la_doi_tac`; việc thường không bao giờ vào phòng đối tác. Phòng đối tác không cần lịch trực.
- `/doi-tac` dùng CHUNG thành phần với phòng dịch vụ (thẻ khách, thẻ dịch vụ, khung tệp, khối Việc đối tác).
- Tài khoản vai Đối tác: thanh bên chỉ "Việc của đối tác"; thu hộ là ô số tiền TUỲ CHỌN, không vào tiền phòng khám.
- "LÀM Ở" ở bàn khám ghi "Phòng đối tác".

**Không migration.** Hai script DỮ LIỆU (đã chạy trên staging 16/10), chạy trên prod SAU deploy, trong `/home/clinicai/clinicai`:
```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/bat-lai-doi-tac-1610.sql
```
Kết quả mong đợi: node làm bên ngoài = 1 (chụp phim ngoài), dịch vụ đối tác tự lấy mẫu = 4 (HPV 40, HPV 16, Thinprep, Combo).
```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/go-dich-vu-thua-phong-doi-tac-1610.sql
```
Gỡ dịch vụ thường khỏi phòng đối tác, chỉ giữ dịch vụ đối tác; tự dừng nếu có dịch vụ mồ côi.
```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/go-dich-vu-doi-tac-khoi-phong-thuong-1610.sql
```
Chiều ngược lại: gỡ dịch vụ đối tác làm trọn (chụp phim ngoài, HPV/Thinprep) khỏi PHÒNG THƯỜNG — "mở hết
phòng" 01/10 gắn chúng vào mọi phòng, làm MRI vú không vào Phòng đối tác (bấm staging 16/10 bắt được).
Tự dừng nếu một dịch vụ không còn phòng đối tác nào làm được.

Các bước sao lưu → ghim SHA → deploy như `RUNBOOK-LEN-PROD-DOT-1610.md` (bỏ bước migration).
