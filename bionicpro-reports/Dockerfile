# Stage 1: Build
FROM maven:3.9.6-eclipse-temurin-21 AS build

WORKDIR /app

# Копируем pom.xml и загружаем зависимости
COPY pom.xml .
RUN mvn dependency:go-offline -B || true

# Копируем исходники
COPY src ./src

# Собираем с детальным выводом ошибок
RUN mvn clean package -DskipTests -e -X

# Stage 2: Run
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Устанавливаем curl для healthcheck
RUN apk add --no-cache curl

# Создаем пользователя
RUN addgroup -S spring && adduser -S spring -G spring

# Копируем JAR
COPY --from=build /app/target/*.jar app.jar

# Меняем владельца
RUN chown -R spring:spring /app

USER spring:spring

EXPOSE 8082 5005

ENTRYPOINT ["java", \
    "-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005", \
    "-jar", \
    "app.jar"]