-- Gán phòng cho hai bước chưa có phòng nào (batch pilot 18/09/2026) — LOCAL/DEMO.
--
-- Không có dòng này thì chỉ định Đo mật độ xương / Tinh dịch đồ kẹt "chờ xếp
-- phòng" mãi (Pack C). Đây là CẤU HÌNH, không phải luật: prod gán bằng màn Cấu
-- trúc phòng khám sau khi Dr4Women xác nhận phòng thật. Suy luận cho demo:
--   * DICHVU-DXA → KN-DOCHISO: vị trí T1_DOCHISO ghi "HA, MĐX (mật độ xương)";
--   * DICHVU-TINHDICHDO → KN-LAYMAU: lấy mẫu dịch, cùng phòng mẫu nước tiểu.

\set ON_ERROR_STOP on

DO $$
BEGIN
    INSERT INTO public.clinic_room_node (clinic_id, room_id, node_code)
    SELECT r.clinic_id, r.id, x.node
      FROM (VALUES ('KN-DOCHISO', 'DICHVU-DXA'),
                   ('KN-LAYMAU', 'DICHVU-TINHDICHDO')) AS x(room, node)
      JOIN public.clinic_room r
        ON r.code = x.room AND r.clinic_id = 'a0000000-0000-4000-8000-000000000001'
    ON CONFLICT DO NOTHING;
END $$;
