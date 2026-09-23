-- Trách nhiệm không được rơi (23/09/2026).
--
-- KHÁCH LÀ TRÊN HẾT. Khách trả tiền siêu âm, máy hỏng, dịch vụ không làm được —
-- lúc đó tiền của khách đang nằm ở phòng khám và **không ai được quên**. Hôm nay
-- hệ thống ghi một dòng sự kiện rồi thôi: `payment.reconciliation_needed` và ba
-- mã tương tự nằm trong `event_log`, không có chủ, không có hạn, không màn nào
-- hiện. Đó là định nghĩa của một trách nhiệm bị rơi.
--
-- Từ nay: sự kiện ấy mở một VIỆC có người chịu trách nhiệm.
--
-- CẮM THÊM CHỨ KHÔNG SỬA. Module Thực hiện dịch vụ không biết gì về file này:
-- nó chỉ phát `service.not_performed` và `service.interrupted`. Module Trách
-- nhiệm nghe hai sự kiện đó rồi mở việc. Mai kia muốn thêm "quá 20 phút chưa ai
-- xử lý thì nhắc trưởng ca" thì thêm một bên nghe nữa — vẫn không đụng Thực hiện.
--
-- Chạy lại được: IF NOT EXISTS / ON CONFLICT.

-- ── Việc gắn với một chỉ định cụ thể ───────────────────────────────────────
-- Thiếu cột này thì không trả lời được "việc đối soát này là của chỉ định nào",
-- và không chặn được việc mở hai lần cho cùng một chuyện.
ALTER TABLE public.work_item
    ADD COLUMN IF NOT EXISTS service_order_id uuid;

CREATE INDEX IF NOT EXISTS ix_work_item_service_order
    ON public.work_item (clinic_id, service_order_id)
    WHERE service_order_id IS NOT NULL;

-- Một chỉ định + một loại việc = tối đa MỘT việc đang mở. Sự kiện giao lại
-- (at-least-once) hay hai người cùng bấm đều không được sinh hai việc.
CREATE UNIQUE INDEX IF NOT EXISTS uq_work_item_mot_viec_dang_mo
    ON public.work_item (clinic_id, service_order_id, node_code)
    WHERE service_order_id IS NOT NULL
      AND status IN ('PENDING', 'IN_PROGRESS');

-- ── Ba loại việc mới ───────────────────────────────────────────────────────
-- `actor_roles` ở đây là NGƯỜI DỰ PHÒNG nhận việc khi chưa ai được giao đích
-- danh — không phải hàng rào quyền. Quyền vẫn là capability.
--
-- TÊN NODE LẤY ĐÚNG TỪ THIẾT KẾ ĐÃ CHỐT (ChatGPT tin 112), không tự đặt:
-- OPS-ROUTING-REASSIGN · OPS-SERVICE-INTERRUPTED · OPS-FINANCIAL-RESOLUTION.
-- Sửa 23/09/2026: bản trước dùng hai tên do Claude tự nghĩ ra
-- (OPS-DOI-SOAT-TIEN, OPS-QUYET-LAM-LAI). Đặt tên khác thiết kế nghĩa là hai
-- bên bàn về cùng một thứ bằng hai từ, và tới lúc nối thì không khớp.
--
-- VIỆC TIỀN KHÔNG TỰ GIAO TRƯỞNG CA hay điều dưỡng (cùng tin 112). Trưởng ca
-- điều phối phòng và người, không đối soát sổ tiền của khách; giao mặc định cho
-- họ là đẩy trách nhiệm tài chính sang người không có công cụ để làm.
INSERT INTO public.node_definition
    (clinic_id, code, name, flow_group, workspace, actor_roles, priority, is_group)
SELECT 'a0000000-0000-4000-8000-000000000001'::uuid, v.code, v.name,
       'van_hanh', 'khu_van_hanh', v.roles, v.uu_tien, false
  FROM (VALUES
    ('OPS-ROUTING-REASSIGN',
     'Điều phối lại dịch vụ: phòng cũ không còn dùng được',
     ARRAY['TRUONG_CA', 'MANAGEMENT'], 'P1'),
    ('OPS-SERVICE-INTERRUPTED',
     'Quyết định làm lại sau khi dịch vụ bị dừng giữa chừng',
     ARRAY['TRUONG_CA', 'DOCTOR', 'MANAGEMENT'], 'P1'),
    ('OPS-FINANCIAL-RESOLUTION',
     'Đối soát tiền: khách đã trả mà dịch vụ không làm',
     ARRAY['MANAGEMENT', 'CASHIER'], 'P1')
  ) AS v(code, name, roles, uu_tien)
 WHERE EXISTS (SELECT 1 FROM public.clinic
                WHERE id = 'a0000000-0000-4000-8000-000000000001'::uuid)
ON CONFLICT (clinic_id, code) DO UPDATE
    SET name = EXCLUDED.name, actor_roles = EXCLUDED.actor_roles,
        updated_at = now();

-- Phiên bản nút: `work_item` trỏ tới phiên bản, không trỏ tới định nghĩa —
-- đổi tên việc sau này không làm đổi các việc đã mở.
INSERT INTO public.node_definition_version
    (clinic_id, node_definition_id, version, snapshot)
SELECT d.clinic_id, d.id, d.current_version,
       jsonb_build_object('code', d.code, 'name', d.name,
                          'actor_roles', to_jsonb(d.actor_roles))
  FROM public.node_definition d
 WHERE d.clinic_id = 'a0000000-0000-4000-8000-000000000001'::uuid
   AND d.code IN ('OPS-ROUTING-REASSIGN', 'OPS-SERVICE-INTERRUPTED',
                  'OPS-FINANCIAL-RESOLUTION')
ON CONFLICT (node_definition_id, version) DO NOTHING;

COMMENT ON COLUMN public.work_item.service_order_id IS
    'Việc này về chỉ định nào. Cùng một chỉ định + một loại việc chỉ có một việc đang mở.';
