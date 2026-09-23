-- Quyền xác nhận tệp kết quả vào hệ quyền MỚI (CORE-B2, 23/09/2026).
--
-- Trước đây có HAI hệ quyền chạy song song: `capability_grant` (màn /phan-quyen)
-- và `staff_capability` cũ (màn /nhan-su, đúng một quyền `ket_qua.xac_nhan`).
-- Từ migration này `capability_grant` là nguồn DUY NHẤT: quyền xác nhận thành
-- `result.file.confirm` trong khối riêng `xac_nhan_ket_qua`.
--
-- Khối riêng, KHÔNG nằm trong preset nào: trước đây quyền này chỉ có ai được
-- tick tay; gộp vào khối `ket_qua` là tự dưng cả bác sĩ, thư ký, điều dưỡng
-- xác nhận được tệp của đối tác.
--
-- `staff_capability` KHÔNG bị xoá: dữ liệu cũ còn đó để tra. Không code nào
-- đọc/ghi nó nữa. Bảng cũ không có clinic_id, nên chép sang MỌI phòng khám người
-- đó đang làm (trước đây người làm ≥2 phòng khám bị chặn hết — giờ quyền theo
-- từng phòng khám nên không cần chặn thế nữa).

INSERT INTO public.work_pack (ma, ten, module, mo_ta)
VALUES ('xac_nhan_ket_qua', 'Xác nhận tệp kết quả', 'result',
        'Xác nhận hoặc từ chối tệp kết quả đối tác gửi về')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES ('result.file.confirm', 'Xác nhận / từ chối / thu hồi tệp kết quả',
        'xac_nhan_ket_qua', 'result', 'clinical', false)
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, ly_do)
SELECT m.clinic_id, sc.staff_id, 'result.file.confirm', 'xac_nhan_ket_qua',
       'Chuyển từ staff_capability ket_qua.xac_nhan (23/09/2026)'
  FROM public.staff_capability sc
  JOIN public.clinic_membership m ON m.staff_id = sc.staff_id AND m.is_active
 WHERE sc.capability = 'ket_qua.xac_nhan'
   AND NOT EXISTS (
         SELECT 1 FROM public.capability_grant g
          WHERE g.clinic_id = m.clinic_id AND g.staff_id = sc.staff_id
            AND g.capability = 'result.file.confirm')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE public.staff_capability IS
    'NGHỈ từ 23/09/2026 — chỉ còn để tra lịch sử. Quyền thật ở capability_grant (result.file.confirm).';
