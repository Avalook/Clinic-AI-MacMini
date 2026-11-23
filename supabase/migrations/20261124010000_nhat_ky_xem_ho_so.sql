-- NHẬT KÝ XEM HỒ SƠ — ai đã MỞ hồ sơ của khách nào, lúc nào, qua cửa nào (24/11/2026).
--
-- Vì sao: dữ liệu sức khoẻ là dữ liệu cá nhân nhạy cảm (NĐ 356/2025 Điều 4 k.2),
-- phải giới hạn và lần lại được ai đã truy cập. Trước bảng này hệ thống chỉ ghi
-- thao tác GHI (`event_log`, `domain_event`, `*_lich_su`); ĐỌC thì không để lại
-- vết nào — không trả lời được "ai đã xem bệnh án của chị X tuần trước".
--
-- Ghi gì: CHỈ định danh — người xem (staff_id + vai lúc xem), khách
-- (clinic_patient_id), loại hồ sơ, id của bản ghi được mở (nếu có), cửa API.
-- KHÔNG chép nội dung hồ sơ, không tên, không SĐT: đọc nhật ký không được trở
-- thành một đường đọc hồ sơ thứ hai.
--
-- Ghi gộp: cùng người · cùng khách · cùng loại · cùng bản ghi · cùng cửa trong
-- một khung 5 phút chỉ giữ MỘT dòng (chỉ mục duy nhất trên `khung` + ON CONFLICT
-- DO NOTHING). Màn bác sĩ tự tải lại theo tin thời gian thực nên một lần mở
-- hồ sơ có thể gọi cùng cửa hàng chục lần; ghi từng lượt sẽ làm nhật ký phình
-- mà không thêm thông tin "ai xem khi nào".
--
-- Không khoá ngoại sang `patient`: nhật ký phải sống lâu hơn hồ sơ (khách nháp
-- bị xoá tận gốc thì vết "đã có người mở nó" vẫn còn). Giữ: không tự xoá — đề
-- xuất ≥ 10 năm cùng bệnh án (xem thân PR); xoá chỉ bằng migration có duyệt.
--
-- Chỉ thêm: trigger chặn UPDATE/DELETE (cùng nếp `result_correction`).
-- Đọc: chỉ qua FastAPI (`GET /ops/xem-ho-so`), quyền `permission.manage` (khối
-- Phân quyền — chỉ Quản lý). KHÔNG `ops.view`/`audit.view`: từ "mở full lego"
-- 30/09 gần như mọi tài khoản nội bộ có hai quyền ấy. Không mở cho
-- `authenticated` qua PostgREST. Chạy lại được.

CREATE TABLE IF NOT EXISTS public.nhat_ky_xem_ho_so (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    staff_id          uuid NOT NULL REFERENCES public.staff (id) ON DELETE RESTRICT,
    -- Vai LÚC XEM (vai đổi được về sau; nhật ký phải nói đúng lúc ấy là ai).
    vai               text NOT NULL,
    clinic_patient_id uuid NOT NULL,
    loai              text NOT NULL,
    -- id bản ghi được mở (lượt khám, phiếu, tệp…); NULL = cả hồ sơ khách.
    doi_tuong_id      text,
    -- Mẫu đường dẫn của cửa API ("GET /api/v1/patients/{patient_id}"), không
    -- đường dẫn thật (đường thật có thể mang tham số tìm kiếm = tên/SĐT).
    cua               text NOT NULL,
    xem_luc           timestamptz NOT NULL DEFAULT now(),
    khung             timestamptz NOT NULL
        DEFAULT date_bin('5 minutes', now(), timestamptz '2000-01-01 00:00:00+00'),
    CONSTRAINT nhat_ky_xem_ho_so_loai_ck CHECK (loai IN (
        'ho_so_khach',          -- thông tin hành chính + tiền sử của khách
        'lich_su_kham',         -- danh sách / dòng thời gian các lượt khám
        'phieu_kham',           -- bệnh án, phiếu khám, ghi chú tư vấn, sinh hiệu
        'ket_qua',              -- kết quả dịch vụ / xét nghiệm / siêu âm
        'tep_ket_qua',          -- ảnh / video / PDF kết quả
        'don_thuoc',            -- đơn thuốc
        'ban_in'                -- bản in phiếu khám / kết quả
    )),
    CONSTRAINT nhat_ky_xem_ho_so_cua_ck CHECK (length(cua) BETWEEN 1 AND 200)
);

COMMENT ON TABLE public.nhat_ky_xem_ho_so IS
'Ai đã mở hồ sơ khách nào, lúc nào, qua cửa API nào (24/11/2026, NĐ 356/2025). Chỉ định danh, không nội dung. Chỉ thêm; gộp theo khung 5 phút.';

CREATE UNIQUE INDEX IF NOT EXISTS ux_nhat_ky_xem_ho_so_gop
    ON public.nhat_ky_xem_ho_so
       (clinic_id, staff_id, clinic_patient_id, loai, cua, doi_tuong_id, khung)
    NULLS NOT DISTINCT;
CREATE INDEX IF NOT EXISTS ix_nhat_ky_xem_ho_so_luc
    ON public.nhat_ky_xem_ho_so (clinic_id, xem_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_xem_ho_so_khach
    ON public.nhat_ky_xem_ho_so (clinic_id, clinic_patient_id, xem_luc DESC);

DROP TRIGGER IF EXISTS trg_nhat_ky_xem_ho_so_chi_them ON public.nhat_ky_xem_ho_so;
CREATE TRIGGER trg_nhat_ky_xem_ho_so_chi_them
    BEFORE UPDATE OR DELETE ON public.nhat_ky_xem_ho_so
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

-- TRUNCATE không qua trigger dòng — chặn riêng.
DROP TRIGGER IF EXISTS trg_nhat_ky_xem_ho_so_khong_truncate ON public.nhat_ky_xem_ho_so;
CREATE TRIGGER trg_nhat_ky_xem_ho_so_khong_truncate
    BEFORE TRUNCATE ON public.nhat_ky_xem_ho_so
    FOR EACH STATEMENT EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

-- RLS bật, KHÔNG có policy cho `authenticated`/`anon` → PostgREST không đọc được.
-- Backend (service role) bỏ qua RLS và tự lọc clinic_id + quyền ở FastAPI.
ALTER TABLE public.nhat_ky_xem_ho_so ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.nhat_ky_xem_ho_so FROM anon, authenticated;
GRANT SELECT, INSERT ON public.nhat_ky_xem_ho_so TO service_role;
