-- XÉT NGHIỆM ĐỐI TÁC — CHẶNG 1: NỀN (kế hoạch docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md
-- mục 4.1–4.3, ADR-0015). Module sở hữu: `xet_nghiem_doi_tac`.
--
-- 1. `doi_tac` — phòng xét nghiệm ngoài. Không xoá: ngưng (có lý do), bật lại được.
-- 2. `doi_tac_dich_vu` — đối tác nào làm dịch vụ nào, giá gợi ý + hẹn trả. Một nơi
--    duy nhất đặt hẹn trả (NULL ⇒ mặc định của đối tác). Mỗi dịch vụ tối đa MỘT
--    dòng mặc định còn hoạt động (chỉ mục duy nhất có điều kiện).
-- 3. `xet_nghiem_viec` — CHỤP lúc chỉ định (1–1 với service_order): việc này đi
--    đối tác nào, giá gợi ý lúc đó. Đổi ánh xạ sau này KHÔNG đổi việc cũ. Bảng riêng,
--    không thêm cột vào service_order (bảng của module lượt khám).
--    Chỉ tạo cho chỉ định TỪ KHI migration này lên (5b: 420 việc cũ ở lại bàn cũ,
--    không bù, không đoán).
-- 4. `xet_nghiem_cai_dat` — một dòng/phòng khám: ngưỡng "đã thu, chưa lấy mẫu"
--    (câu F, mặc định 2 ngày).
-- 5. Báo tin SSE cho cả bốn bảng.
--
-- Chạy lại được.

