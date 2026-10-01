-- BÁN THÊM VẬT TƯ Ở QUẦY THU DỊCH VỤ (Tuyền 01/10/2026, việc C13).
--
-- Tuyền: "Ở quầy thu dịch vụ có thể tick / thêm 'Mua thêm vật tư' vào hoá đơn
-- của khách" — trước hết hai đầu dò Bio (1 lần 300.000đ, nhiều lần 900.000đ)
-- chọn nhanh bằng một cú bấm; hàng khác tìm theo tên. Nguồn danh mục: file
-- "[Dr4women] Danh sách vật tư 01.10.2026 (Hà Nguyễn gửi).xlsx" (KiotViet, 84
-- dòng, nhóm "Nguyên liệu tiêu hao"). Ghi chú ở cuối file:
--   1. "Giá bán = 0 → không được phép bán".
--   2. "Vòng nội tiết Mirena (4.000.000đ): thông thường không bán (đã nằm trong
--      giá dịch vụ đặt vòng); khi sự cố cần vòng thứ 2 thì nhân sự báo QL xin
--      duyệt bán".
--
-- THIẾT KẾ
--   * Danh mục = `service_price` nhóm MỚI "vat_tu" (không phòng, không nhóm việc,
--     không phải phí khám) — cùng Bảng giá của quản lý: sửa giá / bật tắt ở đó.
--     Giá 0 trong Excel nạp thành NULL = "chưa có giá — không bán" (không bao giờ
--     nạp 0đ — thu 0 đồng là sai).
--   * Dòng bán cho MỘT khách: `luot_vat_tu` (theo lượt, KHÔNG gắn chỉ định) —
--     tên / đơn vị / đơn giá chốt lúc thêm, số lượng 1..99, bỏ = đóng dấu.
--   * Tiền vào hoá đơn DỊCH VỤ (dòng `vat_tu` của `payment_bill_line`) — KHÔNG
--     phải tiền thuốc: thu ở quầy Thu tiền dịch vụ, tách thuốc / dịch vụ như
--     20261002800000.
--   * Hàng cần quản lý duyệt (Mirena): cột `can_ql_duyet`. Postgres ép: dòng bán
--     hàng ấy phải có người DUYỆT (một quản lý đang làm việc) + lý do.
--   * Hàng chọn nhanh (`chon_nhanh`) và dịch vụ gợi ý nó (`vat_tu_goi_y`): lượt
--     có "Tập máy Bio…" thì hai đầu dò nổi lên đầu.
--
-- Chạy lại được (hàm `dong_bo_vat_tu`, khoá theo tên + đơn vị, KHÔNG đè giá
-- quản lý đã sửa trừ khi gọi với p_ghi_de_gia = true).

-- ── 1. service_price: nhóm vat_tu + 3 cột ───────────────────────────────────
ALTER TABLE public.service_price DROP CONSTRAINT IF EXISTS service_price_group_check;
ALTER TABLE public.service_price ADD CONSTRAINT service_price_group_check
    CHECK ("group" = ANY (ARRAY['thuoc'::text, 'dich_vu'::text, 'vat_tu'::text]));

ALTER TABLE public.service_price ADD COLUMN IF NOT EXISTS don_vi text;
ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS can_ql_duyet boolean NOT NULL DEFAULT false;
ALTER TABLE public.service_price
    ADD COLUMN IF NOT EXISTS chon_nhanh boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.service_price.don_vi IS
'Đơn vị tính (cái, hộp…) — hiện cho vật tư (nhóm vat_tu), 01/10/2026.';
COMMENT ON COLUMN public.service_price.can_ql_duyet IS
'Vật tư KHÔNG bán thông thường: mỗi dòng bán phải có quản lý duyệt + lý do (vd vòng Mirena thứ 2). 01/10/2026.';
COMMENT ON COLUMN public.service_price.chon_nhanh IS
'Vật tư hiện thành nút chọn nhanh ở quầy thu dịch vụ (đầu dò Bio). 01/10/2026.';

-- ── 2. Dịch vụ gợi ý vật tư ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.vat_tu_goi_y (
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    dich_vu_id       uuid NOT NULL REFERENCES public.service_price(id) ON DELETE CASCADE,
    vat_tu_id        uuid NOT NULL REFERENCES public.service_price(id) ON DELETE CASCADE,
    PRIMARY KEY (dich_vu_id, vat_tu_id)
);
COMMENT ON TABLE public.vat_tu_goi_y IS
'Dịch vụ nào thường mua kèm vật tư nào (Tập máy Bio → đầu dò) — quầy thu cho vật tư ấy nổi lên đầu khi lượt có dịch vụ. 01/10/2026.';
ALTER TABLE public.vat_tu_goi_y ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vat_tu_goi_y_select_own_clinic ON public.vat_tu_goi_y;
CREATE POLICY vat_tu_goi_y_select_own_clinic ON public.vat_tu_goi_y
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.vat_tu_goi_y TO service_role;

-- ── 3. Dòng vật tư bán cho một lượt ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.luot_vat_tu (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    visit_id         uuid NOT NULL,
    service_price_id uuid NOT NULL REFERENCES public.service_price(id)
                         ON DELETE RESTRICT,
    ten              text NOT NULL,
    don_vi           text,
    don_gia          numeric(12, 0) NOT NULL CHECK (don_gia > 0),
    so_luong         integer NOT NULL CHECK (so_luong BETWEEN 1 AND 99),
    chon_boi         uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    chon_luc         timestamptz NOT NULL DEFAULT now(),
    -- Quản lý duyệt (hàng can_ql_duyet) + lý do — luôn đi cùng nhau.
    duyet_boi        uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    duyet_ly_do      text CHECK (duyet_ly_do IS NULL
                                 OR char_length(btrim(duyet_ly_do)) BETWEEN 5 AND 500),
    bo_boi           uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    bo_luc           timestamptz,
    CONSTRAINT luot_vat_tu_duyet_di_cung CHECK ((duyet_boi IS NULL) = (duyet_ly_do IS NULL))
);
-- Một mặt hàng một dòng sống mỗi lượt (bấm thêm lần nữa = cộng số lượng).
CREATE UNIQUE INDEX IF NOT EXISTS luot_vat_tu_mot_dong_song
    ON public.luot_vat_tu (clinic_id, visit_id, service_price_id)
    WHERE bo_luc IS NULL;
