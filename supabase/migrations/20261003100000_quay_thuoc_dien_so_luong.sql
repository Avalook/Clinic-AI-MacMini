-- C14 (Tuyền 01/10/2026): bác sĩ / điều dưỡng hay vội và QUÊN ghi số lượng thuốc.
-- Quầy thu thuốc điền (hoặc sửa phần mình điền) số lượng ngay lúc thu, không bị
-- chặn "bác sĩ chưa nhập số lượng". Ai điền + lúc nào nằm ngay trên dòng đơn để
-- màn kê đơn của bác sĩ hiện "SL do thu ngân điền".
--
-- Chạy lại được.

ALTER TABLE public.prescription
    ADD COLUMN IF NOT EXISTS so_luong_dien_boi uuid REFERENCES public.staff (id),
    ADD COLUMN IF NOT EXISTS so_luong_dien_luc timestamptz;

ALTER TABLE public.prescription
    DROP CONSTRAINT IF EXISTS prescription_so_luong_dien_cap_doi;
ALTER TABLE public.prescription
    ADD CONSTRAINT prescription_so_luong_dien_cap_doi
    CHECK ((so_luong_dien_boi IS NULL) = (so_luong_dien_luc IS NULL));

COMMENT ON COLUMN public.prescription.so_luong_dien_boi IS
    'Nhân sự quầy thu thuốc đã ĐIỀN số lượng (bác sĩ để trống). NULL = số lượng do người kê ghi.';
COMMENT ON COLUMN public.prescription.so_luong_dien_luc IS
    'Lúc quầy điền / sửa số lượng gần nhất. Đi cặp với so_luong_dien_boi.';

