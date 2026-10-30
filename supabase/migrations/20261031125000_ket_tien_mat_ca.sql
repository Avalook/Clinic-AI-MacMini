-- KIỂM KÊ TIỀN MẶT ĐẦU CA – CUỐI CA (31/10/2026).
--
-- Trước: "Chốt ca" chỉ có ô ghi chú tự do ("két đủ") — không ai biết két đầu ca
-- có bao nhiêu, cuối ca đếm được bao nhiêu, lệch bao nhiêu và vì sao.
-- (Khác `kiem_ke_ca` — kiểm kê HÀNG thuốc / vật tư.)
--
-- `ket_tien_mat_ca` — MỘT dòng cho mỗi (phòng khám, cơ sở, ngày, ca), cùng khoá
-- với chốt ca:
--   * đầu ca: `quy_dau` (tổng; hoặc đếm theo mệnh giá `quy_dau_dem` — tổng phải
--     khớp bảng đếm, Postgres ép bằng `tong_to_tien`);
--   * cuối ca: `dem_cuoi` (+ `dem_cuoi_dem`), `thu_tien_mat` = tiền mặt THỰC THU
--     trong ca (thu − huỷ − hoàn tiền mặt, đúng số của báo cáo cuối ca) chụp lúc
--     đếm, `du_kien` = quỹ đầu + thu_tien_mat, `lech` = đếm − dự kiến. Lệch ≠ 0
--     thì bắt lý do. Người nhận bàn giao tuỳ chọn.
--   * Mở lại sau khi đếm (bắt lý do) = xoá phần cuối ca để đếm lại; sửa quỹ đầu
--     khi đã đếm cuối thì phải mở lại trước. Không xoá dòng.
-- `ket_tien_mat_ca_lich_su` — sổ CHỈ THÊM mọi lần ghi (vết: ai, lúc nào, lý do,
-- bản chụp dòng sau khi ghi).
--
-- Chạy lại được.

-- Tổng tiền của một bảng đếm {"500000": số tờ, …}. Mệnh giá lạ / số tờ âm / rác
-- → -1 (CHECK so với tổng sẽ hỏng — không để NULL lọt qua CHECK).
CREATE OR REPLACE FUNCTION public.tong_to_tien(p jsonb)
RETURNS bigint LANGUAGE sql IMMUTABLE AS $fn$
    SELECT CASE
        WHEN jsonb_typeof(p) <> 'object' THEN -1
        WHEN EXISTS (
            SELECT 1 FROM jsonb_each(p) e
             WHERE e.key NOT IN ('500000', '200000', '100000', '50000', '20000',
                                 '10000', '5000', '2000', '1000')
                OR jsonb_typeof(e.value) <> 'number'
                OR (e.value::text)::numeric < 0
                OR (e.value::text)::numeric <> trunc((e.value::text)::numeric)
                OR (e.value::text)::numeric > 1000000) THEN -1
        ELSE (SELECT coalesce(sum(e.key::bigint * (e.value::text)::bigint), 0)
                FROM jsonb_each(p) e)
    END
$fn$;
GRANT EXECUTE ON FUNCTION public.tong_to_tien(jsonb) TO service_role;

CREATE TABLE IF NOT EXISTS public.ket_tien_mat_ca (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    location_id   uuid NOT NULL REFERENCES public.clinic_location (id) ON DELETE RESTRICT,
    ngay          date NOT NULL,
    ca            text NOT NULL CHECK (ca IN ('SANG', 'CHIEU', 'TOI')),
    quy_dau       bigint NOT NULL CHECK (quy_dau >= 0),
    quy_dau_dem   jsonb,
    quy_dau_boi   uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    quy_dau_luc   timestamptz NOT NULL DEFAULT now(),
    dem_cuoi      bigint CHECK (dem_cuoi >= 0),
    dem_cuoi_dem  jsonb,
    thu_tien_mat  bigint,
    du_kien       bigint,
    lech          bigint,
    ly_do_lech    text,
    nguoi_nhan    text CHECK (nguoi_nhan IS NULL OR length(nguoi_nhan) <= 120),
    dem_boi       uuid REFERENCES public.staff (id) ON DELETE RESTRICT,
    dem_luc       timestamptz,
    CONSTRAINT ket_tien_mat_ca_mot_dong UNIQUE (clinic_id, location_id, ngay, ca),
    CONSTRAINT ket_tien_mat_ca_quy_dau_khop CHECK (
        quy_dau_dem IS NULL OR public.tong_to_tien(quy_dau_dem) = quy_dau),
    CONSTRAINT ket_tien_mat_ca_dem_cuoi_khop CHECK (
        dem_cuoi_dem IS NULL OR public.tong_to_tien(dem_cuoi_dem) = dem_cuoi),
    -- Phần cuối ca có đủ cả cụm hoặc không có gì.
    CONSTRAINT ket_tien_mat_ca_cuoi_du_cum CHECK (
        (dem_cuoi IS NULL) = (thu_tien_mat IS NULL)
        AND (dem_cuoi IS NULL) = (du_kien IS NULL)
        AND (dem_cuoi IS NULL) = (lech IS NULL)
        AND (dem_cuoi IS NULL) = (dem_boi IS NULL)
        AND (dem_cuoi IS NULL) = (dem_luc IS NULL)
        AND (dem_cuoi IS NOT NULL OR (dem_cuoi_dem IS NULL AND ly_do_lech IS NULL
                                      AND nguoi_nhan IS NULL))),
    -- Mỗi con số giải thích được: dự kiến = quỹ đầu + thực thu tiền mặt; lệch =
    -- đếm − dự kiến; lệch ≠ 0 phải có lý do.
    CONSTRAINT ket_tien_mat_ca_so_khop CHECK (
        dem_cuoi IS NULL
        OR (du_kien = quy_dau + thu_tien_mat AND lech = dem_cuoi - du_kien)),
    CONSTRAINT ket_tien_mat_ca_lech_co_ly_do CHECK (
        lech IS NULL OR lech = 0
        OR length(btrim(coalesce(ly_do_lech, ''))) BETWEEN 3 AND 500)
);

