-- Idempotency key table — prevents double-submit for POST booking/payment.
-- A small table holding recently-used keys and their cached responses.
-- Keys auto-expire after 24h (a cleanup job or pg_cron can prune old rows).
--
-- Phase 2 of the System Design completion plan (Bài 14 — Transactions).

CREATE TABLE IF NOT EXISTS idempotency_key (
    key         TEXT        PRIMARY KEY,
    endpoint    TEXT        NOT NULL,
    response    JSONB       NOT NULL,
    status_code SMALLINT    NOT NULL DEFAULT 200,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE idempotency_key IS
  'Prevents double-submit: stores cached responses for recently-used idempotency keys.';

-- Index for cleanup queries (DELETE WHERE created_at < now() - interval '24h').
CREATE INDEX IF NOT EXISTS idx_idempotency_key_created
  ON idempotency_key (created_at);
