-- PHÒNG CHUYÊN ★ + NHẬN THEO CHỈ ĐỊNH (Tuyền chốt 07/10/2026 —
-- docs/KE-HOACH-NHAN-TAI-PHONG.md, mục "Phòng chuyên + nhận theo chỉ định").
--
-- Lỗi thật trên staging: khách 3 chỉ định (Soi cổ tử cung + Siêu âm → quầy
-- hướng dẫn Phòng siêu âm; Monitor → Phòng thủ thuật). Phòng thủ thuật làm được
-- cả ba node nên bấm Nhận (theo KHÁCH) gom cả ba; phòng siêu âm mất khách.
--
-- 1. `clinic_room_node.chuyen`: phòng này là PHÒNG CHUYÊN của chức năng ấy.
--    Chỉ dùng để TICK SẴN khi Nhận (chỉ định chưa có hướng dẫn) và GỢI Ý hướng
--    dẫn ở quầy / phiếu — không thu hẹp phòng làm được, không ẩn khách ở phòng
--    khác. Không seed: quản lý tự đánh ★ ở /settings/clinic-config.
--    Chỉ ở mức node: ngoại lệ theo dịch vụ đã có `clinic_room_service` thu hẹp
--    phòng làm được, giao với ★ của node là đủ (không thêm ô thứ hai).
-- 2. Hàm `phong_chuyen(clinic, room, node, service)` = làm được (luật
--    `phong_lam_duoc`) VÀ phòng đánh ★ node ấy. MỘT luật cho mọi chỗ.
-- 3. View `v_moc_hanh_trinh` dựng lại không còn `service.room_release_undone`
--    (bỏ nút Nhả 07/10 — chỉ ghi sự kiện thật người bấm; chưa lên prod).
--
-- Chạy lại được.

-- ── 1. Cột ★ ────────────────────────────────────────────────────────────────
ALTER TABLE public.clinic_room_node
    ADD COLUMN IF NOT EXISTS chuyen boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clinic_room_node.chuyen IS
'Phòng chuyên ★ của chức năng (node) này — tick sẵn khi phòng Nhận chỉ định chưa có hướng dẫn, gợi ý hướng dẫn ở quầy/phiếu. Không thu hẹp phòng làm được. Đổi qua /clinic-config/room-node-chuyen (nhật ký clinic_config.room_node_chuyen). 07/10/2026.';

-- ── 2. Một luật: phòng này là phòng chuyên của chỉ định (node, dịch vụ) ─────
CREATE OR REPLACE FUNCTION public.phong_chuyen(
    p_clinic_id uuid, p_room_id uuid, p_node_code text, p_service_code text)
RETURNS boolean
LANGUAGE sql
STABLE
AS $fn$
    SELECT public.phong_lam_duoc(p_clinic_id, p_room_id, p_node_code, p_service_code)
       AND EXISTS (
            SELECT 1 FROM public.clinic_room_node rn
             WHERE rn.clinic_id = p_clinic_id AND rn.room_id = p_room_id
               AND rn.node_code = p_node_code AND rn.chuyen)
$fn$;

COMMENT ON FUNCTION public.phong_chuyen(uuid, uuid, text, text) IS
'Phòng là phòng chuyên ★ của chỉ định: làm được (phong_lam_duoc) và đánh ★ node của chỉ định (clinic_room_node.chuyen). 07/10/2026.';

-- ── 3. View mốc hành trình — bỏ hoàn tác Nhả ────────────────────────────────
-- Cùng cột, cùng thứ tự với 20261007500000 (CREATE OR REPLACE VIEW đòi vậy).
CREATE OR REPLACE VIEW public.v_moc_hanh_trinh
    WITH (security_invoker = true) AS
