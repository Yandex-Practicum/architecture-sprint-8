# Node 18 — более свежий npm, обычно стабильнее при загрузке пакетов
FROM node:18-alpine AS build

WORKDIR /app

ARG REACT_APP_API_URL=
ARG REACT_APP_AUTH_PREFIX=
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_AUTH_PREFIX=$REACT_APP_AUTH_PREFIX
ENV NPM_CONFIG_PROGRESS=false

COPY package.json package-lock.json ./

# Длинные таймауты + несколько попыток при ERR_SOCKET_TIMEOUT / обрыве сети к registry.npmjs.org
RUN npm config set fetch-retries 15 \
    && npm config set fetch-retry-mintimeout 30000 \
    && npm config set fetch-retry-maxtimeout 180000 \
    && npm config set fetch-timeout 600000 \
    && set -e; \
    for attempt in 1 2 3 4 5; do \
      npm ci && exit 0; \
      echo "npm ci failed (attempt $attempt), retry in 25s..."; \
      [ "$attempt" -eq 5 ] && exit 1; \
      sleep 25; \
    done; \
    exit 1

COPY . .

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
