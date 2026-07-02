# AGENTS.md — общая память проекта для AI-агентов

> **Проект:** `order-service` — Food Delivery Platform, сервис заказов.
> **Ветка по умолчанию:** `FDS-21-order-validation-and-read-apis` (актуальная на 2026-07-02).
> **Язык:** Python 3.12+, AWS Lambda (без фреймворков), Supabase (Postgres).

Order Service управляет жизненным циклом заказа: создание, валидация корзины,
оркестрация оплаты/доставки, отмена, чтение заказов клиента. Это набор Python
Lambda-хендлеров, запускаемых через Step Functions и API Gateway. Хранилище —
Supabase (Postgres), события — SNS/SQS, оркестрация — Step Functions.

---

## Архитектура и статус

### Lambda-хендлеры (`src/lambdas/`)

| Хендлер | Статус | Описание |
|---|---|---|
| `create_order` | стаб (501) | Создание заказа, старт Step Functions |
| `cancel_order` | стаб (501) | Отмена заказа |
| `get_customer_orders` | ✅ реализован (FDS-21) | GET /orders — список заказов клиента |
| `get_order_by_id` | ✅ реализован (FDS-21) | GET /orders/{id} — один заказ |
| `get_order_status` | стаб (501) | Статус заказа |
| `validate_order` | ✅ реализован (FDS-21) | Валидация корзины через Menu Service (шаг Step Functions) |
| `process_inbound_event` | стаб (501) | Обработчик входящих событий (SQS) |

### Feature-модули (`src/modules/`)

| Модуль | Слой | Статус |
|---|---|---|
| `orders/model/` | Order, OrderItem, DeliveryAddress, OrderStatus, CancelReason, OrderStatusHistory | ✅ (FDS-16) |
| `orders/repository/` | `order_repository.py` — read-методы | ✅ (FDS-21) |
| `orders/service/` | `order_read_service.py` | ✅ (FDS-21) |
| `orders/api/` | `dtos.py`, `mappers.py` | ✅ (FDS-21) |
| `orders/validation/` | `cart_validation_service.py` | ✅ (FDS-21) |
| `orders/state_machine/` | пусто | ❌ не начато |
| `menu/client/` | `menu_service_client.py` — HTTP-клиент валидации корзины | ✅ (FDS-21) |
| `menu/model/` | `menu_validation.py` | ✅ (FDS-16) |
| `payments/client/` | пусто | ❌ не начато |
| `payments/model/` | `payment_session.py` | ✅ (FDS-16) |
| `events/model/` | `delivery_event.py`, `order_event.py`, `payment_event.py` | ✅ (FDS-16) |
| `events/consumer/` | пусто | ❌ не начато |
| `events/publisher/` | пусто | ❌ не начато |
| `orchestration/step_functions/` | `pre_payment_payload.py`, `post_payment_payload.py` | ✅ (FDS-16) |

### Shared-инфраструктура (`src/shared/`)

| Категория | Файлы | Статус |
|---|---|---|
| `aws/` | dynamodb, sns, sqs, step_functions clients | ✅ (стабы) |
| `config/` | env loader | ✅ |
| `db/` | supabase_client | ✅ (стаб) |
| `errors/` | AppError | ✅ |
| `http/` | api_response helpers | ✅ |
| `utils/` | ids (UUID-генератор) | ✅ |

### Что ещё не начато

- `orders/state_machine/` — логика переходов статусов заказа
- `payments/client/` — HTTP-клиент к Payment Service
- `events/consumer/` + `events/publisher/` — реальная обработка событий
- `create_order`, `cancel_order`, `get_order_status`, `process_inbound_event` — бизнес-логика
- Тесты (`tests/` отсутствует)
- CI/CD (есть только GitHub Actions для ruff)

---

## Конвенции проекта

- **Лямбды:** `src/lambdas/<name>/handler.py`, экспортируют `handler(event, context)`.
- **Фича-модули:** `src/modules/<name>/<layer>/<file>.py`, где layer = `api`, `model`, `repository`, `service`, `validation`, `state_machine`, `client`, `consumer`, `publisher`.
- **Shared-утилиты:** `src/shared/<category>/<thing>.py`.
- **Каждый `__init__.py`** пуст, но обязателен (держит пакет).
- **Локальный запуск:** `python scripts/invoke_local.py <handler_name> [event.json]`.
- **Линтер/форматтер:** `ruff format src scripts` + `ruff check --fix src scripts` + `ruff check src scripts`.
- **Ошибки:** `AppError(http_status, code, message)` из `src/shared/errors/app_error.py`.
- **Модели:** Python dataclasses в `src/modules/*/model/`.
- **Ветка по умолчанию:** `FDS-21-order-validation-and-read-apis` (на 2026-07-02).

---

## Правило ведения журнала

Каждый AI-агент в конце сессии дописывает строку в ленту ниже.
Формат — одна строка на действие:

```markdown
- YYYY-MM-DD [Agent/model] краткое описание (issue/ветка)
```

Для длинных сессий — развёрнутый блок перед лентой:

```markdown
## YYYY-MM-DD — Agent (model) — задача
- Цель: ...
- Изменено: ...
- Открыто: ...
- Дальше: ...
```

---

## Лента

- 2026-07-02 [DeepSeek/deepseek-v4-pro] создал AGENTS.md, обновил .gitignore (.ruff_cache), пофиксил order_repository, validate_order handler, mappers, menu_service_client, readme (FDS-21)
- 2026-07-02 [Codebuff/minimax-m3] создал бриф .local/handoff-to-deepseek-2026-07-02.md, добавил паттерны в .gitignore
