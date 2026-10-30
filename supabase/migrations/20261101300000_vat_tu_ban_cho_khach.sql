-- BÁN VẬT TƯ TRỪ KHO ĐÚNG PHÒNG + DANH SÁCH ĐỐI SOÁT (Tuyền 31/10/2026).
--
-- Trước đây bán vật tư (quầy dịch vụ, Bio theo chỉ định, hàng trùng mã ở quầy
-- thuốc) chỉ ghi tiền; sổ `vat_tu_txn` không biết. Từ nay MỖI NGUỒN BÁN có MỘT
-- dòng `vat_tu_ban`: tiền thu xong thì trừ thật (phiếu loại BAN), hoàn tác / hoàn
-- tiền / bỏ chỉ định thì đảo đúng phiếu ấy (phiếu HOAN), thu lại thì trừ lại.
--
-- Dòng là "trạng thái hiện tại" để đối soát; lịch sử thật nằm ở sổ phiếu (chỉ
-- thêm). Mọi thay đổi đi qua `vat_tu_ban_service` — so số cần trừ với số đang trừ
-- nên gọi lại bao nhiêu lần cũng ra một kết quả.
--
-- KHÔNG đụng dữ liệu cũ: migration này không ghi sổ, không tạo dòng cho khoản đã
-- thu. `luot_vat_tu.tru_kho`: dòng có TRƯỚC lúc lên = false, dòng mới = true — để
-- "dịch vụ đã làm" của dòng cũ không tự trừ ngược, kho không âm hàng loạt.

ALTER TABLE public.luot_vat_tu
    ADD COLUMN IF NOT EXISTS tru_kho boolean NOT NULL DEFAULT false;
ALTER TABLE public.luot_vat_tu ALTER COLUMN tru_kho SET DEFAULT true;
COMMENT ON COLUMN public.luot_vat_tu.tru_kho IS
'Dòng tạo sau khi có trừ kho khi bán (31/10/2026): được trừ kho theo trạng thái dịch vụ. Dòng cũ false — chỉ trừ nếu có lần thu MỚI.';

