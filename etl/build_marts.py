from __future__ import annotations
import io
import json
from datetime import datetime
from pathlib import Path
import boto3
import joblib
import numpy as np
import pandas as pd
from botocore.client import Config
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text
from config import MARTS_BUCKET, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, minio_endpoint_url, postgres_url
MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=minio_endpoint_url(),
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
def upload_df(client, df: pd.DataFrame, key: str) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    client.put_object(Bucket=MARTS_BUCKET, Key=key, Body=buf.getvalue())
def build_mart_production(engine) -> pd.DataFrame:
    q = """
    SELECT
        p.date,
        w.well_id,
        w.name AS well_name,
        w.status,
        p.oil_ton,
        p.downtime_hours,
        p.temperature,
        p.pressure,
        p.energy_kwh,
        ROUND((p.downtime_hours / 24.0)::numeric, 4) AS downtime_ratio
    FROM production p
    JOIN wells w ON w.well_id = p.well_id
    WHERE p.oil_ton > 0
    """
    df = pd.read_sql(text(q), engine)
    kpi = (
        df.groupby(["well_id", "well_name"], as_index=False)
        .agg(
            avg_oil_ton=("oil_ton", "mean"),
            total_oil_ton=("oil_ton", "sum"),
            avg_downtime_pct=("downtime_ratio", "mean"),
            avg_pressure=("pressure", "mean"),
            avg_temperature=("temperature", "mean"),
        )
    )
    kpi["downtime_pct"] = (kpi["avg_downtime_pct"] * 100).round(2)
    daily = df.groupby("date", as_index=False).agg(total_oil_ton=("oil_ton", "sum"))
    return df, kpi, daily
