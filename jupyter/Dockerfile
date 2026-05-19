FROM jupyter/datascience-notebook:latest

USER root
RUN pip install --no-cache-dir \
    boto3 \
    pyarrow \
    fastparquet \
    sqlalchemy \
    psycopg2-binary \
    minio \
    python-dotenv

USER ${NB_UID}
