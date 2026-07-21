# Build stage
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
# no external dependencies — go.sum is not required
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/bionicpro-auth .

# Runtime stage
FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build /out/bionicpro-auth /app/bionicpro-auth
EXPOSE 8000
USER nonroot:nonroot
ENTRYPOINT ["/app/bionicpro-auth"]
