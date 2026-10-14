-- SỔ NỢ HAI CHIỀU (Tuyền chốt 14/10/2026 — docs/KE-HOACH-DONG-TIEN-KHO-KE-TOAN-1410.md G4b).
--
-- Kế toán giữ hai sổ cho mỗi lượt khám ĐÃ VỀ (check-out, hoặc lượt của ngày
-- trước chưa đóng):
--   PHAI_THU — khách nợ phòng khám (dịch vụ đã làm / thuốc đã lấy mà chưa thu).
--   PHAI_TRA — phòng khám nợ khách (đã thu mà chưa làm / đã bỏ / không làm,
--              trừ phần đã hoàn; "giữ lại tiền thừa" vẫn là nợ khách).
--
-- Mỗi dòng là một CHÊNH LỆCH có dấu so với số dư trước của chính lượt ấy, kèm
-- số dư sau, vì sao (loai + sự kiện gây ra), ai, lúc nào. Không sửa, không xoá:
-- số của ngày đã qua không bao giờ đổi — sửa sau = một dòng mới ở ngày sửa.
--
-- Một chỗ ghi duy nhất: bên nhận `so_no` (events/consumers/so_no.py) tính lại số
-- dư bằng chính các hàm đang chặn check-out (`no_khi_ve`, tiền thừa, "đã thu
-- chưa làm") rồi ghi phần chênh. Lượt đối chiếu định kỳ quét bù những thay đổi
-- không phát sự kiện (hoàn tiền xong / thất bại) và ghi SỐ DƯ ĐẦU KỲ cho lượt
-- có trước ngày bật sổ (`so_no_moc`).
--
-- Chạy lại được.

CREATE TABLE IF NOT EXISTS public.so_no (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Thứ tự ghi tuyệt đối — "số dư trước" = dòng có seq lớn nhất của lượt.
    seq               bigint GENERATED ALWAYS AS IDENTITY,
    clinic_id         uuid NOT NULL REFERENCES public.clinic (id) ON DELETE RESTRICT,
    visit_id          uuid NOT NULL,
    clinic_patient_id uuid NOT NULL
                           REFERENCES public.patient (clinic_patient_id)
                           ON DELETE RESTRICT,
    chieu             text NOT NULL CHECK (chieu IN ('PHAI_THU', 'PHAI_TRA')),
    -- Chênh lệch có dấu (+ phát sinh thêm, − giảm). Không có dòng 0đ.
    so_tien           numeric(12, 0) NOT NULL CHECK (so_tien <> 0),
    so_du             numeric(12, 0) NOT NULL CHECK (so_du >= 0),
    loai              text NOT NULL CHECK (loai IN (
                          'DAU_KY',        -- số dư lúc bật sổ (lượt có trước mốc)
                          'KHI_VE',        -- khách về / lượt đóng
                          'MO_LAI_LUOT',   -- mở lại lượt đã đóng
                          'GHI_NO',        -- lễ tân ghi nợ / ghi lại / huỷ ghi nợ
                          'THU',           -- lần thu (thu nợ, thu thêm)
                          'HUY_PHIEU',     -- huỷ phiếu / huỷ lần CK chờ
                          'HOAN_TIEN',
                          'DOI_CHI_DINH',  -- bỏ / đặt lại / làm xong / không làm
                          'DOI_CHIEU')),   -- lượt đối chiếu định kỳ thấy lệch
    -- Sự kiện gây ra (domain_event). NULL = lượt đối chiếu định kỳ.
    su_kien_id        uuid,
    su_kien_ten       text,
    boi               uuid REFERENCES public.staff (id),
    -- Giờ NGHIỆP VỤ (giờ sự kiện xảy ra) — báo cáo lọc theo cột này.
    luc               timestamptz NOT NULL,
    ghi_luc           timestamptz NOT NULL DEFAULT now(),
    -- Các khoản tạo nên số dư SAU dòng này: [{ten, so_tien, loai}].
    chi_tiet          jsonb NOT NULL DEFAULT '[]'::jsonb
                           CHECK (jsonb_typeof(chi_tiet) = 'array'),
    CONSTRAINT so_no_luot_fk FOREIGN KEY (clinic_id, visit_id)
        REFERENCES public.visit (clinic_id, visit_id) ON DELETE RESTRICT
);

-- Một sự kiện chỉ ghi một lần mỗi chiều (bên nhận chạy lại / phát lại thì im).
CREATE UNIQUE INDEX IF NOT EXISTS ux_so_no_su_kien
    ON public.so_no (clinic_id, su_kien_id, chieu)
    WHERE su_kien_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_so_no_luc ON public.so_no (clinic_id, luc);
CREATE INDEX IF NOT EXISTS ix_so_no_luot
    ON public.so_no (clinic_id, visit_id, chieu, seq DESC);
CREATE INDEX IF NOT EXISTS ix_so_no_khach
    ON public.so_no (clinic_id, clinic_patient_id, luc DESC);

COMMENT ON TABLE public.so_no IS
'Sổ nợ hai chiều theo lượt (14/10/2026): PHAI_THU khách nợ phòng khám, PHAI_TRA '
'phòng khám nợ khách. Mỗi dòng = chênh lệch có dấu + số dư sau. Chỉ thêm.';

-- Số dư sau phải đúng bằng số dư trước + chênh lệch: hai bên nhận chạy chen
-- nhau (hoặc ai đó INSERT tay) không thể làm sổ tự mâu thuẫn.
CREATE OR REPLACE FUNCTION public.so_no_kiem_so_du()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    truoc numeric(12, 0);
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('so_no:' || NEW.clinic_id || ':' || NEW.visit_id));
    SELECT so_du INTO truoc FROM public.so_no
     WHERE clinic_id = NEW.clinic_id AND visit_id = NEW.visit_id
       AND chieu = NEW.chieu
     ORDER BY seq DESC LIMIT 1;
    IF coalesce(truoc, 0) + NEW.so_tien <> NEW.so_du THEN
        RAISE EXCEPTION 'so_no: số dư lệch (trước %, chênh %, sau %)',
            coalesce(truoc, 0), NEW.so_tien, NEW.so_du
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_so_no_kiem_so_du ON public.so_no;
CREATE TRIGGER trg_so_no_kiem_so_du
    BEFORE INSERT ON public.so_no
    FOR EACH ROW EXECUTE FUNCTION public.so_no_kiem_so_du();

