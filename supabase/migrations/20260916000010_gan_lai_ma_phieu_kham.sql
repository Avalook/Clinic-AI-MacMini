-- Gắn lại mã phiếu khám cho từng loại dịch vụ — trên final cloud nó đã MẤT.
--
-- Migration 20260807000007 đã gắn đúng: PHU_KHOA→PK, SAN_1→SK, NOI_TIET→NT,
-- NAM_KHOA→NK, HIEM_MUON→HMVS, và ghi rằng Sản 2/3, Khám tiền sản, Hồ sơ sinh
-- cũng trỏ SK. Nhưng đo ngày 16/09/2026 trên VPS mới: CẢ 14 loại khám đều
-- `form_code = NULL`, và tên đã trở về dạng cũ ("Sản 1", "Nội tiết - Tình
-- dục"). Tức dữ liệu `service_type` đã bị nạp đè SAU khi migration kia chạy, và
-- sổ migration vẫn ghi "đã áp" — nên không ai chạy lại nó.
--
-- HỆ QUẢ ĐO ĐƯỢC: Bàn khám bác sĩ hiện ô vàng "Dịch vụ … chưa gắn biểu mẫu khám
-- nào" cho MỌI khách, không riêng "Sản 1". Bác sĩ không mở được phiếu nào.
--
-- CHỈ GẮN MÃ PHIẾU. Không đổi tên, không bật tắt dịch vụ: hai việc ấy đổi thứ
-- khách nhìn thấy khi đặt lịch và ảnh hưởng lịch hẹn đang có — là quyết định của
-- phòng khám, không phải một bước sửa dữ liệu.
--
-- CHẠY LẠI ĐƯỢC. Chỉ ghi chỗ đang khác giá trị đúng, nên lần sau nếu dữ liệu lại
-- bị nạp đè thì chạy lại migration này là đủ.

BEGIN;

UPDATE public.service_type st
   SET form_code = m.form_code
  FROM (VALUES
    ('PHU_KHOA', 'PK'),
    ('SAN_1', 'SK'),
    -- Số 1/2/3 là TẦNG, không phải loại khám — cùng một phiếu Sản khoa.
    ('SAN_2', 'SK'),
    ('SAN_3', 'SK'),
    ('KHAM_TIEN_SAN', 'SK'),
    ('HO_SO_SINH', 'SK'),
    ('NOI_TIET_TINH_DUC', 'NT'),
    ('NAM_KHOA', 'NK'),
    ('HIEM_MUON', 'HMVS')
  ) AS m(code, form_code)
 WHERE st.code = m.code
   AND st.form_code IS DISTINCT FROM m.form_code
   -- Chỉ gắn phiếu đang BẬT trong danh mục. Gắn một phiếu đang tắt thì bàn khám
   -- mời mở một phiếu mà máy chủ sẽ từ chối lưu.
   AND EXISTS (
       SELECT 1 FROM public.clinical_form_catalogue c
        WHERE c.clinic_id = st.clinic_id
          AND c.form_code = m.form_code
          AND c.is_active
   );

DO $$
DECLARE
    co_phieu integer;
    tong integer;
BEGIN
    SELECT count(*) FILTER (WHERE form_code IS NOT NULL), count(*)
      INTO co_phieu, tong
      FROM public.service_type WHERE is_active;
    RAISE NOTICE 'Loại khám đang bật có phiếu: % / %', co_phieu, tong;
END $$;

COMMIT;
