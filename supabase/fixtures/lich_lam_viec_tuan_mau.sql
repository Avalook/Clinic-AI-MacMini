-- Lịch làm việc chuẩn của phòng khám — MỘT TUẦN MẪU, trải ra nhiều tuần.
--
-- NGUỒN: sheet "LLV 06-2026" trong "BẢNG LÀM VIỆC 05.2026.xlsx" (Data khách
-- gửi). Sheet đó chỉ có đúng một tuần: 01/06–07/06/2026, và 01/06 là thứ Hai
-- nên thứ trong tuần khớp thẳng sang mọi tuần khác.
--
-- VÌ SAO LÀ MỘT TUẦN LẶP LẠI, KHÔNG PHẢI LỊCH TỪNG THÁNG. Quang (07/08/2026):
-- "lịch rất ít thay đổi". Phòng khám vẫn sửa từng ô trên màn Lịch làm việc;
-- file này chỉ lo cho những tuần CHƯA AI ĐỘNG TỚI.
--
-- CHỐT AN TOÀN: một tuần đã có dù chỉ MỘT dòng thì bỏ qua nguyên tuần. Đó là
-- tuần phòng khám đã tự xếp — ghi đè lên nó là xoá công của người ta. Nên file
-- này chạy lại bao nhiêu lần cũng không đổi gì thêm.
--
-- TRA THEO short_name, KHÔNG theo full_name. full_name của bác sĩ đã đổi
-- thành tên đầy đủ kèm học hàm ("BS Thành" → "TS.BS. Phan Chí Thành"), nên
-- khớp theo full_name là lần chạy sau không tìm ra ai. short_name không đổi.
--
--   psql -v tu_ngay="'2026-08-03'" -v so_tuan=26 -f lich_lam_viec_tuan_mau.sql
--
-- `tu_ngay` PHẢI là một thứ Hai; script tự lùi về thứ Hai nếu không phải.

\set tu_ngay :tu_ngay
\set so_tuan :so_tuan