SELECT e.event_id,
       e.seq,
       e.clinic_id,
       coalesce(nullif(e.payload->>'visit_id', '')::uuid, e.correlation_id)
           AS visit_id,
       CASE WHEN e.aggregate_type = 'service_order' THEN e.aggregate_id END
           AS service_order_id,
       CASE WHEN e.aggregate_type = 'consultation' THEN e.aggregate_id END
           AS consultation_id,
       coalesce(nullif(e.payload->>'room_id', '')::uuid, a.room_id_snapshot)
           AS room_id,
       CASE e.event_type
           WHEN 'service.routed' THEN
               CASE WHEN e.payload->>'nguon' = 'tai_phong' THEN 'NHAN'
                    ELSE 'XEP_PHONG' END
           WHEN 'service.room_released' THEN 'NHA'
           WHEN 'service.room_receive_undone' THEN 'HOAN_TAC_NHAN'
           WHEN 'service.room_guided' THEN 'HUONG_DAN'
           WHEN 'service.routing_invalidated' THEN 'HUY_XEP_PHONG'
           WHEN 'service.room_transferred' THEN 'CHUYEN_PHONG'
           WHEN 'service.started' THEN 'BAT_DAU'
           WHEN 'service.start_cancelled' THEN 'HUY_BAT_DAU'
           WHEN 'service.completed' THEN 'XONG'
           WHEN 'service.completion_undone' THEN 'HOAN_TAC_XONG'
           WHEN 'service.interrupted' THEN 'GIAN_DOAN'
           WHEN 'service.not_performed' THEN 'KHONG_LAM'
           WHEN 'service.patient_moved' THEN 'CHUYEN_KHACH'
           WHEN 'consultation.started' THEN 'KHAM_BAT_DAU'
           WHEN 'consultation.resumed' THEN 'KHAM_LAI'
           WHEN 'consultation.completed' THEN 'KHAM_XONG'
           WHEN 'consultation.reopened' THEN 'HOAN_TAC_KHAM_XONG'
       END AS loai_moc,
       e.occurred_at AS luc,
       e.actor_staff_id AS nguoi_id,
       s.full_name AS nguoi,
       e.actor_role AS vai,
       e.on_behalf_of AS lam_thay_cho,
       ht.event_id IS NOT NULL AS bi_hoan_tac,
       ht.occurred_at AS hoan_tac_luc,
       -- Xong là tự nhả (không có cú bấm Nhả riêng).
       CASE e.event_type
           WHEN 'service.room_released' THEN e.payload->>'ly_do'
           WHEN 'service.completed' THEN 'XONG'
       END AS ly_do_nha,
       e.payload->>'trang_thai_truoc' AS trang_thai_truoc,
       coalesce(e.payload->>'from_room_id', e.payload->>'nhan_cheo_tu_room_id',
                e.payload->>'tu_room_id')::uuid AS tu_phong_id,
       coalesce(e.payload->>'sang_room_id', e.payload->>'to_room_id')::uuid
           AS sang_phong_id,
       CASE WHEN e.event_type = 'service.room_guided'
            THEN nullif(e.payload->>'room_id', '')
            ELSE e.payload->>'huong_dan_room_id' END::uuid AS huong_dan_phong_id,
       (e.payload->>'dung_huong_dan')::boolean AS dung_huong_dan,
       (e.payload->>'thu_tu_huong_dan')::int AS thu_tu_huong_dan,
       (e.payload->>'thu_tu_thuc_te')::int AS thu_tu_thuc_te,
       coalesce(e.payload->>'lan', e.payload->>'attempt_no')::int AS lan,
       e.payload->>'nguon' AS nguon,
       e.event_type,
       e.payload
  FROM public.domain_event e
  LEFT JOIN public.service_execution_attempt a
    ON a.clinic_id = e.clinic_id
   AND a.id = nullif(e.payload->>'attempt_id', '')::uuid
  LEFT JOIN public.staff s ON s.id = e.actor_staff_id
  LEFT JOIN LATERAL (
      SELECT u.event_id, u.occurred_at
        FROM public.domain_event u
       WHERE u.clinic_id = e.clinic_id
         AND u.aggregate_type = e.aggregate_type
         AND u.aggregate_id = e.aggregate_id
         AND u.seq > e.seq
         AND u.event_type = CASE e.event_type
                 WHEN 'service.routed' THEN
                     CASE WHEN e.payload->>'nguon' = 'tai_phong'
                          THEN 'service.room_receive_undone'
                          ELSE 'service.routing_invalidated' END
                 WHEN 'service.started' THEN 'service.start_cancelled'
                 WHEN 'service.completed' THEN 'service.completion_undone'
                 WHEN 'consultation.completed' THEN 'consultation.reopened'
             END
         AND NOT EXISTS (
             SELECT 1 FROM public.domain_event e2
              WHERE e2.clinic_id = e.clinic_id
                AND e2.aggregate_type = e.aggregate_type
                AND e2.aggregate_id = e.aggregate_id
                AND e2.event_type = e.event_type
                AND e2.seq > e.seq AND e2.seq < u.seq)
       ORDER BY u.seq
       LIMIT 1
  ) ht ON true
 WHERE e.event_type IN (
       'service.routed', 'service.room_released', 'service.room_receive_undone',
       'service.room_guided', 'service.routing_invalidated',
       'service.room_transferred', 'service.started', 'service.start_cancelled',
       'service.completed', 'service.completion_undone', 'service.interrupted',
       'service.not_performed', 'service.patient_moved', 'consultation.started',
       'consultation.resumed', 'consultation.completed', 'consultation.reopened');

COMMENT ON VIEW public.v_moc_hanh_trinh IS
'Mỗi mốc hành trình một dòng (Nhận · Bắt đầu · Xong · rời phòng do nhận chéo / quầy bỏ dịch vụ · hướng dẫn · khám lại · các hoàn tác), đọc từ domain_event. bi_hoan_tac = mốc đã bị rút lại. 07/10/2026.';
