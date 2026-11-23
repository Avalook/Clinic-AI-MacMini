-- LIÊN THÔNG ĐƠN THUỐC QUỐC GIA (24/11/2026) — dựng sẵn, TẮT bằng biến môi trường
-- `DTQG_BAT` (mặc định tắt). Căn cứ: TT 26/2025/TT-BYT Điều 12 khoản 6d (gửi đơn
-- lên Hệ thống đơn thuốc quốc gia ngay sau khi kết thúc khám), Điều 13 khoản 3b
-- (cơ sở không phải bệnh viện kê đơn điện tử trước 01/01/2026). Chuẩn kết nối:
-- QĐ 808/QĐ-BYT (01/04/2022). Tài liệu: docs/LIEN-THONG-DON-THUOC.md.
--
-- MỘT bảng, chỉ worker `su-kien` ghi (khi công tắc bật). Công tắc tắt ⇒ không ai
-- ghi, không màn nào đọc ⇒ hành vi hiện tại không đổi.
--
-- `dtqg_gui` — hàng chờ gửi (outbox). Mỗi PHIÊN BẢN nội dung đơn của một lượt khám
-- một dòng (`phien_ban` 1, 2, …), chụp gói đơn lúc vào hàng (`goi`) + dấu vân tay.
-- Mỗi phiên bản MỘT MÃ ĐƠN riêng: đơn đã gửi lên hệ thống quốc gia không sửa / huỷ
-- được (QĐ 425/QĐ-BYT Điều 9; QĐ 808 không có API sửa/huỷ) — đổi đơn = gửi đơn
-- MỚI mã mới. Trạng thái TÍNH RA từ sự việc (luật thiết kế 3), không lưu chữ:
--      DA_GUI    da_gui_luc IS NOT NULL
--      BI_THAY   chưa gửi mà lượt đã có phiên bản mới hơn (chỉ bản mới nhất được gửi)
--      KHONG_CAN bản "đơn gỡ hết" của lượt chưa từng gửi — không có gì phải báo
--      LOI       chưa gửi, het_luot_luc IS NOT NULL (hết lượt thử / bị từ chối /
--                thiếu dữ liệu / đơn đã gửi bị gỡ hết — cần người xem)
--      CHO_GUI   còn lại
-- Hàm SQL `dtqg_trang_thai` và Python `hang_cho.trang_thai_dong` là MỘT luật.
--
-- Idempotent ở Postgres: (clinic_id, visit_id, phien_ban) duy nhất — hai worker cùng
-- thấy đơn đổi thì một dòng thắng, dòng kia ON CONFLICT DO NOTHING; mã đơn duy
-- nhất trong clinic (36^7 tổ hợp cho 7 ký tự ngẫu nhiên — trùng thì INSERT hỏng,
-- vòng sau sinh mã khác).
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.dtqg_gui (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id      uuid NOT NULL REFERENCES public.visit (visit_id) ON DELETE RESTRICT,
    phien_ban     integer NOT NULL CHECK (phien_ban >= 1),
    -- QĐ 808 mục VII.1 / TT 26 PL I: 5 ký tự mã cơ sở + 7 ký tự ngẫu nhiên 0-9a-z
    -- + '-' + loại đơn (c thường, n gây nghiện, h hướng thần, y cổ truyền) = 14.
    ma_don        text NOT NULL CHECK (ma_don ~ '^[0-9A-Za-z]{5}[0-9a-z]{7}-[cnhy]$'),
    -- Gói đơn chuẩn của ClinicAI (không phải định dạng API) lúc vào hàng — để gửi
    -- lại đúng nội dung đã thấy và đối chiếu sau này.
    goi           jsonb NOT NULL,
    dau_van_tay   text NOT NULL CHECK (dau_van_tay ~ '^[0-9a-f]{64}$'),
    -- Mọi dòng thuốc đã gỡ ⇒ phiên bản này là "đơn rỗng" (không gửi được gì).
    la_huy        boolean NOT NULL DEFAULT false,
    tao_luc       timestamptz NOT NULL DEFAULT now(),
    -- Lần thử: số lần, lần kế tiếp, lỗi cuối (mã + câu ngắn, không dữ liệu khách).
    so_lan_thu    integer NOT NULL DEFAULT 0 CHECK (so_lan_thu >= 0),
    thu_lai_luc   timestamptz NOT NULL DEFAULT now(),
    loi_cuoi      text CHECK (loi_cuoi IS NULL OR length(loi_cuoi) <= 500),
    het_luot_luc  timestamptz,
    -- Gửi thành công: lúc nào, nhà cung cấp nào, hệ thống quốc gia trả gì.
    da_gui_luc    timestamptz,
    nha_cung_cap  text CHECK (nha_cung_cap IS NULL OR nha_cung_cap IN ('GIA_LAP', 'THAT')),
    ma_tra_ve     text CHECK (ma_tra_ve IS NULL OR length(ma_tra_ve) <= 200),
    CONSTRAINT uq_dtqg_gui_phien_ban UNIQUE (clinic_id, visit_id, phien_ban),
    CONSTRAINT uq_dtqg_gui_ma_don UNIQUE (clinic_id, ma_don),
    CONSTRAINT dtqg_gui_da_gui_du_dau_vet CHECK ((da_gui_luc IS NULL) = (nha_cung_cap IS NULL)),
    -- Đã gửi thì không "hết lượt"; đơn rỗng không bao giờ gửi được.
    CONSTRAINT dtqg_gui_mot_ket_cuc CHECK (da_gui_luc IS NULL OR het_luot_luc IS NULL),
    CONSTRAINT dtqg_gui_huy_khong_gui CHECK (NOT la_huy OR da_gui_luc IS NULL)
);
CREATE INDEX IF NOT EXISTS ix_dtqg_gui_cho
    ON public.dtqg_gui (clinic_id, thu_lai_luc)
    WHERE da_gui_luc IS NULL AND het_luot_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_dtqg_gui_luot
    ON public.dtqg_gui (clinic_id, visit_id, phien_ban DESC);