-- ── 1. Đối tác ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.doi_tac (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id                 uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    ten                       text NOT NULL,
    ma_ngan                   text NOT NULL,
    sdt                       text,
    ghi_chu                   text,
    drive_folder_id           text,
    hen_tra_so_ngay_mac_dinh  integer,
    tao_luc                   timestamptz NOT NULL DEFAULT now(),
    tao_boi                   uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    sua_luc                   timestamptz NOT NULL DEFAULT now(),
    sua_boi                   uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ngung_luc                 timestamptz,
    ngung_boi                 uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ly_do_ngung               text,
    CONSTRAINT doi_tac_id_clinic UNIQUE (id, clinic_id),
    CONSTRAINT doi_tac_chu_hop_le CHECK (
        length(btrim(ten)) BETWEEN 1 AND 120
        AND ma_ngan ~ '^[A-Za-z0-9]{2,10}$'
        AND (sdt IS NULL OR length(sdt) <= 30)
        AND (ghi_chu IS NULL OR length(ghi_chu) <= 2000)
        AND (drive_folder_id IS NULL OR drive_folder_id ~ '^[A-Za-z0-9_-]{10,200}$')),
    CONSTRAINT doi_tac_hen_tra_hop_le CHECK (
        hen_tra_so_ngay_mac_dinh IS NULL OR hen_tra_so_ngay_mac_dinh BETWEEN 0 AND 90),
    CONSTRAINT doi_tac_ngung_co_dau_vet CHECK (
        (ngung_luc IS NULL AND ngung_boi IS NULL AND ly_do_ngung IS NULL)
        OR (ngung_luc IS NOT NULL AND ngung_boi IS NOT NULL
            AND length(btrim(ly_do_ngung)) BETWEEN 3 AND 2000))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_ma_ngan
    ON public.doi_tac (clinic_id, lower(ma_ngan));

COMMENT ON TABLE public.doi_tac IS
'Đối tác xét nghiệm (05/11/2026, ADR-0015). Không xoá: ngưng có lý do. Đơn cũ giữ doi_tac_id; đổi tên không đổi đơn.';

-- ── 2. Ánh xạ đối tác ↔ dịch vụ ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.doi_tac_dich_vu (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL,
    doi_tac_id        uuid NOT NULL,
    service_price_id  uuid NOT NULL,
    gia_goi_y         numeric(12, 0) CHECK (gia_goi_y IS NULL OR gia_goi_y >= 0),
    hen_tra_so_ngay   integer CHECK (hen_tra_so_ngay IS NULL OR hen_tra_so_ngay BETWEEN 0 AND 90),
    mac_dinh          boolean NOT NULL DEFAULT true,
    tao_luc           timestamptz NOT NULL DEFAULT now(),
    tao_boi           uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    sua_luc           timestamptz NOT NULL DEFAULT now(),
    sua_boi           uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ngung_luc         timestamptz,
    ngung_boi         uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    CONSTRAINT doi_tac_dich_vu_doi_tac_fk FOREIGN KEY (doi_tac_id, clinic_id)
        REFERENCES public.doi_tac (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT doi_tac_dich_vu_gia_fk FOREIGN KEY (clinic_id, service_price_id)
        REFERENCES public.service_price (clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT doi_tac_dich_vu_ngung_dau_vet CHECK (
        (ngung_luc IS NULL) = (ngung_boi IS NULL)),
    CONSTRAINT doi_tac_dich_vu_mac_dinh_con_dung CHECK (NOT mac_dinh OR ngung_luc IS NULL)
);
-- Một cặp (đối tác, dịch vụ) còn hoạt động chỉ một dòng.
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_dich_vu_cap
    ON public.doi_tac_dich_vu (clinic_id, doi_tac_id, service_price_id)
    WHERE ngung_luc IS NULL;
-- Mỗi dịch vụ tối đa MỘT đối tác mặc định (hai người lưu cùng lúc: một người thua).
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_dich_vu_mot_mac_dinh
    ON public.doi_tac_dich_vu (clinic_id, service_price_id)
    WHERE mac_dinh;

COMMENT ON TABLE public.doi_tac_dich_vu IS
'Đối tác làm dịch vụ nào (05/11/2026). Một nơi đặt hẹn trả + giá gợi ý. Mỗi dịch vụ một mặc định còn hoạt động.';

-- ── 3. Chụp lúc chỉ định ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.xet_nghiem_viec (
    service_order_id          uuid PRIMARY KEY
                              REFERENCES public.service_order (id) ON DELETE RESTRICT,
    clinic_id                 uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    doi_tac_id                uuid NOT NULL,
    gia_goi_y_luc_chi_dinh    numeric(12, 0) CHECK (
                                  gia_goi_y_luc_chi_dinh IS NULL OR gia_goi_y_luc_chi_dinh >= 0),
    tao_luc                   timestamptz NOT NULL DEFAULT now(),
    -- Quản lý cho lấy mẫu khi chưa ghi nhận thu (câu 2) — đặt một lần, có lý do.
    cho_lay_mau_truoc_luc     timestamptz,
    cho_lay_mau_truoc_boi     uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    cho_lay_mau_truoc_ly_do   text,
    CONSTRAINT xet_nghiem_viec_doi_tac_fk FOREIGN KEY (doi_tac_id, clinic_id)
        REFERENCES public.doi_tac (id, clinic_id) ON DELETE RESTRICT,
    -- Cho chặng 3: FK ghép (việc, đối tác) từ mau_xet_nghiem_viec ép "một ống một đối tác".
    CONSTRAINT xet_nghiem_viec_viec_doi_tac UNIQUE (service_order_id, doi_tac_id),
    CONSTRAINT xet_nghiem_viec_cho_qua_dau_vet CHECK (
        (cho_lay_mau_truoc_luc IS NULL AND cho_lay_mau_truoc_boi IS NULL
            AND cho_lay_mau_truoc_ly_do IS NULL)
        OR (cho_lay_mau_truoc_luc IS NOT NULL AND cho_lay_mau_truoc_boi IS NOT NULL
            AND length(btrim(cho_lay_mau_truoc_ly_do)) BETWEEN 3 AND 2000))
);
CREATE INDEX IF NOT EXISTS ix_xet_nghiem_viec_doi_tac
    ON public.xet_nghiem_viec (clinic_id, doi_tac_id, tao_luc DESC);

COMMENT ON TABLE public.xet_nghiem_viec IS
'Chụp lúc chỉ định việc đối tác (05/11/2026). Có dòng ở đây = việc đối tác của luồng mới. Đổi ánh xạ không đổi dòng cũ.';

-- Chụp không sửa được; chỉ được đặt "cho qua" đúng một lần. Không xoá.
CREATE OR REPLACE FUNCTION public.xet_nghiem_viec_chi_cho_qua()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'xet_nghiem_viec: không xoá'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.service_order_id, NEW.clinic_id, NEW.doi_tac_id,
        NEW.gia_goi_y_luc_chi_dinh, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.service_order_id, OLD.clinic_id, OLD.doi_tac_id,
        OLD.gia_goi_y_luc_chi_dinh, OLD.tao_luc)
       OR (OLD.cho_lay_mau_truoc_luc IS NOT NULL
           AND (NEW.cho_lay_mau_truoc_luc, NEW.cho_lay_mau_truoc_boi,
                NEW.cho_lay_mau_truoc_ly_do)
               IS DISTINCT FROM
               (OLD.cho_lay_mau_truoc_luc, OLD.cho_lay_mau_truoc_boi,
                OLD.cho_lay_mau_truoc_ly_do)) THEN
        RAISE EXCEPTION 'xet_nghiem_viec: bản chụp không sửa được'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_xet_nghiem_viec_chi_cho_qua ON public.xet_nghiem_viec;
CREATE TRIGGER trg_xet_nghiem_viec_chi_cho_qua
    BEFORE UPDATE OR DELETE ON public.xet_nghiem_viec
    FOR EACH ROW EXECUTE FUNCTION public.xet_nghiem_viec_chi_cho_qua();

-- Đối tác + ánh xạ: không xoá (ngưng thay xoá — việc cũ còn trỏ vào).
CREATE OR REPLACE FUNCTION public.xet_nghiem_khong_xoa()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '%: không xoá — ngưng thay vì xoá', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_doi_tac_khong_xoa ON public.doi_tac;
CREATE TRIGGER trg_doi_tac_khong_xoa BEFORE DELETE ON public.doi_tac
    FOR EACH ROW EXECUTE FUNCTION public.xet_nghiem_khong_xoa();
DROP TRIGGER IF EXISTS trg_doi_tac_dich_vu_khong_xoa ON public.doi_tac_dich_vu;
CREATE TRIGGER trg_doi_tac_dich_vu_khong_xoa BEFORE DELETE ON public.doi_tac_dich_vu
    FOR EACH ROW EXECUTE FUNCTION public.xet_nghiem_khong_xoa();

-- ── 4. Cài đặt theo phòng khám ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.xet_nghiem_cai_dat (
    clinic_id            uuid PRIMARY KEY REFERENCES public.clinic (id) ON DELETE RESTRICT,
    nguong_lay_mau_ngay  integer NOT NULL DEFAULT 2
                         CHECK (nguong_lay_mau_ngay BETWEEN 1 AND 30),
    sua_luc              timestamptz NOT NULL DEFAULT now(),
    sua_boi              uuid REFERENCES public.staff (id) ON DELETE RESTRICT
);
COMMENT ON TABLE public.xet_nghiem_cai_dat IS
'Cài đặt bàn xét nghiệm theo phòng khám (câu F 05/11: "đã thu, chưa lấy mẫu" quá N ngày thì vàng). Không có dòng = mặc định 2.';

-- ── Quyền đọc + RLS ─────────────────────────────────────────────────────────
DO $$
DECLARE b text;
BEGIN
    FOREACH b IN ARRAY ARRAY['doi_tac', 'doi_tac_dich_vu', 'xet_nghiem_viec',
                             'xet_nghiem_cai_dat'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', b);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', b || '_select_own_clinic', b);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO service_role '
            'USING (clinic_id IN (SELECT current_clinic_ids()))',
            b || '_select_own_clinic', b);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON public.%I TO service_role', b);
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', 'trg_notify_' || b, b);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.notify_row_change()',
            'trg_notify_' || b, b);
    END LOOP;
END $$;
