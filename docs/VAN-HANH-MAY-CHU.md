# Vận hành máy chủ ClinicAI (VPS `clinic-vps-moi`)

Sổ tay cho người có sudo (Tuyền/Quang). Viết 27/09/2026 sau kiểm toán
(`docs/KIEM-TOAN-HE-THONG-2709.md`). Mỗi việc: làm gì · lệnh · kiểm ra sao.

## 0. Xem sức khoẻ hằng ngày (không cần sudo)

| Muốn biết | Làm |
|---|---|
| Lỗi / cảnh báo của hệ thống | Đăng nhập tài khoản Quản lý → `/ops` tab **Lỗi & cảnh báo** (bộ canh gác chạy mỗi phút, tự mở/đóng) |
| Ai làm gì, lúc nào, mất bao lâu | `/ops` tab **Nhật ký vận hành** (chọn ngày, tìm khách; ô cam = chậm gấp đôi trung vị) |
| Nhanh từ máy Mac | `bash scripts/suc-khoe.sh` (prod /health, người đưa tin, container, đĩa, sao lưu) |
| Bản sao lưu ở Mac | `cat ~/Projects/ClinicAI-Backups/TRANG-THAI.txt` → phải "BÌNH THƯỜNG", tuổi < 30 giờ |
| Log một lỗi cụ thể (có "mã lỗi" 8 ký tự) | `ssh clinic-vps-moi` rồi `sudo journalctl CONTAINER_NAME=clinicai_prod-api-1 --since "2 hours ago" \| grep <mã>` — log giữ qua deploy từ 27/09 (đã chuyển journald). Container đang chạy thì `docker logs clinicai_prod-api-1` cũng được. Muốn bỏ `sudo`: `sudo usermod -aG systemd-journal clinicai` (đăng nhập lại) |

Cảnh báo tự gửi Telegram khi đặt `TELEGRAM_OPS_CHAT_ID` (id nhóm Telegram
riêng cho kỹ thuật) vào `.env.prod`, rồi deploy lại. Không đặt thì cảnh báo vẫn
hiện ở `/ops`.

## 1. Việc đã làm 27/09 (kiểm lại được)

- Journal lưu bền (`/var/log/journal`, trần 2G) + lịch collector `/ops` mỗi phút
  — `scripts/may-chu/bat-theo-doi-may-chu.sh`. Lần deploy kế tiếp in
  `==> log container: journald`.
- Kéo sao lưu về Mac chạy lại (trỏ `clinic-vps-moi`), gỡ đường hầm staging chết.

## 2. Việc CẦN SUDO — chạy một lần (5 phút)

```bash
ssh clinic-vps-moi
cd /home/clinicai/clinicai && git pull --ff-only
sudo ./scripts/may-chu/cung-co-may-chu.sh
```

Script làm: **swap 4G** (trước 0 — hết RAM là tiến trình bị giết thẳng) ·
**SSH chỉ nhận khoá** (14 ngày: 0 lần vào bằng mật khẩu, 45.562 lần dò mật khẩu)
· **fail2ban** cho SSH · dọn build cache Docker (~12G).

⚠️ SSH có **chốt tự hoàn tác 3 phút**: sau khi script chạy xong, MỞ MỘT CỬA SỔ
TERMINAL MỚI và `ssh clinic-vps-moi`. Vào được thì ở cửa sổ cũ gõ
`sudo systemctl stop hoan-tac-ssh.timer`. Không vào được thì cứ để 3 phút — máy
tự trả cấu hình SSH cũ.

ufw đã bật (chặn mọi chiều vào, mở 22/80/443) — không cần làm gì.

## 3. Hệ điều hành hết hỗ trợ → dựng lại trên Ubuntu 26.04 LTS

