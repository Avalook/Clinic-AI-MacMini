-- Quyền cho bước Thực hiện dịch vụ (23/09/2026).
--
-- Contract: docs/ai/lifecycle-v1/ClinicAI-EXECUTION-v1.md §6, §9–§11, §14.
--
-- Tách năm quyền chứ không gộp một "được thao tác phòng dịch vụ": bắt đầu và
-- xong là việc thường ngày của người đứng phòng, còn **đánh dấu không làm**,
-- **dừng giữa chừng** và **quyết định làm lại** đụng tới tiền đã thu và tới
-- quyết định chuyên môn. Gộp chung là mất khả năng giao việc thường ngày cho
-- điều dưỡng mà vẫn giữ quyết định khó cho người có thẩm quyền.
--
-- Ở khối công việc thì cả năm nằm chung "Thực hiện dịch vụ", nên quản lý vẫn chỉ
-- bật một ô. Bung ra chỉ khi phòng khám cần siết.

INSERT INTO public.work_pack (ma, ten, module, mo_ta) VALUES
    ('thuc_hien', 'Thực hiện dịch vụ', 'execution',
     'Bắt đầu, hoàn thành, dừng giữa chừng, đánh dấu không làm được')
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, module = EXCLUDED.module, mo_ta = EXCLUDED.mo_ta;

INSERT INTO public.capability (ma, ten, work_pack, module, rui_ro, chung_chi_lam_sang)
VALUES
    ('service.execute.start', 'Bắt đầu làm dịch vụ',
     'thuc_hien', 'execution', 'operational', false),
    ('service.execute.complete', 'Đánh dấu đã làm xong',
     'thuc_hien', 'execution', 'operational', false),
    ('service.execute.not_performed', 'Đánh dấu không làm được',
     'thuc_hien', 'execution', 'financial', false),
    ('service.execute.interrupt', 'Dừng giữa chừng',
     'thuc_hien', 'execution', 'financial', false),
    ('service.execute.retry', 'Quyết định làm lại sau khi dừng',
     'thuc_hien', 'execution', 'clinical', false)
ON CONFLICT (ma) DO UPDATE
    SET ten = EXCLUDED.ten, work_pack = EXCLUDED.work_pack,
        module = EXCLUDED.module, rui_ro = EXCLUDED.rui_ro;

-- Ai đang đứng phòng dịch vụ thì làm được ngay, như hôm qua vẫn làm.
INSERT INTO public.capability_grant
    (clinic_id, staff_id, capability, tu_khoi, tu_preset, ly_do)
SELECT m.clinic_id, m.staff_id, c.ma, 'thuc_hien', m.role,
       'Chép từ preset khi thêm khối Thực hiện (23/09/2026)'
  FROM public.clinic_membership m
  JOIN public.capability c ON c.work_pack = 'thuc_hien'
 WHERE m.is_active
   AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR', 'NURSE_ULTRASOUND', 'TKYK',
                  'TRUONG_CA', 'MANAGEMENT')
ON CONFLICT DO NOTHING;
