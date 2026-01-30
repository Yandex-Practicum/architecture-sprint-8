# BionicPRO Architecture

## Overview
This project implements a secure authentication system for BionicPRO using Keycloak, Redis, and a Python backend with React frontend.

## Services

### Authentication Backend (bionicpro-auth)
- **Port**: 8081
- **Technology**: FastAPI (Python)
- **Features**:
  - OAuth2 flow with PKCE
  - Session management with HTTP-only cookies
  - Token encryption and storage in Redis
  - Automatic token refresh

### Frontend
- **Port**: 3000
- **Technology**: React with TypeScript
- **Features**:
  - Authentication integration
  - Session cookie handling
  - Report page with protected content

### Keycloak
- **Port**: 8080
- **Technology**: Keycloak 21.1
- **Database**: PostgreSQL
- **Realm**: reports-realm

### Redis
- **Port**: 6379
- **Technology**: Redis 7
- **Usage**: Token storage with TTL

### RedisInsight (Redis UI)
- **Port**: 8001
- **Technology**: RedisInsight
- **Usage**: Web-based Redis management and monitoring
- **Access**: http://localhost:8001
- **Pre-configured**: Automatically connected to local Redis instance

## Getting Started

1. **Start all services**:
   ```bash
   docker compose up -d
   ```

2. **Access the application**:
   - Frontend: http://localhost:3000
   - Keycloak Admin: http://localhost:8080 (admin/admin)
   - RedisInsight: http://localhost:8001

3. **Authentication Flow**:
   - Visit the frontend
   - Click login to authenticate via Keycloak
   - Access protected reports after authentication

## Development

### Adding RedisInsight
RedisInsight provides a web-based interface for Redis monitoring and management.

To add RedisInsight to your setup:
1. Add the service to `docker-compose.yaml`
2. Run `docker compose up -d redis-insight`
3. Access at http://localhost:8001

### Environment Variables
- `KEYCLOAK_URL`: Keycloak server URL (internal: http://keycloak:8080)
- `KEYCLOAK_REALM`: Realm name (reports-realm)
- `REDIS_URL`: Redis connection URL (redis://redis:6379)

## Security Features
- HTTP-only session cookies (secure=False for dev mode)
- Encrypted token storage
- Automatic session rotation
- PKCE for OAuth2 security
- Cross-browser compatibility (Chrome, Safari, Firefox)
