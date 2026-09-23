-- Bỏ hàng rào chứng chỉ hành nghề + Quản lý có MỌI khối (24/09/2026).
--
-- Tuyền chốt: "bỏ chứng chỉ này đi" và "quản lý quyền cao nhất — có module đó
-- thì mọi quyền của nó có cả; giờ chưa cần cầu kì". Ai được làm gì = khối được
-- cấp, hết. Cột `chung_chi_lam_sang` GIỮ (mọi dòng false) để sau này phòng khám
-- cần thì bật lại mà không phải đổi lược đồ; không lệnh nào đọc nó để chặn nữa.

UPDATE public.capability SET chung_chi_lam_sang = false WHERE chung_chi_lam_sang;

-- Nhóm mẫu Quản lý = tất cả khối đang có (hoàn tất khám, duyệt kết quả… vào nốt).
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(w.ma ORDER BY w.ma) FROM public.work_pack w)
 WHERE p.ma = 'MANAGEMENT' AND p.he_thong;

-- Người đang làm nhận khối mới theo nhóm (ai đã bị thu thì giữ nguyên).
SELECT public.cap_quyen_cho_moi_thanh_vien();
