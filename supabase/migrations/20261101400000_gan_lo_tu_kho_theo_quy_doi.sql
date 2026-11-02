-- Gán lô từ KHO khi dòng đơn bán khác đơn vị lô (31/10/2026, bấm thật bản gộp).
--
-- Bán 1 hộp (30 gói), quầy thiếu 1 gói: dòng chờ gán ghi 0,033 hộp, sổ trừ 1 gói. Chốt
-- ở trigger còn đòi cùng đơn vị và cùng con số, nên gán từ KHO báo "Lô này đang ở KHO"
-- dù màn cho chọn. Khách trả về lô kho cũng vướng cùng điều kiện đơn vị.
-- Chỉ thay hàm, không đụng dữ liệu. Hoàn tác: chạy lại định nghĩa ở
-- 20261101100000_kho_quay_that.sql.

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
                   AND EXISTS (
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
                                     lo.location_id) = lo.location_id)) THEN
        RAISE EXCEPTION 'Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao.'
            USING ERRCODE = 'exclusion_violation', CONSTRAINT = 'lo_o_kho';
    END IF;
    RETURN NEW;
END
$$;

-- Dòng kê "10 v" với thuốc bán viên: Python nhận ra, SQL thì không, nên phần chờ gán không
-- được tách khi kiểm ca và kho trừ hai lần. Hai bên dùng chung một luật, từ chắc tới yếu,
-- mỗi bước phải ra đúng một đơn vị (xem `BangDonVi._khop`).
CREATE OR REPLACE FUNCTION public.bo_dau_don_vi(p_don_vi text)
RETURNS text
LANGUAGE sql STABLE
AS $$
    SELECT translate(public.chuan_don_vi(p_don_vi),
        'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ',
        'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd')
$$;

CREATE OR REPLACE FUNCTION public.he_so_don_vi(p_clinic uuid, p_thuoc uuid, p_don_vi text)
RETURNS numeric
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    c text := public.chuan_don_vi(p_don_vi);
    kd text := public.bo_dau_don_vi(p_don_vi);
    goc text;
    n integer;
    hs numeric;
BEGIN
    IF c = '' THEN
        RETURN NULL;
    END IF;
    SELECT public.chuan_don_vi(d.don_vi_ban) INTO goc
      FROM public.drug_catalog d
     WHERE d.id = p_thuoc AND d.clinic_id = p_clinic;
    IF c = goc THEN
        RETURN 1;
    END IF;
    SELECT q.he_so INTO hs FROM public.thuoc_quy_doi q
     WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc AND q.don_vi = c;
    IF FOUND THEN
        RETURN hs;
    END IF;
    FOR buoc IN 1..3 LOOP
        SELECT count(*), max(k.he_so) INTO n, hs
          FROM (SELECT goc AS don_vi, 1::numeric AS he_so WHERE coalesce(goc, '') <> ''
                UNION ALL
                SELECT q.don_vi, q.he_so FROM public.thuoc_quy_doi q
                 WHERE q.clinic_id = p_clinic AND q.drug_catalog_id = p_thuoc) k
         WHERE CASE buoc
                   WHEN 1 THEN public.bo_dau_don_vi(k.don_vi) = kd
                   WHEN 2 THEN public.bo_dau_don_vi(k.don_vi) = split_part(kd, ' ', 1)
                   ELSE length(kd) <= 2 AND public.bo_dau_don_vi(k.don_vi) LIKE kd || '%'
               END;
        IF n = 1 THEN
            RETURN hs;
        ELSIF n > 1 THEN
            RETURN NULL;
        END IF;
    END LOOP;
    RETURN NULL;
END $$;
