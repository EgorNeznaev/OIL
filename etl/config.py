import os
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "oiluser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "oilpass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "oildb")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
RAW_BUCKET = "oil-raw"
PROCESSED_BUCKET = "oil-processed"
MARTS_BUCKET = "oil-marts"
def minio_endpoint_url() -> str:
    raw = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip().rstrip("/")
    if raw.startswith("https://"):
        return raw
    if raw.startswith("http://"):
        return raw
    scheme = "https" if MINIO_SECURE else "http"
    return f"{scheme}://{raw}"
def postgres_url() -> str:
    return (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
