-- LẦN CHỈ ĐỊNH (26/09/2026 — lát 4 bản giao diện mẫu). Tuyền chốt: bấm "+ Chỉ định
-- thêm" là một LẦN mới trong cùng lượt khám (lượt = check-in → check-out); xem lại
-- lần cũ, dịch vụ đã chỉ định ở lần trước vẫn chỉ định lại được.
--
-- Trước đây "lần" suy từ vòng khám (`consultation.round_no`) — chỉ định thêm trong
-- CÙNG phiên dùng chung vòng nên mọi lần hiện là "Lần 1". Mở hẳn một phiên khám mới
-- chỉ để đánh số thì khách bị đẩy ra hàng chờ và mất trạng thái "đang khám".
--
-- Nay: cột `lan_chi_dinh`, gán bằng TRIGGER — mọi chỉ định tạo (hoặc nháp được
-- duyệt) trong CÙNG một giao dịch là MỘT lần (ba đường tạo chỉ định đều đi qua đây, không sửa từng đường);
-- lần kế = max của lượt + 1, khoá theo lượt (advisory lock) nên hai người bấm cùng
-- lúc không trùng số. Chỉ định MANG SANG từ lượt trước: không có lần (NULL).
-- Nháp chưa duyệt / đã huỷ: chưa có lần. Dữ liệu cũ đánh số bù theo đúng cách
-- tính cũ (thứ tự vòng khám), bỏ dòng huỷ. Chạy lại được.

ALTER TABLE public.service_order ADD COLUMN IF NOT EXISTS lan_chi_dinh smallint;

CREATE OR REPLACE FUNCTION public.gan_lan_chi_dinh()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  khoa text;
  lan text;
BEGIN
  -- Mang sang (dòng của lượt trước chuyển visit_id sang lượt này): bỏ số lần của
  -- lượt cũ — nó không thuộc lần nào ở lượt mới.
  IF NEW.mang_tu_visit_id IS NOT NULL THEN
    NEW.lan_chi_dinh := NULL;
    RETURN NEW;
  END IF;
  IF NEW.lan_chi_dinh IS NOT NULL OR NEW.visit_id IS NULL OR NEW.exec_status IN ('draft', 'cancelled') THEN
    RETURN NEW;
  END IF;
  -- Sửa dòng: chỉ đánh số lúc NHÁP được duyệt (thư ký ghi nháp, bác sĩ duyệt —
  -- lần tính theo lúc duyệt). Dòng cũ chưa có số giữ nguyên NULL.
  IF TG_OP = 'UPDATE' AND OLD.exec_status IS DISTINCT FROM 'draft' THEN
    RETURN NEW;
  END IF;
  khoa := 'clinicai.lan_' || replace(NEW.visit_id::text, '-', '');
  lan := nullif(current_setting(khoa, true), '');
  IF lan IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext('lan_chi_dinh:' || NEW.visit_id::text));
    SELECT (coalesce(max(o.lan_chi_dinh), 0) + 1)::text INTO lan
      FROM public.service_order o
     WHERE o.visit_id = NEW.visit_id AND o.clinic_id = NEW.clinic_id;
    PERFORM set_config(khoa, lan, true);  -- chỉ sống trong giao dịch này
  END IF;
  NEW.lan_chi_dinh := lan::smallint;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_gan_lan_chi_dinh ON public.service_order;
CREATE TRIGGER trg_gan_lan_chi_dinh
  BEFORE INSERT OR UPDATE OF exec_status, visit_id, mang_tu_visit_id ON public.service_order
  FOR EACH ROW EXECUTE FUNCTION public.gan_lan_chi_dinh();

-- Đánh số bù dữ liệu cũ: thứ tự vòng khám có chỉ định trong lượt (như cách cũ).
WITH so AS (
  SELECT o.id,
         dense_rank() OVER (PARTITION BY o.visit_id ORDER BY c.round_no) AS lan
    FROM public.service_order o
    JOIN public.consultation c
      ON c.id = o.consultation_id AND c.clinic_id = o.clinic_id
     AND c.visit_id = o.visit_id
   WHERE o.lan_chi_dinh IS NULL AND o.mang_tu_visit_id IS NULL
     AND o.exec_status NOT IN ('draft', 'cancelled')
)
UPDATE public.service_order o SET lan_chi_dinh = so.lan
  FROM so WHERE so.id = o.id;

COMMENT ON COLUMN public.service_order.lan_chi_dinh IS
'Lần chỉ định trong lượt khám (1, 2, 3…) — mọi chỉ định cùng một giao dịch là một lần; mang sang từ lượt trước = NULL (26/09/2026).';
