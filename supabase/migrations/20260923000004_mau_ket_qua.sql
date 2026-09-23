-- Mẫu kết quả cận lâm sàng, và dịch vụ nào dùng mẫu nào (23/09/2026).
--
-- NGUỒN. Phiếu chỉ định giấy của Dr4Women (bản 17/08/2026, Tuyền gửi
-- `chi-dinh.html`) có 18 biểu mẫu kết quả và các nút "📄 Xem mẫu" đứng cạnh từng
-- dịch vụ. Hôm nay quan hệ ấy chỉ nằm trong tờ giấy và trong đầu người làm: hệ
-- thống không biết siêu âm tuyến vú thì điền mẫu nào.
--
-- HAI BẢNG, VÌ ĐÓ LÀ HAI THỨ KHÁC NHAU
--   `ket_qua_mau`          danh mục mẫu — đổi tên mẫu không đụng dịch vụ nào.
--   `dich_vu_mau_ket_qua`  dịch vụ nào dùng mẫu nào — đổi bảng giá không mất mẫu.
-- Gộp hai thứ này vào một cột trên `service_price` là cách chắc chắn để mai kia
-- KiotViet đồng bộ đè bảng giá là mất luôn liên kết.
--
-- KHÔNG ĐOÁN LIÊN KẾT. Migration này seed 18 mẫu, và KHÔNG tự gắn mẫu vào dịch
-- vụ nào: mã dịch vụ trên bản thật do KiotViet cấp, còn tờ giấy chỉ có tên gọi.
-- Gắn theo tên là cách âm thầm gắn nhầm mẫu kết quả cho bệnh nhân. Việc gắn làm
-- bằng lệnh có người xác nhận (`scripts/de-xuat-mau-ket-qua.py` đề xuất, người
-- duyệt).
--
-- Chạy lại được: IF NOT EXISTS / ON CONFLICT.

CREATE TABLE IF NOT EXISTS public.ket_qua_mau (
    clinic_id  uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    ma         text NOT NULL,
    nhom       text NOT NULL,
    ten        text NOT NULL,
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, ma),
    CONSTRAINT ket_qua_mau_ma_hoa
        CHECK (ma = upper(ma) AND length(ma) BETWEEN 1 AND 48)
);

CREATE TABLE IF NOT EXISTS public.dich_vu_mau_ket_qua (
    clinic_id    uuid NOT NULL,
    service_code text NOT NULL,
    mau          text NOT NULL,
    -- Ai gắn, lúc nào: gắn nhầm mẫu là chuyện lâm sàng, phải truy được.
    gan_boi      uuid REFERENCES public.staff(id),
    gan_luc      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clinic_id, service_code, mau),
    FOREIGN KEY (clinic_id, mau)
        REFERENCES public.ket_qua_mau(clinic_id, ma) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_dich_vu_mau_ket_qua_dich_vu
    ON public.dich_vu_mau_ket_qua (clinic_id, service_code);

ALTER TABLE public.ket_qua_mau ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dich_vu_mau_ket_qua ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ket_qua_mau_select_own_clinic ON public.ket_qua_mau;
CREATE POLICY ket_qua_mau_select_own_clinic ON public.ket_qua_mau
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
DROP POLICY IF EXISTS dich_vu_mau_ket_qua_select_own_clinic
    ON public.dich_vu_mau_ket_qua;
CREATE POLICY dich_vu_mau_ket_qua_select_own_clinic ON public.dich_vu_mau_ket_qua
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT ON public.ket_qua_mau, public.dich_vu_mau_ket_qua TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.ket_qua_mau, public.dich_vu_mau_ket_qua TO service_role;

