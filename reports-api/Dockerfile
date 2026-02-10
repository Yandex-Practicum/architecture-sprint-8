FROM golang:1.24-alpine AS build
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY *.go ./
RUN go mod tidy && CGO_ENABLED=0 go build -o /reports-api .

FROM alpine:3.19
EXPOSE 9000
COPY --from=build /reports-api /reports-api
CMD ["/reports-api"]
