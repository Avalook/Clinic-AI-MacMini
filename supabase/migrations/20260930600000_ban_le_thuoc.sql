-- V8 (30/09/2026): KHÁCH CHỈ ĐẾN MUA THUỐC — lượt "Bán lẻ".
--
-- Mọi thứ ở quầy thuốc bám vào một lượt (`visit`): đơn bán (`prescription`),
-- hoá đơn, lần thu, phân lô. Khách không khám mà chỉ mua thuốc vẫn cần một
-- lượt để gắn các thứ ấy — nhưng lượt đó KHÔNG phải lượt khám: không tiền khám,
-- không hàng chờ bác sĩ, không điều phối, không hành trình, không đếm vào số
-- "lượt khám".
--
-- CỜ TRÊN LƯỢT, KHÔNG PHẢI MỘT `service_type` ĐẶC BIỆT. Một loại khám giả sẽ lọt
-- vào mọi chỗ đọc `service_type` (danh sách loại khám ở đặt lịch, phí khám theo
-- loại, sức chứa, sổ bác sĩ theo loại, báo cáo nhóm theo loại) và mỗi chỗ phải
-- nhớ loại nó ra. Cờ `ban_le` mặc định FALSE: dòng cũ không đổi nghĩa, và chỗ
-- nào cần loại lượt bán lẻ thì nói thẳng `NOT v.ban_le`.
ALTER TABLE visit ADD COLUMN IF NOT EXISTS ban_le boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN visit.ban_le IS
  'Lượt BÁN LẺ (V8 30/09/2026): khách chỉ mua thuốc. Không tiền khám, không '
  'hàng chờ/điều phối/hành trình, không tính vào số lượt khám. Thu xong tiền '
  'thuốc thì tự đóng (closed_at).';

-- MỘT lượt bán lẻ đang mở cho mỗi khách. Hai người cùng bấm "Khách mua thuốc"
-- cho cùng một khách (hay một người bấm hai lần) phải ra CÙNG một lượt — chốt ở
-- Postgres (ON CONFLICT … DO NOTHING rồi đọc lại), không tự khoá trong Python.
CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_ban_le_dang_mo
    ON visit (clinic_id, clinic_patient_id)
 WHERE ban_le AND closed_at IS NULL;

-- Màn Nhà thuốc đọc lượt bán lẻ trong ngày (kể cả khi chưa có đơn).
CREATE INDEX IF NOT EXISTS idx_visit_ban_le_ngay
    ON visit (clinic_id, created_at DESC)
 WHERE ban_le;
