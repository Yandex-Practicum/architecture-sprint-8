# Build stage
FROM node:16-alpine as build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build arguments for React environment variables
ARG REACT_APP_API_URL
ARG REACT_APP_AUTH_SERVICE_URL
ARG REACT_APP_KEYCLOAK_URL
ARG REACT_APP_KEYCLOAK_REALM
ARG REACT_APP_KEYCLOAK_CLIENT_ID

# Set environment variables from build args (for React build)
ENV REACT_APP_API_URL=${REACT_APP_API_URL}
ENV REACT_APP_AUTH_SERVICE_URL=${REACT_APP_AUTH_SERVICE_URL}
ENV REACT_APP_KEYCLOAK_URL=${REACT_APP_KEYCLOAK_URL}
ENV REACT_APP_KEYCLOAK_REALM=${REACT_APP_KEYCLOAK_REALM}
ENV REACT_APP_KEYCLOAK_CLIENT_ID=${REACT_APP_KEYCLOAK_CLIENT_ID}

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