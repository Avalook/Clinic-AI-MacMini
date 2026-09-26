-- TỆP KẾT QUẢ THEO BÊN (26/09/2026 — lát 3 bản giao diện mẫu). Mẫu hai bên
-- (Thai A | Thai B, trái | phải) có HAI ô tải riêng; mỗi tệp gắn `ben` = chỉ số
-- cột của mục bảng đầu tiên trong mẫu (0 = cột đầu). NULL = tệp chung / tệp cũ
-- (màn xếp vào bên đầu). Chạy lại được.

ALTER TABLE public.tep_ket_qua ADD COLUMN IF NOT EXISTS ben smallint;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tep_ket_qua_ben') THEN
    ALTER TABLE public.tep_ket_qua
      ADD CONSTRAINT tep_ket_qua_ben CHECK (ben IS NULL OR ben BETWEEN 0 AND 7);
  END IF;
END;
$$;

COMMENT ON COLUMN public.tep_ket_qua.ben IS
'Bên của tệp trong mẫu hai bên (chỉ số cột mục bảng: Thai A=0, Thai B=1…). NULL = tệp chung.';
