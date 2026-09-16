# BÀN GIAO — dựng lại toàn bộ hệ thống trên VPS mới (16/09/2026)

> **Vì sao vài chỗ ghi `<ID>` / `<IP-DBaaS>`:** repo này CÔNG KHAI. Đường dẫn
> SMB đầy đủ cộng tên tài khoản AD là đã đủ để người ngoài chỉ còn thiếu mỗi
> mật khẩu — và chính Viettel dặn không tiết lộ thông tin đường dẫn. Số thật
> nằm trong memory ClinicAI và trong `/etc/clinicai-viettel-smb.cred`,
> `~/.env.viettel` trên máy chủ (cả hai quyền 600).

> Đọc file này TRƯỚC khi chạm vào hạ tầng. Mọi con số dưới đây là **đo thật**
> trong phiên 16/09, không phải chép từ tài liệu cũ — tài liệu cũ nay đã sai ở
> gần như mọi địa chỉ.

## 0. Việc gấp nhất khi vào phiên

1. **Máy chủ đã đổi.** `clinic-vps` (cũ) đã chết. Dùng **`clinic-vps-moi`**.
2. **Hệ thống đang chạy thật** ở https://dr4women.io.vn — có HTTPS, đăng nhập được.
3. **Dữ liệu bệnh nhân cũ KHÔNG được nạp lại** (Tuyền chốt 16/09: làm mới hoàn toàn).
4. Còn **8 tài khoản thử** phải xoá trước khi phòng khám nhập bệnh nhân thật.

---

## 1. Hạ tầng — cái gì ở đâu

