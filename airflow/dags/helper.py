from datetime import datetime, timedelta
import logging
import pandas as pd
from io import StringIO


def convert_string_to_datetime(date_string):
    if not date_string or not date_string.strip() or date_string.strip().lower() in ('na', 'nat', 'none', 'null'):
        return None

    cleaned_string = date_string.strip()
    datetime_formats = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f')

    for date_format in datetime_formats:
        try:
            return datetime.strptime(cleaned_string, date_format)
        except ValueError:
            continue

    logging.warning(f"Ошибка преобразования даты: {date_string}")
    return None


def serialize_dataframe_xcom(dataframe, task_instance, xcom_key):
    output_buffer = StringIO()
    dataframe.to_csv(output_buffer, index=False, date_format='%Y-%m-%d %H:%M:%S')
    task_instance.xcom_push(key=xcom_key, value=output_buffer.getvalue())


def deserialize_xcom_dataframe(task_instance, source_task, xcom_key):
    csv_content = task_instance.xcom_pull(task_ids=source_task, key=xcom_key)
    if not csv_content:
        raise ValueError(f"Отсутствуют данные XCom: задача={source_task}, ключ={xcom_key}")

    dataframe = pd.read_csv(StringIO(csv_content))

    datetime_columns = [col for col in ['signal_time', 'last_signal_time'] if col in dataframe.columns]
    if datetime_columns:
        for time_column in datetime_columns:
            dataframe[time_column] = pd.to_datetime(dataframe[time_column], errors='coerce')

    return dataframe