# Задание 3. Снижение нагрузки на базу данных

Отчёты меняются только после планового ETL, поэтому одинаковые запросы можно не
пересчитывать. `reports-api` кэширует сформированные отчёты в объектном
хранилище **S3 (MinIO)** и отдаёт ссылку на **CDN (Nginx)**; повторные запросы
обслуживаются из CDN и **не доходят до OLAP**.

## Схема взаимодействия (cache-aside)

```
GET /api/reports ──▶ reports-api
     │ 1. watermark = max(report_date)   (дешёвый запрос метаданных)
     │ 2. key = <user>/<from>_<to>_<watermark>_<hmac>.json
     │ 3. HEAD key в S3?
     │      ├─ есть  ─▶ вернуть CDN-ссылку (cached=true)      ← OLAP НЕ запрашивается
     │      └─ нет   ─▶ Build() из OLAP → PUT в S3 → CDN-ссылка (cached=false)
Браузер ──GET CDN-ссылка──▶ Nginx (CDN, proxy_cache) ──▶ MinIO (origin)
                              HIT → отдаёт из кеша, MISS → тянет из MinIO и кладёт в кеш
```

## Инвалидация кеша и структура хранения

Ключ объекта **контентно-адресуемый**: включает `watermark` (дату последнего
периода, обработанного Airflow). Отчёт для `(user, период, версия данных)`
неизменяем, поэтому:
- при обновлении данных ETL сдвигает watermark → **меняется ключ** → новый объект
  и новый URL; CDN никогда не отдаёт устаревший отчёт, старые записи вытесняются
  по TTL/inactive. Отдельная «очистка» кеша не нужна.
- структура `reports/<username>/...` — префикс по пользователю: быстрый доступ и
  простое управление жизненным циклом (lifecycle policy) по пользователю.
- HMAC-подпись в имени (`REPORT_URL_SECRET`) не даёт перечислить/угадать объекты
  других пользователей; доступ к *генерации ссылки* дополнительно ограничен
  правилом «только свой отчёт» (Задание 2).

## Что сделано

| Задача | Реализация |
|---|---|
| Запись отчётов в S3 (Minio/Ceph) | [`reports-api/internal/storage/objectstore.go`](../reports-api/internal/storage/objectstore.go) (minio-go) |
| Логика S3↔CDN в API | [`reports-api/internal/httpapi/server.go`](../reports-api/internal/httpapi/server.go) → `serveCached`, `objectKey` |
| Проверка S3 → ссылка на CDN, иначе генерация→S3→CDN | `serveCached` (cache-aside) |
| Nginx как reverse proxy c кешем | [`nginx/cdn.conf`](../nginx/cdn.conf) (папка `nginx/`) |
| Nginx в docker-compose | сервис `cdn` + `minio` + `minio-init` в `docker-compose.yaml` |

Конфигурация MinIO — сервис `minio` (+ `minio-init` создаёт бакет `reports` и
делает объекты публично читаемыми для CDN).

## Сервисы

| Компонент | Технология | Порт |
|---|---|---|
| `minio` | MinIO (S3) | 9002 (API), 9001 (console) |
| `cdn` | Nginx (reverse proxy + proxy_cache) | 8090 |

## Замечания
- Бакет `reports` сделан публично читаемым (anonymous download) — так CDN отдаёт
  файлы без S3-подписи и корректно кеширует. Для прода: подписанные CDN-ссылки /
  токенизированные пути / signed cookies, т.к. отчёты содержат перс. данные.
- `reports-api` работает и без S3 (`S3_ENDPOINT` пуст) — тогда возвращает тело
  отчёта напрямую (режим Задания 2).
