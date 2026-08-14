-- Dọn dữ liệu vận hành trên PROD trước khi bàn giao (Tuyền chốt 14/08/2026).
--
-- PHẠM VI DO TUYỀN CHỐT: bệnh nhân + lịch hẹn + lượt khám + bệnh án + sổ sự
-- kiện, và mọi thứ treo vào chúng.
--
-- GIỮ NGUYÊN — nói rõ ra vì đây là chỗ dễ mất oan nhất:
--     work_roster, work_session*      lịch trực (vừa nhân sang tuần 17/08)
--     drug_batch, inventory_txn       kho thuốc
--     staff, clinic_membership        nhân sự + tài khoản đăng nhập
--     service_type, service_price     danh mục dịch vụ
--     clinic, clinic_hours, luật đặt lịch, định nghĩa bước
--
-- VÌ SAO KHÔNG DÙNG `don-du-lieu-thu.sh`. Hai lý do, cả hai đều quan trọng:
--
--   1. Nó có khoá an toàn: chỉ xoá khi MỌI hồ sơ khớp mẫu dữ liệu thử đã biết
--      (DEMO-, BN-KIEMTHU-, STG-, tên ZZ*). Hồ sơ trên prod mang mã
--      `BN-2026-…` — dạng mà chính ứng dụng sinh cho bệnh nhân THẬT. Khoá ấy
--      sẽ dừng, và đó là hành vi ĐÚNG của nó.
--
--   2. Danh sách bảng của nó TRUNCATE luôn `work_roster`, `work_session`,
--      `drug_batch`, `inventory_txn` — lịch trực và kho thuốc. Ngoài phạm vi
--      Tuyền chốt, và lịch trực thì vừa mới nhân sang tuần sau xong.
--
-- Danh sách dưới đây LẤY TỪ script ấy (đã được soát kỹ, có cả những bảng dễ
-- quên như `pregnancy`, `visit_route`, `clinical_release`, `pos_outbox`), BỎ ra
-- những bảng ngoài phạm vi, và THÊM bốn bảng của màn chăm sóc ra đời sau nó:
-- `tuong_tac_cskh`, `tep_ket_qua`, `phan_hoi_khach`, `hen_goi_lai`.
--
-- ĐÃ KIỂM TRƯỚC KHI GIAO (14/08/2026):
--   · cả 39 bảng đều tồn tại trên prod
--   · CASCADE không kéo thêm bảng nào ngoài danh sách — tập đã đóng theo đồ
--     thị khoá ngoại, nên không có bảng nào bị xoá ngoài ý muốn
--   · bản sao lưu chụp lúc 11:27 cùng ngày: 225KB, gzip toàn vẹn, kèm tài
--     khoản đăng nhập (clinicai_production_clinicai-db_20260814_112732)
--
-- CHẠY MỘT LẦN, TRONG MỘT GIAO DỊCH. `session_replication_role = 'replica'`
-- tắt MỌI trigger người dùng — kể cả bảy chốt chống xoá cứng và các trigger
-- cộng dồn. Phải chạy một mạch rồi để nó tự hết hiệu lực khi giao dịch kết
-- thúc; không được để hở ra ngoài.
--
--   docker cp scripts/don-prod-truoc-ban-giao.sql clinicai_db:/tmp/
--   docker exec clinicai_db psql -U postgres -d postgres \
--       -v ON_ERROR_STOP=1 -f /tmp/don-prod-truoc-ban-giao.sql
--
-- Có lỗi giữa chừng thì ON_ERROR_STOP + giao dịch sẽ cuộn lại toàn bộ: không
-- xoá được một nửa.

BEGIN;

SET LOCAL session_replication_role = 'replica';

TRUNCATE
  -- Bệnh nhân và mọi hồ sơ treo vào người
  patient, patient_contact_channel, patient_next_of_kin,
  patient_medical_profile, patient_link, pregnancy,
  mpi_merge_queue, clinical_data_consent,
  -- Lịch hẹn, lượt khám, giữ chỗ
  appointment, visit, visit_amendment, visit_route, visit_gate_override,
  slot_hold, idempotency_key,
  -- Bệnh án và kết quả
  clinical_record, clinical_form_response, clinical_release,
  lab_result, ultrasound_record, service_log, prescription,
  -- Việc trong quy trình
  work_item, work_item_dependency, work_item_event, staff_task,
  -- Thanh toán
  payment, pos_outbox,
  -- Chăm sóc khách hàng
  care_episode, cskh_action, cskh_log, follow_up_case, nhac_tai_kham,
  thong_bao, tuong_tac_cskh, tep_ket_qua, phan_hoi_khach, hen_goi_lai,
  -- Sổ sự kiện. Tuyền chốt xoá cả cái này; hệ quả đã nói trước: bảng KPI "đặt
  -- lịch theo nhân viên" đọc người đặt từ đây (appointment không có cột người
  -- tạo), và màn Lịch sử thao tác cũng đọc từ đây. Cả hai sẽ đếm lại từ đầu.
  event_log
CASCADE;

COMMIT;

-- Đếm lại để nhìn thấy kết quả, và để thấy những thứ ĐƯỢC GIỮ vẫn còn nguyên.
SELECT 'benh_nhan' AS bang, count(*) FROM patient
UNION ALL SELECT 'lich_hen', count(*) FROM appointment
UNION ALL SELECT 'luot_kham', count(*) FROM visit
UNION ALL SELECT 'benh_an', count(*) FROM clinical_record
UNION ALL SELECT 'so_su_kien', count(*) FROM event_log
UNION ALL SELECT 'GIU: nhan_su', count(*) FROM staff
UNION ALL SELECT 'GIU: ca_truc', count(*) FROM work_roster
UNION ALL SELECT 'GIU: dich_vu', count(*) FROM service_type
ORDER BY 1;
