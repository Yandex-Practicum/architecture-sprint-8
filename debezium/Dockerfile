FROM debezium/connect:2.4

# Install wget to download plugins
USER root
RUN microdnf install -y wget tar gzip

# Switch back to kafka user
USER kafka

# Create plugins directory
RUN mkdir -p /kafka/connect/plugins

# Download and install Debezium PostgreSQL connector
RUN cd /tmp && \
    wget https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/2.4.2.Final/debezium-connector-postgres-2.4.2.Final-plugin.tar.gz && \
    tar -xzf debezium-connector-postgres-2.4.2.Final-plugin.tar.gz -C /kafka/connect/plugins && \
    rm -f debezium-connector-postgres-2.4.2.Final-plugin.tar.gz

# Verify plugins are installed
RUN ls -la /kafka/connect/plugins/