CREATE OR REPLACE FUNCTION public.so_no_chi_them()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'so_no: sổ chỉ thêm — sửa bằng một dòng chênh lệch mới'
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS trg_so_no_chi_them ON public.so_no;
CREATE TRIGGER trg_so_no_chi_them
    BEFORE UPDATE OR DELETE ON public.so_no
    FOR EACH ROW EXECUTE FUNCTION public.so_no_chi_them();

DROP TRIGGER IF EXISTS trg_notify_so_no ON public.so_no;
CREATE TRIGGER trg_notify_so_no
    AFTER INSERT ON public.so_no
    FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();

ALTER TABLE public.so_no ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS so_no_select_own_clinic ON public.so_no;
CREATE POLICY so_no_select_own_clinic ON public.so_no
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT ON public.so_no TO service_role;

-- Mốc bật sổ của từng phòng khám: lượt có TRƯỚC mốc mà còn số dư thì lượt đối
-- chiếu ghi một dòng DAU_KY (giờ = mốc) — không đoán lịch sử theo từng ngày.
-- Ghi đầu kỳ chạy dần trong worker (giờ tạo lượt giảm dần — lượt gần đây, dễ bị
-- đụng tới nhất, đi trước); con trỏ (dau_ky_den, dau_ky_den_id) nhớ chỗ dừng.
CREATE TABLE IF NOT EXISTS public.so_no_moc (
    clinic_id     uuid PRIMARY KEY REFERENCES public.clinic (id) ON DELETE RESTRICT,
    bat_dau       timestamptz NOT NULL DEFAULT now(),
    dau_ky_den    timestamptz,
    dau_ky_den_id uuid,
    dau_ky_xong   boolean NOT NULL DEFAULT false
);
INSERT INTO public.so_no_moc (clinic_id)
SELECT id FROM public.clinic
ON CONFLICT (clinic_id) DO NOTHING;
ALTER TABLE public.so_no_moc ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS so_no_moc_select_own_clinic ON public.so_no_moc;
CREATE POLICY so_no_moc_select_own_clinic ON public.so_no_moc
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.so_no_moc TO service_role;
