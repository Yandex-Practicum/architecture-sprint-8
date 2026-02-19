docker run --rm --network architecture-bionicpro_default \
  minio/mc:RELEASE.2025-08-13T08-35-41Z \
  sh -c 'mc alias set local http://minio:9000 minioadmin minioadmin && echo "--- buckets ---" && mc ls local && echo "--- reports ---" && mc ls local/reports || true'
