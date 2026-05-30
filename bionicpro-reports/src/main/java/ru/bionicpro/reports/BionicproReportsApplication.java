package ru.bionicpro.reports;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableCaching
@EnableScheduling
@SpringBootApplication(scanBasePackages = "ru.bionicpro.reports")
public class BionicproReportsApplication {

    public static void main(String[] args) {
        SpringApplication.run(BionicproReportsApplication.class, args);
    }

}

