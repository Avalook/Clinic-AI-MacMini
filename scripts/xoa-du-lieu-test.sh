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
    union all select 'clinical_data_consent', count(*) from clinical_data_consent
    union all select 'patient_link', count(*) from patient_link
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

-- BẢY BẢNG CẤM XOÁ CỨNG, và cái cấm đó ĐÚNG.
--
--     prevent_hard_delete()   appointment · clinical_record · lab_result
--                             patient · payment · visit
--     enforce_append_only()   event_log
--
-- HAI HÀM KHÁC NHAU, và lần chạy thứ hai vấp đúng chỗ đó: tôi liệt kê sáu bảng
-- theo `prevent_hard_delete` rồi tưởng là đủ, còn event_log dùng hàm riêng nên
-- lọt lưới. Danh sách này phải lấy theo HÀNH VI (trigger nào bắt DELETE), không
-- theo tên hàm:
--
--     select c.relname, t.tgname from pg_trigger t
--       join pg_class c on c.oid=t.tgrelid
--      where not t.tgisinternal and t.tgtype::int & 8 = 8;
--
-- `prevent_hard_delete()` giữ cho hồ sơ bệnh án là thứ chỉ ghi thêm: huỷ một
-- lịch hẹn là đổi trạng thái, không phải làm cho nó chưa từng tồn tại. Lần chạy
-- đầu của script này đã đâm vào đúng cái chốt ấy và quay lại sạch — nó làm đúng
-- việc của nó.
--
-- Ở đây ta cố tình mở khoá, VÀ ĐÓNG LẠI TRONG CÙNG GIAO DỊCH. Nếu bất kỳ lệnh
-- nào phía dưới hỏng thì ROLLBACK trả cả dữ liệu lẫn trigger về nguyên trạng —
-- không có cửa nào để prod đứng dậy mà thiếu lớp bảo vệ này.
--
-- Chỉ dùng khi dữ liệu đang có là dữ liệu chạy thử. Với dữ liệu bệnh nhân thật,
-- câu trả lời đúng là KHÔNG XOÁ.
ALTER TABLE appointment     DISABLE TRIGGER trg_appointment_no_delete;
ALTER TABLE clinical_record DISABLE TRIGGER trg_clinical_record_no_delete;
ALTER TABLE event_log       DISABLE TRIGGER trg_event_log_no_delete;
ALTER TABLE lab_result      DISABLE TRIGGER trg_lab_result_no_delete;
ALTER TABLE patient         DISABLE TRIGGER trg_patient_no_delete;
ALTER TABLE payment         DISABLE TRIGGER trg_payment_no_delete;
ALTER TABLE visit           DISABLE TRIGGER trg_visit_no_delete;

-- TRÌNH TỰ NÀY LẤY TỪ ĐỒ THỊ KHOÁ NGOẠI, KHÔNG PHẢI TỪ TRÍ NHỚ.
--
-- Hai lần chạy trước đổ vì thiếu bảng, mỗi lần lộ ra một cái. Đoán tiếp là cách
-- để đổ lần thứ ba, nên danh sách dưới đây dựng bằng truy vấn — mọi bảng có
-- khoá ngoại trỏ vào patient / appointment / visit / care_episode / work_item /
-- event_log, lần theo tối đa 4 bậc:
--
--     select c.relname, f.relname from pg_constraint k
--       join pg_class c on c.oid=k.conrelid join pg_class f on f.oid=k.confrelid
--      where k.contype='f' and f.relname in ('patient','appointment','visit', ...);
--
-- Bảy bảng lộ ra mà script chưa từng biết: pregnancy, follow_up_case, cskh_log,
-- mpi_merge_queue, patient_contact_channel, patient_medical_profile,
-- patient_next_of_kin.
--
-- Đã diễn thử trọn bộ trên prod trong một giao dịch rồi ROLLBACK: đi hết, và
-- giữ nguyên 57 nhân sự · 3262 ca trực · 12 phòng.
DELETE FROM work_item_event;
DELETE FROM work_item_dependency;
DELETE FROM clinical_record;
DELETE FROM clinical_release;
DELETE FROM visit_amendment;
DELETE FROM clinical_form_response;
DELETE FROM prescription;
DELETE FROM lab_result;
DELETE FROM service_log;
DELETE FROM payment;
DELETE FROM ultrasound_record;
-- pregnancy SAU clinical_record và ultrasound_record — cả hai trỏ vào nó.
DELETE FROM pregnancy;
DELETE FROM follow_up_case;
DELETE FROM work_item;
DELETE FROM visit_route;
DELETE FROM visit;
DELETE FROM slot_hold;
DELETE FROM cskh_action;
DELETE FROM cskh_log;
DELETE FROM staff_task;
DELETE FROM mpi_merge_queue;
DELETE FROM patient_contact_channel;
DELETE FROM patient_medical_profile;
DELETE FROM patient_next_of_kin;

