-- CHỌN BÁC SĨ TRONG PHÒNG NHIỀU BÁC SĨ (Tuyền chốt 30/09/2026).
--
-- "Phòng siêu âm 2 máy — nếu có đủ 2 bác sĩ ở hai máy thì lúc chọn dịch vụ ở
-- node thanh toán, chọn phòng siêu âm 2 máy rồi thì thêm cả lựa chọn các bác
-- sĩ ở ngày đó nữa, rất open, để không tách nhỏ phòng ra nữa. Một phòng có thể
-- có 2 bác sĩ, mỗi bác sĩ có điều dưỡng, thư ký riêng thì vẫn tách ra (theo
-- cặp)."
--
-- TỔNG QUÁT CHO MỌI PHÒNG, không viết cứng mã phòng trong luật:
--
--   1. `vi_tri_lam_viec.lan` — LÀN của vị trí trong phòng (1, 2, …; NULL = vị
--      trí không thuộc làn nào). Một làn = MỘT vị trí bác sĩ + các vị trí điều
--      dưỡng / thư ký cùng số. Ghép bằng DỮ LIỆU, không đoán theo tên / hậu tố
--      mã (T1_SA_BS ↔ T4_SA_BS1 không có quy luật chung nào đoán được). Vị trí
--      bác sĩ không ghi làn vẫn chọn được (mỗi vị trí là một lựa chọn), chỉ
--      không có điều dưỡng / thư ký đi kèm.
--      Điền cho Phòng siêu âm 2 máy (KN-SA1): BS 1 · ĐD 1 · TK 1 = làn 1;
--      BS 2 · ĐD 2 · TK 2 = làn 2 — theo mã vị trí, chỉ khi vị trí ĐANG thuộc
--      phòng KN-SA1 của cùng phòng khám.
--   2. `service_order.bac_si_lam_id` (+ `lan_lam`, ai / lúc chọn) — bác sĩ quầy
--      chọn cho chỉ định trong phòng của nó. Chỉ là LỰA CHỌN, không khoá: ai
--      trong phòng vẫn bắt đầu làm được (luật "mở"). Máy chủ kiểm bác sĩ được
--      chọn đang trực làn của phòng ấy hôm nay (Python — phụ thuộc giờ ca).
--   3. BẤT BIẾN ép ở Postgres (không để mỗi lệnh tự nhớ): lựa chọn bác sĩ gắn
--      với PHÒNG của chỉ định (phòng đã xếp, chưa xếp thì phòng dự kiến). Phòng
--      ấy đổi mà lệnh không tự ghi bác sĩ mới → trigger xoá lựa chọn cũ. Mọi
--      lối đổi phòng (xếp tay, dây H4, đổi phòng dự kiến, huỷ xếp, trưởng ca
--      chuyển khi đang làm, migration gộp phòng) đều đi qua đây.
--
-- CHẠY LẠI ĐƯỢC: ADD COLUMN IF NOT EXISTS, CREATE OR REPLACE, chỉ ghi dòng khác.

-- ── 1. Làn của vị trí ───────────────────────────────────────────────────────
ALTER TABLE public.vi_tri_lam_viec
    ADD COLUMN IF NOT EXISTS lan integer;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'vi_tri_lam_viec_lan_check') THEN
        ALTER TABLE public.vi_tri_lam_viec
            ADD CONSTRAINT vi_tri_lam_viec_lan_check
            CHECK (lan IS NULL OR lan BETWEEN 1 AND 20);
    END IF;
END
$$;

COMMENT ON COLUMN public.vi_tri_lam_viec.lan IS
'Làn trong phòng (30/09/2026): một vị trí BAC_SI + các vị trí ĐD/TK cùng số là một cặp làm việc. NULL = không thuộc làn. Quầy chọn bác sĩ theo làn khi phòng có ≥2 bác sĩ trực.';

-- Mỗi làn của một phòng có đúng MỘT vị trí bác sĩ — hai vị trí bác sĩ cùng làn
-- thì "khách của làn tôi" không còn nghĩa.
CREATE UNIQUE INDEX IF NOT EXISTS vi_tri_lam_viec_mot_bac_si_moi_lan
    ON public.vi_tri_lam_viec (clinic_id, room_id, lan)
    WHERE lan IS NOT NULL AND nhom_nghe = 'BAC_SI' AND is_active;

UPDATE public.vi_tri_lam_viec v
   SET lan = m.lan
  FROM (VALUES
        ('T1_SA_BS', 1), ('T1_SA_DD', 1), ('T1_SA_TK', 1),
        ('T4_SA_BS1', 2), ('T4_SA_DD1', 2), ('T4_SA_TK1', 2)
       ) AS m(code, lan),
       public.clinic_room r
 WHERE v.code = m.code
   AND r.clinic_id = v.clinic_id AND r.id = v.room_id AND r.code = 'KN-SA1'
   AND v.lan IS DISTINCT FROM m.lan;

-- ── 2. Bác sĩ được chọn trên chỉ định ───────────────────────────────────────
ALTER TABLE public.service_order
    ADD COLUMN IF NOT EXISTS bac_si_lam_id uuid
        REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS lan_lam integer,
    ADD COLUMN IF NOT EXISTS bac_si_lam_boi uuid
        REFERENCES public.staff(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS bac_si_lam_luc timestamptz;

COMMENT ON COLUMN public.service_order.bac_si_lam_id IS
'Bác sĩ quầy chọn trong phòng nhiều bác sĩ (30/09/2026). Chỉ là lựa chọn — không khoá ai bắt đầu làm. Đổi phòng → trigger xoá. Ghi qua lệnh xếp / đặt phòng (ServiceRoutingService), phát service.doctor_chosen.';
COMMENT ON COLUMN public.service_order.lan_lam IS
'Làn (vi_tri_lam_viec.lan) của bác sĩ được chọn lúc chọn — lọc "Khách của làn tôi" ở hàng chờ phòng. NULL = vị trí bác sĩ không ghi làn.';

-- Hàng chờ phòng lọc theo bác sĩ / làn của chỉ định.
CREATE INDEX IF NOT EXISTS idx_service_order_bac_si_lam
    ON public.service_order (clinic_id, bac_si_lam_id)
    WHERE bac_si_lam_id IS NOT NULL;

-- ── 3. Đổi phòng → bỏ lựa chọn bác sĩ ───────────────────────────────────────
-- "Phòng của chỉ định" = phòng đã xếp, chưa xếp thì phòng dự kiến. Lệnh nào
-- đổi phòng VÀ ghi bác sĩ mới trong cùng câu UPDATE thì giữ bác sĩ mới.
CREATE OR REPLACE FUNCTION public.service_order_bo_bac_si_khi_doi_phong()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
BEGIN
    IF coalesce(NEW.room_id, NEW.phong_du_kien_id)
           IS DISTINCT FROM coalesce(OLD.room_id, OLD.phong_du_kien_id)
       AND NEW.bac_si_lam_id IS NOT DISTINCT FROM OLD.bac_si_lam_id
       AND OLD.bac_si_lam_id IS NOT NULL THEN
        NEW.bac_si_lam_id := NULL;
        NEW.lan_lam := NULL;
        NEW.bac_si_lam_boi := NULL;
        NEW.bac_si_lam_luc := NULL;
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_service_order_bo_bac_si_khi_doi_phong
    ON public.service_order;
CREATE TRIGGER trg_service_order_bo_bac_si_khi_doi_phong
    BEFORE UPDATE OF room_id, phong_du_kien_id ON public.service_order
    FOR EACH ROW EXECUTE FUNCTION public.service_order_bo_bac_si_khi_doi_phong();
