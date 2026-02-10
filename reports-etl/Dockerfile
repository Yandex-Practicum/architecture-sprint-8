FROM golang:1.24-alpine AS build
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY *.go ./
RUN go mod tidy && CGO_ENABLED=0 go build -o /reports-etl .

FROM alpine:3.19
COPY --from=build /reports-etl /reports-etl
CMD ["/reports-etl"]