WITH mau(thu, ca, tram, ten_bang, ten_ngan, thu_tu) AS (
    VALUES
        (1, 'FULL', 'LAY_MAU', 'Quỳnh Anh', 'Quỳnh Anh', 0),
        (1, 'FULL', 'LE_TAN', 'Thư', 'Thư', 0),
        (1, 'FULL', 'LICH_KHAM', 'BS NAM', 'Nam', 0),
        (1, 'FULL', 'PHU_BS_SA', 'BS NAM', 'Nam', 0),
        (1, 'FULL', 'PHU_BS_SA', 'Dương Trang', 'Dương Trang', 10),
        (2, 'FULL', 'LAY_MAU', 'Hải Yến', 'Hải Yến', 0),
        (2, 'FULL', 'LE_TAN', 'Dương Trang', 'Dương Trang', 0),
        (2, 'FULL', 'LE_TAN', 'Quỳnh Anh', 'Quỳnh Anh', 10),
        (2, 'FULL', 'LICH_KHAM', 'BS THÀNH', 'Thành', 0),
        (2, 'FULL', 'LICH_KHAM', 'BS THIỆP', 'Thiệp', 10),
        (2, 'FULL', 'MAY_NGOAI', 'Tiên', NULL, 10),
        (2, 'FULL', 'MAY_TRONG', 'Hải', 'Thanh Hải', 10),
        (2, 'FULL', 'PHONG_NGOAI_MOR', 'Thúy', 'Diễm Thúy', 10),
        (2, 'FULL', 'PHU_BS_KHAM', 'BS THÀNH', 'Thành', 0),
        (2, 'FULL', 'PHU_BS_KHAM', 'Thư', 'Thư', 10),
        (2, 'FULL', 'PHU_BS_KHAM', 'Hà Vũ', 'Hà Vũ', 11),
        (2, 'FULL', 'PHU_BS_SA', 'BS THIỆP', 'Thiệp', 0),
        (2, 'FULL', 'PHU_BS_SA', 'Vân Anh', 'Vân Anh', 10),
        (2, 'FULL', 'TLYK', 'Nam', 'Duy Nam', 10),
        (3, 'FULL', 'LAY_MAU', 'Hải Yến', 'Hải Yến', 0),
        (3, 'FULL', 'LE_TAN', 'Quỳnh Anh', 'Quỳnh Anh', 0),
        (3, 'FULL', 'LICH_KHAM', 'BS HẰNG', 'Hằng', 0),
        (3, 'FULL', 'LICH_KHAM', 'BS LINH Nam khoa', 'Linh NK', 10),
        (3, 'FULL', 'MAY_TRONG', 'BS Linh Nam khoa', 'Linh NK', 0),
        (3, 'FULL', 'MAY_TRONG', 'Huế', 'Huế', 10),
        (3, 'FULL', 'PHU_BS_SA', 'BS HẰNG', 'Hằng', 0),
        (3, 'FULL', 'PHU_BS_SA', 'Vân Anh', 'Vân Anh', 10),
        (3, 'FULL', 'PHU_BS_SA', 'Phạm Hà', 'Hà Phạm', 11),
        (4, 'FULL', 'LAY_MAU', 'Hải Yến', 'Hải Yến', 0),
        (4, 'FULL', 'LE_TAN', 'Thư', 'Thư', 0),
        (4, 'FULL', 'LE_TAN', 'Phương Anh', 'Phương Anh', 10),
        (4, 'FULL', 'LICH_KHAM', 'BS THÀNH', 'Thành', 0),
        (4, 'FULL', 'LICH_KHAM', 'BS NAM', 'Nam', 10),
        (4, 'FULL', 'MAY_NGOAI', 'Linh', 'Hương Linh', 10),
        (4, 'FULL', 'MAY_TRONG', 'Hải', 'Thanh Hải', 10),
        (4, 'FULL', 'PHONG_NGOAI_MOR', 'Dương Trang', 'Dương Trang', 10),
        (4, 'FULL', 'PHU_BS_KHAM', 'BS THÀNH', 'Thành', 0),
        (4, 'FULL', 'PHU_BS_KHAM', 'Hằng', 'Hằng LT', 10),
        (4, 'FULL', 'PHU_BS_KHAM', 'Trang Lê', 'Trang Lê', 11),
        (4, 'FULL', 'PHU_BS_SA', 'BS NAM', 'Nam', 0),
        (4, 'FULL', 'PHU_BS_SA', 'Hà Phạm', 'Hà Phạm', 10),
        (4, 'FULL', 'TLYK', 'Thanh Phương', 'Thanh Phương', 10),
        (5, 'FULL', 'LAY_MAU', 'Phương Anh', 'Phương Anh', 0),
        (5, 'FULL', 'LE_TAN', 'Hằng', 'Hằng LT', 0),
        (5, 'FULL', 'LICH_KHAM', 'BS HÙNG', 'Hùng', 0),
        (5, 'FULL', 'LICH_KHAM', 'BS LINH Nam khoa', 'Linh NK', 10),
        (5, 'FULL', 'MAY_TRONG', 'BS Linh Nam khoa', 'Linh NK', 0),
        (5, 'FULL', 'MAY_TRONG', 'Thư', 'Thư', 10),
        (5, 'FULL', 'PHU_BS_SA', 'BS HÙNG', 'Hùng', 0),
        (5, 'FULL', 'PHU_BS_SA', 'Hà Phạm', 'Hà Phạm', 10),
        (6, 'SANG', 'LAY_MAU', 'Hải Yến', 'Hải Yến', 0),
        (6, 'CHIEU', 'LAY_MAU', 'Hải Yến', 'Hải Yến', 0),
        (6, 'SANG', 'LE_TAN', 'Dương Trang', 'Dương Trang', 0),
        (6, 'CHIEU', 'LE_TAN', 'Trang Lê', 'Trang Lê', 0),
        (6, 'SANG', 'LE_TAN', 'Trang A', NULL, 10),
        (6, 'CHIEU', 'LE_TAN', 'Trang A', NULL, 10),
        (6, 'SANG', 'LICH_KHAM', 'BS THÀNH', 'Thành', 0),
        (6, 'CHIEU', 'LICH_KHAM', 'BS THÀNH', 'Thành', 0),
        (6, 'SANG', 'LICH_KHAM', 'BS HÙNG', 'Hùng', 10),
        (6, 'CHIEU', 'LICH_KHAM', 'BS QUYẾT', 'Quyết', 10),
        (6, 'SANG', 'MAY_NGOAI', 'Thanh Phương', 'Thanh Phương', 10),
        (6, 'CHIEU', 'MAY_NGOAI', 'Huế', 'Huế', 10),
        (6, 'SANG', 'MAY_TRONG', 'Thủy Tiên', 'Thủy Tiên', 10),
        (6, 'CHIEU', 'MAY_TRONG', 'Thủy Tiên', 'Thủy Tiên', 10),
        (6, 'SANG', 'PHONG_NGOAI_MOR', 'Linh', 'Hương Linh', 10),
        (6, 'CHIEU', 'PHONG_NGOAI_MOR', 'Linh', 'Hương Linh', 10),
        (6, 'SANG', 'PHU_BS_KHAM', 'BS THÀNH', 'Thành', 0),
        (6, 'CHIEU', 'PHU_BS_KHAM', 'BS THÀNH', 'Thành', 0),
        (6, 'SANG', 'PHU_BS_KHAM', 'Trang Lê', 'Trang Lê', 10),
        (6, 'CHIEU', 'PHU_BS_KHAM', 'Hà Vũ', 'Hà Vũ', 10),
        (6, 'SANG', 'PHU_BS_KHAM', 'Hà Vũ', 'Hà Vũ', 11),
        (6, 'CHIEU', 'PHU_BS_KHAM', 'Hà Phạm', 'Hà Phạm', 11),
        (6, 'SANG', 'PHU_BS_SA', 'BS HÙNG', 'Hùng', 0),
        (6, 'CHIEU', 'PHU_BS_SA', 'BS QUYẾT', 'Quyết', 0),
        (6, 'SANG', 'PHU_BS_SA', 'Vân Anh', 'Vân Anh', 10),
        (6, 'CHIEU', 'PHU_BS_SA', 'Trang Dương', 'Dương Trang', 10),
        (6, 'SANG', 'TLYK', 'Huế', 'Huế', 10),
        (6, 'CHIEU', 'TLYK', 'Thanh Phương', 'Thanh Phương', 10),
        (7, 'SANG', 'LAY_MAU', 'Phương Anh', 'Phương Anh', 0),
        (7, 'CHIEU', 'LAY_MAU', 'Phương Anh', 'Phương Anh', 0),
        (7, 'SANG', 'LE_TAN', 'Trang Lê', 'Trang Lê', 0),
        (7, 'CHIEU', 'LE_TAN', 'Trang Lê', 'Trang Lê', 0),
        (7, 'SANG', 'LICH_KHAM', 'BS THIỆP', 'Thiệp', 0),
        (7, 'CHIEU', 'LICH_KHAM', 'BS THIỆP', 'Thiệp', 0),
        (7, 'SANG', 'PHU_BS_SA', 'BS THIỆP', 'Thiệp', 0),
        (7, 'CHIEU', 'PHU_BS_SA', 'BS THIỆP', 'Thiệp', 0),
        (7, 'SANG', 'PHU_BS_SA', 'Hà Vũ', 'Hà Vũ', 10),
        (7, 'CHIEU', 'PHU_BS_SA', 'Phạm Hà', 'Hà Phạm', 10),
        (7, 'SANG', 'PHU_BS_SA', 'Hải', 'Thanh Hải', 11),
        (7, 'CHIEU', 'PHU_BS_SA', 'Hải', 'Thanh Hải', 11)
),
-- Thứ Hai của tuần chứa `tu_ngay`, rồi cộng dồn 7 ngày.
goc AS (
    SELECT (:tu_ngay::date - (extract(isodow FROM :tu_ngay::date)::int - 1))::date AS t0
),
tuan AS (
    SELECT (SELECT t0 FROM goc) + (n * 7) AS week_start
      FROM generate_series(0, :so_tuan - 1) AS n
),
-- Phòng khám: file này dựng cho phòng khám DUY NHẤT đang có. Có phòng khám
-- thứ hai thì phải truyền vào, không đoán.
pk AS (SELECT id FROM public.clinic ORDER BY created_at LIMIT 1),
-- Ô ĐẦU CỘT, KHÔNG PHẢI CA TRỰC.
--
-- Ở mọi trạm phụ, dòng `thu_tu = 0` mang tên một BÁC SĨ là tiêu đề cột trong
-- file Excel — nó nói TRẠM NÀY PHỤC VỤ AI, chứ không nói ai đứng ở đó. Bản nạp
-- đầu tiên đọc cả cột thành người và sinh ra 390 ca trực ma trên bản thật:
-- "BS THÀNH · Phụ BS (khám + thuốc)", bác sĩ tự phụ chính mình.
-- Xem 20260809000001 để biết cách phát hiện và dọn.
--
-- Ở trạm KHÔNG có bác sĩ (Lấy máu, Lễ tân…) thì `thu_tu = 0` chỉ là người đầu
-- danh sách — nên điều kiện phải gồm CẢ chức danh, không chỉ số thứ tự.
dau_cot AS (
    SELECT m.thu, m.ca, m.tram, s.id AS bac_si_id
      FROM mau m JOIN public.staff s
        ON s.short_name = m.ten_ngan AND s.is_active
     WHERE m.tram <> 'LICH_KHAM' AND m.thu_tu = 0
       AND s.primary_department = 'DOCTOR'
)
INSERT INTO public.work_roster
    (clinic_id, week_start, work_date, shift, station, staff_id, staff_name,
     sort, status, bac_si_phu_trach_id)
