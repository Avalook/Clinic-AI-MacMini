#!/usr/bin/env bash
# Dọn sạch DỮ LIỆU THỬ để bàn giao cho phòng khám dùng thật.
#
# Xoá: bệnh nhân, lịch hẹn, lượt khám, bệnh án, phiếu khám, việc, đơn thuốc,
# thanh toán, nhật ký CSKH, thông báo, kho thuốc thử, sổ sự kiện.
# GIỮ: cấu hình phòng khám — clinic, cơ sở, phòng, nhân sự, tài khoản đăng
# nhập, danh mục dịch vụ, danh mục thuốc, định nghĩa bước, luật đặt lịch.
#
# ─────────────────────────────────────────────────────────────────────────
# KHOÁ AN TOÀN — ĐỌC TRƯỚC KHI SỬA FILE NÀY.
#
# Bảy bảng (patient, visit, appointment, clinical_record, lab_result, payment,
# event_log) có chốt CHỐNG XOÁ CỨNG. Script này tắt chốt trong một giao dịch
# để dọn được — nghĩa là nó có đủ quyền xoá bệnh án thật.
#
# Nên nó ĐẾM TRƯỚC: mọi hồ sơ phải khớp một trong các mẫu dữ liệu thử đã biết.
# Thấy một hồ sơ lạ là DỪNG, không xoá gì. Một script dọn không có khoá này là
# một khẩu súng đã lên đạn chĩa vào hồ sơ của phòng khám.
#
# Muốn dọn một database đã có bệnh nhân thật thì KHÔNG sửa khoá này — hãy sao
# lưu, rồi làm bằng tay, có người thứ hai nhìn.
# ─────────────────────────────────────────────────────────────────────────
#
#   ./scripts/don-du-lieu-thu.sh clinicai_db        # production
#   ./scripts/don-du-lieu-thu.sh clinicai_stg_db    # staging
#
# CHẠY TRÊN MÁY CHỦ — dùng docker của máy đang gõ lệnh.

set -euo pipefail

DB="${1:-}"
[ -n "$DB" ] || { echo "Dùng: $0 <ten-container-database>" >&2; exit 1; }
docker inspect "$DB" >/dev/null 2>&1 || { echo "!! không có container $DB" >&2; exit 1; }

PSQL=(docker exec -i "$DB" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres)

#: Mẫu mã hồ sơ do CHÍNH CHÚNG TA sinh ra khi thử. Thêm mẫu mới thì thêm ở đây.
LA_THU="patient_code LIKE 'DEMO-%'
     OR patient_code LIKE 'BN-KIEMTHU%'
     OR patient_code LIKE 'BN-2026-%'
     OR patient_code LIKE 'BN-LOCAL-%'
     OR patient_code LIKE 'BN-DIENTHU-%'
     OR full_name ILIKE 'ZZ%'"

la=$("${PSQL[@]}" -Atc "SELECT count(*) FROM patient WHERE NOT ($LA_THU)")
tong=$("${PSQL[@]}" -Atc "SELECT count(*) FROM patient")

echo "==> $DB: $tong hồ sơ, $la hồ sơ KHÔNG khớp mẫu dữ liệu thử"
if [ "$la" != "0" ]; then
  echo "!! DỪNG. Có $la hồ sơ trông như bệnh nhân THẬT:" >&2
  "${PSQL[@]}" -c "SELECT patient_code, full_name, created_at::date
                     FROM patient WHERE NOT ($LA_THU) LIMIT 10" >&2
  echo "!! Không xoá gì cả. Xem khoá an toàn ở đầu file." >&2
  exit 1
fi

echo "==> dọn"
"${PSQL[@]}" <<'SQL'
BEGIN;
-- Tắt CHỐT CHỐNG XOÁ CỨNG trong đúng giao dịch này. `session_replication_role`
-- tắt mọi trigger người dùng — kể cả trigger cộng dồn tồn kho — nên phải chạy
-- một mạch rồi bật lại, không để hở ra ngoài giao dịch.
SET LOCAL session_replication_role = 'replica';

TRUNCATE
  -- Người bệnh và mọi thứ bám vào
  patient, patient_contact_channel, patient_next_of_kin,
  patient_medical_profile, patient_summary, patient_link, pregnancy,
  mpi_merge_queue, clinical_data_consent,
  -- Lượt khám
  appointment, visit, visit_amendment, visit_route, visit_gate_override,
  slot_hold,
  -- Nội dung lâm sàng
  clinical_record, clinical_form_response, clinical_release,
  lab_result, ultrasound_record, service_log, prescription,
  -- Việc
  work_item, work_item_dependency, work_item_event, staff_task,
  -- Tiền
  payment, pos_outbox,
  -- Chăm sóc khách hàng
  care_episode, cskh_action, cskh_log, follow_up_case, nhac_tai_kham,
  thong_bao,
  -- Kho thuốc thử (danh mục thuốc GIỮ LẠI)
  drug_batch, inventory_txn,
  -- Lịch trực thử
  work_roster, work_session, work_session_staff,
  -- Sổ sự kiện
  event_log
CASCADE;
COMMIT;
SQL

echo "==> còn lại"
"${PSQL[@]}" -c "SELECT
  (SELECT count(*) FROM patient)      AS benh_nhan,
  (SELECT count(*) FROM appointment)  AS lich_hen,
  (SELECT count(*) FROM visit)        AS luot_kham,
  (SELECT count(*) FROM staff)        AS nhan_su,
  (SELECT count(*) FROM service_type WHERE is_active) AS dich_vu,
  (SELECT count(*) FROM drug_catalog) AS danh_muc_thuoc,
  (SELECT count(*) FROM auth.users)   AS tai_khoan"
