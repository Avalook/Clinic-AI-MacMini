-- Bổ sung 16 thuốc còn thiếu so với bảng thuốc Tuyền gửi 16/09/2026.
--
-- Đối chiếu ảnh bảng thuốc (9 dòng) với `drug_catalog` (64 dòng, nạp từ bản
-- bàn giao cũ): thiếu 16, và có 12 dòng trong database không còn trong ảnh.
--
-- CHỈ THÊM, KHÔNG XOÁ — và đây là quyết định chứ không phải lười.
--
-- Trong 12 dòng "thừa" có ít nhất hai cái trông như ĐỔI TÊN chứ không phải bỏ:
-- `Aspirin` ↔ `Aspilete` (Aspilete là một biệt dược của aspirin), và
-- `Folic Mum` ↔ `5MTHF/ Folic mum`. Xoá một thuốc đang nằm trong đơn của bệnh
-- nhân là làm hỏng đơn ấy; đổi tên mà tưởng là bỏ thì phòng khám mất lịch sử kê
-- của chính thuốc đó. Cả hai đều tệ hơn việc để một dòng thừa nằm im.
--
-- Danh sách 12 dòng cần Tuyền xác nhận (bỏ hẳn / đổi tên / vẫn dùng):
--   L1 Venice · Aspirin · Folic Mum · Ferlatum
--   L2 Endokirogen
--   L3 Cyclo Progynova
--   L4 Hyalogyn
--   L7 Cumlaude Lubripiu HA
--   L8 Cyclo
--   L9 L-Agrinine · Kingseal · Glutathione
-- Xác nhận xong thì tắt bằng `is_active = FALSE` (đừng xoá dòng — đơn cũ còn
-- trỏ tới nó).
--
-- `needs_review = TRUE` cho 16 dòng mới: tên đọc từ ẢNH nên có thể sai chính tả,
-- và chưa dòng nào có giá. Màn danh mục lọc được theo cờ này để người phụ trách
-- soát lại trước khi đem ra kê đơn.

BEGIN;

-- Tên bảng xuống dòng, KHÔNG phải để cho đẹp: chốt trước commit nhận diện bản
-- dump database bằng mẫu `^INSERT INTO public\.` ở đầu dòng, và nó chặn đúng —
-- một bản dump lọt vào kho hồi 09/08/2026 là lý do chốt ấy tồn tại. Viết liền
-- một dòng thì migration này bị chặn oan. Đừng gộp lại.
INSERT INTO
    public.drug_catalog
    (clinic_id, group_label, name_base, name_raw, variant, needs_review, is_active)
SELECT c.id, v.nhom, v.ten, v.tho, v.bien, TRUE, TRUE
  FROM public.clinic c
  CROSS JOIN (VALUES
      ('L1', 'Aspilete',                 'Aspilete',                     NULL),
      ('L1', '5MTHF/ Folic mum',         '5MTHF/ Folic mum',             NULL),
      ('L1', 'Gemapaxan',                'Gemapaxan',                    NULL),
      ('L2', 'Dunium/ Fetogard',         'Dunium/ Fetogard (10v/15v)',   '10v/15v'),
      ('L3', 'Valiera',                  'Valiera',                      NULL),
      ('L3', 'Dienosis',                 'Dienosis',                     NULL),
      ('L3', 'Betmiga',                  'Betmiga',                      NULL),
      ('L4', 'Filrosy progesteron 200',  'Filrosy progesteron 200 Đ',    'Đ'),
      ('L4', 'Levina 5',                 'Levina 5',                     NULL),
      ('L4', 'Indurat 5',                'Indurat 5 (Đ/ U)',             'Đ/U'),
      ('L4', 'usatestos',                'usatestos Đ',                  'Đ'),
      ('L7', 'Fosamax',                  'Fosamax 2800/5600',            '2800/5600'),
      ('L8', 'isoflavon',                'isoflavon',                    NULL),
      ('L9', 'Mensterona',               'Mensterona',                   NULL),
      ('L9', 'Fersen',                   'Fersen',                       NULL),
      ('L9', 'Avanafil',                 'Avanafil (Flepgo 100)',        'Flepgo 100')
  ) AS v(nhom, ten, tho, bien)
 WHERE NOT EXISTS (
     SELECT 1 FROM public.drug_catalog d
      WHERE d.clinic_id = c.id
        AND lower(d.name_base) = lower(v.ten)
        AND d.variant IS NOT DISTINCT FROM v.bien
 );

-- Chốt kiểm: chạy lại không được thêm dòng nào nữa.
DO $$
DECLARE
    con integer;
BEGIN
    SELECT count(*) INTO con
      FROM public.drug_catalog
     WHERE is_active AND needs_review;
    RAISE NOTICE 'Danh mục thuốc: % dòng chờ soát lại', con;
END $$;

COMMIT;
