docker-compose run --rm airflow-webserver airflow db migrate

docker-compose run --rm airflow-webserver airflow connections create-default-connections

docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

echo "admin:admin"