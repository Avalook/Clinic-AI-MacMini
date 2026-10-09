-- AGENT GIÁM SÁT — Layer 1, giai đoạn shadow (09/10/2026).
--
-- Anh Quang chốt: Phase 1 là theo dõi + giám sát, sau đó đề xuất, người thực
-- thi. Hợp đồng: `docs/ai/HOP-DONG-AGENT.md`. Agent là một LEGO CẮM THÊM chạy
-- trong vòng su-kien (cạnh bộ canh gác) — rút ra thì hệ chạy y nguyên.
--
-- `agent_nhan_dinh`: mỗi điều agent thấy là MỘT dòng, giữ bằng chứng và vòng
-- đời. Khác `canh_bao` (canh HẠ TẦNG: tin kẹt, lỗi dồn) — đây là VẬN HÀNH
-- (khách chờ, khách lặng im, việc quá hạn). Mỗi (phòng khám, loại, khoá) chỉ
-- MỘT dòng đang mở: chạy lại mỗi phút chỉ cộng dồn, không đẻ dòng.
-- Đóng TỰ ĐỘNG khi hiện trạng hết chuyện ('HET') — đó là "đóng vòng" ở mức
-- quan sát. Người quản lý chấm ĐÚNG / SAI: đó là số đo độ đúng để quyết lên
-- giai đoạn tiếp (hiện cho trưởng ca). Chấm là dữ liệu của người, agent không ghi.
--
-- Nội dung chỉ mã lượt / số tiếp đón / tên phòng — KHÔNG tên khách, SĐT, mã
-- khách: bảng này là đầu vào của bản tóm tắt bằng LLM về sau (NĐ 13/2023).
--
-- `agent_cau_hinh`: công tắc theo loại (hoặc '*' = mọi loại). Không có dòng =
-- 'shadow'. Tắt là một UPDATE, không deploy. Giai đoạn này chỉ có tat/shadow;
-- 'hien'/'de_xuat' thêm bằng migration khi số đo cho phép.

CREATE TABLE IF NOT EXISTS public.agent_nhan_dinh (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id        uuid NOT NULL REFERENCES public.clinic(id) ON DELETE CASCADE,
    location_id      uuid,
    loai             text NOT NULL CHECK (loai ~ '^[a-z_]+$'),
    -- Đối tượng của nhận định: id lượt / phòng / việc. Cùng loại + cùng khoá
    -- = cùng một chuyện.
    khoa             text NOT NULL CHECK (length(khoa) > 0),
    muc              text NOT NULL CHECK (muc IN ('warning', 'critical')),
    noi_dung         text NOT NULL,
    -- Hiến pháp §3.3: sự thật / suy luận. Rule đọc hiện trạng = 'quan_sat';
    -- đoán từ chỗ VẮNG sự kiện = 'suy_ra'.
    muc_bang_chung   text NOT NULL CHECK (muc_bang_chung IN ('quan_sat', 'suy_ra')),
    bang_chung       jsonb NOT NULL DEFAULT '{}'::jsonb,
    agent_version    text NOT NULL CHECK (length(agent_version) > 0),
    so_lan           integer NOT NULL DEFAULT 1 CHECK (so_lan >= 1),
    mo_luc           timestamptz NOT NULL DEFAULT now(),
    lan_cuoi         timestamptz NOT NULL DEFAULT now(),
    dong_luc         timestamptz,
    ly_do_dong       text CHECK (ly_do_dong IN ('HET', 'TAT')),
    danh_gia         text CHECK (danh_gia IN ('dung', 'sai', 'khong_ro')),
    danh_gia_ghi_chu text,
    danh_gia_boi     uuid REFERENCES public.staff(id),
    danh_gia_luc     timestamptz,
    CONSTRAINT agent_nhan_dinh_dong_co_ly_do
        CHECK ((dong_luc IS NULL) = (ly_do_dong IS NULL)),
    CONSTRAINT agent_nhan_dinh_danh_gia_co_nguoi
        CHECK ((danh_gia IS NULL) = (danh_gia_luc IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_nhan_dinh_mot_dang_mo
    ON public.agent_nhan_dinh (clinic_id, loai, khoa) WHERE dong_luc IS NULL;
CREATE INDEX IF NOT EXISTS agent_nhan_dinh_moi_nhat
    ON public.agent_nhan_dinh (clinic_id, lan_cuoi DESC);

COMMENT ON TABLE public.agent_nhan_dinh IS
'Nhận định của agent giám sát (Layer 1, shadow). Không tên/SĐT khách. Xem 20261009860000.';

CREATE TABLE IF NOT EXISTS public.agent_cau_hinh (
    clinic_id     uuid NOT NULL REFERENCES public.clinic(id) ON DELETE CASCADE,
    loai          text NOT NULL CHECK (loai = '*' OR loai ~ '^[a-z_]+$'),
    che_do        text NOT NULL CHECK (che_do IN ('tat', 'shadow')),
    cap_nhat_luc  timestamptz NOT NULL DEFAULT now(),
    cap_nhat_boi  uuid REFERENCES public.staff(id),
    PRIMARY KEY (clinic_id, loai)
);

COMMENT ON TABLE public.agent_cau_hinh IS
'Công tắc agent giám sát theo loại nhận định (''*'' = mọi loại). Không dòng = shadow.';

-- Chỉ backend đọc ghi; dashboard đọc qua FastAPI (/ops), như loi_nhom/canh_bao.
ALTER TABLE public.agent_nhan_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_cau_hinh ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.agent_nhan_dinh TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.agent_cau_hinh TO service_role;
