-- BẬT LẠI "ĐỐI TÁC LÀM" (Tuyền 16/10/2026) — đảo ngược scripts tắt hôm 01/10
-- (ClinicAI-Backups/bo-doi-tac-lam-0110.sql). DỮ LIỆU, không migration. Tuyền chạy
-- trên STAGING trước (xem bảng kiểm), rồi prod:
--   ssh clinic-vps-moi 'docker exec -i clinicai_stg_db psql -U postgres -d postgres' < scripts/bat-lai-doi-tac-1610.sql
-- SỬA danh sách mã dưới đây cho ĐÚNG các nhóm việc / dịch vụ đối tác làm thật
-- (chạy scripts/kiem-doi-tac-1610.sql để xem 5 node + 3 dịch vụ từng bị tắt).
-- Chưa điền mã thì KHÔNG đổi gì (UPDATE theo danh sách rỗng).
BEGIN;
-- Nhóm việc làm bên ngoài (5 mã đã tắt 01/10: HINHANH-NGOAI, LAYMAU-MAU, -NUOCTIEU, -AMDAO, SANGLOC-COTUCUNG).
-- Tuyền chốt 16/10: chỉ chụp phim ngoài (MRI vú, chụp tử cung – vòi trứng, chụp vú ép).
-- Lấy máu / nước tiểu / âm đạo: điều dưỡng lấy trong nhà rồi gửi mẫu — KHÔNG bật.
UPDATE public.node_definition SET lam_ben_ngoai = true
 WHERE code = ANY (ARRAY['DICHVU-HINHANH-NGOAI']::text[]);
-- Dịch vụ đối tác tự lấy mẫu — Tuyền chốt 16/10: HPV + Thinprep (cả HPV 16 type và combo).
UPDATE public.service_price SET doi_tac_lay_mau = true, updated_at = now()
 WHERE "group" = 'dich_vu' AND service_code = ANY (ARRAY[
       'CLS_HPV', 'CLS_THINPREP', 'KV_SP000169', 'KV_SP000170']::text[]);
-- Bên thu: dịch vụ đối tác làm ⇒ "Thu hộ đối tác" (tiền KHÔNG vào phòng khám). Đặt chọn tay
-- để đổi phòng làm ở Bảng giá không lật lại. Điền mã dịch vụ.
UPDATE public.service_price SET billing_owner = 'EXTERNAL_PARTNER',
       billing_owner_chon_tay = true, updated_at = now()
 WHERE "group" = 'dich_vu' AND service_code = ANY (ARRAY[
       'CLS_HPV', 'CLS_THINPREP', 'KV_SP000169', 'KV_SP000170',
       'CLS_CHUP_MRI_VU', 'CLS_CHUP_TU_CUNG_VOI_TRUNG', 'CLS_CHUP_VU_EP']::text[]);
SELECT 'node lam_ben_ngoai' AS muc, count(*) FROM public.node_definition WHERE lam_ben_ngoai
UNION ALL SELECT 'dich vu doi_tac_lay_mau', count(*) FROM public.service_price WHERE doi_tac_lay_mau
UNION ALL SELECT 'dich vu thu ho doi tac', count(*) FROM public.service_price
 WHERE "group" = 'dich_vu' AND billing_owner = 'EXTERNAL_PARTNER';
COMMIT;
