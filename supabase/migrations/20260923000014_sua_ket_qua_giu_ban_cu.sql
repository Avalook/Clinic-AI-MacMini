-- Sửa kết quả mà không mất bản cũ (23/09/2026).
--
-- CHUYỆN CÓ THẬT Ở PHÒNG KHÁM NÀY: kết quả được IN RA GIẤY và giao cho khách
-- (Notion "output - tờ in kết quả"). Nên một bản đã phát hành rồi mới phát hiện
-- sai thì bản cũ KHÔNG được biến mất — người bệnh đang cầm nó trên tay.
--
-- Bản trước ghi đè `form_instance.du_lieu` rồi chỉ phát `result.corrected`.
-- Tức là hệ thống ghi RẰNG có sửa, không ghi SỬA CÁI GÌ. Hỏi "trước khi sửa nó
-- ghi gì" thì không chỗ nào trả lời được.
--
-- KHÔNG DỰNG HỆ PHIÊN BẢN THỨ HAI. `visit_amendment` đã là bảng chỉ-thêm với
-- `original_values` + `corrected_values`, và `prescription_correction` đã chứng
-- minh khuôn ấy dùng lại được cho một miền khác. Đi đúng đường đó.
--
--     form_instance  →  result_correction  →  visit_amendment
--                       (link mỏng)           (ảnh chụp đầy đủ)

-- ── 1. Hai lỗ có sẵn của form_instance ─────────────────────────────────────
-- `service_order_id` là NOT NULL nhưng KHÔNG có khoá ngoại nào: một phiếu kết
-- quả trỏ vào chỉ định không tồn tại, hoặc của phòng khám khác, mà không gì
-- chặn. Cột ghép chặn cả hai. `UNIQUE (clinic_id, id)` là thứ `result_correction`
-- và `form_result_release` cần để khoá ngoại của chúng không đi xuyên phòng khám.
-- THÊM NẾU CHƯA CÓ, KHÔNG "DROP RỒI ADD". Chạy lần hai thì `result_correction`
-- đã trỏ vào chỉ mục này, nên DROP hỏng: "other objects depend on it". Migration
-- từ 20260730 trở đi phải chạy lại được — `db push` có thể thử lại, và bài diễn
-- tập phục hồi phát lại cả chuỗi.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_form_instance_clinic_id'
                      AND conrelid = 'public.form_instance'::regclass) THEN
        ALTER TABLE public.form_instance
            ADD CONSTRAINT uq_form_instance_clinic_id UNIQUE (clinic_id, id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'form_instance_order_fk'
                      AND conrelid = 'public.form_instance'::regclass) THEN
        ALTER TABLE public.form_instance
            ADD CONSTRAINT form_instance_order_fk
            FOREIGN KEY (clinic_id, service_order_id)
            REFERENCES public.service_order(clinic_id, id) ON DELETE RESTRICT;
    END IF;
END $$;

