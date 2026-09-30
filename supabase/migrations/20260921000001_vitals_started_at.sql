-- Thêm mốc bắt đầu đo sinh hiệu (vitals_started_at, vitals_started_by).
-- Mốc gọi loa (goi_do_luc) giữ cho dữ liệu lịch sử, không dùng làm started_at cho lượt mới.
-- CHỈ TẠO MIGRATION, KHÔNG TỰ ĐỘNG APPLY (theo yêu cầu vận hành).

ALTER TABLE public.encounter_flow
    ADD COLUMN IF NOT EXISTS vitals_started_at timestamptz,
    ADD COLUMN IF NOT EXISTS vitals_started_by uuid REFERENCES public.staff (id);

COMMENT ON COLUMN public.encounter_flow.vitals_started_at IS
'Thời điểm điều dưỡng bấm Bắt đầu đo sinh hiệu tại phòng đo.';

COMMENT ON COLUMN public.encounter_flow.vitals_started_by IS
'Điều dưỡng bấm Bắt đầu đo sinh hiệu.';
