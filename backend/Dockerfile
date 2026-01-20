FROM golang:1.23-alpine AS builder
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o prothetic-server .

FROM alpine:latest
WORKDIR /root/

COPY --from=builder /app/prothetic-server .

EXPOSE 8000

CMD ["./prothetic-server"]