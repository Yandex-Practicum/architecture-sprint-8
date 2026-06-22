FROM golang:1.21-alpine AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /bionicpro-auth .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=build /bionicpro-auth /app/bionicpro-auth
EXPOSE 8000
ENTRYPOINT ["/app/bionicpro-auth"]
