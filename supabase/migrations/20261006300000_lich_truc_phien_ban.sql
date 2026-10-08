-- Lịch trực có lịch sử thay đổi (Khối 3, Tuyền chốt 06/10/2026).
--
-- Trưởng ca cần xem lại lịch của một tuần ở từng thời điểm, kiểu lịch sử
-- Google Docs: lịch gốc lúc áp dụng, rồi mỗi lần đổi người / xoá ca / thêm
-- người vào ca trống là một phiên bản, ô đổi được tô màu so với bản trước.
--
-- Vì sao ghi bằng TRIGGER chứ không ghi trong Python: lịch trực đang được ghi
-- từ 5 chỗ ở 2 service (thêm ca, sửa ca, xoá ca, đổi người trong ca, khách đặt
-- tự trải ca). Ghi ở hàm thì sửa một lối sót lối khác — đúng loại lỗi từng cắn
-- (CLAUDE.md "Sửa giao diện"). Ở tầng bảng thì không lối nào, kể cả lối thêm
-- sau này, đi vòng được.
--
-- Một PHIÊN BẢN = một giao dịch: đổi người trong ca là một UPDATE + một dòng
-- sổ thay người, cùng một txid → cùng một phiên bản. Không cần bảng phiên bản
-- riêng; dựng lại phiên bản = ảnh lịch gốc + các thay đổi theo thứ tự txid.
--
-- Người sửa: trigger không biết ai bấm, nên service đặt
-- `set_config('app.staff_id', <staff>, true)` trong giao dịch. Lối nào quên đặt
-- thì vẫn ghi được thay đổi, chỉ thiếu tên người — không bao giờ chặn thao tác.
--
-- Lịch sử chỉ có từ lúc migration này chạy: thay đổi trước đó không có sổ.
-- Tuần ĐÃ áp dụng trước ngày lên bản được chụp một ảnh `LEN_BAN` ngay trong
-- migration — để thay đổi từ nay về sau của tuần ấy có một mốc mà so.
--
-- Hàm trigger là SECURITY DEFINER: ai ghi được lịch trực thì sổ cũng ghi được,
-- không phụ thuộc quyền/RLS của vai đang ghi (API ghi bằng `postgres`, nhưng
-- một lối ghi sau này bằng vai khác không được làm hỏng cú xếp ca).

-- ── Ảnh lịch lúc áp dụng tuần ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lich_truc_anh (
    id            bigserial   PRIMARY KEY,
    -- CASCADE: xoá phòng khám (dọn dữ liệu thử) không bị sổ lịch sử chặn lại.
    clinic_id     uuid        NOT NULL REFERENCES public.clinic(id) ON DELETE CASCADE,
    week_start    date        NOT NULL,
    -- GOC = lần áp dụng đầu tiên; AP_DUNG_LAI = sửa rồi bấm áp dụng lại;
    -- LEN_BAN = tuần đã áp dụng TRƯỚC ngày lên bản này (chụp trong migration).
    loai          text        NOT NULL CHECK (loai IN ('GOC', 'AP_DUNG_LAI', 'LEN_BAN')),
    txid          bigint      NOT NULL DEFAULT txid_current(),
    luc           timestamptz NOT NULL DEFAULT now(),
    boi_staff_id  uuid        REFERENCES public.staff(id) ON DELETE SET NULL,
    -- Mỗi phần tử: {id, work_date, shift, station, staff_id, staff_name, status}
    ca            jsonb       NOT NULL
);
CREATE INDEX IF NOT EXISTS lich_truc_anh_tuan
    ON public.lich_truc_anh (clinic_id, week_start, txid);

