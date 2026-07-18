# AGENTS.md — общая память проекта для AI-агентов

> **Проект:** `order-service` — Food Delivery Platform, сервис заказов.
> **Ветка по умолчанию:** `FDS-24-order-creation-and-persistence` (актуальная на 2026-07-05).
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
| `create_order_step` | ✅ реализован (FDS-24) | Создание и персистенция заказа (шаг Step Functions после валидации) |
| `cancel_order` | стаб (501) | Отмена заказа |
| `get_customer_orders` | ✅ реализован (FDS-21) | GET /orders — список заказов клиента |
| `get_order_by_id` | ✅ реализован (FDS-21) | GET /orders/{id} — один заказ |
| `get_order_status` | стаб (501) | Статус заказа |
| `validate_order` | ✅ реализован (FDS-21) | Валидация корзины через Menu Service (шаг Step Functions) |
| `resolve_delivery_address` | ✅ реализован (FDS-25) | Резолвинг адреса доставки (create-or-verify, шаг Step Functions) |
| `process_inbound_event` | стаб (501) | Обработчик входящих событий (SQS) |

### Feature-модули (`src/modules/`)

| Модуль | Слой | Статус |
|---|---|---|
| `orders/model/` | Order, OrderItem, DeliveryAddress, OrderStatus, CancelReason, OrderStatusHistory | ✅ (FDS-16) |
| `orders/repository/` | `order_repository.py` — read/write-методы | ✅ (FDS-21, FDS-24) |
| `orders/service/` | `order_read_service.py`, `order_create_service.py` | ✅ (FDS-21, FDS-24) |
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
- `create_order` (API Gateway), `cancel_order`, `get_order_status`, `process_inbound_event` — бизнес-логика
- Payment intent / payment step оркестрации — отдельная будущая задача
- Тесты (`tests/` отсутствует)
- CI/CD (есть только GitHub Actions для ruff)
- ASL-определение state machine (пока задаётся в AWS-консоли / CloudFormation)

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
- **Ветка по умолчанию:** `FDS-24-order-creation-and-persistence` (на 2026-07-05).

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

## 2026-07-02 — DeepSeek (deepseek-v4-pro) — передача дел от Codebuff + 8 коммитов в FDS-21

- **Цель:** принять бриф от Codebuff/minimax-m3, создать общую память проекта
  (AGENTS.md), предложить pre-commit hook для авто-журнала, и выполнить
  7 запланированных коммитов по замечаниям к ветке FDS-21.
- **Изменено:**
  - Создан `AGENTS.md` (4 раздела: описание, архитектура/статус, конвенции, журнал).
  - `.gitignore` — добавлен `.ruff_cache/`.
  - `order_repository.py` — `_row_to_order` + `_row_to_address` бросают `AppError`
    на пустых items и отсутствующих полях адреса.
  - `validate_order/handler.py` — `try/except AppError` → `valid: False` вместо
    падения; возвращён `event["restaurant_id"]` (fail-fast).
  - `mappers.py` — переход на `dataclasses.asdict`, в ответ добавлен
    `delivery_address`; `status_history` и `cancel_reason` исключены из выдачи.
  - `menu_service_client.py` — 400/422 от Menu Service → `CART_VALIDATION_FAILED`
    (422), остальные HTTP-ошибки → `MENU_SERVICE_ERROR` (502).
  - `readme.md` — пример с `/health` заменён на `get_order_by_id`.
  - `ruff format` прогнан, smoke-import OK.
- **Открыто:** pre-commit hook не установлен (показан текст). В коде брифа
  обнаружены две проблемы: утечка `status_history`/`cancel_reason` через `asdict`
  и смягчение `event["restaurant_id"]` → `.get()`. Обе исправлены отдельным
  коммитом после код-ревью.
- **Дальше:** установить pre-commit hook. Реализовать `orders/state_machine/`,
  `payments/client/`, `events/`, бизнес-логику оставшихся лямбд. Добавить тесты.

---

## 2026-07-05 — DeepSeek (deepseek-v4-pro) — FDS-24 order creation and persistence

- **Цель:** реализовать создание и персистенцию заказа как шаг Step Functions
  после успешной валидации корзины.
