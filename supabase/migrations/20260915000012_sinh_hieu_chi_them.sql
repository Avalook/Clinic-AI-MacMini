-- SINH HIỆU LÀ LỊCH SỬ CHỈ THÊM (15/09/2026).
--
-- LUẬT (CONTEXT v1.0 [PM]): 100% đo huyết áp; khách có thai đo thêm chiều cao
-- và cân nặng. Sinh hiệu phải biết ai đo, lúc nào, và đo lại không làm mất số cũ.
--
-- Lát 1 (20260911000001) đã có `vital_measurement`: mỗi lần đo một dòng, huyết
-- áp hai số NOT NULL. Nhưng chỉ màn luồng khám mới ghi vào đó; hồ sơ khám cũ
-- (ClinicalRecordForm) vẫn ghi đè JSON `clinical_record.soap_objective.vitals`.
-- Từ bản này clinical_record_service ghi CẢ HAI đường vào cùng bảng này — không
-- dựng bảng lịch sử thứ hai.
--
-- Bảng thiếu một điều cho đúng nghĩa "lịch sử": không gì cấm sửa/xoá dòng đã
-- đo. Trigger dưới đây cấm cả hai, như `visit` (prevent_hard_delete) — lượt
-- khám cha vốn không xoá được nên FK CASCADE không bao giờ cần đi qua đây.

CREATE OR REPLACE FUNCTION public.vital_measurement_chi_them()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
BEGIN
    RAISE EXCEPTION 'Sinh hiệu đã đo chỉ thêm — đo lại thì ghi dòng mới'
        USING ERRCODE = 'check_violation';
END;
$fn$;

DROP TRIGGER IF EXISTS trg_vital_measurement_chi_them ON public.vital_measurement;
CREATE TRIGGER trg_vital_measurement_chi_them
    BEFORE UPDATE OR DELETE ON public.vital_measurement
    FOR EACH ROW EXECUTE FUNCTION public.vital_measurement_chi_them();
