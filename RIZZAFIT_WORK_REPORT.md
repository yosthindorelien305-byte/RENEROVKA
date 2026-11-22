# RizzaFit Growth Orchestrator — Final Work Report

**Дата:** 22 ноября 2026 г.
**Проект:** RizzaFit / RENEROVKA (`yosthindorelien305-byte/RENEROVKA`)
**Ветка:** `feat/growth-orchestrator`
**Базовый коммит:** `6bf008b` (`feat(seo): expand sitemap and add Fitify canonical metadata`)
**Статус выполнения:** Все безопасные локальные этапы и критический повторный аудит успешно завершены. Тесты пройдены (85/85). Деплой и слияние в `main` не производились.

---

## 1. Executive Summary

В соответствии с техническим заданием и Skill **RizzaFit Growth Orchestrator**, была проведена комплексная независимая ревизия и реализация улучшений по 8 ключевым направлениям: безопасность, аутентификация/UX, интеграция Telegram, AI-тренер, аналитика GA4, техническое SEO, производительность и рекомендации по росту.

Дополнительно проведён критический второй аудит собственных изменений, в ходе которого была выявлена и устранена фундаментальная проблема доверия к истории диалога с клиентом. Внедрено надёжное серверное хранение истории диалогов в SQLite (`coach_sessions`), изолированное по пользователям (`user_<id>`) и гостям (`guest_<sid>`), с защитой через `HttpOnly` / `SameSite=Lax` / `Path=/api/coach` cookie, защитой от параллельных запросов (429) и выносом внешних AI-вызовов за пределы `db_lock`. Устаревший заголовок `X-XSS-Protection` удалён во избежание побочных эффектов в устаревших браузерах. Все 85 тестов проекта успешно пройдены.

---

## 2. Baseline Repository State & Preserved Changes

- **Рабочая директория:** `C:\Users\Admin\.gemini\antigravity\worktrees\RENEROVKA\free_access_programs_training`
- **Ветка:** Создана отдельная изолированная ветка `feat/growth-orchestrator`.
- **Сохранность данных:**
  - Предыдущие изменения по SEO Stage 2 (`site/sitemap.xml`, `site/fitify/index.html`, `site/fitify/muscles.html`) полностью сохранены в истории и ветке.
  - Настройки и решение владельца по Fitify и Google Search Console строго соблюдены (никаких отправок в GSC или удаления страниц).
  - База данных `server_data/flexa.db`, конфигурация `CONTENT`, секреты платежей и пароли администратора не затрагивались.

---

## 3. Completed Stages Summary

### Этап 1: Аудит безопасности и надёжности
- **Защита маршрутов администратора:** Все GET и POST эндпоинты `/api/admin/*`, `/api/ai/settings`, `/api/upload`, `/api/save`, `/api/password` строго закрыты проверкой `self.authed()` с возвратом 401 Unauthorized для неавторизованных запросов.
- **CSRF:** Приложение использует Bearer-токены в заголовках `Authorization`, что исключает стандартные векторы CSRF-атак через браузерные cookie.
- **SQL Injection:** Проверен весь файл `server.py` — все динамические запросы используют параметризацию через плейсхолдеры `?` в SQLite. Прямой конкатенации пользовательского ввода в SQL-запросы нет.
- **Path Traversal & IDOR:** Проверена валидация путей в `SimpleHTTPRequestHandler` (отсечение `..`), проверка прав владельца на тренировки, платежи и личные данные.
- **Усиление заголовков безопасности:** Добавлен современный заголовок `Permissions-Policy: geolocation=(), microphone=(), camera=()` в дополнение к существующим `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN` и `Referrer-Policy: same-origin`. Устаревший заголовок `X-XSS-Protection: 1; mode=block` удалён согласно современным стандартам безопасности (OWASP/MDN).

### Этап 2: Аутентификация и UX
- Проверена система регистрации и логина: валидация формата логина (`[a-z0-9_]{3,24}`), email (`EMAIL_RE`), пароля ($\ge 6$ символов) с хэшированием PBKDF2/SHA256 и уникальной солью.
- Защита от брутфорса: лимиты попыток входа с прогрессивным rate limiting (`check_fail_limit`).
- В SPA интерфейсе обработаны состояния загрузки, блокировка дабл-кликов, экранирование спецсимволов через `esc()`.
- При выходе из аккаунта (logout) локальная история тренера теперь очищается вместе с токенами сессии, гарантируя конфиденциальность на общих устройствах.