SELECT pk.id,
       t.week_start,
       t.week_start + (m.thu - 1),
       m.ca,
       m.tram,
       s.id,                     -- NULL khi tên trong bảng không khớp ai
       m.ten_bang,               -- giữ NGUYÊN chữ trong bảng của phòng khám
       m.thu_tu,
       'APPROVED',
       dc.bac_si_id              -- trạm phụ này phục vụ bác sĩ nào
  FROM tuan t
 CROSS JOIN mau m
 CROSS JOIN pk
  LEFT JOIN public.staff s
    ON s.short_name = m.ten_ngan AND s.is_active
  LEFT JOIN dau_cot dc
    ON dc.thu = m.thu AND dc.ca = m.ca AND dc.tram = m.tram
 WHERE NOT EXISTS (
         SELECT 1 FROM public.work_roster w
          WHERE w.clinic_id = pk.id AND w.week_start = t.week_start
       )
   -- Bỏ chính dòng đầu cột đi: thông tin của nó đã nằm ở cột bên phải.
   AND NOT EXISTS (
         SELECT 1 FROM dau_cot d
          WHERE d.thu = m.thu AND d.ca = m.ca AND d.tram = m.tram
            AND d.bac_si_id = s.id
       );

-- Nói ra ngay cái không khớp, đừng để nó lặng lẽ thành ô trống trên màn.
DO $$
DECLARE thieu int;
BEGIN
    SELECT count(DISTINCT staff_name) INTO thieu
      FROM public.work_roster WHERE staff_id IS NULL;
    IF thieu > 0 THEN
        RAISE NOTICE '% tên trong bảng chưa ghép được nhân sự nào — xem: SELECT DISTINCT staff_name FROM work_roster WHERE staff_id IS NULL;', thieu;
    END IF;
END $$;
