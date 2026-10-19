-- Đối chiếu thuốc đã giao: được ghi lô thực tế ở KHO, không tạo phiếu chuyển giả.
-- Bán/phân lô trước giao vẫn giữ guard QUAY; chỉ pending giao thật được mở.
CREATE OR REPLACE FUNCTION public.gac_ban_tu_quay() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
DECLARE lo record;
BEGIN
    IF NEW.txn_type NOT IN ('SALE', 'DISPENSE', 'RETURN_RECEIVED', 'CHUYEN_VAO') THEN
        RETURN NEW;
    END IF;
    SELECT noi_chua, expiry_date, drug_catalog_id, unit, location_id INTO lo FROM public.drug_batch
     WHERE id = NEW.drug_batch_id AND clinic_id = NEW.clinic_id;
    -- Không thấy lô (sai phòng khám / không tồn tại): để khoá ngoại và
    -- `inventory_txn_apply` từ chối bằng đúng câu của chúng, không đè bằng câu này.
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    IF NEW.txn_type = 'CHUYEN_VAO' THEN
        IF lo.noi_chua = 'QUAY'
           AND lo.expiry_date < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date THEN
            RAISE EXCEPTION 'Lô đã hết hạn — không chuyển ra quầy.'
                USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_het_han_quay';
        END IF;
    ELSIF NEW.txn_type = 'RETURN_RECEIVED' AND lo.noi_chua = 'KHO'
          AND NEW.ref_type = 'drug_return'
          AND EXISTS (
            SELECT 1 FROM public.drug_return r
              JOIN public.inventory_txn x
                ON x.id = r.original_dispense_txn_id AND x.clinic_id = r.clinic_id
              JOIN public.prescription p
                ON p.id = r.prescription_id AND p.clinic_id = r.clinic_id
             WHERE r.id = NEW.ref_id AND r.clinic_id = NEW.clinic_id
               AND r.drug_batch_id = NEW.drug_batch_id
               AND r.returned_qty = NEW.quantity
               AND r.returned_qty > 0
               AND x.txn_type = 'DISPENSE' AND x.ref_type = 'prescription'
               AND x.ref_id = p.id AND x.drug_batch_id = NEW.drug_batch_id
               AND -x.quantity >= r.returned_qty
               AND p.drug_catalog_id = lo.drug_catalog_id
               AND lower(trim(coalesce(p.unit, ''))) =
                   lower(trim(coalesce(lo.unit, '')))
               AND coalesce(public.co_so_cua_luot(r.clinic_id, p.visit_id),
                            lo.location_id) = lo.location_id) THEN
        -- Trả về đúng lô đã giao từ kho, vẫn cách ly qua drug_return.disposition.
        RETURN NEW;
    ELSIF lo.noi_chua IS DISTINCT FROM 'QUAY'
          AND NOT (NEW.txn_type = 'DISPENSE'
                   AND NEW.ref_type = 'prescription'
                   AND EXISTS (
                     SELECT 1 FROM public.thuoc_giao_chua_gan_lo g
                       JOIN public.prescription p
                         ON p.id = g.prescription_id AND p.clinic_id = g.clinic_id
                      WHERE g.clinic_id = NEW.clinic_id
                        AND g.prescription_id = NEW.ref_id
                        AND g.drug_batch_id IS NULL
                        AND g.so_luong = -NEW.quantity
                        AND g.drug_catalog_id = lo.drug_catalog_id
                        AND lower(trim(coalesce(p.unit, ''))) =
                            lower(trim(coalesce(lo.unit, '')))
                        AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id),
                                     lo.location_id) = lo.location_id)) THEN
        RAISE EXCEPTION 'Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_o_kho';
    END IF;
    RETURN NEW;
END
$$;
