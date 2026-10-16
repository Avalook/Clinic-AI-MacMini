# Runbook lên prod — đợt `gop-staging-1410m` (soạn 16/10/2026, CHƯA chạy)

**Điều kiện bắt đầu (Tuyền nói "lên prod" + đủ ba thứ):** CI máy của đợt xanh · Tuyền đã bấm xong kịch bản staging
(`docs/HUONG-DAN-BAM-THU-NOTION-1610.md`) · các câu "Cần Tuyền quyết" ở cuối đã chốt.
Lệnh GHI lên VPS (merge, sao lưu, áp migration, deploy) **do Tuyền chạy**; chạy ngoài giờ khám (sau 21h) vì deploy dựng lại
container, người đang dùng thấy 502 khoảng một phút.

## 0. Đợt này gồm
~211 commit, ~60 nhánh (G3b mã vạch, G4 dòng tiền, G5 kế toán/thuế/hoá đơn công ty/MISA, G6 kiểm kê ca, G7 tách kho/quầy,
G8 vật tư + duyệt nhập, G9 Bio ở chỉ định, bán theo đơn + phản hồi thuốc, gọi xác nhận mọi lịch đặt hộ, email khách,
7 PR giảm chậm, sửa lỗi, vai Kế toán, Phòng đối tác chạy chung luồng phòng). **29 migration mới**:

`20261010100000` `20261010100001` `20261010200000` · `20261014110000` `…130000` `…130002` `…135000` `…140000` `…147000`
`…148000` `…149000` `…150000` `…155000` `…156000` `…157000` `…160000` `…170000` `…180000` `…180100` `…180101` `…181000`
`…181100` `…190000` `…200000` `…200100` `…220000` · `20261015110000` · `20261016300000` `20261016400000`.
Hai nhóm thay đổi có hiệu ứng thấy ngay: **view `v_viec_cskh`** (mọi lịch đặt hộ thành việc "Gọi xác nhận lịch") và
**cột/ràng buộc kho** (`drug_batch.noi_chua`, công tắc `tach_kho_quay` mặc định TẮT → quầy bán như cũ).

## 1. Soát (trên Mac, hai lệnh riêng — KHÔNG nối `&&`)
```bash
git fetch origin
```
```bash
git log --oneline origin/main..origin/gop-staging-1410m
```
Đọc từng nhóm commit; chốt **một SHA** (SHA đầu nhánh đợt sau khi CI xanh). Nếu `main` có commit mới ngoài đợt thì dừng và báo.

## 2. Số liệu đếm TRƯỚC khi áp (chỉ đọc, trên VPS)
Số việc "Gọi xác nhận lịch" sẽ bật cùng lúc khi áp `20261015110000` (không backfill):
```bash
ssh clinic-vps-moi "docker exec clinicai_db psql -U postgres -d postgres -Atc \"SELECT count(*) FROM appointment a WHERE a.status NOT IN ('CANCELLED','NO_SHOW','DOCTOR_DECLINED','COMPLETED','CHECKED_IN') AND upper(coalesce(a.booking_channel,'')) <> 'WALK_IN' AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AND (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + 7 AND NOT EXISTS (SELECT 1 FROM tuong_tac_cskh t WHERE t.appointment_id = a.id AND t.loai = 'XAC_NHAN_LICH' AND t.huy_luc IS NULL)\""
```
Ghi con số vào PR. Nếu lớn (hàng chục) và Tuyền chưa chốt cách tính hạn → hoãn migration này.

## 3. Merge đợt vào `main` (Tuyền bấm trên GitHub)
Mở PR `gop-staging-1410m` → `main`, kiểm CI máy xanh, merge **bằng merge commit** (giữ lịch sử). Rồi trên Mac:
```bash
git fetch origin
```
```bash
git rev-parse origin/main
```
Giá trị in ra là SHA đã soát (gọi `SHA_PROD`). **Không** dùng `origin/main` ở bước deploy (30/09: commit chen giữa soát và deploy).