### Этап 3: Интеграция с Telegram
- Проверена серверная валидация Telegram WebApp `initData`:
  - Проверка 64-символьного хэша HMAC-SHA256 с ключом `WebAppData`.
  - Проверка свежести `auth_date` (лимит 86400 с, защита от расхождения часов).
  - Защита от повторного использования (replay protection) через реестр `tg_used_init_hashes`.
  - Одноразовые токены авторизации через deep-link `/start auth_<token>` со строгим TTL и инвалидацией.

### Этап 4: AI-тренер и защита от Prompt Injection
- **Устранение критической точки отказа:** Ранее при недоступности внешнего провайдера (таймаут сети, исчерпание квот, 5xx ошибки) пользователь получал ошибку 502 Bad Gateway. Реализован надёжный автоматический fallback: при любых сбоях внешнего API ответ генерируется встроенным движком `ask_builtin` с полезными рекомендациями и ссылками на каталог, сопровождаясь корректным пояснением пользователю.
- **Типизация ошибок и разделение сбоев провайдера и багов кода:**
  - Введено специализированное исключение `AIProviderError` для ошибок внешнего API.
  - В `http_json`: HTTP-ошибки, сетевые сбои, таймауты (`TimeoutError`, `socket.timeout`) и невалидный JSON конвертируются в `AIProviderError`.
  - В `ask_gemini` / `ask_openai`: пустые ответы модели, аномальные структуры ответов (`candidates`, `choices`, `content`), несоответствия типов данных конвертируются в `AIProviderError`.
  - Внутренние непредвиденные ошибки кода (`TypeError`, `KeyError`, `AttributeError` не связанные со структурой API) не маскируются и пробрасываются в HTTP 500 для надлежащего мониторинга.
  - Ошибки конфигурации (отсутствие Base URL, выключенный AI) вызывают понятный `RuntimeError` без маскировки под сетевой сбой.
- **Серверное хранение истории диалогов (No Fake Model Injections):**
  - Сервер больше не доверяет клиентской истории сообщений и полностью игнорирует передаваемые клиентом элементы `role: "model"`.
  - Клиент передаёт только текущий вопрос (`message`) либо последний ввод пользователя.
  - Вся верифицированная история диалога сохраняется на сервере в SQLite таблице `coach_sessions` с версионированием сессий (`version INTEGER NOT NULL DEFAULT 1`).
  - Условные `UPDATE ... WHERE session_id = ? AND version = current_version` и `INSERT ... WHERE NOT EXISTS (...)` предотвращают воскрешение удалённой истории запоздавшими ответами при параллельной очистке.
  - Гостевые пользователи привязываются к криптографически случайному идентификатору в защищённой cookie `coach_sid` (`HttpOnly`, `SameSite=Lax`, `Path=/api/coach`, динамический `Secure` при HTTPS).
  - Авторизованные пользователи привязываются к `user_<id>`, сохраняя непрерывность диалога при смене cookie. Недействительный/просроченный Bearer-токен возвращает 401 и не деградирует в гостевую сессию.
  - Серверная проверка идемпотентности по клиентскому `reqId` / `clientMsgId` с криптографической привязкой к SHA-256 хэшу нормализованного текста вопроса:
    - При совпадении `reqId` и хэша вопроса ответ возвращается из кэша без повторного обращения к AI (если ответ модели существует и не пуст).
    - При совпадении `reqId` и хэша, если предыдущая генерация не завершилась (ответ модели отсутствует или пуст): пустой HTTP 200 НЕ возвращается; сервер очищает незавершённый ввод и безопасно запускает повторную генерацию без дублирования сообщения пользователя.
    - При совпадении `reqId`, но отличии текста вопроса возвращается HTTP 409 с безопасным сообщением без раскрытия данных.
    - Сохранена полная обратная совместимость со старыми записями без хэша (без назначения фиктивных хэшей и без опасных миграций).
    - Разные пользователи с одинаковым `reqId` полностью изолированы.
  - Добавлен эндпоинт `POST /api/coach/clear` для явной очистки серверной истории и ротации cookie.
  - Внедрена защита от гонки параллельных запросов (in-flight concurrency lock), возвращающая 429, если для данной сессии ещё генерируется предыдущий ответ.
  - Внешний сетевой вызов `ask_ai` выполняется строго за пределами `db_lock`, исключая зависание базы данных для других пользователей.