- **Изменено:**
  - `OrderItem` — `line_total` стал полем (не property), модель без расчётов.
  - `Order` — добавлены поля `subtotal` (float, default 0.0) и `currency` (str, default "ILS"), убран property `total`.
  - `order_repository.py` — добавлен `insert_order()` для записи заказа и позиций
    (изначально JSONB, затем переведён на таблицу `order_items` через RPC).
  - `order_create_service.py` (новый) — сервис создания заказа: snapshot позиций (name/price от Menu Service), расчёт line_total и subtotal, статус PENDING_PAYMENT, первая запись в status_history.
  - `create_order_step/handler.py` (новый) — Lambda-хендлер: получает validated cart data, вызывает сервис, возвращает заказ для следующего шага.
  - `validate_order/handler.py` — validated_items теперь включают `quantity` (из исходного запроса), чтобы CreateOrderStep мог считать line_total.
  - `mappers.py` — адаптирован под новые поля (`subtotal`, `line_total`), убран ручной маппинг line_total (теперь идёт через asdict).
  - `events/create-order-step.json` (новый) — тестовое событие для локального запуска CreateOrderStep.
  - `orchestration/order-creation-state-machine.asl.json` (новый) — placeholder ASL-определения (CreateOrderStep после валидации).
- **Открыто:**
  - ASL-определение state machine отсутствует в репозитории (задаётся в AWS). Payment intent — отдельная будущая задача.
  - ~~Хранение позиций: items embedded как JSONB~~ → **Решено:** отдельная таблица
    `order_items`, атомарный upsert через RPC `upsert_order_with_items`.
    Чтение — PostgREST resource embedding (`*, order_items(*)`).
  - РИСК: delivery_address не пробрасывается из validate_order в CreateOrderStep,
    и deliveryAddressId нигде не резолвится в полный адрес → шаг упадёт в реальном
    потоке. **Решено (FDS-25):** добавлен шаг ResolveAddress (отдельная Lambda)
    между валидацией и CreateOrderStep.
- **Дальше:** реализовать payment step, state machine, создать тесты.

---

## 2026-07-08 — DeepSeek (deepseek-v4-pro) — FDS-25 resolve delivery address

- **Цель:** добавить шаг резолвинга адреса доставки между валидацией корзины
  и созданием заказа (по решению Дениса).
- **Изменено:**
  - `dtos.py` — `CreateOrderRequest` теперь несёт полный `delivery_address`
    (`DeliveryAddressDTO`) + опциональный `delivery_address_id`.
  - `resolve_delivery_address/handler.py` (новый) — Lambda-хендлер:
    create-or-verify логика (нет id → создать; есть id → проверить).
  - `order-creation-state-machine.asl.json` — добавлен шаг `ResolveAddress`
    между `CartValidChoice` и `CreateOrderStep` с `ResultPath: $.delivery_address`.
  - `events/resolve-delivery-address-with-id.json` (новый) — тест-ивент: случай с существующим адресом.
  - `events/resolve-delivery-address-no-id.json` (новый) — тест-ивент: случай с новым адресом.
- **Решено:** адреса хранятся локально в таблице `addresses` (Supabase).
  Стабы заменены на реальные вызовы `address_repository`.
- **Открыто:** —
- **Дальше:** заменить стабы реальными вызовами к User Service / таблице
  `addresses`; реализовать `process_payment`.

---

---

## 2026-07-08 — DeepSeek (deepseek-v4-pro) — FDS-24 приведение persistence к реальной схеме БД

- **Цель:** выровнять persistence по реальной схеме БД (подтверждённой Ярославом):
  колонки `orders` (id/venue_id/delivery_address_id/...), `order_items`
  (menu_item_name, ...), `order_status_history` (отдельная таблица).
- **Изменено:**
  - `scripts/order_items_rpc.sql` — RPC переписан под 3 таблицы: UPSERT orders
    (ON CONFLICT id), delete-then-insert order_items, INSERT order_status_history
    с NOT EXISTS guard (идемпотентно).
  - `order_repository.py` — payload и `_row_to_order` под реальные колонки:
    orders.id/venue_id/delivery_address_id, order_items.menu_item_name,
    order_status_history.to_status/created_at/note. Убран `_row_to_address`,
    вместо него — DeliveryAddress(address_id=...) с None-полями.
  - `DeliveryAddress` — street/city/postal_code стали опциональными (None by default).
  - `create_order_step/handler.py` — принимает `delivery_address_id` вместо
    полного address-объекта (адрес = FK, резолвится в FDS-25).
  - `order_create_service.py` — сигнатура `delivery_address_id: str`, внутри
    создаётся DeliveryAddress(address_id=...) без полей адреса.
  - `mappers.py` — убран `data.pop("currency", None)`, валюта сохраняется в ответе API.
  - `events/create-order-step.json` — обновлён под `delivery_address_id`.
