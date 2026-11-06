-- XÉT NGHIỆM ĐỐI TÁC — bản mẫu 05/11 (Tuyền chốt 8 chỗ lệch):
--   1. `doi_tac.tai_khoan_nhan_ck`: số tài khoản nhận chuyển khoản thu hộ của đối tác —
--      bàn XN hiện "Chuyển khoản vào: …" (máy chủ trả, không viết cứng ở màn).
--   2. Ảnh chuyển khoản thu hộ (không bắt buộc) — kế hoạch 4.4, chọn (b) BẢNG RIÊNG
--      `anh_chuyen_khoan_thu_ho`. Vì sao không (a): mọi chỗ đọc `anh_chuyen_khoan`
--      (anh_cua_cac_lan_thu, doc, go, payment_access_service) bám `cycle_id` và nằm
--      trong luồng quyền QUẦY THU — dòng cycle_id NULL sẽ phải rẽ nhánh ở cả 5 chỗ và
--      ảnh thu hộ lọt vào luồng két, trái câu chốt 1 (thu hộ là sổ riêng). Bảng riêng
--      giữ ĐÚNG bộ cột tệp của `anh_chuyen_khoan` để job day_tep dùng chung câu chọn lô.
-- Migration mới, không sửa migration cũ. Chạy lại được.

-- ── 1. Số tài khoản nhận CK của đối tác ────────────────────────────────────
ALTER TABLE public.doi_tac
    ADD COLUMN IF NOT EXISTS tai_khoan_nhan_ck text;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'doi_tac_tai_khoan_nhan_ck_do_dai') THEN
        ALTER TABLE public.doi_tac
            ADD CONSTRAINT doi_tac_tai_khoan_nhan_ck_do_dai
            CHECK (tai_khoan_nhan_ck IS NULL OR length(tai_khoan_nhan_ck) <= 200);
    END IF;
END $$;
COMMENT ON COLUMN public.doi_tac.tai_khoan_nhan_ck IS
'Tài khoản nhận chuyển khoản THU HỘ của đối tác (ngân hàng · số · tên) — bàn XN hiện khi khách trả CK. Chữ tự do, chỉ để hiển thị.';

-- ── 2. Ảnh chuyển khoản thu hộ ─────────────────────────────────────────────
-- FK ghép (thanh_toan_id, clinic_id) cần khoá duy nhất ghép ở bảng sổ.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'doi_tac_thanh_toan_id_clinic') THEN
        ALTER TABLE public.doi_tac_thanh_toan
            ADD CONSTRAINT doi_tac_thanh_toan_id_clinic UNIQUE (id, clinic_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.anh_chuyen_khoan_thu_ho (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id            uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    thanh_toan_id        uuid NOT NULL,
    khoa                 text NOT NULL UNIQUE,
    mime                 text NOT NULL,
    so_byte              bigint NOT NULL CHECK (so_byte > 0),
    sha256               text NOT NULL,
    tai_len_boi_staff_id uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    tai_len_luc          timestamptz NOT NULL DEFAULT now(),
    -- Gỡ ảnh nhầm: ẩn khỏi màn, giữ tệp + dòng (vết) — như anh_chuyen_khoan.
    go_luc               timestamptz,
    go_boi_staff_id      uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    -- Cùng bộ cột đẩy tệp với tep_ket_qua / anh_chuyen_khoan — day_tep đọc chung.
    vi_tri               text NOT NULL DEFAULT 'vps',
    da_day_luc           timestamptz,
    so_lan_day_loi       int NOT NULL DEFAULT 0,
    loi_day_cuoi         text,
    day_loi_luc          timestamptz,
    da_xoa_ban_vps_luc   timestamptz,
    da_don_tep_luc       timestamptz,
    CONSTRAINT anh_ck_thu_ho_thanh_toan_fkey
        FOREIGN KEY (thanh_toan_id, clinic_id)
        REFERENCES public.doi_tac_thanh_toan (id, clinic_id) ON DELETE RESTRICT,
    CONSTRAINT anh_ck_thu_ho_go_du_vet CHECK (
        (go_luc IS NULL) = (go_boi_staff_id IS NULL)),
    CONSTRAINT anh_ck_thu_ho_vi_tri_hop_le CHECK (
        vi_tri IN ('vps', 'cfs')
        AND so_lan_day_loi >= 0
        AND (vi_tri = 'cfs' OR (da_day_luc IS NULL AND da_xoa_ban_vps_luc IS NULL))
        AND (da_xoa_ban_vps_luc IS NULL OR da_day_luc IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_anh_ck_thu_ho_thanh_toan
    ON public.anh_chuyen_khoan_thu_ho (clinic_id, thanh_toan_id);
CREATE INDEX IF NOT EXISTS idx_anh_ck_thu_ho_cho_day
    ON public.anh_chuyen_khoan_thu_ho (tai_len_luc) WHERE vi_tri = 'vps';

COMMENT ON TABLE public.anh_chuyen_khoan_thu_ho IS
'Ảnh chuyển khoản của một khoản THU HỘ đối tác (05/11/2026, kế hoạch 4.4 phương án b). Sổ riêng — không nối payment_cycle. Ổ VPS trước → day-tep đẩy sang CFS. Gỡ = ẩn (go_luc), không xoá.';

ALTER TABLE public.anh_chuyen_khoan_thu_ho ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anh_chuyen_khoan_thu_ho_select_own_clinic
    ON public.anh_chuyen_khoan_thu_ho;
CREATE POLICY anh_chuyen_khoan_thu_ho_select_own_clinic ON public.anh_chuyen_khoan_thu_ho
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.anh_chuyen_khoan_thu_ho TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.anh_chuyen_khoan_thu_ho TO service_role;

-- Báo màn khi thêm / gỡ; việc đẩy tệp (vi_tri, đếm lỗi…) không làm màn tải lại.
DROP TRIGGER IF EXISTS trg_notify_anh_chuyen_khoan_thu_ho ON public.anh_chuyen_khoan_thu_ho;
CREATE TRIGGER trg_notify_anh_chuyen_khoan_thu_ho
    AFTER INSERT OR DELETE ON public.anh_chuyen_khoan_thu_ho
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
DROP TRIGGER IF EXISTS trg_anh_ck_thu_ho_bao_tin_khi_go ON public.anh_chuyen_khoan_thu_ho;
CREATE TRIGGER trg_anh_ck_thu_ho_bao_tin_khi_go
    AFTER UPDATE ON public.anh_chuyen_khoan_thu_ho
    FOR EACH ROW
    WHEN (OLD.go_luc IS DISTINCT FROM NEW.go_luc)
    EXECUTE FUNCTION public.notify_row_change();
