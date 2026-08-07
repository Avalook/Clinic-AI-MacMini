-- Dr4Women là PHÒNG KHÁM, không phải cơ sở. Nó có hai cơ sở: Kim Ngưu và Hào Nam.
--
-- CHUYỆN ĐÃ XẢY RA. Migration 20260730000003 có một chốt: phòng khám nào chưa
-- có cơ sở nào thì tạo cho nó một cơ sở `MAIN` lấy luôn tên phòng khám. Chốt đó
-- đúng cho một phòng khám vừa được tạo. Nhưng nó dựa trên giả định ghi ngay
-- trong file: "Trên production không đổi gì: cơ sở đã có sẵn từ seed."
--
-- Giả định đó SAI trên máy tự dựng. Ở đó lược đồ được dựng bằng cách chạy hết
-- migration trên một database trắng RỒI mới nạp seed. Tại thời điểm
-- 20260730000003 chạy, `clinic_location` còn rỗng — nên chốt kia nổ, và
-- "Phòng khám Dr4Women" thành cơ sở thứ ba bên cạnh Kim Ngưu và Hào Nam.
--
-- Hậu quả không dừng ở một dòng thừa: mọi thứ dựng SAU đó mà cần một cơ sở đều
-- bám vào cơ sở giả ấy. Trên bản thật, cả 12 phòng (4 phòng khám, 3 phòng siêu
-- âm, nhà thuốc, thu ngân, tiếp nhận, lấy máu, sinh hiệu) nằm dưới nó, còn Kim
-- Ngưu — nơi 36 nhân sự thật đang làm — không có phòng nào. Người dùng nhìn
-- thấy ba cơ sở, trong đó một cái là tên phòng khám.
--
-- CÁCH SỬA: gộp cơ sở giả vào cơ sở thật rồi xoá nó. Không đổi tên tại chỗ —
-- Kim Ngưu đã tồn tại sẵn, đổi tên MAIN thành "Kim Ngưu" sẽ thành hai Kim Ngưu.
--
-- ĐIỀU KIỆN CHẶT: chỉ động vào cơ sở có code 'MAIN' VÀ tên trùng đúng tên phòng
-- khám VÀ phòng khám còn cơ sở khác. Thiếu vế cuối là xoá cơ sở duy nhất của
-- một phòng khám mới mở — đúng thứ chốt kia sinh ra để tránh.

DO $$
DECLARE
    r          record;
    v_that     uuid;
    v_phong    int;
    v_nhan_su  int;
BEGIN
    FOR r IN
        SELECT l.id, l.clinic_id, c.name AS ten_phong_kham
          FROM public.clinic_location l
          JOIN public.clinic c ON c.id = l.clinic_id
         WHERE l.code = 'MAIN'
           AND l.name = c.name
    LOOP
        -- Cơ sở thật để gộp về: ưu tiên cơ sở ĐANG HOẠT ĐỘNG, cũ nhất trước.
        -- Kim Ngưu đang mở, Hào Nam thì chưa — nên thứ tự này chọn Kim Ngưu mà
        -- không cần ghim mã cơ sở vào migration.
        SELECT id INTO v_that
          FROM public.clinic_location
         WHERE clinic_id = r.clinic_id
           AND id <> r.id
         ORDER BY is_active DESC, created_at, code
         LIMIT 1;

        IF v_that IS NULL THEN
            -- Phòng khám này CHỈ có cơ sở MAIN. Đó là phòng khám mới, chốt kia
            -- đang làm đúng việc của nó. Không đụng vào.
            CONTINUE;
        END IF;

        SELECT count(*) INTO v_phong
          FROM public.clinic_room WHERE location_id = r.id;
        SELECT count(*) INTO v_nhan_su
          FROM public.staff WHERE primary_location_id = r.id;

        -- Mọi bảng có khoá ngoại tới clinic_location. Liệt kê tay chứ không
        -- sinh động: thêm một bảng mới mà quên ở đây thì migration này đứt ở
        -- lệnh DELETE bên dưới, to và rõ — hơn là một vòng lặp im lặng bỏ sót.
        UPDATE public.appointment     SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.block_budget    SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.clinic_room     SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.patient         SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.pregnancy       SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.staff           SET primary_location_id = v_that WHERE primary_location_id = r.id;
        UPDATE public.staff_node      SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.staff_task      SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.visit           SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.visit_gate_rule SET location_id = v_that WHERE location_id = r.id;
        UPDATE public.work_session    SET location_id = v_that WHERE location_id = r.id;

        DELETE FROM public.clinic_location WHERE id = r.id;

        RAISE NOTICE 'Gộp cơ sở giả "%" vào cơ sở thật %: % phòng, % nhân sự.',
            r.ten_phong_kham, v_that, v_phong, v_nhan_su;
    END LOOP;
END $$;
