-- Nền event-driven — bước 2: bên nhận đầu tiên (23/09/2026).
--
-- `luot_dong_thoi_gian` là một PROJECTION: ảnh chụp để đọc, dựng hoàn toàn từ
-- `domain_event`. Xoá sạch bảng này rồi chạy lại sổ sự kiện thì phải ra đúng như
-- cũ — đó là phép thử của quyết định "state-first + event đầy đủ". Không ai được
-- ghi vào đây bằng tay, và không luật nghiệp vụ nào được đọc nó để ra quyết định.
--
-- Chọn bên nhận này làm bên nhận ĐẦU TIÊN vì nó vô hại: hỏng thì màn dòng thời
-- gian thiếu một dòng, không ai bị chặn, không tiền nào sai. Đúng bước 3 của
-- đường chuyển đổi (strangler fig).
--
-- Chạy lại được: IF NOT EXISTS / DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS public.luot_dong_thoi_gian (
    -- Một sự kiện chỉ để lại một dòng: bên nhận chạy lại (at-least-once) không
    -- được nhân đôi dòng trên màn. Ép ở Postgres, không bằng "nhớ kiểm tra".
    event_id    uuid PRIMARY KEY
        REFERENCES public.domain_event(event_id) ON DELETE CASCADE,
    clinic_id   uuid NOT NULL,
    visit_id    uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    event_type  text NOT NULL,
    nhan        text NOT NULL,
    chi_tiet    jsonb NOT NULL DEFAULT '{}'::jsonb,
    actor_type  text NOT NULL,
    actor_staff_id uuid,
    ghi_luc     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_luot_dong_thoi_gian_luot
    ON public.luot_dong_thoi_gian (clinic_id, visit_id, occurred_at);

ALTER TABLE public.luot_dong_thoi_gian ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS luot_dong_thoi_gian_select_own_clinic
    ON public.luot_dong_thoi_gian;
CREATE POLICY luot_dong_thoi_gian_select_own_clinic
    ON public.luot_dong_thoi_gian
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.luot_dong_thoi_gian TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.luot_dong_thoi_gian TO service_role;

COMMENT ON TABLE public.luot_dong_thoi_gian IS
    'Projection dòng thời gian lượt khám — dựng lại được hoàn toàn từ domain_event. Không ghi tay, không dùng để ra quyết định nghiệp vụ.';
