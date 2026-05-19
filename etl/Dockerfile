FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    pandas \
    pyarrow \
    boto3 \
    sqlalchemy \
    psycopg2-binary \
    scikit-learn \
    joblib \
    python-dotenv

COPY . .

CMD ["python", "export_to_minio.py"]
