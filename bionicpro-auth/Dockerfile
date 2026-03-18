FROM golang:1.25-alpine AS builder

WORKDIR /src

RUN apk add --no-cache ca-certificates tzdata

COPY go.mod ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/bionicpro-auth ./cmd/bionicpro-auth

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

COPY --from=builder /out/bionicpro-auth /app/bionicpro-auth

EXPOSE 8082

USER nonroot:nonroot

ENTRYPOINT ["/app/bionicpro-auth"]