-- APPOINTMENT VÀ CARE_EPISODE TRỎ VÀO NHAU — một VÒNG TRÒN khoá ngoại:
--
--     appointment.episode_id             → care_episode
--     care_episode.opened_appointment_id → appointment
--
-- Không thứ tự tuyến tính nào thoả được vòng này, nên đảo hai dòng DELETE cho
-- nhau cũng vẫn đổ, chỉ đổi tên bảng trong thông báo lỗi. Cả hai cột đều CHO
-- NULL và ràng buộc KHÔNG hoãn được, nên cách duy nhất là cắt vòng trước.
UPDATE care_episode SET opened_appointment_id = NULL
 WHERE opened_appointment_id IS NOT NULL;
UPDATE appointment  SET episode_id = NULL
 WHERE episode_id IS NOT NULL;

DELETE FROM appointment;
DELETE FROM care_episode;
-- Hai bảng này trỏ vào bệnh nhân bằng clinic_patient_id và KHÔNG có khoá ngoại,
-- nên xoá bệnh nhân không kéo theo chúng và database cũng không kêu. Bỏ sót thì
-- lần chạy sau còn lại những bản đồng ý chia sẻ hồ sơ giữa hai người không còn
-- tồn tại — và chúng vẫn có hiệu lực.
DELETE FROM clinical_data_consent;
DELETE FROM patient_link;
DELETE FROM patient;
-- event_log xoá SAU CÙNG: nó ghi nhật ký của chính mấy bảng trên, và giữ lại
-- nhật ký của những dòng đã biến mất chỉ làm màn Nhật ký thao tác đầy những
-- tham chiếu trỏ vào hư không.
DELETE FROM event_log;

ALTER TABLE appointment     ENABLE TRIGGER trg_appointment_no_delete;
ALTER TABLE clinical_record ENABLE TRIGGER trg_clinical_record_no_delete;
ALTER TABLE event_log       ENABLE TRIGGER trg_event_log_no_delete;
ALTER TABLE lab_result      ENABLE TRIGGER trg_lab_result_no_delete;
ALTER TABLE patient         ENABLE TRIGGER trg_patient_no_delete;
ALTER TABLE payment         ENABLE TRIGGER trg_payment_no_delete;
ALTER TABLE visit           ENABLE TRIGGER trg_visit_no_delete;

-- Đếm lại TRƯỚC KHI COMMIT. Một lệnh ENABLE gõ sai tên bảng sẽ đổ ngay ở trên,
-- nhưng một cái BỊ QUÊN thì im lặng — và prod sẽ chạy tiếp mà không còn lớp
-- chống xoá cứng, cho tới lúc có người xoá thật.
--
-- SOI THEO HÀNH VI, KHÔNG THEO TÊN HÀM. Bản đầu của khối này chỉ tìm trigger
-- dùng `prevent_hard_delete` — nên nó KHÔNG soi `trg_event_log_no_delete`,
-- vốn dùng `enforce_append_only`. Đúng cái trigger mà script này tắt ở trên.
-- Nghĩa là một lần chạy hỏng nửa chừng có thể để prod đứng dậy với nhật ký
-- xoá được, và khối "tự kiểm" vẫn báo sạch.
--
-- Điều kiện đúng là "trigger nào bắt DELETE hoặc TRUNCATE", đọc từ tgtype:
--     bit 3 (giá trị 8)  = DELETE
--     bit 5 (giá trị 32) = TRUNCATE
DO $kiem$
DECLARE
    con_tat text;
BEGIN
    SELECT string_agg(c.relname || '.' || t.tgname, ', ')
      INTO con_tat
      FROM pg_trigger t
      JOIN pg_class c ON c.oid = t.tgrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND NOT t.tgisinternal
       AND (t.tgtype::int & 8 = 8 OR t.tgtype::int & 32 = 32)
       AND t.tgenabled = 'D';
    IF con_tat IS NOT NULL THEN
        RAISE EXCEPTION 'còn trigger chống xoá đang TẮT: % — huỷ toàn bộ', con_tat;
    END IF;
END
$kiem$;

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
