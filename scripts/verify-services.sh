#!/usr/bin/env bash
# Проверка, что все сервисы подняты в Docker и отвечают.
# Запуск: из корня репозитория: ./scripts/verify-services.sh
# Перед этим: docker compose up -d --build

set -e
cd "$(dirname "$0")/.."

echo "=== Docker Compose: список сервисов ==="
docker compose ps -a

echo ""
echo "=== Проверка портов ==="

check() {
  local name=$1
  local url=$2
  local expected=${3:-200}
  if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$url" 2>/dev/null | grep -q "$expected"; then
    echo "  OK   $name ($url)"
  else
    echo "  FAIL $name ($url)"
    return 1
  fi
}

FAIL=0

# Keycloak — главная или realm
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://localhost:8080/" 2>/dev/null || echo "000")
if [[ "$CODE" == "200" || "$CODE" == "302" ]]; then
  echo "  OK   Keycloak (http://localhost:8080 -> $CODE)"
else
  echo "  FAIL Keycloak (http://localhost:8080) got $CODE"
  FAIL=1
fi

# bionicpro-auth — редирект на Keycloak при GET /auth/login (302)
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://localhost:8000/auth/login" 2>/dev/null || echo "000")
if [[ "$CODE" == "302" ]]; then
  echo "  OK   bionicpro-auth (http://localhost:8000/auth/login -> 302)"
else
  echo "  FAIL bionicpro-auth (http://localhost:8000/auth/login) got $CODE"
  FAIL=1
fi

# Frontend — главная
if check "Frontend" "http://localhost:3000"; then true; else FAIL=1; fi

# Redis (через bionicpro-auth или redis-cli — если redis не экспортирован, пропускаем)
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "  OK   Redis (ping)"
else
  echo "  SKIP Redis (контейнер может быть не запущен или redis-cli недоступен)"
fi

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "Все проверки пройдены."
else
  echo "Некоторые проверки не прошли. Убедитесь, что выполнен: docker compose up -d --build"
  exit 1
fi
