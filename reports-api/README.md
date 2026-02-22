# reports-api — сервис отчётов

Сервис предоставляет endpoint `/reports/{user_id}` — возвращает агрегированный отчёт по данным из ClickHouse.

Как работает:
- Валидирует сессию, вызывая `bionicpro-auth` `/session/validate` (использует cookie сессии);
- Выполняет SQL-запрос к ClickHouse HTTP-интерфейсу (`http://olap_db:8123/`) и формирует JSON-отчёт.

Запуск (через docker-compose):
```bash
docker compose up --build
```
