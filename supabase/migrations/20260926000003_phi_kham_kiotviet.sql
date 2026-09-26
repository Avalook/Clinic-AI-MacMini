-- PHÍ KHÁM THEO KIOTVIET (26/09/2026 — lát 2 bản giao diện mẫu). Mã `KHAM_*`
-- (tiền khám theo loại khám) đều đang "GIÁ GIẢ ĐỊNH 17/09 — phòng khám cần sửa".
-- Ghép theo TÊN với nhóm "Phí khám" của KiotViet — chỉ 4 cặp khớp rõ:
--   KHAM_HIEM_MUON ← SP000003 Khám mong con lần đầu      400.000
--   KHAM_PHU_KHOA  ← SP000005 Khám tư vấn viêm nhiễm PK  300.000
--   KHAM_NAM_KHOA  ← SP000007 Khám nam khoa              300.000
--   KHAM_SAN_1     ← SP000079 Khám quản lý thai          200.000
-- Loại khám không có mã KV tương ứng (Nội tiết, Thủ thuật, Sàn chậu, …) GIỮ
-- NGUYÊN — quản lý sửa ở Bảng giá. Tên loại khám giữ nguyên (màn đặt lịch đọc).
-- Chỉ đè khi dòng vẫn còn nhãn "GIÁ GIẢ ĐỊNH" (chưa ai sửa tay). Chạy lại được.

WITH ghep (code, ma, gia) AS (
  VALUES ('KHAM_HIEM_MUON', 'SP000003', 400000::numeric),
         ('KHAM_PHU_KHOA',  'SP000005', 300000::numeric),
         ('KHAM_NAM_KHOA',  'SP000007', 300000::numeric),
         ('KHAM_SAN_1',     'SP000079', 200000::numeric)
)
UPDATE public.service_price p
   SET ma_kiotviet = g.ma,
       unit_price = g.gia,
       category = 'Tiền khám · KiotViet 26/09/2026',
       updated_at = now()
  FROM ghep g
 WHERE p."group" = 'dich_vu' AND p.service_code = g.code
   AND p.category LIKE '%GIÁ GIẢ ĐỊNH%'
   AND NOT EXISTS (SELECT 1 FROM public.service_price x
                    WHERE x.clinic_id = p.clinic_id AND x.ma_kiotviet = g.ma);
