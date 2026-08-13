-- Trưởng ca gọi bộ phận (migration 20260807000006).
--
-- Khẳng định quan trọng nhất là ③: BẤM NHIỀU LẦN CHỈ RA MỘT THÔNG BÁO. Lúc
-- phòng đang tắc thì người ta bấm liên tục; nếu mỗi lần bấm là một dòng thì bên
-- nhận thấy mười việc cho một chuyện, và cái chuông lại thành thứ để bỏ qua.
--
-- Chống trùng phải nằm ở DATABASE, không phải ở nút disabled trong trình duyệt:
-- mở hai tab là nút kia không biết gì về nút này.
--
-- Mọi thứ rollback.

BEGIN;

DO $$
DECLARE
    v_clinic uuid := (SELECT id FROM public.clinic ORDER BY id LIMIT 1);
    v_tc     uuid;   -- trưởng ca (người gọi)
    v_dd     uuid;   -- điều dưỡng (người xử lý)
    v_id     uuid;
    v_n      integer;
BEGIN
    IF v_clinic IS NULL THEN
        RAISE EXCEPTION 'Không dựng được dữ liệu kiểm';
    END IF;

    INSERT INTO public.staff (full_name, short_name, primary_department,
                              employment_type, is_active)
    VALUES ('Trưởng ca kiểm thử', 'TCKT', 'TRUONG_CA', 'FULL_TIME', TRUE)
    RETURNING id INTO v_tc;
    INSERT INTO public.staff (full_name, short_name, primary_department,
                              employment_type, is_active)
    VALUES ('Điều dưỡng kiểm thử', 'DDKT', 'NURSE_ULTRASOUND', 'FULL_TIME', TRUE)
    RETURNING id INTO v_dd;

    -- ── ① Gọi một bộ phận ──────────────────────────────────────────────────
    INSERT INTO public.thong_bao
        (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
         nguoi_goi_staff_id)
    VALUES (v_clinic, 'NURSE_ULTRASOUND', 'KHAN',
            'SA1 đang tắc', '4 người chờ, lâu nhất 38 phút',
            'dispatch_alert', 'SA1', v_tc)
    RETURNING id INTO v_id;

    -- ── ② Phải có người nhận ───────────────────────────────────────────────
    BEGIN
        INSERT INTO public.thong_bao
            (clinic_id, tieu_de, noi_dung, nguon, nguoi_goi_staff_id)
        VALUES (v_clinic, 'Không gửi cho ai', 'x', 'dispatch_alert', v_tc);
        RAISE EXCEPTION 'Thông báo không có người nhận vẫn lưu được';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    -- ── ③ BẤM LẠI KHI CHƯA AI XỬ LÝ: KHÔNG TẠO THÊM ────────────────────────
    FOR i IN 1..9 LOOP
        INSERT INTO public.thong_bao
            (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
             nguoi_goi_staff_id)
        VALUES (v_clinic, 'NURSE_ULTRASOUND', 'KHAN',
                'SA1 đang tắc', 'bấm lần ' || i,
                'dispatch_alert', 'SA1', v_tc)
        ON CONFLICT (clinic_id, nguon, nguon_id, vai_nhan)
            WHERE da_xu_ly_luc IS NULL
              AND nguon_id IS NOT NULL
              AND vai_nhan IS NOT NULL
        DO NOTHING;
    END LOOP;

    SELECT count(*) INTO v_n FROM public.thong_bao
     WHERE clinic_id = v_clinic AND nguon_id = 'SA1';
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'Bấm 10 lần ra % thông báo — lẽ ra phải là 1', v_n;
    END IF;

    -- ── ④ Gọi BỘ PHẬN KHÁC về cùng một phòng thì VẪN được ──────────────────
    -- Phòng tắc có thể cần cả điều dưỡng lẫn lễ tân; chống trùng theo cặp
    -- (nguồn, vai), không theo riêng nguồn.
    INSERT INTO public.thong_bao
        (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
         nguoi_goi_staff_id)
    VALUES (v_clinic, 'RECEPTION', 'KHAN', 'SA1 đang tắc',
            'nhờ lễ tân giãn khách', 'dispatch_alert', 'SA1', v_tc);

    SELECT count(*) INTO v_n FROM public.thong_bao
     WHERE clinic_id = v_clinic AND nguon_id = 'SA1';
    IF v_n <> 2 THEN
        RAISE EXCEPTION 'Gọi hai bộ phận khác nhau ra % dòng, lẽ ra 2', v_n;
    END IF;

    -- ── ⑤ ĐÃ XỬ LÝ THÌ PHẢI BIẾT AI XỬ LÝ ──────────────────────────────────
    BEGIN
        UPDATE public.thong_bao SET da_xu_ly_luc = now() WHERE id = v_id;
        RAISE EXCEPTION 'Đóng thông báo mà không ghi ai đóng, KHÔNG bị chặn';
    EXCEPTION WHEN check_violation THEN NULL;   -- đúng
    END;

    UPDATE public.thong_bao
       SET da_xu_ly_luc = now(), da_xu_ly_boi = v_dd,
           ghi_chu_xu_ly = 'Đã điều thêm một điều dưỡng sang SA1'
     WHERE id = v_id;

    -- ── ⑥ XỬ LÝ XONG RỒI THÌ GỌI LẠI ĐƯỢC ──────────────────────────────────
    -- Việc tái diễn là chuyện thường; khoá chống trùng chỉ chặn khi cái cũ
    -- còn đang mở, nếu không thì lần tắc thứ hai sẽ không ai gọi được.
    INSERT INTO public.thong_bao
        (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
         nguoi_goi_staff_id)
    VALUES (v_clinic, 'NURSE_ULTRASOUND', 'KHAN', 'SA1 lại tắc',
            'lần thứ hai trong ca', 'dispatch_alert', 'SA1', v_tc);

    SELECT count(*) INTO v_n FROM public.thong_bao
     WHERE clinic_id = v_clinic AND nguon_id = 'SA1'
       AND vai_nhan = 'NURSE_ULTRASOUND';
    IF v_n <> 2 THEN
        RAISE EXCEPTION 'Sau khi xử lý xong vẫn không gọi lại được (% dòng)', v_n;
    END IF;

    RAISE NOTICE 'thong_bao_goi_bo_phan: tất cả khẳng định đều đạt';
END $$;

ROLLBACK;