Ubuntu 25.04 hết hỗ trợ 15/01/2026: không còn bản vá bảo mật. Tuyền chốt 27/09:
**dựng máy mới LTS, chuyển dữ liệu, làm trong khung đêm có người xem.** Chọn **26.04 LTS** (máy báo đã có 26.04.1, hỗ trợ tới ~2031) thay vì 24.04. KHÔNG `do-release-upgrade` trên prod — nâng từ bản đã hết hỗ trợ dễ hỏng giữa chừng, không đường lùi.
Cách này có đường lùi (máy cũ còn nguyên tới khi máy mới chạy ổn).

1. **Thuê VPS mới** 26.04 LTS cùng cấu hình (4 vCPU, 8G RAM, ≥ 50G) — tài khoản
   nhà cung cấp là của Tuyền/Quang. Gắn ổ Viettel CFS như máy cũ.
2. **Dựng sẵn ban ngày** (không ảnh hưởng prod): cài Docker, clone repo, chép
   `.env.prod`, `.env.viettel` (qua `scp`, không dán vào chat), chạy
   `bat-theo-doi-may-chu.sh` + `cung-co-may-chu.sh`, dựng stack
   (`docker compose -f docker-compose.supabase.yml … up -d`, rồi
   `./scripts/deploy-backend.sh prod`) với database RỖNG để kiểm máy chạy được.
3. **Khung đêm (1h–4h), có người xem:**
   1. Máy cũ: dừng nhận khách (`docker compose -p clinicai_prod stop dashboard`),
      sao lưu lần cuối (`scripts/backup-db.sh`, lệnh đầy đủ ở CLAUDE.md).
   2. Chép bản sao lưu sang máy mới, khôi phục (`scripts/restore-db.sh`; hướng dẫn sống ở `~/Projects/ClinicAI-Backups/HUONG-DAN-PHUC-HOI.md` trên Mac),
      áp migration còn thiếu (`scripts/apply-pending-migrations.sh --apply`),
      `NOTIFY pgrst, 'reload schema'`.
   3. Chép `/var/lib/clinicai/media` nếu có tệp không nằm trên CFS.
   4. Đổi DNS `dr4women.io.vn` sang IP máy mới (TTL để thấp từ hôm trước).
   5. Kiểm: đăng nhập, mở một phiếu khám cũ, xem ảnh kết quả, `/health/su-kien`,
      `/ops` tab Lỗi & cảnh báo trống.
   6. Máy cũ giữ nguyên (tắt dashboard) ít nhất 7 ngày rồi mới huỷ.
4. Sửa `~/.ssh/config` (Host `clinic-vps-moi` → IP mới) và biến `MAY` trong
   `~/Projects/ClinicAI-Backups/keo-ve.sh` nếu đổi tên host.

## 4. Dựng lại Uptime Kuma (canh TỪ NGOÀI)

Bộ canh gác trong hệ thống canh "API sống mà nghiệp vụ kẹt"; Kuma canh "API
chết hẳn". Kuma trên máy hiện có 0 monitor.

```bash
ssh -L 3001:127.0.0.1:3001 clinic-vps-moi   # rồi mở http://localhost:3001 trên máy mình
```

Tạo tài khoản quản trị (lần đầu), rồi thêm monitor theo `monitoring/monitors.json`
(API /health/db, Dashboard, Caddy, `/health/su-kien`, TLS). Kênh báo: Telegram
bot + nhóm ops. Kiểm lại: `bash scripts/suc-khoe.sh` phần "Uptime Kuma".

## 5. Việc định kỳ

| Khi nào | Việc |
|---|---|
| Mỗi sáng | `/ops` tab Lỗi & cảnh báo; `TRANG-THAI.txt` ở Mac |
| Mỗi tháng | Diễn tập khôi phục: `scripts/restore-drill.sh` (bản sao chưa phục hồi thử = chưa phải bản sao) |
| Trước 16/10/2026 | **Gia hạn Viettel CFS** (nơi lưu ảnh/video kết quả + bản sao lưu) |
| Trước 07/11/2026 | Gia hạn Viettel DBaaS (nếu còn dùng) |
| 15/12/2026 | Chứng chỉ TLS — Caddy tự gia hạn; kiểm `/ops` không có cảnh báo |
