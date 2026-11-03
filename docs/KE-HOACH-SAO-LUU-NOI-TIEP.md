# Kế hoạch: sao lưu nối tiếp (bản đầy đủ + nhật ký thay đổi)

Mức 3 — Tuyền duyệt 03/11/2026; code ở nhánh `claude/sao-luu-noi-tiep`, đã thử local, chưa lên staging. Soạn từ số đo prod cùng ngày.

## Vì sao

Hiện `backup-db.sh` dump **đầy đủ** mỗi 15 phút (7h–22h) và mỗi đêm. Mỗi bản ~55 MB nén
và to thêm ~50 MB mỗi tháng theo database.

| Đo 03/11 | Số |
|---|---|
| Database (`pg_database_size`) | 642 MB |
| Nhật ký thay đổi (`pg_stat_wal`, từ 16/09) | ~207 MB/ngày chưa nén |
| Bản sao lưu trên CFS `db-backups/` | **85,5 GB**, 5.319 tệp (giữ 30 đêm) |
| Bản 15 phút trên ổ VPS | 9,4 GB (giữ 2 ngày) |

Giữ nguyên thì sau ~1 năm riêng bản sao lưu ~1,1 TB trên CFS và ~80 GB trên ổ VPS.
Dump còn chỉ có schema `public` (+ `auth` tệp riêng), lùi được tới mốc 15 phút gần nhất.

## Đích

- **pgBackRest**: bản đầy đủ mỗi tuần + bản chênh lệch mỗi đêm + chép nhật ký (WAL) liên tục.
  Khôi phục tới **bất kỳ giây nào** trong thời gian giữ, cả cụm Postgres (mọi schema).
- Giữ **một `pg_dump` mỗi đêm** (30 ngày): định dạng độc lập phòng pgBackRest hỏng, và là
  nguồn nạp staging 03:30 (`staging-nap-ban-sao.sh`) — không đổi đường đó.
- Bỏ bản 15 phút.

Ước dung lượng 30 ngày: 4–5 bản đầy đủ (~60 MB nén mỗi bản) + nhật ký (~40–50 MB/ngày nén)
≈ **1,5–2 GB**, thay cho 85 GB. Tăng theo lượng ghi mỗi ngày, không theo số bản.

## Thiết kế

| Phần | Chọn | Vì sao |
|---|---|---|
| Công cụ | pgBackRest (gói PGDG) | posix repo, `archive-async`, kiểm toàn vẹn, giữ theo số bản đầy đủ; không thêm dịch vụ chạy 24/7 |
| Cài ở đâu | ảnh DB riêng `Dockerfile.db` = `FROM postgres:17` + `pgbackrest` | `archive_command` chạy TRONG container DB; image `postgres:17` không có sẵn |
| Kho chính (repo1) | **ổ VPS** `/home/clinicai/pgbackrest` (bind vào container) | chép nhật ký không bao giờ chờ ổ mạng: CFS chập chờn mà `archive_command` treo là `pg_wal` phình tới đầy ổ, DB dừng |
| Bản ngoài máy | timer chép tệp MỚI của repo1 sang CFS `/mnt/viettel-cfs/pgbackrest` + `keo-ve.sh` trên Mac kéo về | cùng khuôn day-tep: tệp kho bất biến, chỉ chép thêm; kiểm `pgbackrest verify` trên bản CFS |
| Chặn đầy ổ | `archive-push-queue-max=4GB` | nhật ký không chép được quá 4 GB thì bỏ bớt (mất khả năng lùi giây, DB vẫn chạy) thay vì làm đầy ổ |
| Giữ | repo1: 2 bản đầy đủ (~14–21 ngày) · CFS/Mac: 5 bản đầy đủ (~35 ngày) · dump đêm 30 ngày | |
| Canh gác | luật mới trong `canh_gac`: `pg_stat_archiver.failed_count` tăng, hoặc `last_archived_time` cũ > 15 phút, hoặc bản đầy đủ cũ > 8 ngày → `/ops` + Telegram ops | hôm nay sao lưu hỏng không ai biết đã xảy ra (11/10) |
| Cấu hình Postgres | `archive_mode=on`, `archive_command='pgbackrest --stanza=clinicai archive-push %p'`, `archive_timeout=300` | `archive_mode` cần **khởi động lại DB** |

Làm chung lần khởi động lại đó (việc 5 của báo cáo hạ tầng): `shared_buffers` 128 MB → ~1,5 GB
(máy 8 GB chung staging), `effective_cache_size` 4 GB giữ nguyên.

## Các bước

