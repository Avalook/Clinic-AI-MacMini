-- KẾT QUẢ ĐỐI TÁC QUA GMAIL — CHẶNG G1 (docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 1, 3 G1).
--
-- Đối tác (True Medicine, Greenlab, High Detect, Eurofins…) gửi PDF kết quả về Gmail phòng
-- khám. Máy chủ đọc CHỈ ĐỌC (G2), mọi thư vào Kho; thư sau mốc `gmail_tu_ngay` mới tự ghép (G3).
--
-- 1. `doi_tac.email_gui_ket_qua` — địa chỉ người gửi của đối tác (chữ thường, duy nhất/phòng khám).
-- 2. `doi_tac_dich_vu.ma_ben_doi_tac` — mã xét nghiệm đối tác ghi trong tên tệp (vd `HPV`), gỡ
--    "một khách hai việc". Chữ hoa, duy nhất trong một đối tác (dòng còn hoạt động).
-- 3. `xet_nghiem_cai_dat.gmail_tu_ngay` — NULL = chưa tự ghép thư nào (mọi thư "Lưu trữ").
-- 4. `drive_tep` nhận thêm nguồn GMAIL (dùng lại hàng ghép tay / Gán / Từ chối đã chạy):
--    - cột thư (`email_*`), mã đối tác trong tên tệp, gợi ý khách/việc cho Kho;
--    - BỘ CỘT ĐẨY TỆP giống `tep_ket_qua` (khoa, sha256, vi_tri, da_day_luc…): PDF Gmail lưu
--      ngay lúc nhận vào ổ VPS rồi `day_tep` đẩy sang CFS như mọi tệp khác — không thêm đường
--      đẩy thứ hai, không để PDF nằm mãi trên ổ VPS (4 đối tác ≈ vài GB, ổ VPS từng 89% 31/10).
--      Thay cho cột `vi_tri_tep` trong kế hoạch. Dòng DRIVE không lưu byte (đọc thẳng Drive) ⇒
--      các cột này NULL.
--    - lý do mới: LUU_TRU (thư trước mốc / mốc trống — chỉ nằm trong Kho, KHÔNG vào hàng ghép
--      tay), CHUA_LAY_MAU (khớp khách nhưng việc chưa bấm Lấy mẫu), CO_BAN_MOI (thư gửi lại).
-- 5. `drive_nhip` — một dòng mỗi (đối tác, nguồn); con trỏ nạp lịch sử Gmail.
-- 6. `tep_ket_qua.nguon` nhận 'GMAIL' (tờ tạo từ thư, G3).
--
-- Không BEGIN/COMMIT, chạy lại được. Không sửa migration cũ.

