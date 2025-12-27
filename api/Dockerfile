FROM golang:1.23.2 AS builder
RUN go version

WORKDIR /app
COPY . .
RUN set -Eeux && \
	go mod download && \
	go mod verify

RUN GOOS=linux GOARCH=amd64 \
	go build \
	-o reports cmd/reports/main.go

FROM scratch
WORKDIR /root/

COPY --from=builder /app/reports reports

ENTRYPOINT ["./reports"]
