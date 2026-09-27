#!/bin/bash
# SIẾT MÁY CHỦ (27/09/2026 — kiểm toán hệ thống, Tuyền: "xử lý hết đi cho chạy tốt").
#
#     cd /home/clinicai/clinicai && sudo ./scripts/may-chu/cung-co-may-chu.sh
#     # rồi từ MÁY KHÁC mở một phiên SSH mới; vào được thì:
#     sudo systemctl stop hoan-tac-ssh.timer
#
# Chạy lại bao nhiêu lần cũng được. Làm bốn việc:
#   1. SWAP 4G (+ swappiness 10). Trước đó 0 swap: hết RAM là kernel giết thẳng
#      tiến trình (thường là Postgres / api) — không có đệm, không có báo trước.
#   2. SSH CHỈ NHẬN KHOÁ. Đo 14 ngày tới 27/09: 0 lần vào bằng mật khẩu thành
#      công, 45.562 lần dò mật khẩu thất bại. Tắt mật khẩu = dò bao nhiêu cũng vô
#      ích. CÓ CHỐT HOÀN TÁC: 3 phút sau tự gỡ cấu hình mới, TRỪ KHI người chạy
#      đã thử vào bằng phiên SSH MỚI thành công và dừng timer `hoan-tac-ssh`.
#   3. fail2ban cho sshd — chặn IP dò liên tục (bớt rác log, bớt tải).
#   4. Dọn build cache Docker (~12G, không phải dữ liệu — build lại là có).
#      KHÔNG xoá volume: volume mồ côi có thể còn dữ liệu, để người xem quyết.
#
# ufw đã bật sẵn (deny vào, mở 22/80/443) — không đụng.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Cần sudo." >&2; exit 1; }

echo "==> [1/4] swap"
if swapon --show=NAME --noheadings | grep -q .; then
  echo "   đã có swap: $(swapon --show=NAME,SIZE --noheadings | tr '\n' ' ')"
else
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "   bật /swapfile 4G"
fi
printf 'vm.swappiness=10\n' > /etc/sysctl.d/99-clinicai.conf
sysctl -q -p /etc/sysctl.d/99-clinicai.conf
echo "   $(free -h | awk 'NR==3{print "swap: " $2}') · swappiness $(cat /proc/sys/vm/swappiness)"

echo "==> [2/4] SSH chỉ nhận khoá"
DROP=/etc/ssh/sshd_config.d/00-clinicai.conf
# 00- để đứng ĐẦU: sshd lấy giá trị GẶP TRƯỚC, mà 50-cloud-init.conf đang bật mật khẩu.
cat > "$DROP" <<'CFG'
# ClinicAI 27/09/2026 — xem scripts/may-chu/cung-co-may-chu.sh
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
MaxAuthTries 3
CFG
chmod 644 "$DROP"
if ! sshd -t; then
  rm -f "$DROP"
  echo "!! cấu hình SSH mới không hợp lệ — đã gỡ, giữ nguyên như cũ" >&2
  exit 1
fi
systemctl stop hoan-tac-ssh.timer 2>/dev/null || true
systemctl reset-failed hoan-tac-ssh.service 2>/dev/null || true
systemd-run --quiet --unit=hoan-tac-ssh --on-active=180 \
  /bin/sh -c "rm -f $DROP && systemctl reload ssh"
systemctl reload ssh
echo "   $(sshd -T | grep -E '^passwordauthentication ')"
echo "   !! 3 phút nữa TỰ HOÀN TÁC nếu không dừng: sudo systemctl stop hoan-tac-ssh.timer"

echo "==> [3/4] fail2ban"
if ! command -v fail2ban-client >/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban >/dev/null \
    || echo "!! không cài được fail2ban (kho gói của bản Ubuntu hết hỗ trợ?) — bỏ qua"
fi
if command -v fail2ban-client >/dev/null; then
  cat > /etc/fail2ban/jail.d/clinicai.local <<'JAIL'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
JAIL
  systemctl enable --now fail2ban >/dev/null 2>&1 || true
  systemctl restart fail2ban
  sleep 2
  echo "   $(fail2ban-client status sshd 2>/dev/null | grep -E 'Currently banned' | xargs)"
fi

echo "==> [4/4] dọn build cache Docker"
docker builder prune -af 2>/dev/null | tail -1 || true
df -h / | awk 'NR==2{print "   đĩa: " $5 " đã dùng, trống " $4}'

echo
echo "XONG. Nhớ: mở phiên SSH MỚI thử vào, được thì dừng timer hoàn tác."
