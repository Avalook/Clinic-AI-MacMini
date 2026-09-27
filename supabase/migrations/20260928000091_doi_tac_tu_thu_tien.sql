-- ĐỐI TÁC TỰ THU TIỀN (Tuyền chốt 27/09/2026, câu Q1): "Tiền dịch vụ đối tác:
-- KHÁCH TRẢ TRỰC TIẾP cho đối tác, màn đối tác cũng phải có ghi nhận thanh toán
-- thực hiện."
--
-- 1. BÊN THU. Mọi dòng giá dịch vụ có PHÒNG LÀM là bước làm bên ngoài
--    (`node_definition.lam_ben_ngoai` — LAYMAU-MAU, LAYMAU-NUOCTIEU,
--    LAYMAU-AMDAO, SANGLOC-COTUCUNG, HINHANH-NGOAI hôm nay) chuyển sang
--    `billing_owner = 'EXTERNAL_PARTNER'`. Khoá theo NODE, không theo tên. Giá
--    GIỮ NGUYÊN — nay là giá THAM KHẢO đối tác thu (quầy hiện, không cộng).
--    Trước đây prod 110/110 dịch vụ CLINIC: quầy cộng tiền đối tác vào hoá đơn
--    phòng khám.
--
-- 2. GHI NHẬN THANH TOÁN CỦA ĐỐI TÁC. Bảng CỦA khối Đối tác: đối tác bấm "Đã
--    thu tiền khách" cho một việc (số tiền, hình thức, ghi chú). Một việc có
--    TỐI ĐA MỘT ghi nhận còn hiệu lực; sửa = huỷ bản cũ (bắt buộc lý do) rồi
--    ghi bản mới — không viết lại quá khứ. Phòng khám (quầy, Xem lượt) đọc để
--    biết "Đối tác đã thu / chưa thu". Đây KHÔNG phải sổ tiền của phòng khám
--    (payment_cycle / payment_bill_line): tiền này không vào két phòng khám.
--
-- Chạy lại được.

UPDATE public.service_price sp
   SET billing_owner = 'EXTERNAL_PARTNER', updated_at = now()
  FROM public.node_definition n
 WHERE n.clinic_id = sp.clinic_id
   AND n.code = sp.node_code
   AND n.lam_ben_ngoai
   AND sp."group" = 'dich_vu'
   AND sp.billing_owner <> 'EXTERNAL_PARTNER';

-- Nhận việc KHÔNG chờ phòng khám thu tiền: đối tác tự lấy mẫu + tự thu thì
-- khách chốt làm ở quầy là đủ (`service_selection.confirmed`) — lý do mới.
ALTER TABLE public.doi_tac_nhan_viec
    DROP CONSTRAINT IF EXISTS doi_tac_nhan_viec_ly_do_check;
ALTER TABLE public.doi_tac_nhan_viec
    ADD CONSTRAINT doi_tac_nhan_viec_ly_do_check
    CHECK (ly_do IN ('DA_THU_TIEN', 'KHACH_DA_CHON', 'DA_LAY_MAU', 'BU_DU_LIEU'));

CREATE TABLE IF NOT EXISTS public.doi_tac_thanh_toan (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    service_order_id uuid NOT NULL REFERENCES public.service_order (id)
                          ON DELETE RESTRICT,
    so_tien          numeric(12, 0) NOT NULL CHECK (so_tien >= 0),
    hinh_thuc        text NOT NULL CHECK (hinh_thuc IN ('CASH', 'TRANSFER')),
    ghi_chu          text CHECK (ghi_chu IS NULL OR length(ghi_chu) <= 2000),
    ghi_boi          uuid NOT NULL REFERENCES public.staff (id),
    ghi_luc          timestamptz NOT NULL DEFAULT now(),
    huy_luc          timestamptz,
    huy_boi          uuid REFERENCES public.staff (id),
    ly_do_huy        text,
    -- Huỷ thì phải biết AI huỷ, LÚC NÀO, VÌ SAO — và ngược lại.
    CONSTRAINT doi_tac_thanh_toan_huy_co_dau_vet CHECK (
        (huy_luc IS NULL AND huy_boi IS NULL AND ly_do_huy IS NULL)
        OR (huy_luc IS NOT NULL AND huy_boi IS NOT NULL
            AND length(btrim(ly_do_huy)) BETWEEN 3 AND 2000))
);

-- Một việc — một ghi nhận còn hiệu lực (hai người bấm cùng lúc: một người thua).
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_thanh_toan_con_hieu_luc
    ON public.doi_tac_thanh_toan (clinic_id, service_order_id)
    WHERE huy_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_doi_tac_thanh_toan_chi_dinh
    ON public.doi_tac_thanh_toan (clinic_id, service_order_id, ghi_luc DESC);

COMMENT ON TABLE public.doi_tac_thanh_toan IS
'Đối tác ghi nhận đã thu tiền khách cho một việc làm bên ngoài (Q1, 27/09/2026). '
'Không phải sổ tiền phòng khám. Sửa = huỷ (có lý do) rồi ghi mới.';

-- Nội dung ghi nhận không sửa được; chỉ được ĐÓNG (huỷ) đúng một lần.
CREATE OR REPLACE FUNCTION public.doi_tac_thanh_toan_chi_huy()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'doi_tac_thanh_toan: không xoá — huỷ kèm lý do'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.huy_luc IS NOT NULL
       OR (NEW.clinic_id, NEW.service_order_id, NEW.so_tien, NEW.hinh_thuc,
           NEW.ghi_chu, NEW.ghi_boi, NEW.ghi_luc)
          IS DISTINCT FROM
          (OLD.clinic_id, OLD.service_order_id, OLD.so_tien, OLD.hinh_thuc,
           OLD.ghi_chu, OLD.ghi_boi, OLD.ghi_luc) THEN
        RAISE EXCEPTION 'doi_tac_thanh_toan: chỉ được huỷ ghi nhận đang hiệu lực'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_doi_tac_thanh_toan_chi_huy ON public.doi_tac_thanh_toan;
CREATE TRIGGER trg_doi_tac_thanh_toan_chi_huy
    BEFORE UPDATE OR DELETE ON public.doi_tac_thanh_toan
    FOR EACH ROW EXECUTE FUNCTION public.doi_tac_thanh_toan_chi_huy();

ALTER TABLE public.doi_tac_thanh_toan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS doi_tac_thanh_toan_select_own_clinic ON public.doi_tac_thanh_toan;
CREATE POLICY doi_tac_thanh_toan_select_own_clinic ON public.doi_tac_thanh_toan
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.doi_tac_thanh_toan TO service_role;
