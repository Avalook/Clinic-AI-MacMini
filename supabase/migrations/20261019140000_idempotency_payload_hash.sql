-- Không cho một Idempotency-Key đã ghi thành công bị dùng lại với body khác.
BEGIN;

ALTER TABLE public.idempotency_key
    ADD COLUMN IF NOT EXISTS request_hash text;

DO $constraint$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.idempotency_key'::regclass
           AND conname = 'idempotency_key_request_hash_format'
    ) THEN
        ALTER TABLE public.idempotency_key
            ADD CONSTRAINT idempotency_key_request_hash_format
            CHECK (request_hash IS NULL OR request_hash ~ '^[0-9a-f]{64}$');
    END IF;
END;
$constraint$;

COMMENT ON COLUMN public.idempotency_key.request_hash IS
    'SHA-256 of canonical request JSON + query. NULL is a pre-migration reservation.';

COMMIT;
