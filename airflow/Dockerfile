FROM apache/airflow:2.8.1

COPY --chown=airflow:0 requirements.txt /requirements.txt

USER airflow

RUN PYVER="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" && \
    pip install --no-cache-dir -r /requirements.txt \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-${PYVER}.txt"