-- ── 2. Bản nháp của lần sửa, tách khỏi bản chính thức ──────────────────────
-- VÌ SAO CẦN CỘT NÀY. Luồng sửa có hai bước: [Sửa lại] mở chế độ sửa, [Xác nhận
-- sửa] mới chốt. Giữa hai bước ấy người dùng gõ và TỰ LƯU nhiều lần. Bản trước
-- cho tự lưu ghi thẳng vào `du_lieu`, nên:
--
--   * câu trên màn "bản cũ vẫn là kết quả chính thức" là SAI ngay từ lần gõ đầu;
--   * tới lúc chốt thì bản v1 không còn đọc được nữa để mà chụp lại.
--
--     du_lieu            LUÔN là bản kết quả chính thức hiện hành.
--     du_lieu_dang_sua   bản nháp của lần sửa, chỉ tồn tại khi dang_sua = true.
--
-- [Sửa lại] chép `du_lieu` sang nháp MỘT LẦN. Người thứ hai mở ra sửa thì thấy
-- đúng bản nháp đang có, KHÔNG chép lại từ bản chính thức — chép lại là xoá mất
-- những gì người đầu vừa gõ.
-- METADATA CŨNG PHẢI ĐI THEO BẢN NHÁP, không chỉ nội dung.
--
-- Contract Form Engine từ đầu đã tách `nhap_boi` (người GÕ — nhật ký) khỏi
-- `thuc_hien_boi` (người LÀM — dữ liệu nghiệp vụ). Nếu bản nháp chỉ mang JSON
-- thì hai thứ ấy không có chỗ đứng trong lúc sửa, và hệ thống mất dấu:
--
--     v1: điều dưỡng A nhập · bác sĩ B thực hiện
--     sửa: điều dưỡng C gõ · bác sĩ B vẫn là người thực hiện
--          · bác sĩ D bấm [Xác nhận sửa]
--
-- Ba người, ba vai. Thiếu cột nháp thì C biến mất hoàn toàn.
--
-- Còn một hệ quả thực dụng: màn hình cho CHỌN người thực hiện. Nếu chỉ tự lưu
-- JSON thì đổi lựa chọn ấy rồi tải lại trang là mất — tức tự lưu mới lưu nửa
-- cái phiếu.
ALTER TABLE public.form_instance
    ADD COLUMN IF NOT EXISTS du_lieu_dang_sua jsonb,
    ADD COLUMN IF NOT EXISTS nhap_boi_dang_sua uuid REFERENCES public.staff(id),
    ADD COLUMN IF NOT EXISTS thuc_hien_boi_dang_sua uuid REFERENCES public.staff(id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'form_instance_dang_sua_co_nhap'
                      AND conrelid = 'public.form_instance'::regclass) THEN
        ALTER TABLE public.form_instance
            ADD CONSTRAINT form_instance_dang_sua_co_nhap
            CHECK (dang_sua = (du_lieu_dang_sua IS NOT NULL));
    END IF;
END $$;

COMMENT ON COLUMN public.form_instance.du_lieu IS
    'Bản kết quả CHÍNH THỨC hiện hành. Tự lưu lúc đang sửa KHÔNG chạm vào đây.';
COMMENT ON COLUMN public.form_instance.du_lieu_dang_sua IS
    'Bản nháp của lần sửa. Chỉ có khi dang_sua = true; [Xác nhận sửa] mới đẩy nó thành chính thức.';
COMMENT ON COLUMN public.form_instance.nhap_boi_dang_sua IS
    'Người GÕ bản nháp. Khác người gõ bản chính thức, và khác người bấm [Xác nhận sửa].';
COMMENT ON COLUMN public.form_instance.thuc_hien_boi_dang_sua IS
    'Người THỰC HIỆN theo lựa chọn đang sửa. Có cột riêng thì đổi lựa chọn rồi tải lại trang không mất.';

