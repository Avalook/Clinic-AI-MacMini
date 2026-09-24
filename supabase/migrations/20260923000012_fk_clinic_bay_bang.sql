-- Bảy bảng mới thiếu khoá ngoại tới `clinic` (23/09/2026).
--
-- Bài kiểm `supabase/tests/multi_tenant_foundation.sql` đòi MỌI bảng có cột
-- `clinic_id` phải có khoá ngoại thẳng tới `public.clinic`. Bảy bảng thêm hôm
-- nay không có, và job `database` của CI đỏ vì chuyện ấy.
--
-- ĐÂY KHÔNG PHẢI THỦ TỤC. Thiếu khoá ngoại nghĩa là một dòng có thể mang
-- `clinic_id` của một phòng khám KHÔNG TỒN TẠI. Với `domain_event` — sổ chỉ
-- thêm, không sửa được — một dòng như thế nằm lại vĩnh viễn và không ai biết
-- nó thuộc về ai.
--
-- Hai bảng trong số này đã có khoá ngoại GHÉP sang bảng khác cùng phòng khám
-- (`dich_vu_mau_ket_qua → ket_qua_mau`, `form_instance → form_definition`).
-- Ràng buộc ấy chặt hơn về mặt nghiệp vụ, nhưng nó KHÔNG thay được khoá ngoại
-- thẳng: nó bảo đảm "cùng phòng khám với bảng cha", không bảo đảm "phòng khám
-- ấy có thật".
--
-- `ON DELETE RESTRICT` theo đúng nếp mọi bảng tenant khác trong kho: xoá một
-- phòng khám mà còn dữ liệu là một việc phải làm có ý thức, không phải hệ quả
-- của một câu DELETE.
--
-- Migration MỚI chứ không sửa 20260923000001..11 đã đẩy lên nhánh: migration
-- đã rời khỏi máy mình thì coi như lịch sử.

ALTER TABLE public.domain_event
    DROP CONSTRAINT IF EXISTS domain_event_clinic_fk,
    ADD  CONSTRAINT domain_event_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.event_delivery
    DROP CONSTRAINT IF EXISTS event_delivery_clinic_fk,
    ADD  CONSTRAINT event_delivery_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.luot_dong_thoi_gian
    DROP CONSTRAINT IF EXISTS luot_dong_thoi_gian_clinic_fk,
    ADD  CONSTRAINT luot_dong_thoi_gian_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.capability_grant
    DROP CONSTRAINT IF EXISTS capability_grant_clinic_fk,
    ADD  CONSTRAINT capability_grant_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.dich_vu_mau_ket_qua
    DROP CONSTRAINT IF EXISTS dich_vu_mau_ket_qua_clinic_fk,
    ADD  CONSTRAINT dich_vu_mau_ket_qua_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.form_instance
    DROP CONSTRAINT IF EXISTS form_instance_clinic_fk,
    ADD  CONSTRAINT form_instance_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;

ALTER TABLE public.hen_gio
    DROP CONSTRAINT IF EXISTS hen_gio_clinic_fk,
    ADD  CONSTRAINT hen_gio_clinic_fk
         FOREIGN KEY (clinic_id) REFERENCES public.clinic(id) ON DELETE RESTRICT;