1. **PR code (Mức 3, một PR):** `Dockerfile.db`, `docker-compose.supabase.yml` (ảnh + cờ
   `-c`), `pgbackrest.conf`, `scripts/sao-luu-noi-tiep.sh` (full/diff), `scripts/chep-kho-sao-luu.sh`
   (repo1 → CFS), unit `scripts/systemd/clinicai-pgbackrest-*.{service,timer}`, luật canh gác +
   test, sửa `restore-drill.sh` thêm đường `pgbackrest restore`, `keo-ve.sh` (Mac) kéo repo,
   `.claude/skills/len-prod` + `docs/VAN-HANH-MAY-CHU.md`.
2. **Thử local** (`scripts/dev-up.sh`, ảnh DB mới): stanza-create → full → ghi dữ liệu → khôi phục
   tới một giây cụ thể vào DB tạm, đếm dòng bảng chính khớp.
3. **Staging** (`clinicai_stg_db`, cùng ảnh mới): chạy 2–3 ngày, xem nhật ký chép đều, bản đêm,
   bản CFS, cảnh báo khi cố ý làm hỏng `archive_command`.
4. **Prod, khung đêm có người xem (~15 phút, DB ngừng ~1 phút):** sao lưu dump như cũ → deploy
   ảnh DB mới + cờ mới → `stanza-create` → full đầu tiên → kiểm `pg_stat_archiver` → diễn tập
   khôi phục bản vừa có vào DB tạm.
5. **Một tuần sau, khi đã có bản đầy đủ thứ hai và diễn tập đạt:** tắt timer 15 phút, đổi dump đêm
   giữ 30 ngày, dọn `db-backups/` cũ trên CFS (giữ 7 ngày cuối) và `backups/clinicai-15p/` trên VPS.

## Đã thử (03/11, Mac, ảnh `clinicai-db:17-pgbackrest`, pgBackRest 2.60.0)

`bat` → `full` (22,6 MB, 1,5 s) → ghi 50 dòng → mốc T → ghi 30 dòng →
`dien-tap "T"` ra **150** dòng, `dien-tap` (mới nhất) ra **180** = khớp DB thật;
container/volume tạm tự dọn. Năm lỗi chỉ lộ ra khi chạy thật, đã sửa trong script:
log-path không tự tạo · `--archive-async` không hợp lệ cho `restore` ·
`--spool-path` không hợp lệ cho `archive-get` đồng bộ · restore đòi thư mục thuộc
postgres (dùng volume) · **giờ không ghi múi giờ bị hiểu là UTC — lệch 7 tiếng**
(script tự gắn `+07`).

## Lệnh chạy

DB prod dựng bằng `--env-file .env.supabase-local`; DB staging bằng `.env.staging` +
`docker-compose.supabase.staging.yml` (nhãn compose trên container, đọc 03/11).

Staging (thử trước, ngoài giờ khám hoặc trước 17h ngày thường):
```bash
ssh clinic-vps-moi 'cd /home/clinicai/clinicai-staging && git fetch -q origin && git checkout -q claude/sao-luu-noi-tiep && git pull -q --ff-only origin claude/sao-luu-noi-tiep && sudo ./scripts/may-chu/bat-sao-luu-noi-tiep.sh staging'
```
rồi thêm vào `.env.staging`: `SUPABASE_DB_IMAGE=clinicai-db:17-pgbackrest`,
`SUPABASE_DB_ARCHIVE_MODE=on`, `SUPABASE_DB_PGBACKREST_DIR=/home/clinicai/pgbackrest-staging`,
dựng lại DB staging và:
```bash
ssh clinic-vps-moi 'cd /home/clinicai/clinicai-staging && docker compose --env-file .env.staging -f docker-compose.supabase.yml -f docker-compose.supabase.staging.yml -p clinicai_stg_db up -d db && export CLINIC_DB_CONTAINER=clinicai_stg_db SUPABASE_DB_PGBACKREST_DIR=/home/clinicai/pgbackrest-staging && ./scripts/sao-luu-noi-tiep.sh bat && ./scripts/sao-luu-noi-tiep.sh full && ./scripts/sao-luu-noi-tiep.sh dien-tap'
```
Prod: y như trên với `.env.supabase-local`, `-p clinicai_db`, không có tệp staging,
thư mục `/home/clinicai/pgbackrest`, thêm `SUPABASE_DB_SHARED_BUFFERS=1536MB`; bước
`bat-sao-luu-noi-tiep.sh prod` cài luôn timer.

## Lùi

Đổi lại ảnh `postgres:17` + bỏ cờ `archive_*` → khởi động lại DB (~1 phút), bật lại timer 15 phút.
Dữ liệu không đụng; dump đêm chạy suốt nên luôn có bản cũ để khôi phục.

## Chưa biết, phải đo khi thử

- Tỉ lệ nén nhật ký thật (ước 4–5×).
- Thời gian bản đầy đủ đầu tiên và tải CPU lúc chạy (chạy `nice`, ngoài giờ khám).
- pgBackRest đọc kho trên CFS (SMB) để `verify` mất bao lâu.