CREATE INDEX IF NOT EXISTS luot_vat_tu_theo_luot
    ON public.luot_vat_tu (clinic_id, visit_id);
COMMENT ON TABLE public.luot_vat_tu IS
'Vật tư khách mua thêm ở quầy thu dịch vụ (01/10/2026). Tiền vào hoá đơn DỊCH VỤ (payment_bill_line.source_type = vat_tu). Bỏ = đóng dấu bo_luc, không xoá.';

ALTER TABLE public.luot_vat_tu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS luot_vat_tu_select_own_clinic ON public.luot_vat_tu;
CREATE POLICY luot_vat_tu_select_own_clinic ON public.luot_vat_tu
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.luot_vat_tu TO service_role;

-- Tin thay đổi cho màn đang mở (SSE: LISTEN/NOTIFY → /api/events/stream).
DROP TRIGGER IF EXISTS trg_notify_luot_vat_tu ON public.luot_vat_tu;
CREATE TRIGGER trg_notify_luot_vat_tu
    AFTER INSERT OR UPDATE OR DELETE ON public.luot_vat_tu
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- Lưới cuối (SO-LUAT Phần 6) — ép ở Postgres, không chỉ ở Python:
--   * hàng `can_ql_duyet` phải có người duyệt là QUẢN LÝ đang làm việc;
--   * hàng phải là vật tư (nhóm vat_tu) đang bán, có giá > 0 lúc thêm;
--   * dòng đã nằm trong lần thu (chờ xác minh / đã thu) thì KHÔNG đổi số lượng,
--     giá, và không bỏ — đổi phải hoàn tác lần thu trước.
CREATE OR REPLACE FUNCTION public.luot_vat_tu_gac()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    sp record;
    trung uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT s."group", s.active, s.unit_price, s.can_ql_duyet, s.clinic_id
          INTO sp FROM public.service_price s WHERE s.id = NEW.service_price_id;
        IF NOT FOUND OR sp."group" <> 'vat_tu' OR sp.clinic_id <> NEW.clinic_id THEN
            RAISE EXCEPTION 'luot_vat_tu: không phải vật tư của phòng khám này'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT sp.active OR coalesce(sp.unit_price, 0) <= 0 THEN
            RAISE EXCEPTION 'luot_vat_tu: vật tư chưa có giá hoặc đã ngưng bán — không bán được'
                USING ERRCODE = 'check_violation';
        END IF;
        IF sp.can_ql_duyet AND NOT EXISTS (
               SELECT 1 FROM public.clinic_membership m
                WHERE m.clinic_id = NEW.clinic_id AND m.staff_id = NEW.duyet_boi
                  AND m.role = 'MANAGEMENT' AND m.is_active) THEN
            RAISE EXCEPTION 'luot_vat_tu: hàng này cần quản lý duyệt bán (kèm lý do)'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- UPDATE: đổi số lượng / giá / bỏ khi đã nằm trong lần thu.
    IF NEW.so_luong IS DISTINCT FROM OLD.so_luong
       OR NEW.don_gia IS DISTINCT FROM OLD.don_gia
       OR (NEW.bo_luc IS NOT NULL AND OLD.bo_luc IS NULL) THEN
        SELECT bl.payment_cycle_id INTO trung
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = OLD.clinic_id
           AND bl.source_type = 'vat_tu' AND bl.source_id = OLD.id::text
           AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PENDING_VERIFICATION', 'PAID')
         LIMIT 1;
        IF trung IS NOT NULL THEN
            RAISE EXCEPTION
                'luot_vat_tu: dòng đã nằm trong lần thu % — hoàn tác lần thu trước khi đổi', trung
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_luot_vat_tu_gac ON public.luot_vat_tu;
CREATE TRIGGER trg_luot_vat_tu_gac
    BEFORE INSERT OR UPDATE ON public.luot_vat_tu
    FOR EACH ROW EXECUTE FUNCTION public.luot_vat_tu_gac();

-- ── 4. Hoá đơn: loại dòng mới `vat_tu` ──────────────────────────────────────
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_source_type_check;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_source_type_check
    CHECK (source_type = ANY (ARRAY['exam', 'service_order', 'prescription',
                                    'phu_thu', 'vat_tu']));

-- Cùng chốt "không thu hai lần" với tiền khám / chỉ định / phụ thu (chép
-- 20260928000099, thêm 'vat_tu').
CREATE OR REPLACE FUNCTION public.payment_bill_line_mot_lan_phu()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    trung uuid;
BEGIN
    IF NEW.billing_owner <> 'CLINIC'
       OR NEW.source_type NOT IN ('service_order', 'exam', 'phu_thu', 'vat_tu') THEN
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'payment_bill_line_phu|' || NEW.clinic_id::text || '|' || NEW.source_type
        || '|' || NEW.source_id, 0));
    SELECT bl.payment_cycle_id INTO trung
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
     WHERE bl.clinic_id = NEW.clinic_id
       AND bl.source_type = NEW.source_type
       AND bl.source_id = NEW.source_id
       AND bl.billing_owner = 'CLINIC'
       AND c.status IN ('PENDING_VERIFICATION', 'PAID')
     LIMIT 1;
    IF trung IS NOT NULL THEN
        RAISE EXCEPTION
            'payment_bill_line: % % đã nằm trong lần thu % — không thu hai lần',
            NEW.source_type, NEW.source_id, trung
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'payment_bill_line_mot_lan_phu';
    END IF;
    RETURN NEW;
