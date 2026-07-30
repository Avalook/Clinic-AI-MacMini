-- W7 — Outbox for pushing to an external point-of-sale (ADR-0010).
--
-- ClinicAI owns payment and inventory. KiotViet, if a clinic uses it, is a
-- system we push TO — never a system we read the truth from. This table is the
-- seam: a row is written in the same transaction as the payment it describes,
-- and a relay drains it afterwards. KiotViet being down therefore cannot fail a
-- cashier, and a crash between "money taken" and "POS told" cannot lose the
-- push.
--
-- WHY A SEPARATE TABLE, rather than reusing event_log: `event_published` is a
-- single boolean shared by every consumer. The notification relay already
-- claims events by flipping it, so a second relay reading the same flag would
-- steal notifications and have its own deliveries marked done by the notifier.
-- One flag cannot serve two consumers. (Generalising event_log to per-consumer
-- delivery tracking is worth doing when a third consumer appears.)

CREATE TABLE IF NOT EXISTS public.pos_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clinic_id uuid DEFAULT public.default_clinic_id() NOT NULL,
    kind text NOT NULL,
    -- What the row is about: a payment id, a stock movement id. Unique per
    -- clinic and kind, so enqueueing twice for the same subject is a no-op
    -- rather than a double invoice at the POS.
    subject_id uuid NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    status text DEFAULT 'PENDING' NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_error text,
    -- Whatever the POS calls this record on its side, kept for reconciliation.
    external_ref text,
    sent_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT pos_outbox_pkey PRIMARY KEY (id),
    CONSTRAINT pos_outbox_clinic_id_fkey FOREIGN KEY (clinic_id)
        REFERENCES public.clinic(id) ON DELETE RESTRICT,
    CONSTRAINT uq_pos_outbox_subject UNIQUE (clinic_id, kind, subject_id),
    CONSTRAINT pos_outbox_kind_check CHECK (kind IN ('invoice', 'invoice_void', 'stock_movement')),
    -- DEAD is the dead-letter state: attempts exhausted, waiting for a human.
    CONSTRAINT pos_outbox_status_check CHECK (status IN ('PENDING', 'SENT', 'DEAD')),
    CONSTRAINT pos_outbox_sent_when_sent CHECK ((status = 'SENT') = (sent_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_pos_outbox_clinic_id ON public.pos_outbox (clinic_id);
-- The relay's only query: what is due, oldest first.
CREATE INDEX IF NOT EXISTS idx_pos_outbox_due
    ON public.pos_outbox (next_attempt_at)
    WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_pos_outbox_dead
    ON public.pos_outbox (clinic_id, updated_at)
    WHERE status = 'DEAD';

COMMENT ON TABLE public.pos_outbox IS
  'Pending pushes to an external POS. Written with the transaction that caused '
  'them; drained by clinicai.services.pos_relay. ClinicAI remains the source of '
  'truth — nothing here ever writes back into the ledger.';

-- Operational data written and read only by the backend: RLS on, no policy,
-- and no grant to end users (same treatment as idempotency_key).
ALTER TABLE public.pos_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pos_outbox FROM anon, authenticated;
GRANT ALL ON public.pos_outbox TO service_role;
