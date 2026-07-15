FROM bellsoft/liberica-openjdk-alpine:17 AS builder
WORKDIR /app
COPY gradlew settings.gradle build.gradle ./
COPY gradle ./gradle
RUN ./gradlew dependencies
COPY . .
RUN ./gradlew build

FROM bellsoft/liberica-openjre-alpine:17
WORKDIR /app
COPY --from=builder /app/build/libs/bionicpro-auth-*.jar bionicpro-auth.jar
ENTRYPOINT ["java", "-jar", "bionicpro-auth.jar"]