CREATE TABLE IF NOT EXISTS public.vat_tu_ban (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    location_id uuid NOT NULL REFERENCES public.clinic_location(id) ON DELETE RESTRICT,
    nguon text NOT NULL,
    luot_vat_tu_id uuid REFERENCES public.luot_vat_tu(id) ON DELETE RESTRICT,
    prescription_id uuid REFERENCES public.prescription(id) ON DELETE RESTRICT,
    -- Khoá gửi của nhập bù (không có nguồn bán để làm khoá).
    khoa_gui text,
    visit_id uuid,
    clinic_patient_id uuid NOT NULL,
    vat_tu_id uuid NOT NULL REFERENCES public.service_price(id) ON DELETE RESTRICT,
    ten text NOT NULL,
    don_vi text,
    -- Số đang bán. Hoàn hết thì GIỮ số cũ, trạng thái DA_HOAN nói phần còn lại.
    so_luong numeric(18,3) NOT NULL,
    don_gia numeric(14,0),
    -- Tiền thực thu còn lại (sau giảm, sau hoàn). Nhập bù luôn 0.
    thanh_tien numeric(14,0) NOT NULL DEFAULT 0,
    -- Giá vốn chụp lúc trừ (giá nhập gần nhất) — doanh thu không đọc cột này.
    gia_von numeric(18,0) NOT NULL DEFAULT 0,
    -- HOÀN TIỀN KHÔNG có nghĩa hàng về: `so_hoan_tien` chép từ sổ hoàn, `so_tra` =
    -- người kho / quầy đã nhận lại hàng, `so_khong_nhan` = kết luận không nhận lại.
    so_hoan_tien numeric(18,3) NOT NULL DEFAULT 0,
    so_tra numeric(18,3) NOT NULL DEFAULT 0,
    so_khong_nhan numeric(18,3) NOT NULL DEFAULT 0,
    -- NULL = dịch vụ đã làm mà chưa thu ("làm trước, thu sau", ghi nợ).
    payment_cycle_id uuid,
    ban_boi uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    ban_luc timestamptz NOT NULL DEFAULT now(),
    bac_si_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    -- Nơi lấy: PHONG (room_id) · KHO (Kho cơ sở). NULL = chưa xác định được.
    noi_lay text,
    room_id uuid REFERENCES public.clinic_room(id) ON DELETE RESTRICT,
    -- Ai quyết nơi lấy: CHI_DINH · BAC_SI (máy suy) · KHO (người kho gán — máy
    -- không tự đổi nữa).
    noi_nguon text,
    trang_thai text NOT NULL,
    ly_do text,
    -- Phiếu BAN đang có hiệu lực (chưa đảo).
    phieu_id uuid REFERENCES public.vat_tu_phieu(id) ON DELETE RESTRICT,
    -- Đếm phiếu đã ghi: làm khoá gửi phiếu, hai lần ghi đua nhau thì một lần đỏ.
    so_phieu integer NOT NULL DEFAULT 0,
    sua_boi uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    sua_luc timestamptz,
    tao_luc timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vat_tu_ban_nguon_check
        CHECK (nguon IN ('QUAY_DICH_VU', 'CHI_DINH', 'QUAY_THUOC', 'NHAP_BU')),
    CONSTRAINT vat_tu_ban_co_nguon CHECK (
        (nguon IN ('QUAY_DICH_VU', 'CHI_DINH')) = (luot_vat_tu_id IS NOT NULL)
        AND (nguon = 'QUAY_THUOC') = (prescription_id IS NOT NULL)
        AND (nguon = 'NHAP_BU') = (khoa_gui IS NOT NULL)
    ),
    CONSTRAINT vat_tu_ban_nhap_bu_khong_tien
        CHECK (nguon <> 'NHAP_BU' OR (thanh_tien = 0 AND ly_do IS NOT NULL)),
    CONSTRAINT vat_tu_ban_so_luong CHECK (
        so_luong > 0 AND so_luong NOT IN ('NaN'::numeric, 'Infinity'::numeric)
        AND so_hoan_tien >= 0 AND so_tra >= 0 AND so_khong_nhan >= 0
    ),
    CONSTRAINT vat_tu_ban_trang_thai_check
        CHECK (trang_thai IN ('DA_TRU', 'CHO_GAN_PHONG', 'DA_HOAN')),
    CONSTRAINT vat_tu_ban_noi_check CHECK (
        (noi_lay IS NULL OR noi_lay IN ('PHONG', 'KHO'))
        AND (noi_nguon IS NULL OR noi_nguon IN ('CHI_DINH', 'BAC_SI', 'KHO'))
        AND (noi_lay IS NOT DISTINCT FROM 'PHONG') = (room_id IS NOT NULL)
    ),
    -- DA_TRU ⇔ đang có phiếu; chờ gán thì chưa có nơi lấy.
    CONSTRAINT vat_tu_ban_phieu_check CHECK (
        (trang_thai = 'DA_TRU') = (phieu_id IS NOT NULL)
        AND (trang_thai <> 'DA_TRU' OR noi_lay IS NOT NULL)
        AND (trang_thai <> 'CHO_GAN_PHONG' OR noi_lay IS NULL)
    ),
    -- Mỗi phiếu BAN thuộc đúng một dòng: một lần bán không chiếm hai phiếu.
    CONSTRAINT vat_tu_ban_mot_phieu UNIQUE (clinic_id, phieu_id)
);

-- Mỗi nguồn bán MỘT dòng — gửi lại lệnh thu không sinh dòng thứ hai.
CREATE UNIQUE INDEX IF NOT EXISTS vat_tu_ban_mot_dong_luot
    ON public.vat_tu_ban (clinic_id, luot_vat_tu_id)
    WHERE luot_vat_tu_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS vat_tu_ban_mot_dong_don
    ON public.vat_tu_ban (clinic_id, prescription_id)
    WHERE prescription_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS vat_tu_ban_mot_dong_nhap_bu
    ON public.vat_tu_ban (clinic_id, location_id, khoa_gui)
    WHERE khoa_gui IS NOT NULL;
CREATE INDEX IF NOT EXISTS vat_tu_ban_theo_luot
    ON public.vat_tu_ban (clinic_id, visit_id);
CREATE INDEX IF NOT EXISTS vat_tu_ban_theo_ngay
    ON public.vat_tu_ban (clinic_id, location_id, ban_luc DESC);

