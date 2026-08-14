-- Dọn dữ liệu vận hành trên PROD trước khi bàn giao (Tuyền chốt 14/08/2026).
--
-- PHẠM VI DO TUYỀN CHỐT: bệnh nhân + lịch hẹn + lượt khám + bệnh án + sổ sự
-- kiện. Giữ nguyên cấu hình phòng khám: nhân sự, tài khoản đăng nhập, danh mục
-- dịch vụ/thuốc, luật đặt lịch, lịch trực.
--
-- VÌ SAO KHÔNG DÙNG `don-du-lieu-thu.sh`. Script ấy có khoá an toàn: nó chỉ xoá
-- khi MỌI hồ sơ khớp mẫu dữ liệu thử đã biết (DEMO-, BN-KIEMTHU-, STG-, ZZ*).
-- Hồ sơ trên prod mang mã `BN-2026-…` — dạng mà chính ứng dụng sinh cho bệnh
-- nhân THẬT. Khoá ấy sẽ dừng, và đó là hành vi đúng của nó; ghi chú trong
-- chính script nói: *"Muốn dọn một database đã có bệnh nhân thật thì KHÔNG sửa
-- khoá này — hãy sao lưu, rồi làm bằng tay, có người thứ hai nhìn."*
--
-- Nên đây là bản làm tay, chạy một lần, có Tuyền xác nhận phạm vi, và có bản
-- sao lưu chụp ngay trước đó (clinicai_production_…_112732, 225KB, gzip đã
-- kiểm toàn vẹn).
--
-- MỘT GIAO DỊCH DUY NHẤT. Bảy bảng có chốt chống xoá cứng; tắt chốt bằng
-- `session_replication_role` thì tắt MỌI trigger người dùng — kể cả trigger
-- cộng dồn tồn kho. Phải chạy một mạch trong một giao dịch rồi để nó tự hết
-- hiệu lực, không được để hở ra ngoài.
--
-- THỨ TỰ XOÁ ĐI TỪ LÁ VÀO GỐC. Khoá ngoại vẫn còn hiệu lực trong giao dịch
-- này (chỉ trigger bị tắt, không phải ràng buộc), nên xoá gốc trước là lỗi.

BEGIN;

SET LOCAL session_replication_role = 'replica';

-- ── LÁ: những bảng trỏ vào lượt khám / lịch hẹn / bệnh nhân ────────────────
DELETE FROM public.clinical_form_response;
DELETE FROM public.clinical_record;
DELETE FROM public.lab_result;
DELETE FROM public.service_log;
DELETE FROM public.prescription_item;
DELETE FROM public.prescription;
DELETE FROM public.payment_item;
DELETE FROM public.payment;
DELETE FROM public.work_item_event;
DELETE FROM public.work_item;
DELETE FROM public.staff_task;

-- ── SỔ CHĂM SÓC CSKH ──────────────────────────────────────────────────────
DELETE FROM public.tuong_tac_cskh;
DELETE FROM public.tep_ket_qua;
DELETE FROM public.phan_hoi_khach;
DELETE FROM public.hen_goi_lai;
DELETE FROM public.nhac_tai_kham;
DELETE FROM public.cskh_action;

-- ── GIỮ CHỖ + KHOÁ CHỐNG TRÙNG ────────────────────────────────────────────
DELETE FROM public.slot_hold;
DELETE FROM public.idempotency_key;

-- ── LƯỢT KHÁM, LỊCH HẸN, BỆNH NHÂN ────────────────────────────────────────
DELETE FROM public.visit;
DELETE FROM public.appointment;
DELETE FROM public.patient_contact_channel;
DELETE FROM public.patient_medical_profile;
DELETE FROM public.patient_next_of_kin;
DELETE FROM public.patient_link;
DELETE FROM public.patient;

-- ── SỔ SỰ KIỆN ────────────────────────────────────────────────────────────
--
-- Tuyền chốt xoá cả cái này. Hệ quả đã nói trước và Tuyền vẫn quyết: bảng KPI
-- "đặt lịch theo nhân viên" đọc người đặt từ đây (appointment không có cột
-- người tạo), và màn Lịch sử thao tác cũng đọc từ đây. Cả hai sẽ rỗng và đếm
-- lại từ đầu — đúng ý khi bàn giao một hệ thống sạch.
DELETE FROM public.event_log;

COMMIT;
