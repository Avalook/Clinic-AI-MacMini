-- CHI PHÍ LLM + TÓM TẮT NGÀY CỦA AGENT (09/10/2026).
--
-- `llm_lan_goi`: MỌI lần ClinicAI gọi Anthropic API là một dòng — model, token
-- (vào / ra / đọc cache / ghi cache), tiền USD tính theo bảng giá trong code lúc
-- gọi (`clinicai/llm/chi_phi.py`). Đây là "đồng hồ điện" của mình: không cần
-- vào Console vẫn biết đã đốt bao nhiêu, theo model, theo tính năng, theo ngày;
-- và là chỗ trần chi phí theo ngày đọc để TỰ DỪNG gọi khi vượt.
-- Không lưu nội dung gửi/nhận — chỉ số.
--
-- `agent_tom_tat`: bản tóm tắt cuối ngày LLM viết từ nhận định của agent (đã
-- không tên khách). Giữ mọi lần tạo (tự động hoặc bấm tay) để so được; màn đọc
-- bản mới nhất của ngày.

CREATE TABLE IF NOT EXISTS public.llm_lan_goi (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    luc               timestamptz NOT NULL DEFAULT now(),
    clinic_id         uuid REFERENCES public.clinic(id) ON DELETE SET NULL,
    tinh_nang         text NOT NULL CHECK (tinh_nang ~ '^[a-z_]+$'),
    model             text NOT NULL,
    input_tokens      integer NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens     integer NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cache_doc_tokens  integer NOT NULL DEFAULT 0 CHECK (cache_doc_tokens >= 0),
    cache_ghi_tokens  integer NOT NULL DEFAULT 0 CHECK (cache_ghi_tokens >= 0),
    -- NULL = model chưa có trong bảng giá: vẫn ghi token, màn nói "chưa có giá".
    chi_phi_usd       numeric(12, 6) CHECK (chi_phi_usd IS NULL OR chi_phi_usd >= 0),
    thanh_cong        boolean NOT NULL DEFAULT true,
    loi               text,
    ma_yeu_cau        text,
    thoi_gian_ms      integer
);
CREATE INDEX IF NOT EXISTS llm_lan_goi_luc ON public.llm_lan_goi (luc DESC);

COMMENT ON TABLE public.llm_lan_goi IS
'Mỗi lần gọi Anthropic API: model, token, USD. Không nội dung. Xem 20261009870000.';

CREATE TABLE IF NOT EXISTS public.agent_tom_tat (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   uuid NOT NULL REFERENCES public.clinic(id) ON DELETE CASCADE,
    ngay        date NOT NULL,
    noi_dung    text NOT NULL,
    model       text NOT NULL,
    lan_goi_id  uuid REFERENCES public.llm_lan_goi(id) ON DELETE SET NULL,
    -- NULL = vòng su-kien tự tạo cuối ngày; có giá trị = người bấm "Tóm tắt ngay".
    tao_boi     uuid REFERENCES public.staff(id),
    tao_luc     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_tom_tat_ngay
    ON public.agent_tom_tat (clinic_id, ngay, tao_luc DESC);

COMMENT ON TABLE public.agent_tom_tat IS
'Tóm tắt ngày của agent giám sát (LLM đọc nhận định đã không tên khách).';

ALTER TABLE public.llm_lan_goi ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_tom_tat ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT ON public.llm_lan_goi TO service_role;
GRANT SELECT, INSERT ON public.agent_tom_tat TO service_role;
