-- Make idempotency atomic and scope keys by endpoint + verified actor.
-- Existing rows are completed cached responses in the server actor scope ('').

ALTER TABLE public.idempotency_key
    ADD COLUMN IF NOT EXISTS actor_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS state text NOT NULL DEFAULT 'COMPLETED',
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.idempotency_key
    ALTER COLUMN response DROP NOT NULL;

ALTER TABLE public.idempotency_key
    DROP CONSTRAINT IF EXISTS idempotency_key_pkey;

ALTER TABLE public.idempotency_key
    ADD CONSTRAINT idempotency_key_pkey PRIMARY KEY (key, endpoint, actor_id);

ALTER TABLE public.idempotency_key
    DROP CONSTRAINT IF EXISTS idempotency_key_state_check;

ALTER TABLE public.idempotency_key
    ADD CONSTRAINT idempotency_key_state_check
    CHECK (
        (state = 'PROCESSING' AND response IS NULL)
        OR (state = 'COMPLETED' AND response IS NOT NULL)
    );

COMMENT ON COLUMN public.idempotency_key.actor_id IS
  'Verified auth/staff scope. Empty string is the trusted server scope for endpoints without end-user JWT.';

COMMENT ON COLUMN public.idempotency_key.state IS
  'PROCESSING reserves a key before side effects; COMPLETED stores its replay response.';
