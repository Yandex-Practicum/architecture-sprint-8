FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /app

COPY pom.xml .
RUN mvn -B dependency:go-offline

COPY src ./src
RUN mvn -B package -DskipTests

FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY --from=build /app/target/bionicpro-auth-*.jar app.jar

EXPOSE 8081

CMD ["java", "-jar", "app.jar"]
