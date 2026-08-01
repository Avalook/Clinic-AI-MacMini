#!/usr/bin/env bash
# Cấu hình Uptime Kuma: tài khoản admin + monitor cho từng thành phần.
#
# Container Uptime Kuma đã chạy 10 ngày với ĐÚNG 0 monitor và 0 kênh báo động.
# Nó "đang giám sát" theo nghĩa tiến trình còn sống, và theo mọi nghĩa khác thì
# không: không có đường nào từ "API chết lúc 2 giờ sáng" tới một con người.
# Một container giám sát chưa cấu hình còn tệ hơn không có, vì nhìn vào danh
# sách container thấy nó xanh thì tưởng đã được canh.
#
# Kuma không có REST API để cấu hình (mọi thứ qua socket.io), nên script ghi
# thẳng vào SQLite rồi khởi động lại container để Kuma nạp lại. Chạy lại được:
# monitor nhận diện theo tên, không nhân bản.
#
#   scripts/setup-uptime-kuma.sh [prod|staging]
#
# BÁO ĐỘNG cần credential mà repo không có (Telegram bot token / SMTP). Script
# tạo monitor và NÓI RÕ là chưa có kênh báo — xem cuối output.

set -euo pipefail

ENVIRONMENT="${1:-staging}"
case "$ENVIRONMENT" in prod|staging) : ;; *) echo "usage: $0 [prod|staging]" >&2; exit 2 ;; esac

CONTAINER="clinicai_${ENVIRONMENT}-uptime-kuma-1"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUMA_USER="${KUMA_USER:-admin}"
KUMA_PASS="${KUMA_PASS:-clinicai-kuma-2026}"

docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" || {
    echo "ERROR: không thấy container $CONTAINER" >&2; exit 1; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
docker cp "$CONTAINER:/app/data/kuma.db" "$TMP/kuma.db" >/dev/null

# bcrypt hash sinh bằng chính node trong container Kuma, để chắc chắn cùng thư
# viện và cùng cost với thứ Kuma dùng khi tự đăng ký.
HASH=$(docker exec "$CONTAINER" node -e "
const b=require('bcryptjs');
process.stdout.write(b.hashSync('$KUMA_PASS', 10));
" 2>/dev/null)
[ -n "$HASH" ] || { echo "ERROR: không sinh được hash mật khẩu" >&2; exit 1; }

python3 - "$TMP/kuma.db" "$KUMA_USER" "$HASH" "$ENVIRONMENT" <<'PY'
import sqlite3, sys, json
db, user, pw_hash, env = sys.argv[1:5]
c = sqlite3.connect(db)

# --- tài khoản admin -------------------------------------------------------
row = c.execute("SELECT id FROM user LIMIT 1").fetchone()
if row:
    uid = row[0]
    c.execute("UPDATE user SET password=?, active=1 WHERE id=?", (pw_hash, uid))
    print(f"  admin: cập nhật mật khẩu (id={uid})")
else:
    cur = c.execute(
        "INSERT INTO user (username, password, active, timezone) VALUES (?,?,1,?)",
        (user, pw_hash, "Asia/Ho_Chi_Minh"))
    uid = cur.lastrowid
    print(f"  admin: tạo mới '{user}'")

# --- monitor ---------------------------------------------------------------
# Tên container, không phải 127.0.0.1: Kuma sống trong cùng mạng docker, nên
# 127.0.0.1 với nó là chính nó. Đây đúng là lỗi đã làm hỏng đăng nhập ở
# dashboard, chỉ khác vị trí.
suffix = f"clinicai_{env}"
MONITORS = [
    # (tên, url, giây, mô tả vì sao theo dõi)
    (f"API /health",        "http://api:8000/health",        60),
    (f"Dashboard /health",  "http://dashboard:3000/health",  60),
    (f"Caddy (ingress)",    "http://caddy:80/health",        60),
]
# Kuma đòi DẢI dạng CHUỖI, không phải số. Đưa số vào thì nó log
# "Accepted status code not a string" cho từng mã rồi coi mọi phản hồi là hỏng —
# kể cả 200. Monitor vẫn chạy, vẫn đỏ, và lý do nằm trong log chứ không hiện ra
# màn hình.
ok = json.dumps(["200-299", "300-399"])
added = 0
for name, url, interval in MONITORS:
    full = f"{name} · {env}"
    if c.execute("SELECT 1 FROM monitor WHERE name=?", (full,)).fetchone():
        print(f"  monitor: '{full}' đã có")
        continue
    c.execute("""INSERT INTO monitor
        (name, active, user_id, interval, url, type, weight, maxretries,
         ignore_tls, upside_down, maxredirects, accepted_statuscodes_json,
         retry_interval, resend_interval, timeout)
        VALUES (?,1,?,?,?,'http',2000,2,0,0,10,?,60,0,30)""",
        (full, uid, interval, url, ok))
    added += 1
    print(f"  monitor: + {full}  ({url}, mỗi {interval}s)")

c.commit()
n_mon = c.execute("SELECT count(*) FROM monitor WHERE active=1").fetchone()[0]
n_not = c.execute("SELECT count(*) FROM notification").fetchone()[0]
print(f"  → {n_mon} monitor đang bật, {n_not} kênh báo động")
PY

docker cp "$TMP/kuma.db" "$CONTAINER:/app/data/kuma.db" >/dev/null
docker restart "$CONTAINER" >/dev/null
echo "  đã khởi động lại $CONTAINER"

for _ in $(seq 1 30); do
    docker exec "$CONTAINER" node -e "require('http').get('http://127.0.0.1:3001',r=>process.exit(0)).on('error',()=>process.exit(1))" 2>/dev/null && break
    sleep 2
done

cat <<EOF

  Uptime Kuma: http://127.0.0.1:$([ "$ENVIRONMENT" = prod ] && echo 3001 || echo 3002)
    tài khoản: ${KUMA_USER} / ${KUMA_PASS}

  CHƯA CÓ KÊNH BÁO ĐỘNG. Monitor sẽ chuyển đỏ trên màn hình, nhưng không ai
  được báo khi API chết lúc 2 giờ sáng — đúng cái khoảng trống mà bảng giám sát
  này lẽ ra phải lấp.

  Muốn có báo động Telegram, cần 2 thứ rồi thêm ở Settings → Notifications:
    1. Bot token   — chat với @BotFather trên Telegram, /newbot
    2. Chat ID     — chat với @userinfobot, nó trả về id

  Kiểm monitor có thật sự phát hiện sự cố (không chỉ nằm im màu xanh):
    docker stop clinicai_${ENVIRONMENT}-api-1 && sleep 160
    docker exec ${CONTAINER} sh -c \
      "sqlite3 /app/data/kuma.db 'SELECT name FROM monitor'"
    docker start clinicai_${ENVIRONMENT}-api-1
  Phải chờ >= 2.5 chu kỳ (160s): tắt rồi bật trong vòng một chu kỳ thì sự cố
  lọt giữa hai lần kiểm và monitor không bao giờ thấy — tôi đã tự lừa mình một
  lần đúng như thế.

  ĐỌC DB PHẢI QUA CONTAINER. SQLite bật WAL, nên `docker cp` mỗi file .db sẽ
  đọc ra bản cũ và mọi thứ trông như chưa từng thay đổi.
EOF
