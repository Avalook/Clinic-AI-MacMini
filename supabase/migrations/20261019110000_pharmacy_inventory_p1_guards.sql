-- Kho thuốc P1 (19/10/2026): số hữu hạn + nhận retry an toàn trong cùng giao dịch.
-- Bảng request nằm ngoài schema public nên PostgREST không đưa nó ra API.

ALTER TABLE public.inventory_txn
    ADD CONSTRAINT inventory_txn_quantity_finite
    CHECK (lower(quantity::text) NOT IN ('nan', 'infinity', '-infinity'));

ALTER TABLE public.drug_batch
    ADD CONSTRAINT drug_batch_quantity_finite
    CHECK (lower(quantity_on_hand::text) NOT IN ('nan', 'infinity', '-infinity'));

ALTER TABLE public.drug_batch
    ADD CONSTRAINT drug_batch_cost_price_finite
    CHECK (
        cost_price IS NULL
        OR lower(cost_price::text) NOT IN ('nan', 'infinity', '-infinity')
    );

CREATE SCHEMA IF NOT EXISTS app_private;

CREATE TABLE app_private.pharmacy_inventory_request (
    clinic_id uuid NOT NULL
        REFERENCES public.clinic (id) ON DELETE RESTRICT,
    staff_id uuid NOT NULL
        REFERENCES public.staff (id) ON DELETE RESTRICT,
    operation text NOT NULL
        CHECK (operation IN ('receive', 'adjust', 'discard')),
    idempotency_key uuid NOT NULL,
    payload_sha256 text NOT NULL
        CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    inventory_txn_id uuid NOT NULL,
    drug_batch_id uuid NOT NULL,
    response jsonb NOT NULL
        CHECK (jsonb_typeof(response) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pharmacy_inventory_request_pkey
        PRIMARY KEY (clinic_id, staff_id, operation, idempotency_key),
    CONSTRAINT pharmacy_inventory_request_txn_fkey
        FOREIGN KEY (inventory_txn_id, clinic_id, drug_batch_id)
        REFERENCES public.inventory_txn (id, clinic_id, drug_batch_id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE app_private.pharmacy_inventory_request IS
    'Kết quả chống ghi trùng cho nhập/điều chỉnh/huỷ kho thuốc. Ghi cùng transaction với inventory_txn.';

CREATE OR REPLACE FUNCTION app_private.pharmacy_inventory_request_immutable_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'không được sửa hoặc xoá khoá gửi lại kho thuốc'
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER pharmacy_inventory_request_immutable
    BEFORE UPDATE OR DELETE ON app_private.pharmacy_inventory_request
    FOR EACH ROW
    EXECUTE FUNCTION app_private.pharmacy_inventory_request_immutable_guard();