-- ── Sổ từng thay đổi ô lịch ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lich_truc_thay_doi (
    id            bigserial   PRIMARY KEY,
    clinic_id     uuid        NOT NULL REFERENCES public.clinic(id) ON DELETE CASCADE,
    week_start    date        NOT NULL,
    roster_id     uuid        NOT NULL,           -- work_roster.id (dòng có thể đã xoá)
    hanh_dong     text        NOT NULL CHECK (hanh_dong IN ('THEM', 'XOA', 'DOI_NGUOI', 'SUA')),
    truoc         jsonb,                          -- NULL khi THEM
    sau           jsonb,                          -- NULL khi XOA
    txid          bigint      NOT NULL DEFAULT txid_current(),
    luc           timestamptz NOT NULL DEFAULT now(),
    boi_staff_id  uuid        REFERENCES public.staff(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS lich_truc_thay_doi_tuan
    ON public.lich_truc_thay_doi (clinic_id, week_start, txid, id);

ALTER TABLE public.lich_truc_anh ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lich_truc_thay_doi ENABLE ROW LEVEL SECURITY;

-- Người bấm: đọc từ giao dịch; rác / trống → NULL, không ném.
CREATE OR REPLACE FUNCTION public.lich_truc_nguoi_bam()
RETURNS uuid
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v text := nullif(current_setting('app.staff_id', true), '');
BEGIN
    IF v IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN v::uuid;
EXCEPTION WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.lich_truc_o(r public.work_roster)
RETURNS jsonb
LANGUAGE sql IMMUTABLE
AS $$
    SELECT jsonb_build_object(
        'id', r.id, 'work_date', r.work_date, 'shift', r.shift,
        'station', r.station, 'staff_id', r.staff_id,
        'staff_name', r.staff_name, 'status', r.status
    )
$$;

CREATE OR REPLACE FUNCTION public.lich_truc_ghi_thay_doi()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    hd text;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.lich_truc_thay_doi
            (clinic_id, week_start, roster_id, hanh_dong, sau, boi_staff_id)
        VALUES (NEW.clinic_id, NEW.week_start, NEW.id, 'THEM',
                public.lich_truc_o(NEW), public.lich_truc_nguoi_bam());
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO public.lich_truc_thay_doi
            (clinic_id, week_start, roster_id, hanh_dong, truoc, boi_staff_id)
        VALUES (OLD.clinic_id, OLD.week_start, OLD.id, 'XOA',
                public.lich_truc_o(OLD), public.lich_truc_nguoi_bam());
        RETURN OLD;
    END IF;

    -- UPDATE: chỉ ghi khi đổi thứ người xem thấy trên bảng lịch (đổi thứ tự
    -- sắp xếp / dấu thời gian thì bỏ qua).
    IF public.lich_truc_o(OLD) = public.lich_truc_o(NEW) THEN
        RETURN NEW;
    END IF;
    -- Dòng chuyển sang TUẦN KHÁC (đổi ngày): mỗi tuần một sổ, nên tuần cũ thấy
    -- ca biến mất, tuần mới thấy ca xuất hiện.
    IF OLD.week_start IS DISTINCT FROM NEW.week_start
       OR OLD.clinic_id IS DISTINCT FROM NEW.clinic_id THEN
        INSERT INTO public.lich_truc_thay_doi
            (clinic_id, week_start, roster_id, hanh_dong, truoc, boi_staff_id)
        VALUES (OLD.clinic_id, OLD.week_start, OLD.id, 'XOA',
                public.lich_truc_o(OLD), public.lich_truc_nguoi_bam());
        INSERT INTO public.lich_truc_thay_doi
            (clinic_id, week_start, roster_id, hanh_dong, sau, boi_staff_id)
        VALUES (NEW.clinic_id, NEW.week_start, NEW.id, 'THEM',
                public.lich_truc_o(NEW), public.lich_truc_nguoi_bam());
        RETURN NEW;
    END IF;
    hd := CASE
        WHEN OLD.staff_id IS DISTINCT FROM NEW.staff_id
          OR OLD.staff_name IS DISTINCT FROM NEW.staff_name THEN 'DOI_NGUOI'
        ELSE 'SUA'
    END;
    INSERT INTO public.lich_truc_thay_doi
        (clinic_id, week_start, roster_id, hanh_dong, truoc, sau, boi_staff_id)
    VALUES (NEW.clinic_id, NEW.week_start, NEW.id, hd,
            public.lich_truc_o(OLD), public.lich_truc_o(NEW),
            public.lich_truc_nguoi_bam());
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lich_truc_ghi_thay_doi ON public.work_roster;
CREATE TRIGGER lich_truc_ghi_thay_doi
    AFTER INSERT OR UPDATE OR DELETE ON public.work_roster
    FOR EACH ROW EXECUTE FUNCTION public.lich_truc_ghi_thay_doi();

-- Áp dụng tuần (upsert roster_week) → chụp ảnh cả tuần.
CREATE OR REPLACE FUNCTION public.lich_truc_chup_anh()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.lich_truc_anh (clinic_id, week_start, loai, boi_staff_id, ca)
    SELECT NEW.clinic_id, NEW.week_start,
           CASE WHEN EXISTS (SELECT 1 FROM public.lich_truc_anh a
                              WHERE a.clinic_id = NEW.clinic_id
                                AND a.week_start = NEW.week_start)
                THEN 'AP_DUNG_LAI' ELSE 'GOC' END,
           coalesce(public.lich_truc_nguoi_bam(), NEW.applied_by_staff_id),
           coalesce(jsonb_agg(public.lich_truc_o(w) ORDER BY w.work_date, w.shift,
                              w.station, w.sort), '[]'::jsonb)
      FROM public.work_roster w
     WHERE w.clinic_id = NEW.clinic_id AND w.week_start = NEW.week_start;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lich_truc_chup_anh ON public.roster_week;
CREATE TRIGGER lich_truc_chup_anh
    AFTER INSERT OR UPDATE OF applied_at ON public.roster_week
    FOR EACH ROW EXECUTE FUNCTION public.lich_truc_chup_anh();

-- ── Mốc cho tuần đã áp dụng trước ngày lên bản ─────────────────────────────
-- Không có ảnh này thì đổi người trong tuần đang chạy (đã áp dụng hôm qua)
-- không có gì để so, và màn sẽ báo "chưa có lịch sử" cho đúng tuần cần xem nhất.
INSERT INTO public.lich_truc_anh (clinic_id, week_start, loai, ca)
SELECT rw.clinic_id, rw.week_start, 'LEN_BAN',
       coalesce((SELECT jsonb_agg(public.lich_truc_o(w)
                                  ORDER BY w.work_date, w.shift, w.station, w.sort)
                   FROM public.work_roster w
                  WHERE w.clinic_id = rw.clinic_id
                    AND w.week_start = rw.week_start), '[]'::jsonb)
  FROM public.roster_week rw
 WHERE NOT EXISTS (SELECT 1 FROM public.lich_truc_anh a
                    WHERE a.clinic_id = rw.clinic_id
                      AND a.week_start = rw.week_start);

COMMENT ON TABLE public.lich_truc_anh IS
'Ảnh cả tuần lịch trực lúc áp dụng tuần (GOC / AP_DUNG_LAI) hoặc lúc lên bản (LEN_BAN). Chỉ thêm — trigger lich_truc_chup_anh ghi.';
COMMENT ON TABLE public.lich_truc_thay_doi IS
'Sổ từng thay đổi ô lịch trực (THEM/XOA/DOI_NGUOI/SUA), một giao dịch = một phiên bản (txid). Chỉ thêm — trigger lich_truc_ghi_thay_doi ghi.';