- **Решено:** адрес хранится по delivery_address_id (реляционно); история статуса —
  в отдельной таблице order_status_history.
- **Открыто:**
  - **total** — это `subtotal + delivery_fee`? `total`/`delivery_fee` — NOT NULL? (→ Ярослав)
  - **order_status_history при создании** — `from_status` = NULL допустим?
    `actor_id`/`actor_type` — customer или system? Запись делает наш шаг или
    триггер БД? (→ Ярослав)
  - **Таблица адресов** — как называется (куда FK delivery_address_id) и должен ли
    адрес существовать ДО создания заказа? (→ Денис / Ярослав; будущий FDS-25)
- **Дальше:** дождаться ответов на CONFIRM; задеплоить RPC; протестировать
  локально; реализовать payment step.

---

---

## 2026-07-08 — DeepSeek (deepseek-v4-pro) — FDS-24 pydantic validation + tests folder

- **Цель:** заменить ручные проверки в create_order_step на pydantic; создать tests/.
- **Изменено:**
  - `requirements.txt` — добавлены pydantic>=2.6, pytest>=8.0.
  - `src/lambdas/create_order_step/schema.py` (новый) — pydantic-модель CreateOrderStepEvent с вложенными DeliveryAddressInput / ValidatedItemInput.
  - `create_order_step/handler.py` — ручные `if not` проверки заменены на `CreateOrderStepEvent(**event)`, ValidationError → AppError(400, "INVALID_EVENT").
  - `order_create_service.py` — параметр `delivery_address_id: str` → `delivery_address: DeliveryAddress`.
  - Создана папка `tests/` (unit + fixtures/events). Все 11 JSON-файлов из `events/` → `tests/fixtures/events/`.
  - `tests/unit/test_create_order_step_schema.py` (новый) — 3 теста на валидацию.
  - `scripts/invoke_local.py` — docstring обновлён на новый путь к events.
- **Открыто:** —
- **Дальше:** перевод на SQLAlchemy (убрать Supabase), process_payment.

---

## 2026-07-12 — DeepSeek (deepseek-v4-pro) — FDS-25 CI/CD deployment

FDS-25 snapshot (2026-07-12):
- **Secrets Manager runtime loader** (`src/shared/config/secrets.py`) — lazy-init,
  one-call-per-warm-Lambda caching with empty-dict local-dev fallback.
- **DB creds hydrated from Secrets Manager** with env fallback (`env.py`
  `_hydrate`). When `SERVICE_SECRET_ARN` is unset, behaviour is identical to
  plain env (local dev unchanged).
- **Lambda packaging script** (`scripts/package_lambdas.py`) — zips the `src/`
  tree per deployable Lambda. `DEPLOYABLE = ["validate_order",
  "resolve_delivery_address", "create_order_step"]`.
- **Deploy workflow** (`.github/workflows/deploy-step-functions.yml`):
  validate ASL → package → deploy/create lambdas → set `SERVICE_SECRET_ARN`
  (ARN only) → render ASL with real Lambda ARNs (jq `walk`) → create/update
  state machine → summary in `$GITHUB_STEP_SUMMARY`.
- **Deployment docs + least-privilege IAM** (`docs/deployment.md`): required
  GitHub secrets/variables, IAM policies for deployer and Lambda execution role.
- **Secret VALUE never** enters env vars, logs, CI output, or committed files —
  only the ARN is passed.
- **SERVICE_SECRET_ARN** is stored as a GitHub repository **Secret** (not Variable)
  for consistency with all other AWS values in the deploy workflow.
  `docs/deployment.md` reflects this.

---

## 2026-07-18 — DeepSeek (deepseek-v4-pro) — FDS-27 P2-C6 paypal_webhook lambda

