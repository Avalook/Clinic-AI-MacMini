-- HAI DÒNG BỊ BỎ SÓT KHI PARSE PHIẾU CHỈ ĐỊNH.
--
-- Phiếu chỉ định giấy của phòng khám có 31 mục; `service_price` chỉ có 29.
-- Hai mục mất là "Biofeedback cơ bản" và "Biofeedback nâng cao", nằm cuối cột
-- "Thủ thuật". CHANGELOG của lần parse ghi "KHÔNG bỏ sót dòng nào" — sai.
--
-- Hậu quả cụ thể, không phải lý thuyết: `order_services()` TỪ CHỐI dịch vụ
-- không có trong danh mục (đúng thiết kế — xem 20260801000002). Nên hôm nay bác
-- sĩ chỉ định Biofeedback thì không có gì để chọn, và bệnh nhân đi làm
-- Biofeedback là một lượt việc hệ thống không hề biết.
--
-- Giá để trống: phiếu giấy không in giá, và ĐOÁN GIÁ THÌ SAI HƠN LÀ ĐỂ TRỐNG.
-- `unit_price` NULL giống cả 29 dịch vụ còn lại; khi nào phòng khám đưa bảng
-- giá thì điền một lượt.

-- ---------------------------------------------------------------------------
-- 1. Thêm hai dịch vụ — chỉ cho phòng khám ĐÃ nạp phiếu chỉ định này
-- ---------------------------------------------------------------------------
-- Không CROSS JOIN toàn bộ `clinic`: danh mục dịch vụ là bảng giá riêng của
-- từng cơ sở, và nhét dịch vụ của Dr4Women vào một tenant khác là bịa danh mục
-- hộ họ. Mốc nhận biết là CLS_SOI_CO_TU_CUNG — cùng cột "Thủ thuật", cùng tờ
-- phiếu. Phòng khám nào có dòng đó thì đã nạp tờ này.
INSERT INTO public.service_price
       (clinic_id, service_code, name, "group", unit_price, category, tang, active)
SELECT src.clinic_id, v.service_code, v.name, 'dich_vu', NULL, 'Thủ thuật', NULL, true
  FROM (SELECT DISTINCT clinic_id
          FROM public.service_price
         WHERE service_code = 'CLS_SOI_CO_TU_CUNG') AS src
 CROSS JOIN (VALUES
        ('CLS_BIOFEEDBACK_CO_BAN',   'Biofeedback cơ bản'),
        ('CLS_BIOFEEDBACK_NANG_CAO', 'Biofeedback nâng cao')
 ) AS v(service_code, name)
    ON CONFLICT (clinic_id, "group", service_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Dạy luật map cho hai mã mới
-- ---------------------------------------------------------------------------
-- CREATE OR REPLACE nguyên hàm thay vì thêm một UPDATE rời: seed.sql gọi
-- map_services_to_nodes() SAU khi nạp dữ liệu (database trắng thì bảng còn rỗng
-- lúc migration chạy), nên luật phải nằm trong hàm mới có tác dụng ở cả hai
-- đường. Chỉ khác bản 20260801000001 đúng một chỗ: IN-list của thủ thuật.
CREATE OR REPLACE FUNCTION public.map_services_to_nodes()
RETURNS integer
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
    mapped integer;
BEGIN
-- ---------------------------------------------------------------------------

-- Every ultrasound goes to the ultrasound room. Fifteen of the 31 services.
    UPDATE public.service_price SET node_code = 'DICHVU-SIEUAM'
     WHERE service_code LIKE 'CLS_SIEU_AM%' AND node_code IS NULL;

-- Specimen collection, split by what is collected — different room prep, and
-- in the case of the vaginal swab a different set of roles.
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-MAU'
     WHERE service_code = 'CLS_XET_NGHIEM_MAU' AND node_code IS NULL;
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-NUOCTIEU'
     WHERE service_code = 'CLS_NUOC_TIEU' AND node_code IS NULL;
    UPDATE public.service_price SET node_code = 'DICHVU-LAYMAU-AMDAO'
     WHERE service_code = 'CLS_XET_NGHIEM_DICH_AM_DAO' AND node_code IS NULL;

-- Cervical screening: colposcopy is the screening node, not a procedure.
    UPDATE public.service_price SET node_code = 'DICHVU-SANGLOC-COTUCUNG'
     WHERE service_code = 'CLS_SOI_CO_TU_CUNG' AND node_code IS NULL;

-- Imaging this clinic does not perform itself.
    UPDATE public.service_price SET node_code = 'DICHVU-HINHANH-NGOAI'
     WHERE service_code IN ('CLS_CHUP_MRI_VU', 'CLS_CHUP_VU_EP',
                            'CLS_CHUP_TU_CUNG_VOI_TRUNG')
       AND node_code IS NULL;

    UPDATE public.service_price SET node_code = 'DICHVU-DXA'
     WHERE service_code = 'CLS_DO_MAT_DO_XUONG' AND node_code IS NULL;

-- Procedures: insertion and removal of contraceptives, monitoring, and the two
-- biofeedback sessions (pelvic-floor work — performed in the nurse/procedure
-- area by the same node, per the paper form's own grouping).
    UPDATE public.service_price SET node_code = 'DICHVU-THUTHUAT'
     WHERE service_code IN ('CLS_CAY_QUE_TRANH_THAI', 'CLS_THAO_QUE_TRANH_THAI',
                            'CLS_DAT_VONG_NOI_TIET', 'CLS_THAO_VONG',
                            'CLS_CHAY_MONITORING',
                            'CLS_BIOFEEDBACK_CO_BAN', 'CLS_BIOFEEDBACK_NANG_CAO')
       AND node_code IS NULL;

-- CLS_KHAM_PHU_KHOA is a consultation, not an order the doctor raises for
-- somebody else to perform. It stays NULL on purpose: ordering it from the
-- composer would create a second consultation work item for a patient already
-- in front of a doctor.

    SELECT count(node_code) INTO mapped FROM public.service_price;
    RETURN mapped;
END
$fn$;

-- Map ngay cho cài đặt đang chạy (prod: bảng giá là thật). Database trắng thì
-- lệnh này không map gì — seed.sql gọi lại ở cuối file.
SELECT public.map_services_to_nodes();
