#!/usr/bin/env bash
# Đứng thay chỗ `pg_dump` khi database chạy trong container trên chính máy này.
#
# VÌ SAO CẦN. Trên VPS, `pg_dump` của hệ điều hành là bản 16.14 còn máy chủ
# database là 17.10. pg_dump từ chối dump một máy chủ mới hơn chính nó — nên
# đường sao lưu trên host là ngõ cụt, không phải chuyện cấu hình.
#
# Cài thêm gói pg_dump 17 lên host là một phiên bản nữa phải nhớ nâng cấp mỗi
# lần đổi Postgres. Dump từ TRONG container thì phiên bản luôn khớp, mãi mãi,
# vì nó là cùng một cài đặt.
#
# Dùng với backup-db.sh:
#   PG_DUMP_BIN=scripts/pg-dump-qua-container.sh \
#   CLINIC_DB_CONTAINER=clinicai_db  ./scripts/backup-db.sh
#
# CHỐT CHỐNG DUMP NHẦM DATABASE. Cầu nối này bỏ qua PGHOST/PGPORT của người gọi
# — bên trong container thì database luôn ở localhost:5432. Bỏ qua một cách im
# lặng nghĩa là: backup-db.sh tưởng nó đang sao lưu database A, còn ta lại dump
# database B, và tên file vẫn ghi A. Một bản sao lưu dán nhãn sai còn tệ hơn
# không có bản nào — người ta sẽ tin nó vào đúng lúc cần nhất.
#
# Nên: PGHOST phải TRÙNG tên container. Trên VPS, DATABASE_URL của prod ghi
# `@clinicai_db:5432` và container tên đúng `clinicai_db` — chúng vốn là một
# thứ. Lệch nhau là dừng.

set -euo pipefail

CONTAINER="${CLINIC_DB_CONTAINER:-}"
[ -n "$CONTAINER" ] || {
    echo "pg-dump-qua-container: thiếu CLINIC_DB_CONTAINER" >&2
    exit 1
}

if [ -n "${PGHOST:-}" ] && [ "$PGHOST" != "$CONTAINER" ]; then
    echo "pg-dump-qua-container: DỪNG — người gọi muốn dump '$PGHOST' nhưng" >&2
    echo "  cầu nối này chạy trong container '$CONTAINER'. Hai database khác" >&2
    echo "  nhau; bản sao lưu sẽ mang tên sai. Sửa CLINIC_DB_CONTAINER hoặc" >&2
    echo "  DATABASE_URL cho khớp." >&2
    exit 1
fi

docker inspect "$CONTAINER" >/dev/null 2>&1 || {
    echo "pg-dump-qua-container: không có container '$CONTAINER'" >&2
    exit 1
}

# `--version` phải trả lời được mà không cần container chạy đúng vai database —
# backup-db.sh gọi nó ở bước tiền kiểm để ghi vào nhật ký.
DB_USER="${PGUSER:-postgres}"
DB_NAME="${PGDATABASE:-postgres}"

# -i chứ không -it: không có TTY khi chạy từ systemd, và pg_dump ghi ra stdout.
# Không truyền -h/-p: bên trong container là socket cục bộ, xác thực trust.
exec docker exec -i "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" "$@"
