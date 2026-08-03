#!/usr/bin/env bash
# Lịch sử migration nói gì, và database THẬT SỰ có gì.
#
# VÌ SAO CẦN. Ngày 2026-08-03, `supabase db push --dry-run` báo chỉ còn 2
# migration chờ — nghĩa là CLI tin rằng 35 migration trước đó đã áp xong. Nhưng
# `20260803000003` đổ ngay lập tức với:
#
#     ERROR: relation "public.work_item" does not exist
#
# work_item được tạo bởi 20260730000005, một migration mà bảng lịch sử ghi là
# ĐÃ ÁP. Kiểm kỹ thì 23 migration ở tình trạng đó: có tên trong
# supabase_migrations.schema_migrations, không có gì trong schema.
#
# Đây là kiểu hỏng tệ nhất của công cụ migration: nó không báo lỗi, không lệch
# dần, và mọi lệnh kiểm tra thông thường (`db push --dry-run`) đều nói "mọi thứ
# ổn". Chỉ khi một migration mới tình cờ chạm vào bảng thiếu thì mới lộ.
#
# Script này không tin bảng lịch sử. Nó hỏi thẳng database: đối tượng đặc trưng
# của từng migration có tồn tại không?
#
#   ./scripts/check-schema-drift.sh              # .env.prod
#   ENV_FILE=.env.staging ./scripts/check-schema-drift.sh
#
# CHỈ ĐỌC. Không ghi gì, không sửa gì.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO}/.env.prod}"

export PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/opt/postgresql@17/bin:${PATH}"
command -v psql >/dev/null 2>&1 || { echo "Cần psql: brew install libpq" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || { echo "Không thấy $ENV_FILE" >&2; exit 1; }

# DATABASE_URL trong .env.prod dùng scheme của SQLAlchemy
# (postgresql+asyncpg://). psql không hiểu "+asyncpg" và sẽ âm thầm rơi về
# socket local — báo lỗi "server on socket /tmp/.s.PGSQL.5432 failed", trông
# như Postgres chưa chạy chứ không như một URL sai định dạng.
PSQL_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- \
           | sed 's|postgresql+asyncpg://|postgresql://|')
[[ -n "$PSQL_URL" ]] || { echo "Không đọc được DATABASE_URL từ $ENV_FILE" >&2; exit 1; }

