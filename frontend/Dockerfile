# Стадия сборки
FROM node:16-alpine as build

WORKDIR /app

# Копируем файлы пакета
COPY package.json package-lock.json ./

# Устанавливаем зависимости
RUN npm ci

# Копируем исходный код
COPY . .

# Переменные REACT_APP_* вшиваются в статический бандл на этапе сборки,
# поэтому их нужно передавать как build args, а не как env-переменные контейнера.
ARG REACT_APP_AUTH_URL
ENV REACT_APP_AUTH_URL=$REACT_APP_AUTH_URL

# Собираем приложение
RUN npm run build

# Продакшн-стадия
FROM nginx:alpine

# Копируем собранные файлы со стадии сборки
COPY --from=build /app/build /usr/share/nginx/html

# Копируем конфигурацию nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт
EXPOSE 3000

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]