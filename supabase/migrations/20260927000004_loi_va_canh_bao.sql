-- KHO LỖI + CẢNH BÁO TỰ DỰNG TRONG POSTGRES (27/09/2026 — theo dõi lỗi Pha 1).
--
-- Tuyền chốt: không Sentry (dữ liệu y tế, NĐ 13/2023) → lỗi gom ở chính
-- Postgres của mình. Trước đây lỗi 500 chỉ nằm trong log container (mất khi
-- deploy) và bộ đếm trong RAM (`core/telemetry.py`, mất khi restart), nên câu
-- "hôm qua lỗi gì, bao nhiêu lần, còn không" không ai trả lời được.
--
-- `loi_nhom`: MỘT dòng cho mỗi kiểu lỗi (dấu vân = nguồn + vị trí + kiểu lỗi +
-- khung code), đếm số lần, lần đầu/cuối, mã yêu cầu gần nhất để tra log.
-- KHÔNG giữ thân yêu cầu, tham số, dữ liệu khách — thông điệp đã qua bộ che.
--
-- `canh_bao`: bộ canh gác (vòng su-kien, mỗi phút) mở một cảnh báo khi có
-- chuyện (tin sự kiện kẹt, lỗi mới dồn dập, hàng chờ ma…) và TỰ ĐÓNG khi hết.
-- Mỗi mã chỉ có MỘT cảnh báo đang mở (unique một phần) — chạy lại vô hại.

CREATE TABLE IF NOT EXISTS public.loi_nhom (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nguon         text NOT NULL CHECK (nguon IN ('api', 'worker', 'web')),
    dau_van       text NOT NULL,
    vi_tri        text NOT NULL,
    kieu          text NOT NULL,
    thong_diep    text NOT NULL DEFAULT '',
    so_lan        integer NOT NULL DEFAULT 1 CHECK (so_lan >= 1),
    lan_dau       timestamptz NOT NULL DEFAULT now(),
    lan_cuoi      timestamptz NOT NULL DEFAULT now(),
    ma_yeu_cau    text,
    trang_thai    text NOT NULL DEFAULT 'MOI'
                  CHECK (trang_thai IN ('MOI', 'DA_BIET', 'DA_SUA', 'BO_QUA')),
    doi_luc       timestamptz,
    doi_boi       uuid REFERENCES public.staff(id),
    UNIQUE (nguon, dau_van)
);
CREATE INDEX IF NOT EXISTS loi_nhom_lan_cuoi_idx ON public.loi_nhom (lan_cuoi DESC);

COMMENT ON TABLE public.loi_nhom IS
'Lỗi hệ thống gom theo kiểu (api / worker / web). Không dữ liệu khách. Xem 20260927000004.';

CREATE TABLE IF NOT EXISTS public.canh_bao (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ma          text NOT NULL,
    muc         text NOT NULL CHECK (muc IN ('warning', 'critical')),
    noi_dung    text NOT NULL,
    so_lan      integer NOT NULL DEFAULT 1,
    mo_luc      timestamptz NOT NULL DEFAULT now(),
    lan_cuoi    timestamptz NOT NULL DEFAULT now(),
    dong_luc    timestamptz,
    bao_luc     timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS canh_bao_mot_ma_dang_mo
    ON public.canh_bao (ma) WHERE dong_luc IS NULL;
CREATE INDEX IF NOT EXISTS canh_bao_mo_luc_idx ON public.canh_bao (mo_luc DESC);

COMMENT ON TABLE public.canh_bao IS
'Cảnh báo của bộ canh gác (services/canh_gac.py): mở khi có chuyện, tự đóng khi hết.';

-- Chỉ backend (vai postgres / service) đọc ghi; dashboard đọc qua FastAPI.
ALTER TABLE public.loi_nhom ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.canh_bao ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.loi_nhom TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.canh_bao TO service_role;
