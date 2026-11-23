---
name: len-prod
description: Soạn lệnh đưa code ClinicAI lên staging/prod trên VPS (soát SHA, sao lưu DB, diễn tập + áp migration, deploy-backend.sh, kiểm sau deploy), lệnh vận hành VPS hay dùng, kiểm sao lưu kéo về Mac. Dùng khi Tuyền nói deploy, lên prod, lên staging, merge đợt, áp migration prod, sao lưu, rollback, kiểm VPS.
---

# Đưa code lên máy chủ

Lệnh ghi lên VPS (merge, deploy, áp migration) **do Tuyền chạy; AI soạn sẵn lệnh**
— không để chữ mẫu `<…>` trong khối lệnh (Tuyền bấm Run nguyên văn): điền SHA thật,
chưa có thì nói rõ và dừng. Lệnh đưa người khác chạy trên VPS phải bọc
`ssh clinic-vps-moi '…'`.

**Nhịp lên:** theo `CLAUDE.md` QUY TRÌNH mục 5–6 — PR xanh gom đợt lên staging
(`scripts/deploy-staging.sh <nhánh đợt>` + áp migration DB staging, `docs/STAGING.md`),
người thật bấm theo kịch bản, ĐẠT → merge cả đợt → deploy prod **một lần** ghim đúng
SHA đã thử trên staging. Staging chỉ chạy một bản — deploy PR lẻ sẽ đè nhau.

## CI

- **CI chạy trên máy dev**, không trên GitHub (GitHub Actions hỏng thanh toán từ
  25/09/2026): `./scripts/ci-may.sh --bao-github` — sau khi commit + push, cây
  sạch. Nó chạy y hệt `ci.yml`: ruff · mypy · pytest · máy kiểm phạm vi phòng
  khám · tsc · eslint · test frontend · migration chạy thật (`--anh` để dựng
  thêm ảnh amd64). **Xanh mới được merge, xanh mới được deploy.**
- **Không có CD tự động.** Runner của VPS cũ đã chết; `cd.yml` đã gỡ (01/10).

## Deploy prod = làm tay trên VPS, ghim đúng SHA đã soát

1. **Soát:** `git fetch origin` rồi `git log --oneline HEAD..origin/main` — đọc
   từng commit (migration? commit lạ?), chốt **một SHA**. Soát và deploy là hai
   lệnh riêng, không nối `&&`.
2. Sao lưu database (lệnh bên dưới).
3. Có migration mới → **diễn tập trước** trên bản sao (worktree tách ở đúng SHA
   đó + container Postgres phụ nạp dữ liệu prod, áp thử, số dòng bảng chính
   không đổi; xong xoá **kèm volume** `docker rm -fv` — 52 volume bản sao từng
   treo vì thiếu `-v`), rồi mới áp thật + `NOTIFY pgrst`.
4. `git checkout -B main <sha-đã-soát>` — **không** fetch lại, **không**
   `origin/main` (30/09: phiên khác merge #291 kèm migration chen vào 5 phút
   giữa soát và deploy → prod lên bản chưa soát).
5. `DEPLOY_EXPECTED_SHA=<đúng SHA ở bước 4, đủ 40 ký tự> ./scripts/deploy-backend.sh prod`
   (đứng trên nhánh `main`, không detached). **Bắt buộc:** thiếu biến (mã 2), SHA
   rút gọn (mã 2), hoặc `HEAD` ≠ SHA (mã 1) là script dừng ngay; script không còn
   tự `git pull` (trước đó thiếu biến thì kéo commit mới hơn rồi deploy luôn — 01/10
   và LẶP 29/10). Lấy SHA từ bước 1 (`git rev-parse <sha-ngắn>` ở Mac), **không**
   tính bằng `git rev-parse HEAD` trên VPS. Mỗi lần deploy chụp mã nguồn bất biến
   theo SHA vào `.release-source-prod/<sha>` để rollback chạy đúng bản cũ.
   **Giờ khám:** thứ 2–6 16h–23h, thứ 7–CN 7h–23h (giờ VN) script dừng, mã 3,
   chưa dựng gì (20/11 deploy 16:23 giữa ca). Soạn lệnh thì ghi giờ được chạy ngay
   trên khối lệnh. Sửa khẩn không chờ được: thêm `DEPLOY_KHAN_LY_DO="<lý do ≥ 10 ký tự>"`
   đứng đầu lệnh — script in cảnh báo và ghi lý do vào mốc deploy (màn Ops).
   `CHO_PHEP_GIO_KHAM=1` chỉ có tác dụng với staging, không mở được prod.
   **Lùi bản bằng tay** (bản mới chạy được nhưng sai nghiệp vụ) cũng qua đúng
   cửa này: `git checkout -B main <SHA bản trước, 40 ký tự>` rồi
   `DEPLOY_EXPECTED_SHA=<cùng SHA>`; trong giờ khám kèm `DEPLOY_KHAN_LY_DO`.
   (Bản mới không khởi động được thì script TỰ lùi, không cần lệnh này.)
6. Kiểm: dòng `deployment verified at <sha>` **đúng SHA đã soát**; container api
   được tạo lại, log api 0 lỗi, `/health/su-kien` ok, 0 sự kiện kẹt.

- Khuôn chạy cả chuỗi: `~/Projects/ClinicAI-Backups/ban-giao-2909/deploy_3009_chung.sh`
  (trên Mac, chép lên VPS rồi chạy) — **thay `origin/main` trong đó bằng SHA đã soát**.
- Deploy dựng lại container nên người đang dùng thấy 502 khoảng một phút.
  `.release-source-prod/` giữ mọi bản (chưa tự dọn).

## Lệnh hay dùng

```bash
ssh clinic-vps-moi                                    # vào máy chủ
cd /home/clinicai/clinicai

# sao lưu — PHẢI kèm env như unit systemd; chạy trần thì thoát 1 im lặng
PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db \
  BACKUP_ENV_FILE=.env.prod CLINIC_BACKUP_DIR=/home/clinicai/backups/clinicai \
  ./scripts/backup-db.sh

CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh          # thử khô
CLINIC_DB_CONTAINER=clinicai_db ./scripts/apply-pending-migrations.sh --apply  # áp thật
docker exec clinicai_db psql -U postgres -c "NOTIFY pgrst, 'reload schema'"

# khuôn cho AI: điền SHA thật (40 ký tự) ở CẢ HAI dòng trước khi đưa Tuyền
git checkout -B main <sha-đã-soát>                   # KHÔNG origin/main
DEPLOY_EXPECTED_SHA=<sha-đã-soát> ./scripts/deploy-backend.sh prod   # 40 ký tự; ngoài giờ khám
CLINIC_ENV_FILE="$PWD/.env.prod" docker compose --env-file .env.prod -p clinicai_prod ps
```

## Sao lưu và máy Mac

Sao lưu trên VPS: mỗi 15 phút (`clinicai-backup-15p`, giữ 2 ngày) + đêm 02:15
(giữ 7 ngày) → Viettel CFS; Mac kéo về 0:30 và 6:30
(`~/Projects/ClinicAI-Backups/keo-ve.sh`) — bản sao phải nằm ở máy khác với thứ nó
sao lưu. Kiểm nhanh: `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` phải
"BÌNH THƯỜNG" (từng hỏng 12→27/09 vì script trỏ VPS cũ). Lịch trên VPS đều là
systemd timer (unit trong `scripts/systemd/`). Mac từng còn LaunchDaemon
`com.dr4women.*` cố dựng prod mỗi 5 phút: `launchctl list | grep dr4women` còn
thấy thì gỡ (cần sudo).
