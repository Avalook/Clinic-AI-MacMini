# Đưa lô mẫu `DEMO1709-*` về 0 trên prod (điều chỉnh, không xoá)

Mức 3 (dữ liệu prod, kho) · soạn 27/10/2026 · **Tuyền chạy tay**, AI chỉ soạn lệnh.

## Việc này làm gì

Prod chỉ có **lô mẫu** (`DEMO1709-*`, 80 lô mỗi cơ sở, tổng ~3.200), chưa có tồn thật.
Khi PR "giao thuốc tự chọn lô" lên prod, máy sẽ tự trừ vào lô mẫu còn tồn. Script này đưa
mọi lô mẫu về **0 bằng một dòng điều chỉnh (ADJUST) cho mỗi lô** — lô, sổ nhập gốc, lịch
sử đều **giữ nguyên**, chỉ thêm dòng "Đưa lô mẫu DEMO1709 về 0 để nạp tồn thật (27/10/2026)".

- Chỉ động vào lô có mã bắt đầu `DEMO1709-`. Lô khác: kiểm trước/sau, lệch là huỷ.
- Người ghi sổ: tài khoản Quản lý `Quản lý hệ thống` (không có thì Quản lý đang hoạt động
  đầu tiên theo tên). Tên hiện ở bảng tóm tắt cuối.
- **Dừng, không ghi gì** nếu có lô mẫu đang bị giữ cho một đơn, hoặc có thuốc khách trả
  chờ kiểm — việc thật, xử lý tay trước.
- Chạy lại: không ghi thêm. Lùi: `kho-hoan-tac-lo-mau-ve-0.sql` (cộng lại đúng số đã bớt).
- Thứ tự với PR giao tự chọn lô: **dọn lô mẫu trước, deploy PR sau**; rồi nạp tồn thật.

## Trước khi chạy

1. Ngoài giờ khám, hoặc lúc quầy thuốc vắng. Không chạy khi có phiếu **Kiểm ca** ở quầy
   đang đếm dở (chốt hoặc đợi hết ca) — con số "tồn máy" của phiếu sẽ đổi giữa chừng.
2. Đứng đúng thư mục có hai script (nhánh có tệp `scripts/kho-dua-lo-mau-ve-0.sql`):

```bash
cd /Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/clinicai-handover-package-c4ff3e
```

   Sau khi PR được merge, chạy từ checkout `main` — đường dẫn `scripts/...` giống hệt.

## Bước 1 — Sao lưu prod (ngay trước khi chạy)

```bash
ssh clinic-vps-moi 'cd /home/clinicai/clinicai && PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db BACKUP_ENV_FILE=.env.prod CLINIC_BACKUP_DIR=/home/clinicai/backups/clinicai ./scripts/backup-db.sh'
```

Kiểm bản vừa tạo (tên có ngày giờ vừa xong, kích thước cỡ 40 MB):

```bash
ssh clinic-vps-moi 'ls -lt /home/clinicai/backups/clinicai | head -4'
```

## Bước 2 — Diễn tập trên BẢN SAO prod (trên Mac, không đụng prod)

Dựng Postgres tạm từ bản sao lưu đêm mới nhất (cách của `~/Projects/ClinicAI-Backups/HUONG-DAN-PHUC-HOI.md`):

```bash
BAN=$(ls -t ~/Projects/ClinicAI-Backups/ban-sao/clinicai_production_clinicai-db_*[0-9].sql.gz | grep -v '_auth\|_lich_su' | head -1) && echo "$BAN" && gzip -t "$BAN" && echo "file lành"
```

```bash
docker rm -fv clinic-dien-tap-lo-mau >/dev/null 2>&1; docker run -d --name clinic-dien-tap-lo-mau -e POSTGRES_PASSWORD=dien-tap-local -e TZ=Asia/Ho_Chi_Minh -p 127.0.0.1:55477:5432 postgres:17 && until docker exec clinic-dien-tap-lo-mau pg_isready -U postgres; do sleep 1; done
```

```bash
docker exec -i clinic-dien-tap-lo-mau psql -q -U postgres -d postgres <<'SQL'
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE SCHEMA IF NOT EXISTS auth;
DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE service_role NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticator NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
SQL
```

```bash
gzip -dc "$BAN" | docker exec -i clinic-dien-tap-lo-mau psql -U postgres -d postgres > /tmp/phuc-hoi-dien-tap.log 2>&1; grep -c '^ERROR' /tmp/phuc-hoi-dien-tap.log
```

Phải ra đúng **2** (`schema "public" already exists` và `auth.users does not exist`, cả hai vô hại).

