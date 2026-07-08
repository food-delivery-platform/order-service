-- ============================================================================
-- upsert_order_with_items(payload JSONB)
--
-- Atomic upsert of an order row + line items + initial status history entry
-- across three tables: orders, order_items, order_status_history.
--
-- Call via Supabase RPC:
--   client.rpc('upsert_order_with_items', {'payload': {...}})
--
-- Usage (SQL):
--   SELECT upsert_order_with_items('{
--     "order_row": {...},
--     "items": [...]
--   }'::jsonb);
--
-- Idempotent: ON CONFLICT (id) for orders, delete-then-insert for items,
-- and NOT EXISTS guard for status history prevent duplicates on retry.
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
    -- 1. UPSERT the order row (idempotent — ON CONFLICT on PK id)
    -- ---------------------------------------------------------------------
    INSERT INTO orders (
        id,
        customer_id,
        venue_id,
        delivery_address_id,
        status,
        subtotal,
        delivery_fee,
        total,
        currency,
        created_at,
        updated_at
    )
    VALUES (
        (v_order_row ->> 'id')::uuid,
        (v_order_row ->> 'customer_id')::uuid,
        (v_order_row ->> 'venue_id')::uuid,
        (v_order_row ->> 'delivery_address_id')::uuid,
        (v_order_row ->> 'status')::order_status,
        (v_order_row ->> 'subtotal')::numeric,
        (v_order_row ->> 'delivery_fee')::numeric,
        (v_order_row ->> 'total')::numeric,
        v_order_row ->> 'currency',
        (v_order_row ->> 'created_at')::timestamptz,
        (v_order_row ->> 'updated_at')::timestamptz
    )
    ON CONFLICT (id) DO UPDATE SET
        customer_id         = EXCLUDED.customer_id,
        venue_id            = EXCLUDED.venue_id,
        delivery_address_id = EXCLUDED.delivery_address_id,
        status              = EXCLUDED.status,
        subtotal            = EXCLUDED.subtotal,
        delivery_fee        = EXCLUDED.delivery_fee,
        total               = EXCLUDED.total,
        currency            = EXCLUDED.currency,
        updated_at          = EXCLUDED.updated_at;

    -- ---------------------------------------------------------------------
    -- 2. ITEMS: delete-then-insert (idempotent inside this transaction)
    -- ---------------------------------------------------------------------
    DELETE FROM order_items
    WHERE order_id = (v_order_row ->> 'id')::uuid;

    INSERT INTO order_items (
        order_id,
        menu_item_id,
        menu_item_name,
        unit_price,
        quantity,
        line_total
    )
    SELECT
        (v_order_row ->> 'id')::uuid,
        (item ->> 'menu_item_id')::uuid,
        item ->> 'menu_item_name',
        (item ->> 'unit_price')::numeric,
        (item ->> 'quantity')::int,
        (item ->> 'line_total')::numeric
    FROM jsonb_array_elements(v_items) AS item;

    -- ---------------------------------------------------------------------
    -- 3. STATUS HISTORY: insert the initial entry only if it doesn't exist
    --    (idempotent on retry — won't duplicate)
    --    CONFIRM: from_status=NULL for creation? actor_type=customer?
    -- ---------------------------------------------------------------------
    INSERT INTO order_status_history (
        order_id,
        from_status,
        to_status,
        actor_id,
        actor_type,
        note
    )
    SELECT
        (v_order_row ->> 'id')::uuid,
        NULL,
        (v_order_row ->> 'status')::order_status,
        (v_order_row ->> 'customer_id')::uuid,
        'customer',
        NULL
    WHERE NOT EXISTS (
        SELECT 1 FROM order_status_history
        WHERE order_id = (v_order_row ->> 'id')::uuid
    );

END;
$$;
