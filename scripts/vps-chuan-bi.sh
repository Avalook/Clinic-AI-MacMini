#!/usr/bin/env bash
#
# Chuẩn bị một VPS trống để chạy ClinicAI. CHẠY MỘT LẦN, TRÊN VPS, BẰNG root.
#
#   ssh root@<IP> -p <PORT> 'bash -s' < scripts/vps-chuan-bi.sh
#
# Làm bốn việc, theo đúng thứ tự đó:
#   1. tạo người dùng thường `clinicai` — không chạy ứng dụng bằng root
#   2. bật tường lửa, chỉ mở SSH + 80 + 443
#   3. cài Docker
#   4. siết SSH: khoá thay mật khẩu, cấm root đăng nhập
#
# VIỆC 4 LÀ VIỆC KHÓA CỬA, và nó CHỈ chạy khi đã có khoá công khai nằm sẵn cho
# `clinicai`. Siết trước khi có khoá là tự nhốt mình ở ngoài — lúc ấy chỉ còn
# đường vào bằng console của Vietnix.

set -euo pipefail

NGUOI_DUNG="${CLINICAI_USER:-clinicai}"
SSH_PORT="${SSH_PORT:-22}"

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
canh() { printf '\033[33m!! %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "phải chạy bằng root" >&2; exit 1; }

# ---------------------------------------------------------------------------
log "1/4 · người dùng thường"
# ---------------------------------------------------------------------------
# Ứng dụng KHÔNG chạy bằng root. Một lỗ trong container mà container ấy chạy
# bằng root của máy thì lỗ ấy là cả máy chủ.
if id "$NGUOI_DUNG" >/dev/null 2>&1; then
    echo "đã có người dùng $NGUOI_DUNG"
else
    adduser --disabled-password --gecos "" "$NGUOI_DUNG"
    echo "đã tạo $NGUOI_DUNG (không đặt mật khẩu — chỉ vào bằng khoá SSH)"
fi
usermod -aG sudo "$NGUOI_DUNG" 2>/dev/null || usermod -aG wheel "$NGUOI_DUNG"

# SUDO KHÔNG CẦN MẬT KHẨU — và đây là sửa một lỗi đã gặp thật.
#
# `adduser --disabled-password` tạo tài khoản KHÔNG có mật khẩu. Thêm vào nhóm
# sudo là chưa đủ: sudo vẫn hỏi mật khẩu, mà tài khoản không có mật khẩu nào để
# trả lời. Cộng với việc bước 4 cấm luôn root đăng nhập, kết quả là MỘT MÁY CHỦ
# KHÔNG CÒN AI QUẢN TRỊ ĐƯỢC — đường cứu duy nhất là console của Vietnix.
#
# (Lần đầu chạy script này đã rơi đúng vào đó. Cứu được nhờ nhóm `docker`, xem
# đoạn dưới.)
#
# VÀ NOPASSWD Ở ĐÂY KHÔNG NỚI THÊM QUYỀN NÀO. Tài khoản này thuộc nhóm `docker`,
# mà nhóm docker TƯƠNG ĐƯƠNG root: ai chạy được container là gắn được `/` của
# máy chủ vào container rồi ghi bất cứ đâu. Chính trình cài Docker cũng cảnh báo
# câu ấy. Nên NOPASSWD chỉ làm cho quyền vốn đã có trở nên dùng được — thứ bảo
# vệ thật là khoá SSH và tường lửa, không phải lời hỏi mật khẩu của sudo.
install -d -m 755 /etc/sudoers.d
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$NGUOI_DUNG" > "/etc/sudoers.d/90-$NGUOI_DUNG"
chmod 440 "/etc/sudoers.d/90-$NGUOI_DUNG"
visudo -c -q && echo "đã cấp sudo cho $NGUOI_DUNG"

# Chép khoá công khai của root sang, để lần SSH tới vào thẳng bằng người dùng
# thường. Không có bước này thì siết SSH ở việc 4 sẽ khoá luôn cả mình.
if [ -f /root/.ssh/authorized_keys ]; then
    install -d -m 700 -o "$NGUOI_DUNG" -g "$NGUOI_DUNG" "/home/$NGUOI_DUNG/.ssh"
    install -m 600 -o "$NGUOI_DUNG" -g "$NGUOI_DUNG" \
        /root/.ssh/authorized_keys "/home/$NGUOI_DUNG/.ssh/authorized_keys"
    echo "đã chép khoá công khai sang $NGUOI_DUNG"
    CO_KHOA=1
else
    canh "root chưa có authorized_keys — BỎ QUA bước siết SSH ở việc 4."
    canh "Chạy ssh-copy-id từ máy Mac rồi chạy lại script này."
    CO_KHOA=0
fi

# ---------------------------------------------------------------------------
log "2/4 · tường lửa"
# ---------------------------------------------------------------------------
# Mặc định CHẶN HẾT rồi mở ba cổng. Ngược lại — mở hết rồi chặn dần — là cách
# để quên mất một cổng và không bao giờ biết.
if command -v ufw >/dev/null 2>&1; then
    ufw --force reset >/dev/null
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow "${SSH_PORT}/tcp" comment 'SSH'
    ufw allow 80/tcp   comment 'HTTP - Caddy chuyển hướng sang HTTPS'
    ufw allow 443/tcp  comment 'HTTPS'
    ufw --force enable
    ufw status numbered
else
    canh "không có ufw — cài rồi chạy lại, hoặc tự cấu hình firewalld"
fi

# CỔNG POSTGRES KHÔNG BAO GIỜ MỞ RA NGOÀI. Ứng dụng nói chuyện với database qua
# mạng nội bộ của Docker (hoặc qua đường riêng tới Viettel IDC). Mở 5432 ra
# Internet là mời cả thế giới thử mật khẩu.

# ---------------------------------------------------------------------------
log "3/4 · Docker"
# ---------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
    echo "đã có $(docker --version)"
else
    curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker "$NGUOI_DUNG"
systemctl enable --now docker

# Bó log lại. Một sự cố ghi log liên tục sẽ ăn hết đĩa, và lúc đĩa đầy thì
# Postgres dừng ghi — hỏng ở chỗ xa nhất so với nguyên nhân.
install -d /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" }
}
JSON
systemctl restart docker
docker --version
docker compose version

# ---------------------------------------------------------------------------
log "4/4 · siết SSH"
# ---------------------------------------------------------------------------
if [ "$CO_KHOA" -eq 1 ]; then
    cat > /etc/ssh/sshd_config.d/99-clinicai.conf <<CONF
# Mật khẩu là thứ đoán được; khoá thì không. Vietnix gửi mật khẩu root qua
# email — nếu hộp thư ấy lộ thì cả máy chủ lộ theo.
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
CONF
    sshd -t && systemctl reload ssh 2>/dev/null || systemctl reload sshd
    echo "đã tắt đăng nhập bằng mật khẩu và cấm root"
    canh "GIỮ NGUYÊN phiên SSH này. Mở một cửa sổ MỚI và thử:"
    canh "    ssh $NGUOI_DUNG@<IP> -p $SSH_PORT"
    canh "Vào được thì mới đóng phiên cũ."
else
    canh "bỏ qua — chưa có khoá công khai"
fi

log "xong"
echo "  người dùng : $NGUOI_DUNG"
echo "  Docker     : $(docker --version | cut -d, -f1)"
echo "  cổng mở    : $SSH_PORT (SSH) · 80 · 443"
