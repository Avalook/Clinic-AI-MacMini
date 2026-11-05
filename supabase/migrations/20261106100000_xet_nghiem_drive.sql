-- XÉT NGHIỆM ĐỐI TÁC — CHẶNG 4: KẾT QUẢ TỰ VỀ TỪ GOOGLE DRIVE (kế hoạch
-- docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md chặng 4 + 4.7, Tuyền duyệt 05/11/2026).
--
-- 1. `tep_ket_qua`: tệp do máy quét Drive chép về KHÔNG có nhân viên tải
--    (`tai_len_boi_staff_id` NULL) — đổi lại phải ghi `nguon = 'DRIVE'`. Tên người
--    thả tệp trên Drive (nếu Drive cho biết) chụp vào `drive_nguoi_tai`, chỉ để hiện.
--    Mọi chỗ đọc cột người tải đã là LEFT JOIN staff (soát 05/11, 22 chỗ).
-- 2. `drive_tep` — mỗi (tệp Drive, md5) một dòng: SỰ VIỆC (ai thả, lúc nào, ghép vào
--    tờ nào, ai ghép/từ chối, vì sao chờ ghép tay). Trạng thái TÍNH RA từ các cột này
--    (luật thiết kế 3), không lưu chữ trạng thái. Cùng file_id, md5 khác ⇒ bản mới.
-- 3. `drive_nhip` — mỗi đối tác một dòng: lần quét cuối, lỗi cuối (đèn nhịp, canh_bao).
--
-- Chạy lại được.

-- ── 1. tep_ket_qua: nguồn Drive ──────────────────────────────────────────────
ALTER TABLE public.tep_ket_qua
    ADD COLUMN IF NOT EXISTS nguon text NOT NULL DEFAULT 'TAI_LEN',
    ADD COLUMN IF NOT EXISTS drive_nguoi_tai text;
ALTER TABLE public.tep_ket_qua ALTER COLUMN tai_len_boi_staff_id DROP NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tep_ket_qua_nguon_hop_le') THEN
        ALTER TABLE public.tep_ket_qua ADD CONSTRAINT tep_ket_qua_nguon_hop_le CHECK (
            nguon IN ('TAI_LEN', 'DRIVE')
            AND (drive_nguoi_tai IS NULL OR length(drive_nguoi_tai) <= 200)
            -- Không ai tải ⇒ phải là Drive; tải tay luôn có người.
            AND (tai_len_boi_staff_id IS NOT NULL OR nguon = 'DRIVE'));
    END IF;
END $$;

