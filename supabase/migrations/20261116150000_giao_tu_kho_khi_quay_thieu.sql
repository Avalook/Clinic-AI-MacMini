-- Quầy không đủ thì giao luôn từ KHO (Tuyền 16/11/2026, thu tiền thuốc = giao luôn).
--
-- Luật: lần giao không chỉ định lô trừ QUẦY trước (FEFO); quầy thiếu thì phần còn lại
-- trừ ở KHO, lô hạn gần nhất; cả hai thiếu mới vào sổ chờ gán lô. Chốt `lo_o_kho` trước
-- đây chỉ mở cho lần GÁN LÔ (dòng chờ gán khớp số). Nay mở thêm đúng một cửa: DISPENSE
-- trỏ dòng đơn, mang dấu `reason` của đường tự chọn lô
-- (`pharmacy_service.LY_DO_LAY_TU_KHO`), lô còn hạn, đúng thuốc, đúng cơ sở của lượt,
-- và lượt đã thu tiền thuốc (PAID). Bán (SALE) / phân lô / giao chọn lô KHO bằng tay
-- vẫn bị chặn như cũ.
--
-- Chỉ thay hàm, không đụng dữ liệu. Hoàn tác: chạy lại định nghĩa ở
-- 20261101400000_gan_lo_tu_kho_theo_quy_doi.sql.

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
               AND coalesce(public.co_so_cua_luot(r.clinic_id, p.visit_id),
                            lo.location_id) = lo.location_id) THEN
        -- Trả về đúng lô đã giao từ kho, vẫn cách ly qua drug_return.disposition.
        RETURN NEW;
    ELSIF lo.noi_chua IS DISTINCT FROM 'QUAY'
          AND NOT (NEW.txn_type = 'DISPENSE'
                   AND NEW.ref_type = 'prescription'
                   AND (
                     EXISTS (
                       SELECT 1 FROM public.thuoc_giao_chua_gan_lo g
                         JOIN public.prescription p
                           ON p.id = g.prescription_id AND p.clinic_id = g.clinic_id
                        WHERE g.clinic_id = NEW.clinic_id
                          AND g.prescription_id = NEW.ref_id
                          AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL
                          AND g.drug_catalog_id = lo.drug_catalog_id
                          -- Dòng bán hộp, lô tính gói: so sau khi quy đổi. Đơn vị chưa
                          -- khai thì so thẳng như cũ. Sai số là phần làm tròn của sổ.
                          AND abs(coalesce(
                                  g.so_luong
                                  * public.he_so_don_vi(g.clinic_id, g.drug_catalog_id, p.unit)
                                  / public.he_so_don_vi(g.clinic_id, g.drug_catalog_id, lo.unit),
                                  g.so_luong) + NEW.quantity) <= 0.06
                          AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id),
                                       lo.location_id) = lo.location_id)
                     -- Quầy không đủ: lần giao tự chọn lô lấy phần còn lại ở kho.
                     -- coalesce: reason NULL thì cả biểu thức thành NULL và
                     -- ELSIF bỏ qua, tức là KHÔNG chặn — bẫy đã cắn lúc viết.
                     OR (coalesce(NEW.reason, '') = 'Quầy không đủ — lấy từ kho'
                         AND lo.noi_chua = 'KHO'
                         AND (lo.expiry_date IS NULL
                              OR lo.expiry_date >=
                                 (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
                         AND EXISTS (
                           SELECT 1 FROM public.prescription p
                             JOIN public.payment_cycle c
                               ON c.clinic_id = p.clinic_id AND c.visit_id = p.visit_id
                              AND c.kind = 'thuoc' AND c.status = 'PAID'
                            WHERE p.id = NEW.ref_id AND p.clinic_id = NEW.clinic_id
                              AND p.drug_catalog_id = lo.drug_catalog_id
                              AND coalesce(public.co_so_cua_luot(p.clinic_id, p.visit_id),
                                           lo.location_id) = lo.location_id))
                   )) THEN
        RAISE EXCEPTION 'Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_o_kho';
    END IF;
    RETURN NEW;
END
$$;
