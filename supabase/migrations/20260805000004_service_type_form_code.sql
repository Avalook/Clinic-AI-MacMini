-- Phiếu khám nào đi với dịch vụ nào — quản lý khai, không đoán từ tên.
--
-- HÔM NAY HỆ THỐNG ĐOÁN BẰNG TỪ KHOÁ TRONG TÊN DỊCH VỤ. `resolveServiceCode`
-- ở lib/form-schemas/index.ts dò chuỗi: thấy "nam khoa" ra NK, thấy "sản" ra
-- SK. Đo trên 14 dịch vụ thật của Dr4Women thì 8 tên dò ra, 6 tên KHÔNG:
--
--     Hồ sơ sinh · Tiền hôn nhân · Tư vấn chuyên sâu · NPĐH · Thủ thuật · FREE
--
-- Với 6 dịch vụ ấy, bác sĩ mở lượt khám ra và KHÔNG THẤY PHIẾU NÀO — màn hình
-- ẩn hẳn phần đó, không báo lỗi, không nói gì. Bác sĩ không phân biệt được
-- "dịch vụ này không cần phiếu" với "hệ thống hỏng".
--
-- VÀ CÁCH ĐOÁN ẤY KHÔNG SỬA ĐƯỢC BẰNG CÁCH THÊM TỪ KHOÁ. Phòng khám đổi tên
-- một dịch vụ là mất phiếu; phòng khám thứ hai đặt tên khác là hỏng ngay; và
-- muốn đổi thì phải sửa code, deploy — đúng thứ mà cả tuần nay đang gỡ bỏ.
--
-- TIỀN HÔN NHÂN LÀ CA LÀM LỘ RA VẤN ĐỀ THẬT SỰ.
--
-- Tra hướng dẫn khám tiền hôn nhân (vnpa.moh.gov.vn và các bệnh viện lớn) thì
-- nội dung khác nhau THEO GIỚI:
--
--     nữ   khám phụ khoa · siêu âm tử cung–buồng trứng · nội tiết · AMH
--     nam  khám nam khoa · tinh dịch đồ · nội tiết
--
-- Nên "một dịch vụ ⇒ một phiếu" là mô hình sai ngay từ đầu. Cần hai cột.

ALTER TABLE public.service_type
    ADD COLUMN IF NOT EXISTS form_code text,
    --: Phiếu dùng khi bệnh nhân là NAM. NULL = dùng `form_code`.
    --: Chỉ khai cho dịch vụ mà nội dung khám khác nhau theo giới; phần lớn
    --: dịch vụ để trống.
    ADD COLUMN IF NOT EXISTS form_code_nam text;

COMMENT ON COLUMN public.service_type.form_code IS
    'Mã phiếu khám chuyên khoa cho dịch vụ này. NULL = dịch vụ không có phiếu '
    'riêng (thủ thuật, tư vấn) — màn hình phải NÓI RA, không được ẩn im lặng.';
COMMENT ON COLUMN public.service_type.form_code_nam IS
    'Phiếu dùng khi bệnh nhân là nam. NULL = dùng form_code. Có vì khám tiền '
    'hôn nhân nữ (phụ khoa) và nam (nam khoa) là hai nội dung khác nhau.';

-- Mã phải có thật trong danh mục form CỦA CHÍNH phòng khám đó. Không dùng khoá
-- ngoại vì `clinical_form_catalogue` khoá theo (clinic_id, form_code) và
-- service_type mang clinic_id riêng — trigger nói được câu rõ hơn, và nói đúng
-- tên phòng khám.
CREATE OR REPLACE FUNCTION public.service_type_form_code_exists()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_ma text;
BEGIN
    FOREACH v_ma IN ARRAY ARRAY[NEW.form_code, NEW.form_code_nam] LOOP
        IF v_ma IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.clinical_form_catalogue f
             WHERE f.clinic_id = NEW.clinic_id AND f.form_code = v_ma
        ) THEN
            RAISE EXCEPTION
                'Không có phiếu khám mã % trong danh mục của phòng khám này.',
                v_ma
                USING ERRCODE = 'foreign_key_violation';
        END IF;
    END LOOP;
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS trg_service_type_form_code ON public.service_type;
CREATE TRIGGER trg_service_type_form_code
    BEFORE INSERT OR UPDATE OF form_code, form_code_nam ON public.service_type
    FOR EACH ROW EXECUTE FUNCTION public.service_type_form_code_exists();