-- ── 3. Một lần sửa kết quả ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.result_correction (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    form_instance_id uuid NOT NULL,
    -- CHỈ để khoá toàn vẹn, không để đọc. `form_instance` cố ý KHÔNG giữ
    -- `visit_id`: nó suy được qua service_order, và một bản sao là một chỗ để
    -- lệch. Trigger dưới ép hai nguồn luôn khớp.
    visit_id         uuid NOT NULL,
    -- PHIÊN BẢN CHUYÊN MÔN, không bao giờ là `form_instance.revision` —
    -- `revision` tăng cả khi tự lưu nháp, nên lấy nó làm số bản là nói với bác
    -- sĩ rằng kết quả đã sang bản 14 trong khi chưa ai sửa gì.
    -- v1 = lần [Hoàn tất] đầu tiên, nằm trong chính form_instance.
    ban_thu          integer NOT NULL CHECK (ban_thu >= 2),
    -- Người · lý do · lúc nào đọc Ở ĐÂY. Chép sang là mở đường cho hai chỗ lệch.
    amendment_id     uuid NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_result_correction_ban UNIQUE (clinic_id, form_instance_id, ban_thu),
    -- Một lần sửa sinh ĐÚNG MỘT amendment.
    CONSTRAINT uq_result_correction_amendment UNIQUE (amendment_id),
    CONSTRAINT result_correction_form_fk
        FOREIGN KEY (clinic_id, form_instance_id)
        REFERENCES public.form_instance(clinic_id, id) ON DELETE RESTRICT,
    CONSTRAINT result_correction_amendment_fk
        FOREIGN KEY (amendment_id, clinic_id, visit_id)
        REFERENCES public.visit_amendment(amendment_id, clinic_id, visit_id)
        ON DELETE RESTRICT,
    CONSTRAINT result_correction_visit_fk
        FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit(clinic_id, visit_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_result_correction_phieu
    ON public.result_correction (clinic_id, form_instance_id, ban_thu);

-- ── 4. Quyền phát hành, theo TỪNG BẢN ──────────────────────────────────────
-- `release` = BÁC SĨ CHO PHÉP GỬI. KHÔNG phải "bệnh nhân đã nhận" — dấu đã-nhận
-- thật hiện chỉ có `tep_ket_qua.gui_luc`, và nó chỉ phủ tệp, chưa phủ tờ in giao
-- tay. Lớp "đã giao" là việc riêng, chưa làm.
--
-- SỬA v1 → v2 THÌ DÒNG CỦA v1 Ở LẠI. Không có "hạ cờ", nên không có chỗ nào xoá
-- mất sự thật rằng v1 từng được duyệt. v2 chưa có dòng nên chưa được gửi — bản
-- mới không thừa hưởng quyền của bản cũ.
--
-- HAI GIỚI HẠN, ghi ra để không ai đọc nhầm bảng này thành thứ nó chưa là:
--
-- 1. CHỈ CẤP, CHƯA THU HỒI. Bác sĩ duyệt nhầm rồi muốn rút lại mà không sửa nội
--    dung là một luồng khác, chưa làm. "Chưa có thu hồi" không có nghĩa "đã
--    duyệt là vĩnh viễn".
--
-- 2. CHƯA CÓ AI HỎI BẢNG NÀY. Kiểm ngày 23/09: KHÔNG đường gửi hay in nào đọc
--    `form_instance` — `/print/sono` in `ultrasound_record` (bảng đời cũ), và
--    `tep_ket_qua` là đường TỆP, khác hẳn kết quả có cấu trúc. Nên bảng này
--    hiện là NỀN và nguồn sự thật, chưa phải hàng rào đang chặn ai.
--
--    Câu "v2 chưa duyệt thì không gửi được" chỉ thành thật khi đường phát hành
--    kết quả có cấu trúc được dựng và nó hỏi `form_result_release` của đúng
--    `ban_thu` hiện hành. Đừng viết tài liệu nói nó đã chặn.
CREATE TABLE IF NOT EXISTS public.form_result_release (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE RESTRICT,
    form_instance_id uuid NOT NULL,
    ban_thu          integer NOT NULL CHECK (ban_thu >= 1),
    released_by      uuid NOT NULL REFERENCES public.staff(id) ON DELETE RESTRICT,
    released_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_form_result_release_ban
        UNIQUE (clinic_id, form_instance_id, ban_thu),
    CONSTRAINT form_result_release_form_fk
        FOREIGN KEY (clinic_id, form_instance_id)
        REFERENCES public.form_instance(clinic_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_form_result_release_phieu
    ON public.form_result_release (clinic_id, form_instance_id, ban_thu);

-- ── 5. Hai bất biến ép ở Postgres, không nhờ Python nhớ ────────────────────
CREATE OR REPLACE FUNCTION public.result_correction_hop_le() RETURNS trigger AS $$
DECLARE
    luot_dung   uuid;
    ban_ke_tiep integer;
BEGIN
    -- (1) Đúng lượt của chỉ định mà phiếu này thuộc về.
    SELECT o.visit_id INTO luot_dung
      FROM public.form_instance f
      JOIN public.service_order o
        ON o.clinic_id = f.clinic_id AND o.id = f.service_order_id
     WHERE f.clinic_id = NEW.clinic_id AND f.id = NEW.form_instance_id;

    IF luot_dung IS DISTINCT FROM NEW.visit_id THEN
        RAISE EXCEPTION
            'result_correction.visit_id (%) khac luot cua phieu (%)',
            NEW.visit_id, luot_dung;
    END IF;

    -- (2) Bản kế tiếp LIỀN MẠCH. v1 nằm trong form_instance, nên bản mới luôn
    --     là 2 + số lần đã sửa. Không cho chèn v7 khi mới có v1.
    --
    --     Đây chặn CHÈN BẬY, không chặn ĐUA NHAU: hai giao dịch cùng lúc có thể
    --     cùng đọc ra v2. Thứ chặn đua là `uq_result_correction_ban`. Hai lớp
    --     cho hai chuyện khác nhau, không lớp nào thay được lớp kia.
    SELECT 2 + count(*) INTO ban_ke_tiep
      FROM public.result_correction c
     WHERE c.clinic_id = NEW.clinic_id
       AND c.form_instance_id = NEW.form_instance_id;

    IF NEW.ban_thu <> ban_ke_tiep THEN
        RAISE EXCEPTION
            'ban ket qua phai lien mach: cho v%, nhan v%',
            ban_ke_tiep, NEW.ban_thu;
    END IF;

    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_result_correction_hop_le ON public.result_correction;
CREATE TRIGGER trg_result_correction_hop_le
    BEFORE INSERT ON public.result_correction
    FOR EACH ROW EXECUTE FUNCTION public.result_correction_hop_le();

-- Không duyệt phát hành một bản chưa tồn tại.
CREATE OR REPLACE FUNCTION public.release_ban_phai_co_that() RETURNS trigger AS $$
BEGIN
    IF NEW.ban_thu = 1 THEN
        RETURN NEW;  -- v1 = lần [Hoàn tất] đầu tiên, nằm trong form_instance
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.result_correction c
         WHERE c.clinic_id = NEW.clinic_id
           AND c.form_instance_id = NEW.form_instance_id
           AND c.ban_thu = NEW.ban_thu) THEN
        RAISE EXCEPTION
            'khong the duyet phat hanh ban v% — ban ay chua ton tai', NEW.ban_thu;
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_release_ban_phai_co_that ON public.form_result_release;
CREATE TRIGGER trg_release_ban_phai_co_that
    BEFORE INSERT ON public.form_result_release
    FOR EACH ROW EXECUTE FUNCTION public.release_ban_phai_co_that();

-- ── 6. Chỉ thêm, không sửa, không xoá ──────────────────────────────────────
-- Cùng nếp `visit_amendment` và `domain_event`: sửa lịch sử y khoa không phải
-- là một câu SQL.
CREATE OR REPLACE FUNCTION public.chi_duoc_them_ket_qua() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% chi duoc THEM: lich su ket qua khong sua, khong xoa',
        TG_TABLE_NAME;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_result_correction_chi_them ON public.result_correction;
CREATE TRIGGER trg_result_correction_chi_them
    BEFORE UPDATE OR DELETE ON public.result_correction
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

DROP TRIGGER IF EXISTS trg_form_result_release_chi_them ON public.form_result_release;
CREATE TRIGGER trg_form_result_release_chi_them
    BEFORE UPDATE OR DELETE ON public.form_result_release
    FOR EACH ROW EXECUTE FUNCTION public.chi_duoc_them_ket_qua();

-- ── 7. Phạm vi phòng khám ──────────────────────────────────────────────────
ALTER TABLE public.result_correction   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_result_release ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS result_correction_select_own_clinic ON public.result_correction;
CREATE POLICY result_correction_select_own_clinic ON public.result_correction
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));

DROP POLICY IF EXISTS form_result_release_select_own_clinic ON public.form_result_release;
CREATE POLICY form_result_release_select_own_clinic ON public.form_result_release
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));

GRANT SELECT ON public.result_correction   TO authenticated;
GRANT SELECT ON public.form_result_release TO authenticated;
GRANT SELECT, INSERT ON public.result_correction   TO service_role;
GRANT SELECT, INSERT ON public.form_result_release TO service_role;
