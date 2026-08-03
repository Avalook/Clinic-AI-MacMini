#!/usr/bin/env bash
# Gỡ 35 dòng staff mà clinic_roster.sql vừa tạo nhầm trên prod.
#
# CHUYỆN ĐÃ XẢY RA. supabase/fixtures/clinic_roster.sql được viết cho một
# database mà — theo đúng lời phần đầu file — "chỉ có 7 tài khoản giả của
# staff_logins.sql". Prod thật thì đã có 55 nhân sự thật, nhập từ 2026-06-19.
#
# Fixture dùng id cố định d0000000-…-0000000000NN và `ON CONFLICT (id)`, nên nó
# không nhận ra người đã tồn tại: nó khớp theo ID, còn người cũ mang UUID ngẫu
# nhiên. Kết quả là 35 dòng MỚI, trong đó 18 trùng tên chính xác với người đã có
# ("ĐD Trang Lê", "BS Đào", "ĐD Hà Vũ"…). Hai dòng cho một con người.
#
# Hai hậu quả:
#   * Ô chọn bác sĩ / điều dưỡng hiện tên hai lần, không phân biệt được.
#   * 90 nhân sự đang hoạt động thay vì 55, nên chốt an toàn của
#     20260730000004_tenant_scoped_rls đếm 82 người chưa có login và từ chối áp.
#
# VÌ SAO XOÁ CHỨ KHÔNG PHẢI is_active=false. Đã kiểm 18 bảng có khoá ngoại trỏ
# tới staff: KHÔNG dòng nghiệp vụ nào tham chiếu các id fixture (0 lịch hẹn,
# 0 ca trực). Chúng được tạo cách đây vài giờ và chưa từng được dùng. Đánh dấu
# ngừng hoạt động sẽ để lại 35 cái tên chết trong mọi báo cáo và mọi bộ lọc
# "nhân sự cũ" về sau; xoá hẳn mới thật sự hoàn tác được thao tác nhầm.
#
# AN TOÀN. Script kiểm lại điều kiện đó ngay trước khi xoá và DỪNG nếu có bất kỳ
# tham chiếu nào — nó sẽ không bao giờ xoá một nhân sự đã có dữ liệu.
#
#   ./scripts/undo-roster-fixture.sh            # THỬ, không ghi gì
#   ./scripts/undo-roster-fixture.sh --apply    # xoá thật

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO}/.env.prod}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

export PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/opt/postgresql@17/bin:${PATH}"
command -v psql >/dev/null 2>&1 || { echo "Cần psql: brew install libpq" >&2; exit 1; }

PSQL_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- \
           | sed 's|postgresql+asyncpg://|postgresql://|')
[[ -n "$PSQL_URL" ]] || { echo "Không đọc được DATABASE_URL từ $ENV_FILE" >&2; exit 1; }

PREFIX='d0000000-0000-4000-8000-%'

echo "=== Dòng staff do fixture tạo ==="
psql "$PSQL_URL" -At -F' | ' -c "
SELECT full_name, primary_department
  FROM public.staff WHERE id::text LIKE '${PREFIX}' ORDER BY full_name;"

echo
echo "=== Tham chiếu nghiệp vụ tới các dòng đó (phải là 0) ==="
psql "$PSQL_URL" -At -F' = ' -c "
SELECT 'appointment.doctor_id',        count(*) FROM appointment        WHERE doctor_id::text            LIKE '${PREFIX}'
UNION ALL SELECT 'work_roster.staff_id',       count(*) FROM work_roster       WHERE staff_id::text             LIKE '${PREFIX}'
UNION ALL SELECT 'work_session_staff.staff_id',count(*) FROM work_session_staff WHERE staff_id::text            LIKE '${PREFIX}'
UNION ALL SELECT 'visit.attending_doctor_id',  count(*) FROM visit             WHERE attending_doctor_id::text  LIKE '${PREFIX}'
UNION ALL SELECT 'visit.checked_in_by',        count(*) FROM visit             WHERE checked_in_by::text        LIKE '${PREFIX}'
UNION ALL SELECT 'visit.finalized_by',         count(*) FROM visit             WHERE finalized_by::text         LIKE '${PREFIX}'
UNION ALL SELECT 'payment.paid_by_staff_id',   count(*) FROM payment           WHERE paid_by_staff_id::text     LIKE '${PREFIX}'
UNION ALL SELECT 'lab_result.reviewed_by',     count(*) FROM lab_result        WHERE reviewed_by_staff_id::text LIKE '${PREFIX}'
UNION ALL SELECT 'ultrasound_record.performed_by', count(*) FROM ultrasound_record WHERE performed_by::text     LIKE '${PREFIX}'
UNION ALL SELECT 'staff_task.assigned_to',     count(*) FROM staff_task        WHERE assigned_to::text          LIKE '${PREFIX}'
UNION ALL SELECT 'pregnancy.primary_doctor_id',count(*) FROM pregnancy         WHERE primary_doctor_id::text    LIKE '${PREFIX}'
UNION ALL SELECT 'block_budget.doctor_id',     count(*) FROM block_budget      WHERE doctor_id::text            LIKE '${PREFIX}'
ORDER BY 1;"

if [[ $APPLY -eq 0 ]]; then
    echo
    echo "(THỬ — chưa xoá gì. Thêm --apply để xoá thật.)"
    exit 0
fi

echo
echo "=== Đang xoá ==="
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<SQL
BEGIN;

-- Chốt chặn cuối: nếu bất kỳ tham chiếu nghiệp vụ nào xuất hiện giữa lúc kiểm
-- và lúc xoá, huỷ toàn bộ. Thà không hoàn tác được còn hơn xoá nhầm một nhân sự
-- đã có lịch sử khám.
DO \$guard\$
DECLARE n integer;
BEGIN
    SELECT (SELECT count(*) FROM appointment WHERE doctor_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM work_roster WHERE staff_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM work_session_staff WHERE staff_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM visit WHERE attending_doctor_id::text LIKE '${PREFIX}'
                                          OR checked_in_by::text       LIKE '${PREFIX}'
                                          OR finalized_by::text        LIKE '${PREFIX}')
         + (SELECT count(*) FROM payment WHERE paid_by_staff_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM lab_result WHERE reviewed_by_staff_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM ultrasound_record WHERE performed_by::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM staff_task WHERE assigned_to::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM pregnancy WHERE primary_doctor_id::text LIKE '${PREFIX}')
         + (SELECT count(*) FROM block_budget WHERE doctor_id::text LIKE '${PREFIX}')
      INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION
          'Huỷ: % dòng nghiệp vụ đang trỏ tới staff của fixture. Không xoá.', n;
    END IF;
END
\$guard\$;

DELETE FROM public.staff_capability   WHERE staff_id::text LIKE '${PREFIX}';
DELETE FROM public.clinic_membership  WHERE staff_id::text LIKE '${PREFIX}';
DELETE FROM public.staff              WHERE id::text       LIKE '${PREFIX}';

COMMIT;
SQL

echo
echo "=== Còn lại ==="
psql "$PSQL_URL" -At -F' | ' -c "
SELECT 'nhân sự đang hoạt động = '||count(*) FILTER (WHERE COALESCE(is_active,true)),
       'trong đó CHƯA có login = '||count(*) FILTER (WHERE COALESCE(is_active,true) AND auth_user_id IS NULL)
  FROM public.staff;"