COMMENT ON TABLE public.vat_tu_ban IS
'Danh sách đối soát vật tư bán cho khách (31/10/2026): mỗi nguồn bán một dòng, nơi lấy, trạng thái. Sổ thật là vat_tu_txn qua phiếu BAN/HOAN.';

CREATE OR REPLACE FUNCTION public.vat_tu_ban_gac() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic_location
                    WHERE id = NEW.location_id AND clinic_id = NEW.clinic_id)
       OR NOT EXISTS (SELECT 1 FROM public.service_price
                       WHERE id = NEW.vat_tu_id AND clinic_id = NEW.clinic_id
                         AND "group" = 'vat_tu')
       OR (NEW.room_id IS NOT NULL AND NOT EXISTS (
               SELECT 1 FROM public.clinic_room
                WHERE id = NEW.room_id AND clinic_id = NEW.clinic_id
                  AND location_id = NEW.location_id)) THEN
        RAISE EXCEPTION 'Dòng bán vật tư sai cơ sở/mặt hàng/phòng'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS vat_tu_ban_gac ON public.vat_tu_ban;
CREATE TRIGGER vat_tu_ban_gac BEFORE INSERT OR UPDATE ON public.vat_tu_ban
    FOR EACH ROW EXECUTE FUNCTION public.vat_tu_ban_gac();

ALTER TABLE public.vat_tu_ban ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vat_tu_ban_select_own_clinic ON public.vat_tu_ban;
CREATE POLICY vat_tu_ban_select_own_clinic ON public.vat_tu_ban
    FOR SELECT TO service_role USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.vat_tu_ban TO service_role;

DROP TRIGGER IF EXISTS trg_notify_vat_tu_ban ON public.vat_tu_ban;
CREATE TRIGGER trg_notify_vat_tu_ban
    AFTER INSERT OR UPDATE OR DELETE ON public.vat_tu_ban
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

-- ── Phiếu loại BAN: có khách, có lần thu ────────────────────────────────────
ALTER TABLE public.vat_tu_phieu
    ADD COLUMN IF NOT EXISTS ban_id uuid REFERENCES public.vat_tu_ban(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS clinic_patient_id uuid,
    ADD COLUMN IF NOT EXISTS payment_cycle_id uuid;

CREATE INDEX IF NOT EXISTS vat_tu_phieu_theo_ban
    ON public.vat_tu_phieu (clinic_id, ban_id) WHERE ban_id IS NOT NULL;
-- Lịch sử thao tác lọc theo mặt hàng.
CREATE INDEX IF NOT EXISTS vat_tu_txn_mat_hang
    ON public.vat_tu_txn (clinic_id, vat_tu_id, phieu_id);

ALTER TABLE public.vat_tu_phieu DROP CONSTRAINT IF EXISTS vat_tu_phieu_loai_check;
ALTER TABLE public.vat_tu_phieu ADD CONSTRAINT vat_tu_phieu_loai_check
    CHECK (loai IN (
        'NHAP', 'XUAT_PHONG', 'TRA_KHO', 'CHUYEN_PHONG', 'KIEM',
        'DIEU_CHINH', 'HUY', 'TRA_NCC', 'HOAN', 'BAN'
    ));

ALTER TABLE public.vat_tu_phieu DROP CONSTRAINT IF EXISTS vat_tu_phieu_ban_check;
ALTER TABLE public.vat_tu_phieu ADD CONSTRAINT vat_tu_phieu_ban_check
    CHECK (loai <> 'BAN' OR ban_id IS NOT NULL);

-- Thêm hai lưới cuối (SO-LUAT Phần 6):
--   * phiếu đảo của một lần bán phải đi cùng dòng bán — hoàn tác tay ở Lịch sử thao
--     tác không được đảo sổ sau lưng danh sách đối soát;
--   * một dòng bán chỉ có MỘT phiếu BAN chưa đảo — Python có lỗi cũng không trừ hai lần.
CREATE OR REPLACE FUNCTION public.vat_tu_phieu_gac() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.clinic_location WHERE id=NEW.location_id AND clinic_id=NEW.clinic_id)
       OR NOT EXISTS (SELECT 1 FROM public.clinic_membership WHERE clinic_id=NEW.clinic_id AND staff_id=NEW.tao_boi AND is_active) THEN
        RAISE EXCEPTION 'Phiếu vật tư sai cơ sở/người tạo' USING ERRCODE='check_violation';
    END IF;
    IF NEW.dao_phieu_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.vat_tu_phieu WHERE id=NEW.dao_phieu_id AND clinic_id=NEW.clinic_id
          AND location_id=NEW.location_id AND loai<>'HOAN'
          AND ban_id IS NOT DISTINCT FROM NEW.ban_id) THEN
        RAISE EXCEPTION 'Không đảo phiếu khác cơ sở, phiếu đảo, hoặc phiếu bán ngoài dòng bán' USING ERRCODE='check_violation';
    END IF;
    IF NEW.loai='BAN' AND EXISTS (
        SELECT 1 FROM public.vat_tu_phieu p
         WHERE p.clinic_id=NEW.clinic_id AND p.ban_id=NEW.ban_id AND p.loai='BAN'
           AND NOT EXISTS (SELECT 1 FROM public.vat_tu_phieu d
                            WHERE d.clinic_id=p.clinic_id AND d.dao_phieu_id=p.id)) THEN
        RAISE EXCEPTION 'Dòng bán đang có phiếu BAN chưa đảo — không trừ hai lần' USING ERRCODE='check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Thêm: BAN luôn là số ra.
