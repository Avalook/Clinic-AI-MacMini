-- Service Lifecycle v1 — Slice 4: trục routing khớp phòng hiện hành (22/09/2026).
--
-- Contract: docs/ai/lifecycle-v1/ClinicAI-ROUTING-v1.md §2.
--   ASSIGNED              → room_id NOT NULL
--   REASSIGNMENT_REQUIRED → room_id NULL (phòng cũ nằm trong sự kiện, không để
--                           room_id tiếp tục trỏ một phân phòng đã vô hiệu)
--
-- UNASSIGNED KHÔNG bị ràng buộc room_id ở DB — có chủ ý: luồng đối tác tự lấy
-- mẫu (doi_tac_da_lay_mau, chính sách đối tác còn OPEN) ghi phòng đối tác lên
-- chỉ định để lưu vết, ngoài lệnh routing. AssignServiceRoom không bao giờ coi
-- room_id của dòng UNASSIGNED là phân phòng chính thức.
--
-- routing_status NULL = dòng cũ (legacy): KHÔNG ràng buộc, đọc theo đường cũ.
-- Không backfill: mọi dòng hiện có đều NULL nên thoả. Chạy lại được.

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_routing_khop_phong;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_routing_khop_phong CHECK (
        routing_status IS DISTINCT FROM 'ASSIGNED' OR room_id IS NOT NULL);

ALTER TABLE public.service_order
    DROP CONSTRAINT IF EXISTS service_order_routing_mat_hieu_luc_khong_phong;
ALTER TABLE public.service_order
    ADD CONSTRAINT service_order_routing_mat_hieu_luc_khong_phong CHECK (
        routing_status IS DISTINCT FROM 'REASSIGNMENT_REQUIRED' OR room_id IS NULL);
