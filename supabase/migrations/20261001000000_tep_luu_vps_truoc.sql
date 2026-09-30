-- TẢI LÊN LƯU Ổ VPS TRƯỚC, ĐẨY SANG VIETTEL CFS SAU (Tuyền chốt 30/09/2026).
--
-- Trước migration này mọi tệp kết quả ghi THẲNG lên ổ mạng Viettel CFS
-- (`/mnt/viettel-cfs`). Ổ ấy chập chờn: 29/09 đọc còn 69KB/s, 105 lần kết nối
-- lại từ 16/09 — tải lên lúc ổ chậm là lượt tải hỏng, và đường đọc đứng theo.
--
-- Từ đây: tải lên ghi vào ổ của CHÍNH VPS (nhanh, không qua mạng), dòng mới
-- mang `vi_tri = 'vps'`. Container `day-tep` đẩy sang CFS khi phép đo báo ổ ổn
-- 2 lần liên tiếp, chép → fsync → ĐỌC LẠI tính sha256 so với `sha256` của dòng
-- + so `so_byte`, khớp mới đổi `vi_tri = 'cfs'`. Bản VPS giữ thêm 7 ngày để đọc
-- nhanh rồi xoá (hoặc sớm hơn khi ổ VPS vượt trần) — KHÔNG BAO GIỜ xoá tệp chưa
-- đẩy (`vi_tri = 'vps'` là bản DUY NHẤT của nó).
--
--   vi_tri               'vps' = bản duy nhất đang ở ổ VPS (chưa đẩy)
--                        'cfs' = đã có bản trên CFS (mọi dòng cũ: mặc định 'cfs')
--   da_day_luc           lúc đẩy sang CFS xong (đã kiểm sha256)
--   so_lan_day_loi       số lần đẩy hỏng liên tiếp (lùi dần theo số này)
--   loi_day_cuoi         lỗi gần nhất (để /ops + cảnh báo nói rõ vì sao)
--   day_loi_luc          lúc hỏng gần nhất — mốc tính lùi dần (thêm ngoài bản
--                        chốt: lùi dần cần biết lần hỏng gần nhất lúc nào, và
--                        giữ trong RAM thì khởi động lại là mất)
--   da_xoa_ban_vps_luc   đã xoá bản trên ổ VPS (tệp chỉ còn ở CFS)
--
-- Trigger V9 (`trg_tep_ket_qua_khoa_vet_xoa`) chỉ nghe các cột xoá mềm, nên
-- không chặn các cột này. CHECK dưới đây ép thứ tự hợp lệ ở Postgres, không
-- nhờ Python nhớ.

-- ── 1. Cột ──────────────────────────────────────────────────────────────────
ALTER TABLE public.tep_ket_qua
    ADD COLUMN IF NOT EXISTS vi_tri text NOT NULL DEFAULT 'cfs',
    ADD COLUMN IF NOT EXISTS da_day_luc timestamptz,
    ADD COLUMN IF NOT EXISTS so_lan_day_loi int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS loi_day_cuoi text,
    ADD COLUMN IF NOT EXISTS day_loi_luc timestamptz,
    ADD COLUMN IF NOT EXISTS da_xoa_ban_vps_luc timestamptz;

COMMENT ON COLUMN public.tep_ket_qua.vi_tri IS
    'vps = bản duy nhất ở ổ VPS, chờ đẩy; cfs = đã có bản trên Viettel CFS (01/10/2026).';
COMMENT ON COLUMN public.tep_ket_qua.da_day_luc IS
    'Lúc container day-tep đẩy xong sang CFS (đã đọc lại, sha256 + số byte khớp).';
COMMENT ON COLUMN public.tep_ket_qua.so_lan_day_loi IS
    'Số lần đẩy sang CFS hỏng (lùi dần theo số này; ≥5 → cảnh báo /ops).';
COMMENT ON COLUMN public.tep_ket_qua.da_xoa_ban_vps_luc IS
    'Đã xoá bản trên ổ VPS (7 ngày sau khi đẩy, hoặc sớm hơn khi ổ VPS vượt trần).';