COMMENT ON TABLE public.dtqg_gui IS
'Hàng chờ gửi đơn lên Hệ thống đơn thuốc quốc gia (24/11/2026). Mỗi phiên bản nội dung đơn một dòng, một mã đơn; trạng thái tính bằng dtqg_trang_thai().';

-- Sự việc đã ghi không sửa: nội dung + khoá đứng yên; dòng đã gửi đứng yên hẳn;
-- chỉ được ghi thêm lần thử / kết cục. Không xoá.
CREATE OR REPLACE FUNCTION public.dtqg_gui_chi_di_tiep()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'dtqg_gui: không xoá' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.id, NEW.clinic_id, NEW.visit_id, NEW.phien_ban, NEW.ma_don, NEW.goi,
        NEW.dau_van_tay, NEW.la_huy, NEW.tao_luc)
       IS DISTINCT FROM
       (OLD.id, OLD.clinic_id, OLD.visit_id, OLD.phien_ban, OLD.ma_don, OLD.goi,
        OLD.dau_van_tay, OLD.la_huy, OLD.tao_luc)
       OR OLD.da_gui_luc IS NOT NULL
       OR OLD.het_luot_luc IS NOT NULL
       OR NEW.so_lan_thu < OLD.so_lan_thu THEN
        RAISE EXCEPTION 'dtqg_gui: sự việc đã ghi không sửa được'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_dtqg_gui_chi_di_tiep ON public.dtqg_gui;
CREATE TRIGGER trg_dtqg_gui_chi_di_tiep
    BEFORE UPDATE OR DELETE ON public.dtqg_gui
    FOR EACH ROW EXECUTE FUNCTION public.dtqg_gui_chi_di_tiep();

-- Trạng thái tính ra (một luật với `trang_thai_dong` trong
-- services/don_thuoc_quoc_gia/hang_cho.py — test so khớp).
CREATE OR REPLACE FUNCTION public.dtqg_trang_thai(g public.dtqg_gui)
RETURNS text LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN g.da_gui_luc IS NOT NULL THEN 'DA_GUI'
        WHEN EXISTS (SELECT 1 FROM public.dtqg_gui m
                      WHERE m.clinic_id = g.clinic_id AND m.visit_id = g.visit_id
                        AND m.phien_ban > g.phien_ban) THEN 'BI_THAY'
        WHEN g.la_huy AND NOT EXISTS (
                 SELECT 1 FROM public.dtqg_gui s
                  WHERE s.clinic_id = g.clinic_id AND s.visit_id = g.visit_id
                    AND s.phien_ban < g.phien_ban
                    AND s.da_gui_luc IS NOT NULL) THEN 'KHONG_CAN'
        WHEN g.het_luot_luc IS NOT NULL THEN 'LOI'
        ELSE 'CHO_GUI'
    END
$$;

-- ── Quyền + RLS (chỉ backend; không màn nào đọc thẳng) ──────────────────────
ALTER TABLE public.dtqg_gui ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtqg_gui_select_own_clinic ON public.dtqg_gui;
CREATE POLICY dtqg_gui_select_own_clinic ON public.dtqg_gui FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.dtqg_gui TO service_role;
