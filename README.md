# architecture-bionicpro

## Запуск

Запускать `docker compose` нужно **из корня репозитория** (где лежит `docker-compose.yaml`), с пересборкой сервисов:

```bash
cd <папка-репозитория>
docker compose up -d --build
```

Если запускаете из другой директории, укажите путь к compose-файлу явно:

```bash
docker compose -f ./docker-compose.yaml up -d --build
```


