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
KUMA_PASS="${KUMA_PASS:?set KUMA_PASS to a strong unique password}"

docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" || {
    echo "ERROR: không thấy container $CONTAINER" >&2; exit 1; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# SINH HASH TRƯỚC KHI DỪNG CONTAINER — `docker exec` cần container đang chạy.
# Bản đầu của bản vá này dừng container rồi mới sinh hash, và nó hỏng ngay ở
# lần chạy đầu. Thứ tự ở đây không phải chuyện thẩm mỹ.
#
# bcrypt hash sinh bằng chính node trong container Kuma, để chắc chắn cùng thư
# viện và cùng cost với thứ Kuma dùng khi tự đăng ký.
HASH=$(docker exec -e KUMA_SETUP_PASS="$KUMA_PASS" "$CONTAINER" node -e "
const b=require('bcryptjs');
process.stdout.write(b.hashSync(process.env.KUMA_SETUP_PASS, 10));
" 2>/dev/null)
[ -n "$HASH" ] || { echo "ERROR: không sinh được hash mật khẩu" >&2; exit 1; }


# DỪNG KUMA TRƯỚC KHI ĐỌC DB. Đây là lỗi của chính bản trước: nó `docker cp` mỗi
# `kuma.db` ra, sửa, rồi chép ngược vào — bỏ mặc `kuma.db-wal`.
#
# SQLite của Kuma chạy chế độ WAL, và đo ngày 11/08/2026 thì `kuma.db-wal` nặng
# 523KB, gần bằng chính file `.db` (544KB). Nghĩa là phần lớn dữ liệu mới nhất
# nằm trong WAL chứ không trong `.db`. Chép `.db` ra là đọc một bản CŨ; chép
# ngược vào là đặt một `.db` không khớp với `-wal`/`-shm` còn nguyên trong
# container. Khởi động lại, SQLite phát lại WAL cũ đè lên — thay đổi của script
# mất, hoặc tệ hơn là DB hỏng.
#
# Trớ trêu là chân script này đã tự cảnh báo "ĐỌC DB PHẢI QUA CONTAINER... docker
# cp mỗi file .db sẽ đọc ra bản cũ" — biết luật mà thân script vẫn phạm.
#
# Dừng container thì Kuma đóng DB sạch sẽ, WAL được gộp vào `.db`, và ba file
# thành nhất quán. Ngắt vài giây, đổi lại một lần cấu hình không mất dữ liệu.
echo "  dừng $CONTAINER để đọc DB nhất quán (WAL được gộp lúc đóng)"
docker stop "$CONTAINER" >/dev/null
docker cp "$CONTAINER:/app/data/kuma.db" "$TMP/kuma.db" >/dev/null

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
    (f"API /health/db",     "http://api:8000/health/db",     60),
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

# --- monitor kiểu PUSH: sao lưu đêm ----------------------------------------
#
# BA MONITOR HTTP Ở TRÊN CANH "ỨNG DỤNG CÒN SỐNG". Chúng KHÔNG canh được sự cố
# đã thật sự xảy ra ở dự án này: bản sao lưu ngoài máy hỏng IM LẶNG nhiều đêm
# liền. Unit systemd có dấu `-` trước lệnh đẩy, nên systemd bỏ qua mã lỗi và
# `systemctl status` vẫn xanh trong khi chưa đêm nào bản sao rời khỏi máy chủ.
#
# Canh cái chưa từng hỏng mà bỏ cái đã hỏng thì bảng giám sát chỉ để nhìn cho
# yên tâm. Một monitor HTTP không bao giờ phát hiện được điều này, vì API vẫn
# khoẻ trong suốt thời gian đó — chính xác là vấn đề: hệ thống trông hoàn hảo
# trong khi lưới an toàn của nó đã rách.
#
# Monitor PUSH đảo chiều: Kuma KHÔNG đi hỏi ai cả, nó chờ được báo về. Script
# sao lưu gọi URL push khi và chỉ khi dump chạy xong và verify xong. Quá hạn mà
# im lặng thì Kuma tự chuyển đỏ. Im lặng trở thành tín hiệu, thay vì trở thành
# sự yên tâm.
#
# 26 giờ, không phải 24: sao lưu chạy 02:15: đúng 24h thì một lần chạy chậm vài
# phút cũng thành báo động giả, và báo động giả lặp lại là thứ khiến người ta
# tắt chuông.
import secrets, string

PUSH = [("Sao lưu đêm", 26 * 3600)]
for name, interval in PUSH:
    full = f"{name} · {env}"
    if c.execute("SELECT 1 FROM monitor WHERE name=?", (full,)).fetchone():
        tok = c.execute("SELECT push_token FROM monitor WHERE name=?", (full,)).fetchone()[0]
        print(f"  monitor: '{full}' đã có")
    else:
        # Cột `push_token` là VARCHAR(20) — đo bằng PRAGMA table_info. Dùng
        # đúng 20 ký tự chữ-số: vừa cột, và không có ký tự nào cần thoát khi
        # ghép vào URL. `token_urlsafe` sinh tới 22 ký tự và có `-`/`_`.
        tok = "".join(secrets.choice(string.ascii_letters + string.digits)
                      for _ in range(20))
        c.execute("""INSERT INTO monitor
            (name, active, user_id, interval, type, weight, maxretries,
             ignore_tls, upside_down, maxredirects, accepted_statuscodes_json,
             retry_interval, resend_interval, timeout, push_token)
            VALUES (?,1,?,?,'push',2000,0,0,0,10,?,3600,0,30,?)""",
            (full, uid, interval, ok, tok))
        print(f"  monitor: + {full}  (kiểu push, quá {interval // 3600}h không báo về là đỏ)")
    with open("/tmp/kuma-push-token", "w") as f:
        f.write(tok)

c.commit()
n_mon = c.execute("SELECT count(*) FROM monitor WHERE active=1").fetchone()[0]
n_not = c.execute("SELECT count(*) FROM notification").fetchone()[0]
print(f"  → {n_mon} monitor đang bật, {n_not} kênh báo động")
PY

docker cp "$TMP/kuma.db" "$CONTAINER:/app/data/kuma.db" >/dev/null

# `-wal`/`-shm` cũ giờ đã lạc hậu so với `.db` vừa ghi vào. Container đang DỪNG
# nên không ai đang mở DB — xoá chúng là an toàn, và bỏ lại là mời SQLite phát
# lại một WAL không còn khớp.
docker run --rm -v "clinicai_${ENVIRONMENT}_kuma_data:/d" alpine \
    sh -c 'rm -f /d/kuma.db-wal /d/kuma.db-shm' 2>/dev/null || true

docker start "$CONTAINER" >/dev/null
echo "  đã khởi động lại $CONTAINER"

# Ghi token push ra nơi script sao lưu đọc được. Không in ra màn hình: ai có
# token là đẩy được nhịp tim giả, tức là làm monitor xanh trong khi sao lưu đã
# chết — đúng thứ nó sinh ra để ngăn.
if [ -f /tmp/kuma-push-token ]; then
    mkdir -p "$HOME/.config/clinicai"
    install -m 600 /tmp/kuma-push-token "$HOME/.config/clinicai/kuma-push-backup"
    rm -f /tmp/kuma-push-token
    echo "  token push đã ghi: ~/.config/clinicai/kuma-push-backup (quyền 600)"
fi

for _ in $(seq 1 30); do
    docker exec "$CONTAINER" node -e "require('http').get('http://127.0.0.1:3001',r=>process.exit(0)).on('error',()=>process.exit(1))" 2>/dev/null && break
    sleep 2
done

cat <<EOF

  Uptime Kuma: http://127.0.0.1:$([ "$ENVIRONMENT" = prod ] && echo 3001 || echo 3002)
    tài khoản: ${KUMA_USER} (mật khẩu đã được đặt từ KUMA_PASS và không in ra)

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

  ĐỌC DB PHẢI QUA CONTAINER. SQLite bật WAL, nên docker cp mỗi file .db sẽ
  đọc ra bản cũ và mọi thứ trông như chưa từng thay đổi.
EOF
