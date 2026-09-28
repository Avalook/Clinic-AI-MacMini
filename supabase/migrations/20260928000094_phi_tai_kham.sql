-- PHÍ KHÁM THEO KIOTVIET (Tuyền 28/09/2026: "sửa giá theo file KiotViet").
--
-- Đối chiếu file "DanhSachSanPham_KV21092026-171729-2929.xlsx" (nhóm Phí khám)
-- với bảng giá: mọi dịch vụ đã khớp giá, trừ:
--   * Hiếm muộn TÁI KHÁM — KiotViet SP000004 "Tái khám mong con" 150.000đ; hệ
--     thống tính 400.000đ (giá lần đầu SP000003) cho cả lần tái khám. Thêm dòng
--     "<loại khám> (tái khám)"; bill_service chọn dòng ấy khi lượt là tái khám.
--   * Sàn chậu chuyên sâu 300.000đ = SP000006 → bỏ nhãn giá tạm.
-- Nội tiết và Thủ thuật KHÔNG có trong file → giữ giá tạm, chờ phòng khám.
--
-- Chạy lại được.

INSERT INTO service_price
    (clinic_id, service_code, name, "group", unit_price, ma_kiotviet, billing_owner)
SELECT p.clinic_id, 'KHAM_HIEM_MUON_TAI_KHAM', p.name || ' (tái khám)', 'dich_vu',
       150000, 'SP000004', 'CLINIC'
  FROM public.service_price p
 WHERE p.service_code = 'KHAM_HIEM_MUON'
   AND NOT EXISTS (
       SELECT 1 FROM public.service_price q
        WHERE q.clinic_id = p.clinic_id
          AND q.service_code = 'KHAM_HIEM_MUON_TAI_KHAM');

UPDATE public.service_price
   SET gia_tam = false
 WHERE service_code = 'KHAM_SAN_CHAU' AND unit_price = 300000 AND gia_tam;
