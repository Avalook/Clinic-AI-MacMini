-- G9 — ĐẦU DÒ BIO CHỌN Ở CHỈ ĐỊNH CẬN LÂM SÀNG (Tuyền chốt 14/10/2026, Q14/Q14b).
--
-- Trước: Bio chỉ thêm ở quầy thu dịch vụ ("Mua thêm vật tư"), dòng `luot_vat_tu`
-- theo LƯỢT, không biết chỉ định nào cần nó. Nay bác sĩ chọn "Bio 1 lần / nhiều
-- lần" ngay ở chỉ định (siêu âm đầu dò, tập máy Bio…): dòng `luot_vat_tu` GẮN
-- `order_id`, và tiền đi theo chỉ định — chỉ định huỷ / khách không chọn làm thì
-- Bio không vào hoá đơn, không thành nợ; khôi phục chỉ định thì Bio quay lại
-- (suy từ trạng thái chỉ định lúc đọc, không chép trạng thái sang dòng Bio).
--
-- Dòng cũ (đã thêm ở quầy) giữ nguyên: order_id NULL. KHÔNG đổi luật duyệt của
-- trigger `luot_vat_tu_gac` (hàng can_ql_duyet vẫn chỉ quản lý duyệt) — việc đó
-- của G8b.
--
-- Chạy lại được (IF NOT EXISTS / DROP … IF EXISTS), không BEGIN/COMMIT.

-- ── 1. Cột mới ───────────────────────────────────────────────────────────────
ALTER TABLE public.luot_vat_tu
    ADD COLUMN IF NOT EXISTS order_id uuid
        REFERENCES public.service_order(id) ON DELETE RESTRICT;
ALTER TABLE public.luot_vat_tu ADD COLUMN IF NOT EXISTS bo_ly_do text;

COMMENT ON COLUMN public.luot_vat_tu.order_id IS
'Chỉ định (service_order) mà vật tư này đi kèm — đầu dò Bio chọn ở chỉ định CLS (G9, 14/10/2026). NULL = dòng thêm ở quầy theo lượt (đường cũ). Tiền theo chỉ định: huỷ / khách không chọn làm thì không tính.';
COMMENT ON COLUMN public.luot_vat_tu.bo_ly_do IS
'Lý do bỏ dòng (quầy thu bỏ Bio do bác sĩ chọn thì bắt ghi lý do — G9). Chỉ có khi đã bỏ (bo_luc).';

ALTER TABLE public.luot_vat_tu DROP CONSTRAINT IF EXISTS luot_vat_tu_bo_ly_do_hop_le;
ALTER TABLE public.luot_vat_tu ADD CONSTRAINT luot_vat_tu_bo_ly_do_hop_le
    CHECK (bo_ly_do IS NULL
           OR (bo_luc IS NOT NULL AND char_length(btrim(bo_ly_do)) BETWEEN 5 AND 500));

-- ── 2. Một mặt hàng một dòng SỐNG — theo (lượt, hàng, chỉ định) ──────────────
-- Trước: (lượt, hàng). Hai siêu âm đầu dò cùng lượt đều chọn Bio 1 lần phải ra
-- HAI dòng (mỗi dòng theo chỉ định của nó); dòng quầy (order_id NULL) vẫn gộp
-- "bấm nữa = cộng số lượng" như cũ.
DROP INDEX IF EXISTS public.luot_vat_tu_mot_dong_song;
CREATE UNIQUE INDEX IF NOT EXISTS luot_vat_tu_mot_dong_song_v2
    ON public.luot_vat_tu (
        clinic_id, visit_id, service_price_id,
        (coalesce(order_id, '00000000-0000-0000-0000-000000000000'::uuid)))
    WHERE bo_luc IS NULL;
CREATE INDEX IF NOT EXISTS luot_vat_tu_theo_chi_dinh
    ON public.luot_vat_tu (clinic_id, order_id) WHERE order_id IS NOT NULL;

-- ── 3. Lưới cuối: chỉ định phải CÙNG lượt, CÙNG phòng khám ───────────────────
CREATE OR REPLACE FUNCTION public.luot_vat_tu_chi_dinh_khop()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.order_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.order_id IS NOT DISTINCT FROM OLD.order_id THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.service_order o
         WHERE o.id = NEW.order_id AND o.clinic_id = NEW.clinic_id
           AND o.visit_id = NEW.visit_id) THEN
        RAISE EXCEPTION 'luot_vat_tu: chỉ định không thuộc lượt khám / phòng khám này'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_luot_vat_tu_chi_dinh_khop ON public.luot_vat_tu;
CREATE TRIGGER trg_luot_vat_tu_chi_dinh_khop
    BEFORE INSERT OR UPDATE ON public.luot_vat_tu
    FOR EACH ROW EXECUTE FUNCTION public.luot_vat_tu_chi_dinh_khop();
