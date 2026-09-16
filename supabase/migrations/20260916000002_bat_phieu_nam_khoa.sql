-- BẬT PHIẾU KHÁM NAM KHOA (NK) — Tuyền chốt 16/09/2026.
--
-- 102 trường của phiếu đã viết xong từ lâu (`lib/form-schemas/nk.ts`) nhưng
-- danh mục để `is_active = FALSE` từ 20260730000017: phiếu render ra điền được,
-- bấm Lưu thì nhận "Phòng khám chưa dùng phiếu: NK". Bác sĩ nam khoa vì thế
-- không có chỗ ghi.
--
-- ĐI QUA ĐÚNG CỔNG, KHÔNG LẬT CỜ. `activate_clinical_form()` (20260804000019)
-- từ chối bật nếu chưa có dòng trong `clinical_form_approval` — ai duyệt, bản
-- nào, dựa trên tài liệu gì. Đó là chốt an toàn lâm sàng, không phải thủ tục
-- giấy tờ: một phiếu bệnh án không ai chịu trách nhiệm là một phiếu không nên
-- có trong hồ sơ. Nên ở đây ghi bản duyệt TRƯỚC rồi mới gọi hàm bật.
--
-- Chạy lại được: INSERT có ON CONFLICT, và bật một phiếu đang bật không đổi gì.

DO $bat_nk$
DECLARE
    v_clinic uuid;
    v_nguoi  uuid;
BEGIN
    FOR v_clinic IN
        SELECT clinic_id FROM public.clinical_form_catalogue WHERE form_code = 'NK'
    LOOP
        -- Người duyệt: quản lý của chính phòng khám ấy. Không có thì bỏ qua —
        -- một phòng khám chưa khai nhân sự thì cũng chưa khám nam khoa, và
        -- migration không được phép dựng một người duyệt không tồn tại.
        SELECT m.staff_id INTO v_nguoi
          FROM public.clinic_membership m
         WHERE m.clinic_id = v_clinic AND m.role = 'MANAGEMENT' AND m.is_active
         ORDER BY m.created_at
         LIMIT 1;
        CONTINUE WHEN v_nguoi IS NULL;

        INSERT INTO public.clinical_form_approval (
            clinic_id, form_code, schema_version, approved_by_staff_id,
            source_document, note
        )
        VALUES (
            v_clinic, 'NK', '2026-09-16', v_nguoi,
            'Sáng Ý — Bàn giao thông tin Khám Chữa bệnh (danh mục 5 dịch vụ '
            'khám: PK, SK, NT, NK, HMVS; phần khám nam khoa và tinh dịch đồ)',
            'Tuyền chốt 16/09/2026 sau khi đối chiếu tài liệu bàn giao với '
            'phiếu đã dựng. Các mục còn TODO-BS-REVIEW trong nk.ts vẫn phải '
            'đưa bác sĩ rà trước khi dùng trên bệnh nhân thật.'
        )
        ON CONFLICT (clinic_id, form_code, schema_version) DO NOTHING;

        PERFORM public.activate_clinical_form(v_clinic, 'NK', '2026-09-16');
    END LOOP;
END
$bat_nk$;

DO $kiem$
DECLARE
    v_tat int;
BEGIN
    SELECT count(*) INTO v_tat
      FROM public.clinical_form_catalogue c
     WHERE c.form_code = 'NK' AND NOT c.is_active
       AND EXISTS (SELECT 1 FROM public.clinic_membership m
                    WHERE m.clinic_id = c.clinic_id
                      AND m.role = 'MANAGEMENT' AND m.is_active);
    IF v_tat > 0 THEN
        RAISE EXCEPTION 'Còn % phòng khám có quản lý mà phiếu NK vẫn tắt', v_tat;
    END IF;
    RAISE NOTICE 'phiếu NK: đã bật ở mọi phòng khám có người duyệt';
END
$kiem$;
