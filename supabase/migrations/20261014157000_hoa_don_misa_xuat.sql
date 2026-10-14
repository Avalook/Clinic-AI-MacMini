-- ĐÁNH DẤU "ĐÃ XUẤT SANG MISA" (G5c · Tuyền 14/10/2026).
--
-- Kế toán tải file Excel rồi nhập vào MISA; hệ thống không tự biết. Sau khi tải,
-- kế toán đánh dấu khoảng ngày đó là "đã xuất". Máy chủ dựng lại danh sách hoá đơn
-- của khoảng và lưu MỖI hoá đơn một dòng cùng hai dấu vân tay (người mua / nội
-- dung) — sau này tính lại và so để biết hoá đơn nào CÓ THAY ĐỔI SAU KHI XUẤT.
-- Bỏ đánh dấu = đặt huy_luc (hoàn tác được, không xoá). Chạy lại được.

CREATE TABLE IF NOT EXISTS public.hoa_don_misa_xuat (
    id          uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id   uuid        NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    tu_ngay     date        NOT NULL,
    den_ngay    date        NOT NULL,
    co_so       text,
    loai        text,
    so_hoa_don  integer     NOT NULL DEFAULT 0 CHECK (so_hoa_don >= 0),
    tong_tien   bigint      NOT NULL DEFAULT 0,
    ghi_chu     text        NOT NULL DEFAULT '' CHECK (char_length(ghi_chu) <= 500),
    xuat_boi    uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    xuat_luc    timestamptz NOT NULL DEFAULT now(),
    huy_luc     timestamptz,
    huy_boi     uuid        REFERENCES public.staff (id) ON DELETE SET NULL,
    CONSTRAINT hoa_don_misa_xuat_khoang_ngay CHECK (den_ngay >= tu_ngay)
);
CREATE INDEX IF NOT EXISTS idx_hoa_don_misa_xuat_luc
    ON public.hoa_don_misa_xuat (clinic_id, xuat_luc DESC);
COMMENT ON TABLE public.hoa_don_misa_xuat IS
'Một lần kế toán đánh dấu "đã xuất sang MISA" cho khoảng ngày. Bỏ đánh dấu = huy_luc (G5c 14/10/2026).';

CREATE TABLE IF NOT EXISTS public.hoa_don_misa_xuat_dong (
    id               uuid   NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    clinic_id        uuid   NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    xuat_id          uuid   NOT NULL REFERENCES public.hoa_don_misa_xuat (id) ON DELETE CASCADE,
    -- Không khoá ngoại sang payment_cycle: dấu vết đã xuất phải còn dù phiếu bị dọn.
    payment_cycle_id uuid   NOT NULL,
    ma_phieu         text   NOT NULL DEFAULT '',
    tong             bigint NOT NULL DEFAULT 0,
    dau_nguoi_mua    text   NOT NULL,
    dau_noi_dung     text   NOT NULL,
    CONSTRAINT uq_hoa_don_misa_xuat_dong UNIQUE (xuat_id, payment_cycle_id)
);
CREATE INDEX IF NOT EXISTS idx_hoa_don_misa_xuat_dong_phieu
    ON public.hoa_don_misa_xuat_dong (clinic_id, payment_cycle_id);
COMMENT ON TABLE public.hoa_don_misa_xuat_dong IS
'Mỗi hoá đơn trong một lần xuất MISA + dấu vân tay lúc xuất để phát hiện thay đổi sau đó (G5c 14/10/2026).';

ALTER TABLE public.hoa_don_misa_xuat ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_misa_xuat_select_own_clinic ON public.hoa_don_misa_xuat;
CREATE POLICY hoa_don_misa_xuat_select_own_clinic ON public.hoa_don_misa_xuat
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.hoa_don_misa_xuat TO service_role;

ALTER TABLE public.hoa_don_misa_xuat_dong ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hoa_don_misa_xuat_dong_select_own_clinic ON public.hoa_don_misa_xuat_dong;
CREATE POLICY hoa_don_misa_xuat_dong_select_own_clinic ON public.hoa_don_misa_xuat_dong
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.hoa_don_misa_xuat_dong TO service_role;
