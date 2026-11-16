-- Tin `clinicai_changes` mang thêm id lượt khám (`v`) khi hàng có cột `visit_id`.
--
-- VÌ SAO (đo prod 13–16/11/2026). Tin cũ chỉ có {t: bảng, c: phòng khám}. Mỗi
-- lượt ghi ở BẤT KỲ lượt nào làm mọi phiếu đang mở hỏi lại — bàn khám mở phiếu có
-- ~12 hook nghe theo MỘT lượt. Một lượt ghi kéo theo ~15 GET trong 1,5 giây, đỉnh
-- 443 lượt/phút/người, 1.834 lượt 429. Có `v`, hook theo lượt bỏ tin lượt khác.
--
-- TIN VẪN NGHÈO CÓ CHỦ Ý (lý do gốc ở 20260806000001): không gửi dữ liệu hàng —
-- NOTIFY có trần 8000 byte (vượt thì HỎNG CẢ GIAO DỊCH GHI), và gửi dữ liệu qua
-- đây là mở lối đọc ngoài mọi lớp kiểm quyền. Thêm đúng MỘT uuid, không hơn.
--
-- `to_jsonb(NEW)->>'visit_id'` chạy được cho MỌI bảng: bảng không có cột ấy thì
-- ra NULL và tin y như cũ (không `v`) — màn coi là "có thể là lượt của mình" và
-- hỏi lại như trước. Bảng `visit` có khoá chính tên `visit_id` nên tự khớp.
-- Truy ngược qua `service_order` cho form_instance / tep_ket_qua: CHƯA làm (thêm
-- một truy vấn vào mỗi lượt ghi) — đo xong rồi tính.
--
-- pg_notify gộp tin TRÙNG Y HỆT trong một giao dịch. Có `v`, UPDATE 300 lượt sinh
-- 300 tin khác nhau; hàng đợi mỗi màn (change_broker.QUEUE_SIZE) đầy thì đổi
-- thành một tin "không rõ" — cùng PR.
--
-- LÙI: chạy lại thân hàm ở 20260806000001 (chỉ CREATE OR REPLACE, không đổi
-- trigger nào). Trình duyệt cũ bỏ qua khoá `v` (RealtimeRefresher chỉ đọc `t`),
-- nên áp migration này TRƯỚC khi lên frontend là an toàn.

CREATE OR REPLACE FUNCTION public.notify_row_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $$
DECLARE
    v_hang jsonb;
    v_clinic uuid;
    v_luot text;
    v_luot_cu text;
BEGIN
    -- DELETE thì dữ liệu nằm ở OLD. Không có dòng này, mọi lần xoá đều mất tin
    -- báo và màn hình giữ lại một hàng vừa biến mất.
    IF TG_OP = 'DELETE' THEN
        v_hang := to_jsonb(OLD);
    ELSE
        v_hang := to_jsonb(NEW);
    END IF;
    v_clinic := (v_hang ->> 'clinic_id')::uuid;
    v_luot := v_hang ->> 'visit_id';

    -- HÀNG DỜI GIỮA HAI LƯỢT (nút "Làm hôm nay" / "Để lần sau" đổi
    -- service_order.visit_id): phiếu của CẢ lượt cũ lẫn lượt mới phải hỏi lại.
    -- Chỉ đọc OLD khi bảng có cột lượt — bảng khác không tốn thêm gì.
    IF TG_OP = 'UPDATE' AND v_hang ? 'visit_id' THEN
        v_luot_cu := to_jsonb(OLD) ->> 'visit_id';
    END IF;

    IF v_clinic IS NOT NULL THEN
        IF v_luot IS NULL THEN
            PERFORM pg_notify(
                'clinicai_changes',
                json_build_object('t', TG_TABLE_NAME, 'c', v_clinic)::text
            );
        ELSE
            PERFORM pg_notify(
                'clinicai_changes',
                json_build_object('t', TG_TABLE_NAME, 'c', v_clinic, 'v', v_luot)::text
            );
        END IF;
        IF v_luot_cu IS NOT NULL AND v_luot_cu IS DISTINCT FROM v_luot THEN
            PERFORM pg_notify(
                'clinicai_changes',
                json_build_object('t', TG_TABLE_NAME, 'c', v_clinic, 'v', v_luot_cu)::text
            );
        END IF;
    END IF;

    RETURN NULL;  -- AFTER trigger: giá trị trả về không được dùng.
END;
$$;
