package com.bionicpro.reports.config;

import com.clickhouse.jdbc.ClickHouseDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;
import java.sql.SQLException;
import java.util.Properties;

@Configuration
public class ClickHouseConfig {

    @Value("${clickhouse.url:jdbc:clickhouse://localhost:8123/bionicpro_reports}")
    private String clickhouseUrl;

    @Value("${clickhouse.user:default}")
    private String clickhouseUser;

    @Value("${clickhouse.password:}")
    private String clickhousePassword;

    @Bean
    public DataSource clickHouseDataSource() throws SQLException {
        Properties properties = new Properties();
        // Всегда передаем user
        properties.setProperty("user", clickhouseUser != null ? clickhouseUser : "default");
        // Для ClickHouse с пустым паролем нужно передать пустую строку явно
        // Если пароль не указан или пустой, передаем пустую строку
        String password = (clickhousePassword != null && !clickhousePassword.trim().isEmpty()) 
            ? clickhousePassword 
            : "";
        properties.setProperty("password", password);
        // Увеличиваем timeout для подключения
        properties.setProperty("socket_timeout", "30000");
        properties.setProperty("connect_timeout", "10000");
        // Отключаем сжатие, так как LZ4 не поддерживается
        properties.setProperty("compress", "0");
        
        return new ClickHouseDataSource(clickhouseUrl, properties);
    }

    @Bean
    public JdbcTemplate jdbcTemplate(DataSource clickHouseDataSource) {
        return new JdbcTemplate(clickHouseDataSource);
    }
}