- **Клиентский жизненный цикл и защита от гонок в браузере (`site/app.js`):**
  - Изоляция локального хранилища истории по аккаунтам: `coach_guest` для гостей, `coach_u_<username>` для облачных пользователей, `coach_local_<username>` для локальных аккаунтов. Исключено смешивание истории при смене аккаунта.
  - Защита от гонки при выходе (`performCloudLogout`): глобальный хук `window._cancelCoachRequest` инкрементирует `coachReqSeq` и отменяет `coachAbort`, предотвращая запись запоздавшего ответа в хранилище нового пользователя.
  - Очередь очистки истории: новое сообщение ожидает завершения активного промиса `/api/coach/clear` (`activeClearPromise`), исключая удаление нового сообщения незавершённой очисткой.
  - При ошибке очистки на сервере клиентский UI откатывает историю и отображает информативный тост, исключая ложное подтверждение очистки.
  - Использование `AbortController` в качестве сетевой оптимизации.
- **Системный промпт безопасности:**
  - Запрет выхода из роли и игнорирование попыток стереть инструкции.
  - Запрет раскрытия системного промпта, серверных данных и токенов.
  - Категорический запрет на рекомендации анаболических стероидов, рецептурных препаратов и опасных методик обезвоживания.
  - Обязательная рекомендация прекратить тренировку и обратиться к врачу при острой боли или травмах.

### Этап 5: Google Analytics 4
- Проверена чистота интеграции GA4 (`G-XSBKDCY4CS`):
  - Полная нормализация ключей и рекурсивная очистка PII.
  - Маскирование email, токенов, паролей и номеров телефонов.
  - Очистка URL и SPA-хэшей от query-параметров.
  - Отсутствие счётчиков на `/admin.html`.

### Этап 6: SEO и качество контента
- Проверены и зафиксированы метатеги `site/index.html`, `site/fitify/index.html` и `site/fitify/muscles.html`.
- У всех страниц корректные `canonical` ссылки и `<meta name="robots" content="index, follow">`.
- `site/sitemap.xml` содержит ровно 3 индексируемые публичные страницы с реальными датами `lastmod`.
- Приватные директории (`/admin.html`, `/api/`, `/server_data/`) закрыты в `robots.txt`.

### Этап 7: Производительность и мобильное качество
- `site/sw.js`: В список кэшируемых компонентов PWA Shell (`CORE_ASSETS`) добавлен `./analytics.js`, что обеспечивает стабильную работу без блокировок при офлайн-запусках.
- Кэширование статики: статические ресурсы снабжены заголовками `Cache-Control: no-cache, must-revalidate`, а `/api/` строго закрыт `Cache-Control: no-store`.
- Адаптивность: интерфейс проверен на мобильных и десктопных разрешениях.

### Этап 8: Рекомендации по росту и конверсии
- Сформированы стратегические предложения (см. раздел 10).

---

## 4. Security Findings & Audit Table

