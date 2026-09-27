-- PHÂN QUYỀN THEO KỸ NĂNG (Tuyền chốt 28/09/2026, bản "D").
--
-- Phòng khám nghĩ theo KỸ NĂNG (file "Sáng Ý - Thông tin nhân sự": Phụ SA, Phụ
-- sàn chậu, Bio, TKYK, Lấy mẫu…), không theo 21 khối màn hình. Hai bảng của khối
-- Phân quyền (modules.py `permission.bang`):
--
--   ky_nang          — một kỹ năng = những LEGO nào (mã MAN trong
--                      permissions/catalogue.py) + làm ở PHÒNG nào (lego "phong").
--   nhan_su_ky_nang  — ai có kỹ năng nào.
--
-- Quyền thật VẪN là capability_grant: tick một kỹ năng = service bật đúng các
-- lego ấy qua `doi_lego` (cùng một đường cấp quyền, cùng sổ kiểm toán). Bảng
-- thành viên phải LƯU riêng — không suy ngược được từ lego: TKYK và Phụ BS Sản
-- cùng mở Bàn khám, Lấy mẫu trùm phòng của Phụ SA.
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.ky_nang (
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    ma         text NOT NULL CHECK (ma ~ '^[a-z0-9_]{2,40}$'),
    ten        text NOT NULL CHECK (length(btrim(ten)) BETWEEN 1 AND 80),
    nhom       text NOT NULL DEFAULT 'Khác',
    thu_tu     int  NOT NULL DEFAULT 0,
    lego       text[] NOT NULL DEFAULT '{}',
    phong_ids  uuid[] NOT NULL DEFAULT '{}',
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, ma)
);

COMMENT ON TABLE public.ky_nang IS
'Kỹ năng (vị trí) của phòng khám = tập lego + phòng làm. Khối Phân quyền.';

CREATE TABLE IF NOT EXISTS public.nhan_su_ky_nang (
    clinic_id  uuid NOT NULL,
    staff_id   uuid NOT NULL REFERENCES public.staff(id) ON DELETE CASCADE,
    ky_nang_ma text NOT NULL,
    gan_luc    timestamptz NOT NULL DEFAULT now(),
    gan_boi    uuid REFERENCES public.staff(id) ON DELETE SET NULL,
    PRIMARY KEY (clinic_id, staff_id, ky_nang_ma),
    FOREIGN KEY (clinic_id, ky_nang_ma)
        REFERENCES public.ky_nang(clinic_id, ma) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS nhan_su_ky_nang_theo_ky_nang
    ON public.nhan_su_ky_nang (clinic_id, ky_nang_ma);

COMMENT ON TABLE public.nhan_su_ky_nang IS
'Nhân sự ↔ kỹ năng. Tick/bỏ tick đi qua service, service bật/tắt lego tương ứng.';

ALTER TABLE public.ky_nang ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nhan_su_ky_nang ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ky_nang_select_own_clinic ON public.ky_nang;
CREATE POLICY ky_nang_select_own_clinic ON public.ky_nang
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS nhan_su_ky_nang_select_own_clinic ON public.nhan_su_ky_nang;
CREATE POLICY nhan_su_ky_nang_select_own_clinic ON public.nhan_su_ky_nang
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ky_nang TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.nhan_su_ky_nang TO service_role;