-- ── 18 mẫu của Dr4Women (phiếu giấy 17/08/2026) ────────────────────────────
INSERT INTO public.ket_qua_mau (clinic_id, ma, nhom, ten)
SELECT 'a0000000-0000-4000-8000-000000000001'::uuid, m.ma, m.nhom, m.ten
  FROM (VALUES
    ('SA_OBUNG', 'Siêu âm tổng quát', 'Kết quả siêu âm ổ bụng'),
    ('SA_VU', 'Siêu âm chuyên khoa', 'Kết quả siêu âm tuyến vú'),
    ('SA_GIAP', 'Siêu âm chuyên khoa', 'Kết quả siêu âm tuyến giáp'),
    ('SA_MACH_CANH', 'Siêu âm mạch máu', 'Kết quả siêu âm động mạch cảnh'),
    ('SA_MACH_THAN', 'Siêu âm mạch máu', 'Kết quả siêu âm động mạch thận'),
    ('SA_DOPPLER_AM_VAT', 'Sàn chậu & Tình dục nữ', 'Siêu âm Doppler âm vật'),
    ('SA_TINH_HOAN', 'Siêu âm Nam khoa', 'Kết quả siêu âm tinh hoàn'),
    ('SA_TC_BT', 'Siêu âm phụ khoa', 'Kết quả siêu âm tử cung buồng trứng'),
    ('SA_TC_PP', 'Siêu âm phụ khoa', 'Kết quả siêu âm tử cung phần phụ'),
    ('SA_THAI_SOM', 'Siêu âm Sản khoa', 'Kết quả siêu âm thai sớm (dưới 11 tuần)'),
    ('SA_THAI_QUY_1', 'Siêu âm Sản khoa', 'Kết quả siêu âm thai quý I'),
    ('SA_THAI_QUY_23', 'Siêu âm Sản khoa', 'Kết quả siêu âm thai quý II - III'),
    ('SA_SONG_THAI_QUY_1', 'Siêu âm Sản khoa', 'Kết quả siêu âm song thai quý I'),
    ('SA_SONG_THAI_QUY_23', 'Siêu âm Sản khoa',
     'Kết quả siêu âm song thai quý II - III'),
    ('SOI_AM_HO', 'Thủ thuật & Khám sàn chậu', 'Phiếu soi âm hộ'),
    ('XN_HPV', 'Xét nghiệm Sinh học phân tử', 'Kết quả xét nghiệm HPV Genotype'),
    ('XN_PCR_STDS', 'Xét nghiệm Sinh học phân tử',
     'KQXN PCR 13 tác nhân gây bệnh lây truyền tình dục'),
    ('XN_TONG_QUAT', 'Xét nghiệm Huyết học & Sinh hóa',
     'Phiếu kết quả xét nghiệm Tổng Quát (TrueMedicine)')
  ) AS m(ma, nhom, ten)
 WHERE EXISTS (SELECT 1 FROM public.clinic
                WHERE id = 'a0000000-0000-4000-8000-000000000001'::uuid)
ON CONFLICT (clinic_id, ma) DO UPDATE
    SET nhom = EXCLUDED.nhom, ten = EXCLUDED.ten, updated_at = now();

-- ── Quyền quản lý danh mục ────────────────────────────────────────────────
INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('danh_muc', 'Danh mục & biểu mẫu', 'catalogue',
     'Sửa danh mục dịch vụ, mẫu kết quả, gắn mẫu cho dịch vụ')
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, module = EXCLUDED.module, mo_ta = EXCLUDED.mo_ta;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES
    ('catalogue.result_template.manage', 'Gắn mẫu kết quả cho dịch vụ',
     'danh_muc', 'catalogue', 'clinical', false)
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, work_pack = EXCLUDED.work_pack,
        module = EXCLUDED.module, rui_ro = EXCLUDED.rui_ro,
        chung_chi_lam_sang = EXCLUDED.chung_chi_lam_sang;

-- Quản lý đang làm được cấp khối mới này ngay, như các khối khác lúc chuyển.
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, 'catalogue.result_template.manage', 'danh_muc',
       m.role, 'Chép từ preset khi thêm khối Danh mục (23/09/2026)'
  FROM public.clinic_membership m
 WHERE m.is_active AND m.role = 'MANAGEMENT'
ON CONFLICT DO NOTHING;

COMMENT ON TABLE public.ket_qua_mau IS
    'Danh mục mẫu kết quả cận lâm sàng (nguồn: phiếu chỉ định giấy Dr4Women 17/08/2026).';
COMMENT ON TABLE public.dich_vu_mau_ket_qua IS
    'Dịch vụ nào dùng mẫu kết quả nào. KHÔNG seed tự động: gắn theo tên là gắn nhầm.';
