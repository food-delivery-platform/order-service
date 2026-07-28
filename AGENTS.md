# AGENTS.md — общая память проекта для AI-агентов

> **Проект:** `order-service` — Food Delivery Platform, сервис заказов.
> **Ветка по умолчанию:** `FDS-24-order-creation-and-persistence` (актуальная на 2026-07-05).
> **Язык:** Python 3.12+, AWS Lambda (без фреймворков), Supabase/Postgres (SQLAlchemy Core).

Order Service управляет жизненным циклом заказа: создание, валидация корзины,
оркестрация оплаты/доставки, отмена, чтение заказов клиента. Это набор Python
Lambda-хендлеров, запускаемых через Step Functions и API Gateway. Хранилище —
Supabase/Postgres через SQLAlchemy Core (FDS-33), события — SNS/SQS, оркестрация — Step Functions.

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
| `db/` | engine.py (SQLAlchemy Core) | ✅ (FDS-27, FDS-33) |
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

## 2026-07-23 — DeepSeek (deepseek-v4-pro) — FDS-33 drop supabase-py, use SQLAlchemy for orders

- **Цель:** механическая замена supabase-py на SQLAlchemy Core в order_repository
  и address_repository, удаление библиотеки supabase из проекта.
- **Изменено:**
  - `src/shared/db/engine.py` — добавлены `order_status` ENUM, таблицы
    `orders_table` / `order_items_table` / `order_status_history_table` /
    `addresses_table`. Engine и payments_table без изменений.
  - `src/modules/orders/repository/order_repository.py` — переписан на
    SQLAlchemy Core: чтение через 3 SELECT (orders + items + history),
    запись через ON CONFLICT upsert + delete/insert items + guarded
    history insert. Функции `get_orders_by_customer`, `get_order_by_id`,
    `insert_order` сохранили сигнатуры.
  - `src/modules/orders/repository/address_repository.py` — переписан на
    SQLAlchemy Core: `create_address` / `get_address` через `addresses_table`.
  - `src/shared/db/supabase_client.py` — удалён.
  - `requirements-lambda.txt`, `requirements.txt` — удалена строка `supabase>=2.4`.
  - `src/shared/config/env.py` — удалены `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
    функция `_hydrate` и импорт `get_service_secret`.
  - `tests/test_env.py` — переписан под оставшийся `get()` и константы.
  - `tests/test_secrets.py` — ключи в фикстурах заменены на `DATABASE_URL`/`DB_HOST`.
  - `docs/deployment.md` — `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` → `DATABASE_URL`.
  - `.github/workflows/deploy-step-functions.yml` — убран "supabase" из описания слоя.
- **Открыто:** —
- **Дальше:** —

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

## 2026-07-19 — DeepSeek (deepseek-v4-pro) — FDS-25 hotfix: Lambda deploy waiter

- **Цель:** исправить ResourceConflictException при деплое — `update-function-configuration`
  запускался до завершения `update-function-code`/`create-function`.
- **Изменено:**
  - `.github/workflows/deploy-step-functions.yml` — добавлены `aws lambda wait
    function-updated-v2` (после update-function-code) и `aws lambda wait
    function-active-v2` (после create-function) в цикл Deploy Lambdas.
- **Дальше:** —

---

## 2026-07-19 — GLM (glm-5.2) — FDS-27 P2-C12 wire publish_order_event into SM#2

- **Цель:** встроить шаг `PublishOrderEvent` во вторую state machine (SM#2)
  между `MarkPaymentResult` и `PaymentResultChoice`, чтобы доменное событие
  `order.paid` / `order.payment_failed` эмитилось в EventBridge после фиксации
  результата платежа.
- **Изменено:**
  - `orchestration/payment-confirmation-state-machine.asl.json`:
    - Все Task `Resource` нормализованы к bare-форме `function:<name>`
      (`verify_payment`, `mark_payment_result`, `publish_order_event`) — убран
      `arn:aws:lambda:...:` префикс для консистентности с part-1 ASL.
    - `MarkPaymentResult.Next` изменён с `PaymentResultChoice` на `PublishOrderEvent`.
    - Добавлен новый Task-стейт `PublishOrderEvent`: Parameters из `$.result.*`,
      `ResultPath: $.published`, `Next: PaymentResultChoice`, `Catch → PublishFailed`.
      Choice по-прежнему читает `$.result.status` (не `$.published`) — коллизии
      ResultPath нет.
    - Добавлен терминальный Fail-стейт `PublishFailed` (`Error: PublishFailed`,
      `Cause: publish_order_event raised`).
    - Обновлён top-level `Comment` (упомянут publish step).
  - `tests/test_payment_confirmation_asl.py`: `function:publish_order_event` добавлен
    в `EXPECTED_FUNCTION_RESOURCES`; assertion кол-ва Task-стейтов поднято с 2 до 3;
    обновлён module docstring (P2-C10 / P2-C12).
- **Открыто:** deploy-workflow (`scripts/package_lambdas.py` DEPLOYABLE +
  `.github/workflows/deploy-step-functions.yml`) для C6/C8/C9/C11 всё ещё не обновлён —
  отдельная задача интеграции (лямбды не пакуются/не деплоятся).
- **Дальше:** добавить publish_order_event (и C6/C8/C9) в DEPLOYABLE + deploy workflow;
  задокументировать `EVENT_BUS_NAME` + IAM `events:PutEvents` в `docs/deployment.md`.

---

## 2026-07-19 — GLM (glm-5.2) — FDS-27 P2-C11 publish_order_event lambda

- **Цель:** добавить Lambda, которая после фиксации результата платежа (C9)
  публикует доменное событие (`order.paid` / `order.payment_failed`) в EventBridge,
  чтобы downstream-сервисы (Delivery, Notifications, Analytics) могли отреагировать.
- **Изменено:**
  - `src/shared/events/event_publisher.py` (новый) — тонкая обёртка над
    `boto3.client("events").put_events`: клиент создаётся внутри `EventPublisher.__init__`
    (lazy import boto3), фабрика `get_event_publisher()` — test-friendly (пэчится в тестах).
    `get_bus_name()` читает `EVENT_BUS_NAME` из секрета first, env second, default `"default"`
    (паттерн как в `paypal_client._get_config`). `put_event` бросает `EventPublishError`
    при ошибке boto3 или при `ErrorCode` в ответе.
  - `src/shared/events/__init__.py` (новый) — пустой маркер пакета.
  - `src/lambdas/publish_order_event/schema.py` (новый) — Pydantic v2 `PublishInput`
    (order_id, paypal_order_id, status — все `min_length=1`).
  - `src/lambdas/publish_order_event/handler.py` (новый) — Lambda-хендлер: валидация
    входа через Pydantic → `AppError(400, "INVALID_INPUT")`; маппинг
    `status in {"PAID","ALREADY_PAID"}` → `order.paid`, иначе `order.payment_failed`;
    публикация через `event_publisher`; ошибка публикации → `AppError(500, "EVENT_PUBLISH_FAILED")`.
  - `src/lambdas/publish_order_event/__init__.py` (новый) — пустой маркер.
  - `tests/test_publish_order_event.py` (новый) — 7 hermetic-тестов: PAID → order.paid
    (с проверкой call_args), FAILED → order.payment_failed, ALREADY_PAID → order.paid,
    ALREADY_FAILED → order.payment_failed, missing order_id → 400, empty status → 400,
    publish failure → 500. Все AWS-вызовы замоканы (`get_event_publisher` + `get_bus_name`).
- **Открыто:** `publish_order_event` ещё не добавлен в `DEPLOYABLE` (`scripts/package_lambdas.py`)
  и в deploy-workflow — отдельная задача интеграции (как для C6/C8/C9/C10).
- **Дальше:** добавить publish_order_event (и C6/C8/C9/C10) в `DEPLOYABLE` + deploy workflow;
  добавить шаг PublishOrderEvent в payment-confirmation state machine после MarkPaymentResult.

---

## 2026-07-19 — GLM (glm-5.2) — FDS-27 P2-C13 wire part 2 into deploy pipeline

- **Цель:** добавить part-2 лямбды и payment-confirmation state machine в пайплайн деплоя.
- **Изменено:**
  - `scripts/package_lambdas.py` — DEPLOYABLE расширен до 8 лямбд: добавлены
    `create_payment_session` (отсутствовал), `paypal_webhook`, `verify_payment`,
    `mark_payment_result`, `publish_order_event`.
  - `.github/workflows/deploy-step-functions.yml`:
    - Validate ASL: добавлена валидация `payment-confirmation-state-machine.asl.json`.
    - Deploy Lambdas: DEPLOYABLE-массив расширен до всех 8 лямбд.
    - Новый шаг "Render + deploy Payment Confirmation SM": резолвинг ARN-ов
      `verify_payment`/`mark_payment_result`/`publish_order_event`, jq-рендеринг
      через `walk`, create/update через `${{ secrets.AWS_PAYMENT_SM_NAME }}`.
    - Deployment Summary: добавлена строка для payment SM.
- **Открыто:** перед деплоем необходимо добавить GitHub secret `AWS_PAYMENT_SM_NAME`.
- **Дальше:** задокументировать `EVENT_BUS_NAME` + IAM `events:PutEvents` в `docs/deployment.md`.

---

## 2026-07-19 — DeepSeek (deepseek-v4-pro) — sync main + Lambda deploy wait fix

- **Цель:** синхронизировать `origin/main` в `FDS-27-part2` после мёрж-конфликтов.
- **Изменено:**
  - `.github/workflows/deploy-step-functions.yml` — `aws lambda wait` команды уже присутствуют (пришли из main hotfix, авто-мёрж).
  - `AGENTS.md` — union журнальных записей обеих веток.
  - `scripts/package_lambdas.py` — сохранена версия HEAD (8 лямбд).
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-19 — DeepSeek (deepseek-v4-pro) — FDS-27 paypal_webhook: start SM + deploy per-lambda env vars

- **Цель:** подключить paypal_webhook Lambda к payment-confirmation state machine,
  вернуть API Gateway proxy response, и расширить CI для per-lambda переменных окружения.
- **Изменено:**
  - `paypal_webhook/handler.py` — весь хендлер обёрнут в try/except AppError →
    `from_app_error`; после верификации подписи и валидации Pydantic читает
    `PAYMENT_CONFIRMATION_SM_ARN` из env (500 если отсутствует), запускает
    payment-confirmation SM через `boto3.client("stepfunctions").start_execution`,
    возвращает `{"statusCode": 200, "body": ...}`.
  - `tests/test_paypal_webhook.py` — 8 hermetic-тестов (было 7): мокается boto3
    stepfunctions + verify_webhook_signature; покрыты пути 200/401/500/400×4/multiValueHeaders.
  - `.github/workflows/deploy-step-functions.yml` — цикл Deploy Lambdas расширен:
    для `publish_order_event` добавляется `EVENT_BUS_NAME="food-delivery-orders"`,
    для `paypal_webhook` — `PAYMENT_CONFIRMATION_SM_ARN` из секрета; все функции
    сохраняют `SERVICE_SECRET_ARN` (merge через jq без перезаписи).
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 validate order_id as UUID in mark_payment_result

- **Цель:** добавить валидацию order_id как UUID в schema mark_payment_result.
- **Изменено:**
  - `src/lambdas/mark_payment_result/schema.py` — добавлен `field_validator("order_id")` с `uuid.UUID(v)`, order_id остаётся str.
  - `tests/test_mark_payment_result.py` — фикстуры переведены на валидный UUID, добавлены test_valid_uuid_order_id_passes и test_non_uuid_order_id_raises_400.
- **Открыто:** —
- **Дальше:** —

---

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — document API endpoints in readme

- **Цель:** задокументировать все HTTP-эндпоинты и Step Functions-шаги в readme.md.
- **Изменено:**
  - `readme.md` — добавлены секции «API Endpoints» (таблица Method | Path | Description) и «Step Functions steps» (order-creation + payment-confirmation).
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 stricter shared PayPal-ID format

- **Цель:** создать общий валидатор формата PayPal ID (не UUID).
- **Изменено:**
  - `src/shared/payments/validators.py` (новый) — `PaypalId` (Annotated, min_length=5, max_length=36, alphanumeric pattern).
  - `mark_payment_result/schema.py`, `verify_payment/schema.py` — `paypal_order_id` → `PaypalId`.
  - `paypal_webhook/schema.py` — `WebhookResource.id` → `PaypalId`.
  - Все тестовые фикстуры (`PP-42`, `PAYPAL-ORDER-42`) заменены на реалистичные PayPal ID (`5O190127TN364715T`).
  - `test_mark_payment_result.py` — добавлены тесты на too-short и non-alphanumeric PayPal ID.
- **Открыто:** —
- **Дальше:** commit 2 (extract validated_input decorator).

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 extract validated_input decorator

- **Цель:** убрать повторяющийся try/except ValidationError из SM-task handler-ов.
- **Изменено:**
  - `src/shared/validation.py` (новый) — декоратор `validated_input(model)`:
    валидирует event через Pydantic, передаёт обработанную модель в handler,
    при ошибке → AppError(400, "INVALID_INPUT").
  - `verify_payment/handler.py`, `mark_payment_result/handler.py`,
    `publish_order_event/handler.py`, `create_payment_session/handler.py` —
    применён `@validated_input(...)`, удалён inline try/except ValidationError.
    `mark_payment_result` также потерял неиспользуемый импорт `AppError`.
  - `paypal_webhook/handler.py` НЕ тронут (другой input shape и INVALID_WEBHOOK_PAYLOAD).
- **Открыто:** —
- **Дальше:** commit 3 (PAID vs ALREADY_PAID comment).

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 explain PAID vs ALREADY_PAID grouping

- **Цель:** задокументировать разницу между PAID и ALREADY_PAID для будущих разработчиков.
- **Изменено:**
  - `publish_order_event/handler.py` — добавлен комментарий над `_PAID_STATUSES`:
    PAID = paid by this execution, ALREADY_PAID = paid by earlier retry;
    оба должны эмитить order.paid.
- **Открыто:** —
- **Дальше:** —

---

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 native UUID order_id, serialize as str

- **Цель:** заменить кастомный field_validator order_id на нативный тип UUID, конвертировать в str на границах JSON.
- **Изменено:**
  - `mark_payment_result/schema.py` — order_id: UUID (был str + field_validator), убраны импорты uuid/field_validator.
  - `publish_order_event/schema.py` — order_id: UUID (был str + min_length=1).
  - `mark_payment_result/handler.py` — str(event.order_id) в return dict.
  - `publish_order_event/handler.py` — str(event.order_id) в EventBridge detail и return dict.
  - `test_mark_payment_result.py` — добавлен test_result_is_json_serializable (json.dumps + round-trip).
  - `test_publish_order_event.py` — фикстуры на валидный UUID, добавлены test_non_uuid_order_id_raises_400 и test_result_is_json_serializable.
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-29 deps as shared Lambda Layer

- **Цель:** перестать бандлить runtime-зависимости в каждый lambda zip; деплоить deps один раз как Lambda Layer, а function zips сделать src/-only.
- **Изменено:**
  - `scripts/package_lambdas.py` — полностью переписан: `build_layer()` создаёт `build/layer.zip` (deps под `python/`), `package_lambda()` пакует только `src/`. Добавлен флаг `--layer`.
  - `.github/workflows/deploy-step-functions.yml` — новый шаг «Publish Lambda Layer» между Package и Deploy Lambdas; `LAYER_ARN` передаётся в `update-function-configuration` через `--layers`.
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-21 — DeepSeek (deepseek-v4-pro) — FDS-27 OpenAPI docs

- **Цель:** добавить машиночитаемую OpenAPI 3.0 спецификацию Order Service API.
- **Изменено:**
  - `docs/openapi.yaml` (новый) — спека для всех HTTP-эндпоинтов.
  - `readme.md` — ссылка на `docs/openapi.yaml` над таблицей API Endpoints.
- **Открыто:** —
- **Дальше:** поддерживать спеку в актуальном состоянии.

---

## 2026-07-22 — DeepSeek (deepseek-v4-pro) — FDS-32 auto-capture PayPal orders

- **Цель:** закрыть gap между APPROVED и COMPLETED в flow PayPal-платежа:
  create_order использует intent=CAPTURE, но никто не делает capture;
  verify_payment требует COMPLETED — платёж никогда не мог settle.
- **Изменено:**
  - `src/shared/payments/paypal_client.py` — добавлен `capture_order()` (метод класса + module-level shim): идемпотентный захват approved PayPal order (200/201 → успех, 422 ORDER_ALREADY_CAPTURED → idempotent success, остальное → PayPalError).
  - `src/lambdas/verify_payment/handler.py` — шаг 3 переписан: fetch → capture if APPROVED → re-fetch → verify. PayPalError и непредвиденные ошибки логируются и пробрасываются как раньше.
  - `tests/shared/payments/test_paypal_capture.py` (новый) — 3 hermetic-теста: capture success, already-captured idempotency, error raises PayPalError.
  - `tests/lambdas/verify_payment/test_verify_capture.py` (новый) — 2 hermetic-теста: capture when APPROVED (side_effect для get_order), skip capture when COMPLETED (assert_not_called).
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-22 — DeepSeek (deepseek-v4-pro) — FDS-30 payment persist fix

- **Цель:** исправить персистенцию create_payment_session: (1) привязать status к Postgres enum типу payment_status, (2) собирать DB DSN из полей DB_HOST/DB_USER/DB_PASS/DB_NAME/DB_PORT когда database_url отсутствует.
- **Изменено:**
  - `src/shared/db/engine.py` — `_dsn()` переписан: сначала database_url (secret/ env), затем сборка из DB_* полей с quote_plus; Column status теперь использует payment_status ENUM (create_type=False); добавлен импорт ENUM и quote_plus.
  - `tests/shared/db/test_engine_dsn.py` (новый) — 9 hermetic-тестов _dsn(): database_url precedence, сборка из полей, mixed secret+env, quote_plus encoding, partial config → RuntimeError.
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-24 — DeepSeek (deepseek-v4-pro) — FDS-33 lint hotfix

- **Цель:** исправить ruff-ошибки на main после мёрджа FDS-33 (python-ci red).
- **Изменено:**
  - `src/shared/payments/payment_repository.py` — убран ненужный `pass` (PIE790).
  - `src/shared/config/secrets.py` — `except Exception:` → `except Exception as exc:`, `raise ... from exc` (B904).
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-24 — DeepSeek (deepseek-v4-pro) — FDS-33 lint hotfix v2

- **Цель:** пройти ruff check --fix + ruff format на всём проекте, убедиться что оба зелёные локально, чтобы CI на PR #19 прошёл.
- **Изменено:**
  - `ruff check src scripts --fix` — All checks passed!
  - `ruff format src scripts` — 105 files already formatted
  - `AGENTS.md` — запись в журнал + лента
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-24 — DeepSeek (deepseek-v4-pro) — FDS-33 lint hotfix v3

- **Цель:** исправить CI ruff I001 (unsorted imports) в 3 payment handler-ах.
- **Изменено:**
  - `ruff check src scripts --fix` — 3 I001 errors auto-fixed (sorted imports).
  - `ruff format src scripts` — 105 files already formatted.
  - `AGENTS.md` — запись в журнал + лента.
- **Открыто:** —
- **Дальше:** —

---

## 2026-07-26 — Claude (sonnet-5) — CORS fix for POST /orders (branch fix-cors-2)

- **Цель:** починить блокер из `todo_26_jul.md` — `OPTIONS /api/v1/orders` (preflight для `POST`)
  отвечал 204 без единого `access-control-*` заголовка, из-за чего браузер резал запрос на
  создание заказа ещё до отправки тела (`TypeError: Failed to fetch`).
- **Находка:** CORS в этом репо нигде не задан как код (ни в лямбдах, ни в IaC — его тут просто
  нет) и настраивался раньше вручную поверх живого HTTP API Gateway (`order-service-http-api`),
  судя по всему только с `AllowMethods=GET,OPTIONS` — отсюда рабочий CORS на `GET` и пустые
  заголовки на `POST`-preflight. Маршрут `POST /api/v1/orders` в `.github/workflows/deploy-step-functions.yml`
  также не был вообще прописан (лямбда `create_order` — стаб FDS-15, не входила в `DEPLOYABLE` и
  не была wired), поэтому без токена и получали `404 Not Found` от самого API Gateway.
- **Изменено (`.github/workflows/deploy-step-functions.yml`):**
  - `create_order` добавлен в `DEPLOYABLE` — деплоится наравне с остальными (пока отвечает
    `501 NOT_IMPLEMENTED`, это отдельная задача FDS-15).
  - Добавлен идемпотентный шаг `aws apigatewayv2 update-api --cors-configuration` — CORS теперь
    задаётся на уровне всего HTTP API (а не по каждому route/OPTIONS отдельно, HTTP API v2 сам
    обслуживает preflight), явно включает `GET,POST,PATCH,DELETE,OPTIONS` и
    `authorization,content-type`. Origin(ы) берутся из секрета `CORS_ALLOWED_ORIGINS`
    (запятая-разделённый список), фолбэк — `http://localhost:3000`. Запускается на каждом деплое,
    так что забытый метод в `AllowMethods` больше не тихий регресс.
  - `wire_route POST "/api/v1/orders" create_order` — маршрут наконец подключён к API Gateway.
