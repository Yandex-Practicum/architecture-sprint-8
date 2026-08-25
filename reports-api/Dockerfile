FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /reports-api .

FROM alpine:3.20
COPY --from=build /reports-api /usr/local/bin/reports-api
EXPOSE 8000
ENTRYPOINT ["reports-api"]
