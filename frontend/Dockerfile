# Build stage
FROM node:16-alpine AS build

WORKDIR /app

ARG REACT_APP_API_URL=
ARG REACT_APP_AUTH_PREFIX=
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_AUTH_PREFIX=$REACT_APP_AUTH_PREFIX

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