END $$;

-- Thuốc ⇔ prescription; dịch vụ ⇔ khám / chỉ định / phụ thu / VẬT TƯ (vật tư là
-- tiền DỊCH VỤ, thu ở quầy dịch vụ — không thu ở quầy thuốc).
ALTER TABLE public.payment_bill_line
    DROP CONSTRAINT IF EXISTS payment_bill_line_kind_khop_nguon;
ALTER TABLE public.payment_bill_line
    ADD CONSTRAINT payment_bill_line_kind_khop_nguon
    CHECK (
        (kind = 'thuoc' AND source_type = 'prescription')
        OR (kind = 'dich_vu'
            AND source_type IN ('exam', 'service_order', 'phu_thu', 'vat_tu'))
    ) NOT VALID;
COMMENT ON CONSTRAINT payment_bill_line_kind_khop_nguon
    ON public.payment_bill_line IS
    'Tiền thuốc và tiền dịch vụ thu riêng hẳn (01/10/2026): dòng thuốc chỉ nằm trong lần thu thuốc; dòng khám / chỉ định / phụ thu / vật tư chỉ nằm trong lần thu dịch vụ. NOT VALID — canh dòng ghi mới, không đụng lịch sử.';

-- ── 5. Nạp danh mục vật tư (84 dòng Excel 01/10) ────────────────────────────
CREATE OR REPLACE FUNCTION public.dong_bo_vat_tu(p_ghi_de_gia boolean DEFAULT false)
RETURNS TABLE (them integer, sua integer, goi_y integer)
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    n_them integer := 0;
    n_sua integer := 0;
    n_goi integer := 0;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS _vat_tu_nguon (
        thu_tu integer, ten text, gia numeric, don_vi text, ma text,
        ma_kiotviet text, chon_nhanh boolean, can_ql_duyet boolean
    ) ON COMMIT DROP;
    DELETE FROM _vat_tu_nguon;
    INSERT INTO _vat_tu_nguon VALUES
        (1, 'KIm gây tê tủy sống (PRP)', 0, NULL, NULL, NULL, false, false),
        (2, 'KIm luồn PRP (cái)', 0, NULL, NULL, NULL, false, false),
        (3, 'Chỉ khâu Bylon/Ethicon (sợi)', 0, NULL, NULL, NULL, false, false),
        (4, 'Dao mổ (cái)', 0, NULL, NULL, NULL, false, false),
        (5, 'Giấy in nhiệt siêu âm SONY ( cuộn)', 0, NULL, NULL, NULL, false, false),
        (6, 'Lugol (lọ)', 0, NULL, NULL, NULL, false, false),
        (7, 'Bông tẩm cồn ( hộp)', 0, NULL, NULL, NULL, false, false),
        (8, 'Gạc ổ bụng', 0, NULL, NULL, NULL, false, false),
        (9, 'Thùng giấy đóng thuốc (cái)', 0, NULL, NULL, NULL, false, false),
        (10, 'Bút lông dầu ( cái )', 0, NULL, NULL, NULL, false, false),
        (11, 'Bút bi (cái)', 0, NULL, NULL, NULL, false, false),
        (12, 'Săng Nilon (cái)', 0, NULL, NULL, NULL, false, false),
        (13, 'Gạc vuông', 0, NULL, NULL, NULL, false, false),
        (14, 'Presept ( hộp)', 0, NULL, NULL, NULL, false, false),
        (15, 'PVD 10% - 500ml (chai)', 0, NULL, NULL, NULL, false, false),
        (16, 'Cồn 70 độ ( chai )', 0, NULL, NULL, NULL, false, false),
        (17, 'Bọc camera (cái)', 0, NULL, NULL, NULL, false, false),
        (18, 'Giấy in hóa đơn ( cuộn)', 0, NULL, NULL, NULL, false, false),
        (19, 'Túi đựng thuốc ( kg)', 0, NULL, NULL, NULL, false, false),
        (20, 'Giấy A5 (Ram)', 0, NULL, NULL, NULL, false, false),
        (21, 'Giấy A4 màu (Ram)', 0, NULL, NULL, NULL, false, false),
        (22, 'Giấy A4 trắng (Ram)', 0, NULL, NULL, NULL, false, false),
        (23, 'Giấy in Monitor ( tệp )', 0, NULL, NULL, NULL, false, false),
        (24, 'Túi rác vàng ( kg)', 0, NULL, NULL, NULL, false, false),
        (25, 'Túi rác xanh ( Kg)', 0, NULL, NULL, NULL, false, false),
        (26, 'Sáp thơm ( cái )', 0, NULL, NULL, NULL, false, false),
        (27, 'Khăn giấy đa năng Pulppy 2 lớp (cuộn)', 0, NULL, NULL, NULL, false, false),
        (28, 'Giấy vệ sinh cuộn to 700gr', 0, NULL, NULL, NULL, false, false),
        (29, 'Giấy vệ sinh ( cuộn nhỏ )', 0, NULL, NULL, NULL, false, false),
        (30, 'Giấy ướt ( Gói )', 0, NULL, NULL, NULL, false, false),
        (31, 'Gel siêu âm (can)', 0, NULL, NULL, NULL, false, false),
        (32, 'Nước rửa tay Lifeboy ( chai/gói )', 0, NULL, NULL, NULL, false, false),
        (33, 'Dung dịch ngâm dụng cụ (can)', 0, NULL, NULL, NULL, false, false),
        (34, 'Cốc nhựa đựng nước tiểu ( dây x 50c)', 0, NULL, NULL, NULL, false, false),
        (35, 'Cốc giấy 7oz ( 1 dây x 50c)', 0, NULL, NULL, NULL, false, false),
        (36, 'Bơm 1ml', 0, NULL, NULL, NULL, false, false),
        (37, 'Bao cao su', 0, NULL, NULL, NULL, false, false),
        (38, 'Áo thủ thuật', 0, NULL, NULL, NULL, false, false),
        (39, 'Topocain - Thuốc tê bôi', 0, 'hộp', NULL, NULL, false, false),
        (40, 'Đầu dò Bio nhiều lần', 900000, 'cái', 'VT_DAU_DO_BIO_NHIEU_LAN', 'SP000153', true, false),
        (41, 'Đầu dò Bio 1 lần', 300000, 'cái', 'VT_DAU_DO_BIO_1_LAN', 'SP000152', true, false),
        (42, 'Kim sinh thiết vú', 0, NULL, NULL, NULL, false, false),
        (43, 'Catheter gynetics', 0, NULL, NULL, NULL, false, false),
        (44, 'Prp kit tropocel isre', 0, 'kit', NULL, NULL, false, false),
        (45, 'Prp kit regenlab', 0, 'kit', NULL, NULL, false, false),
        (46, 'Găng tay y tế ( hộp )', 0, 'hộp', NULL, NULL, false, false),
        (47, 'Que thử nước tiểu', 0, 'hộp', NULL, NULL, false, false),
        (48, 'Sonde Nelaton', 0, 'cái', NULL, NULL, false, false),
        (49, 'Vòng nâng CTC Pessary', 0, 'cái', NULL, NULL, false, false),
        (50, 'Túi clear ( cái)', 0, NULL, NULL, NULL, false, false),
        (51, 'Vòng đồng tránh thai (cái)', 0, NULL, NULL, NULL, false, false),
        (52, 'Vòng nội tiết tránh thai Mirena', 4000000, 'cái', 'VT_MIRENA', NULL, false, true),
        (53, 'Que tránh thai Implanon', 0, 'cái', NULL, NULL, false, false),
        (54, 'Lưỡi dao PT (cái)', 0, NULL, NULL, NULL, false, false),
        (55, 'Băng vệ sinh (cái)', 0, NULL, NULL, NULL, false, false),
        (56, 'Tê tại chỗ Lidocan', 0, 'ống', NULL, NULL, false, false),
        (57, 'Cốc nhựa đựng nước tiểu (cái)', 0, NULL, NULL, NULL, false, false),
        (58, 'Lọ+chổi đựng mẫu PCR (lọ)', 0, NULL, NULL, NULL, false, false),
        (59, 'Lọ + chổi đựng mẫu HPV + Thin (lọ)', 0, NULL, NULL, NULL, false, false),
        (60, 'Mỏ vịt nhựa (cái)', 0, NULL, NULL, NULL, false, false),
        (61, 'Que thử nước tiểu', 0, 'que', NULL, NULL, false, false),
        (62, 'Giấy in xét nghiệm nước tiểu', 0, 'ram', NULL, NULL, false, false),
        (63, 'Giấy A5', 0, 'ram', NULL, NULL, false, false),
        (64, 'Giấy in phun Kim Mai loại 115g (để siêu âm)', 0, 'tệp', NULL, NULL, false, false),
        (65, 'Mực in hồng nhạt', 0, 'lọ', NULL, NULL, false, false),
        (66, 'Mực in hồng đậm', 0, 'lọ', NULL, NULL, false, false),
        (67, 'Mực in xanh nhạt', 0, 'lọ', NULL, NULL, false, false),
        (68, 'Mực in xanh đậm', 0, 'lọ', NULL, NULL, false, false),
        (69, 'Mực in vàng', 0, 'lọ', NULL, NULL, false, false),
        (70, 'Mực in Đen', 0, 'lọ', NULL, NULL, false, false),
        (71, 'Xông tiểu Foley 12/2', 0, 'cái', NULL, NULL, false, false),
        (72, 'Kim luồn G22', 0, 'Hộp', NULL, NULL, false, false),
        (73, 'Túi vàng (10kg)', 0, 'tệp', NULL, NULL, false, false),
        (74, 'Săng vải thủ thuật', 0, 'cái', NULL, NULL, false, false),
        (75, 'Nước muối truyền', 0, 'chai', NULL, NULL, false, false),
        (76, 'Lọ đựng mẫu nắp đỏ', 0, 'lọ', NULL, NULL, false, false),
        (77, 'Kim lấy thuốc', 0, 'hộp', NULL, NULL, false, false),
        (78, 'Găng tay y tế ( hộp )', 0, 'đôi', NULL, NULL, false, false),
        (79, 'Gạc meche phẫu thuật', 0, 'gói', NULL, NULL, false, false),
        (80, 'Gạc củ ấu', 0, 'gói', NULL, NULL, false, false),
        (81, 'Dung dịch sát khuẩn tay', 0, 'chai', NULL, NULL, false, false),
        (82, 'Dây truyền', 0, 'cái', NULL, NULL, false, false),
        (83, 'Bơm 5ml', 0, 'cái', NULL, NULL, false, false),
        (84, 'Băng chun', 0, 'cuộn', NULL, NULL, false, false)
    ;

    -- 5a. Dòng chưa có → thêm (chỉ phòng khám đã có bảng giá dịch vụ).
    WITH moi AS (
        SELECT c.id AS clinic_id, x.*,
               coalesce(x.ma, 'VT_' || upper(substr(md5(
                   public.khoa_ten_dich_vu(x.ten) || '|'
                   || public.khoa_ten_dich_vu(coalesce(x.don_vi, ''))), 1, 10))) AS code
          FROM public.clinic c
         CROSS JOIN _vat_tu_nguon x
         WHERE EXISTS (SELECT 1 FROM public.service_price p
                        WHERE p.clinic_id = c.id AND p."group" = 'dich_vu')
    ),
    them AS (
        INSERT INTO public.service_price
            (clinic_id, service_code, name, "group", unit_price, active, category,
             billing_owner, don_vi, ma_kiotviet, can_ql_duyet, chon_nhanh)
        SELECT m.clinic_id, m.code, m.ten, 'vat_tu',
               CASE WHEN m.gia > 0 THEN m.gia END, true, 'Nguyên liệu tiêu hao',
               'CLINIC', m.don_vi,
               -- Mã kho KiotViet của đầu dò (đã có ở danh mục thuốc/kho) — chỉ gắn
               -- khi chưa dòng nào trong phòng khám giữ mã ấy.
               CASE WHEN m.ma_kiotviet IS NOT NULL AND NOT EXISTS (
                        SELECT 1 FROM public.service_price q
                         WHERE q.clinic_id = m.clinic_id
                           AND q.ma_kiotviet = m.ma_kiotviet)
                    THEN m.ma_kiotviet END,
               m.can_ql_duyet, m.chon_nhanh
          FROM moi m
        ON CONFLICT (clinic_id, "group", service_code) DO NOTHING
        RETURNING 1
    )
    SELECT count(*) INTO n_them FROM them;

    -- 5b. Dòng đã có → đồng bộ tên / nhóm / đơn vị / cờ (giá chỉ khi được phép).
    WITH moi AS (
        SELECT c.id AS clinic_id, x.*,
               coalesce(x.ma, 'VT_' || upper(substr(md5(
                   public.khoa_ten_dich_vu(x.ten) || '|'
                   || public.khoa_ten_dich_vu(coalesce(x.don_vi, ''))), 1, 10))) AS code
          FROM public.clinic c CROSS JOIN _vat_tu_nguon x
    ),
    sua AS (
        UPDATE public.service_price sp
           SET name = m.ten, category = 'Nguyên liệu tiêu hao',
               don_vi = m.don_vi, can_ql_duyet = m.can_ql_duyet,
               chon_nhanh = m.chon_nhanh,
               unit_price = CASE WHEN p_ghi_de_gia
                                 THEN CASE WHEN m.gia > 0 THEN m.gia END
                                 ELSE sp.unit_price END,
               updated_at = now()
          FROM moi m
         WHERE sp.clinic_id = m.clinic_id AND sp."group" = 'vat_tu'
           AND sp.service_code = m.code
           AND (sp.name, sp.category, sp.don_vi, sp.can_ql_duyet, sp.chon_nhanh,
                sp.unit_price)
               IS DISTINCT FROM
               (m.ten, 'Nguyên liệu tiêu hao', m.don_vi, m.can_ql_duyet,
                m.chon_nhanh,
                CASE WHEN p_ghi_de_gia THEN CASE WHEN m.gia > 0 THEN m.gia END
                     ELSE sp.unit_price END)
        RETURNING 1
    )
    SELECT count(*) INTO n_sua FROM sua;

    -- 5c. Gợi ý: dịch vụ Bio "chưa bao gồm đầu dò" (SP000146 Tập máy Bio,
    -- SP000145 Đo trương lực cơ sàn chậu máy Bio) → hai đầu dò chọn nhanh.
    WITH goi AS (
        INSERT INTO public.vat_tu_goi_y (clinic_id, dich_vu_id, vat_tu_id)
        SELECT dv.clinic_id, dv.id, vt.id
          FROM public.service_price dv
          JOIN public.service_price vt
            ON vt.clinic_id = dv.clinic_id AND vt."group" = 'vat_tu'
           AND vt.service_code IN ('VT_DAU_DO_BIO_1_LAN', 'VT_DAU_DO_BIO_NHIEU_LAN')
         WHERE dv."group" = 'dich_vu' AND dv.ma_kiotviet IN ('SP000145', 'SP000146')
        ON CONFLICT DO NOTHING
        RETURNING 1
    )
    SELECT count(*) INTO n_goi FROM goi;

    RETURN QUERY SELECT n_them, n_sua, n_goi;