| | Cũ (đã chết) | **Mới (đang chạy)** |
|---|---|---|
| VPS | `222.255.215.219` | **`222.255.214.133`** |
| Alias SSH | `clinic-vps` | **`clinic-vps-moi`** |
| Tài nguyên | (nhỏ, hay OOM) | **4 CPU · 7,8 GB RAM · 48 GB đĩa** |
| Hệ điều hành | — | Ubuntu, OpenSSH 9.9p1, Docker 29.2.1 + Compose v5.0.2 |
| Địa chỉ web | `http://222.255.215.219` (HTTP trần) | **`https://dr4women.io.vn`** (Let's Encrypt) |
| Tên miền | không có | **`dr4women.io.vn`**, PA Vietnam, hạn **16/09/2027** |

**Vietnix không gia hạn máy cũ — họ cấp máy MỚI, trắng trơn.** Ổ của máy cũ có
thể vẫn còn ở Vietnix (chưa ai hỏi; Tuyền quyết không hỏi). Dữ liệu từ
12/09 02:15 → 18:30 chỉ nằm ở đó, coi như mất.

Bản sao cũ vẫn còn nguyên trên Mac nếu sau này đổi ý:
`~/Projects/ClinicAI-Backups/ban-sao/*_20260912_021517*` (140 tệp, gzip nguyên vẹn).

### DNS
`dr4women.io.vn` và `www` → `222.255.214.133` (bản ghi A, TTL 3600), quản lý tại
PA Vietnam (`access.pavietnam.vn`). Đã lan khắp (Google, Cloudflare, PA).

⚠️ Còn nghĩa vụ pháp lý **chưa làm**: bổ sung hồ sơ chủ thể + khai báo tại
`thongbaotenmien.vn`. Không làm thì tên miền bị tạm ngưng.

---

## 2. Trạng thái hệ thống (đo 16/09)

```
clinicai_db · auth · rest · realtime · supabase_gateway · auth_guard   healthy
clinicai_prod-api · dashboard · caddy · uptime-kuma · dozzle           healthy
```

- Postgres **17.11**, lược đồ **79 bảng · 69 policy · 119 migration · 16 bảng auth**
- Dữ liệu: **1 phòng khám · 3 địa điểm · 43 nhân sự · 22 năng lực · 14 dịch vụ**
- **0 bệnh nhân · 0 lịch hẹn** (cố ý — nhập mới)
- 43 nhân sự = 35 người thật (`clinic_roster.sql`) + 8 tài khoản thử

Khoá JWT **sinh mới hoàn toàn** trên máy này, không bê khoá cũ sang.
`REALTIME_DB_ENC_KEY` cũng đặt riêng (16 ký tự) — chỉ làm được lúc dựng mới.

### Tài khoản thử — XOÁ TRƯỚC KHI CÓ BỆNH NHÂN THẬT
Mật khẩu chung `clinic-test-pw-123` (nằm trong git công khai → là cửa mở).

`letan@` `bs.a@` `bs.sa@` `dd.sa@` `cskh@` `thungan@` `duocsi@` `ql@`
— tất cả `@dr4women.local`.

Dọn bằng `supabase/fixtures/xoa_tai_khoan_dung_chung.sql`.

---

## 3. Lệnh hay dùng

```bash
ssh clinic-vps-moi                              # vào máy chủ

# trạng thái
ssh clinic-vps-moi 'cd ~/clinicai && docker compose --env-file .env.prod -p clinicai_prod ps'
ssh clinic-vps-moi 'cd ~/clinicai && docker compose --env-file .env.supabase-local -f docker-compose.supabase.yml -p clinicai_db ps'

# dựng lại lớp ứng dụng sau khi sửa code
ssh clinic-vps-moi 'cd ~/clinicai && docker compose --env-file .env.prod -p clinicai_prod up -d --build'

# sao lưu tay (PHẢI có hai biến này, xem §5)
ssh clinic-vps-moi 'cd ~/clinicai && PG_DUMP_BIN=scripts/pg-dump-qua-container.sh CLINIC_DB_CONTAINER=clinicai_db ./scripts/backup-db.sh'

# đẩy sang Viettel
ssh clinic-vps-moi 'cd ~/clinicai && ./scripts/day-sao-luu-len-viettel-storage.sh'

# sao lưu tự động
ssh clinic-vps-moi 'systemctl list-timers clinicai-backup.timer --no-pager'
ssh clinic-vps-moi 'sudo journalctl -u clinicai-backup.service -n 30 --no-pager -o cat'

# hỏi database
ssh clinic-vps-moi 'docker exec clinicai_db psql -U postgres -c "select count(*) from staff"'
```

Nhật ký sao lưu nằm ở `~/Library/Logs/clinicai-backup.log` khi chạy tay
(đường dẫn macOS, xem §5) và trong journal khi chạy qua systemd.

---

## 4. Viettel — hai dịch vụ, khác nhau về AN TOÀN chứ không chỉ hình dạng

### ✅ Cloud File Storage — ĐANG DÙNG, là đường sao lưu chính thức

```
\\pv-cfs.viettelidc.com.vn\qtree_<ID>   →  IP công khai (xem memory)
tài khoản AD : <ID>@vtdc.cloud
mount tại    : /mnt/viettel-cfs  (đã vào /etc/fstab)
mật khẩu     : /etc/clinicai-viettel-smb.cred (quyền 600)
```

- SMB **3.1.1 + `seal`** → **mã hoá thật**
- Đo: ghi 34,9 MB/s · đọc 271 MB/s · dung lượng 1,1 TB · mã băm khớp hai đầu
- Hạn gói: **16/10/2026** (1 tháng) — 1.522.500đ/tháng

### ⚠️ Database Service (DBaaS) — KHÔNG DÙNG cho dữ liệu bệnh nhân

```
<IP-DBaaS>:5432  ·  db avalook  ·  user dbadmin  ·  PostgreSQL 18.3
VPC vpc-61366399  ·  hạn 07/11/2026  ·  IP nội bộ + Elastic IP đã gán
chuỗi kết nối: ~/.env.viettel trên VPS (quyền 600)
```

**Máy chủ TỪ CHỐI SSL:** `server does not support SSL, but SSL was required`.
Dump mang tên, số điện thoại, hồ sơ khám sẽ đi **trần** qua Internet công cộng.
Nên `day-sao-luu-len-viettel.sh` (đường DBaaS) **đã bị gỡ khỏi unit systemd**.

Viettel cũng đã chốt trong nhóm Messenger (06/08): **CREATEROLE + REPLICATION
"policy bên em đang không cung cấp cho khách hàng"** → không chạy nổi
GoTrue/PostgREST/Realtime trên đó. Nó chỉ có thể làm kho, không làm database.

**Muốn dùng lại đường này** thì phải bọc mã hoá tệp (`age`/`gpg`) trước khi đẩy,
khoá giải mã giữ ở Mac — **không bao giờ để trên VPS**.

### Câu hỏi treo
Chị Thu báo Viettel **50 GB/ngày**. Nếu đúng, ổ 1 TB đầy trong 21 ngày và giữ
một năm sẽ tốn ~21 triệu/tháng. Tuyền nói "không phải hôm nào cũng hết" — nhưng
con số này chưa ai đo. `.media` trên VPS hiện **rỗng**, ảnh/video đang ở Google
Drive, chưa đi qua hệ thống.

---

## 5. Sáu cạm bẫy đã cắn thật trong phiên này — và cách chúng lộ ra

Tất cả đều cùng một bệnh: **báo thành công theo ý định, không theo sự thật.**

| # | Bẫy | Triệu chứng | Đã vá ở |
|---|---|---|---|
| 1 | `.env.viettel` rỗng 0 byte | script thoát 1, **in ra 0 chữ**, systemd báo "Deactivated successfully" — im lặng 17 đêm | `day-sao-luu-len-viettel.sh` |
| 2 | Ubuntu không có sẵn `ufw` | script vẫn báo *"xong · cổng mở 22·80·443"* trong khi **không có tường lửa nào** | `vps-chuan-bi.sh` |
| 3 | `ANTHROPIC_API_KEY` trống | **cả FastAPI chết** trong lifespan dù `ENABLE_AI_ORCHESTRATOR=false` | `main.py` + 3 router |
| 4 | PostgREST giữ lược đồ cũ | đăng nhập được, dữ liệu nguyên, nhưng 2 màn đỏ *"Could not find a relationship"*; **không lỗi nào vào log database** | `supabase-local-nap.sh` |
| 5 | `backup-db.sh` log vào `~/Library/Logs` | đường dẫn **macOS**; chạy trên Linux thì mọi lỗi chui vào file không ai ngó, terminal im | *chưa vá* |
| 6 | `/mnt/viettel-cfs` khi không mount | vẫn là thư mục thường → `cp` chạy ngon, báo "đã đẩy", bản sao "ngoài máy" nằm **trên chính ổ nó bảo vệ** | `day-sao-luu-len-viettel-storage.sh` |

Bẫy #5 **chưa vá** — đáng vá: `LOG` nên chọn theo hệ điều hành, và lỗi phải
luôn ra stderr chứ không chỉ vào file.

Ngoài ra: `SITE_ADDRESS` **không được chứa dấu cách** (`dr4women.io.vn, www...`)
— mọi script `source` file `.env` sẽ vỡ ở dòng đó.

---

## 6. Sao lưu — đã chạy thật

```
02:15 mỗi đêm (systemd timer clinicai-backup.timer)
  → pg_dump QUA CONTAINER (phiên bản luôn khớp)
  → đẩy lên /mnt/viettel-cfs/db-backups qua SMB3 có mã hoá
  → đọc lại, đối chiếu sha256 hai đầu
  giữ 30 đêm
```

Đã chạy thử qua systemd: `Result: success`.

**Diễn tập khôi phục** (`restore-drill.sh`): **15 PASS / 1 FAIL**.
Cái FAIL là *"backup captured nothing"* — đúng thực tế vì bảng bệnh nhân rỗng.
Đếm trong dump: `clinic 1 · clinic_location 3 · staff 43 · clinic_membership 43
· staff_capability 22 · service_type 14 · patient 0 · appointment 0`, 22 bảng có
dữ liệu. Lược đồ, 69 policy, `clinic_id` từng bảng đều khôi phục đúng.
Chốt kiểm đó sẽ tự xanh khi có bệnh nhân đầu tiên.

---

## 7. Việc còn lại, theo thứ tự

1. **Tài khoản đăng nhập thật cho 35 nhân sự** — `provision-staff-logins.sh`
   dùng luồng invite (mỗi người tự đặt mật khẩu). Cần **danh sách email thật**
   và một đường gửi mail (SMTP). Đây là thứ đang chặn phòng khám dùng được.
2. **Xoá 8 tài khoản thử** trước khi có bệnh nhân thật.
3. **Vá bẫy #5** (log macOS trong `backup-db.sh`).
4. **Nghĩa vụ pháp lý tên miền** — hồ sơ chủ thể + `thongbaotenmien.vn`.
5. **Sổ hợp đồng + ngày hết hạn** (chưa dựng). Ngày đã biết:
   - Viettel Storage **16/10/2026** ← gần nhất
   - Viettel DBaaS **07/11/2026**
   - Tên miền **16/09/2027**
   - VPS Vietnix — **chưa ai xem**
6. **Đo thật lượng media/ngày** trước khi tin con số 50 GB.
7. Thử đường ghi đầu-cuối (tạo bệnh nhân → đặt lịch → khám → thanh toán).
   Chưa làm vì `patient` là bảng cấm xoá cứng, cần Tuyền đồng ý trước.

---

## 8. Đổi mật khẩu — cách làm không để lộ

Mật khẩu **không bao giờ dán vào khung chat**. Gõ thẳng trên máy chủ:

```bash
# Viettel Storage (AD)
ssh -t clinic-vps-moi 'read -rsp "Mat khau AD: " P; echo; umask 077; printf "username=<ID>@vtdc.cloud\npassword=%s\n" "$P" | sudo tee /etc/clinicai-viettel-smb.cred >/dev/null && sudo chmod 600 /etc/clinicai-viettel-smb.cred && echo "da luu, dai ${#P} ky tu"'

# Viettel DBaaS
ssh -t clinic-vps-moi 'read -rsp "Mat khau dbadmin: " P; echo; umask 077; printf "VIETTEL_DATABASE_URL=postgresql://dbadmin:%s@<IP-DBaaS>:5432/avalook?sslmode=require\n" "$P" > ~/.env.viettel && chmod 600 ~/.env.viettel && echo "da luu"'
```

Sinh mật khẩu đủ mạnh mà Viettel chấp nhận (tập `!@#$%^&*`; `~ - _ .` bị họ từ
chối là "chưa đủ mạnh"):

```bash
python3 -c 'import secrets,string
U,L,D,S=string.ascii_uppercase,string.ascii_lowercase,string.digits,"!@#$%^&*"
p=[secrets.choice(U),secrets.choice(L),secrets.choice(D),secrets.choice(S)]
p+=[secrets.choice(U+L+D) for _ in range(10)]
secrets.SystemRandom().shuffle(p)
print("".join(p))'
```

⚠️ Mật khẩu dùng trong **chuỗi URL** (DBaaS) phải tránh `@ : / # ? \` — chúng
cắt nhầm chuỗi kết nối, và lỗi hiện ra trông y hệt "sai mật khẩu".
