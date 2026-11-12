-- QUYỀN XEM KHO EMAIL KẾT QUẢ (TẠM) — Gmail G1 (docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 1.7).
--
-- Kho chứa MỌI thư kết quả đối tác gửi về Gmail (cả thư cũ, chưa ghép) — dữ liệu sức khoẻ.
-- "Kho tạm để mình tôi xem" (Tuyền 09/11): khối KHÔNG nằm trong nhóm mẫu nào (kể cả Quản lý),
-- KHÔNG nằm trong "mở full"; chỉ cấp riêng từng người ở màn Phân quyền. Mỗi lần mở PDF ghi
-- sự kiện `lab.archive_viewed` (khai ở G2, cùng code phát). Bỏ Kho = thu quyền (dữ liệu giữ).
--
-- Chạy lại được (ON CONFLICT), không BEGIN/COMMIT. Không cấp cho ai ở đây.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('kho_email', 'Kho email kết quả (tạm)', 'partner',
     'Xem mọi thư kết quả đối tác gửi về Gmail phòng khám — chỉ cấp riêng từng người')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('xet_nghiem.kho_email', 'Xem Kho email kết quả xét nghiệm đối tác', 'kho_email',
     'partner', 'clinical', false)
ON CONFLICT (ma) DO NOTHING;

-- Nhóm mẫu được cấp hàng loạt (`cap_quyen_theo_preset`) ⇒ khối cấp riêng không được nằm
-- trong nhóm nào, kể cả nhóm người sửa hay migration "nhóm = mọi khối" chép lại sau này.
-- BỎ KHỐI + cảnh báo, KHÔNG ném (cùng mẫu `chan_cap_quyen_noi_bo`, 20261009880000): migration
-- cũ 20260924000015 ghi "Quản lý = mọi work_pack"; chạy lại toàn bộ migration (job CI
-- database) với CHECK thì gãy, với trigger thì xong mà Kho email vẫn không lọt vào nhóm.
-- Lệnh lưu nhóm ở permission_service vẫn từ chối rõ ràng cho người bấm.
CREATE OR REPLACE FUNCTION public.bo_khoi_cap_rieng_khoi_nhom()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    IF 'kho_email' = ANY (NEW.khoi) THEN
        RAISE WARNING 'Bỏ khối cấp riêng kho_email khỏi nhóm mẫu % — chỉ cấp từng người',
            NEW.ma;
        NEW.khoi := array_remove(NEW.khoi, 'kho_email');
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_bo_khoi_cap_rieng_khoi_nhom ON public.quyen_preset;
CREATE TRIGGER trg_bo_khoi_cap_rieng_khoi_nhom
    BEFORE INSERT OR UPDATE OF khoi ON public.quyen_preset
    FOR EACH ROW EXECUTE FUNCTION public.bo_khoi_cap_rieng_khoi_nhom();
