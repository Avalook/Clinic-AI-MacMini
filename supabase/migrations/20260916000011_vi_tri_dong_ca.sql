-- Ô ĐEN và khối NGHỈ của bảng lịch làm việc — vị trí KHÔNG làm ca ấy.
--
-- File Excel xếp lịch của PK Kim Ngưu tô đen những ô mà vị trí không hoạt động
-- (Phòng Nội tiết chỉ mở hôm có BS Thành; phòng siêu âm tầng 4 đóng cả Thứ Hai…)
-- và gộp một khối xám "NGHỈ" cho cả ca phòng khám nghỉ (Thứ Bảy 22/08 sáng,
-- chiều). Tuyền 16/09/2026: "bảng nó phải dạng y hệt như này".
--
-- VÌ SAO KHÔNG ĐỂ TRỐNG LÀ XONG. Ô trống và ô đen nói hai điều trái ngược:
--   trống = cần người mà CHƯA xếp  →  người xếp lịch phải đi tìm người
--   đen   = hôm ấy KHÔNG CẦN ai    →  đừng xếp vào
-- Gộp hai nghĩa vào một ô trắng là để người xếp lịch hoặc xếp thừa người vào
-- một phòng đóng cửa, hoặc bỏ sót một vị trí đang thiếu mà tưởng là đóng.
--
-- VÌ SAO LÀ BẢNG RIÊNG, không nhét vào `work_roster`: một dòng ở đó là "một
-- người đứng một chỗ" — lương, KPI, đặt lịch đều đọc nó như vậy. Một dòng
-- "không ai đứng" nằm lẫn vào là đợi ngày một câu COUNT(*) đếm nó thành người.

BEGIN;

CREATE TABLE IF NOT EXISTS public.vi_tri_dong_ca (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id),
    work_date   date NOT NULL,
    shift       text NOT NULL,
    station     text NOT NULL,
    -- DONG = ô đen (vị trí này không làm ca này).
    -- NGHI = cả ca phòng khám nghỉ (khối xám "NGHỈ").
    ly_do       text NOT NULL DEFAULT 'DONG',
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vi_tri_dong_ca_uq UNIQUE (clinic_id, work_date, shift, station),
    CONSTRAINT vi_tri_dong_ca_shift_check
        CHECK (shift = ANY (ARRAY['FULL', 'SANG', 'CHIEU', 'TOI'])),
    CONSTRAINT vi_tri_dong_ca_ly_do_check
        CHECK (ly_do = ANY (ARRAY['DONG', 'NGHI']))
);

CREATE INDEX IF NOT EXISTS idx_vi_tri_dong_ca_ngay
    ON public.vi_tri_dong_ca (clinic_id, work_date);

-- Đọc được từ trình duyệt như `work_roster` (các màn lịch đọc qua PostgREST),
-- nhưng CHỈ trong phòng khám của mình.
ALTER TABLE public.vi_tri_dong_ca ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vi_tri_dong_ca_select_own_clinic ON public.vi_tri_dong_ca;
CREATE POLICY vi_tri_dong_ca_select_own_clinic ON public.vi_tri_dong_ca
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.vi_tri_dong_ca TO authenticated;

-- ── Hai vị trí KHÔNG thuộc phòng nào ──────────────────────────────────────
--
-- Trong Excel, ô "Quầy tiếp đón" chỉ gộp HAI dòng Lễ tân + Thu ngân. "Đo chỉ số
-- sức khoẻ" và "Lấy mẫu (máu)" có cột Phòng để trống. Migration 000008 kéo tên
-- phòng từ dòng trên xuống nên gán nhầm chúng vào Quầy tiếp đón.
UPDATE public.vi_tri_lam_viec
   SET phong = NULL
 WHERE code IN ('T1_DOCHISO', 'T1_LAYMAU')
   AND phong IS NOT NULL;

COMMIT;