- **Цель:** создать Lambda для приёма и верификации PayPal webhook-уведомлений.
- **Изменено:**
  - `src/lambdas/paypal_webhook/schema.py` (новый) — Pydantic v2 модели WebhookBody / WebhookResource.
  - `src/lambdas/paypal_webhook/handler.py` (новый) — Lambda-хендлер: извлечение PayPal-заголовков из API Gateway event, верификация подписи через существующий PayPalClient.verify_webhook_signature, парсинг и валидация тела, нормализация.
  - `tests/test_paypal_webhook.py` (новый) — 7 тестов: валидная подпись, невалидная подпись, malformed body (missing event_type, missing resource, not JSON), multiValueHeaders, missing body.
- **Открыто:** —
- **Дальше:** добавить paypal_webhook в package_lambdas.py DEPLOYABLE; создать второй state machine для обработки webhook-событий.

---

## 2026-07-18 — DeepSeek (deepseek-v4-pro) — FDS-27 P2-C8 verify_payment lambda

- **Цель:** создать Lambda для сверки PayPal-платежа с сохранённым заказом.
- **Изменено:**
  - `src/lambdas/verify_payment/schema.py` (новый) — Pydantic v2 модель VerifyPaymentInput (paypal_order_id, event_type).
  - `src/lambdas/verify_payment/handler.py` (новый) — Lambda-хендлер: поиск payment_session через payment_repository.get_by_provider_ref, запрос PayPal через paypal_client.get_order, сверка status=="COMPLETED" + amount/currency (Decimal).
  - `tests/test_verify_payment.py` (новый) — 4 теста: match → verified=True, amount mismatch, currency mismatch, unknown provider_ref → AppError(404).
- **Открыто:** —
- **Дальше:** добавить verify_payment как шаг во второй state machine; реализовать mark_paid после успешной верификации.

---

## 2026-07-18 — DeepSeek (deepseek-v4-pro) — FDS-27 P2-C9 mark_payment_result lambda

- **Цель:** создать Lambda для идемпотентного сохранения результата верификации (PAID/FAILED).
- **Изменено:**
  - `src/lambdas/mark_payment_result/schema.py` (новый) — Pydantic v2 модель MarkPaymentInput (verified, order_id, paypal_order_id).
  - `src/lambdas/mark_payment_result/handler.py` (новый) — Lambda-хендлер: по флагу verified вызывает атомарный payment_repository.mark_paid или mark_failed, возвращает статус PAID/ALREADY_PAID/FAILED/ALREADY_FAILED.
  - `tests/test_mark_payment_result.py` (новый) — 5 тестов: verified=True → PAID, already PAID → ALREADY_PAID, verified=False → FAILED, missing field → 400, empty paypal_order_id → 400.
- **Открыто:** —
- **Дальше:** добавить mark_payment_result как шаг во второй state machine.

---

## 2026-07-18 — DeepSeek (deepseek-v4-pro) — FDS-27 P2-C10 payment confirmation state machine

