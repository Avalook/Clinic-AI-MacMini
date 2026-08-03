-- Thời gian khám là thứ ĐO ĐƯỢC, không phải thứ viết cứng trong mã.
--
-- CÁI ĐANG BỊ THAY. booking_service.suggest_load() và lib/capacity.ts giữ một
-- bảng phút bịa:
--
--     khách mới        → 15 phút  (+12 nếu có siêu âm)
--     khách tái khám   →  5 phút  (+8  nếu có siêu âm)
--
-- Bốn con số đó không đến từ phép đo nào. Chúng được gõ vào một lần rồi trở
-- thành "sự thật" của hệ thống: mọi ô lịch tô màu theo chúng, mọi cảnh báo
-- "khung sắp đầy" tính theo chúng. Không ai từng kiểm xem BS Thành có thật sự
-- mất 15 phút cho một khách mới lúc 18:00 thứ Ba hay không — và nếu ông ấy mất
-- 22 phút thì hệ thống vẫn báo còn trống.
--
-- MÔ HÌNH ĐÚNG, TÁCH LÀM HAI VIỆC KHÁC HẲN NHAU:
--
--   1. GIỚI HẠN đặt lịch = SỐ CHỖ mỗi khung. Do Trưởng ca / Quản lý đặt, sửa
--      được ngay trên giao diện, per-phòng-khám và per-khung-giờ
--      (clinic.settings.booking + booking_override). Đây là luật, người quyết,
--      database thi hành.
--
--   2. THỜI LƯỢNG khám = SỐ LIỆU QUAN SÁT. Không ai đặt, không ai đoán — nó
--      được ĐO từ chính work_item mà bàn khám đang bấm mỗi ngày: bấm "Bắt đầu"
--      ghi started_at, bấm "Hoàn tất" ghi finished_at. Dữ liệu đó đã nằm sẵn
--      trong database từ khi workflow kernel chạy; chưa ai đọc nó.
--
-- ĐỂ LÀM GÌ. Trước mắt: nói cho Trưởng ca biết con số thật khi họ chỉnh số chỗ
-- ("khung 18:00 thứ Ba, BS Thành trung vị 19 phút / 34 ca" thì 2 chỗ/15 phút là
-- quá chật). Về sau: đây chính là tập huấn luyện để hệ thống tự đề xuất số chỗ
-- theo khung giờ × loại khách × bác sĩ, thay vì chờ người ngồi đoán.
--
-- VÌ SAO LÀ VIEW CHỨ KHÔNG PHẢI BẢNG. Một bảng cần đường ghi, cần trigger, cần
-- người nhớ ghi — tức thêm một chỗ nữa để lệch. Dữ liệu thô đã đúng và đã đầy
-- đủ trong work_item; cái thiếu chỉ là một cách đọc nó. Khi số dòng đủ lớn để
-- view chậm thì chuyển thành materialized view + refresh theo lịch, và câu truy
-- vấn bên dưới giữ nguyên.

-- (Không dùng `\set` — đó là lệnh psql, `supabase db push` không hiểu.
--  Xem chú thích trong 20260803000004.)