END
$fn$;

DO $$
DECLARE
    r record;
BEGIN
    SELECT * INTO r FROM public.dong_bo_vat_tu(false);
    RAISE NOTICE 'Vật tư 01/10: thêm % · sửa % · gợi ý %', r.them, r.sua, r.goi_y;
END
$$;

-- ── 6. Dọn dữ liệu khách thử biết bảng mới ──────────────────────────────────
-- Chép nguyên hàm của 20261002300000_thu_nhieu_hinh_thuc.sql, chỉ thêm
-- 'luot_vat_tu' vào danh sách bảng dữ liệu khách (không khai thì kiểm "còn dòng
-- trỏ vào dữ liệu đã xoá" dừng khi dọn một khách đã mua vật tư).
CREATE OR REPLACE FUNCTION public.don_khach_thu(
    p_clinic uuid,
    p_khach uuid[],
    p_lam_that boolean,
    p_moc timestamptz DEFAULT NULL,
    p_nguoi uuid DEFAULT NULL,
    p_nguoi_ten text DEFAULT NULL,
    p_nguon text DEFAULT 'man_quan_tri'
) RETURNS jsonb
LANGUAGE plpgsql
AS $fn$
DECLARE
    -- Bảng dữ liệu KHÁCH (lan theo cột nối). Bảng mới có dữ liệu khách mà
    -- chưa khai ở đây → Chốt 1 hoặc Chốt 4 dừng và báo tên.
    bang_khach text[] := ARRAY[
        'patient', 'patient_contact_channel', 'patient_medical_profile',
        'patient_next_of_kin', 'patient_sdt_them', 'patient_link',
        'pregnancy', 'mpi_merge_queue', 'clinical_data_consent',
        'appointment', 'appointment_doi_lich', 'care_episode',
        'follow_up_case', 'round_requirement', 'review_round',
        'nhac_tai_kham', 'hen_goi_lai', 'tuong_tac_cskh', 'cskh_action',
        'cskh_log', 'phan_hoi_khach', 'service_log', 'ghi_chu_khach',
        'luot_phi_kham',
        'visit', 'visit_amendment', 'visit_route', 'visit_gate_override',
        'encounter_flow', 'queue_entry', 'consultation', 'consultation_note',
        'clinical_record', 'clinical_form_response', 'clinical_release',
        'phieu_kham_luot', 'phieu_kham_lich_su', 'ultrasound_record', 'lab_result',
        'vital_measurement', 'form_instance', 'form_result_release',
        'result_correction',
        'service_order', 'service_order_draft', 'service_selection_state',
        'service_execution_attempt', 'doi_tac_nhan_viec', 'doi_tac_thanh_toan',
        'luot_phu_thu', 'luot_vat_tu', 'tep_ket_qua',
        'payment', 'payment_cycle', 'payment_bill_line', 'payment_refund',
        'payment_refund_line', 'payment_cycle_doi_hinh_thuc',
        'payment_cycle_phan', 'anh_chuyen_khoan',
        'prescription', 'prescription_allocation', 'prescription_correction',
        'drug_return', 'thuoc_giao_chua_gan_lo', 'inventory_txn',
        'work_item', 'work_item_dependency', 'work_item_event',
        'nhac_viec_ca_nhan', 'slot_hold',
        'event_delivery', 'luot_dong_thoi_gian'];
    r record;
    n bigint;
    sai text;
    vong int;
    tien boolean;
    con_lai int;
    loi text;
    dk text;
    v_lan uuid;
    v_khach jsonb;
    v_so_dong jsonb;
    v_tep jsonb;
BEGIN
    IF p_nguon NOT IN ('man_quan_tri', 'script_moc') THEN
        RAISE EXCEPTION 'Nguồn không hợp lệ: %', p_nguon;
    END IF;
    p_khach := coalesce(p_khach, ARRAY[]::uuid[]);
    SELECT count(*) INTO n FROM unnest(p_khach) u(id)
    WHERE NOT EXISTS (SELECT 1 FROM public.patient p
                      WHERE p.clinic_patient_id = u.id AND p.clinic_id = p_clinic);
    IF n > 0 THEN
        RAISE EXCEPTION 'Có % khách không tồn tại hoặc không thuộc phòng khám này', n
            USING ERRCODE = 'no_data_found';
    END IF;

    SET CONSTRAINTS ALL IMMEDIATE;

    -- Gọi lần hai trong cùng giao dịch (xem trước rồi xoá): bỏ bảng tạm cũ.
    -- Kiểm tồn tại trước (không `DROP IF EXISTS`) để khỏi rải NOTICE ra client.
    FOREACH dk IN ARRAY ARRAY['_dt_kh', '_dt_d', '_dt_song', '_dt_tb_uuid', '_dt_dem',
                              '_dt_giu', '_dt_trigger', '_dt_tep'] LOOP
        IF to_regclass('pg_temp.' || dk) IS NOT NULL THEN
            EXECUTE format('DROP TABLE pg_temp.%I', dk);
        END IF;
    END LOOP;
    CREATE TEMP TABLE _dt_kh (bang text, k text, PRIMARY KEY (bang, k)) ON COMMIT DROP;
    CREATE TEMP TABLE _dt_d (id uuid PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE _dt_song (id uuid PRIMARY KEY) ON COMMIT DROP;

    -- ── Kế hoạch: khách → mọi dòng kéo theo ───────────────────────────────
    PERFORM public._don_thu_lap('patient',
        'x.clinic_patient_id = ANY (' || quote_literal(p_khach::text) || '::uuid[])');
    PERFORM public._don_thu_lan(bang_khach);

    -- Chốt 2: không rò sang khách không được chọn.
    sai := '';
    FOR r IN
        SELECT c.table_name AS t, c.column_name AS cot
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name IN (SELECT DISTINCT bang FROM _dt_kh)
          AND c.column_name IN ('clinic_patient_id', 'visit_id', 'appointment_id')
          AND c.data_type = 'uuid'
    LOOP
        EXECUTE format(
            'SELECT count(*) FROM public.%I x WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)'
            || ' AND x.%I IS NOT NULL AND x.%I NOT IN (SELECT id FROM _dt_d)',
            r.t, public._don_thu_khoa(('public.' || r.t)::regclass, 'x'), r.t,
            r.cot, r.cot) INTO n;
        IF n > 0 THEN sai := sai || format('%s.%s (%s dòng); ', r.t, r.cot, n); END IF;
    END LOOP;
    IF sai <> '' THEN
        RAISE EXCEPTION 'Kế hoạch rò sang dữ liệu của khách KHÔNG được chọn: %', sai;
    END IF;

    -- ── Sổ sự kiện, thông báo… ────────────────────────────────────────────
    IF p_moc IS NOT NULL THEN
        -- "Còn sống" = khoá chính uuid mọi bảng, trừ dòng sắp xoá.
        FOR r IN
            SELECT c.relname, att.attname
            FROM pg_class c
            JOIN pg_index i ON i.indrelid = c.oid AND i.indisprimary AND i.indnatts = 1
            JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum = i.indkey[0]
            WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND att.atttypid = 'uuid'::regtype
        LOOP
            EXECUTE format('INSERT INTO _dt_song SELECT x.%I FROM public.%I x'
                           || ' ON CONFLICT DO NOTHING', r.attname, r.relname);
        END LOOP;
        DELETE FROM _dt_song WHERE id IN (SELECT id FROM _dt_d);
    END IF;
    -- Thông báo trỏ bằng chuỗi (nguon_id "loai:<uuid>", duong_dan "?selected=<uuid>").
    CREATE TEMP TABLE _dt_tb_uuid ON COMMIT DROP AS
    SELECT b.id AS tb, m[1]::uuid AS u
    FROM public.thong_bao b
    CROSS JOIN LATERAL regexp_matches(
        coalesce(b.nguon_id, '') || ' ' || coalesce(b.duong_dan, ''),
        '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'g') AS m
    WHERE b.clinic_id = p_clinic;
    vong := 0;
    LOOP
        vong := vong + 1;
        EXIT WHEN public._don_thu_lap_so(p_moc) + public._don_thu_lan(bang_khach) = 0;
        IF vong > 20 THEN RAISE EXCEPTION 'Lan sổ quá 20 vòng'; END IF;
    END LOOP;

    -- Chốt 1: dòng được GIỮ trỏ (khoá ngoại) vào dòng sắp xoá → dừng.
    sai := '';
    FOR r IN
        SELECT c.conrelid::regclass AS rr, c.confrelid::regclass AS tt, c.conkey, c.confkey
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
          AND c.confrelid::regclass::text IN (SELECT DISTINCT bang FROM _dt_kh)
    LOOP
        SELECT string_agg(format('r.%I = t.%I', ra.attname, ta.attname), ' AND ')
          INTO dk
        FROM unnest(r.conkey, r.confkey) AS u(rk, tk)
        JOIN pg_attribute ra ON ra.attrelid = r.rr AND ra.attnum = u.rk
        JOIN pg_attribute ta ON ta.attrelid = r.tt AND ta.attnum = u.tk;
        EXECUTE format(
            'SELECT count(*) FROM %s r JOIN %s t ON %s'
            || ' WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)'
            || ' AND %s NOT IN (SELECT k FROM _dt_kh WHERE bang = %L)',
            r.rr, r.tt, dk,
            public._don_thu_khoa(r.tt, 't'), r.tt::text,
            public._don_thu_khoa(r.rr, 'r'), r.rr::text) INTO n;
        IF n > 0 THEN sai := sai || format('%s → %s (%s dòng); ', r.rr, r.tt, n); END IF;
    END LOOP;
    IF sai <> '' THEN
        RAISE EXCEPTION 'Dòng được GIỮ đang trỏ vào dòng sắp xoá (khai bảng vào don_khach_thu hoặc xem lại): %', sai;
    END IF;

    -- ── Kết quả kế hoạch ──────────────────────────────────────────────────
    SELECT coalesce(jsonb_agg(jsonb_build_object(
               'id', p.clinic_patient_id, 'ma', p.patient_code, 'ten', p.full_name)
             ORDER BY p.full_name), '[]'::jsonb)
      INTO v_khach
    FROM public.patient p WHERE p.clinic_patient_id = ANY (p_khach);
    SELECT coalesce(jsonb_object_agg(bang, so), '{}'::jsonb) INTO v_so_dong
    FROM (SELECT bang, count(*) AS so FROM _dt_kh GROUP BY bang) x;
    CREATE TEMP TABLE _dt_tep ON COMMIT DROP AS
    SELECT t.vi_tri, t.khoa FROM public.tep_ket_qua t
    WHERE t.id IN (SELECT id FROM _dt_d) AND t.khoa IS NOT NULL AND t.da_don_tep_luc IS NULL;
    SELECT coalesce(jsonb_agg(jsonb_build_object('vi_tri', vi_tri, 'khoa', khoa) ORDER BY khoa),
                    '[]'::jsonb)
      INTO v_tep FROM _dt_tep;

    -- Chỉ xem trước, hoặc không có gì để xoá (chạy lại lần hai): không ghi nhật ký.
    IF NOT p_lam_that OR v_so_dong = '{}'::jsonb THEN
        RETURN jsonb_build_object('lam_that', false, 'khach', v_khach,
                                  'so_dong', v_so_dong, 'tep', v_tep);
    END IF;

    -- ── Làm thật ──────────────────────────────────────────────────────────
    INSERT INTO public.lan_don_du_lieu_thu
        (clinic_id, boi_staff_id, boi_ten, nguon, moc, khach, so_dong, tep)
    VALUES (p_clinic, p_nguoi, p_nguoi_ten, p_nguon, p_moc, v_khach, v_so_dong, v_tep)
    RETURNING id INTO v_lan;

    -- Bản lưu nguyên văn TRƯỚC khi xoá.
    FOR r IN SELECT DISTINCT bang FROM _dt_kh ORDER BY bang LOOP
        EXECUTE format(
            'INSERT INTO public.du_lieu_da_xoa (lan_id, bang, du_lieu)'
            || ' SELECT %L::uuid, %L, to_jsonb(x) FROM public.%I x'
            || ' WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)',
            v_lan, r.bang, r.bang,
            public._don_thu_khoa(('public.' || r.bang)::regclass, 'x'), r.bang);
    END LOOP;

    -- Chụp số dòng mọi bảng + lịch/lượt của khách GIỮ (Chốt 4).
    CREATE TEMP TABLE _dt_dem (bang text PRIMARY KEY, truoc bigint) ON COMMIT DROP;
    FOR r IN SELECT relname FROM pg_class
             WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
               AND relname NOT IN ('lan_don_du_lieu_thu', 'du_lieu_da_xoa') LOOP
        EXECUTE format('SELECT count(*) FROM public.%I', r.relname) INTO n;
        INSERT INTO _dt_dem VALUES (r.relname, n);
    END LOOP;
    CREATE TEMP TABLE _dt_giu ON COMMIT DROP AS
    SELECT p.clinic_patient_id AS id,
           (SELECT count(*) FROM public.appointment a WHERE a.clinic_patient_id = p.clinic_patient_id) AS so_lich,
           (SELECT count(*) FROM public.visit v WHERE v.clinic_patient_id = p.clinic_patient_id) AS so_luot
    FROM public.patient p
    WHERE p.clinic_id = p_clinic AND p.clinic_patient_id <> ALL (p_khach);

    -- Chốt 3: tắt các trigger BEFORE (chốt chặn xoá cứng / chỉ-thêm) của đúng
    -- các bảng có dòng bị xoá. Trigger AFTER (báo realtime…) vẫn chạy.
    CREATE TEMP TABLE _dt_trigger ON COMMIT DROP AS
    SELECT c.relname AS bang, t.tgname AS ten
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
    WHERE NOT t.tgisinternal AND t.tgenabled <> 'D' AND (t.tgtype & 2) <> 0
      AND c.relnamespace = 'public'::regnamespace
      AND c.relname IN (SELECT DISTINCT bang FROM _dt_kh)
    ORDER BY 1, 2;
    FOR r IN SELECT * FROM _dt_trigger LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE TRIGGER %I', r.bang, r.ten);
    END LOOP;

    -- Kho: trả số lượng của phiếu xuất/bán sắp xoá về lô (lô vẫn giữ).
    UPDATE public.drug_batch b
       SET quantity_on_hand = b.quantity_on_hand - s.q, updated_at = now()
      FROM (SELECT t.drug_batch_id, sum(t.quantity) AS q FROM public.inventory_txn t
            WHERE t.id IN (SELECT id FROM _dt_d) GROUP BY 1) s
     WHERE b.id = s.drug_batch_id;

    -- Vòng khoá ngoại đã biết: appointment.episode_id ↔
    -- care_episode.opened_appointment_id. Cắt ở phía care_episode (dòng sắp xoá).
    UPDATE public.care_episode x SET opened_appointment_id = NULL
    WHERE x.id IN (SELECT id FROM _dt_d) AND x.opened_appointment_id IS NOT NULL;

    -- Xoá theo vòng: bảng nào còn bị trỏ tới thì để vòng sau.
    vong := 0;
    LOOP
        vong := vong + 1; tien := false; con_lai := 0; loi := '';
        FOR r IN SELECT DISTINCT bang FROM _dt_kh ORDER BY bang LOOP
            BEGIN
                EXECUTE format(
                    'DELETE FROM public.%I x WHERE %s IN (SELECT k FROM _dt_kh WHERE bang = %L)',
                    r.bang, public._don_thu_khoa(('public.' || r.bang)::regclass, 'x'), r.bang);
                GET DIAGNOSTICS n = ROW_COUNT;
                IF n > 0 THEN tien := true; END IF;
            -- Bị trỏ tới, hoặc ON DELETE SET NULL của bảng cha đụng CHECK /
            -- NOT NULL ở một dòng CŨNG sắp xoá → để vòng sau.
            EXCEPTION WHEN foreign_key_violation OR restrict_violation
                        OR check_violation OR not_null_violation THEN
                con_lai := con_lai + 1;
                loi := loi || r.bang || ' (' || SQLERRM || '); ';
            END;
        END LOOP;
        EXIT WHEN con_lai = 0;
        IF NOT tien OR vong > 30 THEN
            RAISE EXCEPTION 'Kẹt khoá ngoại, không xoá được: %', loi;
        END IF;
    END LOOP;

    FOR r IN SELECT * FROM _dt_trigger LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE TRIGGER %I', r.bang, r.ten);
    END LOOP;

    -- ── Chốt 4 ────────────────────────────────────────────────────────────
    sai := '';
    FOR r IN SELECT d.bang, d.truoc,
                    (SELECT count(*) FROM _dt_kh k WHERE k.bang = d.bang) AS ke_hoach
             FROM _dt_dem d LOOP
        EXECUTE format('SELECT count(*) FROM public.%I', r.bang) INTO n;
        IF r.truoc - n <> r.ke_hoach THEN
            sai := sai || format('%s (kế hoạch %s, mất %s); ', r.bang, r.ke_hoach, r.truoc - n);
        END IF;
    END LOOP;
    IF sai <> '' THEN RAISE EXCEPTION 'Số dòng mất KHÁC kế hoạch: %', sai; END IF;

    FOR r IN
        SELECT c.table_name AS t, c.column_name AS cot
        FROM information_schema.columns c
        JOIN pg_class pc ON pc.relname = c.table_name
         AND pc.relnamespace = 'public'::regnamespace AND pc.relkind = 'r'
        WHERE c.table_schema = 'public' AND c.data_type = 'uuid'
    LOOP
        EXECUTE format('SELECT count(*) FROM public.%I WHERE %I IN (SELECT id FROM _dt_d)',
                       r.t, r.cot) INTO n;
        IF n > 0 THEN sai := sai || format('%s.%s (%s); ', r.t, r.cot, n); END IF;
    END LOOP;
    IF sai <> '' THEN RAISE EXCEPTION 'Còn dòng trỏ vào dữ liệu đã xoá: %', sai; END IF;

    IF EXISTS (
        SELECT 1 FROM _dt_giu g
        WHERE g.so_lich <> (SELECT count(*) FROM public.appointment a WHERE a.clinic_patient_id = g.id)
           OR g.so_luot <> (SELECT count(*) FROM public.visit v WHERE v.clinic_patient_id = g.id)
           OR NOT EXISTS (SELECT 1 FROM public.patient p WHERE p.clinic_patient_id = g.id)
    ) THEN
        RAISE EXCEPTION 'Dữ liệu của khách KHÔNG được chọn bị đổi — dừng';
    END IF;
    IF EXISTS (SELECT 1 FROM public.drug_batch WHERE quantity_on_hand < 0) THEN
        RAISE EXCEPTION 'Có lô thuốc tồn âm sau khi trả lại';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
               JOIN _dt_trigger x ON x.bang = c.relname AND x.ten = t.tgname
               WHERE t.tgenabled = 'D') THEN
        RAISE EXCEPTION 'Còn trigger bị tắt';
    END IF;

    RETURN jsonb_build_object('lam_that', true, 'lan_id', v_lan, 'khach', v_khach,
                              'so_dong', v_so_dong, 'tep', v_tep);
END $fn$;
