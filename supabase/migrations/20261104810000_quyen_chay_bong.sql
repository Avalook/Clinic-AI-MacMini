-- SỔ CHẠY BÓNG LUẬT "ĐỨNG ĐÂU LÀM VIỆC ĐÓ" (Tuyền 04/11/2026).
--
-- Mỗi lệnh ghi qua cổng quyền ghi một dòng "luật mới sẽ cho hay chặn, vì sao"
-- (`permissions/chay_bong.py`). Chỉ ghi, KHÔNG đổi kết quả quyền. Đo prod 04/11:
-- 67/69 người có đủ 14 việc tại chỗ cả ngày, nên trước khi bật luật mới phải
-- biết ai sẽ bị chặn ở việc nào.

-- ── Sổ chạy bóng ───────────────────────────────────────────────────────────
-- Chỉ khoá ngoại phòng khám (luật đa phòng khám); người / phòng không khoá —
-- sổ đo không được chặn xoá người / phòng.
-- Dọn > 45 ngày (worker su-kien, `permissions/chay_bong.py`).
CREATE TABLE IF NOT EXISTS public.quyen_chay_bong (
    id          bigserial PRIMARY KEY,
    clinic_id   uuid NOT NULL REFERENCES public.clinic (id) ON DELETE CASCADE,
    staff_id    uuid NOT NULL,
    luc         timestamptz NOT NULL DEFAULT now(),
    ngay        date NOT NULL DEFAULT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
    capability  text NOT NULL,
    work_pack   text,
    -- A ai cũng có · B gắn phòng · C theo người · ? chưa xếp nhóm.
    nhom        text NOT NULL CHECK (nhom IN ('A', 'B', 'C', '?')),
    -- Phòng lệnh đang làm (nếu lệnh biết) và các phòng người ấy đứng hôm nay.
    phong_id    uuid,
    phong_lich  uuid[] NOT NULL DEFAULT '{}',
    cho_cu      boolean NOT NULL,
    cho_moi     boolean NOT NULL,
    ly_do       text NOT NULL,
    -- 'lenh' = doi_quyen trong service; 'cua' = cửa router của lệnh ghi.
    cong        text NOT NULL DEFAULT 'lenh'
);

CREATE INDEX IF NOT EXISTS ix_quyen_chay_bong_ngay
    ON public.quyen_chay_bong (clinic_id, ngay);
CREATE INDEX IF NOT EXISTS ix_quyen_chay_bong_luc
    ON public.quyen_chay_bong (luc);

COMMENT ON TABLE public.quyen_chay_bong IS
'Chạy bóng luật "đứng đâu làm việc đó" (04/11/2026): mỗi lệnh ghi qua cổng quyền — luật mới sẽ cho/chặn, lý do. Chỉ đo, không đổi quyền. Giữ 45 ngày.';

ALTER TABLE public.quyen_chay_bong ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quyen_chay_bong_select_own_clinic ON public.quyen_chay_bong;
CREATE POLICY quyen_chay_bong_select_own_clinic ON public.quyen_chay_bong
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, DELETE ON public.quyen_chay_bong TO service_role;
GRANT USAGE ON SEQUENCE public.quyen_chay_bong_id_seq TO service_role;
