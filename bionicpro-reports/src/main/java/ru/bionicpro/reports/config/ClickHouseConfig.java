package ru.bionicpro.reports.config;

import com.clickhouse.jdbc.ClickHouseDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;

import javax.sql.DataSource;
import java.sql.SQLException;
import java.util.Properties;

@Configuration
public class ClickHouseConfig {

    @Value("${clickhouse.host:localhost}")
    private String host;

    @Value("${clickhouse.port:8123}")
    private int port;

    @Value("${clickhouse.database:reports_db}")
    private String database;

    @Value("${clickhouse.user:default}")
    private String user;

    @Value("${clickhouse.password:}")
    private String password;

    @Bean
    public DataSource clickHouseDataSource() throws SQLException {
        String url = String.format("jdbc:clickhouse://%s:%d/%s", host, port, database);
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("connection_timeout", "10000");

        return new ClickHouseDataSource(url, properties);
    }

    @Bean
    public JdbcTemplate clickHouseJdbcTemplate(DataSource clickHouseDataSource) {
        return new JdbcTemplate(clickHouseDataSource);
    }

    @Bean
    public PlatformTransactionManager transactionManager(DataSource clickHouseDataSource) {
        return new DataSourceTransactionManager(clickHouseDataSource);
    }
}