Thử khô trên bản sao — phải thấy bảng tóm tắt rồi `ROLLBACK`:

```bash
docker exec -i clinic-dien-tap-lo-mau psql -v ON_ERROR_STOP=1 -v ket_thuc=ROLLBACK -U postgres -d postgres < scripts/kho-dua-lo-mau-ve-0.sql
```

Với bản sao lưu 27/10 02:15 kết quả đã chạy thử là: **Hào Nam 80 lô / 1.600 · Kim Ngưu 80 lô / 1.600 · người ghi sổ `Quản lý hệ thống` · `tong_lo_mau` 160 = `lo_mau_da_ve_0` 160 · `lo_khac_giu_nguyen` 2, `ton_lo_khac` 0**.

Chạy thật trên bản sao, rồi kiểm:

```bash
docker exec -i clinic-dien-tap-lo-mau psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT -U postgres -d postgres < scripts/kho-dua-lo-mau-ve-0.sql
```

```bash
docker exec clinic-dien-tap-lo-mau psql -U postgres -d postgres -c "SELECT count(*) AS lo_mau, sum(quantity_on_hand) AS ton, count(*) FILTER (WHERE quantity_on_hand <> 0) AS con_ton FROM drug_batch WHERE batch_code LIKE 'DEMO1709-%'" -c "SELECT count(*) AS dong_dieu_chinh_moi, sum(quantity) AS tong FROM inventory_txn WHERE reason LIKE 'Đưa lô mẫu%'"
```

Phải ra: `con_ton` 0 · `dong_dieu_chinh_moi` 160 · `tong` -3200.

Thử lùi trên bản sao (cộng lại đủ 3.200), rồi dọn container **kèm volume**:

```bash
docker exec -i clinic-dien-tap-lo-mau psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT -U postgres -d postgres < scripts/kho-hoan-tac-lo-mau-ve-0.sql
```

```bash
docker rm -fv clinic-dien-tap-lo-mau
```

## Bước 3 — Thử khô trên prod (không ghi gì)

```bash
ssh clinic-vps-moi 'docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -v ket_thuc=ROLLBACK -U postgres -d postgres' < scripts/kho-dua-lo-mau-ve-0.sql
```

Đối chiếu với bước 2: số lô, số bớt từng cơ sở, tên người ghi sổ. **Lệch nhiều so với bản sao
(vd có lô mẫu bị giữ, báo lỗi "xử lý tay trước") thì dừng, đừng chạy thật.**

## Bước 4 — Chạy thật trên prod

```bash
ssh clinic-vps-moi 'docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT -U postgres -d postgres' < scripts/kho-dua-lo-mau-ve-0.sql
```

Dòng cuối phải là `COMMIT`. Gặp lỗi ở giữa thì cả giao dịch tự huỷ, không ghi gì.

## Bước 5 — Kiểm sau

```bash
ssh clinic-vps-moi 'docker exec clinicai_db psql -U postgres -d postgres -c "SELECT count(*) AS lo_mau, sum(quantity_on_hand) AS ton, count(*) FILTER (WHERE quantity_on_hand <> 0) AS con_ton FROM drug_batch WHERE batch_code LIKE '"'"'DEMO1709-%'"'"'"'
```

`con_ton` phải 0. Rồi mở **Kho thuốc → Thuốc trong kho**: các lô mẫu vẫn hiện, tồn 0; **Lịch sử nhập / xuất** của lô có dòng
"Đưa lô mẫu DEMO1709 về 0 để nạp tồn thật". Báo cáo kho: tồn cuối của thuốc mẫu = 0.

## Lùi lại (nếu cần)

```bash
ssh clinic-vps-moi 'docker exec -i clinicai_db psql -v ON_ERROR_STOP=1 -v ket_thuc=COMMIT -U postgres -d postgres' < scripts/kho-hoan-tac-lo-mau-ve-0.sql
```

Cộng lại đúng số đã bớt (bằng dòng ADJUST mới, dòng gốc giữ nguyên). Muốn thử trước: đổi `COMMIT` thành `ROLLBACK`.

## Sau đó: nạp tồn thật

Kho thuốc → **Nhập thuốc** theo đúng **đơn vị bán** của thuốc (nhập theo hộp thì máy hỏi
"1 hộp = ? gói" lần đầu, rồi nhớ). Lô mới không có số lô hoặc hạn thì nhập số lô thật in trên hộp;
hạn có thể bổ sung sau. Chỉ sau khi có tồn thật mới nên deploy PR "giao thuốc tự chọn lô"
(không có tồn thì giao vẫn chạy, vào danh sách "Đã giao, chưa trừ kho" như hiện nay).
