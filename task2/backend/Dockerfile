FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /app

# Копируем pom.xml и загружаем зависимости
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Копируем исходный код и собираем приложение
COPY src ./src
RUN mvn clean package -DskipTests

# Финальный образ
FROM eclipse-temurin:17-jre

# Устанавливаем curl для healthcheck (для Debian-based образа)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем собранный JAR
COPY --from=build /app/target/reports-api-*.jar app.jar

# Открываем порт
EXPOSE 8000

# Запускаем приложение
ENTRYPOINT ["java", "-jar", "app.jar"]