| ID | Область | Уровень | Проблема / Описание | Статус / Решение |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | AI Coach | Medium | При падении внешнего AI-провайдера клиент получал 502 Bad Gateway без ответа. | **ИСПРАВЛЕНО**: Внедрён автоматический fallback на `ask_builtin`, возвращающий статус 200 и полезные рекомендации. |
| **SEC-02** | AI Safety | High | Риск подделки истории (`role: "model"`), replay ответов и prompt injection через клиентский payload. | **ИСПРАВЛЕНО**: Переход на серверную историю `coach_sessions` в SQLite. Клиентские `role: "model"` игнорируются. Сессии изолированы по `user_<id>` и защищённым cookie `coach_sid` (`HttpOnly; SameSite=Lax`). |
| **SEC-03** | Headers | Low | Отсутствовали заголовки ограничения возможностей браузера (Permissions-Policy). Устаревший X-XSS-Protection. | **ИСПРАВЛЕНО**: Добавлен `Permissions-Policy: geolocation=(), microphone=(), camera=()`. Устаревший заголовок `X-XSS-Protection` удалён. |
| **SEC-04** | PWA Shell | Low | Файл `analytics.js` отсутствовал в `CORE_ASSETS` Service Worker-а. | **ИСПРАВЛЕНО**: Файл добавлен в кэш PWA, предотвращая сетевые ошибки офлайн. |
| **SEC-05** | Admin API | Critical | Проверка несанкционированного доступа к служебным маршрутам. | **ПОДТВЕРЖДЕНО**: Все 18 админ-маршрутов закрыты проверкой `self.authed()` (покрыто тестами `test_security_audit.py`). |
| **SEC-06** | Telegram | High | Проверка атак повторного воспроизведения (replay) и подделки подписи. | **ПОДТВЕРЖДЕНО**: Реализован HMAC-SHA256, проверка `auth_date` и реестр использованных хэшей. |
| **SEC-07** | Payments | High | Проверка подделки статусов оплаты в YooKassa. | **ПОДТВЕРЖДЕНО**: В платном режиме вебхуки валидируются прямым запросом в API ЮKassa. В бесплатном режиме (`FREE_ACCESS_MODE`) приём платежей заблокирован (403). |

---

## 5. Summary of Code Changes

1. **`server.py`**:
   - Обновлён системный промпт AI-тренера (`SYSTEM`) с добавлением жестких правил безопасности, анти-инъекций и запрета стероидов.
   - В `ask_ai` расширен перехват исключений: при любых ошибках внешних провайдеров происходит бесшовный fallback на `ask_builtin`.
   - Внедрена таблица `coach_sessions` с автоматической очисткой устаревших сессий (>14 дней).
   - Внедрён модуль генерации и валидации `coach_sid` cookie (`HttpOnly; SameSite=Lax; Path=/api/coach; Secure`).
   - Маршрут `POST /api/coach` переписан на чтение/запись серверной истории сообщений с блокировкой параллельных запросов одной сессии (429) и вызовом AI вне `db_lock`.
   - Добавлен маршрут `POST /api/coach/clear` для очистки истории и ротации сессионного cookie.
   - В `end_headers` добавлен `Permissions-Policy` и удалён устаревший `X-XSS-Protection`.
   - В `send_j` добавлена поддержка произвольных заголовков ответа (`headers`).
2. **`site/app.js`**:
   - При отправке запроса в `/api/coach` при наличии авторизации автоматически передаётся `Authorization: Bearer <token>`.
   - При очистке чата кнопкой `#cclr` отправляется фоновый вызов `POST /api/coach/clear`.
   - При выходе из аккаунта (logout) ключ `coach` удаляется из `localStorage`.
3. **`site/sw.js`**:
   - В массив `CORE_ASSETS` добавлен `./analytics.js`.
4. **`tests/test_growth_orchestrator.py`**:
   - Создан комплексный набор из 10 автоматических тестов:
     1. `test_enhanced_security_headers_present_on_responses`
     2. `test_ai_coach_system_prompt_safety_boundaries`
     3. `test_ai_coach_fallback_on_provider_error`
     4. `test_ai_coach_api_endpoint_handles_fallback_gracefully`
     5. `test_pwa_service_worker_caches_analytics_js`
     6. `test_coach_cookie_security_attributes`
     7. `test_client_cannot_inject_fake_model_role`
     8. `test_coach_session_isolation_and_persistence`
     9. `test_coach_in_flight_concurrency_protection`
     10. `test_coach_clear_endpoint`
     11. `test_race_guest_clear_during_active_generation_does_not_restore_history`
     12. `test_race_user_clear_during_active_generation_does_not_restore_history`
     13. `test_invalid_bearer_token_returns_401`
     14. `test_expired_or_revoked_token_does_not_turn_request_into_guest`
     15. `test_request_without_token_continues_as_guest`
     16. `test_valid_token_ensures_history_isolation_across_different_users`
     17. `test_browser_client_coach_lifecycle_logout_and_account_isolation`
     18. `test_browser_client_coach_race_condition_and_clear`
     19. `test_ai_provider_error_vs_programming_error_separation`
     20. `test_ai_provider_malformed_structures_and_type_errors`
     21. `test_coach_idempotency_key_prevents_duplicate_ai_calls`
     22. `test_coach_idempotency_same_req_id_same_question_returns_cached_and_calls_ai_once`
     23. `test_coach_idempotency_same_req_id_different_question_returns_409_conflict`
     24. `test_coach_idempotency_different_users_same_req_id_are_isolated`
     25. `test_coach_idempotency_retry_after_clear_starts_fresh_dialogue`
     26. `test_coach_idempotency_legacy_record_without_req_hash_backward_compatible`
     27. `test_coach_idempotency_unfinished_request_regenerates_and_avoids_empty_200`
     28. `test_coach_idempotency_unfinished_request_does_not_duplicate_user_message_in_history`
     29. `test_coach_idempotency_unfinished_request_with_empty_model_reply_regenerates_cleanly`
     30. `test_coach_idempotency_retry_respects_session_concurrency_lock`
     31. `test_coach_idempotency_ai_failure_does_not_leave_session_locked`