-- ---------------------------------------------------------------------------
-- 1. Mẫu thô: mỗi bước công việc đã hoàn tất = một quan sát
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW public.v_consultation_duration
WITH (security_invoker = true) AS
SELECT
    w.id                AS work_item_id,
    w.clinic_id,
    w.node_code,
    w.assigned_to       AS staff_id,
    w.visit_id,
    w.appointment_id,
    a.doctor_id,
    a.service_type_id,
    a.patient_kind,
    a.need_sono,
    a.booking_channel,
    w.started_at,
    w.finished_at,
    -- Phút thực tế, làm tròn xuống. NUMERIC để tính trung vị không bị dồn.
    ROUND(EXTRACT(EPOCH FROM (w.finished_at - w.started_at)) / 60.0, 1)
                        AS duration_minutes,
    -- Đặc trưng thời gian, tính theo GIỜ VIỆT NAM. Cột lưu là timestamptz nên
    -- phải đổi múi tường minh — EXTRACT thẳng sẽ ra giờ UTC và mọi thống kê
    -- "theo khung giờ" lệch đúng 7 tiếng, tức vô nghĩa.
    EXTRACT(DOW  FROM w.started_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::int
                        AS vn_weekday,
    EXTRACT(HOUR FROM w.started_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::int
                        AS vn_hour
FROM public.work_item w
LEFT JOIN public.appointment a ON a.id = w.appointment_id
WHERE w.status = 'COMPLETED'
  AND w.started_at IS NOT NULL
  AND w.finished_at IS NOT NULL
  AND w.finished_at > w.started_at
  -- Bỏ mẫu rác. Dưới 1 phút gần như chắc chắn là bấm nhầm hai nút liền nhau;
  -- trên 4 tiếng là quên bấm "Hoàn tất" rồi để máy qua đêm. Cả hai đều là thao
  -- tác của con người chứ không phải thời gian khám, và giữ lại thì trung vị
  -- vẫn ổn nhưng trung bình và p90 hỏng hẳn.
  AND w.finished_at - w.started_at BETWEEN INTERVAL '1 minute'
                                       AND INTERVAL '4 hours';

COMMENT ON VIEW public.v_consultation_duration IS
    'Thời lượng THỰC TẾ của từng bước công việc đã hoàn tất, kèm đặc trưng '
    '(bác sĩ, dịch vụ, loại khách, thứ, giờ VN). Nguồn: work_item.started_at → '
    'finished_at. Đây là dữ liệu quan sát, KHÔNG phải cấu hình.';

-- ---------------------------------------------------------------------------
-- 2. Thống kê: con số để người đọc, và để máy học
-- ---------------------------------------------------------------------------
-- TRUNG VỊ, KHÔNG PHẢI TRUNG BÌNH. Một ca kéo dài 90 phút vì biến chứng kéo
-- trung bình của cả khung lên và làm nó mô tả sai một buổi bình thường. Trung vị
-- trả lời "một ca điển hình mất bao lâu"; p90 trả lời "cần bao nhiêu để hiếm khi
-- vỡ lịch". Xếp lịch cần cả hai.

CREATE OR REPLACE VIEW public.v_consultation_duration_stats
WITH (security_invoker = true) AS
SELECT
    clinic_id,
    node_code,
    doctor_id,
    service_type_id,
    patient_kind,
    vn_weekday,
    vn_hour,
    COUNT(*)                                                    AS sample_count,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_minutes)::numeric, 1)
                                                                AS median_minutes,
    ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY duration_minutes)::numeric, 1)
                                                                AS p90_minutes,
    MIN(duration_minutes)                                       AS min_minutes,
    MAX(duration_minutes)                                       AS max_minutes,
    MAX(finished_at)                                            AS last_observed_at
FROM public.v_consultation_duration
GROUP BY clinic_id, node_code, doctor_id, service_type_id, patient_kind,
         vn_weekday, vn_hour;

COMMENT ON VIEW public.v_consultation_duration_stats IS
    'Trung vị / p90 thời lượng theo (bác sĩ, dịch vụ, loại khách, thứ, giờ VN) '
    'kèm sample_count. sample_count NHỎ nghĩa là con số chưa đáng tin — người '
    'đọc và mô hình đều phải nhìn nó trước khi tin phần còn lại.';

-- ---------------------------------------------------------------------------
-- 3. Quyền đọc
-- ---------------------------------------------------------------------------
-- security_invoker = true ⇒ view chạy dưới quyền NGƯỜI GỌI, nên RLS của
-- work_item và appointment vẫn áp dụng nguyên vẹn: mỗi phòng khám chỉ thấy số
-- liệu của mình. Không có SECURITY DEFINER nào ở đây để lách qua ranh giới đó.

GRANT SELECT ON public.v_consultation_duration        TO authenticated, service_role;
GRANT SELECT ON public.v_consultation_duration_stats  TO authenticated, service_role;

-- Chỉ mục cho đường quét chính (lọc theo phòng khám + đã hoàn tất).
CREATE INDEX IF NOT EXISTS idx_work_item_completed_duration
    ON public.work_item (clinic_id, node_code, finished_at)
    WHERE status = 'COMPLETED' AND started_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. thanh_min / sono_min: đổi ý nghĩa, không xoá cột
-- ---------------------------------------------------------------------------
-- Hai cột này đang giữ con số từ bảng viết cứng. Không DROP: dữ liệu cũ vẫn là
-- lịch sử có thật của những gì hệ thống đã tin, và xoá đi thì không đối chiếu
-- được "hệ thống đoán bao nhiêu" với "thực tế bao nhiêu" — mà chính phép đối
-- chiếu đó là thứ cho biết mô hình sau này có khá hơn không.
--
-- Từ đây chúng chỉ mang giá trị do CON NGƯỜI nhập (CSKH biết ca này lâu hơn
-- thường lệ), NULL khi không ai nhập. Không còn hàm nào tự điền.

COMMENT ON COLUMN public.appointment.thanh_min IS
    'Phút DỰ KIẾN do người đặt lịch nhập tay; NULL = không ai ước lượng. Từ '
    '20260803000005 KHÔNG còn được suy ra từ bảng viết cứng. Thời lượng thật '
    'đọc ở v_consultation_duration.';

COMMENT ON COLUMN public.appointment.sono_min IS
    'Phút siêu âm DỰ KIẾN do người đặt lịch nhập tay; NULL = không ai ước lượng. '
    'Xem chú thích của thanh_min.';
