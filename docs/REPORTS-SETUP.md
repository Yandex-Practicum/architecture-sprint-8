# Сервис отчётов: запуск и проверка

## Что сделано

- **Архитектура**: [docs/REPORTS-ARCHITECTURE.md](REPORTS-ARCHITECTURE.md), [reports-etl-architecture.drawio](../reports-etl-architecture.drawio).
- **OLAP**: PostgreSQL (`olap_db`) с витриной `datamart_reports` (см. [olap/init.sql](../olap/init.sql)).
- **Reports API**: сервис на порту 9000, `GET /reports` — читает из витрины по заголовку `X-User-Id` (его подставляет bionicpro-auth). Доступ только к своему отчёту.
- **Airflow DAG**: [airflow/dags/reports_etl_dag.py](../airflow/dags/reports_etl_dag.py) — ETL по расписанию (ежедневно), заполняет staging и витрину.
- **UI**: кнопка «Получить отчёт» вызывает `/api/reports` с cookie; без авторизации запрос не уходит (редирект на логин); ответ только по своему user_id.

## Запуск

```bash
docker compose up -d --build
```

Поднимаются: olap_db, reports-api, bionicpro-auth (с `REPORTS_API_URL=http://reports-api:9000/reports`), frontend и остальные сервисы.

## Как увидеть отчёт (данные уже в витрине)

Отчёт возвращается только за периоды, которые уже обработаны Airflow. Если витрина пуста для вашего пользователя, API вернёт 404 с сообщением «Данные за период ещё не готовы».

**Вариант 1 — вручную вставить отчёт для user1 (или любого пользователя)**

1. Войдите в приложение (http://localhost:3000) под user1@example.com. На странице отчётов под «Logged in as» будет строка **User ID для отчётов:** с вашим `sub` (UUID). Скопируйте его.
2. В корне проекта выполните (подставьте скопированный UUID вместо `USER_SUB`):

```bash
docker compose exec olap_db psql -U olap_user -d olap_db -c "
INSERT INTO datamart_reports (user_id, period_from, period_to, summary)
VALUES ('USER_SUB', CURRENT_DATE - 7, CURRENT_DATE, '{\"usage_hours\": 5, \"steps\": 1200, \"events_count\": 10}')
ON CONFLICT (user_id, period_from, period_to) DO UPDATE SET summary = EXCLUDED.summary, report_generated_at = NOW();
"
```

Пример (подставьте свой UUID из UI):

```bash
docker compose exec olap_db psql -U olap_user -d olap_db -c "
INSERT INTO datamart_reports (user_id, period_from, period_to, summary)
VALUES ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', CURRENT_DATE - 7, CURRENT_DATE, '{\"usage_hours\": 5, \"steps\": 1200}')
ON CONFLICT (user_id, period_from, period_to) DO UPDATE SET summary = EXCLUDED.summary, report_generated_at = NOW();
"
```

3. Снова нажмите «Получить отчёт» в UI — должен появиться JSON-отчёт.

**Вариант 2 — запустить Airflow и DAG**

- Поднять Airflow, настроить connection `olap_db` на `postgresql://olap_user:olap_password@olap_db:5432/olap_db`.
- Запустить DAG `reports_etl` вручную или дождаться расписания. В демо-DAG в витрину пишутся пользователи `user1-id` и `user2-id`; в проде в DAG подставляются реальные Keycloak `sub` из CRM/синхронизации.

## Результат

- UI вызывает API для генерации/получения отчётов — да (кнопка «Получить отчёт» → `GET /api/reports` с `credentials: 'include'`).
- Неавторизованный пользователь не может получить отчёт — да (bionicpro-auth возвращает 401 без сессии).
- Авторизованный пользователь получает только свой отчёт — да (reports-api читает `X-User-Id` от bionicpro-auth и выбирает из витрины только по этому user_id).
- Отчёты берутся из OLAP — да (reports-api читает из `datamart_reports`).
- Отчёт только за уже обработанный период — да (витрину заполняет Airflow; при отсутствии данных API возвращает 404).