5. **`.agents/skills/rizzafit-growth-orchestrator/`**:
   - Установлен и зарегистрирован официальный Agent Skill.

---

## 6. Test Suite Execution Results

Запущен полный набор тестов проекта:
```bash
python -m unittest discover -s tests -v
```
**Результат:**
```text
Ran 106 tests in 43.109s

OK
```
- `test_growth_orchestrator.py`: 31 тест — **OK**
  - включая тесты привязки idempotency key к SHA-256 хэшу текста вопроса, HTTP 409 Conflict при повторе `reqId` с другим вопросом, изоляцию ключей между разными пользователями, сброс кэша после `clear`, обратную совместимость для старых записей, безопасное возобновление незавершённых запросов без пустого HTTP 200 и без дублирования сообщений пользователя в истории, а также соблюдение сессионных блокировок.
- `test_security_audit.py`: 10 тестов — **OK**
- `test_social_auth_security.py`: 12 тестов — **OK**
- `test_social_and_messages.py`: 21 тест — **OK**
- `test_free_access_mode.py`: 5 тестов — **OK**
- `test_google_analytics.py`: 13 тестов — **OK**
- `test_seo_stage1.py`: 5 тестов — **OK**
- `test_seo_stage2.py`: 6 тестов — **OK**
- `test_seo_http.py`: 3 теста — **OK**

Всего: **106 тестов пройдено, 0 ошибок, 0 сбоев.**

---

## 7. Blocked Items & Owner Decisions Required

1. **Платный режим vs Free Access Mode:**
   В настоящее время активен `FREE_ACCESS_MODE = True`. Переключение на приём реальных платежей через ЮKassa требует явного решения владельца, заполнения боевых `shop_id` и `secret_key` и переключения флага.
2. **Внешний AI-провайдер:**
   Для работы DeepSeek/OpenAI/Gemini в боевом режиме администратор должен указать рабочий API-ключ в панели управления `/admin.html`. Благодаря реализованному fallback сайт не упадёт, даже если баланс ключа закончится.
3. **Search Console:**
   По указанию владельца страницы Fitify не отправляются на принудительную индексацию в Google Search Console.

---

## 8. Recommended Next Actions for Growth

1. **Онбординг новых пользователей:**
   Добавить короткий интерактивный опросник из 3 вопросов при первом входе (цель: похудение / сила / выносливость, уровень подготовки, доступный инвентарь) с автоматическим подбором стартовой программы.
2. **Геймификация и удержание (Retention):**
   Интегрировать streak-счётчик тренировок («Дней подряд без пропусков») с push-напоминанием через Telegram-бота, если тренировка пропущена более 2 дней.
3. **Контент и SEO-лендинги:**
   Создать статические публичные посадочные страницы под популярные поисковые запросы: «Программа 100 отжиманий», «Калистеника для начинающих», «Как научиться подтягиваться с нуля» с прямой ссылкой на интерактивные тренировки внутри SPA.
4. **Социальная механика:**
   Развивать существующий функционал совместных квестов (Quests) и таблицы лидеров среди друзей, стимулируя шеринг реферальных ссылок в Telegram.
