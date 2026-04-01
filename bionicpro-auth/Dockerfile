# ====== Build stage ======
FROM golang:1.23 AS builder

WORKDIR /app

# Копируем всё
COPY . .

# Сборка бинарника
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o bff .

# ====== Final stage ======
FROM alpine:3.19

WORKDIR /app

# Копируем бинарник из builder
COPY --from=builder /app/bff .

# Порт, который слушает приложение
EXPOSE 8001

# Запуск
CMD ["./bff"]