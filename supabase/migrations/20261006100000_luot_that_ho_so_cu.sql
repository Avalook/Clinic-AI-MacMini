-- Chuyển lịch sử khám cũ (schema lich_su_notion, nạp 06/10/2026) thành LƯỢT THẬT.
--
-- Bộ chuyển: src/clinicai/services/chuyen_luot_that.py (một giao dịch, mặc định
-- thử khô). Migration này chỉ tạo SỔ GHÉP (lượt cũ → bản ghi thật) để chạy lại
-- không sinh trùng và gỡ được (scripts/hoan-tac-luot-that.sql), và cho bộ sinh
-- việc nhắc tái khám bỏ qua lượt chuyển từ hồ sơ cũ.

CREATE TABLE IF NOT EXISTS lich_su_notion.lan_chuyen (
    id            bigserial PRIMARY KEY,
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id),
    bat_dau       timestamptz NOT NULL DEFAULT now(),
    so_lieu       jsonb,
    hoan_tac_luc  timestamptz
);

-- Một dòng cho MỖI lượt cũ. Nhiều lượt cũ cùng khách cùng ngày gộp vào một lượt
-- thật (cùng visit_id). trung_luot_co_san = ngày đó khách đã có lượt thật trên
-- hệ thống (nhập song song từ 18/09) → không tạo lượt thứ hai, visit_id NULL,
-- bản cũ vẫn xem ở khối "Hồ sơ khám trước 10/2026".
CREATE TABLE IF NOT EXISTS lich_su_notion.luot_that (
    notion_id          uuid PRIMARY KEY REFERENCES lich_su_notion.luot_kham(notion_id),
    clinic_id          uuid NOT NULL REFERENCES public.clinic(id),
    lan_chuyen_id      bigint NOT NULL REFERENCES lich_su_notion.lan_chuyen(id),
    appointment_id     uuid,
    visit_id           uuid,
    trung_luot_co_san  boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS luot_that_visit_idx ON lich_su_notion.luot_that (visit_id);

-- Bản ghi thật sinh ra từ một bản ghi cũ (chỉ định, tờ kết quả, tệp, đơn thuốc…).
CREATE TABLE IF NOT EXISTS lich_su_notion.ban_ghi_that (
    notion_id      uuid NOT NULL,
    bang           text NOT NULL,
    ban_ghi_id     uuid NOT NULL,
    lan_chuyen_id  bigint NOT NULL REFERENCES lich_su_notion.lan_chuyen(id),
    PRIMARY KEY (notion_id, bang, ban_ghi_id)
);
CREATE INDEX IF NOT EXISTS ban_ghi_that_ban_ghi_idx ON lich_su_notion.ban_ghi_that (bang, ban_ghi_id);

CREATE OR REPLACE FUNCTION public.sinh_viec_nhac_tai_kham(
    p_clinic_id uuid,
    p_ngay      date DEFAULT NULL
)
RETURNS TABLE (luot1_moi integer, luot2_moi integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_ngay  date;
    v_l1    integer;
    v_l2    integer;
BEGIN
    v_ngay := coalesce(p_ngay,
                       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date);

    -- ── LƯỢT 1 — bác sĩ dặn quay lại, khách chưa đặt lịch ──────────────────
    --
    -- Cửa sổ: ngày tái khám còn TỪ 0 TỚI 7 ngày nữa. Cận trên là 7 (đúng luật
    -- "gọi trước 5–7 ngày"); cận dưới là 0 chứ không phải 5, vì một việc chỉ
    -- sinh ra trong ba ngày rồi biến mất là một việc sẽ bị bỏ lỡ. Việc sinh
    -- sớm nhất có thể, `han_goi` nói ngày nên gọi, và nó nằm đó tới khi có
    -- người đóng.
    WITH benh_an AS (
        SELECT DISTINCT ON (v.clinic_patient_id)
               v.clinic_patient_id,
               v.visit_id,
               -- Phiếu khám v5 (mục G "Ngày tái khám", ô `*_follow_date`) TRƯỚC,
               -- bệnh án cũ SAU (26/09/2026). Trước đó hàm JOIN bệnh án cũ —
               -- lượt dùng phiếu v5 không có dòng ấy nên không bao giờ được nhắc.
               coalesce(
                 (SELECT max(nullif(btrim(o.value ->> 'gia_tri'), ''))
                    FROM public.phieu_kham_luot p,
                         jsonb_each(p.du_lieu) AS o
                   WHERE p.clinic_id = v.clinic_id AND p.visit_id = v.visit_id
                     AND right(o.key, 12) = '_follow_date'),
                 (cr.soap_plan #>> '{tai_kham,ngay}')
               ) AS ngay_text
          FROM public.visit v
          LEFT JOIN public.clinical_record cr
            ON cr.visit_id = v.visit_id AND cr.clinic_id = v.clinic_id
         WHERE v.clinic_id = p_clinic_id
           AND v.status IN ('FINALIZED', 'AMENDED')
           AND v.created_at >= (v_ngay - 183)::timestamptz
           -- Lượt chuyển từ hồ sơ cũ (06/10/2026) không có ngày tái khám: nếu nó là
           -- lượt mới nhất, DISTINCT ON sẽ che mất lượt thật có hẹn tái khám.
           AND NOT EXISTS (SELECT 1 FROM lich_su_notion.luot_that t
                            WHERE t.visit_id = v.visit_id)
         ORDER BY v.clinic_patient_id, v.created_at DESC
    ),
    can_goi AS (
        SELECT b.clinic_patient_id,
               b.visit_id,
               b.ngay_text::date AS ngay_hen
          FROM benh_an b
         WHERE b.ngay_text ~ '^\d{4}-\d{2}-\d{2}$'
           AND b.ngay_text::date BETWEEN v_ngay AND v_ngay + 7
           -- Đã đặt lịch rồi thì không cần mời đặt nữa — lượt 2 sẽ lo họ.
           AND NOT EXISTS (
               SELECT 1 FROM public.appointment a
                WHERE a.clinic_id = p_clinic_id
                  AND a.clinic_patient_id = b.clinic_patient_id
                  AND a.slot_start >= v_ngay::timestamptz
                  AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED',
                                   'CONFIRMED', 'CHECKED_IN')
           )
    ),
    them1 AS (
        INSERT INTO public.nhac_tai_kham
            (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi,
             nguon_visit_id)
        SELECT p_clinic_id, c.clinic_patient_id, 1, c.ngay_hen,
               c.ngay_hen - 7, c.visit_id
          FROM can_goi c
        ON CONFLICT (clinic_id, clinic_patient_id, ngay_hen, luot_goi)
        DO NOTHING
        RETURNING 1
    )
    SELECT count(*)::integer INTO v_l1 FROM them1;

    -- ── LƯỢT 2 — đã có lịch hẹn HÔM NAY ────────────────────────────────────
    --
    -- Đây là nhóm không màn nào đang hiện: danh sách nhắc tái khám loại bỏ
    -- người đã đặt lịch, còn màn nhiệm vụ CSKH bắt đầu từ ngày mai.
    WITH lich_hom_nay AS (
        SELECT a.id, a.clinic_patient_id,
               (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_hen
          FROM public.appointment a
         WHERE a.clinic_id = p_clinic_id
           AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = v_ngay
           AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
    ),
    them2 AS (
        INSERT INTO public.nhac_tai_kham
            (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi,
             appointment_id)
        SELECT p_clinic_id, l.clinic_patient_id, 2, l.ngay_hen, l.ngay_hen, l.id
          FROM lich_hom_nay l
        ON CONFLICT (clinic_id, clinic_patient_id, ngay_hen, luot_goi)
        DO NOTHING
        RETURNING 1
    )
    SELECT count(*)::integer INTO v_l2 FROM them2;

    RETURN QUERY SELECT v_l1, v_l2;
END;
$function$;
