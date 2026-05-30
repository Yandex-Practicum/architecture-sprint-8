FROM quay.io/keycloak/keycloak:21.1

USER root
RUN mkdir -p /opt/keycloak/providers

# 🔥 Основной плагин
ADD https://repo1.maven.org/maven2/ru/playa/keycloak/keycloak-russian-providers/21.1.1.rsp/keycloak-russian-providers-21.1.1.rsp.jar \
    /opt/keycloak/providers/

# 🔥 ЗАВИСИМОСТИ (ОБЯЗАТЕЛЬНО):
ADD https://repo1.maven.org/maven2/com/jayway/jsonpath/json-path/2.7.0/json-path-2.7.0.jar \
    /opt/keycloak/providers/
ADD https://repo1.maven.org/maven2/net/minidev/json-smart/2.4.7/json-smart-2.4.7.jar \
    /opt/keycloak/providers/
ADD https://repo1.maven.org/maven2/net/minidev/accessors-smart/2.4.7/accessors-smart-2.4.7.jar \
    /opt/keycloak/providers/
ADD https://repo1.maven.org/maven2/org/ow2/asm/asm/9.3/asm-9.3.jar \
    /opt/keycloak/providers/
ADD https://repo1.maven.org/maven2/org/slf4j/slf4j-api/1.7.36/slf4j-api-1.7.36.jar \
    /opt/keycloak/providers/

# Права для пользователя keycloak
RUN chown -R keycloak:keycloak /opt/keycloak/providers

USER keycloak

# Build при старте
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start-dev", "--build", "--hostname=localhost", "--http-port=8080"]