COMMENT ON TABLE public.ket_tien_mat_ca IS
'Kiểm kê tiền mặt két theo ca (31/10/2026): quỹ đầu, đếm cuối, dự kiến = quỹ đầu + thực thu TM trong ca, lệch (≠0 bắt lý do). Mở lại có lý do; vết ở ket_tien_mat_ca_lich_su.';

CREATE OR REPLACE FUNCTION public.ket_tien_mat_ca_khong_xoa()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '%: không xoá — mở lại / sửa kèm lý do', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_ket_tien_mat_ca_khong_xoa ON public.ket_tien_mat_ca;
CREATE TRIGGER trg_ket_tien_mat_ca_khong_xoa
    BEFORE DELETE ON public.ket_tien_mat_ca
    FOR EACH ROW EXECUTE FUNCTION public.ket_tien_mat_ca_khong_xoa();

CREATE TABLE IF NOT EXISTS public.ket_tien_mat_ca_lich_su (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinic_id uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    ket_id    uuid NOT NULL REFERENCES public.ket_tien_mat_ca (id) ON DELETE RESTRICT,
    hanh_dong text NOT NULL
        CHECK (hanh_dong IN ('QUY_DAU', 'SUA_QUY_DAU', 'DEM_CUOI', 'MO_LAI')),
    ban_chup  jsonb NOT NULL,
    ly_do     text CHECK (ly_do IS NULL OR length(ly_do) <= 500),
    boi       uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    luc       timestamptz NOT NULL DEFAULT now(),
    -- Mở lại / sửa quỹ đầu sau khi đã có số là sửa sổ: bắt lý do.
    CONSTRAINT ket_tien_mat_ca_lich_su_ly_do CHECK (
        hanh_dong NOT IN ('MO_LAI', 'SUA_QUY_DAU')
        OR length(btrim(coalesce(ly_do, ''))) >= 3)
);
CREATE INDEX IF NOT EXISTS ix_ket_tien_mat_ca_lich_su_ket
    ON public.ket_tien_mat_ca_lich_su (ket_id, id);

DROP TRIGGER IF EXISTS trg_ket_tien_mat_ca_lich_su_chi_them
    ON public.ket_tien_mat_ca_lich_su;
CREATE TRIGGER trg_ket_tien_mat_ca_lich_su_chi_them
    BEFORE UPDATE OR DELETE ON public.ket_tien_mat_ca_lich_su
    FOR EACH ROW EXECUTE FUNCTION public.ket_tien_mat_ca_khong_xoa();

ALTER TABLE public.ket_tien_mat_ca ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ket_tien_mat_ca_lich_su ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ket_tien_mat_ca_select_own_clinic ON public.ket_tien_mat_ca;
CREATE POLICY ket_tien_mat_ca_select_own_clinic ON public.ket_tien_mat_ca
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS ket_tien_mat_ca_lich_su_select_own_clinic
    ON public.ket_tien_mat_ca_lich_su;
CREATE POLICY ket_tien_mat_ca_lich_su_select_own_clinic ON public.ket_tien_mat_ca_lich_su
    FOR SELECT TO authenticated USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.ket_tien_mat_ca, public.ket_tien_mat_ca_lich_su TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.ket_tien_mat_ca TO service_role;
GRANT SELECT, INSERT ON public.ket_tien_mat_ca_lich_su TO service_role;

DROP TRIGGER IF EXISTS trg_notify_ket_tien_mat_ca ON public.ket_tien_mat_ca;
CREATE TRIGGER trg_notify_ket_tien_mat_ca
    AFTER INSERT OR UPDATE ON public.ket_tien_mat_ca
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();
