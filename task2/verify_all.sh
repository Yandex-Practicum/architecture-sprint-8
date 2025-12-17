#!/bin/bash

echo "🔍 Проверка проекта BionicPRO Reports..."
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Проверка структуры проекта
echo "1. Проверка структуры проекта..."
if [ -d "backend/src/main/java" ]; then
    echo -e "${GREEN}✓${NC} Backend структура найдена"
else
    echo -e "${RED}✗${NC} Backend структура не найдена"
    ERRORS=$((ERRORS + 1))
fi

if [ -d "airflow/dags" ]; then
    echo -e "${GREEN}✓${NC} Airflow структура найдена"
else
    echo -e "${RED}✗${NC} Airflow структура не найдена"
    ERRORS=$((ERRORS + 1))
fi

# Проверка Java файлов
echo ""
echo "2. Проверка Java файлов..."
JAVA_FILES=$(find backend/src/main/java -name "*.java" 2>/dev/null)
if [ -z "$JAVA_FILES" ]; then
    echo -e "${RED}✗${NC} Java файлы не найдены"
    ERRORS=$((ERRORS + 1))
else
    JAVA_COUNT=$(echo "$JAVA_FILES" | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} Найдено $JAVA_COUNT Java файлов"
    
    # Проверка основных классов
    if [ -f "backend/src/main/java/com/bionicpro/reports/ReportsApiApplication.java" ]; then
        echo -e "${GREEN}✓${NC} Главный класс приложения найден"
    else
        echo -e "${RED}✗${NC} Главный класс приложения не найден"
        ERRORS=$((ERRORS + 1))
    fi
    
    if [ -f "backend/src/main/java/com/bionicpro/reports/controller/ReportsController.java" ]; then
        echo -e "${GREEN}✓${NC} Контроллер найден"
    else
        echo -e "${RED}✗${NC} Контроллер не найден"
        ERRORS=$((ERRORS + 1))
    fi
    
    if [ -f "backend/src/main/java/com/bionicpro/reports/service/ReportsService.java" ]; then
        echo -e "${GREEN}✓${NC} Сервис найден"
    else
        echo -e "${RED}✗${NC} Сервис не найден"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Проверка pom.xml
echo ""
echo "3. Проверка Maven конфигурации..."
if [ -f "backend/pom.xml" ]; then
    echo -e "${GREEN}✓${NC} pom.xml найден"
    
    # Проверка основных зависимостей
    if grep -q "spring-boot-starter-web" backend/pom.xml; then
        echo -e "${GREEN}✓${NC} Spring Boot Web зависимость найдена"
    else
        echo -e "${YELLOW}⚠${NC} Spring Boot Web зависимость не найдена"
    fi
    
    if grep -q "clickhouse-jdbc" backend/pom.xml; then
        echo -e "${GREEN}✓${NC} ClickHouse JDBC зависимость найдена"
    else
        echo -e "${YELLOW}⚠${NC} ClickHouse JDBC зависимость не найдена"
    fi
else
    echo -e "${RED}✗${NC} pom.xml не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка application.yml
echo ""
echo "4. Проверка конфигурации..."
if [ -f "backend/src/main/resources/application.yml" ]; then
    echo -e "${GREEN}✓${NC} application.yml найден"
else
    echo -e "${RED}✗${NC} application.yml не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка Airflow DAG
echo ""
echo "5. Проверка Airflow DAG..."
if [ -f "airflow/dags/reports_etl_dag.py" ]; then
    echo -e "${GREEN}✓${NC} DAG файл найден"
    
    # Проверка синтаксиса Python
    if command -v python3 &> /dev/null; then
        if python3 -m py_compile airflow/dags/reports_etl_dag.py 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Синтаксис Python корректен"
        else
            echo -e "${RED}✗${NC} Ошибка синтаксиса Python"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    echo -e "${RED}✗${NC} DAG файл не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка SQL скрипта
echo ""
echo "6. Проверка SQL скрипта..."
if [ -f "airflow/scripts/create_data_mart.sql" ]; then
    echo -e "${GREEN}✓${NC} SQL скрипт найден"
else
    echo -e "${RED}✗${NC} SQL скрипт не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка фронтенда
echo ""
echo "7. Проверка фронтенда..."
if [ -f "../frontend/src/components/ReportPage.tsx" ]; then
    echo -e "${GREEN}✓${NC} ReportPage.tsx найден"
    
    # Проверка наличия функции fetchReport
    if grep -q "fetchReport" ../frontend/src/components/ReportPage.tsx; then
        echo -e "${GREEN}✓${NC} Функция fetchReport найдена"
    else
        echo -e "${RED}✗${NC} Функция fetchReport не найдена"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Проверка кнопки
    if grep -q "Get Report\|Download Report" ../frontend/src/components/ReportPage.tsx; then
        echo -e "${GREEN}✓${NC} Кнопка получения отчёта найдена"
    else
        echo -e "${YELLOW}⚠${NC} Кнопка получения отчёта не найдена"
    fi
else
    echo -e "${YELLOW}⚠${NC} ReportPage.tsx не найден (возможно в другом месте)"
fi

# Итоги
echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Все проверки пройдены успешно!${NC}"
    exit 0
else
    echo -e "${RED}✗ Найдено ошибок: $ERRORS${NC}"
    exit 1
fi

