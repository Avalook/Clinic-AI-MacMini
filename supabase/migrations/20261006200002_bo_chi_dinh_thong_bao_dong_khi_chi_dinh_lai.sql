-- THÔNG BÁO "CHỈ ĐỊNH BỊ BỎ" ĐỔI THEO (Tuyền thử thật 06/10/2026).
--
-- Quản lý thay bác sĩ bỏ chỉ định → bác sĩ chính nhận thông báo (nút DUY NHẤT
-- Hoàn tác). Hoàn tác bằng nút đóng thông báo (20261006200000). Nhưng nếu người
-- bỏ TICK LẠI chính dịch vụ ấy ở danh mục (một chỉ định MỚI, không phải hoàn
-- tác), thông báo cũ vẫn treo "bị bỏ" — nội dung sai, và nút Hoàn tác của nó
-- chắc chắn bị từ chối (DA_CO_CHI_DINH_MOI).
--
-- Nay: sổ có dòng THÊM cho một mục (cùng lượt, cùng nhóm, cùng mã) → mọi thông
-- báo "chỉ định bị bỏ" còn mở của mục ấy đóng ngay, ghi "Đã chỉ định lại". Ép ở
-- Postgres (trigger trên sổ) nên mọi đường thêm chỉ định / tick dịch vụ khám
-- đều đi qua; chuông nghe bảng `thong_bao` nên đổi tức thì.
--
-- Chạy lại được.

CREATE OR REPLACE FUNCTION public.so_sua_chi_dinh_dong_bao_khi_them()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.hanh_dong <> 'THEM' OR NEW.nhom = 'THUOC' OR NEW.ma_muc IS NULL THEN
        RETURN NULL;
    END IF;
    UPDATE public.thong_bao t
       SET da_xu_ly_luc = now(),
           da_xu_ly_boi = NEW.boi_staff_id,
           ghi_chu_xu_ly = 'Đã chỉ định lại',
           da_doc_luc = coalesce(t.da_doc_luc, now())
     WHERE t.clinic_id = NEW.clinic_id
       AND t.nguon = 'bo_chi_dinh'
       AND t.da_xu_ly_luc IS NULL
       AND t.nguon_id IN (
           SELECT s.id::text FROM public.so_sua_chi_dinh s
            WHERE s.clinic_id = NEW.clinic_id AND s.visit_id = NEW.visit_id
              AND s.hanh_dong = 'BO' AND s.nhom = NEW.nhom
              AND s.ma_muc = NEW.ma_muc AND s.hoan_tac_luc IS NULL);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_so_sua_chi_dinh_dong_bao ON public.so_sua_chi_dinh;
CREATE TRIGGER trg_so_sua_chi_dinh_dong_bao
    AFTER INSERT ON public.so_sua_chi_dinh
    FOR EACH ROW EXECUTE FUNCTION public.so_sua_chi_dinh_dong_bao_khi_them();
