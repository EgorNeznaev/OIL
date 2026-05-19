from __future__ import annotations
import io
import sys
from datetime import datetime
import boto3
import pandas as pd
from botocore.client import Config
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text
from config import (
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    PROCESSED_BUCKET,
    RAW_BUCKET,
    minio_endpoint_url,
    postgres_url,
)
TABLES = [
    "wells",
    "production",
    "well_telemetry",
    "well_targets",
    "pumps",
    "pump_sensors",
    "pump_failures",
    "deliveries",
    "drivers",
    "vehicles",
    "oil_stations",
]
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=minio_endpoint_url(),
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
def ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
def upload_parquet_partitioned(
    client,
    df: pd.DataFrame,
    bucket: str,
    prefix: str,
    date_col: str,
) -> int:
    if df.empty:
        return 0
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    count = 0
    for part_date, part_df in df.groupby(df[date_col].dt.date):
        buf = io.BytesIO()
        part_df.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)
        key = f"{prefix}/date={part_date}/data.parquet"
        client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
        count += 1
    return count
def clean_production(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    numeric_cols = [
        "oil_ton",
        "gas_m3",
        "water_m3",
        "energy_kwh",
        "downtime_hours",
        "temperature",
        "pressure",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    mask_active = df["oil_ton"] > 0
    for col in ["temperature", "pressure"]:
        median = df.loc[mask_active, col].median()
        df[col] = df[col].fillna(median if pd.notna(median) else 0)
    active = df[mask_active]
    if not active.empty:
        q1, q3 = active["oil_ton"].quantile([0.25, 0.75])
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_mask = mask_active & ((df["oil_ton"] < low) | (df["oil_ton"] > high))
        df.loc[outlier_mask, "oil_ton"] = df.loc[mask_active, "oil_ton"].median()
    df["downtime_ratio"] = (df["downtime_hours"].fillna(0) / 24.0).clip(0, 1)
    df["avg_pressure"] = df["pressure"]
    df["avg_temperature"] = df["temperature"]
    return df
def aggregate_telemetry_daily(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    agg = (
        df.groupby(["well_id", "date"])
        .agg(
            avg_pressure_in=("pressure_in", "mean"),
            avg_pressure_out=("pressure_out", "mean"),
            avg_temperature=("temperature", "mean"),
            avg_pump_speed=("pump_speed_rpm", "mean"),
            avg_pump_current=("pump_current", "mean"),
            pump_hours=("timestamp", "count"),
            avg_vibration=("vibration", "mean"),
            avg_oil_flow_rate=("oil_flow_rate", "mean"),
        )
        .reset_index()
    )
    agg["avg_pressure"] = (agg["avg_pressure_in"] + agg["avg_pressure_out"]) / 2
    agg["power_kw"] = agg["avg_pump_current"] * agg["avg_pressure_out"] / 1000
    return agg
def run_export() -> None:
    engine = create_engine(postgres_url())
    client = s3_client()
    ensure_bucket(client, RAW_BUCKET)
    ensure_bucket(client, PROCESSED_BUCKET)
    print(f"[{datetime.utcnow().isoformat()}] ETL started")
    with engine.connect() as conn:
        for table in TABLES:
            df = pd.read_sql(text(f"SELECT * FROM {table}"), conn)
            buf = io.BytesIO()
            df.to_parquet(buf, index=False, engine="pyarrow")
            buf.seek(0)
            client.put_object(
                Bucket=RAW_BUCKET,
                Key=f"postgres/{table}/snapshot.parquet",
                Body=buf.getvalue(),
            )
            print(f"  raw: {table} ({len(df)} rows)")
        production = pd.read_sql(text("SELECT * FROM production"), conn)
        telemetry = pd.read_sql(text("SELECT * FROM well_telemetry"), conn)
    production_clean = clean_production(production)
    n_prod = upload_parquet_partitioned(
        client, production_clean, PROCESSED_BUCKET, "production", "date"
    )
    print(f"  processed: production ({n_prod} partitions)")
    telemetry_daily = aggregate_telemetry_daily(telemetry)
    telemetry_daily["date"] = pd.to_datetime(telemetry_daily["date"])
    n_tel = upload_parquet_partitioned(
        client, telemetry_daily, PROCESSED_BUCKET, "telemetry_daily", "date"
    )
    print(f"  processed: telemetry_daily ({n_tel} partitions)")
    daily_prod = (
        production_clean.groupby("date", as_index=False)
        .agg(
            total_oil_ton=("oil_ton", "sum"),
            total_gas_m3=("gas_m3", "sum"),
            avg_pressure=("pressure", "mean"),
            avg_temperature=("temperature", "mean"),
            avg_downtime_ratio=("downtime_ratio", "mean"),
        )
    )
    upload_parquet_partitioned(
        client, daily_prod, PROCESSED_BUCKET, "aggregates/daily_production", "date"
    )
    print(f"[{datetime.utcnow().isoformat()}] ETL finished")
if __name__ == "__main__":
    try:
        run_export()
    except Exception as exc:
        print(f"ETL failed: {exc}", file=sys.stderr)
        raise