psql "$PSQL_URL" -At <<'SQL'
-- Mỗi migration được đại diện bởi MỘT đối tượng mà nó bắt buộc phải tạo. Bảng,
-- hàm, policy hay cột đều được — điều duy nhất quan trọng là nếu migration chạy
-- thật thì đối tượng đó phải có mặt.
--
-- CHỮ KÝ PHẢI ĐỌC RA TỪ FILE MIGRATION, ĐỪNG ĐOÁN THEO TÊN.
--
-- Bốn dòng dưới đây từng sai vì tôi suy tên từ tên file thay vì mở file ra xem:
--   20260714000004  đoán idx_appointment_slot_start, thật ra ..._slot_start_status
--   20260714000005  đoán cột `scope`, migration thêm actor_id/state/updated_at
--   20260717000002  đoán check_in_appointment(uuid,uuid), thật là (uuid,text[])
--   20260730000018  đoán cột reserved_at, thật ra là uq_staff_task_open_lab_review
--
-- Hậu quả không phải là bỏ sót mà là NGƯỢC LẠI: ba migration đã chạy thành công
-- bị báo "LỆCH", suýt nữa thì repair rồi chạy lại một cách vô ích. Một công cụ
-- kiểm tra báo động giả cũng làm mất niềm tin đúng bằng một công cụ bỏ sót.
WITH sig(version, kind, obj) AS (VALUES
  -- HÀM tồn tại KHÔNG chứng minh luật đang được thi hành. Trên prod ngày
  -- 2026-08-03, enforce_slot_capacity() có mặt còn TRIGGER gọi nó thì không —
  -- nên script này báo OK trong khi sức chứa không chặn gì suốt thời gian đó.
  -- Chữ ký phải là thứ THI HÀNH luật, không phải thứ chứa luật.
  ('20260714000002','trg' ,'appointment.trg_enforce_slot_capacity'),
  ('20260714000003','tbl' ,'public.idempotency_key'),
  ('20260714000004','idx' ,'idx_appointment_slot_start_status'),
  ('20260714000005','col' ,'idempotency_key.state'),
  ('20260717000001','func','public.current_staff_department()'),
  ('20260717000002','func','public.check_in_appointment(uuid,text[])'),
  ('20260730000001','pol' ,'care_episode'),
  ('20260730000002','pol' ,'province'),
  ('20260730000003','func','public.current_clinic_ids()'),
  ('20260730000004','func','public.staff_ensure_default_membership()'),
  ('20260730000005','tbl' ,'public.work_item'),
  ('20260730000007','tbl' ,'public.pos_outbox'),
  ('20260730000008','pol' ,'appointment'),
  ('20260730000009','pol' ,'block_budget'),
  ('20260730000011','tbl' ,'public.clinical_form_catalogue'),
  ('20260730000012','pol' ,'ultrasound_record'),
  ('20260730000013','func','public.current_clinic_ids_for_roles(text[])'),
  ('20260730000016','trg' ,'payment.trg_payment_no_delete'),
  ('20260730000017','pol' ,'clinical_form_response'),
  ('20260730000018','idx' ,'uq_staff_task_open_lab_review'),
  -- 20260731000001 chỉ CREATE OR REPLACE lại check_in_appointment (không tạo
  -- đối tượng mới nào), nên không có gì để hỏi "có tồn tại không" — hàm đã tồn
  -- tại từ 20260717000002. Phân biệt bằng NỘI DUNG: bản per-clinic khai báo
  -- biến clinic_day, bản cũ thì không.
  ('20260731000001','src' ,'check_in_appointment|clinic_day'),
  ('20260731000003','func','public.instantiate_visit_workflow(uuid,uuid,uuid,text,text)'),
  ('20260801000001','func','public.map_services_to_nodes()'),
  ('20260801000002','func','public.order_services(uuid,uuid,text[],uuid,text)'),
  ('20260801000003','tbl' ,'public.visit_amendment'),
  ('20260801000004','tbl' ,'public.owner_feedback'),
  ('20260802000001','tbl' ,'public.drug_batch'),
  ('20260803000001','func','public.clinic_booking_policy(uuid)'),
  ('20260803000002','tbl' ,'public.doctor_booking_override'),
  ('20260803000003','col' ,'visit.current_node_code'),
  ('20260803000004','col' ,'appointment.notes'),
  ('20260803000005','view','public.v_consultation_duration'),
  ('20260803000006','idx' ,'uq_ultrasound_visit_type'),
  -- Không dùng cột primary_location_id: nó đã tồn tại từ baseline, migration này
  -- chỉ đặt NOT NULL. Trigger là thứ nó thật sự TẠO RA.
  ('20260803000007','trg' ,'staff.trg_staff_location_matches_clinic'),
  -- 20260803000008 chỉ GỠ bảng khỏi publication, không tạo gì. Kiểm ngược: nó
  -- đã chạy khi `patient` KHÔNG còn trong supabase_realtime.
  ('20260803000008','unpub','patient'),
  ('20260803000009','col' ,'slot_booking_override.minute_start'),
  ('20260803000010','trg' ,'appointment.trg_enforce_slot_capacity')
),
checked AS (
  SELECT s.version,
         (SELECT 1 FROM supabase_migrations.schema_migrations m
           WHERE m.version = s.version) IS NOT NULL AS in_history,
         CASE
           WHEN s.kind IN ('tbl','view','idx') THEN to_regclass(s.obj) IS NOT NULL
           WHEN s.kind = 'func' THEN to_regprocedure(s.obj) IS NOT NULL
           WHEN s.kind = 'pol'  THEN EXISTS (SELECT 1 FROM pg_policies
                                              WHERE schemaname='public'
                                                AND tablename = s.obj)
           WHEN s.kind = 'col'  THEN EXISTS (SELECT 1 FROM information_schema.columns
                                              WHERE table_schema='public'
                                                AND table_name  = split_part(s.obj,'.',1)
                                                AND column_name = split_part(s.obj,'.',2))
           WHEN s.kind = 'trg'  THEN EXISTS (SELECT 1 FROM pg_trigger t
                                              WHERE t.tgrelid =
                                                    ('public.'||split_part(s.obj,'.',1))::regclass
                                                AND NOT t.tgisinternal
                                                AND t.tgname = split_part(s.obj,'.',2))
           -- 'src': migration chỉ CREATE OR REPLACE một hàm đã có, nên sự tồn
           -- tại không phân biệt được bản cũ với bản mới. Hỏi NỘI DUNG hàm thay
           -- vì hỏi tên nó. obj = 'tên_hàm|chuỗi_đặc_trưng'.
           -- 'unpub': migration GỠ thứ gì đó. Điều kiện "đã chạy" là sự VẮNG
           -- MẶT, nên phép kiểm phải đảo lại — hỏi "còn tồn tại không" ở đây sẽ
           -- báo ngược hoàn toàn.
           WHEN s.kind = 'unpub' THEN NOT EXISTS (
                                       SELECT 1 FROM pg_publication_tables
                                        WHERE pubname = 'supabase_realtime'
                                          AND schemaname = 'public'
                                          AND tablename = s.obj)
           WHEN s.kind = 'src'  THEN EXISTS (
                                       SELECT 1 FROM pg_proc p
                                         JOIN pg_namespace n ON n.oid = p.pronamespace
                                        WHERE n.nspname = 'public'
                                          AND p.proname = split_part(s.obj,'|',1)
                                          AND pg_get_functiondef(p.oid)
                                              LIKE '%'||split_part(s.obj,'|',2)||'%')
         END AS in_schema
    FROM sig s
)
SELECT line FROM (
  SELECT 1 AS ord, version AS sort_key,
         version || '  ' ||
         CASE
           WHEN in_history AND in_schema     THEN 'OK'
           WHEN in_history AND NOT in_schema THEN 'LỆCH — ghi là đã áp, schema KHÔNG có'
           WHEN NOT in_history AND in_schema THEN 'LẠ  — schema có, lịch sử không ghi'
           ELSE                                   'chờ áp'
         END AS line
    FROM checked
  UNION ALL
  -- HAI CON SỐ, KHÔNG PHẢI MỘT.
  --
  -- Bản đầu chỉ đếm "LỆCH" và in "TỔNG: 0" ngay sau khi repair — lúc mà KHÔNG
  -- có gì đã được áp cả. Về mặt kỹ thuật thì đúng (repair đã xoá chúng khỏi lịch
  -- sử nên không còn cái nào "ghi là áp mà schema trống"), nhưng đọc lên thì
  -- giống hệt "xong rồi", và bước push bị bỏ qua vì thế.
  --
  -- Một dòng tổng kết chỉ đúng về mặt câu chữ mà dẫn người đọc sang kết luận
  -- sai thì cũng hỏng như một con số sai.
  SELECT 3, '',
         'LỆCH  : ' || count(*) FILTER (WHERE in_history AND NOT in_schema)
         || '   (ghi là đã áp nhưng schema trống → repair --status reverted)'
    FROM checked
  UNION ALL
  SELECT 4, '',
         'CHỜ ÁP: ' || count(*) FILTER (WHERE NOT in_history AND NOT in_schema)
         || '   (→ chạy `npx supabase db push --include-all`)'
    FROM checked
  UNION ALL
  SELECT 5, '',
         CASE WHEN count(*) FILTER (WHERE NOT in_schema) = 0
              THEN 'KẾT LUẬN: schema khớp toàn bộ migration. Deploy được.'
              ELSE 'KẾT LUẬN: CHƯA XONG — còn '
                   || count(*) FILTER (WHERE NOT in_schema)
                   || ' migration chưa có mặt trong schema.'
         END
    FROM checked
  UNION ALL
  -- Danh sách sẵn sàng dán vào lệnh repair, để không ai phải gõ tay hai mươi mã.
  SELECT 6, '',
         'LỆNH 1: npx supabase migration repair --status reverted '
         || string_agg(version, ' ' ORDER BY version)
    FROM checked WHERE in_history AND NOT in_schema
  UNION ALL
  -- --include-all LÀ BẮT BUỘC SAU KHI REPAIR, KHÔNG PHẢI TUỲ CHỌN.
  --
  -- Sau repair, các migration cần chạy lại có version NHỎ HƠN migration cuối
  -- còn được ghi trên remote. `db push` trần từ chối chèn ngược vào giữa lịch
  -- sử và trả về LegacyDbPushMissingRemoteError — một khối JSON trong đó phần
  -- "suggestion" là một danh sách file dài. Trên terminal nó trông y hệt một
  -- danh sách bình thường, nên rất dễ đọc nhầm thành "đã chạy xong" và bỏ qua.
  SELECT 7, '',
         'LỆNH 2: npx supabase db push --include-all'
    FROM checked WHERE NOT in_schema
   HAVING count(*) > 0
) x ORDER BY ord, sort_key;
SQL