CREATE OR REPLACE FUNCTION public.vat_tu_txn_cong_ton() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE t record; p record; x record;
BEGIN
    SELECT * INTO p FROM public.vat_tu_phieu WHERE id=NEW.phieu_id AND clinic_id=NEW.clinic_id;
    SELECT * INTO t FROM public.vat_tu_ton WHERE id=NEW.ton_id AND clinic_id=NEW.clinic_id FOR UPDATE;
    IF t.id IS NULL OR p.id IS NULL OR t.location_id<>p.location_id OR t.vat_tu_id<>NEW.vat_tu_id THEN
        RAISE EXCEPTION 'Dòng sổ vật tư sai phiếu/nơi chứa/mặt hàng' USING ERRCODE='check_violation';
    END IF;
    IF p.giao_dich<>pg_current_xact_id() THEN
        RAISE EXCEPTION 'Phiếu đã lưu — không thêm dòng, lập phiếu mới' USING ERRCODE='check_violation';
    END IF;
    IF p.loai='KIEM' AND (NEW.so_luong<>0 OR NEW.thuc_te IS NULL) THEN
        RAISE EXCEPTION 'Kiểm đếm chưa điều chỉnh tồn' USING ERRCODE='check_violation';
    END IF;
    IF (p.loai='HOAN') <> (NEW.dao_txn_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Dòng đảo phải trỏ dòng gốc' USING ERRCODE='check_violation';
    END IF;
    IF NEW.dao_txn_id IS NOT NULL THEN
        SELECT * INTO x FROM public.vat_tu_txn WHERE id=NEW.dao_txn_id AND clinic_id=NEW.clinic_id;
        IF x.id IS NULL OR x.phieu_id<>p.dao_phieu_id OR x.ton_id<>NEW.ton_id
           OR x.so_luong<>-NEW.so_luong OR x.gia_nhap<>NEW.gia_nhap THEN
            RAISE EXCEPTION 'Phiếu đảo phải đối ứng đúng dòng gốc' USING ERRCODE='check_violation';
        END IF;
    END IF;
    NEW.ton_may := t.so_luong;
    IF (p.loai='NHAP' AND NEW.so_luong<=0)
       OR (p.loai IN ('HUY','TRA_NCC','BAN') AND NEW.so_luong>=0)
       OR (p.loai='DIEU_CHINH' AND (NEW.thuc_te IS NULL OR NEW.so_luong<>NEW.thuc_te-NEW.ton_may)) THEN
        RAISE EXCEPTION 'Dòng sổ không đúng loại phiếu/đếm thực tế' USING ERRCODE='check_violation';
    END IF;
    UPDATE public.vat_tu_ton SET so_luong=so_luong+NEW.so_luong
      WHERE id=NEW.ton_id AND clinic_id=NEW.clinic_id;
    RETURN NEW;
END $$;

NOTIFY pgrst, 'reload schema';