-- ── 1. doi_tac.email_gui_ket_qua ────────────────────────────────────────────
ALTER TABLE public.doi_tac ADD COLUMN IF NOT EXISTS email_gui_ket_qua text;
ALTER TABLE public.doi_tac DROP CONSTRAINT IF EXISTS doi_tac_email_gui_ket_qua_hop_le;
ALTER TABLE public.doi_tac ADD CONSTRAINT doi_tac_email_gui_ket_qua_hop_le CHECK (
    email_gui_ket_qua IS NULL
    OR (email_gui_ket_qua = lower(btrim(email_gui_ket_qua))
        AND length(email_gui_ket_qua) BETWEEN 6 AND 254
        AND email_gui_ket_qua ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'));
-- Hai đối tác cùng một địa chỉ ⇒ không biết thư của ai: DB từ chối (người lưu sau thua).
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_email_gui_ket_qua
    ON public.doi_tac (clinic_id, email_gui_ket_qua)
    WHERE email_gui_ket_qua IS NOT NULL;
COMMENT ON COLUMN public.doi_tac.email_gui_ket_qua IS
'Địa chỉ đối tác gửi thư kết quả (09/11/2026, Gmail G1). Chữ thường. Máy chủ chỉ đọc thư từ đúng địa chỉ này.';

-- ── 2. doi_tac_dich_vu.ma_ben_doi_tac ───────────────────────────────────────
ALTER TABLE public.doi_tac_dich_vu ADD COLUMN IF NOT EXISTS ma_ben_doi_tac text;
ALTER TABLE public.doi_tac_dich_vu DROP CONSTRAINT IF EXISTS doi_tac_dich_vu_ma_ben_doi_tac_hop_le;
ALTER TABLE public.doi_tac_dich_vu ADD CONSTRAINT doi_tac_dich_vu_ma_ben_doi_tac_hop_le CHECK (
    ma_ben_doi_tac IS NULL OR ma_ben_doi_tac ~ '^[A-Z0-9][A-Z0-9_.-]{0,39}$');
CREATE UNIQUE INDEX IF NOT EXISTS ux_doi_tac_dich_vu_ma_ben_doi_tac
    ON public.doi_tac_dich_vu (clinic_id, doi_tac_id, ma_ben_doi_tac)
    WHERE ma_ben_doi_tac IS NOT NULL AND ngung_luc IS NULL;
COMMENT ON COLUMN public.doi_tac_dich_vu.ma_ben_doi_tac IS
'Mã xét nghiệm đối tác ghi trong tên tệp kết quả (vd HPV, TQ) — gỡ khi một khách có hai việc chờ của cùng đối tác (Gmail G3).';

-- ── 3. xet_nghiem_cai_dat.gmail_tu_ngay ─────────────────────────────────────
ALTER TABLE public.xet_nghiem_cai_dat ADD COLUMN IF NOT EXISTS gmail_tu_ngay date;
COMMENT ON COLUMN public.xet_nghiem_cai_dat.gmail_tu_ngay IS
'Thư Gmail nhận TỪ ngày này (giờ VN) mới tự ghép. NULL (hoặc không có dòng) = chưa tự ghép thư nào: mọi thư vào Kho dạng Lưu trữ.';

-- ── 4. drive_tep: nguồn GMAIL ───────────────────────────────────────────────
ALTER TABLE public.drive_tep
    ADD COLUMN IF NOT EXISTS nguon                   text NOT NULL DEFAULT 'DRIVE',
    ADD COLUMN IF NOT EXISTS email_message_id        text,
    ADD COLUMN IF NOT EXISTS email_tieu_de           text,
    ADD COLUMN IF NOT EXISTS email_than              text,
    ADD COLUMN IF NOT EXISTS email_nhan_luc          timestamptz,
    ADD COLUMN IF NOT EXISTS ma_ben_doi_tac_tep      text,
    ADD COLUMN IF NOT EXISTS goi_y_order_id          uuid
        REFERENCES public.service_order (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS goi_y_clinic_patient_id uuid
        REFERENCES public.patient (clinic_patient_id) ON DELETE RESTRICT,
    -- Cùng bộ cột đẩy tệp với tep_ket_qua / anh_chuyen_khoan — day_tep đọc chung.
    ADD COLUMN IF NOT EXISTS khoa                    text,
    ADD COLUMN IF NOT EXISTS sha256                  text,
    ADD COLUMN IF NOT EXISTS vi_tri                  text,
    ADD COLUMN IF NOT EXISTS tai_len_luc             timestamptz,
    ADD COLUMN IF NOT EXISTS da_day_luc              timestamptz,
    ADD COLUMN IF NOT EXISTS so_lan_day_loi          int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS loi_day_cuoi            text,
    ADD COLUMN IF NOT EXISTS day_loi_luc             timestamptz,
    ADD COLUMN IF NOT EXISTS da_xoa_ban_vps_luc      timestamptz,
    ADD COLUMN IF NOT EXISTS da_don_tep_luc          timestamptz;

-- file_id Gmail = `gmail:<messageId>:<partId>` (có dấu ':') — nới CHECK theo nguồn.
ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_file_id_check;
ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_file_id_hop_le;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_file_id_hop_le CHECK (
    (nguon = 'DRIVE' AND file_id ~ '^[A-Za-z0-9_-]{10,200}$')
    OR (nguon = 'GMAIL' AND file_id ~ '^gmail:[A-Za-z0-9_-]{6,64}:[A-Za-z0-9._-]{1,64}$'));

ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_nguon_hop_le;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_nguon_hop_le CHECK (
    nguon IN ('DRIVE', 'GMAIL')
    AND (email_tieu_de IS NULL OR length(email_tieu_de) <= 500)
    AND (email_than IS NULL OR length(email_than) <= 2000)
    AND (ma_ben_doi_tac_tep IS NULL OR length(ma_ben_doi_tac_tep) <= 40)
    AND (
        -- Gmail: luôn có thư + byte đã lưu (không gọi lại Gmail để xem).
        -- `IS NOT NULL` trước mỗi `~`: NULL ~ '…' ra NULL và CHECK coi NULL là ĐẠT.
        (nguon = 'GMAIL'
            AND email_message_id IS NOT NULL
            AND email_message_id ~ '^[A-Za-z0-9_-]{6,64}$'
            AND starts_with(file_id, 'gmail:' || email_message_id || ':')
            AND email_nhan_luc IS NOT NULL
            AND khoa IS NOT NULL
            AND sha256 IS NOT NULL AND sha256 ~ '^[0-9a-f]{64}$'
            AND vi_tri IS NOT NULL AND tai_len_luc IS NOT NULL
            AND so_byte IS NOT NULL AND so_byte > 0)
        -- Drive: đọc thẳng Drive, không cột thư, không byte lưu.
        OR (nguon = 'DRIVE'
            AND email_message_id IS NULL AND email_tieu_de IS NULL AND email_than IS NULL
            AND email_nhan_luc IS NULL AND ma_ben_doi_tac_tep IS NULL
            AND khoa IS NULL AND sha256 IS NULL AND vi_tri IS NULL)));

ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_vi_tri_hop_le;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_vi_tri_hop_le CHECK (
    vi_tri IS NULL
    OR (vi_tri IN ('vps', 'cfs')
        AND so_lan_day_loi >= 0
        AND (vi_tri = 'cfs' OR (da_day_luc IS NULL AND da_xoa_ban_vps_luc IS NULL))
        AND (da_xoa_ban_vps_luc IS NULL OR da_day_luc IS NOT NULL)));

CREATE UNIQUE INDEX IF NOT EXISTS ux_drive_tep_khoa
    ON public.drive_tep (khoa) WHERE khoa IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_drive_tep_cho_day
    ON public.drive_tep (tai_len_luc) WHERE vi_tri = 'vps';
-- Kho email: theo người gửi, mới trước.
CREATE INDEX IF NOT EXISTS ix_drive_tep_kho_email
    ON public.drive_tep (clinic_id, doi_tac_id, email_nhan_luc DESC)
    WHERE nguon = 'GMAIL';

-- Lý do chờ: thêm LUU_TRU / CHUA_LAY_MAU / CO_BAN_MOI (giữ đủ 10 mã đã có).
ALTER TABLE public.drive_tep DROP CONSTRAINT IF EXISTS drive_tep_ly_do_cho_check;
ALTER TABLE public.drive_tep ADD CONSTRAINT drive_tep_ly_do_cho_check CHECK (
    ly_do_cho IS NULL OR ly_do_cho IN (
        'KHONG_MA', 'SAI_SO_KIEM', 'NHIEU_MA', 'KHONG_THAY_MAU', 'SAI_DOI_TAC',
        'ONG_NHIEU_VIEC', 'LOI_TEP', 'KHONG_DOC_DUOC', 'KHONG_KHOP_KHACH',
        'NHIEU_KHACH', 'LUU_TRU', 'CHUA_LAY_MAU', 'CO_BAN_MOI'));

-- Hàng ghép tay không gồm thư Lưu trữ (chỉ xem ở Kho) — chỉ mục theo đúng điều kiện mới.
DROP INDEX IF EXISTS public.ix_drive_tep_cho;
CREATE INDEX IF NOT EXISTS ix_drive_tep_cho
    ON public.drive_tep (clinic_id, nhan_luc DESC)
    WHERE tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL
      AND ly_do_cho IS DISTINCT FROM 'LUU_TRU';

-- Sự việc không xoá, không sửa. Được đi tiếp: ghép / từ chối / gợi ý / xét lại lý do (G3).
-- Cột ĐẨY TỆP (day_tep) luôn sửa được — kể cả sau khi từ chối, để tệp vẫn lên CFS và dọn ổ VPS.
CREATE OR REPLACE FUNCTION public.drive_tep_chi_di_tiep()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    cot_day CONSTANT text[] := ARRAY['vi_tri', 'da_day_luc', 'so_lan_day_loi', 'loi_day_cuoi',
                                     'day_loi_luc', 'da_xoa_ban_vps_luc', 'da_don_tep_luc'];
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'drive_tep: không xoá' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (to_jsonb(NEW) - cot_day) = (to_jsonb(OLD) - cot_day) THEN
        RETURN NEW;   -- chỉ day_tep đổi cột đẩy
    END IF;
    IF (NEW.clinic_id, NEW.doi_tac_id, NEW.file_id, NEW.md5, NEW.ten, NEW.nhan_luc,
        NEW.drive_tao_luc, NEW.drive_nguoi_tai, NEW.nguon, NEW.email_message_id,
        NEW.email_tieu_de, NEW.email_than, NEW.email_nhan_luc, NEW.ma_ben_doi_tac_tep,
        NEW.khoa, NEW.sha256, NEW.so_byte, NEW.tai_len_luc)
       IS DISTINCT FROM
       (OLD.clinic_id, OLD.doi_tac_id, OLD.file_id, OLD.md5, OLD.ten, OLD.nhan_luc,
        OLD.drive_tao_luc, OLD.drive_nguoi_tai, OLD.nguon, OLD.email_message_id,
        OLD.email_tieu_de, OLD.email_than, OLD.email_nhan_luc, OLD.ma_ben_doi_tac_tep,
        OLD.khoa, OLD.sha256, OLD.so_byte, OLD.tai_len_luc)
       OR (OLD.tu_choi_luc IS NOT NULL)
       OR (OLD.tep_ket_qua_id IS NOT NULL
           AND NEW.tep_ket_qua_id IS DISTINCT FROM OLD.tep_ket_qua_id
           AND NOT EXISTS (SELECT 1 FROM public.tep_ket_qua k
                            WHERE k.id = OLD.tep_ket_qua_id
                              AND (k.da_xoa_luc IS NOT NULL
                                   OR k.xac_nhan_trang_thai IN ('THU_HOI', 'TU_CHOI')))) THEN
        RAISE EXCEPTION 'drive_tep: sự việc đã ghi không sửa được'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

COMMENT ON TABLE public.drive_tep IS
'Tệp kết quả đối tác tự về: Google Drive (05/11/2026) hoặc Gmail (09/11/2026, nguon=GMAIL, byte lưu ở khoa/vi_tri). Mỗi (file_id, md5) một dòng. Trạng thái tính từ tep_ket_qua_id / tu_choi_luc / ly_do_cho.';

-- ── 5. drive_nhip: một dòng mỗi (đối tác, nguồn) ────────────────────────────
ALTER TABLE public.drive_nhip
    ADD COLUMN IF NOT EXISTS nguon           text NOT NULL DEFAULT 'DRIVE',
    ADD COLUMN IF NOT EXISTS con_tro_lich_su text,
    ADD COLUMN IF NOT EXISTS so_lich_su_con  integer;
ALTER TABLE public.drive_nhip DROP CONSTRAINT IF EXISTS drive_nhip_nguon_hop_le;
ALTER TABLE public.drive_nhip ADD CONSTRAINT drive_nhip_nguon_hop_le CHECK (
    nguon IN ('DRIVE', 'GMAIL')
    AND (con_tro_lich_su IS NULL OR length(con_tro_lich_su) <= 500)
    AND (so_lich_su_con IS NULL OR so_lich_su_con >= 0)
    AND (nguon = 'GMAIL' OR (con_tro_lich_su IS NULL AND so_lich_su_con IS NULL)));
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
         WHERE c.conname = 'drive_nhip_pkey'
           AND c.conrelid = 'public.drive_nhip'::regclass
           AND array_length(c.conkey, 1) = 3) THEN
        ALTER TABLE public.drive_nhip DROP CONSTRAINT IF EXISTS drive_nhip_pkey;
        ALTER TABLE public.drive_nhip ADD CONSTRAINT drive_nhip_pkey
            PRIMARY KEY (clinic_id, doi_tac_id, nguon);
    END IF;
END $$;
COMMENT ON TABLE public.drive_nhip IS
'Nhịp quét kết quả tự về theo (đối tác, nguồn DRIVE/GMAIL) (05/11, 09/11/2026). Quá 1 giờ không có ok_cuoi ⇒ canh_bao. Gmail giữ con trỏ nạp thư cũ.';

-- ── 6. tep_ket_qua.nguon nhận GMAIL ─────────────────────────────────────────
ALTER TABLE public.tep_ket_qua DROP CONSTRAINT IF EXISTS tep_ket_qua_nguon_hop_le;
ALTER TABLE public.tep_ket_qua ADD CONSTRAINT tep_ket_qua_nguon_hop_le CHECK (
    nguon IN ('TAI_LEN', 'DRIVE', 'GMAIL')
    AND (drive_nguoi_tai IS NULL OR length(drive_nguoi_tai) <= 200)
    -- Không ai tải ⇒ phải là tệp tự về (Drive / Gmail); tải tay luôn có người.
    AND (tai_len_boi_staff_id IS NOT NULL OR nguon IN ('DRIVE', 'GMAIL')));
