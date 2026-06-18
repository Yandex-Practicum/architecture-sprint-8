FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/bionicpro-auth .

FROM alpine:3
RUN apk add --no-cache ca-certificates tzdata && \
    addgroup -S app && adduser -S -G app app
WORKDIR /app
COPY --from=build /out/bionicpro-auth /app/bionicpro-auth
USER app
EXPOSE 8443
ENTRYPOINT ["/app/bionicpro-auth"]