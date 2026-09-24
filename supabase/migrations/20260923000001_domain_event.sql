-- Nền event-driven — bước 1: sổ sự kiện nghiệp vụ (23/09/2026).
--
-- VÌ SAO CÓ FILE NÀY. `event_log` đang gánh hai vai: sổ nhật ký thao tác (audit)
-- và hộp gửi tin đi (cột `event_published`). Hệ quả đã thấy: mọi dòng audit
-- thuần tuý (đổi cấu hình, đổi tài khoản) cũng nằm chờ "publish"; một cờ boolean
-- không mô tả nổi trạng thái của nhiều bên nhận (Telegram xong không có nghĩa là
-- CSKH xong); và 15 chỗ `INSERT INTO event_log` thô nằm ngoài `audit.py`, mỗi
-- chỗ một dạng metadata.
--
-- Tách làm hai sổ, mỗi sổ một việc:
--   * `event_log`  — GIỮ NGUYÊN, từ nay là nhật ký thao tác. Không ai "nghe".
--   * `domain_event` — sự thật nghiệp vụ, chỉ thêm không sửa, có người nghe.
--   * `event_delivery` — mỗi (sự kiện × bên nhận) một dòng, tạo CÙNG giao dịch.
--
-- Bước này KHÔNG đọc gì: chưa có consumer, chưa có worker. Ghi vào bảng mới
-- không thể làm hỏng đường đang phục vụ bệnh nhân (Event Interception —
-- Fowler, patterns of legacy displacement).
--
-- BA QUYẾT ĐỊNH ĐÃ CHỐT, ghi lại để sau này không phải tra chat:
--   1. State-first: bảng hiện trạng vẫn là sự thật "bây giờ". Không event
--      sourcing. Nhưng MỌI thay đổi nghiệp vụ phải phát sự kiện, nếu không thì
--      màn hành trình / CSKH / AI không dựng lại được.
--   2. Không dùng con trỏ theo số thứ tự cho bên nhận: `bigserial` được cấp
--      TRƯỚC khi commit, hai giao dịch song song commit lệch thứ tự, bên nhận đã
--      đọc qua số lớn sẽ bỏ sót số nhỏ VĨNH VIỄN mà không báo lỗi. Vì vậy dòng
--      giao được tạo sẵn ngay trong giao dịch ghi sự kiện.
--   3. `tx_id` vẫn được ghi (rẻ) để sau này nếu cần đọc theo con trỏ thì lọc
--      được `tx_id < pg_snapshot_xmin(pg_current_snapshot())`.
--
-- Chạy lại được: mọi lệnh dùng IF NOT EXISTS / DROP ... IF EXISTS.

-- ── domain_event ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.domain_event (
    event_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq             bigint GENERATED ALWAYS AS IDENTITY,

    event_type      text NOT NULL,
    event_version   integer NOT NULL DEFAULT 1,

    clinic_id       uuid NOT NULL,

    aggregate_type  text NOT NULL,
    aggregate_id    uuid NOT NULL,
    -- Số thứ tự liền mạch TRONG một aggregate. Bên nhận cần đúng thứ tự thì dựa
    -- vào cột này, không dựa vào seq: `FOR UPDATE SKIP LOCKED` chạy song song và
    -- lần thử lại đều làm đảo thứ tự.
    aggregate_version integer,

    occurred_at     timestamptz NOT NULL DEFAULT now(),
    recorded_at     timestamptz NOT NULL DEFAULT now(),

    correlation_id  uuid,
    causation_id    uuid,

    -- Ai gây ra. `actor_staff_id IS NULL = hệ thống` không đủ: cron, bot Zalo và
    -- AI điều phối phải phân biệt được (theo FHIR Provenance/AuditEvent).
    actor_type      text NOT NULL DEFAULT 'HUMAN',
    actor_staff_id  uuid,
    actor_role      text,
    on_behalf_of    uuid,
    agent_version   text,

    -- Module phát ra sự kiện, ví dụ 'service_order'.
    source_module   text NOT NULL,
    -- Chỉ event public mới được bên ngoài (AI, Zalo, đối tác) nghe, và mới phải
    -- giữ hợp đồng payload nghiêm.
    is_public       boolean NOT NULL DEFAULT true,

    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Đóng dấu khi sự kiện được phát lại / nhập lịch sử. Bên nhận thấy dấu này
    -- thì KHÔNG gửi thông báo ra ngoài (AWS EventBridge gọi là replay-name).
    replay_id       uuid,
    traceparent     text,
    tx_id           xid8 NOT NULL DEFAULT pg_current_xact_id(),

    CONSTRAINT domain_event_type_format
        CHECK (event_type ~ '^[a-z_]+\.[a-z_]+$'),
    CONSTRAINT domain_event_version_positive
        CHECK (event_version > 0),
    CONSTRAINT domain_event_aggregate_version_positive
        CHECK (aggregate_version IS NULL OR aggregate_version > 0),
    CONSTRAINT domain_event_actor_type
        CHECK (actor_type IN ('HUMAN', 'SYSTEM', 'AGENT')),
    -- Người làm thì phải biết là ai; máy và AI thì không cần staff_id.
    CONSTRAINT domain_event_human_has_actor
        CHECK (actor_type <> 'HUMAN' OR actor_staff_id IS NOT NULL),
    -- AI phải khai phiên bản, để sau này truy được bản nào ra quyết định gì.
    CONSTRAINT domain_event_agent_has_version
        CHECK (actor_type <> 'AGENT' OR agent_version IS NOT NULL),
    CONSTRAINT domain_event_source_module_not_empty
        CHECK (length(source_module) > 0)
);

