-- KIỂM DỮ LIỆU PROD — CHỈ ĐỌC, CHỈ TRẢ CON SỐ (21/10/2026).
--
-- 16 bất biến của agent soát hệ thống (nhánh claude/agent-soat-he-thong, 18/10)
-- + 2 câu đo hai lỗi bản đồ code bắt được (PR #522) có từng xảy ra thật chưa.
-- Mỗi câu một giao dịch READ ONLY, trần 20 giây. KHÔNG trả tên / SĐT / ghi chú,
-- KHÔNG trả id — chỉ số dòng vi phạm. Agent không tự chạy trên prod (luật 18/10):
-- Tuyền chạy, dán kết quả về, Claude nạp vào bản đồ.
--
-- Chạy (một lệnh, trên Mac):
--   ssh clinic-vps-moi 'cd /home/clinicai/clinicai && docker exec -i clinicai_db psql -U postgres -d postgres -X -q -t -A' < docs/ban-do/hieu/kiem-du-lieu-prod.sql
-- Mỗi dòng ra là một JSON {"ma":…, "so_dong":…}.

\set ON_ERROR_STOP off

-- D01 Tồn lô thuốc âm
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D01','so_dong',(SELECT count(*) FROM drug_batch WHERE quantity_on_hand < 0))::text; ROLLBACK;
-- D02 Tồn lô lệch tổng sổ kho
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D02','so_dong',(SELECT count(*) FROM drug_batch b LEFT JOIN (SELECT drug_batch_id, SUM(quantity) AS tong FROM inventory_txn GROUP BY drug_batch_id) s ON s.drug_batch_id = b.id WHERE b.quantity_on_hand <> COALESCE(s.tong, 0)))::text; ROLLBACK;
-- D03 Vật tư tồn âm (Quang 17/10: chỉ cảnh báo, không chặn)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D03','so_dong',(SELECT count(*) FROM vat_tu_ton WHERE so_luong < 0))::text; ROLLBACK;
-- D04 Giao thuốc nhiều hơn số đã gán lô
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D04','so_dong',(SELECT count(*) FROM prescription_allocation WHERE handed_over_qty > quantity))::text; ROLLBACK;
-- D05 Lịch hẹn kết thúc trước khi bắt đầu
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D05','so_dong',(SELECT count(*) FROM appointment WHERE slot_end <= slot_start))::text; ROLLBACK;
-- D06 Phiếu thu huỷ thiếu lý do / mốc huỷ mâu thuẫn
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D06','so_dong',(SELECT count(*) FROM payment WHERE (status = 'VOIDED' AND (voided_at IS NULL OR void_reason IS NULL OR btrim(void_reason) = '')) OR (status <> 'VOIDED' AND voided_at IS NOT NULL)))::text; ROLLBACK;
-- D07 Lượt đã chốt thiếu mốc chốt
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D07','so_dong',(SELECT count(*) FROM visit WHERE status = 'FINALIZED' AND finalized_at IS NULL))::text; ROLLBACK;
-- D08 Hoàn tiền mở quá 3 ngày
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D08','so_dong',(SELECT count(*) FROM payment_refund WHERE completed_at IS NULL AND closed_at IS NULL AND created_at < now() - interval '3 days'))::text; ROLLBACK;
-- D09 Thuốc khách trả chờ kiểm quá 2 ngày
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D09','so_dong',(SELECT count(*) FROM drug_return WHERE disposition IS NULL AND returned_at < now() - interval '2 days'))::text; ROLLBACK;
-- D10 Sự kiện chưa xử lý quá 15 phút
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D10','so_dong',(SELECT count(*) FROM event_delivery WHERE processed_at IS NULL AND created_at < now() - interval '15 minutes'))::text; ROLLBACK;
-- D11 Thuốc đã giao chưa gán lô quá 1 ngày
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D11','so_dong',(SELECT count(*) FROM thuoc_giao_chua_gan_lo WHERE drug_batch_id IS NULL AND giao_luc < now() - interval '1 day'))::text; ROLLBACK;
-- D12 Lô hết hạn vẫn còn tồn
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D12','so_dong',(SELECT count(*) FROM drug_batch WHERE expiry_date < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AND quantity_on_hand > 0))::text; ROLLBACK;
-- D13 Lô còn tồn khác đơn vị bán
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D13','so_dong',(SELECT count(*) FROM drug_batch b JOIN drug_catalog c ON c.id = b.drug_catalog_id WHERE c.don_vi_ban IS NOT NULL AND lower(btrim(b.unit)) <> lower(btrim(c.don_vi_ban)) AND b.quantity_on_hand > 0))::text; ROLLBACK;
-- D14 Lượt mở/đang khám quá 2 ngày
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D14','so_dong',(SELECT count(*) FROM visit WHERE status IN ('OPEN','IN_PROGRESS') AND created_at < now() - interval '2 days'))::text; ROLLBACK;
-- D15 Lịch đã xác nhận quá 1 ngày chưa check-in/huỷ
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D15','so_dong',(SELECT count(*) FROM appointment WHERE status = 'CONFIRMED' AND slot_start < now() - interval '1 day'))::text; ROLLBACK;
-- D16 Bảng có clinic_id, đăng nhập đọc được, chưa bật RLS
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D16','so_dong',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'clinic_id' AND NOT a.attisdropped WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity AND (has_table_privilege('anon', c.oid, 'SELECT') OR has_table_privilege('authenticated', c.oid, 'SELECT'))))::text; ROLLBACK;
-- D17 (mới, PR #522) Cấp quyền theo NHÓM ĐÃ TẮT sau lúc tắt — lỗi đã từng xảy ra thật?
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D17','so_dong',(SELECT count(*) FROM capability_grant g JOIN quyen_preset p ON p.clinic_id = g.clinic_id AND g.ly_do = 'Thêm nhanh theo preset ' || p.ma WHERE NOT p.active AND g.granted_at > p.sua_luc))::text; ROLLBACK;
-- D18 (mới, PR #522) Luật sức chứa theo phút có hiệu lực TỪ HÔM TRƯỚC ngày tạo (lệch ngày 0h–7h)
BEGIN READ ONLY; SET LOCAL statement_timeout = '20s';
SELECT jsonb_build_object('ma','D18','so_dong',(SELECT count(*) FROM doctor_booking_override WHERE minute_start IS NOT NULL AND effective_from < (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date))::text; ROLLBACK;
