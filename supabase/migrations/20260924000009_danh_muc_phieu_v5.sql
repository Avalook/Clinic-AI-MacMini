-- DANH MỤC ĐỦ CHO PHIẾU v5 — thêm dịch vụ / thủ thuật còn thiếu (IP-4).
-- Tuyền 23/09/2026 tối: "các cái dịch vụ hay thủ thuật này kia đều có hết" (chi-dinh.html,
-- bảng giá KiotViet). Bảng ghép viết tay: src/clinicai/phieu_kham/anh_xa_danh_muc.py.
--
--   * 20 dịch vụ MỚI (không có trong danh mục V5-A) → THÊM, giá theo chi-dinh.html.
--     Chỉ liệt kê mã mới: mã V5-A đến từ dữ liệu phòng khám (seed), migration không
--     tạo chúng — DB dựng mới chạy migration TRƯỚC seed, tạo trước là đụng seed.
--   * Dịch vụ đã có → KHÔNG đổi tên, phòng hay giá. Chỉ điền giá khi đang TRỐNG
--     (giá đã đặt là quyết định kinh doanh; migration không được đè).
--   * Chỉ thêm khi phòng khám có node làm dịch vụ ấy (node_definition), để
--     dịch vụ mới không thành chỉ định không phòng nào nhận.
--
-- Chạy lại được.

WITH ds (service_code, name, node_code, unit_price, category) AS (
  VALUES
    ('CLS_HPV', 'Xét nghiệm HPV', 'DICHVU-SANGLOC-COTUCUNG', 950000, 'Tầng 1'),
    ('CLS_THINPREP', 'ThinPrep', 'DICHVU-SANGLOC-COTUCUNG', 650000, 'Tầng 1'),
    ('CLS_PCR_12_VK', 'PCR 12 loại vi khuẩn', 'DICHVU-LAYMAU-AMDAO', 1200000, 'Tầng 1'),
    ('CLS_SIEU_AM_4D_SAN_CHAU', 'Siêu âm doppler 4D sàn chậu', 'DICHVU-SIEUAM', 500000, 'Sàn chậu'),
    ('CLS_SIEU_AM_DOPPLER_DUONG_VAT', 'Siêu âm Doppler dương vật', 'DICHVU-SIEUAM', 300000, 'Nam khoa'),
    ('CLS_SIEU_AM_TINH_HOAN', 'Siêu âm tinh hoàn / Doppler', 'DICHVU-SIEUAM', 350000, 'Thủ thuật'),
    ('CLS_DO_CO_LUC_AM_DAO', 'Đo cơ lực âm đạo bằng máy (sàng lọc)', 'DICHVU-THUTHUAT', 300000, 'Sàn chậu'),
    ('CLS_GHE_DTT_YEU_CO', 'Trải nghiệm 5 phút ghế ĐTT — yếu cơ', 'DICHVU-THUTHUAT', 150000, 'Sàn chậu'),
    ('CLS_GHE_DTT_DAU_CO', 'Trải nghiệm 5 phút ghế ĐTT — đau cơ', 'DICHVU-THUTHUAT', 150000, 'Sàn chậu'),
    ('CLS_KHAM_SAN_CHAU', 'Khám sàn chậu', 'DICHVU-THUTHUAT', 300000, 'Sàn chậu'),
    ('CLS_SOI_BUONG_TU_CUNG', 'Soi buồng tử cung', 'DICHVU-THUTHUAT', 6000000, 'Thủ thuật'),
    ('CLS_HUT_BUONG_TU_CUNG', 'Hút buồng tử cung', 'DICHVU-THUTHUAT', 2000000, 'Thủ thuật'),
    ('CLS_SOI_AM_HO', 'Soi âm hộ', 'DICHVU-THUTHUAT', 250000, 'Thủ thuật'),
    ('CLS_NONG_BAO_QUY_DAU_AV', 'Nong bao quy đầu âm vật', 'DICHVU-THUTHUAT', 1000000, 'Thủ thuật'),
    ('CLS_TACH_BAO_QUY_DAU_AV', 'Tách bao quy đầu âm vật', 'DICHVU-THUTHUAT', 7000000, 'Thủ thuật'),
    ('CLS_BIOFEEDBACK', 'Biofeedback', 'DICHVU-THUTHUAT', 900000, 'Sàn chậu'),
    ('CLS_GHE_DTT', 'Ghế điện từ trường (ĐTT)', 'DICHVU-THUTHUAT', 500000, 'Sàn chậu'),
    ('CLS_LASER', 'Laser sàn chậu', 'DICHVU-THUTHUAT', 7000000, 'Sàn chậu'),
    ('CLS_LASER_TRE_HOA', 'Laser trẻ hoá', 'DICHVU-THUTHUAT', 7000000, 'Sàn chậu'),
    ('CLS_LASER_ST_SSD', 'Laser ST/SSD', 'DICHVU-THUTHUAT', 15000000, 'Sàn chậu')
)
INSERT INTO public.service_price
    (clinic_id, service_code, name, "group", unit_price, active, category, node_code)