- **Цель:** создать ASL-определение второго state machine (SM#2), связывающее webhook → verify → mark → Choice (PAID/Failed).
- **Изменено:**
  - `orchestration/payment-confirmation-state-machine.asl.json` (новый) — ASL: VerifyPayment → MarkPaymentResult → PaymentResultChoice → PaymentSucceeded/PaymentFailed; Catch-блоки для VerificationFailed/MarkFailed.
  - `tests/test_payment_confirmation_asl.py` (новый) — 4 структурных теста: валидный JSON, StartAt в States, все Next/Default/Choice цели существуют, Task Resource содержит `function:` плейсхолдеры.
- **Открыто:** —
- **Дальше:** добавить verify_payment + mark_payment_result в DEPLOYABLE + deploy workflow; интегрировать SM#2 в CI/CD.

---

## Лента

- 2026-07-18 [DeepSeek/deepseek-v4-pro] FDS-27 P2-C10: add payment confirmation state machine (ASL)
- 2026-07-18 [DeepSeek/deepseek-v4-pro] FDS-27 P2-C9: add mark_payment_result lambda (idempotent mark_paid/mark_failed)
- 2026-07-18 [DeepSeek/deepseek-v4-pro] FDS-27 P2-C8: add verify_payment lambda (match amount/currency/status)
- 2026-07-15 [DeepSeek/deepseek-v4-pro] FDS-27: SM#1 creates PayPal session, returns approval URL
- 2026-07-15 [DeepSeek/deepseek-v4-pro] FDS-27: add create_payment_session lambda
- 2026-07-15 [DeepSeek/deepseek-v4-pro] FDS-27: add payments repository (correlation + idempotency)
- 2026-07-15 [DeepSeek/deepseek-v4-pro] FDS-27: add payment domain models + statuses
- 2026-07-15 [DeepSeek/deepseek-v4-pro] FDS-27: add PayPal REST client wrapper + unit tests
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27 R3: validate create_payment_session input with Pydantic
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27 R2: align payments to real DB schema + SQLAlchemy repository
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27: encapsulate PayPal auth token in PayPalClient (drop module globals)
- 2026-07-13 [DeepSeek/deepseek-v4-pro] FDS-25: stub ProcessPayment as Pass placeholder (process_payment not yet implemented)
- 2026-07-13 [DeepSeek/deepseek-v4-pro] FDS-25: drop unsupported $comment/$note root fields from ASL (SFN schema)
- 2026-07-13 [DeepSeek/deepseek-v4-pro] FDS-25: wait for Lambda active/updated before patching config (fix ResourceConflictException)
- 2026-07-13 [DeepSeek/deepseek-v4-pro] FDS-25: switch CI to OIDC (AWS_ROLE_ARN), add deploy branch for pre-merge test
- 2026-07-13 [DeepSeek/deepseek-v4-pro] FDS-25: fix SERVICE_SECRET_ARN reference — read from GitHub Secrets (not vars) for consistency with other AWS values
- 2026-07-12 [DeepSeek/deepseek-v4-pro] FDS-25: hydrate DB credentials from Secrets Manager with env fallback (env.py _hydrate + tests)
- 2026-07-12 [DeepSeek/deepseek-v4-pro] FDS-25: document deployment secrets and least-privilege IAM (docs/deployment.md)
- 2026-07-12 [DeepSeek/deepseek-v4-pro] FDS-25: add Step Functions + Lambda deploy workflow (deploy-step-functions.yml)
- 2026-07-12 [DeepSeek/deepseek-v4-pro] FDS-25: add lambda packaging step (scripts/package_lambdas.py)
- 2026-07-12 [DeepSeek/deepseek-v4-pro] FDS-25: add Secrets Manager runtime loader (secrets.py + tests)
- 2026-07-08 [DeepSeek/deepseek-v4-pro] FDS-24: валидация входа create_order_step через pydantic (CreateOrderStepEvent); создана папка tests/ (fixtures/events + unit), events перенесены
- 2026-07-08 [DeepSeek/deepseek-v4-pro] FDS-24: persistence выровнен по реальной схеме (orders.id/venue_id/delivery_address_id, order_items.menu_item_name, order_status_history); RPC пишет 3 таблицы атомарно
- 2026-07-08 [DeepSeek/deepseek-v4-pro] FDS-25: стабы адресов заменены на реальную таблицу `addresses` в Supabase — модель `CustomerAddress`, репозиторий `address_repository`
- 2026-07-08 [DeepSeek/deepseek-v4-pro] FDS-24: persistence переведён на таблицу order_items (решение Дениса); insert_order идемпотентен через RPC upsert_order_with_items; чтение через PostgREST resource embedding (A1-A2)
- 2026-07-05 [DeepSeek] хотфикс validate_order: убран декартов цикл в validated_items; insert_order сделан идемпотентным (FDS-24)
- 2026-07-05 [DeepSeek/deepseek-v4-pro] реализовал FDS-24: CreateOrderStep с персистенцией, snapshot-ами позиций и статусом PENDING_PAYMENT (FDS-24)
- 2026-07-02 [DeepSeek/deepseek-v4-pro] создал AGENTS.md, обновил .gitignore (.ruff_cache), пофиксил order_repository, validate_order handler, mappers, menu_service_client, readme (FDS-21)
- 2026-07-02 [Codebuff/minimax-m3] создал бриф .local/handoff-to-deepseek-2026-07-02.md, добавил паттерны в .gitignore
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27 R4: move tests into dedicated tests/ directory
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27: R1–R4 complete (PayPal client encapsulation, DB schema alignment, Pydantic input validation, tests moved to tests/); pushed for review.
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27 R5: map CreatePaymentSession input in ASL (subtotal->amount) so SM#1 runs end-to-end
- 2026-07-16 [DeepSeek/deepseek-v4-pro] FDS-27 R6: drop redundant amount before-validator (Pydantic v2 coerces Decimal natively)
- 2026-07-18 [DeepSeek/deepseek-v4-pro] FDS-27 P2-C6: add paypal_webhook lambda with signature verification