def build_mart_ml(engine) -> tuple[pd.DataFrame, dict]:
    q = """
    SELECT
        t.well_id,
        t.date,
        t.daily_oil_ton,
        COALESCE(AVG(wt.pressure_out), MAX(p.pressure)) AS avg_pressure,
        COALESCE(AVG(wt.temperature), MAX(p.temperature)) AS avg_temperature,
        COALESCE(
            AVG(wt.pump_current * wt.pressure_out / 1000.0),
            MAX(p.energy_kwh) / 24.0
        ) AS power_kw,
        COALESCE(COUNT(wt.record_id), 24 - COALESCE(MAX(p.downtime_hours), 0)) AS pump_hours
    FROM well_targets t
    LEFT JOIN well_telemetry wt
        ON wt.well_id = t.well_id
       AND DATE(wt.timestamp) = t.date
    LEFT JOIN production p
        ON p.well_id = t.well_id
       AND p.date = t.date
    GROUP BY t.well_id, t.date, t.daily_oil_ton
  """
    df = pd.read_sql(text(q), engine)
    features = ["avg_pressure", "avg_temperature", "power_kw", "pump_hours"]
    X = df[features].fillna(df[features].median())
    y = df["daily_oil_ton"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    model = rf if rf.score(X_test, y_test) >= lr.score(X_test, y_test) else lr
    model_name = "random_forest" if model is rf else "linear_regression"
    y_pred = model.predict(X_test)
    metrics = {
        "model": model_name,
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(model.score(X_test, y_test)),
    }
    df["predicted_oil_ton"] = model.predict(X)
    df["error"] = df["daily_oil_ton"] - df["predicted_oil_ton"]
    df["abs_error"] = df["error"].abs()
    joblib.dump(model, MODELS_DIR / "flow_rate_model.joblib")
    (MODELS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return df, metrics
def build_mart_failures(engine) -> pd.DataFrame:
    sensors = pd.read_sql(text("SELECT * FROM pump_sensors"), engine)
    failures = pd.read_sql(text("SELECT * FROM pump_failures"), engine)
    sensors["timestamp"] = pd.to_datetime(sensors["timestamp"])
    failures["failure_date"] = pd.to_datetime(failures["failure_date"])
    feature_cols = ["temperature", "vibration", "current", "rpm", "pressure"]
    X = sensors[feature_cols].fillna(sensors[feature_cols].median())
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    z = np.abs((X - X.mean()) / X.std())
    sensors["zscore_anomaly"] = (z.max(axis=1) > 2.5).astype(int)
    iso = IsolationForest(contamination=0.1, random_state=42)
    sensors["iso_anomaly"] = (iso.fit_predict(Xs) == -1).astype(int)
    sensors["is_anomaly"] = ((sensors["zscore_anomaly"] + sensors["iso_anomaly"]) >= 1).astype(int)
    risk = (
        sensors.groupby("pump_id")
        .agg(
            anomaly_rate=("is_anomaly", "mean"),
            max_vibration=("vibration", "max"),
            avg_temperature=("temperature", "mean"),
        )
        .reset_index()
    )
    risk["risk_score"] = (
        0.5 * risk["anomaly_rate"]
        + 0.3 * (risk["max_vibration"] / (risk["max_vibration"].max() + 1e-6))
        + 0.2 * (risk["avg_temperature"] / (risk["avg_temperature"].max() + 1e-6))
    ).round(4)
    pre_failure = []
    for _, fail in failures.iterrows():
        window_start = fail["failure_date"] - pd.Timedelta(hours=24)
        window = sensors[
            (sensors["pump_id"] == fail["pump_id"])
            & (sensors["timestamp"] >= window_start)
            & (sensors["timestamp"] < fail["failure_date"])
        ]
        if not window.empty:
            pre_failure.append(
                {
                    "pump_id": fail["pump_id"],
                    "failure_date": fail["failure_date"],
                    "failure_type": fail["failure_type"],
                    "avg_vibration": window["vibration"].mean(),
                    "max_vibration": window["vibration"].max(),
                    "avg_temperature": window["temperature"].mean(),
                }
            )
    pre_df = pd.DataFrame(pre_failure)
    sensors_out = sensors.merge(risk[["pump_id", "risk_score"]], on="pump_id", how="left")
    return sensors_out, risk, pre_df, failures
def build_mart_logistics(engine) -> pd.DataFrame:
    q = """
    SELECT
        d.*,
        dr.name AS driver_name,
        dr.experience_years,
        v.plate_number,
        ROUND((d.cost_usd / NULLIF(d.distance_km, 0))::numeric, 2) AS cost_per_km
    FROM deliveries d
    LEFT JOIN drivers dr ON dr.driver_id = d.driver_id
    LEFT JOIN vehicles v ON v.vehicle_id = d.vehicle_id
    """
    df = pd.read_sql(text(q), engine)
    df["is_delayed"] = (df["delay_hours"] > 0).astype(int)
    return df
def write_marts_to_postgres(engine, tables: dict[str, pd.DataFrame]) -> None:
    with engine.begin() as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False)
            print(f"  mart saved: {name} ({len(df)} rows)")
def run() -> None:
    engine = create_engine(postgres_url())
    client = s3_client()
    try:
        client.head_bucket(Bucket=MARTS_BUCKET)
    except Exception:
        client.create_bucket(Bucket=MARTS_BUCKET)
    print(f"[{datetime.utcnow().isoformat()}] Building marts...")
    prod_detail, prod_kpi, prod_daily = build_mart_production(engine)
    ml_df, metrics = build_mart_ml(engine)
    sensors, risk, pre_failure, failures = build_mart_failures(engine)
    logistics = build_mart_logistics(engine)
    marts = {
        "mart_production": prod_kpi,
        "mart_production_daily": prod_daily,
        "mart_production_detail": prod_detail,
        "mart_ml_predictions": ml_df,
        "mart_pump_sensors": sensors,
        "mart_pump_risk": risk,
        "mart_pre_failure": pre_failure,
        "mart_failures": failures,
        "mart_logistics": logistics,
    }
    write_marts_to_postgres(engine, marts)
    upload_df(client, prod_kpi, "mart_production/data.parquet")
    upload_df(client, prod_daily, "mart_production_daily/data.parquet")
    upload_df(client, ml_df, "mart_ml_predictions/data.parquet")
    upload_df(client, risk, "mart_pump_risk/data.parquet")
    upload_df(client, logistics, "mart_logistics/data.parquet")
    print(f"  ML metrics: {metrics}")
    print(f"[{datetime.utcnow().isoformat()}] Marts ready")
if __name__ == "__main__":
    run()
