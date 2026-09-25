-- Xem nhanh tình hình kho thuốc — CHỈ ĐỌC, chỉ số đếm/tổng (không tên bệnh nhân).
--
--   ssh clinic-vps-moi 'docker exec -i clinicai_db psql -U postgres -d postgres' < scripts/xem-kho-thuoc.sql

SET default_transaction_read_only = on;

\echo '== Danh mục thuốc'
SELECT count(*) AS tong,
       count(*) FILTER (WHERE is_active) AS dang_dung,
       count(*) FILTER (WHERE needs_review) AS can_soat,
       count(*) FILTER (WHERE coalesce(unit_price, 0) = 0) AS chua_co_gia_ban
FROM drug_catalog;

\echo '== Thuốc cần soát / chưa có giá bán (tên thuốc)'
SELECT name_raw, unit_price, needs_review FROM drug_catalog
WHERE needs_review OR coalesce(unit_price, 0) = 0 ORDER BY name_raw;

\echo '== Lô thuốc'
SELECT count(*) AS lo,
       count(DISTINCT drug_catalog_id) AS so_thuoc_co_lo,
       count(*) FILTER (WHERE quantity_on_hand > 0) AS lo_con_hang,
       count(*) FILTER (WHERE quantity_on_hand = 0) AS lo_het_hang,
       count(*) FILTER (WHERE expiry_date < current_date AND quantity_on_hand > 0) AS het_han_van_con,
       count(*) FILTER (WHERE expiry_date BETWEEN current_date AND current_date + 90
                          AND quantity_on_hand > 0) AS sap_het_han_90_ngay,
       count(*) FILTER (WHERE expiry_date IS NULL) AS khong_ghi_han,
       count(*) FILTER (WHERE coalesce(cost_price, 0) = 0) AS khong_gia_von
FROM drug_batch;

\echo '== Thuốc đang dùng mà KHÔNG còn lô nào có hàng'
SELECT count(*) FROM drug_catalog d
WHERE d.is_active AND NOT EXISTS (
  SELECT 1 FROM drug_batch b WHERE b.drug_catalog_id = d.id AND b.quantity_on_hand > 0);

\echo '== Phiếu kho theo loại'
SELECT txn_type, count(*) AS so_phieu, sum(quantity) AS tong_so_luong
FROM inventory_txn GROUP BY 1 ORDER BY 1;

\echo '== Phiếu kho theo ngày'
SELECT performed_at::date AS ngay, txn_type, count(*)
FROM inventory_txn GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== Lô có tồn KHÁC tổng phiếu kho (phải = 0)'
SELECT count(*) FROM drug_batch b
LEFT JOIN (SELECT drug_batch_id, sum(quantity) AS q FROM inventory_txn GROUP BY 1) s
  ON s.drug_batch_id = b.id
WHERE b.quantity_on_hand <> coalesce(s.q, 0);

\echo '== Dòng đơn thuốc chưa gắn kho'
SELECT count(*) FILTER (WHERE drug_catalog_id IS NULL) AS chua_gan, count(*) AS tong
FROM prescription WHERE removed_at IS NULL;
