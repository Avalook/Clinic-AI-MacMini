-- Ma trận "vai nào đứng được vị trí nào", nạp lại theo 27 vị trí của Kim Ngưu.
--
-- VÌ SAO BẮT BUỘC, KHÔNG PHẢI DỌN DẸP CHO ĐẸP:
--
-- `config_service._kiem_pham_vi_tram` chặn lúc LƯU một ca trực, đối chiếu với
-- bảng này. Nó đang chứa toàn mã trạm đời Hào Nam — `MAY_TRONG`, `PHU_BS_SA`,
-- `HSS_THU_THUAT`… — nên khi màn xếp lịch chuyển sang mã mới (`T1_LETAN`,
-- `T4_SAN_BS`…), mọi lần lưu của bảy vai đã khai trong ma trận sẽ bị từ chối
-- kèm câu "Vị trí hợp lệ: HSS_THU_THUAT, MAY_NGOAI, …" — một câu vô nghĩa với
-- người đang nhìn bảng Kim Ngưu.
--
-- Bảng có nhánh "chưa khai thì cho qua", nhưng nó chỉ cứu vai CHƯA CÓ DÒNG NÀO.
-- Bảy vai kia đã có dòng, nên chúng bị khoá chặt vào một danh mục đã chết.
--
-- LUẬT MỚI CHỈ CÒN MỘT TẦNG: nhóm nghề của vị trí.
--
--   nhom_nghe = BAC_SI      → chỉ bác sĩ (DOCTOR, ULTRASOUND_DOCTOR)
--   nhom_nghe = DIEU_DUONG  → mọi vai làm việc KHÔNG phải bác sĩ
--   nhom_nghe = DOI_TAC     → mọi vai làm việc (ô "Lấy mẫu" có hôm ghi
--                             "Green Lab", có hôm ghi tên điều dưỡng)
--
-- Không siết hơn, có chủ ý. Hai tuần lịch thật cho thấy một điều dưỡng đứng
-- tới TÁM vị trí khác nhau ở ba tầng — mọi luật tinh vi hơn "bác sĩ / không
-- phải bác sĩ" đều sẽ chặn nhầm một ca có thật, và Tuyền chốt 16/09 là mở
-- quyền cho mọi tài khoản thao tác được.
--
-- Ranh giới DUY NHẤT được giữ là bác sĩ, vì nó có luật hành nghề đứng sau.

BEGIN;

-- ── 1. Cho các dòng đời cũ nghỉ, KHÔNG xoá ─────────────────────────────────
--
-- Giữ lại để còn đọc được phòng khám từng khai gì, và để bật lại được nếu có
-- ngày quay về danh mục ấy. Xoá đi là mất luôn lịch sử của một quyết định.
UPDATE public.vai_duoc_vao_tram
   SET is_active = FALSE
 WHERE tram_ma NOT IN (SELECT code FROM public.vi_tri_lam_viec)
   -- `LICH_KHAM` KHÔNG nằm trong `vi_tri_lam_viec` (nó không phải một vị trí
   -- trong Excel mà là "bác sĩ nào trực hôm ấy"), nên không miễn trừ ở đây thì
   -- câu lệnh này tắt luôn quyền xếp lịch khám — và bác sĩ không còn được đặt
   -- lịch cho ai. Bản nháp đầu của migration này mắc đúng lỗi đó.
   AND tram_ma <> 'LICH_KHAM';

-- ── 2. Nạp ma trận mới từ chính danh mục vị trí ────────────────────────────
INSERT INTO
    public.vai_duoc_vao_tram (clinic_id, vai, tram_ma, is_active)
SELECT v.clinic_id, r.vai, v.code, TRUE
  FROM public.vi_tri_lam_viec v
 CROSS JOIN (VALUES
    ('DOCTOR', 'BAC_SI'),
    ('ULTRASOUND_DOCTOR', 'BAC_SI'),
    ('NURSE_ULTRASOUND', 'DIEU_DUONG'),
    ('RECEPTION', 'DIEU_DUONG'),
    ('TKYK', 'DIEU_DUONG'),
    ('CSKH', 'DIEU_DUONG'),
    ('TRUONG_CA', 'DIEU_DUONG'),
    ('CASHIER', 'DIEU_DUONG'),
    ('CASHIER_THUOC', 'DIEU_DUONG'),
    ('CASHIER_DV', 'DIEU_DUONG'),
    ('PHARMACIST', 'DIEU_DUONG'),
    ('MANAGEMENT', 'DIEU_DUONG')
 ) AS r(vai, nhom)
 WHERE v.is_active
   AND (v.nhom_nghe = r.nhom OR v.nhom_nghe = 'DOI_TAC')
 ON CONFLICT (clinic_id, tram_ma, vai) DO UPDATE SET is_active = TRUE;

-- ── 3. "Lịch khám": CẢ HAI loại bác sĩ ────────────────────────────────────
--
-- Ma trận cũ chỉ khai ULTRASOUND_DOCTOR ở đây — tức bác sĩ chính KHÔNG xếp
-- được vào lịch khám của chính mình nếu lưu qua API. Không ai gặp, vì lịch
-- trực tới nay đều nạp bằng script đi thẳng database, không qua cửa kiểm này.
INSERT INTO
    public.vai_duoc_vao_tram (clinic_id, vai, tram_ma, is_active)
SELECT c.id, r.vai, 'LICH_KHAM', TRUE
  FROM public.clinic c
 CROSS JOIN (VALUES ('DOCTOR'), ('ULTRASOUND_DOCTOR')) AS r(vai)
 ON CONFLICT (clinic_id, tram_ma, vai) DO UPDATE SET is_active = TRUE;

DO $$
DECLARE
    so_moi integer;
    so_cu  integer;
BEGIN
    SELECT count(*) INTO so_moi FROM public.vai_duoc_vao_tram WHERE is_active;
    SELECT count(*) INTO so_cu FROM public.vai_duoc_vao_tram WHERE NOT is_active;
    RAISE NOTICE 'Ma trận vai↔vị trí: % dòng đang dùng, % dòng đã cho nghỉ',
        so_moi, so_cu;
END $$;

COMMIT;
