package ru.bionicpro.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(proxyBeanMethods = false)
public final class Application {

	public static void main(String[] args) {
		SpringApplication.run(Application.class, args);
	}

}
