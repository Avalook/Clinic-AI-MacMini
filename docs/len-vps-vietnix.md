# Đưa ClinicAI lên VPS Vietnix

Làm theo thứ tự. Mỗi bước có cách **tự kiểm** — đừng sang bước sau khi bước
trước chưa xanh.

Ba số Vietnix gửi qua email: **IP**, **cổng SSH** (thường 22), **mật khẩu root**.
Mật khẩu chỉ dùng đúng một lần ở bước 2, sau đó bị tắt hẳn.

Ký hiệu trong tài liệu: thay `<IP>` và `<PORT>` bằng số thật của anh.

---

## Bước 1 · Tạo khoá SSH trên máy Mac

```bash
ssh-keygen -t ed25519 -C "clinicai-mac-mini" -f ~/.ssh/id_ed25519
```

Nhấn Enter khi nó hỏi passphrase (hoặc đặt một câu — an toàn hơn, phải gõ mỗi
lần dùng).

**Vì sao khoá chứ không mật khẩu.** Mật khẩu root do Vietnix gửi **qua email**.
Hộp thư ấy lộ thì cả máy chủ lộ theo, và không có gì ghi lại rằng đã có người
vào. Khoá riêng thì không rời khỏi máy Mac.

*Tự kiểm:* `ls ~/.ssh/id_ed25519.pub` phải có tệp.

---

## Bước 2 · Chép khoá lên VPS

```bash
ssh-copy-id -p <PORT> root@<IP>
```

Nó hỏi mật khẩu root — **anh tự gõ**, đây là lần duy nhất cần tới nó.

*Tự kiểm:* `ssh -p <PORT> root@<IP> 'echo vao duoc'` phải vào **không hỏi mật khẩu**.

---

## Bước 3 · Chuẩn bị máy

```bash
ssh -p <PORT> root@<IP> 'SSH_PORT=<PORT> bash -s' < scripts/vps-chuan-bi.sh
```

Script làm bốn việc: tạo người dùng thường `clinicai`, bật tường lửa chỉ mở
SSH/80/443, cài Docker, rồi **tắt đăng nhập bằng mật khẩu và cấm root**.

**GIỮ NGUYÊN cửa sổ SSH đang mở.** Mở một cửa sổ MỚI để thử:

```bash
ssh -p <PORT> clinicai@<IP> 'docker --version && sudo -n true && echo "OK"'
```

Vào được thì mới đóng cửa sổ cũ. Nếu không vào được mà đã đóng cả hai, đường
duy nhất còn lại là console trong trang quản trị Vietnix.

---

## Bước 4 · Lấy mã nguồn lên VPS

Repo công khai nên không cần khoá triển khai.

```bash
ssh -p <PORT> clinicai@<IP> 'git clone https://github.com/Avalook/Clinic-AI-MacMini.git ~/clinicai && cd ~/clinicai && git log --oneline -1'
```

---

## Bước 5 · Bí mật

**KHÔNG chép `.env` từ máy Mac sang.** Bí mật của hai môi trường phải khác nhau
— lộ một bên thì bên kia vẫn an toàn. Sinh mới trên VPS:

```bash
ssh -p <PORT> clinicai@<IP> 'cd ~/clinicai && python3 scripts/sinh-khoa-supabase.py'
```

Rồi tạo `.env.prod` trên VPS. Cần điền:

| Biến | Lấy ở đâu |
|---|---|
| `DATABASE_URL` | chuỗi kết nối Postgres (Viettel IDC, hoặc bộ tự dựng trên chính VPS) |
| `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL` | `https://<tên miền>` |
| `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | từ lệnh sinh khoá ở trên |
| `BACKEND_API_KEY` | `openssl rand -base64 32` |
| `SITE_ADDRESS` | tên miền, ví dụ `clinic.dr4women.vn` |
| `APP_ENV` | `production` |

*Tự kiểm:* `grep -c '=' ~/clinicai/.env.prod` phải ra đủ số dòng, và
`git check-ignore .env.prod` phải báo bị chặn.

---

## Bước 6 · Dựng database

Hai đường, chọn một:

**A · Postgres trên chính VPS** — dùng ngay, không tốn thêm tiền:

```bash
ssh -p <PORT> clinicai@<IP> 'cd ~/clinicai && docker compose --env-file .env.supabase-local -f docker-compose.supabase.yml -p clinicai_db up -d && sleep 25 && ./scripts/supabase-local-nap.sh'
```

**B · Postgres ở Viettel IDC** — chỉ dựng ba dịch vụ còn lại, `DATABASE_URL`
trỏ sang Viettel. Trước khi dựng phải xác nhận Viettel cho:
`wal_level = logical`, vai có `REPLICATION`/`BYPASSRLS`/`CREATEROLE`, và 6
extension. Thiếu `wal_level` thì realtime không nhận sự kiện — hỏng im lặng.

*Tự kiểm (cả hai đường):*

```bash
ssh -p <PORT> clinicai@<IP> 'cd ~/clinicai && docker compose --env-file .env.supabase-local -f docker-compose.supabase.yml -p clinicai_db exec -T db psql -U postgres -tAc "select count(*) || \" bang\" from information_schema.tables where table_schema=\"public\""'
```

Phải ra **67 bảng**.

---

## Bước 7 · Đưa dữ liệu sang

Chỉ làm khi bước 6 đã xanh.

```bash
./scripts/backup-db.sh
```

Rồi chép bản lưu lên VPS và nạp. **Phải mang cả `auth.users` và
`auth.identities`** — `staff.auth_user_id` trỏ vào đó, sai một `id` là nhân sự
ấy mất liên kết đăng nhập và nhận 403 ở mọi thao tác ghi.

*Tự kiểm:* số nhân sự, số dịch vụ, số phòng phải khớp với Supabase cloud.

---

## Bước 8 · Tên miền và HTTPS

Trỏ bản ghi `A` của tên miền về `<IP>`, chờ DNS lan (5–30 phút), rồi:

```bash
ssh -p <PORT> clinicai@<IP> 'cd ~/clinicai && docker compose --env-file .env.prod -p clinicai_prod up -d'
```

Caddy tự xin chứng chỉ Let's Encrypt khi `SITE_ADDRESS` là một tên miền thật.

*Tự kiểm:* mở `https://<tên miền>` — phải thấy ổ khoá, không cảnh báo.

---

## Bước 9 · Sao lưu — hai tầng, và chúng cứu hai chuyện khác nhau

**Tầng 1 · Snapshot của Vietnix.** Gói mặc định chụp **hằng tuần**, có thể mua
thêm để chụp **hằng ngày**. Nó cứu khi *cả máy* hỏng — xoá nhầm, đĩa lỗi, cấu
hình sai không lần ra.

**Tầng 2 · `pg_dump` hằng đêm** (`scripts/backup-db.sh`, đã có). Nó cứu khi
*dữ liệu* sai mà máy vẫn chạy — xoá nhầm một bảng, một migration hỏng. Snapshot
không giúp được, vì khôi phục snapshot là lùi cả máy về tuần trước.

**Và bản lưu phải nằm ở nơi khác.** Bản lưu để cùng máy với dữ liệu gốc thì mất
máy là mất cả hai. Đây là thứ đáng mua thêm — object storage vài chục nghìn một
tháng, rẻ hơn nhiều so với gói database.

**Sao lưu chưa thử khôi phục thì chưa phải sao lưu.** Ngày 04/08 bản lưu chạy
hằng đêm suốt nhưng **khôi phục đổ 60 lỗi** vì `f_unaccent` không ghi rõ schema.
Không ai biết cho tới lúc thử thật. Đặt lịch thử khôi phục mỗi tháng.

---

## Sau khi xong

Máy Mac mini **giữ nguyên, đừng tắt**. Trong ít nhất một tuần nó là đường lùi:
nếu VPS có chuyện, đổi DNS về lại là chạy tiếp.

Hai việc còn phải làm ngày đầu:

- **Đổi `NEXT_PUBLIC_SUPABASE_URL`** sang tên miền mới rồi dựng lại dashboard —
  biến `NEXT_PUBLIC_*` được nướng vào bundle lúc build, không đọc lúc chạy.
- **Kiểm 9 tài khoản đăng nhập** thật sự vào được, và mỗi người thấy đúng màn
  hình của vai mình.
