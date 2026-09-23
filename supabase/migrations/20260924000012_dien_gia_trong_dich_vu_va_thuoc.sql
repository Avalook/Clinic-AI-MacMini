-- GIÁ TRỐNG → điền theo bảng giá của phòng khám (chi-dinh.html), CHỈ chỗ đang trống.
--
-- Hai lỗ của 20260924000009:
--   * Nó điền giá dịch vụ bằng UPDATE ngay trong migration — mà DB dựng mới chạy
--     migration TRƯỚC seed, nên máy dựng mới (local, CI, VPS mới) còn 31 dịch vụ
--     không giá → quầy từ chối thu "chưa có giá".
--   * Thuốc chưa được điền: phiếu v5 kê 58 thuốc có giá trong chi-dinh.html, còn
--     `drug_catalog.unit_price` ở máy dựng mới trống cả 80 dòng.
-- Cách chữa giống `map_services_to_nodes()`: gói luật vào MỘT hàm, migration gọi
-- một lần (DB đang chạy), seed.sql gọi lại sau khi nạp dữ liệu (DB dựng mới).
--
-- Giá đã đặt là quyết định kinh doanh: KHÔNG đè (chỉ `unit_price IS NULL`).
-- Tên thuốc ghép bằng `drug_catalog.name_raw` qua bảng viết tay
-- `src/clinicai/phieu_kham/anh_xa_danh_muc.py` (THUOC). Giá thuốc là giá bán một
-- đơn vị bán như bảng giá ghi (hộp / viên / ống…).
--
-- Chạy lại được.

CREATE OR REPLACE FUNCTION public.dien_gia_trong_theo_phieu_v5()
RETURNS void
LANGUAGE sql
AS $$
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

  WITH ds (name_raw, unit_price) AS (
    VALUES
      ('Androgel', 85000),
      ('Aspilete', 1000),
      ('Assicin (3v/6v/9v)', 170000),
      ('Avanafil (Flepgo 100)', 420000),
      ('Bennatfort', 50000),
      ('Besuto', 750000),
      ('Betmiga', 35000),
      ('Canesten', 55000),
      ('Canxi', 550000),
      ('Cavidagel', 400000),
      ('Cefdinir', 10000),
      ('Cetrotide', 1000000),
      ('CoQ10 (1/2)', 520000),
      ('Cumlaude prebiotic', 600000),
      ('DHA', 360000),
      ('Daikyn', 270000),
      ('Dalacin C', 190000),
      ('Diane', 160000),
      ('Dienosis', 850000),
      ('Diphereline (3.75/0.1)', 3400000),
      ('Docy (15v/30v)', 1500),
      ('Dunium/ Fetogard (10v/15v)', 10000),
      ('Duphaston (4v/ 2v)', 240000),
      ('Durapil', 1200000),
      ('Estrogel', 550000),
      ('Estrogel pump', 550000),
      ('Eulac', 280000),
      ('Fersen', 950000),
      ('Fes 1/10', 740000),
      ('Fes ⅕', 1100000),
      ('Filrosy progesteron 200 Đ', 25000),
      ('Folic Mum', 260000),
      ('Follitrope', 850000),
      ('Fosamax 2800/5600', 450000),
      ('Gemapaxan', 85000),
      ('Glucophage', 140000),
      ('GonaF', 1200000),
      ('IFV-M', 750000),
      ('IVF-C', 300000),
      ('Indurat 5 (Đ/ U)', 33000),
      ('Intimate', 200000),
      ('Kofio', 225000),
      ('Letrozole (10v, 15v)', 50000),
      ('Levina 5', 300000),
      ('Lomexin', 150000),
      ('Magie', 285000),
      ('Meclon', 250000),
      ('Mensterona', 950000),
      ('Metronidazol', 1000),
      ('Nystatin', 20000),
      ('Ovagrow', 550000),
      ('Ovitrelle', 1300000),
      ('Pruzena', 120000),
      ('Vitcofol', 220000),
      ('Yspuripax (2v/4v)', 7000),
      ('ZinC', 275000),
      ('isoflavon', 410000),
      ('usatestos Đ', 20000)
  )
  UPDATE public.drug_catalog d
     SET unit_price = ds.unit_price
    FROM ds
   WHERE d.name_raw = ds.name_raw
     AND d.unit_price IS NULL;
$$;

SELECT public.dien_gia_trong_theo_phieu_v5();