-- Chốt đơn: hai ngoại lệ ĐÚNG HẸP cho dòng quầy / số lượng quầy điền (xem trong hàm).
CREATE OR REPLACE FUNCTION public.prescription_dinh_chinh_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    -- Cột không tính khi so "nội dung có đổi không".
    bo_qua constant text[] := ARRAY['updated_at', 'dispense_status'];
    cot_go constant text[] := ARRAY['removed_at', 'removed_by', 'removal_reason',
                                    'removed_in_correction_id', 'superseded_by_id'];
    ky boolean;
    lan record;
    sau record;
    doi_thuoc boolean;
    doi_huong_dan boolean;
    muc integer;
    -- amendment_id của lần đính chính đang dùng (NULL khi không có / chưa ký).
    lan_sua uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF public.luot_da_ky(OLD.visit_id, OLD.clinic_id) THEN
            RAISE EXCEPTION 'Dòng đơn của hồ sơ đã ký không xoá — gỡ bằng đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.removed_at IS NOT NULL OR OLD.created_in_correction_id IS NOT NULL
           OR public.prescription_muc_dau_vet(OLD.id, OLD.clinic_id) > 0 THEN
            RAISE EXCEPTION 'Dòng đơn đã có dấu vết (nhà thuốc / thu tiền / đính chính) — không xoá, phải gỡ bằng đính chính'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;

    -- Dòng QUẦY thêm (nguon = 'QUAY') không thuộc đơn bác sĩ nên không thuộc hồ sơ
    -- đã ký (TT13): quầy bán thêm / sửa số lượng dòng của mình được ở lượt đã ký.
    -- Dấu vết thu / bán / giao (mức C) vẫn chặn như mọi dòng.
    ky := public.luot_da_ky(NEW.visit_id, NEW.clinic_id)
          AND NEW.nguon IS DISTINCT FROM 'QUAY';

    IF TG_OP = 'INSERT' THEN
        IF NEW.removed_at IS NOT NULL OR NEW.superseded_by_id IS NOT NULL
           OR NEW.removed_in_correction_id IS NOT NULL THEN
            RAISE EXCEPTION 'Dòng đơn mới phải là dòng hiện hành'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.created_in_correction_id IS NOT NULL THEN
            SELECT * INTO lan FROM public.prescription_correction
             WHERE id = NEW.created_in_correction_id AND clinic_id = NEW.clinic_id;
            lan_sua := lan.amendment_id;
            IF lan.corrected_at IS DISTINCT FROM now() THEN
                RAISE EXCEPTION 'Dòng thay thế phải sinh trong chính lần đính chính đang ghi'
                    USING ERRCODE = 'check_violation';
            END IF;
            -- Dòng thay thế KHÔNG kế thừa việc nhà thuốc đã làm cho dòng cũ.
            IF NEW.drug_catalog_id IS NOT NULL OR NEW.purchased_qty IS NOT NULL
               OR NEW.dispensed_qty <> 0 OR NEW.closed_at IS NOT NULL
               OR NEW.refusal_reason IS NOT NULL THEN
                RAISE EXCEPTION 'Dòng thay thế bắt đầu trống: không thuốc kho, không số mua, chưa giao, chưa chốt'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        IF ky AND (lan_sua IS NULL
                   OR lan_sua IS DISTINCT FROM
                      public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id)) THEN
            RAISE EXCEPTION 'Hồ sơ đã ký: thêm dòng đơn phải đi qua đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- UPDATE ─ danh tính không đổi.
    IF NEW.id <> OLD.id OR NEW.clinic_id <> OLD.clinic_id
       OR NEW.visit_id IS DISTINCT FROM OLD.visit_id
       OR NEW.created_in_correction_id IS DISTINCT FROM OLD.created_in_correction_id THEN
        RAISE EXCEPTION 'Dòng đơn: danh tính / nguồn gốc đính chính không sửa được'
            USING ERRCODE = 'check_violation';
    END IF;

    -- Dòng lịch sử: bất biến (chỉ updated_at).
    IF OLD.removed_at IS NOT NULL THEN
        IF (to_jsonb(NEW) - bo_qua) IS DISTINCT FROM (to_jsonb(OLD) - bo_qua) THEN
            RAISE EXCEPTION 'Dòng đơn đã được đính chính (lịch sử) — không sửa được'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Gỡ khỏi đơn hiện hành: một thao tác thuần, không kèm đổi nội dung.
    IF NEW.removed_in_correction_id IS NOT NULL OR NEW.removed_at IS NOT NULL
       OR NEW.removed_by IS NOT NULL OR NEW.removal_reason IS NOT NULL THEN
        IF (to_jsonb(NEW) - bo_qua - cot_go) IS DISTINCT FROM (to_jsonb(OLD) - bo_qua - cot_go) THEN
            RAISE EXCEPTION 'Gỡ dòng đơn không được kèm sửa nội dung dòng'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT * INTO lan FROM public.prescription_correction
         WHERE id = NEW.removed_in_correction_id AND clinic_id = NEW.clinic_id;
        IF lan.corrected_at IS DISTINCT FROM now() THEN
            RAISE EXCEPTION 'Gỡ dòng đơn phải bằng lần đính chính đang ghi'
                USING ERRCODE = 'check_violation';
        END IF;
        -- MỘT nguồn sự thật cho người / lúc / lý do gỡ (review 4a P2): lấy từ
        -- lần đính chính. Gửi kèm giá trị khác thì từ chối — không ghi đè lặng
        -- lẽ một đầu vào mâu thuẫn.
        IF (NEW.removed_by IS NOT NULL AND NEW.removed_by IS DISTINCT FROM lan.corrected_by)
           OR (NEW.removed_at IS NOT NULL AND NEW.removed_at IS DISTINCT FROM lan.corrected_at)
           OR (NEW.removal_reason IS NOT NULL
               AND NEW.removal_reason IS DISTINCT FROM lan.reason) THEN
            RAISE EXCEPTION 'Người / lúc / lý do gỡ phải khớp lần đính chính'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.removed_by := lan.corrected_by;
        NEW.removed_at := lan.corrected_at;
        NEW.removal_reason := lan.reason;
        IF ky AND (lan.amendment_id IS NULL
                   OR lan.amendment_id IS DISTINCT FROM
                      public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id)) THEN
            RAISE EXCEPTION 'Hồ sơ đã ký: gỡ dòng đơn phải đi qua đính chính hồ sơ'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.superseded_by_id IS NOT NULL THEN
            SELECT removed_at, created_in_correction_id INTO sau
              FROM public.prescription
             WHERE id = NEW.superseded_by_id AND clinic_id = NEW.clinic_id;
            IF sau.removed_at IS NOT NULL
               OR sau.created_in_correction_id IS DISTINCT FROM NEW.removed_in_correction_id THEN
                RAISE EXCEPTION 'Dòng thay thế phải là dòng hiện hành sinh trong cùng lần đính chính'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        -- Kế hoạch lô chưa gắn lần thu phải nhả trước ("Bác sĩ đính chính đơn").
        -- Phân lô đã gắn lần thu thì giữ — tiền và kho cũ đối soát riêng.
        IF EXISTS (SELECT 1 FROM public.prescription_allocation a
                    WHERE a.prescription_id = OLD.id AND a.clinic_id = OLD.clinic_id
                      AND a.released_at IS NULL AND a.payment_cycle_id IS NULL) THEN
            RAISE EXCEPTION 'Dòng đơn còn phân lô chưa thu — nhả trước khi gỡ'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- QUẦY ĐIỀN SỐ LƯỢNG bác sĩ quên (Tuyền 01/10/2026): chỉ số lượng / đơn vị
    -- của dòng đang để TRỐNG (hoặc dòng chính quầy đã điền), kèm dấu người + lúc
    -- điền. Không phải quyết định chuyên môn — thuốc, cách dùng, lưu ý đứng
    -- nguyên. Lượt đã ký cũng được; dấu vết nhà thuốc / thu / bán / giao (mức B, C) vẫn chặn.
    -- Lưới toàn vẹn, không phải token bảo mật: cột dấu do máy chủ đặt.
    IF NEW.so_luong_dien_boi IS NOT NULL
       AND NEW.so_luong_dien_luc IS DISTINCT FROM OLD.so_luong_dien_luc
       AND (OLD.quantity_num IS NULL OR OLD.so_luong_dien_boi IS NOT NULL)
       AND NEW.drug_name_raw IS NOT DISTINCT FROM OLD.drug_name_raw
       AND NEW.drug_catalog_id IS NOT DISTINCT FROM OLD.drug_catalog_id
       AND NEW.dosage_instructions IS NOT DISTINCT FROM OLD.dosage_instructions
       AND NEW.caution IS NOT DISTINCT FROM OLD.caution
       AND public.prescription_muc_dau_vet(OLD.id, OLD.clinic_id) = 0 THEN
        RETURN NEW;
    END IF;

    -- Dòng hiện hành, đổi nội dung chuyên môn tại chỗ.
    doi_thuoc := NEW.drug_name_raw IS DISTINCT FROM OLD.drug_name_raw
              OR NEW.quantity IS DISTINCT FROM OLD.quantity
              OR NEW.quantity_num IS DISTINCT FROM OLD.quantity_num
              OR NEW.unit IS DISTINCT FROM OLD.unit;
    doi_huong_dan := NEW.dosage_instructions IS DISTINCT FROM OLD.dosage_instructions
                  OR NEW.caution IS DISTINCT FROM OLD.caution;
    IF NOT (doi_thuoc OR doi_huong_dan) THEN
        RETURN NEW;  -- việc vận hành của nhà thuốc
    END IF;
    IF ky AND public.dang_dinh_chinh_ho_so(NEW.visit_id, NEW.clinic_id) IS NULL THEN
        RAISE EXCEPTION 'Hồ sơ đã ký: sửa đơn phải đi qua đính chính hồ sơ'
            USING ERRCODE = 'check_violation';
    END IF;
    muc := public.prescription_muc_dau_vet(OLD.id, OLD.clinic_id);
    IF muc >= 2 THEN
        RAISE EXCEPTION 'Dòng đơn đã thu tiền / bán / giao / trả — đổi thuốc, số lượng, liều hay lưu ý đều phải tạo dòng thay thế'
            USING ERRCODE = 'check_violation';
    END IF;
    IF muc = 1 AND doi_thuoc THEN
        RAISE EXCEPTION 'Dòng đơn nhà thuốc đã chọn lô / đã chốt — đổi thuốc hay số lượng phải tạo dòng thay thế'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_prescription_dinh_chinh_guard ON public.prescription;
CREATE TRIGGER trg_prescription_dinh_chinh_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.prescription
    FOR EACH ROW EXECUTE FUNCTION public.prescription_dinh_chinh_guard();
