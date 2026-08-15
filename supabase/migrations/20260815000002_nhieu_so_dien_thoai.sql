-- Một bệnh nhân, nhiều số điện thoại (Tuyền 15/08/2026).
--
-- Khách dùng 2–3 số là chuyện thường: gọi từ số mới trong khi hồ sơ giữ số cũ.
-- Trước bản này mỗi hồ sơ chỉ có đúng hai ô (`phone_primary`, `phone_secondary`
-- — số người nhà), nên số thứ ba KHÔNG CÓ CHỖ GHI, và người trực hoặc ghi đè
-- số cũ (mất lịch sử liên lạc) hoặc tạo hồ sơ mới (tách đôi bệnh án).
--
-- THIẾT KẾ HAI TẦNG:
--
--   1. `patient_sdt_them` — nguồn sự thật cho các số THÊM, mỗi dòng một số,
--      biết ai thêm và lúc nào. Hai cột cũ giữ nguyên vai "số chính thức trên
--      hồ sơ" — không dời dữ liệu, không sửa form cũ.
--   2. `patient.sdt_tim_kiem` — cột GỘP MỌI SỐ (chính + người nhà + thêm) do
--      trigger nuôi. Vì sao gộp: mọi đường tìm kiếm hiện có đều là một câu
--      `or(...ilike...)` phẳng của PostgREST trên chính bảng patient — bắt
--      từng đường join sang bảng con là mỗi đường một kiểu và sớm muộn lệch
--      nhau. Đổi MỘT cột trong câu or() thì "tra số nào cũng ra" đúng ở mọi
--      màn bằng cùng một cách.

CREATE TABLE IF NOT EXISTS public.patient_sdt_them (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    clinic_patient_id uuid NOT NULL
        REFERENCES public.patient(clinic_patient_id) ON DELETE CASCADE,
    -- Chuẩn hoá 10 số bắt đầu bằng 0 NGAY TỪ RÀNG BUỘC — cùng dạng mà
    -- normalize_vn_phone của backend trả ra. Một số "+84 90..." lọt vào đây
    -- là cột tìm kiếm chứa một dạng mà không ai gõ để tra.
    so_dien_thoai text NOT NULL CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
    -- CHINH = số của chính khách · NGUOI_NHA = số người nhà (chồng/mẹ…).
    -- Hai loại vẽ ở hai chỗ khác nhau trên hồ sơ, dưới đúng dòng số cùng loại.
    loai text NOT NULL DEFAULT 'CHINH' CHECK (loai IN ('CHINH', 'NGUOI_NHA')),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by_staff_id uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    -- Một số ghi hai lần cho cùng một khách là bấm trùng, không phải dữ liệu.
    -- KHÔNG unique toàn cục: hai mẹ con dùng chung một số là hợp lệ (cùng
    -- triết lý với phone_primary xưa nay — cảnh báo, không chặn).
    UNIQUE (clinic_patient_id, so_dien_thoai)
);

CREATE INDEX IF NOT EXISTS idx_patient_sdt_them_benh_nhan
    ON public.patient_sdt_them (clinic_patient_id);
-- Bất biến của multi_tenant_foundation: mọi bảng tenant phải có một chỉ mục
-- DẪN ĐẦU bằng clinic_id — mọi truy vấn thật đều lọc phòng khám trước.
CREATE INDEX IF NOT EXISTS idx_patient_sdt_them_clinic_so
    ON public.patient_sdt_them (clinic_id, so_dien_thoai);

ALTER TABLE public.patient_sdt_them ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'patient_sdt_them'
           AND policyname = 'patient_sdt_them_select_own_clinic'
    ) THEN
        CREATE POLICY patient_sdt_them_select_own_clinic
            ON public.patient_sdt_them FOR SELECT TO authenticated
            USING (clinic_id IN (SELECT public.current_clinic_ids()));
    END IF;
END $$;

-- Chỉ đọc qua PostgREST; mọi đường GHI đi qua backend (asyncpg, tự khoá
-- clinic_id — tenant-scope audit canh). Không mở INSERT cho authenticated.
GRANT SELECT ON public.patient_sdt_them TO authenticated;

-- ── Cột tìm kiếm gộp ───────────────────────────────────────────────────────

ALTER TABLE public.patient
    ADD COLUMN IF NOT EXISTS sdt_tim_kiem text;

-- Một công thức, ba nơi gọi (trigger patient, trigger bảng con, backfill) —
-- tách thành hàm để ba nơi không bao giờ tính ba kiểu.
CREATE OR REPLACE FUNCTION public.tinh_sdt_tim_kiem(
    p_benh_nhan uuid, p_chinh text, p_nguoi_nha text
) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT nullif(concat_ws(' ',
        p_chinh,
        p_nguoi_nha,
        (SELECT string_agg(t.so_dien_thoai, ' ' ORDER BY t.created_at)
           FROM public.patient_sdt_them t
          WHERE t.clinic_patient_id = p_benh_nhan)
    ), '')
$$;

-- BEFORE trên patient: mọi INSERT/UPDATE tự làm tươi cột gộp — kể cả cú
-- UPDATE "chạm cho tươi" từ trigger của bảng con bên dưới.
CREATE OR REPLACE FUNCTION public.patient_lam_tuoi_sdt()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.sdt_tim_kiem := public.tinh_sdt_tim_kiem(
        NEW.clinic_patient_id, NEW.phone_primary, NEW.phone_secondary);
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_patient_sdt_tim_kiem ON public.patient;
CREATE TRIGGER trg_patient_sdt_tim_kiem
    BEFORE INSERT OR UPDATE ON public.patient
    FOR EACH ROW EXECUTE FUNCTION public.patient_lam_tuoi_sdt();

-- AFTER trên bảng con: thêm/sửa/xoá một số là chạm hồ sơ mẹ cho trigger trên
-- tính lại. UPDATE rỗng (SET clinic_patient_id = chính nó) là đủ để BEFORE
-- trigger chạy — không chép công thức lần hai ở đây.
CREATE OR REPLACE FUNCTION public.sdt_them_lam_tuoi_patient()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    ben uuid := COALESCE(NEW.clinic_patient_id, OLD.clinic_patient_id);
BEGIN
    UPDATE public.patient SET clinic_patient_id = clinic_patient_id
     WHERE clinic_patient_id = ben;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS trg_sdt_them_lam_tuoi ON public.patient_sdt_them;
CREATE TRIGGER trg_sdt_them_lam_tuoi
    AFTER INSERT OR UPDATE OR DELETE ON public.patient_sdt_them
    FOR EACH ROW EXECUTE FUNCTION public.sdt_them_lam_tuoi_patient();

-- Backfill: hồ sơ cũ cũng tra được bằng cột mới ngay từ giây đầu.
UPDATE public.patient
   SET sdt_tim_kiem = public.tinh_sdt_tim_kiem(
        clinic_patient_id, phone_primary, phone_secondary)
 WHERE sdt_tim_kiem IS DISTINCT FROM public.tinh_sdt_tim_kiem(
        clinic_patient_id, phone_primary, phone_secondary);
