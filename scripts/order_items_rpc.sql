-- ============================================================================
-- upsert_order_with_items(payload JSONB)
--
-- Atomic upsert of an order row + its line items into order_items.
-- Call via Supabase RPC: client.rpc('upsert_order_with_items', {'payload': {...}})
--
-- Usage (SQL):
--   SELECT upsert_order_with_items('{
--     "order_row": {...},
--     "items": [...]
--   }'::jsonb);
-- ============================================================================

CREATE OR REPLACE FUNCTION upsert_order_with_items(payload jsonb)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_order_row jsonb;
    v_items      jsonb;
BEGIN
    v_order_row := payload -> 'order_row';
    v_items      := payload -> 'items';

    -- ---------------------------------------------------------------------
    -- 1. Upsert the order row (idempotent — protects against Step Functions
    --    duplicate executions)
    -- ---------------------------------------------------------------------
    INSERT INTO orders (
        order_id,
        customer_id,
        restaurant_id,
        delivery_address,
        status,
        subtotal,
        currency,
        status_history,
        created_at,
        updated_at
    )
    VALUES (
        v_order_row ->> 'order_id',
        v_order_row ->> 'customer_id',
        v_order_row ->> 'restaurant_id',
        (v_order_row -> 'delivery_address')::jsonb,
        v_order_row ->> 'status',
        (v_order_row ->> 'subtotal')::numeric,
        v_order_row ->> 'currency',
        (v_order_row -> 'status_history')::jsonb,
        v_order_row ->> 'created_at',
        v_order_row ->> 'updated_at'
    )
    ON CONFLICT (order_id) DO UPDATE SET
        customer_id      = EXCLUDED.customer_id,
        restaurant_id    = EXCLUDED.restaurant_id,
        delivery_address = EXCLUDED.delivery_address,
        status           = EXCLUDED.status,
        subtotal         = EXCLUDED.subtotal,
        currency         = EXCLUDED.currency,
        status_history   = EXCLUDED.status_history,
        updated_at       = EXCLUDED.updated_at;

    -- ---------------------------------------------------------------------
    -- 2. Upsert line items (one row per menu_item_id per order)
    --    Delete-then-reinsert is safe inside this transaction.
    -- ---------------------------------------------------------------------
    DELETE FROM order_items WHERE order_id = v_order_row ->> 'order_id';

    INSERT INTO order_items (order_id, menu_item_id, name, unit_price, quantity, line_total)
    SELECT
        v_order_row ->> 'order_id',
        item ->> 'menu_item_id',
        item ->> 'name',
        (item ->> 'unit_price')::numeric,
        (item ->> 'quantity')::integer,
        (item ->> 'line_total')::numeric
    FROM jsonb_array_elements(v_items) AS item;

END;
$$;
