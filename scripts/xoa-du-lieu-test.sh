#!/usr/bin/env bash
#
# XOÁ DỮ LIỆU BỆNH NHÂN ĐỂ CHẠY LẠI TỪ ĐẦU — chỉ dùng khi dữ liệu đang có là
# dữ liệu chạy thử.
#
# GIỮ NGUYÊN toàn bộ cấu hình: nhân sự, cơ sở, phòng, dịch vụ, bảng giá, lịch
# làm việc, luật đặt lịch, tuyến điều phối. Chỉ xoá thứ sinh ra từ việc tiếp
# nhận và khám bệnh.
#
# BA LỚP CHẶN, vì đây là lệnh không có đường lùi:
#   1. Bắt buộc có bản sao lưu chụp trong vòng 30 phút. Không có thì tự chụp.
#   2. In ra CHÍNH XÁC số dòng sẽ xoá, rồi đợi gõ đúng chữ để xác nhận.
#   3. Chạy trong MỘT transaction — hỏng giữa chừng thì không xoá gì cả.
#
# Dùng:  ./scripts/xoa-du-lieu-test.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.prod}"
BACKUP_DIR="$HOME/backups/clinicai"

command -v psql >/dev/null || { echo "cần psql: brew install libpq" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "không thấy $ENV_FILE" >&2; exit 1; }

# psql không hiểu scheme "+asyncpg" của SQLAlchemy và sẽ ÂM THẦM rơi về socket
# local — tức là báo thành công trong khi không hề đụng vào database thật.
DSN="$(grep -m1 '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | sed 's/+asyncpg//')"
case "$DSN" in postgresql://*|postgres://*) : ;; *) echo "DATABASE_URL sai" >&2; exit 1 ;; esac

# ── 1. Sao lưu ─────────────────────────────────────────────────────────────
recent="$(find "$BACKUP_DIR" -name 'clinicai_production_*.sql.gz' -mmin -30 2>/dev/null | head -1)"
if [ -z "$recent" ]; then
  echo "==> chưa có bản lưu nào trong 30 phút — chụp một bản trước"
  "$ROOT/scripts/backup-db.sh"
  recent="$(find "$BACKUP_DIR" -name 'clinicai_production_*.sql.gz' -mmin -30 | head -1)"
fi
[ -n "$recent" ] || { echo "!! không tạo được bản lưu — DỪNG" >&2; exit 1; }
echo "==> bản lưu dùng để quay lại: $recent"
echo "    (cách khôi phục: docs/khoi-phuc-du-lieu.md)"
echo

# ── 2. Cho xem trước ───────────────────────────────────────────────────────
echo "==> SẼ XOÁ:"
psql "$DSN" -X -q -c "
select rpad(t,26) || lpad(n::text, 6) as \" \"
  from (
    select 'appointment' t, count(*) n from appointment
    union all select 'visit', count(*) from visit
    union all select 'patient', count(*) from patient
    union all select 'work_item', count(*) from work_item
    union all select 'cskh_action', count(*) from cskh_action
    union all select 'payment', count(*) from payment
    union all select 'prescription', count(*) from prescription
    union all select 'lab_result', count(*) from lab_result
    union all select 'service_log', count(*) from service_log
    union all select 'clinical_form_response', count(*) from clinical_form_response
    union all select 'ultrasound_record', count(*) from ultrasound_record
    union all select 'slot_hold', count(*) from slot_hold
    union all select 'event_log', count(*) from event_log
  ) x where n > 0 order by n desc;"
echo
echo "==> GIỮ NGUYÊN:"
psql "$DSN" -X -q -c "
select rpad(t,26) || lpad(n::text, 6) as \" \"
  from (
    select 'staff' t, count(*) n from staff
    union all select 'clinic_location', count(*) from clinic_location
    union all select 'clinic_room', count(*) from clinic_room
    union all select 'service_type', count(*) from service_type
    union all select 'service_price', count(*) from service_price
    union all select 'work_roster', count(*) from work_roster
    union all select 'booking_channel', count(*) from booking_channel
    union all select 'route_template', count(*) from route_template
  ) x order by n desc;"
echo

printf 'Gõ đúng chữ  XOA HET  rồi Enter để tiếp tục (bất kỳ chữ nào khác = huỷ): '
read -r answer
[ "$answer" = "XOA HET" ] || { echo "đã huỷ, không xoá gì."; exit 0; }

# ── 3. Xoá trong một transaction ───────────────────────────────────────────
# Thứ tự theo khoá ngoại: con trước, cha sau. ON_ERROR_STOP + một transaction
# nghĩa là vấp bảng nào thì toàn bộ quay lại như cũ.
psql "$DSN" -X -q -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DELETE FROM clinical_release;
DELETE FROM visit_amendment;
DELETE FROM clinical_form_response;
DELETE FROM prescription;
DELETE FROM lab_result;
DELETE FROM service_log;
DELETE FROM payment;
DELETE FROM ultrasound_record;
DELETE FROM work_item_event;
DELETE FROM work_item_dependency;
DELETE FROM work_item;
DELETE FROM visit_route;
DELETE FROM visit;
DELETE FROM slot_hold;
DELETE FROM cskh_action;
DELETE FROM staff_task;
DELETE FROM appointment;
DELETE FROM care_episode;
DELETE FROM patient;
-- event_log xoá SAU CÙNG: nó ghi nhật ký của chính mấy bảng trên, và giữ lại
-- nhật ký của những dòng đã biến mất chỉ làm màn Nhật ký thao tác đầy những
-- tham chiếu trỏ vào hư không.
DELETE FROM event_log;
COMMIT;
SQL

echo
echo "==> xong. Còn lại:"
psql "$DSN" -X -q -c "
select 'bệnh nhân=' || (select count(*) from patient)
    || '  lịch hẹn=' || (select count(*) from appointment)
    || '  lượt khám=' || (select count(*) from visit)
    || '  |  nhân sự=' || (select count(*) from staff)
    || '  phòng=' || (select count(*) from clinic_room)
    || '  dịch vụ=' || (select count(*) from service_type) as \" \";"
