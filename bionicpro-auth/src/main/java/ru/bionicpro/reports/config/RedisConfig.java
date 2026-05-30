package ru.bionicpro.reports.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

@Configuration
@Slf4j
public class RedisConfig {

    @Value("${spring.redis.host:localhost}")
    private String redisHost;

    @Value("${spring.redis.port:6379}")
    private int redisPort;

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        LettuceConnectionFactory factory = new LettuceConnectionFactory(redisHost, redisPort);
        factory.setValidateConnection(true);
        return factory;
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // String serializer for keys
        template.setKeySerializer(new StringRedisSerializer());
        template.setHashKeySerializer(new StringRedisSerializer());

        // Configure ObjectMapper for JavaTimeModule
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        objectMapper.activateDefaultTyping(objectMapper.getPolymorphicTypeValidator(),
                ObjectMapper.DefaultTyping.NON_FINAL);
        objectMapper.findAndRegisterModules();

        // Custom serializer
        GenericJackson2JsonRedisSerializer customSerializer = new GenericJackson2JsonRedisSerializer(objectMapper);

        template.setValueSerializer(customSerializer);
        template.setHashValueSerializer(customSerializer);

        template.afterPropertiesSet();
        return template;
    }

    @PostConstruct
    public void testConnection() {
        try {
            LettuceConnectionFactory factory = (LettuceConnectionFactory) redisConnectionFactory();
            factory.afterPropertiesSet();
            RedisConnectionFactory conn = redisConnectionFactory();
            conn.getConnection().ping();
            log.info("Redis connection successful to {}:{}", redisHost, redisPort);
        } catch (Exception e) {
            log.error("Redis connection failed to {}:{}", redisHost, redisPort);
            log.error("Error: {}", e.getMessage());
        }
    }
}