SELECT n.clinic_id, ds.service_code, ds.name, 'dich_vu', ds.unit_price, true,
       ds.category, ds.node_code
  FROM ds
  JOIN public.node_definition n ON n.code = ds.node_code
ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;

WITH ds (service_code, unit_price) AS (
  VALUES
    ('CLS_DO_MAT_DO_XUONG', 200000),
    ('CLS_NUOC_TIEU', 50000),
    ('CLS_CHAY_MONITORING', 200000),
    ('CLS_XET_NGHIEM_MAU', 350000),
    ('CLS_XET_NGHIEM_DICH_AM_DAO', 300000),
    ('CLS_HPV', 950000),
    ('CLS_THINPREP', 650000),
    ('CLS_PCR_12_VK', 1200000),
    ('CLS_SIEU_AM_3D_THAI_12_TUAN', 250000),
    ('CLS_SIEU_AM_3D_THAI_12_TUAN_2', 300000),
    ('CLS_SIEU_AM_THAI_6D', 400000),
    ('CLS_SIEU_AM_DAU_DO_DO_DAI_CTC', 50000),
    ('CLS_SIEU_AM_2D_TC_BT', 250000),
    ('CLS_SIEU_AM_4D_TC_BT', 350000),
    ('CLS_SIEU_AM_BOM_NUOC_TU_CUNG', 800000),
    ('CLS_SIEU_AM_KHOP', 150000),
    ('CLS_SIEU_AM_O_BUNG', 250000),
    ('CLS_SIEU_AM_VU', 200000),
    ('CLS_SIEU_AM_TUYEN_GIAP', 200000),
    ('CLS_SIEU_AM_DOPPLER_MACH_CANH', 400000),
    ('CLS_SIEU_AM_DOPPLER_DM_THAN', 400000),
    ('CLS_SIEU_AM_DOPPLER_AM_VAT', 150000),
    ('CLS_SIEU_AM_4D_SAN_CHAU', 500000),
    ('CLS_SIEU_AM_DOPPLER_DUONG_VAT', 300000),
    ('CLS_SIEU_AM_TINH_HOAN', 350000),
    ('CLS_DO_CO_LUC_AM_DAO', 300000),
    ('CLS_GHE_DTT_YEU_CO', 150000),
    ('CLS_GHE_DTT_DAU_CO', 150000),
    ('CLS_KHAM_SAN_CHAU', 300000),
    ('CLS_CHUP_VU_EP', 500000),
    ('CLS_CHUP_MRI_VU', 2500000),
    ('CLS_CHUP_TU_CUNG_VOI_TRUNG', 1200000),
    ('CLS_DAT_VONG_NOI_TIET', 5000000),
    ('CLS_THAO_VONG', 350000),
    ('CLS_CAY_QUE_TRANH_THAI', 2600000),
    ('CLS_THAO_QUE_TRANH_THAI', 700000),
    ('CLS_SOI_BUONG_TU_CUNG', 6000000),
    ('CLS_HUT_BUONG_TU_CUNG', 2000000),
    ('CLS_SOI_CO_TU_CUNG', 400000),
    ('CLS_SOI_AM_HO', 250000),
    ('CLS_NONG_BAO_QUY_DAU_AV', 1000000),
    ('CLS_TACH_BAO_QUY_DAU_AV', 7000000),
    ('CLS_BIOFEEDBACK', 900000),
    ('CLS_GHE_DTT', 500000),
    ('CLS_LASER', 7000000),
    ('CLS_LASER_TRE_HOA', 7000000),
    ('CLS_LASER_ST_SSD', 15000000)
)
UPDATE public.service_price s
   SET unit_price = ds.unit_price, updated_at = now()
  FROM ds
 WHERE s.service_code = ds.service_code
   AND s."group" = 'dich_vu'
   AND s.unit_price IS NULL;
