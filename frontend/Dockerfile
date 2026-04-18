# Build stage — REACT_APP_* должны быть заданы до `npm run build` (иначе в бандле пустой API URL).
FROM node:16-alpine as build

WORKDIR /app

ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_KEYCLOAK_URL=http://localhost:8090
ARG REACT_APP_KEYCLOAK_REALM=reports-realm
ARG REACT_APP_KEYCLOAK_CLIENT_ID=reports-frontend

ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_KEYCLOAK_URL=$REACT_APP_KEYCLOAK_URL
ENV REACT_APP_KEYCLOAK_REALM=$REACT_APP_KEYCLOAK_REALM
ENV REACT_APP_KEYCLOAK_CLIENT_ID=$REACT_APP_KEYCLOAK_CLIENT_ID

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]