-- ── 2. drive_tep ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drive_tep (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    doi_tac_id       uuid NOT NULL,
    file_id          text NOT NULL CHECK (file_id ~ '^[A-Za-z0-9_-]{10,200}$'),
    md5              text NOT NULL CHECK (md5 ~ '^[0-9a-f]{32}$'),
    ten              text NOT NULL CHECK (length(ten) BETWEEN 1 AND 300),
    mime             text CHECK (mime IS NULL OR length(mime) <= 200),
    so_byte          bigint CHECK (so_byte IS NULL OR so_byte >= 0),
    drive_tao_luc    timestamptz,
    drive_nguoi_tai  text CHECK (drive_nguoi_tai IS NULL OR length(drive_nguoi_tai) <= 200),
    nhan_luc         timestamptz NOT NULL DEFAULT now(),
    -- Vì sao không tự ghép. NULL = đã tự ghép.
    ly_do_cho        text CHECK (ly_do_cho IS NULL OR ly_do_cho IN (
                         'KHONG_MA', 'SAI_SO_KIEM', 'NHIEU_MA', 'KHONG_THAY_MAU',
                         'SAI_DOI_TAC', 'ONG_NHIEU_VIEC', 'LOI_TEP')),
    -- Ghép (tự động: ghep_boi NULL) — tờ kết quả đã tạo.
    tep_ket_qua_id   uuid,
    ghep_luc         timestamptz,
    ghep_boi         uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    -- Từ chối tệp (nhớ theo (file_id, md5) để lượt quét sau bỏ qua).
    tu_choi_luc      timestamptz,
    tu_choi_boi      uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    ly_do_tu_choi    text,
    CONSTRAINT drive_tep_doi_tac_fk FOREIGN KEY (doi_tac_id, clinic_id)
        REFERENCES public.doi_tac (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT drive_tep_tep_fk FOREIGN KEY (tep_ket_qua_id)
        REFERENCES public.tep_ket_qua (id) ON DELETE RESTRICT,
    CONSTRAINT drive_tep_ghep_dau_vet CHECK (
        (tep_ket_qua_id IS NULL) = (ghep_luc IS NULL)),
    CONSTRAINT drive_tep_tu_choi_dau_vet CHECK (
        (tu_choi_luc IS NULL AND tu_choi_boi IS NULL AND ly_do_tu_choi IS NULL)
        OR (tu_choi_luc IS NOT NULL AND tu_choi_boi IS NOT NULL
            AND length(btrim(ly_do_tu_choi)) BETWEEN 3 AND 500)),
    CONSTRAINT drive_tep_mot_ket_cuc CHECK (tep_ket_qua_id IS NULL OR tu_choi_luc IS NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_drive_tep_ban
    ON public.drive_tep (clinic_id, file_id, md5);
CREATE INDEX IF NOT EXISTS ix_drive_tep_cho
    ON public.drive_tep (clinic_id, nhan_luc DESC)
    WHERE tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL;

COMMENT ON TABLE public.drive_tep IS
'Tệp kết quả đối tác thả lên Google Drive (05/11/2026, chặng 4). Mỗi (file_id, md5) một dòng. Trạng thái tính từ tep_ket_qua_id / tu_choi_luc / ly_do_cho.';

-- Sự việc không xoá; dòng chỉ đi tiếp (ghép hoặc từ chối). Trỏ sang tờ khác chỉ khi
-- tờ cũ đã thu hồi / từ chối / xoá ("gán sang" khách đúng).
CREATE OR REPLACE FUNCTION public.drive_tep_chi_di_tiep()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'drive_tep: không xoá' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.clinic_id, NEW.doi_tac_id, NEW.file_id, NEW.md5, NEW.ten, NEW.nhan_luc,
        NEW.drive_tao_luc, NEW.drive_nguoi_tai)
       IS DISTINCT FROM
       (OLD.clinic_id, OLD.doi_tac_id, OLD.file_id, OLD.md5, OLD.ten, OLD.nhan_luc,
        OLD.drive_tao_luc, OLD.drive_nguoi_tai)
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
DROP TRIGGER IF EXISTS trg_drive_tep_chi_di_tiep ON public.drive_tep;
CREATE TRIGGER trg_drive_tep_chi_di_tiep
    BEFORE UPDATE OR DELETE ON public.drive_tep
    FOR EACH ROW EXECUTE FUNCTION public.drive_tep_chi_di_tiep();

-- ── 3. drive_nhip ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drive_nhip (
    clinic_id       uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    doi_tac_id      uuid NOT NULL,
    lan_quet_cuoi   timestamptz NOT NULL,
    ok_cuoi         timestamptz,
    loi_cuoi        text CHECK (loi_cuoi IS NULL OR length(loi_cuoi) <= 500),
    so_tep_cuoi     integer NOT NULL DEFAULT 0 CHECK (so_tep_cuoi >= 0),
    PRIMARY KEY (clinic_id, doi_tac_id),
    CONSTRAINT drive_nhip_doi_tac_fk FOREIGN KEY (doi_tac_id, clinic_id)
        REFERENCES public.doi_tac (id, clinic_id) ON DELETE RESTRICT
);
COMMENT ON TABLE public.drive_nhip IS
'Nhịp quét Drive theo đối tác (05/11/2026). Quá 1 giờ không có ok_cuoi ⇒ canh_bao cho quản lý.';

-- ── Quyền đọc + RLS + báo tin ───────────────────────────────────────────────
DO $$
DECLARE b text;
BEGIN
    FOREACH b IN ARRAY ARRAY['drive_tep', 'drive_nhip'] LOOP
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
