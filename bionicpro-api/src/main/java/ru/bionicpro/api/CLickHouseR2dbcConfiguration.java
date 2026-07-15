package ru.bionicpro.api;

import io.r2dbc.spi.ConnectionFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.r2dbc.core.binding.BindMarkersFactory;

@Configuration(proxyBeanMethods = false)
public final class CLickHouseR2dbcConfiguration {

    @Bean
    public BindMarkersFactory clickHouseBindMarkersFactory() {
        return BindMarkersFactory.named(":", "p", 32);
    }

    @Bean
    public DatabaseClient clickHouseDatabaseClient(
            ConnectionFactory connectionFactory,
            BindMarkersFactory clickHouseBindMarkersFactory
    ) {
        return DatabaseClient.builder()
                .connectionFactory(connectionFactory)
                .bindMarkers(clickHouseBindMarkersFactory)
                .build();
    }

}
