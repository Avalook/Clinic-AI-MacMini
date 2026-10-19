-- Đơn vị là nghĩa của mọi số lượng đã ghi sổ. Đổi sau giao dịch sẽ đổi cách
-- hiểu tồn hiện tại và toàn bộ lịch sử; muốn dùng đơn vị khác phải tạo mặt hàng mới.
BEGIN;

CREATE OR REPLACE FUNCTION public.vat_tu_chan_doi_don_vi_co_giao_dich()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF OLD."group" = 'vat_tu'
       AND NEW.don_vi IS DISTINCT FROM OLD.don_vi
       AND (
           EXISTS (
               SELECT 1
                 FROM public.vat_tu_txn
                WHERE clinic_id = OLD.clinic_id
                  AND vat_tu_id = OLD.id
           ) OR EXISTS (
               SELECT 1
                 FROM public.vat_tu_nhap_cho_duyet y
                 CROSS JOIN LATERAL jsonb_array_elements(y.dong) AS item(elem)
                WHERE y.clinic_id = OLD.clinic_id
                  AND y.trang_thai = 'CHO_DUYET'
                  AND item.elem->>'vat_tu_id' = OLD.id::text
           )
       ) THEN
        RAISE EXCEPTION
            'Vật tư đã có giao dịch kho hoặc phiếu nhập chờ duyệt nên không thể đổi đơn vị; hãy tạo mặt hàng mới'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS vat_tu_don_vi_bat_bien ON public.service_price;
CREATE TRIGGER vat_tu_don_vi_bat_bien
    BEFORE UPDATE OF don_vi ON public.service_price
    FOR EACH ROW
    EXECUTE FUNCTION public.vat_tu_chan_doi_don_vi_co_giao_dich();

-- Ghi sổ / gửi yêu cầu nhập phải khóa hàng cha trước. FOR SHARE xung đột với
-- UPDATE đơn vị, nên một trong hai phía sẽ thấy kết quả đã commit của phía kia.
CREATE OR REPLACE FUNCTION public.vat_tu_txn_khoa_don_vi()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    nhom text;
BEGIN
    SELECT "group" INTO nhom
      FROM public.service_price
     WHERE clinic_id = NEW.clinic_id AND id = NEW.vat_tu_id
     FOR SHARE;
    IF nhom IS DISTINCT FROM 'vat_tu' THEN
        RAISE EXCEPTION 'Mặt hàng không phải vật tư của cơ sở này'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS a_vat_tu_txn_khoa_don_vi ON public.vat_tu_txn;
CREATE TRIGGER a_vat_tu_txn_khoa_don_vi
    BEFORE INSERT ON public.vat_tu_txn
    FOR EACH ROW
    EXECUTE FUNCTION public.vat_tu_txn_khoa_don_vi();

CREATE OR REPLACE FUNCTION public.vat_tu_nhap_cho_duyet_khoa_don_vi()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    dong jsonb;
    don_vi_hien_tai text;
    vat_tu_id uuid;
BEGIN
    FOR dong IN
        SELECT e.value
          FROM jsonb_array_elements(NEW.dong) AS e(value)
         ORDER BY (e.value->>'vat_tu_id')::uuid
    LOOP
        IF NOT (dong ? 'don_vi') THEN
            RAISE EXCEPTION 'Thiếu đơn vị vật tư trong yêu cầu nhập'
                USING ERRCODE = 'check_violation';
        END IF;
        vat_tu_id := (dong->>'vat_tu_id')::uuid;
        SELECT don_vi INTO don_vi_hien_tai
          FROM public.service_price
         WHERE clinic_id = NEW.clinic_id
           AND id = vat_tu_id
           AND "group" = 'vat_tu'
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Mặt hàng không phải vật tư của cơ sở này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF dong->>'don_vi' IS DISTINCT FROM don_vi_hien_tai THEN
            RAISE EXCEPTION 'Đơn vị vật tư đã thay đổi; tải lại danh mục rồi gửi lại'
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS a_vat_tu_nhap_cho_duyet_khoa_don_vi
    ON public.vat_tu_nhap_cho_duyet;
CREATE TRIGGER a_vat_tu_nhap_cho_duyet_khoa_don_vi
    BEFORE INSERT ON public.vat_tu_nhap_cho_duyet
    FOR EACH ROW
    EXECUTE FUNCTION public.vat_tu_nhap_cho_duyet_khoa_don_vi();

COMMIT;
