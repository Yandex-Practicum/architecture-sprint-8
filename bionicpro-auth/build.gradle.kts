plugins {
    id("org.springframework.boot") version "3.5.10" // Use your desired Spring Boot version
    id("io.spring.dependency-management") version "1.1.7"
    id("java")
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-oauth2-client")
}

dependencyManagement {
}

// Apply a specific Java toolchain to ease working on different environments.
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

tasks.bootJar {
    archiveFileName.set("app.jar")
}
