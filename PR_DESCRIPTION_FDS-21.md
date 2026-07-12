# PR Description — FDS-21: order validation and read APIs

> **Скопируй это в описание Pull Request на GitHub.**
> **Ветка:** `FDS-21-order-validation-and-read-apis` → `main` (или куда идёт PR)

---

## Что делает этот PR

Реализует валидацию корзины и read-эндпоинты для Order Service:

### 1. Валидация корзины (шаг Step Functions)
- `validate_order` Lambda — вызывает Menu Service, возвращает `valid: True/False`.
  На `AppError` (недоступен Menu Service, ошибка валидации) возвращает
  `valid: False` + `error`/`message`, чтобы Step Functions останавливал флоу
  через **Choice-состояние**, а не по упавшей Lambda.
- `Menu Service client` — HTTP-клиент к `/api/v1/cart/validate`.
  400/422 от Menu Service → `CART_VALIDATION_FAILED` (422).
  Остальные HTTP-ошибки → `MENU_SERVICE_ERROR` (502).
  `URLError` → `MENU_SERVICE_UNAVAILABLE` (502).
- `CartValidationService` — обёртка над клиентом.

### 2. Read-эндпоинты
- `GET /orders` — список заказов клиента (`get_customer_orders`).
- `GET /orders/{id}` — один заказ (`get_order_by_id`).
- `OrderRepository` — read-методы к Supabase. Бросает `AppError(500, "INVALID_ORDER_DATA")`
  если заказ без items или адрес без обязательных полей (`address_id`, `street`, `city`, `postal_code`).
- `OrderReadService` — бизнес-логика над репозиторием.
- `Mapper` — через `dataclasses.asdict`, включает `delivery_address` в ответ.
  `status_history` и `cancel_reason` из ответа исключены.

### 3. Инфраструктура
- `readme.md` — пример `invoke_local.py health` заменён на `get_order_by_id`.
- `.gitignore` — добавлен `.ruff_cache/`.
- `AGENTS.md` — общая память проекта для AI-агентов (архитектура, статус, конвенции, журнал).

---

## Коммиты (обратный хронологический порядок)

```
79076cd fix: prevent asdict leaks and restore fail-fast restaurant_id (FDS-21)
1cbf5b5 docs: add AGENTS.md project memory file (FDS-21)
cf34d67 style: ruff format (FDS-21)
f7a4942 docs: remove /health example from readme (FDS-21)
a2031af refactor: build order response via asdict and include delivery_address (FDS-21)
7528122 fix: convert Menu Service 400/422 to CART_VALIDATION_FAILED (FDS-21)
80e3674 fix: handle AppError in validate_order handler (FDS-21)
5f1590c fix: reject empty items and address in order repository (FDS-21)
3cc4a3f chore: ignore .ruff_cache (FDS-21)
ec5aefd refactor: drop health lambda for serverless model (FDS-21)  ← начало PR
...
```

---

## На что обратить внимание ревьюеру

- **`validate_order` больше не роняет Lambda** — Choice-состояние в Step Functions
  должно проверять `valid == false`, а не ловить `States.TaskFailed`.
- **`mappers.py`** — `asdict` тянет все поля датакласса, поэтому явно вырезаны
  `status_history` и `cancel_reason` (внутренние детали, не для API).
- **`order_repository.py`** — `_row_to_order` и `_row_to_address` валидируют
  целостность данных из БД и бросают `AppError` на битых записях.
- **`menu_service_client.py`** — парсит тело 400/422 от Menu Service и
  пробрасывает детали валидации в `CART_VALIDATION_FAILED`.

---

## Не входит в этот PR (будет позже)

- `orders/state_machine/` — логика переходов статусов
- `payments/client/` — HTTP-клиент к Payment Service
- `events/consumer/` + `events/publisher/` — обработка событий
- Бизнес-логика `create_order`, `cancel_order`, `get_order_status`, `process_inbound_event`
- Тесты
