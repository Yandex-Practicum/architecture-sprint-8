# Build stage
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/reports-api .

# Runtime stage
FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build /out/reports-api /app/reports-api
EXPOSE 8081
USER nonroot:nonroot
ENTRYPOINT ["/app/reports-api"]
