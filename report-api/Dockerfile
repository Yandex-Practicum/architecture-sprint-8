# ====== Build stage ======
FROM golang:1.26 AS builder

WORKDIR /app

# Копируем всё
COPY . .

# Сборка бинарника
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o report .

# ====== Final stage ======
FROM alpine:3.19

WORKDIR /app

# Копируем бинарник из builder
COPY --from=builder /app/report .

# Порт, который слушает приложение
EXPOSE 8080

# Запуск
CMD ["./report"]