-- Một aggregate không có hai sự kiện cùng số thứ tự.
CREATE UNIQUE INDEX IF NOT EXISTS uq_domain_event_aggregate_version
    ON public.domain_event (clinic_id, aggregate_type, aggregate_id, aggregate_version)
    WHERE aggregate_version IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_domain_event_aggregate
    ON public.domain_event (clinic_id, aggregate_type, aggregate_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_domain_event_correlation
    ON public.domain_event (clinic_id, correlation_id)
    WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_domain_event_type_time
    ON public.domain_event (clinic_id, event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_domain_event_seq
    ON public.domain_event (seq);

-- ── Chỉ thêm, không sửa, không xoá ──────────────────────────────────────────
-- Luật DE-02: chuyện đã xảy ra thì không sửa được. Sai thì phát sự kiện bù
-- (`*.corrected` / `*.cancelled`), không UPDATE dòng cũ. Ép ở Postgres vì đây là
-- loại bất biến không được phép phụ thuộc vào việc lập trình viên nhớ hay quên.
CREATE OR REPLACE FUNCTION public.domain_event_chi_them()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'domain_event chi duoc THEM: % bi tu choi. Sai thi phat su kien bu.',
        TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS trg_domain_event_chi_them ON public.domain_event;
CREATE TRIGGER trg_domain_event_chi_them
    BEFORE UPDATE OR DELETE ON public.domain_event
    FOR EACH ROW EXECUTE FUNCTION public.domain_event_chi_them();

ALTER TABLE public.domain_event ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS domain_event_select_own_clinic ON public.domain_event;
CREATE POLICY domain_event_select_own_clinic
    ON public.domain_event
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.domain_event TO authenticated;
-- KHÔNG cấp UPDATE/DELETE cho bất kỳ vai nào, kể cả service_role.
GRANT SELECT, INSERT ON public.domain_event TO service_role;

COMMENT ON TABLE public.domain_event IS
    'Sổ sự kiện nghiệp vụ, chỉ thêm. Khác event_log (nhật ký thao tác): sổ này có người nghe.';
COMMENT ON COLUMN public.domain_event.aggregate_version IS
    'Số thứ tự trong cùng aggregate — bên nhận dựa vào đây để xử lý đúng thứ tự.';
COMMENT ON COLUMN public.domain_event.replay_id IS
    'Có giá trị = sự kiện phát lại/nhập lịch sử; bên nhận không được gửi thông báo ra ngoài.';

-- ── event_delivery ──────────────────────────────────────────────────────────
-- Mỗi (sự kiện × bên nhận) một dòng, tạo CÙNG giao dịch với sự kiện. Telegram
-- hỏng không kéo CSKH chết theo — đúng bài học `pos_outbox` đã ghi trong repo:
-- một cờ không phục vụ được hai bên nhận.
CREATE TABLE IF NOT EXISTS public.event_delivery (
    event_id         uuid NOT NULL
        REFERENCES public.domain_event(event_id) ON DELETE CASCADE,
    consumer         text NOT NULL,

    clinic_id        uuid NOT NULL,
    -- Chép sang để bên nhận cần đúng thứ tự tìm được "dòng cũ nhất của aggregate
    -- này" mà không phải join.
    aggregate_id     uuid NOT NULL,
    aggregate_version integer,

    status           text NOT NULL DEFAULT 'PENDING',
    attempts         integer NOT NULL DEFAULT 0,
    next_attempt_at  timestamptz NOT NULL DEFAULT now(),
    -- Nhận việc có hạn: worker chết giữa chừng thì hết hạn, người khác nhận lại.
    lease_expires_at timestamptz,
    locked_by        text,
    last_error       text,
    processed_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (event_id, consumer),
    CONSTRAINT event_delivery_status
        CHECK (status IN ('PENDING', 'IN_PROGRESS', 'DONE', 'RETRY', 'DEAD')),
    CONSTRAINT event_delivery_attempts_not_negative
        CHECK (attempts >= 0),
    CONSTRAINT event_delivery_done_has_time
        CHECK ((status = 'DONE') = (processed_at IS NOT NULL)),
    CONSTRAINT event_delivery_consumer_not_empty
        CHECK (length(consumer) > 0)
);

-- Hàng đợi: chỉ quét dòng còn phải làm.
CREATE INDEX IF NOT EXISTS ix_event_delivery_cho_lam
    ON public.event_delivery (consumer, next_attempt_at)
    WHERE status IN ('PENDING', 'RETRY');
-- Dòng đang làm dở, để thu hồi khi hết hạn thuê.
CREATE INDEX IF NOT EXISTS ix_event_delivery_dang_lam
    ON public.event_delivery (lease_expires_at)
    WHERE status = 'IN_PROGRESS';
-- Hộp chết: phải có người nhìn, không được im lặng.
CREATE INDEX IF NOT EXISTS ix_event_delivery_chet
    ON public.event_delivery (clinic_id, created_at DESC)
    WHERE status = 'DEAD';
-- Thứ tự trong cùng aggregate.
CREATE INDEX IF NOT EXISTS ix_event_delivery_theo_aggregate
    ON public.event_delivery (consumer, aggregate_id, aggregate_version)
    WHERE status IN ('PENDING', 'RETRY');

ALTER TABLE public.event_delivery ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS event_delivery_select_own_clinic ON public.event_delivery;
CREATE POLICY event_delivery_select_own_clinic
    ON public.event_delivery
    FOR SELECT TO authenticated
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT ON public.event_delivery TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.event_delivery TO service_role;

COMMENT ON TABLE public.event_delivery IS
    'Mỗi (sự kiện × bên nhận) một dòng, tạo cùng giao dịch với sự kiện. Không dùng con trỏ theo số thứ tự: bigserial commit lệch thứ tự làm bên nhận bỏ sót im lặng.';

-- ── Số đo cho người trực ────────────────────────────────────────────────────
-- Bốn tín hiệu (theo Google SRE: chỉ giữ số đo có người nhìn).
CREATE OR REPLACE VIEW public.v_event_delivery_suc_khoe AS
SELECT
    consumer,
    count(*) FILTER (WHERE status IN ('PENDING', 'RETRY'))            AS cho_lam,
    count(*) FILTER (WHERE status = 'DEAD')                            AS chet,
    count(*) FILTER (WHERE status = 'IN_PROGRESS')                     AS dang_lam,
    max(now() - created_at) FILTER (WHERE status IN ('PENDING', 'RETRY'))
                                                                       AS tuoi_dong_cu_nhat
FROM public.event_delivery
GROUP BY consumer;

GRANT SELECT ON public.v_event_delivery_suc_khoe TO service_role;

COMMENT ON VIEW public.v_event_delivery_suc_khoe IS
    'Bốn số đo trực: chờ làm, chết, đang làm, tuổi dòng cũ nhất. Hai số đầu đáng bắn Telegram.';