- **Открыто:** `POST /orders` после этого фикса может упереться в ту же проблему авторизатора
  (503, см. `todo_24_jul.md`) — раньше не проверялось, preflight резал запрос до неё. Плюс
  `create_order` всё ещё стаб (FDS-15) — реальная бизнес-логика не входит в этот фикс.
- **Дальше:** после деплоя повторно прогнать сценарий из `todo_26_jul.md` («Как проверить») из
  браузера; если авторизатор всплывёт с 503 — разбирать отдельно (Cognito vs raw Google id_token,
  см. `todo_24_jul.md`); затем реализовать FDS-15 (реальный `create_order`).

---

## Лента

- 2026-07-27 [DeepSeek/deepseek-v4-pro] FDS-40-payment-e2e-runbook: first end-to-end sandbox payment completed on 26 July 2026; four failure modes documented in docs/payment-e2e-runbook.md
- 2026-07-26 [Claude/sonnet-5] CORS fix: apigatewayv2 update-api --cors-configuration (API-level, idempotent, GET/POST/PATCH/DELETE/OPTIONS) + wire POST /api/v1/orders -> create_order + add create_order to DEPLOYABLE (fix-cors-2)
- 2026-07-24 [DeepSeek/deepseek-v4-pro] lint hotfix v3: ran ruff check --fix (sorted imports, I001) in 3 payment handlers; ruff check + ruff format --diff both clean locally before push (FDS-33-hotfix-lint-v3)
- 2026-07-24 [DeepSeek/deepseek-v4-pro] lint hotfix v2: ran ruff --fix + ruff format, both green locally (FDS-33-hotfix-lint-v2)
- 2026-07-24 [DeepSeek/deepseek-v4-pro] lint hotfix, main green (FDS-33-hotfix-lint)
- FDS-31 — подняты read-эндпоинты через HTTP API Gateway: GET /api/v1/orders и GET /api/v1/orders/{orderId}.
- 2026-07-22 [DeepSeek/deepseek-v4-pro] FDS-32: verify_payment now captures approved PayPal orders (APPROVED -> COMPLETED) before verifying; added paypal_client.capture_order (idempotent on ORDER_ALREADY_CAPTURED).
- 2026-07-23 [DeepSeek/deepseek-v4-pro] FDS-31: deploy get_customer_orders & get_order_by_id lambdas; wire HTTP API Gateway (order-service-http-api) routes GET /api/v1/orders and GET /api/v1/orders/{orderId}; idempotent CLI step.
- 2026-07-22 [DeepSeek/deepseek-v4-pro] FDS-30: fix payment status to Postgres enum, assemble DB DSN from DB_* fields when database_url missing (FDS-30-payment-persist-fix)
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-29: deps moved from per-function zips to a shared Lambda Layer (FDS-29-lambda-layer)
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: add OpenAPI 3.0 spec for Order Service endpoints (docs/openapi.yaml)
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: native UUID order_id type, serialize as str at JSON boundaries
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: document all API endpoints and Step Functions steps in readme.md
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: explain PAID vs ALREADY_PAID grouping
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: extract input validation into a decorator (validated_input)
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: stricter shared PayPal-ID format validator (validators.py)
- 2026-07-19 [DeepSeek/deepseek-v4-pro] FDS-27: paypal_webhook starts payment-confirmation SM + per-lambda env vars in CI
- 2026-07-19 [GLM/glm-5.2] FDS-27 P2-C13: deploy part-2 lambdas and payment-confirmation state machine
- 2026-07-19 [GLM/glm-5.2] FDS-27 P2-C12: wire publish_order_event into payment confirmation state machine
- 2026-07-19 [GLM/glm-5.2] FDS-27 P2-C11: add publish_order_event lambda (EventBridge domain events)
- 2026-07-19 [DeepSeek/deepseek-v4-pro] FDS-25 hotfix: add Lambda waiters after update-function-code / create-function to fix ResourceConflictException
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
- 2026-07-21 [DeepSeek/deepseek-v4-pro] FDS-27: add OpenAPI 3.0 spec for Order Service endpoints (docs/openapi.yaml)

- 2026-07-28 [DeepSeek/deepseek-v4-pro] FDS-41: adds scripts/check_secrets.py and wires it into the python-checks CI job, so hardcoded AWS access keys, database URLs containing a password, JSON Web Tokens and inline credential assignments now fail the build. Lines may opt out with a "secret-scan: allow" marker; placeholders such as os.environ lookups and <redacted> examples are ignored by design.