-- G8b — PHIẾU NHẬP VẬT TƯ CHỜ DUYỆT (Tuyền chốt 14/10/2026, Q11 + 2e: "phiếu nhập
-- chờ duyệt"; cờ từng mặt hàng `can_duyet_nhap_vat_tu` do Quản lý đặt ở danh mục).
--
-- Sổ vật tư (`vat_tu_phieu` / `vat_tu_txn`, G8a) chỉ-thêm và phiếu lập trong MỘT giao
-- dịch — nên "chờ duyệt" KHÔNG nằm trong sổ: phiếu NHẬP có dòng cần duyệt thành một
-- YÊU CẦU ở bảng riêng này (nội dung bất biến); người có lego Duyệt vật tư
-- (`vat_tu.approve`) duyệt thì hệ thống lập phiếu NHẬP thật đúng số đã xin, từ chối
-- (bắt lý do) hoặc rút lại thì không có gì vào sổ. Yêu cầu chỉ quyết MỘT lần; hoàn
-- tác một lần nhập đã duyệt = phiếu đảo như mọi phiếu.
--
-- Chạy lại được, không BEGIN/COMMIT.

CREATE TABLE IF NOT EXISTS public.vat_tu_nhap_cho_duyet (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id    uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id  uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    ma_yeu_cau   text NOT NULL,
    khoa_gui     text NOT NULL CHECK (length(btrim(khoa_gui)) BETWEEN 1 AND 200),
    -- [{vat_tu_id, den_room_id, so_luong, gia_nhap}] — đã chuẩn hoá, giá nhập là
    -- bản chụp LÚC XIN (đổi danh mục sau không đổi lịch sử).
    dong         jsonb NOT NULL
                 CHECK (jsonb_typeof(dong) = 'array'
                        AND jsonb_array_length(dong) BETWEEN 1 AND 200),
    ghi_chu      text,
    tao_boi      uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    tao_luc      timestamptz NOT NULL DEFAULT now(),
    trang_thai   text NOT NULL DEFAULT 'CHO_DUYET'
                 CHECK (trang_thai IN ('CHO_DUYET', 'DA_DUYET', 'TU_CHOI', 'RUT_LAI')),
    quyet_boi    uuid REFERENCES public.staff(id) ON DELETE RESTRICT,
    quyet_luc    timestamptz,
    quyet_ly_do  text CHECK (quyet_ly_do IS NULL
                             OR char_length(btrim(quyet_ly_do)) BETWEEN 5 AND 500),
    phieu_id     uuid REFERENCES public.vat_tu_phieu(id) ON DELETE RESTRICT,
    CONSTRAINT vat_tu_nhap_cho_duyet_khoa UNIQUE (clinic_id, location_id, khoa_gui),
    CONSTRAINT vat_tu_nhap_cho_duyet_ma UNIQUE (clinic_id, ma_yeu_cau),
    -- Đã quyết ⇔ có người + giờ quyết; đã duyệt ⇔ có phiếu; từ chối phải có lý do.
    CONSTRAINT vat_tu_nhap_cho_duyet_quyet
        CHECK ((trang_thai = 'CHO_DUYET') = (quyet_boi IS NULL AND quyet_luc IS NULL)),
    CONSTRAINT vat_tu_nhap_cho_duyet_phieu
        CHECK ((trang_thai = 'DA_DUYET') = (phieu_id IS NOT NULL)),
    CONSTRAINT vat_tu_nhap_cho_duyet_tu_choi
        CHECK (trang_thai <> 'TU_CHOI' OR quyet_ly_do IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS vat_tu_nhap_cho_duyet_theo_co_so
    ON public.vat_tu_nhap_cho_duyet (clinic_id, location_id, trang_thai, tao_luc DESC);
COMMENT ON TABLE public.vat_tu_nhap_cho_duyet IS
'Yêu cầu nhập vật tư thuộc loại cần duyệt nhập, chờ người có lego Duyệt vật tư (G8b, 14/10/2026). KHÔNG nằm trong sổ vật tư: duyệt thì lập phiếu NHAP thật (phieu_id).';

-- Lưới cuối: nội dung bất biến, chỉ quyết một lần, người quyết phải CÓ lego.
CREATE OR REPLACE FUNCTION public.vat_tu_nhap_cho_duyet_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    co_lego boolean;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Không xoá yêu cầu nhập vật tư — rút lại hoặc từ chối'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.trang_thai <> 'CHO_DUYET' THEN
            RAISE EXCEPTION 'Yêu cầu nhập vật tư mới phải ở trạng thái chờ duyệt'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.clinic_location
                        WHERE id = NEW.location_id AND clinic_id = NEW.clinic_id)
           OR NOT EXISTS (SELECT 1 FROM public.clinic_membership
                           WHERE clinic_id = NEW.clinic_id AND staff_id = NEW.tao_boi
                             AND is_active) THEN
            RAISE EXCEPTION 'Yêu cầu nhập vật tư sai cơ sở / người lập'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- UPDATE
    IF OLD.trang_thai <> 'CHO_DUYET' THEN
        RAISE EXCEPTION 'Yêu cầu nhập vật tư đã quyết — không sửa nữa'
            USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.clinic_id, NEW.location_id, NEW.ma_yeu_cau, NEW.khoa_gui, NEW.dong,
        NEW.ghi_chu, NEW.tao_boi, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.clinic_id, OLD.location_id, OLD.ma_yeu_cau, OLD.khoa_gui, OLD.dong,
        OLD.ghi_chu, OLD.tao_boi, OLD.tao_luc) THEN
        RAISE EXCEPTION 'Không sửa nội dung yêu cầu nhập vật tư đã gửi'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.trang_thai = 'CHO_DUYET' THEN
        RAISE EXCEPTION 'Yêu cầu đang chờ — phải duyệt, từ chối hoặc rút lại'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM public.v_quyen_thuc_te q
          JOIN public.clinic_membership m
            ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id AND m.is_active
         WHERE q.clinic_id = NEW.clinic_id AND q.staff_id = NEW.quyet_boi
           AND q.capability = 'vat_tu.approve' AND q.scope_type = 'CLINIC')
      INTO co_lego;
    -- Duyệt / từ chối: CHỈ người có lego. Rút lại: chính người lập hoặc người có lego.
    IF NEW.trang_thai IN ('DA_DUYET', 'TU_CHOI') AND NOT co_lego THEN
        RAISE EXCEPTION 'Chỉ người có quyền Duyệt vật tư mới duyệt / từ chối được'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.trang_thai = 'RUT_LAI' AND NEW.quyet_boi <> OLD.tao_boi AND NOT co_lego THEN
        RAISE EXCEPTION 'Chỉ người lập hoặc người có quyền Duyệt vật tư mới rút lại được'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS vat_tu_nhap_cho_duyet_gac ON public.vat_tu_nhap_cho_duyet;
CREATE TRIGGER vat_tu_nhap_cho_duyet_gac
    BEFORE INSERT OR UPDATE OR DELETE ON public.vat_tu_nhap_cho_duyet
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_nhap_cho_duyet_gac();

-- RLS đọc theo phòng khám · backend ghi · báo màn đang mở (LISTEN/NOTIFY).
ALTER TABLE public.vat_tu_nhap_cho_duyet ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vat_tu_nhap_cho_duyet_select_own_clinic
    ON public.vat_tu_nhap_cho_duyet;
CREATE POLICY vat_tu_nhap_cho_duyet_select_own_clinic ON public.vat_tu_nhap_cho_duyet
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.vat_tu_nhap_cho_duyet TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.vat_tu_nhap_cho_duyet TO service_role;
DROP TRIGGER IF EXISTS trg_notify_vat_tu_nhap_cho_duyet ON public.vat_tu_nhap_cho_duyet;
CREATE TRIGGER trg_notify_vat_tu_nhap_cho_duyet
    AFTER INSERT OR UPDATE OR DELETE ON public.vat_tu_nhap_cho_duyet
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
NOTIFY pgrst, 'reload schema';