-- ---------------------------------------------------------------------------
-- Khai giá trị cho Dr4Women
-- ---------------------------------------------------------------------------
-- TÁM DÒNG ĐẦU GIỮ NGUYÊN HÀNH VI HÔM NAY — chép lại đúng kết quả mà
-- `resolveServiceCode` đang cho, để bật cột mới lên không đổi gì với những
-- dịch vụ đang chạy tốt.
--
-- HAI DÒNG CUỐI LÀ MỚI, và là quyết định về nghiệp vụ:
--
--   Hồ sơ sinh     → SK   hồ sơ theo dõi thai/sinh, thuộc sản khoa
--   Tiền hôn nhân  → PK cho nữ, NK cho nam   (xem ghi chú trên)
--
-- BỐN DỊCH VỤ CÒN LẠI CỐ Ý ĐỂ TRỐNG, không phải bỏ quên:
--
--   Thủ thuật          làm thủ thuật, không phải một buổi khám chuyên khoa
--   Tư vấn chuyên sâu  ghi vào bệnh án chung là đủ
--   FREE               chỗ giữ, không phải dịch vụ thật
--   NPĐH               CHƯA AI GIẢI NGHĨA ĐƯỢC MÃ NÀY. Đây là lần thứ hai nó
--                      xuất hiện; spec nam khoa §9.6 cũng ghi "mã dịch vụ đặt
--                      lịch duy nhất không có tài liệu". Để trống là trung
--                      thực; đoán bừa một phiếu cho nó thì bác sĩ sẽ điền vào
--                      một biểu mẫu sai.

UPDATE public.service_type st SET
    form_code = v.nu,
    form_code_nam = v.nam
  FROM (VALUES
      ('HIEM_MUON',          'HMVS', NULL),
      ('NAM_KHOA',           'NK',   NULL),
      ('NOI_TIET_TINH_DUC',  'NT',   NULL),
      ('PHU_KHOA',           'PK',   NULL),
      ('SAN_1',              'SK',   NULL),
      ('SAN_2',              'SK',   NULL),
      ('SAN_3',              'SK',   NULL),
      ('KHAM_TIEN_SAN',      'SK',   NULL),
      ('HO_SO_SINH',         'SK',   NULL),
      ('TIEN_HON_NHAN',      'PK',   'NK')
  ) AS v(code, nu, nam)
 WHERE st.code = v.code;

DO $verify$
DECLARE
    v_co   int;
    v_trong int;
    v_thn  record;
BEGIN
    SELECT count(*) FILTER (WHERE form_code IS NOT NULL),
           count(*) FILTER (WHERE form_code IS NULL)
      INTO v_co, v_trong
      FROM public.service_type WHERE is_active;

    SELECT form_code, form_code_nam INTO v_thn
      FROM public.service_type WHERE code = 'TIEN_HON_NHAN' LIMIT 1;

    IF v_thn IS NOT NULL
       AND (v_thn.form_code IS DISTINCT FROM 'PK'
            OR v_thn.form_code_nam IS DISTINCT FROM 'NK') THEN
        RAISE EXCEPTION
            'Tiền hôn nhân phải là PK cho nữ và NK cho nam — nội dung khám hai '
            'giới khác nhau';
    END IF;

    RAISE NOTICE
        'phiếu theo dịch vụ: % dịch vụ đã gán, % để trống (thủ thuật/tư vấn/'
        'FREE/NPĐH — cố ý)', v_co, v_trong;
END
$verify$;
