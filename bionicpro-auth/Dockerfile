FROM golang:1.21-alpine AS builder

WORKDIR /app

# COPY go.mod ./
# COPY go.sum ./

# RUN go mod download

COPY . .

RUN rm -f go.mod go.sum && go mod init bionicpro-auth
RUN CGO_ENABLED=0 GOOS=linux go build -o auth-service ./main.go

FROM alpine:latest

WORKDIR /root/

COPY --from=builder /app/auth-service .

EXPOSE 8081

CMD ["./auth-service"]