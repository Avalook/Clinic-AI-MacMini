-- GỠ VIỆC "ĐO MẬT ĐỘ XƯƠNG" (DICHVU-DXA) KHỎI PHÒNG "ĐO SINH HIỆU" (Tuyền 29/09/2026).
--
-- Log prod: "Bệnh Nhân Thu Test → Đo sinh hiệu · Xếp phòng · Đo mật độ xương ·
-- tự động". Script dựng Kim Ngưu 3 tầng (27/09) gắn phòng Đo sinh hiệu làm được
-- cả LUOTKHAM-03 lẫn DICHVU-DXA nên bộ tự xếp phòng chọn nó. Tuyền chốt: DXA
-- KHÔNG làm ở phòng Đo sinh hiệu.
--
-- CHỈ gỡ ở đúng phòng tên "Đo sinh hiệu", và CHỈ khi cơ sở ấy vẫn còn ít nhất
-- một phòng đang hoạt động khác làm được DXA (nếu không, gỡ là làm dịch vụ mất
-- chỗ xếp — bỏ qua, ghi NOTICE). Chạy lại được: hết dòng để gỡ thì không làm gì.

DO $$
DECLARE
    r record;
    con_phong_khac boolean;
    n integer := 0;
BEGIN
    FOR r IN
        SELECT ph.id AS room_id, ph.clinic_id, ph.location_id, ph.code
          FROM clinic_room ph
         WHERE lower(btrim(ph.name)) = lower('Đo sinh hiệu')
           AND EXISTS (SELECT 1 FROM clinic_room_node rn
                        WHERE rn.room_id = ph.id AND rn.node_code = 'DICHVU-DXA')
    LOOP
        SELECT EXISTS (
            SELECT 1
              FROM clinic_room o
             WHERE o.clinic_id = r.clinic_id
               AND o.id <> r.room_id
               AND o.is_active
               AND lower(btrim(o.name)) <> lower('Đo sinh hiệu')
               AND (o.node_code = 'DICHVU-DXA'
                    OR EXISTS (SELECT 1 FROM clinic_room_node rn2
                                WHERE rn2.room_id = o.id
                                  AND rn2.node_code = 'DICHVU-DXA'))
        ) INTO con_phong_khac;

        IF NOT con_phong_khac THEN
            RAISE NOTICE 'Bỏ qua phòng % (clinic %): không còn phòng nào khác làm DXA',
                r.code, r.clinic_id;
            CONTINUE;
        END IF;

        DELETE FROM clinic_room_node
         WHERE room_id = r.room_id AND node_code = 'DICHVU-DXA';
        n := n + 1;
    END LOOP;
    RAISE NOTICE 'Đã gỡ DXA khỏi % phòng Đo sinh hiệu', n;
END
$$;
