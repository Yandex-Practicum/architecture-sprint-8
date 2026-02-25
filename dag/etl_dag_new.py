import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ============================================================
# Connection parameters
# ============================================================

CLICKHOUSE_HTTP_URL = "http://olap_db:8123"

# S3 (Minio) connection parameters for cache invalidation
S3_ENDPOINT_URL = "http://minio:9000"
S3_ACCESS_KEY = "minio_user"
S3_SECRET_KEY = "minio_password"
S3_BUCKET_NAME = "bionicpro-reports"


# ============================================================
# ETL Functions
# ============================================================

def invalidate_s3_report_cache(**kwargs):
    """
    Invalidate S3 report cache after ETL datamart update.

    Cache update mechanism:
    1. Primary: versioning by datamart_updated_at — new reports automatically
       get a different URL (version hash), so old CDN cache doesn't interfere.
    2. Additional: this function deletes old reports from S3 to free storage.
    3. CDN (Nginx) cache is invalidated automatically via proxy_cache_valid TTL
       or through URL change.
    """
    import boto3
    from botocore.exceptions import ClientError

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1',
        )

        prefix = "reports/"
        deleted_count = 0

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
                objects = page.get('Contents', [])
                if objects:
                    delete_keys = [{'Key': obj['Key']} for obj in objects]
                    s3_client.delete_objects(
                        Bucket=S3_BUCKET_NAME,
                        Delete={'Objects': delete_keys}
                    )
                    deleted_count += len(delete_keys)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                logger.info(f"Bucket '{S3_BUCKET_NAME}' does not exist yet, skipping")
                return
            raise

        logger.info(f"S3 cache invalidation complete: deleted {deleted_count} old reports")

    except Exception as e:
        logger.warning(f"S3 cache invalidation failed (non-critical): {str(e)}")


# ============================================================
# DAG Definition
# ============================================================

default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        dag_id="bionicpro_crm_to_olap_etl",
        default_args=default_args,
        description="ETL: CRM (PostgreSQL) -> OLAP (ClickHouse) + datamart + S3 cache invalidation",
        schedule_interval="0 2 * * *",
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=["bionicpro", "etl", "crm", "olap", "cache"],
) as dag:
    task_invalidate_cache = PythonOperator(
        task_id="invalidate_s3_report_cache",
        python_callable=invalidate_s3_report_cache,
    )

    # Only cache invalidation task remains after CDC implementation
    task_invalidate_cache