## 4. Trên VPS — sao lưu, diễn tập, áp (theo skill `len-prod`)
```bash
ssh clinic-vps-moi
```
```bash
cd /home/clinicai/clinicai
```
Sao lưu (phải kèm env như unit systemd):
```bash
PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db BACKUP_ENV_FILE=.env.prod CLINIC_BACKUP_DIR=/home/clinicai/backups/clinicai ./scripts/backup-db.sh
```
Diễn tập 29 migration trên bản sao (worktree tách ở SHA_PROD + Postgres phụ nạp dữ liệu prod; xong `docker rm -fv`; số dòng
bảng chính không đổi). Rồi thử khô và áp thật:
```bash
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh
```
```bash
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh --apply
```
```bash
docker exec clinicai_db psql -U postgres -c "NOTIFY pgrst, 'reload schema'"
```
Hai script DỮ LIỆU đối tác (đã chạy trên staging 16/10 — kết quả: 1 node làm bên ngoài · 4 dịch vụ đối tác tự lấy mẫu ·
mỗi phòng đối tác gỡ 87 dịch vụ thường, còn 25). Chạy SAU migration, trên VPS trong `/home/clinicai/clinicai`:
```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/bat-lai-doi-tac-1610.sql
```
```bash
docker exec -i clinicai_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 < scripts/go-dich-vu-thua-phong-doi-tac-1610.sql
```
Script thứ hai tự dừng (không đổi gì) nếu có dịch vụ sẽ không còn phòng thường nào làm.

## 5. Deploy ghim SHA
```bash
git fetch origin
```
LỆNH DƯỚI CHƯA CHẠY ĐƯỢC cho tới khi PR đợt được merge: Claude sẽ điền SHA thật (ở bước 3) vào đây và đổi khối thành
lệnh chạy được. Trong khối chỉ có chữ `SHA_PROD` = chưa có SHA → **dừng, đừng chạy**.
```text
git checkout -B main SHA_PROD
```
```bash
./scripts/deploy-backend.sh prod
```

## 6. Kiểm sau deploy
```bash
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod ps
```
- Container api được tạo lại, log api 0 lỗi, `/health/su-kien` ok, 0 sự kiện kẹt.
- Mở `https://dr4women.io.vn/home` và `/customers`: tải trang đo lại (staging: Trang chủ ~0,6 s, Quản lý khách ~0,24 s phía backend).
- `systemctl list-timers | grep clinicai` còn đủ timer; `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` (trên Mac) vẫn BÌNH THƯỜNG.

## 7. Việc làm tay sau khi lên (trên màn, Tuyền)
1. **Tắt cơ sở Kim Ngưu trên prod** (đang BẬT) và dọn hàng chờ cũ; đổi cơ sở mặc định; kiểm báo cáo không còn hiện cơ sở đã ngừng.
2. Bật công tắc **Nhận khách tại phòng** (`/settings/day-noi`) lúc vắng khách (đã quyết 15–16/10); đánh ★ phòng chuyên nếu muốn.
3. Cấp quyền (`/phan-quyen`): **Duyệt vật tư** cho Trưởng ca/Quản lý; **Quản lý khách hàng** cho vai cần thấy hồ sơ vừa tạo.
4. **Chưa** bật `tach_kho_quay` và **chưa** đặt cờ "Cần duyệt nhập" cho mặt hàng nào cho tới khi bấm thử đủ trên staging.
5. Tạo tài khoản kế toán (chị Hoài) và cấp lego Kế toán.

## 8. Hoàn tác nếu hỏng
- Mã: `git checkout -B main SHA_TRUOC_DO` rồi `./scripts/deploy-backend.sh prod` (SHA trước đó ghi lại ở bước 5, trước khi checkout).
- Migration đều **chỉ thêm** (cột/bảng/view/hàm mới, `IF NOT EXISTS`): để nguyên được; riêng view `v_viec_cskh` quay về bản
  `20260930700000` bằng migration đảo (soạn sẵn nếu cần).
- Dữ liệu: khôi phục từ bản sao lưu bước 4 chỉ khi xác nhận hỏng dữ liệu (sau khi báo Tuyền).

## Cần Tuyền quyết trước khi chạy
1. Cách tính hạn cho các việc "Gọi xác nhận lịch" tồn (hạn từ ngày lên prod hay để quá hạn).
2. Công thức **doanh thu thuần** với kế toán (Notion tự mâu thuẫn).
3. Duyệt kế hoạch `docs/KE-HOACH-HAM-SUC-CHUA.md` (làm trong đợt này hay đợt sau).
4. Có đưa **Nhận khách tại phòng** lên cùng đợt không.
