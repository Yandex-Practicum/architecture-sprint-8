# Задание 3. Снижение нагрузки на базу данных

В качестве объектного хранилища, поддерживающее S3 API, выбран Minio.
Отчёты в хранилище будут храниться по пользователям.

В docker-compose добавлена секция с настройками Minio:

```
minio:
  image: minio/minio:latest
  container_name: minio
  ports:
    - "9001:9000"
    - "9002:9001"
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  volumes:
    - ./minio_data:/data
  command: server /data --console-address ":9001"
  networks:
    - bionic-network
  restart: unless-stopped

minio-init:
  image: minio/mc:latest
  depends_on:
    - minio
  entrypoint: >
    sh -c "
    mc alias set local http://minio:9000 minioadmin minioadmin &&
    mc mb local/bionicpro-reports ||
    exit 0
    "
  networks:
    - bionic-network
```

Также добавлен nginx, как reverse proxy с кешем:

```
nginx-cdn:
  image: nginx:alpine
  container_name: nginx-cdn
  ports:
    - "8087:80"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/cache:/var/cache/nginx
  networks:
    - bionic-network
  restart: unless-stopped
```

Изменена логика выдачи отчёта в report-service: если отчёт есть в S3, он берётся оттуда, иначе запускается его фомирование и сохранение.

После поднятия minio в контейнере, нужно создать bucket с именем **bionicpro-reports** (в консоли http://localhost:9002/)
или через командную строку:

```
docker exec -it minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec -it minio mc mb local/bionicpro-reports
```




