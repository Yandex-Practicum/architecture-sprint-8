package com.bionicpro.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class BionicProAuthApplication {
    public static void main(String[] args) {
        SpringApplication.run(BionicProAuthApplication.class, args);
    }
}
