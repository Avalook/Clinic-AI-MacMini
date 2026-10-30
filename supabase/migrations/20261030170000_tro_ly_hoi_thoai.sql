-- Trợ lý AI trả lời khách — hội thoại thử + từng tin (docs/KE-HOACH-TRO-LY-AI-KHACH.md, PR2).
--
-- Chỉ API (service_role) đọc/ghi; giao diện đi qua /api/v1/tro-ly. Nội dung là chữ
-- tự do nhân viên gõ đóng vai khách — có thể lỡ gõ thông tin thật, nên đã khai
-- che trong scripts/staging-che-du-lieu.sql.

CREATE TABLE IF NOT EXISTS public.tro_ly_hoi_thoai (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    -- Kênh tin vào. 'gia_lap' = màn /tro-ly-thu; zalo/messenger khi có adapter kênh.
    kenh          text NOT NULL DEFAULT 'gia_lap'
                  CHECK (kenh IN ('gia_lap', 'zalo', 'messenger')),
    tieu_de       text,
    tao_boi       uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    tao_luc       timestamptz NOT NULL DEFAULT now(),
    cap_nhat_luc  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tro_ly_hoi_thoai_clinic_cap_nhat
    ON public.tro_ly_hoi_thoai (clinic_id, cap_nhat_luc DESC);

CREATE TABLE IF NOT EXISTS public.tro_ly_tin (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hoi_thoai_id  uuid NOT NULL REFERENCES public.tro_ly_hoi_thoai (id) ON DELETE CASCADE,
    -- Thứ tự đúng như model đã thấy. UNIQUE là chốt khi hai lượt ghi cùng lúc.
    thu_tu        integer NOT NULL CHECK (thu_tu > 0),
    vai           text NOT NULL CHECK (vai IN ('khach', 'tro_ly', 'ket_qua_cong_cu')),
    noi_dung      text NOT NULL DEFAULT '',
    goi_cong_cu   jsonb NOT NULL DEFAULT '[]'::jsonb,
    ma_goi        text,
    -- Dòng nháp của một lượt (tin trợ lý cuối) — chỉ dòng này được duyệt.
    la_nhap       boolean NOT NULL DEFAULT false,
    meta          jsonb,
    duyet         text CHECK (duyet IN ('duyet', 'sua', 'chuyen')),
    noi_dung_gui  text,
    duyet_boi     uuid REFERENCES public.staff (id) ON DELETE SET NULL,
    duyet_luc     timestamptz,
    tao_luc       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (hoi_thoai_id, thu_tu),
    CONSTRAINT tro_ly_tin_duyet_chi_nhap CHECK (duyet IS NULL OR la_nhap),
    CONSTRAINT tro_ly_tin_ban_sua CHECK (
        (duyet = 'sua' AND noi_dung_gui IS NOT NULL)
        OR (duyet IS DISTINCT FROM 'sua' AND noi_dung_gui IS NULL)
    )
);

COMMENT ON TABLE public.tro_ly_hoi_thoai IS
'Hội thoại của trợ lý AI trả lời khách (kênh giả lập ở màn /tro-ly-thu).';
COMMENT ON TABLE public.tro_ly_tin IS
'Từng tin trong hội thoại trợ lý: tin khách, lượt gọi công cụ, kết quả công cụ, nháp. Nháp mang meta (model, công cụ, token) và trạng thái nhân viên duyệt.';

ALTER TABLE public.tro_ly_hoi_thoai ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tro_ly_hoi_thoai_service_read ON public.tro_ly_hoi_thoai;
CREATE POLICY tro_ly_hoi_thoai_service_read
    ON public.tro_ly_hoi_thoai
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));

ALTER TABLE public.tro_ly_tin ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tro_ly_tin_service_read ON public.tro_ly_tin;
CREATE POLICY tro_ly_tin_service_read
    ON public.tro_ly_tin
    FOR SELECT TO service_role
    USING (hoi_thoai_id IN (
        SELECT h.id FROM public.tro_ly_hoi_thoai h
         WHERE h.clinic_id IN (SELECT current_clinic_ids())
    ));

GRANT SELECT, INSERT, UPDATE ON public.tro_ly_hoi_thoai TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.tro_ly_tin TO service_role;

NOTIFY pgrst, 'reload schema';
