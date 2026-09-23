-- Đường khám chính hỏi QUYỀN, không hỏi vai (CORE-B3, 23/09/2026).
--
-- Check-in → sinh hiệu → khám → chỉ định → thực hiện → duyệt kết quả → thu
-- tiền dịch vụ nay đều hỏi `capability_grant`. Bốn khối mới, tách theo ĐÚNG
-- ranh giới vai đang có để không ai được/mất việc gì khi chuyển:
--
--   kham           clinical.consult.perform   bác sĩ, thư ký    (CONSULT_ROLES)
--   ghi_benh_an    clinical.record.write      bác sĩ, thư ký, BS siêu âm
--   hoan_tat_kham  clinical.consult.finalize  bác sĩ            (khoá hồ sơ)
--   duyet_ket_qua  result.review.approve      bác sĩ, BS siêu âm
--
-- Hai chỗ preset cũ lệch với code, sửa luôn ở đây:
--   * CASHIER_THUOC có `thu_tien_dv` trong khi code chỉ cho vai này thu tiền
--     THUỐC. Giữ nguyên thì thu tiền dịch vụ chuyển sang quyền là vai này tự
--     dưng thu được tiền dịch vụ. Bỏ khỏi preset + xoá các dòng HỆ THỐNG tự
--     chép (granted_by trống) — dòng quản lý cấp tay giữ nguyên.
--   * (catalogue) MANAGEMENT từng là `list(KHOI)` — tự nhận mọi khối mới, kể cả
--     khối chuyên môn. Nhóm mẫu trong database vốn đã liệt kê rõ; code theo.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('kham', 'Khám bệnh', 'consultation',
     'Gọi khách vào, bắt đầu khám, khám xong chuyển bước'),
    ('ghi_benh_an', 'Ghi bệnh án', 'consultation', 'Ghi ghi chú khám và bệnh án'),
    ('hoan_tat_kham', 'Hoàn tất khám', 'consultation',
     'Hoàn tất lượt khám — khoá hồ sơ; sửa sau đó phải đính chính'),
    ('duyet_ket_qua', 'Duyệt kết quả', 'result', 'Bác sĩ duyệt kết quả cận lâm sàng')
ON CONFLICT (ma) DO NOTHING;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang) VALUES
    ('clinical.consult.perform', 'Gọi khách, bắt đầu khám, khám xong',
     'kham', 'consultation', 'clinical', false),
    ('clinical.record.write', 'Ghi ghi chú khám và bệnh án',
     'ghi_benh_an', 'consultation', 'clinical', false),
    ('clinical.consult.finalize', 'Hoàn tất khám (khoá hồ sơ)',
     'hoan_tat_kham', 'consultation', 'clinical', true),
    ('result.review.approve', 'Duyệt kết quả cận lâm sàng',
     'duyet_ket_qua', 'result', 'clinical', true)
ON CONFLICT (ma) DO NOTHING;

-- Thêm khối vào nhóm mẫu HỆ THỐNG (quản lý có thể đã sửa nhóm — chỉ thêm,
-- không ghi đè, và chạy lại không nhân đôi).
UPDATE public.quyen_preset p
   SET khoi = (SELECT array_agg(DISTINCT k ORDER BY k)
                 FROM unnest(p.khoi || v.them) AS k)
  FROM (VALUES
          ('DOCTOR', ARRAY['kham', 'ghi_benh_an', 'hoan_tat_kham', 'duyet_ket_qua']),
          ('TKYK', ARRAY['kham', 'ghi_benh_an']),
          ('ULTRASOUND_DOCTOR', ARRAY['ghi_benh_an', 'duyet_ket_qua'])
       ) AS v(ma, them)
 WHERE p.ma = v.ma AND p.he_thong
   AND NOT (p.khoi @> v.them);

UPDATE public.quyen_preset
   SET khoi = array_remove(khoi, 'thu_tien_dv')
 WHERE ma = 'CASHIER_THUOC' AND he_thong AND 'thu_tien_dv' = ANY(khoi);

DELETE FROM public.capability_grant
 WHERE tu_preset = 'CASHIER_THUOC' AND tu_khoi = 'thu_tien_dv'
   AND granted_by IS NULL;

-- Người đang làm nhận các khối mới theo vai. Ai đã có/đã bị thu quyền nào thì
-- giữ nguyên (xem cap_quyen_theo_preset, migration 20260923000016).
SELECT public.cap_quyen_cho_moi_thanh_vien();