-- ── 2. CHECK ────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.tep_ket_qua'::regclass
                      AND conname = 'tep_ket_qua_vi_tri_hop_le') THEN
        ALTER TABLE public.tep_ket_qua
            ADD CONSTRAINT tep_ket_qua_vi_tri_hop_le CHECK (
                vi_tri IN ('vps', 'cfs')
                AND so_lan_day_loi >= 0
                -- Chưa đẩy thì chưa thể có mốc đẩy, và bản VPS (bản duy nhất)
                -- không bao giờ được đánh dấu đã xoá.
                AND (vi_tri = 'cfs' OR (da_day_luc IS NULL
                                        AND da_xoa_ban_vps_luc IS NULL))
                -- Đã xoá bản VPS thì phải là tệp đã đẩy.
                AND (da_xoa_ban_vps_luc IS NULL OR da_day_luc IS NOT NULL)
            );
    END IF;
END $$;

-- ── 3. Index một phần: hàng chờ đẩy + việc dọn bản VPS ───────────────────────
CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_cho_day
    ON public.tep_ket_qua (tai_len_luc)
    WHERE vi_tri = 'vps';

CREATE INDEX IF NOT EXISTS idx_tep_ket_qua_ban_vps_con
    ON public.tep_ket_qua (da_day_luc)
    WHERE vi_tri = 'cfs' AND da_day_luc IS NOT NULL AND da_xoa_ban_vps_luc IS NULL;

-- ── 4. View hiệu lực: giữ nguyên nghĩa V9, chỉ thêm cột mới ──────────────────
-- `SELECT t.*` được Postgres mở thành danh sách cột LÚC TẠO view — cột mới của
-- bảng không tự vào view. Tạo lại (cột mới nối ở cuối nên CREATE OR REPLACE
-- được) để chỗ đọc thấy `vi_tri`.
CREATE OR REPLACE VIEW public.v_tep_ket_qua_hieu_luc
    WITH (security_invoker = true) AS
SELECT t.*
  FROM public.tep_ket_qua t
 WHERE t.da_xoa_luc IS NULL
   AND t.thu_hoi_luc IS NULL;

COMMENT ON VIEW public.v_tep_ket_qua_hieu_luc IS
    'Tệp kết quả còn hiệu lực: chưa xoá mềm, chưa thu hồi. Mọi chỗ ĐỌC tệp đọc view này (V9 30/09/2026).';

GRANT SELECT ON public.v_tep_ket_qua_hieu_luc TO authenticated;
GRANT SELECT ON public.v_tep_ket_qua_hieu_luc TO service_role;

-- ── 5. Đẩy tệp không làm mọi màn tải lại ────────────────────────────────────
-- `trg_notify_tep_ket_qua` bắn tin cho MỌI UPDATE → màn CSKH / phiếu khám đang
-- mở tải lại mỗi lần container day-tep đổi `vi_tri` hay đếm lần lỗi — một đợt
-- CFS hồi lại đẩy 50 tệp = 50 lần tải lại trên mọi tab, cho một thay đổi không
-- ai nhìn thấy. Tách: INSERT/DELETE bắn như cũ; UPDATE chỉ bắn khi có cột KHÁC
-- các cột đẩy tệp đổi.
DROP TRIGGER IF EXISTS trg_notify_tep_ket_qua ON public.tep_ket_qua;
CREATE TRIGGER trg_notify_tep_ket_qua
    AFTER INSERT OR DELETE ON public.tep_ket_qua
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

DROP TRIGGER IF EXISTS trg_tep_ket_qua_bao_tin_khi_sua ON public.tep_ket_qua;
CREATE TRIGGER trg_tep_ket_qua_bao_tin_khi_sua
    AFTER UPDATE ON public.tep_ket_qua
    FOR EACH ROW
    WHEN ((to_jsonb(OLD) - ARRAY['vi_tri', 'da_day_luc', 'so_lan_day_loi',
                                 'loi_day_cuoi', 'day_loi_luc',
                                 'da_xoa_ban_vps_luc'])
          IS DISTINCT FROM
          (to_jsonb(NEW) - ARRAY['vi_tri', 'da_day_luc', 'so_lan_day_loi',
                                 'loi_day_cuoi', 'day_loi_luc',
                                 'da_xoa_ban_vps_luc']))
    EXECUTE FUNCTION public.notify_row_change();
