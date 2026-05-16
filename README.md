# Запуск проекта:

### Установить зависимости

pip install -r requirements.txt



### Запустить все сервисы Docker Compose:


    docker-compose down -v  
    docker-compose up -d --build

### Добавить данные в БД

    docker exec -it architecture-bionicpro-keycloak_db-1 psql -U keycloak_user -d keycloak_db -c "
    CREATE TABLE IF NOT EXISTS crm_customers (user_id VARCHAR(255) PRIMARY KEY, first_name VARCHAR(255), last_name VARCHAR(255));
    CREATE TABLE IF NOT EXISTS telemetry (movement_id SERIAL PRIMARY KEY, user_id VARCHAR(255), battery_level FLOAT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    
    INSERT INTO crm_customers (user_id, first_name, last_name) 
    VALUES ('prothetic1', 'Иван', 'Протезов')
    ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name;
    
    INSERT INTO telemetry (user_id, battery_level) VALUES ('prothetic1', 98.5);
    INSERT INTO telemetry (user_id, battery_level) VALUES ('prothetic1', 97.2);
    INSERT INTO telemetry (user_id, battery_level) VALUES ('prothetic1', 95.0);
    INSERT INTO telemetry (user_id, battery_level) VALUES ('prothetic1', 92.1);
    "

### Создать пользователя admin для Airflow (если он еще не создан):

    docker exec -it architecture-bionicpro-airflow-1 airflow users create \
        --username admin \
        --firstname admin \
        --lastname admin \
        --role Admin \
        --email admin@example.com \
        --password admin

## Проверка результата:

    docker ps
 все статусы Up

### Проверка Keycloak (Авторизация и пользователи)


- Открыть браузер и перейти по адресу: http://localhost:8080

Ожидаемый результат: страница приветствия Keycloak. 

Вход в http://localhost:8080/admin под логином admin/admin и убедиться, что realm reports-realm и пользователи (prothetic1, user1 и т.д.) существуют.

### Запуск ETL-процесса через Apache Airflow

- Открыть браузер и перейти по адресу: http://localhost:8081

Вход: логин admin и пароль admin.
- Найти DAG с названием report_sync на главной странице Airflow
- Включить DAG: иконк "Play" Trigger DAG
- Проверить статус: нажать на report_sync и перейдите во вкладку "Graph".

Ожидаемый результат: задачи (create_pg_tables_if_not_exists и sync_crm_and_telemetry) должны успешно выполниться и загореться темно-зеленым цветом. Это подтверждает, что данные из PostgreSQL были извлечены, обработаны и загружены в ClickHouse.

### Проверка данных в OLAP-базе (ClickHouse)

После того как DAG в Airflow успешно завершится (станет зеленым), открыть терминал и ввести:

    docker exec -it architecture-bionicpro-clickhouse-1 clickhouse-client -u default --password password123 -q "SELECT * FROM prothetic_reports"

Ожидаемый результат: одна или несколько строк с данными. Это подтверждает, что витрина данных в ClickHouse успешно создана и заполнена.

### Проверка Backend API (FastAPI)
- Открыть браузер,перейдите по http://localhost:8000/docs
- В интерактивной документации Swagger UI для нашего FastAPI развернуть метод GET/reports и получить  JSON-ответ с данными отчета для пользователя prothetic1 из ClickHouse. 

В поле Authorize ввести  JWT-токен. 
Его можете получить, залогинившись на фронтенде (http://localhost:3000) как prothetic1/prothetic123 через инструменты разработчика (F12) во вкладке "Application" -> "Local Storage" -> http://localhost:3000

или 

во вкладке Network при нажатии на запрос токена в Respons access_token
  

### Проверка Frontend-приложения (React)
- Открть браузер и перейти по http://localhost:3000
- Вход под пользователем prothetic1 с паролем prothetic123
- Нажать на кнопку "Download Report (JSON)"

Ожидаемый результат: браузер должен скачать файл report.json, который содержит агрегированные данные из ClickHouse для пользователя prothetic1.
