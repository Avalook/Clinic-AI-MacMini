-- THUỐC QUY CHUẨN VỀ MỘT KHO (Tuyền 24/09/2026: "kho thuốc giờ chỉ tập trung 1 kho
-- thôi, thuốc quy chuẩn về đi đừng đẻ cái kiểu chưa gắn kho").
--
-- Kho vốn là MỘT (drug_batch không tách cơ sở / kho). "Chưa gắn kho" là dòng đơn
-- không có `drug_catalog_id` — thuốc mẫu của phiếu thiếu dòng ghép, hay tên gõ
-- tay. Từ nay lúc lưu đơn tự gắn theo tên / thêm vào danh mục (dinh_chinh_don
-- `_ma_kho`). Migration này BÙ các dòng cũ:
--   1. Tên chưa có trong danh mục → THÊM vào danh mục kho, `needs_review` (dược
--      sĩ nhập giá sau).
--   2. Gắn mã theo tên trùng khít (không phân biệt hoa thường, gộp khoảng trắng).
-- Chỉ dòng hiện hành của lượt CHƯA KÝ và CHƯA có dấu vết (nhà thuốc / thu tiền /
-- đính chính) — dòng đã khoá giữ nguyên, trigger bảo vệ không cho đổi.
-- Người gắn (dấu vết bắt buộc) = người kê dòng đó. Chạy lại được.

WITH can_gan AS (
    SELECT pr.clinic_id, btrim(regexp_replace(pr.drug_name_raw, '\s+', ' ', 'g')) AS ten
      FROM public.prescription pr
     WHERE pr.drug_catalog_id IS NULL AND pr.removed_at IS NULL
       AND pr.created_by IS NOT NULL
       AND coalesce(btrim(pr.drug_name_raw), '') <> ''
       AND NOT public.luot_da_ky(pr.visit_id, pr.clinic_id)
       AND public.prescription_muc_dau_vet(pr.id, pr.clinic_id) = 0
)
INSERT INTO public.drug_catalog (clinic_id, name_raw, name_base, needs_review)
SELECT DISTINCT c.clinic_id, c.ten, c.ten, true
  FROM can_gan c
 WHERE NOT EXISTS (
       SELECT 1 FROM public.drug_catalog d
        WHERE d.clinic_id = c.clinic_id
          AND (lower(d.name_raw) = lower(c.ten) OR lower(d.name_base) = lower(c.ten)))
ON CONFLICT (clinic_id, name_raw) DO NOTHING;

UPDATE public.prescription pr
   SET drug_catalog_id = (
           SELECT d.id FROM public.drug_catalog d
            WHERE d.clinic_id = pr.clinic_id AND d.is_active
              AND (lower(d.name_raw) = lower(btrim(regexp_replace(pr.drug_name_raw, '\s+', ' ', 'g')))
                   OR lower(d.name_base) = lower(btrim(regexp_replace(pr.drug_name_raw, '\s+', ' ', 'g'))))
            ORDER BY d.created_at, d.id LIMIT 1),
       drug_mapped_by = pr.created_by,
       drug_mapped_at = now(),
       updated_at = now()
 WHERE pr.drug_catalog_id IS NULL AND pr.removed_at IS NULL
   AND pr.created_by IS NOT NULL
   AND coalesce(btrim(pr.drug_name_raw), '') <> ''
   AND NOT public.luot_da_ky(pr.visit_id, pr.clinic_id)
   AND public.prescription_muc_dau_vet(pr.id, pr.clinic_id) = 0
   AND EXISTS (
       SELECT 1 FROM public.drug_catalog d
        WHERE d.clinic_id = pr.clinic_id AND d.is_active
          AND (lower(d.name_raw) = lower(btrim(regexp_replace(pr.drug_name_raw, '\s+', ' ', 'g')))
               OR lower(d.name_base) = lower(btrim(regexp_replace(pr.drug_name_raw, '\s+', ' ', 'g')))));
